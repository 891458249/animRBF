# -*- coding: utf-8 -*-
"""Pose Pruner — data-hygiene analysis + execute (Milestone 3.1).

Three classes of prunable redundancy (addendum §M3.1):

  Prune A — duplicate poses
            (input AND value) both equal at abs_tol=1e-6 →
            keep first, mark subsequent for removal.
            (input only) equal but values differ → "conflict pair",
            informational only — NEVER auto-removed (user error
            requires manual review).

  Prune B — redundant driver dimensions
            For each input dim k, if max - min < 1e-6 across all
            poses, the dim contributes nothing to the kernel
            distance. Drop the RBFtools.input[k] reference (NEVER
            modify driver_node).

  Prune C — constant output dimensions
            For each output dim k, if max - min < 1e-6 across all
            poses, the output is a constant function. Drop the
            RBFtools.output[k] reference (NEVER modify driven_node).

Cross-sub-task contracts (addendum §M3.1):

  alias cleanup       — delegated entirely to M3.7
                        ``core.auto_alias_outputs`` (called inside
                        ``apply_poses``). Pruner makes ZERO direct
                        ``cmds.aliasAttr`` calls (T11 source-scan).

  quat group shift    — only the index of unaffected groups is
                        shifted to track the new packed indices;
                        groups whose span overlaps a removed output
                        retain their ORIGINAL start (None marker
                        in the algorithm output is filtered out
                        by execute, leaving the C++ resolver to
                        silently skip the orphan group).

  driver_node /       — NEVER touched. Pruning is a within-node
  driven_node           operation; rig topology is the user's
                        responsibility.

  read-only dry-run   — :func:`analyse_node` does NOT mutate the
                        scene. T13 source-scan permanent guard.
"""

from __future__ import absolute_import

import maya.cmds as cmds

from RBFtools import core


# Default tolerance — single source of truth, mirrors core.float_eq.
_PRUNE_ABS_TOL = 1e-6


class PruneOptions(object):
    """Caller selects which prune classes to run.

    Mirrors the three checkboxes in :class:`PruneDialog`. All False
    means the pruner is a no-op (validated by
    :meth:`PruneAction.has_changes`)."""

    __slots__ = ("duplicates", "redundant_inputs", "constant_outputs")

    def __init__(self, duplicates=True, redundant_inputs=True,
                 constant_outputs=True):
        self.duplicates = bool(duplicates)
        self.redundant_inputs = bool(redundant_inputs)
        self.constant_outputs = bool(constant_outputs)


class QuatGroupEffect(object):
    """One quat-group's after-prune fate.

    Attributes
    ----------
    group_idx : int
        Index into the source ``outputQuaternionGroupStart[]`` array.
    old_start : int
        The leader index before prune.
    new_start : int or None
        Shifted leader index, or None when the group becomes invalid
        (a removed output overlaps the [start, start+3] span). When
        invalid, the C++ resolver silently skips the group.
    invalidated : bool
        Convenience flag — True iff ``new_start is None``.
    """

    __slots__ = ("group_idx", "old_start", "new_start", "invalidated")

    def __init__(self, group_idx, old_start, new_start):
        self.group_idx = int(group_idx)
        self.old_start = int(old_start)
        self.new_start = (None if new_start is None else int(new_start))
        self.invalidated = (new_start is None)


class PruneAction(object):
    """Read-only result of :func:`analyse_node`.

    All ``*_indices`` lists reference indices in the ORIGINAL data
    (before prune). Execute consumes this and reduces it to the
    packed post-prune representation.
    """

    __slots__ = ("duplicate_pose_indices", "conflict_pairs",
                 "redundant_input_indices", "constant_output_indices",
                 "quat_group_effects",
                 "driver_attr_names", "driven_attr_names",
                 "n_poses_before", "n_inputs_before", "n_outputs_before",
                 "cross_source_redundant")

    def __init__(self):
        self.duplicate_pose_indices = []     # list[int] — pose.index values
        self.conflict_pairs = []             # list[(int, int)]
        self.redundant_input_indices = []    # list[int]
        self.constant_output_indices = []    # list[int]
        self.quat_group_effects = []         # list[QuatGroupEffect]
        self.driver_attr_names = []
        self.driven_attr_names = []
        self.n_poses_before = 0
        self.n_inputs_before = 0
        self.n_outputs_before = 0
        # M_B24b2: cross-source attr-name collision report — list of
        # (attr_name, first_source_idx, duplicate_source_idx) tuples.
        self.cross_source_redundant = []

    def has_changes(self):
        """Return True iff at least one prune class would actually do
        something. Conflict pairs alone do NOT count (informational
        only) — the dialog must surface them but a 'Prune' click
        with no other changes is a no-op."""
        return bool(self.duplicate_pose_indices
                    or self.redundant_input_indices
                    or self.constant_output_indices)


