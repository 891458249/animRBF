# -*- coding: utf-8 -*-
"""Auto-neutral-sample seeding for fresh RBFtools nodes (Milestone 3.6).

============================================================
F0 — CMT 3-pose pattern does NOT map to RBFtools v5
============================================================

A common misreading of Chad Vernon's ``cmt/rig/rbf.py`` is that
``add_neutral_sample=True`` plants three angle-variant samples
(rest / swing / twist). The actual CMT source
(``cmt-master/scripts/cmt/rig/rbf.py:11-48``) shows
``add_neutral_sample`` runs ``add_sample`` three times with the
SAME identity input, varying only the per-sample ``rotationType``
metadata flag (swing / twist / swing_twist).

Three points spell out why the CMT pattern doesn't translate:

  1. CMT's ``rotationType`` is per-sample distance-metric flag,
     NOT input angle variants.
  2. RBFtools v5 hoists the metric to the NODE level
     (``inputEncoding`` from M2.1a/b: Raw / Quat / BendRoll /
     ExpMap / SwingTwist). All samples on a node share one
     encoding.
  3. Therefore the correct RBFtools v5 equivalent is a single
     rest pose. Replicating CMT's literal three-pose would inject
     three identical inputs, mathematically degenerate the kernel
     distance matrix, and trigger the M2.2 PSD guard fallback
     for no benefit.

See addendum §M3.6 F0 for the full analysis.

============================================================
Verify-before-design pattern
============================================================
This module is the third instance of the project's emerging
"verify before designing" pattern, after the M3.0 reverse-then-
reapply commit-split note (addendum §M3.0 appendix) and the
M3.1 F1-F4 helper-behaviour pre-flight check (addendum §M3.1.2).
When a sub-task references third-party behaviour (CMT, AnimaDriver,
Chad Vernon, etc.), the standard procedure is to read the source
directly rather than rely on second-hand descriptions.
"""

from __future__ import absolute_import

import maya.cmds as cmds

from RBFtools import core


# =====================================================================
#  Pure helper — generate_neutral_values
# =====================================================================


def generate_neutral_values(n_outputs, output_is_scale=None,
                            quat_group_starts=None):
    """Build the rest-pose driven-values vector.

    Rules (addendum §M3.6 D.2 + H.2):
      - Default to 0.0 in every slot.
      - Slots flagged ``is_scale=True`` are forced to 1.0.
      - For each quat-group leader index ``s``, slot ``s + 3``
        (the W component) is forced to 1.0 to land on quaternion
        identity ``(0, 0, 0, 1)`` and avoid M2.2 PSD-guard
        fallback on the very first Apply.

    Pure function — no Maya cmds. Unit-tested by T1-T3 (with
    T3.a/b/c covering no-group / single-group / multi-group).
    """
    flags = list(output_is_scale) if output_is_scale else []
    while len(flags) < n_outputs:
        flags.append(False)

    out = [1.0 if flags[i] else 0.0 for i in range(n_outputs)]

    for s in (quat_group_starts or []):
        s = int(s)
        if 0 <= s + 3 < n_outputs:
            out[s + 3] = 1.0  # quaternion W → identity
    return out


# =====================================================================
#  Maya-touching surface — add_neutral_sample
# =====================================================================


def add_neutral_sample(node):
    """Append a single rest pose to *node* at index 0.

    Reads the node's current ``outputQuaternionGroupStart[]`` +
    ``outputIsScale[]`` and uses them to shape the rest values
    (addendum §M3.6 加固): the auto-create path uses the same code
    as the manual button path so a user-pre-set quat_group_starts
    (e.g. from a template-import workflow) is honoured even on
    auto-trigger.

    Does NOT trigger M3.7 alias / M1.2 baseline / M2.3 localXform
    pipelines — those are :func:`core.apply_poses`'s responsibility
    when the user first applies (addendum §M3.6 Q8).

    Returns
    -------
    bool
        True when a rest pose was actually written; False when the
        node already has a pose at index 0 with rest-pose values
        (idempotent guard for the manual button path).
    """
    shape = core.get_shape(node)
    if not core._exists(shape):
        cmds.warning(
            "add_neutral_sample: shape not found for {!r}".format(node))
        return False

    # ---- Read current shape state (single code path, contract 加固) ----
    drv_node, drv_attrs = core.read_driver_info(node)
    drvn_node, drvn_attrs = core.read_driven_info(node)
    n_inputs = len(drv_attrs)
    n_outputs = len(drvn_attrs)
    quat_starts = core.read_quat_group_starts(node)
    baselines = core.read_output_baselines(node)
    output_is_scale = [bool(b[1]) for b in baselines] if baselines else None

    # ---- Build the rest pose ----
    inputs = [0.0] * n_inputs
    values = generate_neutral_values(
        n_outputs, output_is_scale, quat_starts)

    # ---- Idempotent guard: skip if pose[0] already matches ----
    existing = core.read_all_poses(node)
    if existing and core.vector_eq(existing[0].inputs, inputs) and \
       core.vector_eq(existing[0].values, values):
        return False

    # ---- Write pose[0] inside undo_chunk; do NOT touch the
    #      apply pipeline (alias / baseline / localXform are the
    #      Apply step's responsibility — see addendum §M3.6 Q8).
    with core.undo_chunk("RBFtools: add neutral sample"):
        # Insertion semantics (G.3): if there are existing poses, push
        # them by 1 so the rest pose lands at index 0. Caller (the
        # controller) is responsible for the confirm dialog before
        # invoking this in the existing-poses case.
        if existing:
            # Re-pack: rebuild every pose with index += 1 then write
            # the rest pose at 0. Use clear_node_data + per-pose write
            # to keep packed indices contiguous (matches the Apply
            # step's clear-then-write pattern).
            shifted = [
                # Commit 1: index shift preserves per-pose σ.
                core.PoseData(p.index + 1, p.inputs, p.values,
                              radius=getattr(p, "radius", None))
                for p in existing
            ]
            core.clear_node_data(node)
            core._write_pose_to_node(
                shape, 0, core.PoseData(0, inputs, values))
            for p in shifted:
                core._write_pose_to_node(shape, p.index, p)
        else:
            core._write_pose_to_node(
                shape, 0, core.PoseData(0, inputs, values))

    return True