# =====================================================================
#  Pure-function helpers (no maya.cmds — fully mockable)
# =====================================================================


def _scan_duplicates(poses, abs_tol=_PRUNE_ABS_TOL):
    """Scan a list of PoseData for (input AND value) duplicates and
    (input-only) conflict pairs.

    Returns
    -------
    (duplicate_indices, conflict_pairs)
        ``duplicate_indices`` is a list of pose.index values to remove
        (kept-first policy). ``conflict_pairs`` is a list of
        ``(idx_a, idx_b)`` where the inputs match but values differ —
        these are NEVER auto-removed.
    """
    dup = []
    conflicts = []
    for i in range(len(poses)):
        pi = poses[i]
        if pi.index in dup:
            continue
        for j in range(i + 1, len(poses)):
            pj = poses[j]
            if pj.index in dup:
                continue
            if not core.vector_eq(pi.inputs, pj.inputs, abs_tol=abs_tol):
                continue
            if core.vector_eq(pi.values, pj.values, abs_tol=abs_tol):
                dup.append(pj.index)
            else:
                conflicts.append((pi.index, pj.index))
    return dup, conflicts


def _scan_redundant_inputs(poses, n_inputs, abs_tol=_PRUNE_ABS_TOL):
    """Return input-dim indices whose value range across all poses is
    below *abs_tol*. Empty list if there are no poses."""
    if not poses:
        return []
    out = []
    for k in range(n_inputs):
        col = [p.inputs[k] for p in poses if k < len(p.inputs)]
        if not col:
            continue
        if max(col) - min(col) < abs_tol:
            out.append(k)
    return out


def _scan_constant_outputs(poses, n_outputs, abs_tol=_PRUNE_ABS_TOL):
    """Return output-dim indices whose value range across all poses is
    below *abs_tol*. Empty list if there are no poses."""
    if not poses:
        return []
    out = []
    for k in range(n_outputs):
        col = [p.values[k] for p in poses if k < len(p.values)]
        if not col:
            continue
        if max(col) - min(col) < abs_tol:
            out.append(k)
    return out


def shift_quat_starts(starts, removed_output_indices):
    """Compute new quat-group start indices after some output indices
    are removed.

    Algorithm:
      For each *start* in *starts*:
        1. If any removed index falls inside [start, start+3], the
           group is INVALIDATED. Output: None (caller filters out
           or preserves the original start per E.2).
        2. Else: the group's leader still points to the SAME logical
           driven attr; only the packed index needs shifting.
           Output: start - count(removed indices < start).

    Pure function — no scene access, no side effects. Unit-tested by
    T_QUAT_GROUP_SHIFT (T4.a-g, permanent guard).

    Parameters
    ----------
    starts : list[int]
    removed_output_indices : iterable[int]

    Returns
    -------
    list[int or None]
        Same length as *starts*; entries are int (shifted index) or
        None (invalidated group).
    """
    rm = sorted(set(int(r) for r in removed_output_indices))
    new = []
    for s in starts:
        s = int(s)
        if any(s <= r <= s + 3 for r in rm):
            new.append(None)
        else:
            new.append(s - sum(1 for r in rm if r < s))
    return new


def _build_quat_group_effects(starts, removed_output_indices):
    """Pair each input *start* with its post-shift outcome and
    package as :class:`QuatGroupEffect` records for the dialog."""
    shifted = shift_quat_starts(starts, removed_output_indices)
    return [QuatGroupEffect(i, s, ns)
            for i, (s, ns) in enumerate(zip(starts, shifted))]


# =====================================================================
#  Maya-touching surface — analyse + execute
# =====================================================================


def analyse_node(node, opts=None):
    """Read-only dry-run analysis (T13 PERMANENT — no mutation).

    Reads the current state of *node* and produces a
    :class:`PruneAction` describing what an execute pass would do.
    The execute is a separate function (:func:`execute_prune`); this
    one MUST NOT touch the scene.

    The T13 source-text guard enforces this invariant by scanning
    for forbidden ``cmds.*`` mutation calls in the function body.
    """
    if opts is None:
        opts = PruneOptions()

    action = PruneAction()
    poses = core.read_all_poses(node)
    # M_B24b2: multi-source aggregation. read_driver_info_multi
    # returns list[DriverSource]; for legacy single-driver nodes the
    # auto-migration in core.py yields a single-element list, so the
    # aggregation reduces to the legacy attrs list byte-equivalent
    # (sanity-tested in test_m_b24b2_downstream.py).
    drv_sources = core.read_driver_info_multi(node)
    drv_attrs = []
    _seen_attr_to_source = {}
    cross_source_redundant = []
    for sidx, src in enumerate(drv_sources):
        for attr in src.attrs:
            if attr in _seen_attr_to_source:
                # M_B24b2 (A.2): same attr name appearing in two or
                # more sources is flagged as cross-source redundant
                # alongside the within-source redundancy detection.
                cross_source_redundant.append(
                    (attr, _seen_attr_to_source[attr], sidx))
            else:
                _seen_attr_to_source[attr] = sidx
            drv_attrs.append(attr)
    _drvn_node, drvn_attrs = core.read_driven_info(node)
    quat_starts = core.read_quat_group_starts(node)

    action.driver_attr_names = list(drv_attrs)
    action.driven_attr_names = list(drvn_attrs)
    action.n_poses_before = len(poses)
    action.n_inputs_before = len(drv_attrs)
    action.n_outputs_before = len(drvn_attrs)
    action.cross_source_redundant = cross_source_redundant

    if opts.duplicates:
        dup, conflicts = _scan_duplicates(poses)
        action.duplicate_pose_indices = dup
        action.conflict_pairs = conflicts
    if opts.redundant_inputs:
        action.redundant_input_indices = _scan_redundant_inputs(
            poses, len(drv_attrs))
    if opts.constant_outputs:
        action.constant_output_indices = _scan_constant_outputs(
            poses, len(drvn_attrs))

    action.quat_group_effects = _build_quat_group_effects(
        quat_starts, action.constant_output_indices)
    return action


def execute_prune(node, action):
    """Apply *action* to *node* by rebuilding the packed pose data.

    Reuses :func:`core.apply_poses` end-to-end (clear → poses →
    baselines → poseLocalTransform → auto-alias → evaluate). The
    only extra step is :func:`core.write_quat_group_starts` for the
    shifted/filtered group list (E.2 keeps invalid group starts
    untouched in the source array — but we must not write None into
    the multi attr; invalid groups are FILTERED OUT of the writeback
    list, which is C++-equivalent to "silent skip".

    Wait — that conflicts with E.2 ("invalid group start preserved").
    Re-reading the contract: E.2 says **the start value is preserved
    on the array element that originally held it**. Since pruner
    rebuilds the array (clear-then-write), preserving means writing
    back the original start value when invalidated, NOT a None marker.
    The C++ resolver still silently skips because the leader span
    overlaps removed outputs which are now PACKED to different
    indices — the original start happens to point at an attr that
    is no longer a quat-friendly driven slot. That is the documented
    "user has been warned, group will be silently skipped" outcome.
    """
    # M_B24b2: same multi-source aggregation as analyse_node — for
    # legacy single-driver nodes the result is byte-equivalent.
    drv_sources_e = core.read_driver_info_multi(node)
    drv_node = drv_sources_e[0].node if drv_sources_e else ""
    drv_attrs = [a for src in drv_sources_e for a in src.attrs]
    drvn_node, drvn_attrs = core.read_driven_info(node)
    poses = core.read_all_poses(node)

    keep_pose = [p for p in poses
                 if p.index not in set(action.duplicate_pose_indices)]
    keep_in = [i for i in range(len(drv_attrs))
               if i not in set(action.redundant_input_indices)]
    keep_out = [i for i in range(len(drvn_attrs))
                if i not in set(action.constant_output_indices)]

    new_drv_attrs = [drv_attrs[i] for i in keep_in]
    new_drvn_attrs = [drvn_attrs[i] for i in keep_out]
    new_poses = []
    for new_idx, p in enumerate(keep_pose):
        # Commit 1: prune rebuild preserves per-pose σ for the surviving
        # poses (driver/driven attr columns are pruned; the pose's own
        # influence radius is unaffected).
        new_poses.append(core.PoseData(
            new_idx,
            [p.inputs[i] for i in keep_in],
            [p.values[i] for i in keep_out],
            radius=getattr(p, "radius", None)))

    # E.2 contract: invalid quat groups keep their ORIGINAL start.
    # Unaffected groups get the shifted index. Filtered out: nothing
    # — every effect maps to one writeback entry.
    quat_writeback = []
    for eff in action.quat_group_effects:
        if eff.invalidated:
            quat_writeback.append(eff.old_start)  # E.2 preserve
        else:
            quat_writeback.append(eff.new_start)

    with core.undo_chunk("RBFtools: prune poses"):
        core.apply_poses(node, drv_node, drvn_node,
                         new_drv_attrs, new_drvn_attrs, new_poses)
        core.write_quat_group_starts(node, quat_writeback)

    return {
        "removed_poses": len(action.duplicate_pose_indices),
        "removed_inputs": len(action.redundant_input_indices),
        "removed_outputs": len(action.constant_output_indices),
        "kept_poses": len(new_poses),
        "kept_inputs": len(new_drv_attrs),
        "kept_outputs": len(new_drvn_attrs),
        "invalidated_quat_groups": sum(
            1 for eff in action.quat_group_effects if eff.invalidated),
    }
