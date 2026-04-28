# -*- coding: utf-8 -*-
"""
Core business layer — scene topology, RBF builder, pose management.

Phase breakdown
---------------
* **Phase 1** — :func:`undo_chunk` context manager.
* **Phase 2a** — plugin env, DAG topology, attribute filtering,
  connection tracing, node CRUD, driver/driven wiring, radius math.
* **Phase 2b** — :class:`PoseData` dataclass, multi-instance attribute
  CRUD (read / write / recall / delete), ``apply_poses``,
  ``connect_poses``, floating-point tolerance utility.

Design contracts
----------------
* **Zero UI imports** — runs in ``mayapy`` headless mode.
* Every scene-mutating public function wrapped in :func:`undo_chunk`.
* Defensive: all ``cmds.getAttr`` / ``connectAttr`` guarded.
* **Float comparison** via :func:`float_eq` (``math.isclose``).
"""

from __future__ import absolute_import

import contextlib
import math
import re
import warnings
from dataclasses import dataclass

import maya.cmds as cmds


# =====================================================================
#  M_B24a2-1 — Multi-source driver public API + dataclass
# =====================================================================

# Module-level per-session flag for legacy migration warning. Reset to
# False at module reload; first migration sets True so subsequent
# legacy-node loads stay quiet. Pure-python tests reset via monkeypatch.
_MIGRATION_WARNING_ISSUED = False


@dataclass(frozen=True)
class DriverSource:
    """Per-driver companion metadata for the M_B24 multi-source schema.

    Mirrors C++ ``driverSource[d]`` compound (see RBFtools.h M_B24a1).
    Frozen for safety; ``attrs`` is a tuple (not list) to satisfy
    immutability. Construct from a list via ``tuple(attrs_list)``.

    encoding values match inputEncoding enum:
        0 = Raw, 1 = Quaternion, 2 = BendRoll, 3 = ExpMap, 4 = SwingTwist
    """
    node: str
    attrs: tuple
    weight: float = 1.0
    encoding: int = 0

    def __post_init__(self):
        if self.weight < 0.0:
            raise ValueError(
                "DriverSource.weight must be >= 0, got {}".format(self.weight))
        if self.encoding not in (0, 1, 2, 3, 4):
            raise ValueError(
                "DriverSource.encoding must be 0..4, got {}".format(
                    self.encoding))

from RBFtools.constants import (
    PLUGIN_NAME,
    NODE_TYPE,
    FILTER_DEFAULTS,
    FILTER_VAR_TEMPLATE,
    SCALE_ATTR_NAMES,
    DEFAULT_POSE_RADIUS,
)


# =====================================================================
#  Phase 1 — undo infrastructure  (reviewed & approved)
# =====================================================================

@contextlib.contextmanager
def undo_chunk(name="RBFtools"):
    """Context manager that groups enclosed scene edits into one undo.

    Usage::

        with undo_chunk("RBFtools: create node"):
            cmds.createNode("RBFtools")
            cmds.setAttr("RBFtools1.type", 1)

    Parameters
    ----------
    name : str
        Label for Maya *Edit ▸ Undo* menu.

    Notes
    -----
    * ``finally`` guarantees ``closeChunk`` even on exception.
    * Re-entrant safe: Maya collapses nested chunks into the outermost.
    """
    cmds.undoInfo(openChunk=True, chunkName=name)
    try:
        yield
    finally:
        cmds.undoInfo(closeChunk=True)


# =====================================================================
#  1. Plugin & environment
# =====================================================================

def ensure_plugin():
    """Load the RBFtools plugin if it is not already loaded.

    Safe to call repeatedly — short-circuits when the plugin is active.
    """
    if not cmds.pluginInfo(PLUGIN_NAME, query=True, loaded=True):
        cmds.loadPlugin(PLUGIN_NAME)


# =====================================================================
#  2. DAG topology helpers
# =====================================================================

def _exists(node):
    """Return *True* if *node* is a non-empty string that exists in the scene."""
    return bool(node) and cmds.objExists(node)


def get_shape(node):
    """Resolve *node* to its shape.

    * If *node* is already a shape → return as-is.
    * If *node* is a transform → return its first child shape.
    * If *node* does not exist → return the string unchanged
      (caller will handle the missing-node case).

    .. note::
       RBFtools is a locator shape that lives under a transform.
       The hierarchy is: ``transform  →  RBFtoolsShape``.
    """
    if not _exists(node):
        return node
    if cmds.nodeType(node) == "transform":
        shapes = cmds.listRelatives(node, shapes=True, fullPath=False) or []
        if shapes:
            return shapes[0]
    return node


def get_transform(node):
    """Resolve *node* to its parent transform.

    * If *node* is a ``RBFtools`` shape → return its parent.
    * Otherwise → return as-is.
    """
    if not _exists(node):
        return node
    if cmds.nodeType(node) == NODE_TYPE:
        parents = cmds.listRelatives(node, parent=True, fullPath=False) or []
        if parents:
            return parents[0]
    return node


def list_all_nodes():
    """Return the transform names of every ``RBFtools`` node in the scene.

    Duplicate-safe **and** order-stable: uses ``dict.fromkeys()`` which
    is insertion-ordered in Python 3.7+ (and CPython 3.6+).
    ``cmds.ls`` returns a deterministic scene-order, and
    ``dict.fromkeys`` preserves that order while eliminating duplicates
    caused by multiple shapes under the same transform.
    """
    ensure_plugin()
    shapes = cmds.ls(type=NODE_TYPE) or []
    return list(dict.fromkeys(get_transform(s) for s in shapes))


# =====================================================================
#  3. Safe attribute access
# =====================================================================

def safe_get(attr_path, default=0):
    """``cmds.getAttr`` with a fallback.

    Parameters
    ----------
    attr_path : str
        Fully qualified plug, e.g. ``"RBFtools1.type"``.
    default
        Returned if the attribute does not exist or the query fails.
    """
    try:
        return cmds.getAttr(attr_path)
    except Exception:
        return default


def set_node_attr(node, attr, value):
    """Set a single scalar attribute on the **shape** under *node*.

    Wraps the operation in an :func:`undo_chunk` so the user can
    revert individual slider drags.

    Parameters
    ----------
    node : str
        Transform **or** shape name.
    attr : str
        Short attribute name (e.g. ``"type"``, ``"angle"``).
    value
        The new value (bool / int / float).
    """
    shape = get_shape(node)
    if not _exists(shape):
        return
    plug = "{}.{}".format(shape, attr)
    with undo_chunk("RBFtools: set {}".format(attr)):
        try:
            cmds.setAttr(plug, value)
        except Exception as exc:
            cmds.warning("Cannot set {}: {}".format(plug, exc))


def set_node_multi_attr(node, attr, list_values, max_length=10000):
    """Transactional write to a Maya multi-instance attribute on *node*.

    Strategy (v5 addendum §M2.4a — refinement 2):

    1. Wrap in :func:`undo_chunk` so a partial-write failure rolls back
       cleanly via Ctrl+Z.
    2. **Clear all existing indices first** (``removeMultiInstance``),
       then write new values in order. Avoids the half-old / half-new
       hybrid that destination-only ``setAttr`` would leave on failure.
    3. Length cap (default 10000) prevents an oversized list from
       deadlocking the DG; emit warning + truncate.
    4. Per-index ``setAttr`` failure issues a warning but does NOT
       attempt partial recovery — the surrounding ``undo_chunk`` is
       the canonical rollback.

    Parameters
    ----------
    node : str
        Transform or shape name.
    attr : str
        Short multi-attr name (e.g. ``"outputQuaternionGroupStart"``,
        ``"driverInputRotateOrder"``).
    list_values : list
        Ordered values to write at indices 0..len-1. Empty list is
        equivalent to clearing the multi.
    max_length : int
        Safety cap. Lists longer than this are truncated with a warning.
    """
    shape = get_shape(node)
    if not _exists(shape):
        return

    if not isinstance(list_values, (list, tuple)):
        cmds.warning(
            "set_node_multi_attr: list_values must be list/tuple; "
            "got {}".format(type(list_values).__name__))
        return

    if len(list_values) > max_length:
        cmds.warning(
            "set_node_multi_attr: {} values exceeds cap {}; truncating. "
            "If this is legitimate, raise max_length explicitly.".format(
                len(list_values), max_length))
        list_values = list(list_values)[:max_length]

    base = "{}.{}".format(shape, attr)
    with undo_chunk("RBFtools: set multi {}".format(attr)):
        # Step 1: clear existing indices.
        try:
            existing = cmds.getAttr(base, multiIndices=True) or []
        except Exception:
            existing = []
        for idx in existing:
            try:
                cmds.removeMultiInstance("{}[{}]".format(base, idx), b=True)
            except Exception as exc:
                cmds.warning(
                    "set_node_multi_attr: removeMultiInstance "
                    "{}[{}] failed: {}".format(base, idx, exc))

        # Step 2: write new values 0..len-1.
        for i, v in enumerate(list_values):
            plug = "{}[{}]".format(base, i)
            try:
                cmds.setAttr(plug, v)
            except Exception as exc:
                cmds.warning(
                    "set_node_multi_attr: setAttr {} failed: {}; "
                    "undo_chunk will roll back.".format(plug, exc))


def get_all_settings(node):
    """Bulk-read every UI-relevant attribute from *node* → ``dict``.

    Returns ``None`` when the node is empty or does not exist so the
    UI layer can skip population.

    The returned dict keys match the C++ short attribute names exactly.
    """
    if not _exists(node):
        return None
    shape = get_shape(node)
    if not _exists(shape):
        return None

    g = safe_get  # local alias for readability

    return {
        # General
        "active":               g(shape + ".active",               True),
        "type":                 g(shape + ".type",                 0),
        "iconSize":             g(shape + ".iconSize",             1.0),
        # Vector Angle
        "direction":            g(shape + ".direction",            0),
        "invert":               g(shape + ".invert",               False),
        "useRotate":            g(shape + ".useRotate",            True),
        "angle":                g(shape + ".angle",                45.0),
        "centerAngle":          g(shape + ".centerAngle",          0.0),
        "twist":                g(shape + ".twist",                False),
        "twistAngle":           g(shape + ".twistAngle",           90.0),
        "useTranslate":         g(shape + ".useTranslate",         False),
        "grow":                 g(shape + ".grow",                 False),
        "translateMin":         g(shape + ".translateMin",         0.0),
        "translateMax":         g(shape + ".translateMax",         0.0),
        "interpolation":        g(shape + ".interpolation",        0),
        "drawCone":             g(shape + ".drawCone",             True),
        "drawCenterCone":       g(shape + ".drawCenterCone",       False),
        "drawWeight":           g(shape + ".drawWeight",           False),
        # RBF
        "kernel":               g(shape + ".kernel",               1),
        "radiusType":           g(shape + ".radiusType",           0),
        "radius":               g(shape + ".radius",               0.0),
        "allowNegativeWeights": g(shape + ".allowNegativeWeights", True),
        "scale":                g(shape + ".scale",                1.0),
        "rbfMode":              g(shape + ".rbfMode",              0),
        "distanceType":         g(shape + ".distanceType",         0),
        "twistAxis":            g(shape + ".twistAxis",            0),
        # Solver display
        "drawOrigin":           g(shape + ".drawOrigin",           False),
        "drawPoses":            g(shape + ".drawPoses",            False),
        "poseLength":           g(shape + ".poseLength",           1.0),
        "drawIndices":          g(shape + ".drawIndices",          False),
        "indexDistance":         g(shape + ".indexDistance",         0.0),
        "drawTwist":            g(shape + ".drawTwist",            False),
        "opposite":             g(shape + ".opposite",             False),
        "driverIndex":          g(shape + ".driverIndex",          0),
    }


# =====================================================================
#  4. Attribute filtering (for pose-editor lists)
# =====================================================================

def _filter_var_name(role, key):
    """Expand the optionVar name template.

    >>> _filter_var_name("driver", "Keyable")
    'RBFtools_filter_driver_Keyable'
    """
    return FILTER_VAR_TEMPLATE.format(role=role, key=key)


def get_filter_state(role, key):
    """Read one filter toggle from Maya optionVars.

    Falls back to :data:`FILTER_DEFAULTS` when the var does not exist.
    """
    var = _filter_var_name(role, key)
    if cmds.optionVar(exists=var):
        return cmds.optionVar(query=var)
    return FILTER_DEFAULTS.get(key, 0)


def set_filter_state(role, key, value):
    """Persist one filter toggle to Maya optionVars."""
    cmds.optionVar(iv=(_filter_var_name(role, key), int(value)))


# =====================================================================
#  Confirm-dialog optionVar persistence — Milestone 3.0
# =====================================================================
# Centralised here (alongside filter persistence) per addendum §M3.0
# soft-suggestion: all optionVar persistence lives in core.py so the
# i18n / MVC scanners always find a single owner. ConfirmDialog imports
# these via lazy `from RBFtools import core` inside its classmethod.

CONFIRM_OPT_VAR_TEMPLATE = "RBFtools_skip_confirm_{action_id}"


def should_show_confirm_dialog(action_id):
    """Return ``True`` iff the user has NOT silenced this action via
    "Don't ask again". Pure function — testable through mocked
    :func:`cmds.optionVar`.

    Parameters
    ----------
    action_id : str
        snake_case identifier of the action (e.g. ``"prune_poses"``).
        Maps to optionVar ``RBFtools_skip_confirm_<action_id>`` per
        addendum §M3.0 naming contract.
    """
    var = CONFIRM_OPT_VAR_TEMPLATE.format(action_id=action_id)
    if not cmds.optionVar(exists=var):
        return True
    return not bool(cmds.optionVar(query=var))


def set_skip_confirm(action_id, skip):
    """Persist the "Don't ask again" preference for *action_id*."""
    var = CONFIRM_OPT_VAR_TEMPLATE.format(action_id=action_id)
    cmds.optionVar(iv=(var, int(bool(skip))))


def reset_all_skip_confirms():
    """Clear every ``RBFtools_skip_confirm_*`` optionVar.

    Backed by the ``Tools → Reset confirm dialogs`` menu item per
    addendum §M3.0 (a one-click escape hatch — there is intentionally
    no "are you sure" dialog because the act of selecting the menu
    item already constitutes user intent).
    """
    prefix = "RBFtools_skip_confirm_"
    names = cmds.optionVar(list=True) or []
    for name in names:
        if name.startswith(prefix):
            cmds.optionVar(remove=name)


# =====================================================================
#  Rig role selection — Milestone 3.0
# =====================================================================


# =====================================================================
#  Mirror Tool orchestrator — Milestone 3.2
# =====================================================================
# Wires the pure mirror math (core_mirror) into actual node creation
# under a single undo_chunk. Called by controller.mirror_current_node;
# never imported by widgets directly (MVC red line).


def mirror_node(source_node, target_name, mirror_axis,
                naming_rule_index, custom_naming=None,
                naming_direction="auto",
                progress=None,
                overwrite=False):
    """Create a mirrored copy of *source_node* under *target_name*.

    Behaviour (addendum §M3.2.4, §M3.2.9):

    * Wraps the entire operation in one ``undo_chunk`` so a mid-flight
      failure rolls back via Maya undo without leaving an orphan node.
    * Resolves driver / driven node names via *naming_rule_index*.
      Missing R-side targets emit warnings; the orchestrator continues
      with the L-side names so the user can fix wiring after the fact.
    * Mirrors every pose's driver inputs + driven values + M2.3
      ``poseLocalTransform`` per the inputEncoding / Maya raw-attr rules.

    Parameters
    ----------
    source_node : str
        Source RBFtools transform name.
    target_name : str
        Desired target node name (caller has already resolved this
        via ``apply_naming_rule``; passed in to avoid re-running the
        regex inside the orchestrator).
    mirror_axis : int
        0=X (YZ plane), 1=Y, 2=Z.
    naming_rule_index : int
        Used to mirror driver/driven node names.
    custom_naming : tuple[str, str] or None
        Custom regex pair when naming_rule_index == CUSTOM_RULE_INDEX.
    naming_direction : str
        "auto" / "forward" / "reverse" — passed through to
        ``apply_naming_rule`` for driver/driven name remap.
    progress : StatusProgressController or None
        Optional progress feedback (may be None in headless / test).
    overwrite : bool
        When True and target already exists, delete it first. The
        controller is responsible for asking the user via path A
        confirm dialog; the orchestrator only honours the flag.

    Returns
    -------
    dict
        ``{"target": str, "status": str, "warnings": list[str]}``.
        ``status`` ∈ {"created", "overwrote", "skipped", "failed"}.
        Failures raise; never returned silently.
    """
    from RBFtools import core_mirror

    warnings = []
    source_shape = get_shape(source_node)
    enc = safe_get(source_shape + ".inputEncoding", 0) \
        if _exists(source_shape) else 0
    twist_axis = safe_get(source_shape + ".twistAxis", 0) \
        if _exists(source_shape) else 0

    # M_B24c (Hardening 2): Matrix-mode multi-source mirror is DEFERRED
    # to v5.x post-final M_B24c2. Hard guard at the engine entry so we
    # never depend on the controller-layer dialog being honoured. See
    # addendum §M_B24c.matrix-mode-still-deferred + §M_B24c2-stub.
    # Probe wrapped in try/except: when safe_get is mocked to return
    # non-int values in test fixtures we conservatively treat the node
    # as non-Matrix (the Generic-mode mirror path is the legacy default).
    try:
        _src_is_matrix = (
            _exists(source_shape) and _is_matrix_mode(source_shape))
    except Exception:
        _src_is_matrix = False
    if _src_is_matrix:
        _matrix_sources = read_driver_info_multi(source_node)
        if len(_matrix_sources) > 1:
            raise NotImplementedError(
                "RBFtools: Matrix-mode multi-source mirror is DEFERRED "
                "to v5.x post-final M_B24c2. Source node {!r} is in "
                "Matrix mode (type=1 + rbfMode=1) and has {} driver "
                "sources. Either: (1) reduce to single source via "
                "remove_driver_source(), (2) switch node to Generic "
                "mode (rbfMode=0), or (3) wait for M_B24c2. See "
                "addendum §M_B24c2-stub.".format(
                    source_node, len(_matrix_sources)))

    # Read source node's current state up-front so we don't mutate it.
    source_settings = get_all_settings(source_node) or {}
    source_poses = read_all_poses(source_node)
    source_local_xforms = read_pose_local_transforms(source_node)

    # Resolve multi-source driver list (M_B24c) + single driven via
    # name remap. read_driver_info_multi returns >= 1 entries when the
    # node has ANY wiring (legacy single-driver auto-migrates to a
    # 1-source list via _migrate_legacy_single_driver).
    sources = read_driver_info_multi(source_node)
    src_driven, src_driven_attrs = read_driven_info(source_node)

    # Per-source naming remap with F.1 fallback (source keeps original
    # name + warning; mirror does NOT abort).
    remapped = []   # list of (DriverSource, new_name)
    for s in sources:
        if not s.node:
            remapped.append((s, ""))
            continue
        new_name, dr_status = core_mirror.apply_naming_rule(
            s.node, naming_rule_index, custom_naming, naming_direction)
        if dr_status not in ("ok", "both_match"):
            warnings.append(
                "Driver name remap failed for source {!r} ({}): using "
                "original name".format(s.node, dr_status))
            new_name = s.node
        if dr_status == "both_match":
            warnings.append(
                "Driver name {!r} matches BOTH directions — using "
                "forward".format(s.node))
        remapped.append((s, new_name))

    new_driven_name, dn_status = (
        core_mirror.apply_naming_rule(
            src_driven, naming_rule_index, custom_naming,
            naming_direction)
        if src_driven else (src_driven, "no_match"))
    if src_driven and dn_status not in ("ok", "both_match"):
        warnings.append(
            "Driven name remap failed ({}): using source name {!r}".format(
                dn_status, src_driven))
        new_driven_name = src_driven

    # Flat concat of all sources' attrs - matches the
    # input[base+i]/poseInput[i] order produced by add_driver_source
    # appends. Used by apply_poses for auto_alias_outputs slot
    # alignment (single-source legacy case yields the same flat list).
    flat_driver_attrs = []
    for s in sources:
        flat_driver_attrs.extend(s.attrs)

    # Mirror each pose. For Generic mode multi-source we slice
    # pose.inputs by each source's attr count and run
    # mirror_driver_inputs per source so each source's encoding is
    # honoured (M_B24c (A.3) source-by-source semantic).
    mirrored_poses = []
    for pose in source_poses:
        new_inputs = []
        cursor = 0
        for s, _new_name in remapped:
            n_slot = len(s.attrs)
            slice_in = list(pose.inputs[cursor:cursor + n_slot])
            slice_out, in_status = core_mirror.mirror_driver_inputs(
                slice_in, int(s.encoding), mirror_axis,
                driver_attrs=list(s.attrs))
            new_inputs.extend(slice_out)
            cursor += n_slot
            if in_status.get("unsupported_encoding"):
                warnings.append(
                    "BendRoll inputEncoding on source {!r}: driver "
                    "inputs NOT mirrored (addendum §M3.2 (E)). User "
                    "must verify pose data.".format(s.node))
            for nm in in_status.get("unrecognized_attrs", []):
                warnings.append(
                    "Unrecognized driver attr {!r} on source {!r} — "
                    "passed through unchanged".format(nm, s.node))
        # Tail beyond known sources (defensive: if pose.inputs is
        # longer than the concat of source.attrs, preserve the tail
        # untouched so we never silently lose data).
        if cursor < len(pose.inputs):
            new_inputs.extend(pose.inputs[cursor:])
        new_values, unrec = core_mirror.mirror_driven_values(
            list(pose.values), src_driven_attrs, mirror_axis)
        for nm in unrec:
            warnings.append("Unrecognized driven attr {!r} — passed "
                            "through unchanged".format(nm))
        # Commit 1: mirroring preserves per-pose σ (independent of
        # axis flips on the driven side).
        new_pose = PoseData(pose.index, new_inputs, new_values,
                            radius=getattr(pose, "radius",
                                           DEFAULT_POSE_RADIUS))
        mirrored_poses.append(new_pose)

    # Mirror per-pose local Transforms (M2.3 contract).
    mirrored_local_xforms = [
        core_mirror.mirror_pose_local_transform(xf, mirror_axis)
        for xf in source_local_xforms
    ]

    # Begin orchestration under undo_chunk. Failure mid-way rolls back.
    if progress is not None:
        progress.begin("Mirror: starting...")
    overwrote = False
    with undo_chunk("RBFtools: mirror node"):
        try:
            # Step 1: handle target conflict.
            if _exists(target_name):
                if not overwrite:
                    raise RuntimeError(
                        "Target node {!r} already exists and overwrite "
                        "flag is False".format(target_name))
                delete_node(target_name)
                overwrote = True

            # Step 2: create target.
            if progress is not None:
                progress.step(1, 4, "Mirror: creating target node")
            target = create_node()
            target = cmds.rename(target, target_name)

            # Step 3: copy source attrs (kernel / radius / etc.) onto
            # target, EXCLUDING driver/driven wiring (re-done in step 4).
            if progress is not None:
                progress.step(2, 4, "Mirror: copying node settings")
            _copy_node_settings(source_settings, target)

            # Step 4: write mirrored poses. Driver-side wiring is
            # handled per-source via add_driver_source in Step 6
            # (M_B24c (E.3) write-side reuse), so we pass an empty
            # driver_node here. apply_poses still uses
            # flat_driver_attrs for input[]/poseInput[i] slot
            # alignment + auto_alias_outputs.
            if progress is not None:
                progress.step(3, 4, "Mirror: writing poses")
            new_dn_attrs = (
                list(src_driven_attrs) if src_driven_attrs else [])

            apply_poses(target, "", new_driven_name,
                        list(flat_driver_attrs), new_dn_attrs,
                        mirrored_poses)

            # Step 5: write mirrored local-Transform snapshots
            # (apply_poses already calls capture_per_pose_local_transforms
            # via replay; that overwrites whatever we passed in. We
            # explicitly RE-write the mirrored versions here so the
            # M2.3 double-storage stays consistent with the mirrored
            # poseValue rather than with whatever the live driven_node
            # state was at apply-time).
            from RBFtools import core as _self_core   # noqa: F401
            try:
                write_pose_local_transforms(target, mirrored_local_xforms)
            except Exception as exc:
                warnings.append(
                    "poseLocalTransform mirror write failed: {}".format(exc))

            # Step 6 (M_B24c (E.3)): wire driven side + iterate per-
            # source add_driver_source on driver side. Reuses the
            # M_B24d / M_B24d_matrix_followup atomic + mode-exclusion
            # + worldMatrix wiring rather than re-implementing
            # legacy connect_node single-driver path.
            if new_driven_name and _exists(new_driven_name):
                wire_driven_outputs(target, new_driven_name, new_dn_attrs)
            else:
                warnings.append(
                    "Target driven {!r} not found in scene; "
                    "node created without driven connections.".format(
                        new_driven_name))
            wired_any_driver = False
            for s, new_name in remapped:
                if not new_name:
                    continue
                if not _exists(new_name):
                    warnings.append(
                        "Target driver source {!r} not found in scene; "
                        "skipped wiring.".format(new_name))
                    continue
                try:
                    add_driver_source(target, new_name, list(s.attrs),
                                      float(s.weight), int(s.encoding))
                    wired_any_driver = True
                except Exception as exc:
                    warnings.append(
                        "add_driver_source failed for {!r}: {}".format(
                            new_name, exc))
            if not wired_any_driver and remapped:
                warnings.append(
                    "No driver sources wired on target; node created "
                    "without driver connections.")

            if progress is not None:
                progress.step(4, 4, "Mirror: done")

            return {
                "target": target,
                "status": "overwrote" if overwrote else "created",
                "warnings": warnings,
            }
        except Exception as exc:
            if progress is not None:
                progress.end("Mirror: failed — {}".format(exc))
            raise


def _copy_node_settings(source_settings, target):
    """Copy non-pose attrs from a settings dict onto *target*.

    Skips attrs that the apply_poses pipeline manages (poses, baseline,
    poseLocalTransform compound, driver/driven multis). Used by
    :func:`mirror_node` to clone kernel / radius / encoding / clamp
    config from the source node.
    """
    skip = {
        "type", "rbfMode", "evaluate",     # mode + trigger
        # Pose-pipeline attrs are handled by apply_poses / mirror code:
        # poses[], baseValue[], outputIsScale[], poseLocalTransform[],
        # outputQuaternionGroupStart[].
    }
    for k, v in (source_settings or {}).items():
        if k in skip:
            continue
        try:
            set_node_attr(target, k, v)
        except Exception:
            # Non-fatal — settings the target's schema doesn't know
            # about (e.g. a future v6 attr) just get dropped.
            pass


def select_rig_for_node(node, role):
    """Select the driver or driven scene object connected to *node*.

    Composes the existing :func:`read_driver_info` /
    :func:`read_driven_info` helpers with ``cmds.select`` — M3.x tools
    (Mirror, Profiler, etc.) need this one-step "show me the rig" UX
    primitive without each tool re-implementing the connection lookup.

    Parameters
    ----------
    node : str
        Transform or shape of an RBFtools node.
    role : str
        ``"driver"`` or ``"driven"``. Anything else emits a warning
        and no-ops.
    """
    if role == "driver":
        target, _attrs = read_driver_info(node)
    elif role == "driven":
        target, _attrs = read_driven_info(node)
    else:
        cmds.warning(
            "select_rig_for_node: invalid role {!r}".format(role))
        return
    if target and _exists(target):
        cmds.select(target, replace=True)


def get_all_filters(role):
    """Return the complete filter dict for *role* (``'driver'`` / ``'driven'``)."""
    return {k: get_filter_state(role, k) for k in FILTER_DEFAULTS}


def list_filtered_attributes(node, filters):
    """Return attribute names from *node* respecting the *filters* dict.

    Parameters
    ----------
    node : str
        Scene node to query (e.g. ``"pSphere1"``).
    filters : dict
        ``{filter_key: 0|1}`` — same structure as :data:`FILTER_DEFAULTS`.

    Returns
    -------
    list[str]
        Clean attribute names.  Indexed multi entries (``attr[0]``) and
        compound children (``translate.translateX``) are stripped.

    .. warning::
       **Never** pass ``multi=True`` to ``cmds.listAttr``.
       It expands indexed multi-instance plugs and produces thousands of
       entries on complex nodes (deformers, blend shapes), causing Maya
       to freeze.  See historical bug report in the project summary.
    """
    if not _exists(node):
        return []

    f_keyable    = filters.get("Keyable",    1)
    f_nonkeyable = filters.get("NonKeyable", 0)
    f_readable   = filters.get("Readable",   1)
    f_writable   = filters.get("Writable",   1)
    f_connected  = filters.get("Connected",  0)
    f_hidden     = filters.get("Hidden",     0)
    f_userdef    = filters.get("UserDefined", 0)

    # ----- Build listAttr keyword flags -----
    kw = {}
    if f_keyable and not f_nonkeyable:
        kw["keyable"] = True
    if f_readable:
        kw["read"] = True
    if f_writable:
        kw["write"] = True
    if f_hidden:
        kw["hidden"] = True
    if f_userdef:
        kw["userDefined"] = True

    raw = cmds.listAttr(node, **kw) or []

    # ----- Strip multi-indices and compound children -----
    # "weight[0]" → skip (indexed multi)
    # "translate.translateX" → skip (compound child path)
    attrs = [a for a in raw if "[" not in a and "." not in a]

    # ----- Post-filter: connected only -----
    if f_connected:
        conns = cmds.listConnections(
            node, plugs=True, connections=True,
            skipConversionNodes=True) or []
        connected = set()
        for i in range(0, len(conns), 2):
            connected.add(conns[i].split(".")[-1])
        attrs = [a for a in attrs if a in connected]

    # ----- Post-filter: non-keyable (exclude keyable) -----
    if f_nonkeyable and not f_keyable:
        keyable_set = set(cmds.listAttr(node, keyable=True) or [])
        attrs = [a for a in attrs if a not in keyable_set]

    return attrs


# =====================================================================
#  5. Connection tracing — driver / driven discovery
# =====================================================================

def _read_legacy_input_connections(node):
    """Internal: trace <shape>.input[i] connections, single-driver
    legacy semantics. Returns (first_driver, [attrs]) — same shape as
    the legacy read_driver_info."""
    shape = get_shape(node)
    if not _exists(shape):
        return "", []
    conns = cmds.listConnections(
        shape + ".input",
        source=True, destination=False,
        plugs=True, connections=True,
        skipConversionNodes=True,
    ) or []
    driver = ""
    attrs = []
    for i in range(0, len(conns), 2):
        src_plug = conns[i + 1]
        parts = src_plug.split(".")
        if not driver:
            driver = parts[0]
        if len(parts) > 1:
            attrs.append(parts[1])
    return driver, attrs


def _migrate_legacy_single_driver(node):
    """Detect a v5.0-pre-M_B24 single-driver node and migrate it to the
    M_B24 multi-source schema (write driverSource[0] from existing
    input[] connections). Fail-soft per addendum 加固 4: returns the
    legacy tuple even if the migration write fails, so callers never
    break. Best-effort.

    Returns
    -------
    (str, list[str])
        Legacy tuple — same shape as :func:`read_driver_info`.
    """
    global _MIGRATION_WARNING_ISSUED
    try:
        legacy_node, legacy_attrs = _read_legacy_input_connections(node)
        if not legacy_node:
            return ("", [])
        shape = get_shape(node)
        if not _exists(shape):
            return (legacy_node, legacy_attrs)
        # Detect: has the migration already run? Check if
        # driverSource[0].driverSource_node has an incoming connection
        # OR driverSource_attrs default differs from empty.
        already = False
        try:
            srcs = cmds.listConnections(
                shape + ".driverSource[0].driverSource_node",
                source=True, destination=False) or []
            already = bool(srcs)
        except Exception:
            already = False
        if already:
            return (legacy_node, legacy_attrs)
        # Best-effort migration write.
        try:
            cmds.connectAttr(
                legacy_node + ".message",
                shape + ".driverSource[0].driverSource_node",
                force=True)
            cmds.setAttr(
                shape + ".driverSource[0].driverSource_attrs",
                len(legacy_attrs), *legacy_attrs, type="stringArray")
            cmds.setAttr(
                shape + ".driverSource[0].driverSource_weight", 1.0)
            cmds.setAttr(
                shape + ".driverSource[0].driverSource_encoding", 0)
            if not _MIGRATION_WARNING_ISSUED:
                cmds.warning(
                    "RBFtools: Legacy single-driver schema detected on "
                    "'{}'. Migrated to multi-source driverSource[0]. "
                    "See addendum #M_B24a2.".format(node))
                _MIGRATION_WARNING_ISSUED = True
        except Exception as exc:
            cmds.warning(
                "RBFtools: Migration failed on '{}': {}. Continuing "
                "with legacy schema.".format(node, exc))
        return (legacy_node, legacy_attrs)
    except Exception:
        return ("", [])


def read_driver_info_multi(node):
    """Discover all drivers + per-source metadata on a M_B24 node.

    Returns a list of :class:`DriverSource` objects. Empty list if no
    drivers are connected. For legacy v5.0-pre-M_B24 nodes (no
    driverSource[]), the function calls
    :func:`_migrate_legacy_single_driver` so the read returns the
    migrated single-element list seamlessly.

    Connection topology (M_B24)::

        driverSource[d].driverSource_node    <- driver.message
        driverSource[d].driverSource_attrs    = [attr1, attr2, ...]
        driverSource[d].driverSource_weight   = 1.0
        driverSource[d].driverSource_encoding = 0..4

    Legacy fallback topology::

        driver.translateX -> RBFtoolsShape.input[0]
        driver.translateY -> RBFtoolsShape.input[1]
        ...

    Mirror operations on multi-source nodes are CURRENTLY DEFERRED
    to v5.x post-final M_B24c sub-task. See addendum
    §M_B24b2.mirror-deferred-rationale for the controller-layer
    migration plan and the 14 deprecated read_driver_info call-sites
    (including 5 in mirror flow) preserved by M_B24a2-1 backcompat.

    STATUS UPDATE (M_B24c): RESOLVED for Generic-mode multi-source
    mirror; Matrix-mode multi-source mirror remains DEFERRED to
    M_B24c2 (see addendum §M_B24c.matrix-mode-still-deferred +
    §M_B24c2-stub). The pre-M_B24c "5 in mirror flow" callsite count
    was empirically corrected to 2 (controller.py mirror_current_node
    + core.py mirror_node) via verify-before-design 20th-use double-
    grep; see §M_B24c.planner-error-correction. The 14-callsite
    aggregate is unchanged - the other 12 (live-edit / alias / load-
    editor / json / neutral / docs / tests) remain on the deprecated
    wrapper per M_B24a2-1 backcompat.
    """
    shape = get_shape(node)
    if not _exists(shape):
        return []
    # Probe driverSource[]; if it has populated entries, prefer them.
    indices = []
    try:
        indices = cmds.getAttr(shape + ".driverSource", multiIndices=True) or []
    except Exception:
        indices = []
    sources = []
    for d in indices:
        node_plug = "{}.driverSource[{}].driverSource_node".format(shape, d)
        srcs = cmds.listConnections(
            node_plug, source=True, destination=False) or []
        if not srcs:
            continue
        attrs_raw = cmds.getAttr(
            "{}.driverSource[{}].driverSource_attrs".format(shape, d)) or []
        weight = cmds.getAttr(
            "{}.driverSource[{}].driverSource_weight".format(shape, d))
        encoding = cmds.getAttr(
            "{}.driverSource[{}].driverSource_encoding".format(shape, d))
        try:
            ds = DriverSource(
                node=srcs[0],
                attrs=tuple(attrs_raw),
                weight=float(weight),
                encoding=int(encoding))
        except (ValueError, TypeError) as exc:
            cmds.warning(
                "RBFtools: skipping malformed driverSource[{}] on "
                "'{}': {}".format(d, node, exc))
            continue
        sources.append(ds)
    if sources:
        return sources
    # Legacy path — migrate (fail-soft) and synthesize one entry.
    legacy_node, legacy_attrs = _migrate_legacy_single_driver(node)
    if not legacy_node:
        return []
    return [DriverSource(
        node=legacy_node, attrs=tuple(legacy_attrs),
        weight=1.0, encoding=0)]


def _is_matrix_mode(shape):
    """M_B24d: detect RBF Matrix mode (type=1 + rbfMode=1).

    Generic mode  = type=1 + rbfMode=0 (input[i] flat scalar wiring).
    Matrix mode   = type=1 + rbfMode=1 (driverList[d].driverInput
                                         matrix wiring; DEFERRED to
                                         M_B24d_matrix_followup).
    Vector-Angle  = type=0 (input[i] flat scalar wiring).

    Returns True only for the Matrix sub-mode."""
    type_val = int(safe_get(shape + ".type", 0))
    rbf_mode = int(safe_get(shape + ".rbfMode", 0))
    return type_val == 1 and rbf_mode == 1


def _count_existing_input_attrs(shape):
    """M_B24d: count current `<shape>.input[]` populated indices.

    Used as the base offset for appending new driver attrs in
    add_driver_source (Generic mode). Returns 0 if input[] is empty
    or if the multiIndices query fails."""
    try:
        indices = cmds.getAttr(shape + ".input", multiIndices=True) or []
    except Exception:
        indices = []
    return (max(indices) + 1) if indices else 0


def _count_existing_driver_list(shape):
    """M_B24d_matrix_followup: next free `<shape>.driverList[]` index.

    Matrix mode appends one driverList entry per add_driver_source
    call (each entry holds one driver's worldMatrix). Returns 0 if
    driverList[] is empty or if the multiIndices query fails."""
    try:
        indices = cmds.getAttr(shape + ".driverList", multiIndices=True) or []
    except Exception:
        indices = []
    return (max(indices) + 1) if indices else 0


def _has_generic_wiring(shape):
    """M_B24d_matrix_followup: detect populated input[] indices on shape.

    Used by add_driver_source mode-exclusion semantic to surface a
    user-facing RuntimeError when the caller would mix Generic and
    Matrix mode wiring on the same node. See addendum
    §M_B24d_matrix_followup.mode-exclusion-semantic."""
    try:
        indices = cmds.getAttr(shape + ".input", multiIndices=True) or []
    except Exception:
        indices = []
    return bool(indices)


def _has_matrix_wiring(shape):
    """M_B24d_matrix_followup: detect any driverList[d].driverInput
    incoming connection on shape.

    Counterpart to :func:`_has_generic_wiring`. Probes every
    populated driverList[] index for an actual incoming connection
    (legacy single-driver Matrix node has driverList[0] connected
    too, so any populated index counts)."""
    try:
        dl_indices = cmds.getAttr(
            shape + ".driverList", multiIndices=True) or []
    except Exception:
        dl_indices = []
    for d in dl_indices:
        plug = "{}.driverList[{}].driverInput".format(shape, d)
        try:
            conns = cmds.listConnections(
                plug, source=True, destination=False) or []
        except Exception:
            conns = []
        if conns:
            return True
    return False


def _resolve_driver_rotate_order(shape, driver_node, idx):
    """M_B24d_matrix_followup (Hardening 3): connect
    driver_node.rotateOrder -> shape.driverInputRotateOrder[idx]
    if the driver node carries a rotateOrder attribute. Standard
    transform / joint nodes always do; falls back to the Maya
    default xyz=0 for exotic node types lacking the attribute
    (no setAttr needed since 0 is the array slot default)."""
    plug = "{}.driverInputRotateOrder[{}]".format(shape, idx)
    if cmds.attributeQuery("rotateOrder", node=driver_node, exists=True):
        cmds.connectAttr(driver_node + ".rotateOrder", plug, force=True)


def _wire_matrix_mode_data_path(shape, driver_node, idx):
    """M_B24d_matrix_followup (Hardening 2): connect
    driver_node.worldMatrix[0] -> shape.driverList[idx].driverInput.

    worldMatrix[0] (NOT .matrix / local) is required by the C++
    compute() math chain at RBFtools.cpp:2113:

        transMatDriver = driverMat * driverParentMatInv * jointOrientMatInv

    The driverParentMatInv step is mathematically meaningful only
    when driverMat is a world-space matrix; connecting the local
    .matrix would make the parentInverse step a no-op-ish error.
    See addendum §M_B24d_matrix_followup.matrix-vs-worldmatrix
    for the verbatim derivation.

    Post-connect verification is mandatory: cpp:2087-2093 has an
    early-return guard on unconnected driverInput, so a silently
    failed connectAttr would blind the entire RBF compute()."""
    target = "{}.driverList[{}].driverInput".format(shape, idx)
    cmds.connectAttr(driver_node + ".worldMatrix[0]", target, force=True)
    incoming = cmds.listConnections(
        target, source=True, destination=False) or []
    if not incoming:
        raise RuntimeError(
            "RBFtools: driverList[{}].driverInput connectAttr appeared "
            "to succeed but listConnections returned empty. C++ "
            "compute() early-returns on unconnected driverInput "
            "(RBFtools.cpp:2087-2093) - this would silently fail the "
            "entire RBF compute. Aborting.".format(idx))


def _unwire_matrix_mode_data_path(shape, driver_node, idx):
    """M_B24d_matrix_followup: symmetric disconnect for
    :func:`_wire_matrix_mode_data_path`. Best-effort - any failure
    is swallowed since this runs from rollback / remove paths and
    must never re-raise."""
    target = "{}.driverList[{}].driverInput".format(shape, idx)
    if driver_node:
        try:
            cmds.disconnectAttr(driver_node + ".worldMatrix[0]", target)
        except Exception:
            pass
        rot_plug = "{}.driverInputRotateOrder[{}]".format(shape, idx)
        try:
            if cmds.attributeQuery(
                    "rotateOrder", node=driver_node, exists=True):
                cmds.disconnectAttr(driver_node + ".rotateOrder", rot_plug)
        except Exception:
            pass


def add_driver_source(node, driver_node, driver_attrs,
                      weight=1.0, encoding=0):
    """Append a new :class:`DriverSource` to driverSource[].

    Returns the index of the newly-added entry. Forms the
    driverSource_node message connection from ``driver_node.message``
    and writes the attrs / weight / encoding fields.

    M_B24d data path: in addition to the metadata write, this
    function also creates the actual data connections so RBF
    compute() sees the new driver. For Generic mode (type=1,
    rbfMode=0) this means appending each ``driver_node.<attr>``
    to ``shape.input[base+i]`` where base is the current input[]
    count. Matrix mode (type=1, rbfMode=1) wires
    ``driver_node.worldMatrix[0]`` to
    ``shape.driverList[idx].driverInput`` plus an optional
    ``driver_node.rotateOrder`` -> ``driverInputRotateOrder[idx]``
    sync (M_B24d_matrix_followup; see addendum
    §M_B24d_matrix_followup.matrix-vs-worldmatrix for the math
    chain that mandates worldMatrix over .matrix).

    M_B24d_matrix_followup mode-exclusion semantic: callers must
    not mix Generic and Matrix wiring on the same shape. If the
    shape currently carries wiring of one kind and the caller
    targets the other, a RuntimeError is raised with a user-facing
    instruction (remove all driver sources first, then re-add).

    Atomic fail-soft (Hardening 1): metadata write happens first,
    then data path. If any data-path connectAttr fails, the
    metadata is rolled back via removeMultiInstance so the node
    never holds a half-state driverSource[idx].
    """
    shape = get_shape(node)
    if not _exists(shape):
        raise RuntimeError(
            "add_driver_source: shape not found for {!r}".format(node))
    # M_B24d_matrix_followup (Hardening 1): mode-exclusion semantic.
    # Detect existing wiring topology and reject the mismatched
    # branch before any state is written. See addendum
    # §M_B24d_matrix_followup.mode-exclusion-semantic.
    is_matrix = _is_matrix_mode(shape)
    if is_matrix and _has_generic_wiring(shape):
        raise RuntimeError(
            "RBFtools: cannot mix Matrix mode and Generic mode driver "
            "sources on the same node. Existing sources are in Generic "
            "mode (shape.input[] populated); current node is in Matrix "
            "mode (type=1 + rbfMode=1). Remove all driver sources "
            "first via remove_driver_source(), then re-add. See "
            "addendum "
            "§M_B24d_matrix_followup.mode-exclusion-semantic.")
    if (not is_matrix) and _has_matrix_wiring(shape):
        raise RuntimeError(
            "RBFtools: cannot mix Matrix mode and Generic mode driver "
            "sources on the same node. Existing sources are in Matrix "
            "mode (shape.driverList[].driverInput connected); current "
            "node is in Generic mode (type=1 + rbfMode=0 or type=0). "
            "Remove all driver sources first via "
            "remove_driver_source(), then re-add. See addendum "
            "§M_B24d_matrix_followup.mode-exclusion-semantic.")
    # Validate via dataclass (enforces weight >= 0, encoding 0..4).
    DriverSource(node=driver_node, attrs=tuple(driver_attrs),
                 weight=float(weight), encoding=int(encoding))
    # Find next free index.
    indices = cmds.getAttr(shape + ".driverSource", multiIndices=True) or []
    next_idx = (max(indices) + 1) if indices else 0
    base_plug = "{}.driverSource[{}]".format(shape, next_idx)
    # ---- Step 1: write metadata (existing behavior) ----
    cmds.connectAttr(driver_node + ".message",
                     base_plug + ".driverSource_node", force=True)
    cmds.setAttr(base_plug + ".driverSource_attrs",
                 len(driver_attrs), *driver_attrs, type="stringArray")
    cmds.setAttr(base_plug + ".driverSource_weight", float(weight))
    cmds.setAttr(base_plug + ".driverSource_encoding", int(encoding))
    # ---- Step 2: data path (atomic fail-soft) ----
    if is_matrix:
        # Matrix mode (M_B24d_matrix_followup): append one
        # driverList[matrix_idx] entry per add_driver_source call.
        # driver_attrs is metadata-only here (forward-compat M5+;
        # decision D.2). Atomic try/except mirrors Generic branch.
        matrix_idx = _count_existing_driver_list(shape)
        wired_matrix = False
        try:
            _wire_matrix_mode_data_path(shape, driver_node, matrix_idx)
            wired_matrix = True
            _resolve_driver_rotate_order(shape, driver_node, matrix_idx)
        except Exception as exc:
            if wired_matrix:
                _unwire_matrix_mode_data_path(
                    shape, driver_node, matrix_idx)
            try:
                cmds.removeMultiInstance(base_plug, b=True)
            except Exception:
                pass
            cmds.warning(
                "add_driver_source: Matrix mode data path wiring "
                "failed for {!r} ({}); rolled back metadata + "
                "partial connections. Error: {}".format(
                    driver_node, driver_attrs, exc))
            raise
        return next_idx
    # Generic mode: append driver attrs to shape.input[base..base+n].
    # base is the current count of populated input[] indices, so this
    # respects existing single-driver wire_driver_inputs() output and
    # any prior add_driver_source() appends.
    input_base = _count_existing_input_attrs(shape)
    connected = []
    try:
        for i, attr in enumerate(driver_attrs):
            src = "{}.{}".format(driver_node, attr)
            dst = "{}.input[{}]".format(shape, input_base + i)
            cmds.connectAttr(src, dst, force=True)
            connected.append((src, dst))
    except Exception as exc:
        # Hardening 1 atomic rollback: undo any partial input[]
        # connections + remove the metadata entry. Inner try/except
        # ensures rollback itself never raises.
        for src, dst in connected:
            try:
                cmds.disconnectAttr(src, dst)
            except Exception:
                pass
        try:
            cmds.removeMultiInstance(base_plug, b=True)
        except Exception:
            pass
        cmds.warning(
            "add_driver_source: data path wiring failed for {!r} "
            "({}); rolled back metadata + partial connections. "
            "Error: {}".format(driver_node, driver_attrs, exc))
        raise
    return next_idx


def remove_driver_source(node, index):
    """Disconnect + remove driverSource[index]. No-op if the index does
    not exist.

    M_B24d data path: in addition to clearing the metadata via
    removeMultiInstance, this function also disconnects the
    corresponding ``shape.input[base..base+n]`` connections that
    add_driver_source created. The base offset is recomputed by
    summing attr counts of all driverSource[*] entries with logical
    index < `index`.
    """
    shape = get_shape(node)
    if not _exists(shape):
        return
    plug = "{}.driverSource[{}]".format(shape, index)
    # M_B24d data path: also disconnect the input[base..base+n]
    # connections that add_driver_source created. Compute base by
    # summing attr counts of all driverSource[*] entries with
    # logical index < `index`. Best-effort — failures warn but do
    # not block the metadata removal below.
    try:
        all_indices = cmds.getAttr(
            shape + ".driverSource", multiIndices=True) or []
    except Exception:
        all_indices = []
    if index in all_indices:
        # Read this source's driver node from the message connection
        # (shared by Generic + Matrix branches below).
        try:
            srcs = cmds.listConnections(
                plug + ".driverSource_node",
                source=True, destination=False) or []
        except Exception:
            srcs = []
        drv_node = srcs[0] if srcs else ""
        if _is_matrix_mode(shape):
            # M_B24d_matrix_followup: Matrix mode appended one
            # driverList[] entry per add_driver_source call. The
            # logical position of `index` within the sorted
            # driverSource[] indices yields the matching driverList
            # offset (entries are appended in lockstep).
            ordered = sorted(all_indices)
            matrix_idx = ordered.index(index)
            _unwire_matrix_mode_data_path(shape, drv_node, matrix_idx)
        else:
            base = 0
            my_attrs = []
            for prior in sorted(all_indices):
                attrs_plug = (
                    "{}.driverSource[{}].driverSource_attrs".format(
                        shape, prior))
                try:
                    attrs_raw = cmds.getAttr(attrs_plug) or []
                except Exception:
                    attrs_raw = []
                if prior < index:
                    base += len(attrs_raw)
                elif prior == index:
                    my_attrs = list(attrs_raw)
                    break
            for i, attr in enumerate(my_attrs):
                try:
                    src = "{}.{}".format(drv_node, attr)
                    dst = "{}.input[{}]".format(shape, base + i)
                    cmds.disconnectAttr(src, dst)
                except Exception:
                    # disconnect failures are best-effort; leave any
                    # stale connection for the caller to clean up
                    # manually if needed.
                    pass
    try:
        cmds.removeMultiInstance(plug, b=True)
    except Exception as exc:
        cmds.warning(
            "RBFtools: remove_driver_source({}, {}) failed: {}".format(
                node, index, exc))


def format_node_for_display(name, mode):
    """Phase 3 (Header naming radio 2026-04-27): format a Maya node
    name for display in the inspector per the active naming mode.

      mode == "long"  -> long name with full DAG path
      mode == "short" -> last-component short name
      mode == "nice"  -> last-component name with leading
                          namespace stripped

    Pure string transformation - never queries Maya. Returns the
    input name unchanged if the mode is unknown or transformation
    fails.
    """
    if not name:
        return ""
    try:
        if mode == "short":
            # Last DAG component (everything after final '|').
            return name.rsplit("|", 1)[-1]
        if mode == "nice":
            short = name.rsplit("|", 1)[-1]
            return short.rsplit(":", 1)[-1]   # strip namespace
        # default + "long"
        return name
    except Exception:
        return name


def cleanup_remove_connectionless_inputs(node):
    """Phase 3 (Utility - cleanup tools): walk shape.input[] and
    remove every multi-index whose plug has no incoming connection.

    Returns the number of indices removed; 0 on no-op or failure.
    """
    shape = get_shape(node)
    if not _exists(shape):
        return 0
    try:
        indices = cmds.getAttr(
            shape + ".input", multiIndices=True) or []
    except Exception:
        return 0
    removed = 0
    for d in list(indices):
        plug = "{}.input[{}]".format(shape, d)
        try:
            srcs = cmds.listConnections(
                plug, source=True, destination=False) or []
        except Exception:
            srcs = []
        if not srcs:
            try:
                cmds.removeMultiInstance(plug, b=True)
                removed += 1
            except Exception:
                pass
    return removed


def cleanup_remove_connectionless_outputs(node):
    """Phase 3: walk shape.output[] and remove every multi-index
    whose plug has no outgoing connection."""
    shape = get_shape(node)
    if not _exists(shape):
        return 0
    try:
        indices = cmds.getAttr(
            shape + ".output", multiIndices=True) or []
    except Exception:
        return 0
    removed = 0
    for d in list(indices):
        plug = "{}.output[{}]".format(shape, d)
        try:
            dests = cmds.listConnections(
                plug, source=False, destination=True) or []
        except Exception:
            dests = []
        if not dests:
            try:
                cmds.removeMultiInstance(plug, b=True)
                removed += 1
            except Exception:
                pass
    return removed


def cleanup_remove_redundant_poses(node):
    """Phase 3: walk shape.poses[] and remove poses whose inputs
    AND values exactly match an earlier pose. This is the
    'same pose data / same value in all poses' cleanup the
    AnimaRbfSolver reference exposes."""
    shape = get_shape(node)
    if not _exists(shape):
        return 0
    poses = read_all_poses(node)
    seen = []
    to_remove = []
    for p in poses:
        sig = (tuple(p.inputs), tuple(p.values))
        if sig in seen:
            to_remove.append(p.index)
        else:
            seen.append(sig)
    removed = 0
    # High-to-low so logical indices stay valid as we go.
    for idx in sorted(to_remove, reverse=True):
        plug = "{}.poses[{}]".format(shape, idx)
        try:
            cmds.removeMultiInstance(plug, b=True)
            removed += 1
        except Exception:
            pass
    return removed


def disconnect_driver_source_attrs(node, index):
    """M_DISCONNECT_FIX (Phase 1, P0 critical fix 2026-04-27): true
    disconnect for a single driver source - directly disconnects
    the source's `input[base..base+n]` wires + clears the
    `driverSource_attrs` MStringArray, without rebuilding any other
    source.

    Why a dedicated function:
      - The previous Disconnect path called
        `set_driver_source_attrs(idx, [])` which goes through the
        remove-all + re-add-all rebuild orchestrator. That has
        unintended side effects (remove of driverSource[idx] itself
        plus re-add of every OTHER source via add_driver_source,
        which restores their wires correctly but is heavy and
        depends on `cmds.setAttr(plug, 0, type="stringArray")`
        round-tripping cleanly across Maya versions).
      - User report 2026-04-27: under some scenes Disconnect was
        observed to leave the source's selected attrs WIRED to
        input[]. The direct-disconnect path eliminates that whole
        class of failure.

    Implementation:
      1. Read current sources list (multi).
      2. Resolve index'th source's node + attrs + base offset
         (sum of attr counts for sources at logical index < idx).
      3. For each (attr at offset i): cmds.disconnectAttr(
           "<src>.<attr>", "<shape>.input[base+i]").
      4. cmds.setAttr("<shape>.driverSource[idx].driverSource_attrs",
                      0, type="stringArray").

    Returns True on success, False on out-of-range / failure
    (with cmds.warning surfacing the cause).
    """
    shape = get_shape(node)
    if not _exists(shape):
        cmds.warning(
            "disconnect_driver_source_attrs: shape not found "
            "for {!r}".format(node))
        return False
    sources = read_driver_info_multi(node)
    if not sources:
        cmds.warning(
            "disconnect_driver_source_attrs: no driver sources "
            "on {!r}".format(node))
        return False
    if index < 0 or index >= len(sources):
        cmds.warning(
            "disconnect_driver_source_attrs: index {} out of "
            "range (0..{})".format(index, len(sources) - 1))
        return False
    target = sources[index]
    if not target.attrs:
        # Already empty - nothing to disconnect. Still treat as
        # success (idempotent) so the slot guards don't loop.
        return True
    # Compute base offset for this source's input[] slice. Matches
    # the convention add_driver_source uses (sum of attr counts of
    # all logically-prior sources).
    base = 0
    for i, s in enumerate(sources):
        if i == index:
            break
        base += len(s.attrs)
    # 1) disconnect each input[] wire.
    src_node = target.node or ""
    for i, attr in enumerate(target.attrs):
        if not src_node:
            break
        src_plug = "{}.{}".format(src_node, attr)
        dst_plug = "{}.input[{}]".format(shape, base + i)
        try:
            cmds.disconnectAttr(src_plug, dst_plug)
        except Exception:
            # Best-effort: a manually-disconnected wire would raise
            # here; we still want to clear the metadata below.
            pass
    # 2) clear driverSource_attrs metadata. The MStringArray empty
    # form is `setAttr <plug> 0 -type "stringArray"` (length 0 +
    # zero values).
    attrs_plug = "{}.driverSource[{}].driverSource_attrs".format(
        shape, index)
    try:
        cmds.setAttr(attrs_plug, 0, type="stringArray")
    except Exception as exc:
        cmds.warning(
            "disconnect_driver_source_attrs: failed to clear "
            "{}: {}".format(attrs_plug, exc))
        return False
    return True


def set_driver_source_attrs(node, index, new_attrs):
    """M_UIRECONCILE_PLUS (Item 4b): replace the attrs list of an
    existing driverSource[index] entry.

    Implementation: read the full source list, replace index'th
    entry's attrs, then remove + re-add every source in order. This
    keeps the driverSource[*] indices stable and the input[] /
    driverList[] wiring consistent with the rest of the multi-
    source pipeline; performance is fine for the typical 4-10
    source workload.

    Returns True on success, False if the index is out of range or
    the underlying mutation raised. Failures emit cmds.warning so
    the controller layer surfaces them to the TD via the script
    editor.
    """
    sources = read_driver_info_multi(node)
    if not sources:
        cmds.warning(
            "set_driver_source_attrs: no driver sources on {!r}".format(
                node))
        return False
    if index < 0 or index >= len(sources):
        cmds.warning(
            "set_driver_source_attrs: index {} out of range "
            "(0..{})".format(index, len(sources) - 1))
        return False
    # Build the rebuilt source list (in-memory copy + mutation at
    # the requested index).
    rebuilt = []
    for i, src in enumerate(sources):
        if i == index:
            rebuilt.append(DriverSource(
                node=src.node,
                attrs=tuple(new_attrs),
                weight=float(src.weight),
                encoding=int(src.encoding)))
        else:
            rebuilt.append(src)
    # Remove every existing source (high-to-low index so logical
    # indices stay valid as we go).
    try:
        existing_indices = sorted(cmds.getAttr(
            get_shape(node) + ".driverSource",
            multiIndices=True) or [], reverse=True)
    except Exception:
        existing_indices = list(range(len(sources) - 1, -1, -1))
    for d in existing_indices:
        try:
            remove_driver_source(node, d)
        except Exception as exc:
            cmds.warning(
                "set_driver_source_attrs: remove sweep failed at "
                "index {}: {}".format(d, exc))
            return False
    # Re-add the rebuilt list.
    for src in rebuilt:
        try:
            add_driver_source(node, src.node, list(src.attrs),
                              weight=float(src.weight),
                              encoding=int(src.encoding))
        except Exception as exc:
            cmds.warning(
                "set_driver_source_attrs: re-add failed for {!r}: "
                "{}".format(src.node, exc))
            return False
    return True


def read_driver_info(node):
    """DEPRECATED. Use :func:`read_driver_info_multi` for new code.

    Legacy single-driver wrapper that returns the first driver's
    (node_name, attrs) tuple. Triggers :class:`DeprecationWarning` on
    every call. The implementation routes through
    :func:`read_driver_info_multi`, which auto-migrates legacy nodes.

    Returns
    -------
    (str, list[str])
        ``(driver_node_name, [attr_1, attr_2, ...])``.
        Returns ``("", [])`` if nothing is connected.
    """
    warnings.warn(
        "read_driver_info is deprecated; use read_driver_info_multi",
        DeprecationWarning, stacklevel=2)
    sources = read_driver_info_multi(node)
    if not sources:
        return "", []
    first = sources[0]
    return first.node, list(first.attrs)


# =====================================================================
#  M_DRIVEN_MULTI — multi-driven source orchestrator (Item 4c)
# =====================================================================
#
# The driven side has, until now, been single-target: `wire_driven_outputs`
# wires `shape.output[i]` -> `<driven_node>.<attrs[i]>` for one node.
# The Tekken 8 paradigm + the user's 2026-04-27 batch (Item 4c) calls for
# multi-driven (multiple driven nodes, each with their own attribute slice).
#
# C++ `output` is a flat `MFnNumericData::kDouble` multi attribute - no
# schema change is required. We split `output[]` by source: source 0
# consumes output[0..n0-1], source 1 consumes output[n0..n0+n1-1], etc.
#
# Persistence uses a **dynamic compound attribute** added at runtime via
# `cmds.addAttr` (rather than a C++ schema rebuild). The compound is
# named `drivenSource` mirroring the M_B24a1 `driverSource` schema.
# Migration: legacy single-driven nodes auto-migrate on first read into a
# 1-source list, exactly like `_migrate_legacy_single_driver` does for
# the driver side.

class DrivenSource(object):
    """Driven counterpart to :class:`DriverSource`. Frozen-style dataclass
    that pairs a target node with its ordered attribute list."""

    __slots__ = ("node", "attrs")

    def __init__(self, node, attrs):
        if not isinstance(node, str):
            raise TypeError(
                "DrivenSource.node must be a str, got {!r}".format(
                    type(node).__name__))
        self.node  = node
        self.attrs = tuple(attrs)

    def __repr__(self):
        return "DrivenSource(node={!r}, attrs={!r})".format(
            self.node, list(self.attrs))

    def __eq__(self, other):
        if not isinstance(other, DrivenSource):
            return NotImplemented
        return self.node == other.node and self.attrs == other.attrs

    def __ne__(self, other):
        result = self.__eq__(other)
        if result is NotImplemented:
            return result
        return not result


def _ensure_driven_source_compound(shape):
    """M_DRIVEN_MULTI: lazily create the `drivenSource` dynamic compound
    attribute on the shape (parallel to the M_B24a1 driverSource C++
    schema). Idempotent - skips if the attribute already exists."""
    if cmds.attributeQuery("drivenSource", node=shape, exists=True):
        return
    cmds.addAttr(
        shape, longName="drivenSource", attributeType="compound",
        numberOfChildren=2, multi=True)
    cmds.addAttr(
        shape, longName="drivenSource_node",
        attributeType="message", parent="drivenSource")
    cmds.addAttr(
        shape, longName="drivenSource_attrs",
        dataType="stringArray", parent="drivenSource")


def read_driven_info_multi(node):
    """Read every driven source on *node* as a list[DrivenSource].

    Mirrors :func:`read_driver_info_multi` for the driven side. If the
    `drivenSource` dynamic compound has populated entries, return them;
    otherwise fall back to the legacy single-driven shape via
    :func:`read_driven_info` and synthesize a 1-source list.
    """
    shape = get_shape(node)
    if not _exists(shape):
        return []
    sources = []
    if cmds.attributeQuery("drivenSource", node=shape, exists=True):
        try:
            indices = cmds.getAttr(
                shape + ".drivenSource", multiIndices=True) or []
        except Exception:
            indices = []
        for d in indices:
            node_plug = "{}.drivenSource[{}].drivenSource_node".format(
                shape, d)
            try:
                srcs = cmds.listConnections(
                    node_plug, source=True, destination=False) or []
            except Exception:
                srcs = []
            if not srcs:
                continue
            attrs_plug = (
                "{}.drivenSource[{}].drivenSource_attrs".format(shape, d))
            try:
                attrs_raw = cmds.getAttr(attrs_plug) or []
            except Exception:
                attrs_raw = []
            try:
                sources.append(DrivenSource(
                    node=srcs[0], attrs=tuple(attrs_raw)))
            except (TypeError, ValueError) as exc:
                cmds.warning(
                    "RBFtools: skipping malformed drivenSource[{}] on "
                    "'{}': {}".format(d, node, exc))
        if sources:
            return sources
    # Legacy / fall-back: synthesize from existing output[] connections.
    legacy_node, legacy_attrs = read_driven_info(node)
    if not legacy_node:
        return []
    return [DrivenSource(node=legacy_node, attrs=tuple(legacy_attrs))]


def _disconnect_all_outputs(shape):
    """M_DRIVEN_MULTI helper: disconnect every existing `shape.output[i]`
    -> driven plug. Used before re-wiring across all driven sources so the
    output[] index ordering stays consistent."""
    try:
        conns = cmds.listConnections(
            shape + ".output",
            source=False, destination=True,
            plugs=True, connections=True,
            skipConversionNodes=True) or []
    except Exception:
        conns = []
    for i in range(0, len(conns), 2):
        src_plug = conns[i]
        dst_plug = conns[i + 1]
        try:
            cmds.disconnectAttr(src_plug, dst_plug)
        except Exception:
            pass


def _wire_driven_sources(shape, sources):
    """M_DRIVEN_MULTI: wire `shape.output[base..base+n]` to each driven
    source's attrs in order. Cumulative base offset across all sources."""
    base = 0
    for src in sources:
        if not src.node or not _exists(src.node):
            base += len(src.attrs)
            continue
        for i, attr in enumerate(src.attrs):
            src_plug = "{}.output[{}]".format(shape, base + i)
            dst_plug = "{}.{}".format(src.node, attr)
            try:
                cmds.connectAttr(src_plug, dst_plug, force=True)
            except Exception as exc:
                cmds.warning(
                    "_wire_driven_sources: {} -> {} failed: {}".format(
                        src_plug, dst_plug, exc))
        base += len(src.attrs)


def add_driven_source(node, driven_node, driven_attrs):
    """M_DRIVEN_MULTI (Item 4c): append a new DrivenSource entry on
    *node*'s `drivenSource` compound + re-wire every driven source's
    output[] connections so the new source slots in at the end.

    Atomic fail-soft: on any wiring failure the new entry is rolled back
    via removeMultiInstance (mirroring M_B24d Hardening 1 for the driver
    side). Returns the index of the new entry.
    """
    shape = get_shape(node)
    if not _exists(shape):
        raise RuntimeError(
            "add_driven_source: shape not found for {!r}".format(node))
    _ensure_driven_source_compound(shape)
    DrivenSource(node=driven_node, attrs=tuple(driven_attrs))   # validate
    indices = cmds.getAttr(
        shape + ".drivenSource", multiIndices=True) or []
    next_idx = (max(indices) + 1) if indices else 0
    base_plug = "{}.drivenSource[{}]".format(shape, next_idx)
    cmds.connectAttr(driven_node + ".message",
                     base_plug + ".drivenSource_node", force=True)
    cmds.setAttr(base_plug + ".drivenSource_attrs",
                 len(driven_attrs), *driven_attrs, type="stringArray")
    try:
        _disconnect_all_outputs(shape)
        _wire_driven_sources(shape, read_driven_info_multi(node))
    except Exception as exc:
        try:
            cmds.removeMultiInstance(base_plug, b=True)
        except Exception:
            pass
        cmds.warning(
            "add_driven_source: wiring failed for {!r} ({}); "
            "rolled back metadata. Error: {}".format(
                driven_node, driven_attrs, exc))
        raise
    return next_idx


def remove_driven_source(node, index):
    """M_DRIVEN_MULTI: remove `drivenSource[index]` + re-wire the
    remaining sources so output[] indices stay contiguous from 0."""
    shape = get_shape(node)
    if not _exists(shape):
        return
    plug = "{}.drivenSource[{}]".format(shape, index)
    try:
        existing = cmds.getAttr(
            shape + ".drivenSource", multiIndices=True) or []
    except Exception:
        existing = []
    if index not in existing:
        return
    _disconnect_all_outputs(shape)
    try:
        cmds.removeMultiInstance(plug, b=True)
    except Exception as exc:
        cmds.warning(
            "remove_driven_source({}, {}) failed: {}".format(
                node, index, exc))
        return
    _wire_driven_sources(shape, read_driven_info_multi(node))


def disconnect_driven_source_attrs(node, index):
    """M_DISCONNECT_FIX driven mirror of
    :func:`disconnect_driver_source_attrs`. Direct disconnect on
    `output[base..base+n]` wires + clear `drivenSource_attrs`
    metadata. No remove-all + re-add-all rebuild."""
    shape = get_shape(node)
    if not _exists(shape):
        cmds.warning(
            "disconnect_driven_source_attrs: shape not found "
            "for {!r}".format(node))
        return False
    sources = read_driven_info_multi(node)
    if not sources:
        cmds.warning(
            "disconnect_driven_source_attrs: no driven sources "
            "on {!r}".format(node))
        return False
    if index < 0 or index >= len(sources):
        cmds.warning(
            "disconnect_driven_source_attrs: index {} out of "
            "range (0..{})".format(index, len(sources) - 1))
        return False
    target = sources[index]
    if not target.attrs:
        return True
    # Base offset across logically-prior driven sources.
    base = 0
    for i, s in enumerate(sources):
        if i == index:
            break
        base += len(s.attrs)
    # 1) disconnect output[base+i] -> driven_node.attr_i wires.
    dvn_node = target.node or ""
    for i, attr in enumerate(target.attrs):
        if not dvn_node:
            break
        src_plug = "{}.output[{}]".format(shape, base + i)
        dst_plug = "{}.{}".format(dvn_node, attr)
        try:
            cmds.disconnectAttr(src_plug, dst_plug)
        except Exception:
            pass
    # 2) clear drivenSource_attrs metadata (the dynamic compound
    # added by _ensure_driven_source_compound).
    if cmds.attributeQuery("drivenSource", node=shape, exists=True):
        attrs_plug = (
            "{}.drivenSource[{}].drivenSource_attrs".format(
                shape, index))
        try:
            cmds.setAttr(attrs_plug, 0, type="stringArray")
        except Exception as exc:
            cmds.warning(
                "disconnect_driven_source_attrs: failed to clear "
                "{}: {}".format(attrs_plug, exc))
            return False
    return True


def set_driven_source_attrs(node, index, new_attrs):
    """M_DRIVEN_MULTI: replace the attrs list of an existing
    drivenSource[index] entry. Same remove-all + re-add-in-order pattern
    used by :func:`set_driver_source_attrs`."""
    sources = read_driven_info_multi(node)
    if not sources:
        cmds.warning(
            "set_driven_source_attrs: no driven sources on {!r}".format(
                node))
        return False
    if index < 0 or index >= len(sources):
        cmds.warning(
            "set_driven_source_attrs: index {} out of range "
            "(0..{})".format(index, len(sources) - 1))
        return False
    rebuilt = []
    for i, src in enumerate(sources):
        if i == index:
            rebuilt.append(DrivenSource(
                node=src.node, attrs=tuple(new_attrs)))
        else:
            rebuilt.append(src)
    try:
        existing_indices = sorted(cmds.getAttr(
            get_shape(node) + ".drivenSource",
            multiIndices=True) or [], reverse=True)
    except Exception:
        existing_indices = list(range(len(sources) - 1, -1, -1))
    for d in existing_indices:
        try:
            remove_driven_source(node, d)
        except Exception as exc:
            cmds.warning(
                "set_driven_source_attrs: remove sweep failed at "
                "index {}: {}".format(d, exc))
            return False
    for src in rebuilt:
        try:
            add_driven_source(node, src.node, list(src.attrs))
        except Exception as exc:
            cmds.warning(
                "set_driven_source_attrs: re-add failed for {!r}: "
                "{}".format(src.node, exc))
            return False
    return True


def read_driven_info(node):
    """Discover which node and attributes are driven by the *output[]* array.

    Symmetric counterpart to :func:`read_driver_info`.

    Connection topology::

        RBFtoolsShape.output[0]  →  blendShape1.brow_up
        RBFtoolsShape.output[1]  →  blendShape1.brow_down
    """
    shape = get_shape(node)
    if not _exists(shape):
        return "", []

    conns = cmds.listConnections(
        shape + ".output",
        source=False, destination=True,
        plugs=True, connections=True,
        skipConversionNodes=True,
    ) or []

    driven = ""
    attrs = []
    for i in range(0, len(conns), 2):
        dst_plug = conns[i + 1]
        parts = dst_plug.split(".")
        if not driven:
            driven = parts[0]
        if len(parts) > 1:
            attrs.append(parts[1])

    return driven, attrs


# =====================================================================
#  6. Node CRUD
# =====================================================================

def create_node():
    """Create a new ``RBFtools`` shape and return its **transform** name.

    Preserves the user's current selection (createNode side-effect).

    M_QUICKWINS (Item 3, 2026-04-27): the C++ schema default for
    `.type` is 0 (Vector-Angle); in the v5 era multi-source workflow
    the RBF mode is the expected default - new nodes are created
    with `type = 1` so the GeneralSection defaults to RBF without
    the TD having to switch the combo every time.
    """
    ensure_plugin()
    with undo_chunk("RBFtools: create node"):
        sel = cmds.ls(selection=True) or []
        shape = cmds.createNode(NODE_TYPE)
        transform = get_transform(shape)
        transform = cmds.rename(transform, "RBFnode#")
        # M_QUICKWINS Item 3: default to RBF mode (type=1). Wrapped
        # in try/except so a future schema rename never blocks node
        # creation - the existing GeneralSection combo can correct
        # the value if the setAttr fails.
        try:
            cmds.setAttr(get_shape(transform) + ".type", 1)
        except Exception as exc:
            cmds.warning(
                "create_node: defaulting .type to RBF failed: {} "
                "(node still created)".format(exc))
        if sel:
            cmds.select(sel, replace=True)
    return transform


def delete_node(node):
    """Delete the transform (and its child shapes) for *node*.

    No-op if *node* does not exist.
    """
    if not _exists(node):
        return
    with undo_chunk("RBFtools: delete node"):
        cmds.delete(node)


def clear_node_data(node):
    """Remove all multi-instance data (``input``, ``poses``, ``output``)
    from the shape under *node*.

    This resets the solver to a blank state without destroying the node,
    allowing in-place re-application of new pose data.

    Returns
    -------
    str
        The transform name (for call-chaining).
    """
    shape = get_shape(node)
    if not _exists(shape):
        return get_transform(node)

    with undo_chunk("RBFtools: clear node data"):
        for attr in ("input", "poses", "output", "baseValue", "outputIsScale"):
            try:
                indices = cmds.getAttr(
                    "{}.{}".format(shape, attr), multiIndices=True) or []
            except Exception:
                indices = []
            for idx in indices:
                try:
                    cmds.removeMultiInstance(
                        "{}.{}[{}]".format(shape, attr, idx), b=True)
                except Exception as exc:
                    cmds.warning("clear_node_data: removeMultiInstance "
                                 "{}.{}[{}] failed: {}".format(
                                     shape, attr, idx, exc))

    return get_transform(shape)


# =====================================================================
#  7. RBF builder — wiring & evaluation
# =====================================================================

def wire_driver_inputs(node, driver_node, driver_attrs):
    """Connect driver attributes into the solver's ``input[]`` array.

    Creates the connections::

        driver_node.attr_0  →  shape.input[0]
        driver_node.attr_1  →  shape.input[1]
        ...

    Parameters
    ----------
    node : str
        Transform or shape of the ``RBFtools``.
    driver_node : str
        The upstream scene object (e.g. ``"pSphere1"``).
    driver_attrs : list[str]
        Ordered attribute names to wire (e.g. ``["tx", "ty", "tz"]``).
    """
    shape = get_shape(node)
    if not _exists(shape) or not _exists(driver_node):
        return
    for i, attr in enumerate(driver_attrs):
        src = "{}.{}".format(driver_node, attr)
        dst = "{}.input[{}]".format(shape, i)
        try:
            cmds.connectAttr(src, dst, force=True)
        except Exception as exc:
            cmds.warning("wire_driver_inputs: {} → {} failed: {}".format(
                src, dst, exc))


def wire_driven_outputs(node, driven_node, driven_attrs):
    """Connect the solver's ``output[]`` array to the driven attributes.

    Creates the connections::

        shape.output[0]  →  driven_node.attr_0
        shape.output[1]  →  driven_node.attr_1
        ...
    """
    shape = get_shape(node)
    if not _exists(shape) or not _exists(driven_node):
        return
    for i, attr in enumerate(driven_attrs):
        src = "{}.output[{}]".format(shape, i)
        dst = "{}.{}".format(driven_node, attr)
        try:
            cmds.connectAttr(src, dst, force=True)
        except Exception as exc:
            cmds.warning("wire_driven_outputs: {} → {} failed: {}".format(
                src, dst, exc))


def disconnect_outputs(node):
    """Disconnect ALL connections between the RBF solver and external nodes.

    Handles intermediate ``unitConversion`` nodes that Maya inserts
    automatically for rotation attributes — these are disconnected
    and deleted to leave a clean graph.

    Parameters
    ----------
    node : str
        Transform or shape of the ``RBFtools`` node.
    """
    shape = get_shape(node)
    if not _exists(shape):
        return

    with undo_chunk("RBFtools: disconnect all"):
        orphan_nodes = set()

        # --- 1) Disconnect output[] → driven (with unitConversion cleanup) ---
        out_conns = cmds.listConnections(
            shape + ".output", source=False, destination=True,
            connections=True, plugs=True) or []
        for i in range(0, len(out_conns), 2):
            src_plug = out_conns[i]
            dst_plug = out_conns[i + 1]

            try:
                cmds.disconnectAttr(src_plug, dst_plug)
            except Exception:
                pass

            # If dst is a unitConversion, disconnect its outputs too
            dst_node = dst_plug.split(".")[0]
            if cmds.objExists(dst_node) and cmds.nodeType(dst_node) == "unitConversion":
                _disconnect_and_collect_unit_conversion(dst_node, orphan_nodes)

        # --- 2) Disconnect driver → input[] ---
        in_conns = cmds.listConnections(
            shape + ".input", source=True, destination=False,
            connections=True, plugs=True) or []
        for i in range(0, len(in_conns), 2):
            shape_plug = in_conns[i]
            source_plug = in_conns[i + 1]

            # If source is a unitConversion, disconnect it first
            src_node = source_plug.split(".")[0]
            if cmds.objExists(src_node) and cmds.nodeType(src_node) == "unitConversion":
                _disconnect_and_collect_unit_conversion(src_node, orphan_nodes)

            try:
                cmds.disconnectAttr(source_plug, shape_plug)
            except Exception:
                pass

        # --- 3) Fallback: scan ALL shape connections ---
        all_conns = cmds.listConnections(
            shape, connections=True, plugs=True) or []
        for i in range(0, len(all_conns), 2):
            shape_plug = all_conns[i]
            other_plug = all_conns[i + 1]
            plug_attr = shape_plug.split(".")[-1] if "." in shape_plug else ""
            if not (plug_attr.startswith("output") or plug_attr.startswith("input")):
                continue
            is_src = cmds.connectionInfo(shape_plug, isSource=True)
            try:
                if is_src:
                    cmds.disconnectAttr(shape_plug, other_plug)
                else:
                    cmds.disconnectAttr(other_plug, shape_plug)
            except Exception:
                pass

        # --- 4) Delete orphaned unitConversion nodes ---
        for uc_node in orphan_nodes:
            if cmds.objExists(uc_node):
                remaining = cmds.listConnections(uc_node) or []
                if not remaining:
                    try:
                        cmds.delete(uc_node)
                    except Exception:
                        pass


def _disconnect_and_collect_unit_conversion(uc_node, orphan_set):
    """Disconnect all connections on a unitConversion node and mark for deletion.

    Parameters
    ----------
    uc_node : str
        The unitConversion node name.
    orphan_set : set
        Collects node names to be deleted later.
    """
    # Disconnect its outputs (unitConversion.output → driven.attr)
    uc_out = cmds.listConnections(
        uc_node + ".output", source=False, destination=True,
        connections=True, plugs=True) or []
    for j in range(0, len(uc_out), 2):
        try:
            cmds.disconnectAttr(uc_out[j], uc_out[j + 1])
        except Exception:
            pass

    # Disconnect its inputs (source → unitConversion.input)
    uc_in = cmds.listConnections(
        uc_node + ".input", source=True, destination=False,
        connections=True, plugs=True) or []
    for j in range(0, len(uc_in), 2):
        try:
            cmds.disconnectAttr(uc_in[j + 1], uc_in[j])
        except Exception:
            pass

    orphan_set.add(uc_node)


def trigger_evaluation(node):
    """Force the solver to recompute by toggling the ``evaluate`` plug.

    The C++ node watches ``evaluate`` transitions::

        evaluate = 0  →  1   # triggers a full solve
        evaluate = 1  →  0   # resets the flag

    A ``cmds.refresh()`` between each step ensures the DG propagates
    the new value before the next ``setAttr``.
    """
    shape = get_shape(node)
    if not _exists(shape):
        return
    cmds.setAttr(shape + ".evaluate", 1)
    cmds.refresh()
    cmds.setAttr(shape + ".evaluate", 0)
    cmds.refresh()


def update_evaluation(node):
    """Alias for :func:`trigger_evaluation` — matches legacy MEL naming."""
    trigger_evaluation(node)


def compute_radius(node):
    r"""Compute and lock the radius value based on the current ``radiusType``.

    The radius feeds into the RBF kernel as a normalisation factor.
    Depending on the ``radiusType`` enum, it is derived from the
    solver's internal statistics:

    +---------+---------------------+--------------------------------------------+
    | Index   | radiusType          | Formula                                    |
    +=========+=====================+============================================+
    | 0       | Mean Distance       | :math:`r = \bar{d}`                        |
    +---------+---------------------+--------------------------------------------+
    | 1       | Variance            | :math:`r = \sigma^{2}`                     |
    +---------+---------------------+--------------------------------------------+
    | 2       | Standard Deviation  | :math:`r = \sqrt{\sigma^{2}}`              |
    +---------+---------------------+--------------------------------------------+
    | 3       | Custom              | User-editable, no automatic computation.   |
    +---------+---------------------+--------------------------------------------+

    Where :math:`\bar{d}` = ``meanDistance`` attribute and
    :math:`\sigma^{2}` = ``variance`` attribute, both computed
    internally by the C++ solver.

    The radius plug is **locked** for types 0-2 to prevent accidental
    manual edits, and **unlocked** for type 3 (Custom).
    """
    shape = get_shape(node)
    if not _exists(shape):
        return

    with undo_chunk("RBFtools: compute radius"):
        # Unlock first so we can write
        cmds.setAttr(shape + ".radius", lock=False)

        rtype = safe_get(shape + ".radiusType", 0)

        if rtype == 0:
            # r = meanDistance
            val = safe_get(shape + ".meanDistance", 0.0)
            cmds.setAttr(shape + ".radius", val)
            cmds.setAttr(shape + ".radius", lock=True)
        elif rtype == 1:
            # r = variance  (σ²)
            val = safe_get(shape + ".variance", 0.0)
            cmds.setAttr(shape + ".radius", val)
            cmds.setAttr(shape + ".radius", lock=True)
        elif rtype == 2:
            # r = √variance  (σ)
            var = safe_get(shape + ".variance", 0.0)
            cmds.setAttr(shape + ".radius", math.sqrt(max(var, 0.0)))
            cmds.setAttr(shape + ".radius", lock=True)
        # type 3 = Custom → leave unlocked, user edits directly

    trigger_evaluation(node)


def lock_radius_type(node):
    """Lock or unlock the ``radiusType`` based on the active kernel.

    When ``kernel == 0`` (Linear), the radius concept does not apply
    to the solver, so ``radiusType`` is locked to prevent confusion.
    For all other kernels (Gaussian, Thin Plate, etc.) it is unlocked.
    """
    shape = get_shape(node)
    if not _exists(shape):
        return

    with undo_chunk("RBFtools: lock radius type"):
        is_linear_kernel = (safe_get(shape + ".kernel", 1) == 0)
        cmds.setAttr(shape + ".radiusType", lock=is_linear_kernel)

    trigger_evaluation(node)


def read_current_values(node, attrs):
    """Read the current scene values for a list of attributes.

    Used to capture a "snapshot" of the driver / driven state when
    the user clicks *Add Pose*.

    Parameters
    ----------
    node : str
        The scene object.
    attrs : list[str]
        Attribute short names.

    Returns
    -------
    list[float]
        One value per attribute, defaulting to 0.0 on failure.
    """
    if not _exists(node):
        return [0.0] * len(attrs)
    return [safe_get("{}.{}".format(node, a), 0.0) for a in attrs]


# =====================================================================
#  Phase 2b — Pose data structure & management
# =====================================================================
# =====================================================================
#  8. Floating-point tolerance
# =====================================================================

# Default absolute tolerance for comparing Maya attribute values.
# Maya's internal double precision stores ~15 significant digits,
# but roundtrip through getAttr/setAttr introduces noise in the
# last 5–6 digits.  1e-6 provides a comfortable safety margin.
FLOAT_ABS_TOL = 1e-6


def float_eq(a, b, abs_tol=FLOAT_ABS_TOL):
    """Tolerance-based floating-point equality.

    **Never use** ``a == b`` for Maya attribute values.

    Uses :func:`math.isclose` with *abs_tol* only (no relative
    tolerance) because RBF pose values can legitimately be zero,
    and a relative comparison to zero is meaningless.

    Parameters
    ----------
    a, b : float
        Values to compare.
    abs_tol : float
        Absolute tolerance.  Default :data:`FLOAT_ABS_TOL` = 1e-6.

    Examples
    --------
    >>> float_eq(0.0, 1e-8)
    True
    >>> float_eq(1.0, 1.0 + 1e-4)
    False
    """
    return math.isclose(a, b, abs_tol=abs_tol, rel_tol=0.0)


def vector_eq(vec_a, vec_b, abs_tol=FLOAT_ABS_TOL):
    """Element-wise :func:`float_eq` for two equal-length float lists.

    Returns ``False`` immediately if lengths differ (short-circuit).
    """
    if len(vec_a) != len(vec_b):
        return False
    return all(float_eq(a, b, abs_tol) for a, b in zip(vec_a, vec_b))


# =====================================================================
#  9. PoseData — typed transport object
# =====================================================================

class PoseData(object):
    """Typed transport object representing one RBF pose.

    Using ``__slots__`` for memory efficiency and attribute-access safety
    (prevents accidental typo-based attribute creation).

    Attributes
    ----------
    index : int
        Pose index in the ``poses[]`` multi-instance array.
    inputs : list[float]
        Driver attribute snapshot (one value per ``input[i]``).
    values : list[float]
        Driven attribute snapshot (one value per ``output[i]``).
    radius : float
        Commit 1 (M_PER_POSE_SIGMA): per-pose RBF kernel σ. Default
        ``DEFAULT_POSE_RADIUS`` (5.0) for newly-created poses; legacy
        nodes (no ``poseRadius[]`` plug populated) round-trip through
        the same default. Constructors taking only ``(index, inputs,
        values)`` remain valid — radius is keyword-only with default.

    Design note
    -----------
    This is a **transport object** — it carries data between core
    functions and the UI layer.  It is intentionally not a ``dict``
    so that misspelled keys become immediate ``AttributeError`` s
    rather than silent ``KeyError`` / ``None`` bugs.
    """

    __slots__ = ("index", "inputs", "values", "radius")

    def __init__(self, index, inputs, values, radius=None):
        self.index  = int(index)
        self.inputs = list(inputs)
        self.values = list(values)
        # Commit 1: positional-compat — None => DEFAULT_POSE_RADIUS so
        # all 6 historical PoseData(idx, in, val) callsites keep working.
        self.radius = (DEFAULT_POSE_RADIUS
                       if radius is None
                       else float(radius))

    def __repr__(self):
        return ("PoseData(index={}, inputs={}, values={}, "
                "radius={})").format(
                    self.index, self.inputs, self.values, self.radius)

    def __eq__(self, other):
        """Tolerance-based equality (see :func:`float_eq`).

        Commit 1: radius participates in equality but uses
        :func:`float_eq` so legacy poses (radius == DEFAULT) compare
        bit-equal to JSON-deserialised ones."""
        if not isinstance(other, PoseData):
            return NotImplemented
        return (self.index == other.index
                and vector_eq(self.inputs, other.inputs)
                and vector_eq(self.values, other.values)
                and float_eq(self.radius, other.radius))

    def __ne__(self, other):
        result = self.__eq__(other)
        if result is NotImplemented:
            return result
        return not result


# =====================================================================
#  10. Pose CRUD — reading from the RBFtools node
# =====================================================================

def _multi_indices(shape, attr):
    """Return the existing multi-instance indices for *attr*, or ``[]``.

    Maya's multi-instance arrays can be **sparse** — e.g. indices
    ``[0, 2, 5]`` with gaps.  Always iterate over the actual index
    list, never assume contiguous ``range(n)``.

    Parameters
    ----------
    shape : str
        The ``RBFtools`` shape node.
    attr : str
        Top-level multi attr name (``"poses"``, ``"input"``, ``"output"``).
    """
    try:
        return cmds.getAttr("{}.{}".format(shape, attr),
                            multiIndices=True) or []
    except Exception:
        return []


def read_all_poses(node):
    """Read every pose stored on the ``RBFtools`` node.

    Each pose lives in the multi-instance compound::

        shape.poses[p].poseInput[i]   — driver snapshot values
        shape.poses[p].poseValue[i]   — driven snapshot values

    The input/output **sizes** (number of driver / driven attrs)
    are inferred from the ``input`` and ``output`` multi-attr sizes,
    which reflect how many driver/driven attributes are wired.

    Parameters
    ----------
    node : str
        Transform or shape name.

    Returns
    -------
    list[PoseData]
        Ordered by pose index.  Empty list if the node has no poses
        or is not in RBF mode.

    Sparse-array safety
    -------------------
    ``multiIndices=True`` returns only *existing* indices — we never
    assume contiguous ``range(n)``.  Each ``poseInput[i]`` read is
    individually guarded by :func:`safe_get`.
    """
    shape = get_shape(node)
    if not _exists(shape):
        return []

    # Only meaningful in RBF mode (type == 1)
    if safe_get(shape + ".type", 0) != 1:
        return []

    # Determine dimensionality from the wired input/output arrays
    try:
        n_inputs = cmds.getAttr(shape + ".input", size=True)
    except Exception:
        n_inputs = 0
    try:
        n_outputs = cmds.getAttr(shape + ".output", size=True)
    except Exception:
        n_outputs = 0

    if n_inputs == 0 or n_outputs == 0:
        return []

    pose_indices = _multi_indices(shape, "poses")

    # If pose[0] is missing, synthesise a virtual zero-valued rest pose
    # in the returned list WITHOUT writing to the scene.
    prepend_rest = (pose_indices and pose_indices[0] != 0)

    poses = []
    if prepend_rest:
        # Commit 1: synthetic rest pose uses default σ; never written
        # back to scene unless the user explicitly creates pose 0.
        poses.append(PoseData(0,
                              [0.0] * n_inputs,
                              [0.0] * n_outputs,
                              radius=DEFAULT_POSE_RADIUS))

    for pid in pose_indices:
        inputs = [
            safe_get("{}.poses[{}].poseInput[{}]".format(shape, pid, i), 0.0)
            for i in range(n_inputs)
        ]
        values = [
            safe_get("{}.poses[{}].poseValue[{}]".format(shape, pid, i), 0.0)
            for i in range(n_outputs)
        ]
        # Commit 1 (M_PER_POSE_SIGMA): per-pose σ lives at the
        # top-level multi attr ``shape.poseRadius[pid]`` (parallel
        # array, NOT a child of poses[]). Legacy v5-pre-M_PERPOSE
        # nodes have no slot at this index — safe_get returns the
        # fallback (DEFAULT_POSE_RADIUS) so old scenes round-trip
        # unchanged.
        radius = safe_get("{}.poseRadius[{}]".format(shape, pid),
                          DEFAULT_POSE_RADIUS)
        if not radius or radius <= 0.0:
            radius = DEFAULT_POSE_RADIUS
        poses.append(PoseData(pid, inputs, values, radius=radius))

    return poses


# =====================================================================
#  10b. Base pose values — Commit 1 (M_BASE_POSE)
# =====================================================================


def read_base_pose_values(node):
    """Read ``shape.basePoseValue[]`` as a flat list[float].

    Commit 1 (M_BASE_POSE): per-output additive baseline applied at
    plugin ``setOutputValues`` time. Empty plug / legacy node returns
    ``[]``; the plugin treats absent indices as 0.0 (bit-identical to
    pre-M_BASE_POSE behaviour).

    Sparse-array safety: ``multiIndices=True`` skips holes. Returned
    list is **dense**, indexed by output channel; missing indices are
    filled with 0.0 up to ``output[]`` size. Returns ``[]`` when the
    plug has never been written so callers can distinguish "no
    baseline configured" from "all-zero baseline".
    """
    shape = get_shape(node)
    if not _exists(shape):
        return []
    try:
        n_outputs = cmds.getAttr(shape + ".output", size=True)
    except Exception:
        n_outputs = 0
    indices = _multi_indices(shape, "basePoseValue")
    if not indices:
        return []
    result = [0.0] * max(n_outputs, max(indices) + 1)
    for idx in indices:
        result[idx] = safe_get(
            "{}.basePoseValue[{}]".format(shape, idx), 0.0)
    return result


def write_base_pose_values(node, values):
    """Write ``shape.basePoseValue[i] = values[i]`` for each i.

    Commit 1 (M_BASE_POSE): does NOT clear higher indices; callers
    that shrink the baseline must pass a full-length list and rely on
    the plugin's sparse-array semantics for trailing absent indices
    (which evaluate to 0.0 — same as pre-M_BASE_POSE behaviour).
    """
    shape = get_shape(node)
    if not _exists(shape):
        return
    with undo_chunk("RBFtools: write basePoseValue"):
        for i, v in enumerate(values or []):
            try:
                cmds.setAttr(
                    "{}.basePoseValue[{}]".format(shape, i), float(v))
            except Exception as exc:
                cmds.warning(
                    "write_base_pose_values: index {} failed: {}".format(
                        i, exc))


# =====================================================================
#  11. Pose CRUD — writing to the RBFtools node
# =====================================================================

def _write_pose_to_node(shape, sequential_idx, pose):
    """Write one :class:`PoseData` into ``shape.poses[sequential_idx]``.

    Parameters
    ----------
    shape : str
        The ``RBFtools`` shape node.
    sequential_idx : int
        **Contiguous** array slot on the node (0, 1, 2, …).
        This is distinct from ``pose.index`` which is the UI-facing
        identifier.  The node stores poses in a packed array; the UI
        may use arbitrary indices (e.g. after deletions).
    pose : PoseData
        Source data.

    Multi-instance attribute layout::

        poses[p].poseInput[0]  =  driver_attr_0_value
        poses[p].poseInput[1]  =  driver_attr_1_value
        ...
        poses[p].poseValue[0]  =  driven_attr_0_value
        poses[p].poseValue[1]  =  driven_attr_1_value
    """
    for i, v in enumerate(pose.inputs):
        try:
            cmds.setAttr(
                "{}.poses[{}].poseInput[{}]".format(shape, sequential_idx, i), v)
        except Exception as exc:
            cmds.warning("_write_pose_to_node: poseInput[{}][{}] failed: {}".format(
                sequential_idx, i, exc))
    for i, v in enumerate(pose.values):
        try:
            cmds.setAttr(
                "{}.poses[{}].poseValue[{}]".format(shape, sequential_idx, i), v)
        except Exception as exc:
            cmds.warning("_write_pose_to_node: poseValue[{}][{}] failed: {}".format(
                sequential_idx, i, exc))
    # Commit 1 (M_PER_POSE_SIGMA): write per-pose σ. Indexed parallel
    # to poses[sequential_idx]. Failure non-fatal — legacy plugins
    # without the poseRadius attr just emit a warning and the caller
    # gets pre-M_PERPOSE behaviour (global radius for all poses).
    try:
        radius = float(getattr(pose, "radius", DEFAULT_POSE_RADIUS))
        if radius <= 0.0:
            radius = DEFAULT_POSE_RADIUS
        cmds.setAttr(
            "{}.poseRadius[{}]".format(shape, sequential_idx), radius)
    except Exception as exc:
        cmds.warning(
            "_write_pose_to_node: poseRadius[{}] failed (legacy "
            "plugin without per-pose σ?): {}".format(
                sequential_idx, exc))


# =====================================================================
#  11b. Output baselines — Milestone 1.2 (v5 PART C.2.4 / 铁律 B6)
# =====================================================================


def _is_scale_attr(attr_name):
    """Return ``True`` if *attr_name* names a Maya scale channel.

    Matches exact long (``scaleX/Y/Z``) and short (``sx/sy/sz``) names.
    Used to force a 1.0 training baseline on scale outputs so a
    transient driven.scale == 0 at Apply time cannot silently poison
    the solver and collapse the mesh on t-pose recall.
    """
    return attr_name in SCALE_ATTR_NAMES


def capture_output_baselines(driven_node, driven_attrs, poses=None):
    """Collect per-output ``(base_value, is_scale)`` for the driven attrs.

    Source priority (v5 addendum 2026-04-24 §M1.2):

    1. If *poses* is provided AND ``poses[0]`` has all driver inputs
       ≈ 0 (the rest pose by convention), use ``poses[0].values[i]``
       as the baseline. Deterministic, reproducible from stored data.
    2. Otherwise fall back to the current scene value at
       ``driven_node.attr``. Emits ``cmds.warning`` because this
       depends on the user having the rig in rest pose at Apply time.

    **Scale channels always override the source to 1.0** regardless of
    captured value, as a defense against pose[0] / scene being at 0.

    Parameters
    ----------
    driven_node : str
        The node whose attributes are driven by ``output[]``.
    driven_attrs : list[str]
        Ordered attribute names (same order as the node's ``output[]``).
    poses : list[PoseData] or None, optional
        Full pose list. When provided and ``poses[0]`` is a rest pose,
        ``poses[0].values`` acts as the baseline source.

    Returns
    -------
    list[tuple[float, bool]]
        ``[(base_value, is_scale), ...]`` indexed by ``driven_attrs``.
    """
    rest_from_pose0 = None
    if poses and len(poses) > 0:
        p0 = poses[0]
        if p0.inputs and all(float_eq(v, 0.0) for v in p0.inputs):
            rest_from_pose0 = list(p0.values)

    if rest_from_pose0 is None and _exists(driven_node):
        cmds.warning(
            "capture_output_baselines: no rest-pose row found in pose[0]; "
            "falling back to current scene value on '{}' — ensure the rig "
            "is in rest pose before Apply.".format(driven_node))

    baselines = []
    for i, attr in enumerate(driven_attrs):
        is_scale = _is_scale_attr(attr)
        if is_scale:
            base_value = 1.0
        elif rest_from_pose0 is not None and i < len(rest_from_pose0):
            base_value = float(rest_from_pose0[i])
        else:
            plug = "{}.{}".format(driven_node, attr)
            try:
                base_value = float(cmds.getAttr(plug))
            except Exception as exc:
                cmds.warning(
                    "capture_output_baselines: getAttr {} failed: {}; "
                    "using 0.0".format(plug, exc))
                base_value = 0.0
        baselines.append((base_value, is_scale))
    return baselines


def write_output_baselines(node, baselines):
    """Write ``(base_value, is_scale)`` pairs onto the solver node.

    Fills ``shape.baseValue[i]`` and ``shape.outputIsScale[i]`` for each
    index *i* in *baselines*. No-op if the shape does not exist; each
    per-index write is guarded so one failure does not abort the rest.
    """
    shape = get_shape(node)
    if not _exists(shape):
        return
    for i, (bv, is_scale) in enumerate(baselines):
        bv_plug = "{}.baseValue[{}]".format(shape, i)
        is_plug = "{}.outputIsScale[{}]".format(shape, i)
        try:
            cmds.setAttr(bv_plug, float(bv))
        except Exception as exc:
            cmds.warning("write_output_baselines: setAttr {} failed: {}".format(
                bv_plug, exc))
        try:
            cmds.setAttr(is_plug, bool(is_scale))
        except Exception as exc:
            cmds.warning("write_output_baselines: setAttr {} failed: {}".format(
                is_plug, exc))


def read_output_baselines(node):
    """Read ``(base_value, is_scale)`` back from the node.

    Returns
    -------
    list[tuple[float, bool]]
        Empty list if the node has no ``baseValue`` / ``outputIsScale``
        multi indices set (e.g., a v4 rig before its first v5 Apply).
    """
    shape = get_shape(node)
    if not _exists(shape):
        return []
    try:
        bv_ids = cmds.getAttr(shape + ".baseValue", multiIndices=True) or []
    except Exception:
        return []
    try:
        is_ids = cmds.getAttr(shape + ".outputIsScale", multiIndices=True) or []
    except Exception:
        is_ids = []
    max_idx = max(list(bv_ids) + list(is_ids) + [-1])
    if max_idx < 0:
        return []
    out = []
    for i in range(max_idx + 1):
        bv = 0.0
        is_scale = False
        if i in bv_ids:
            try:
                bv = float(cmds.getAttr("{}.baseValue[{}]".format(shape, i)))
            except Exception:
                pass
        if i in is_ids:
            try:
                is_scale = bool(cmds.getAttr(
                    "{}.outputIsScale[{}]".format(shape, i)))
            except Exception:
                pass
        out.append((bv, is_scale))
    return out


def _node_has_baseline_schema(node):
    """Return True when *node* already has a v5 baseline array written.

    Used by :func:`apply_poses` to emit a one-time upgrade notice when
    an old v4 node (poses present, no baseline array) is first applied
    under v5.
    """
    shape = get_shape(node)
    if not _exists(shape):
        return False
    try:
        ids = cmds.getAttr(shape + ".baseValue", multiIndices=True) or []
    except Exception:
        return False
    return bool(ids)


# =====================================================================
#  11c. Local-Transform snapshot — Milestone 2.3 (v5 PART D.5 / 铁律 B10)
# =====================================================================


def capture_per_pose_local_transforms(driven_node, driven_attrs, poses):
    """Replay each pose through *driven_node* and snapshot its local Transform.

    **Single-sever / single-restore lifecycle** (v5 addendum §M2.3 —
    refinement 1): incoming connections on ``driven_attrs`` are severed
    ONCE before the loop and restored ONCE after. The replay loop only
    runs ``setAttr`` and ``get_local_matrix`` — never disconnects nor
    reconnects mid-loop. This avoids DG dirty-storms and short-lived
    intermediate evaluation states that would corrupt downstream nodes.

    **Non-driven-channel freeze contract** (addendum §M2.3 — refinement
    2): transform channels NOT in ``driven_attrs`` keep their
    Apply-time scene state throughout the replay. If the user left the
    driven_node at a stale orientation at Apply time, that orientation
    is baked into every pose's quaternion. Users should reset the
    driven_node to rest before calling Apply; M3 UI will automate this.

    Parameters
    ----------
    driven_node : str
        Scene node whose local Transform is being captured.
    driven_attrs : list[str]
        Attributes to set per pose (typically a subset of transform
        channels).
    poses : list[PoseData]
        Same ordering as the caller's ``poses`` — returned list aligns
        element-wise.

    Returns
    -------
    list[dict]
        Per-pose ``{"translate":(3), "quat":(4), "scale":(3)}``.
        Always the same length as *poses*. On ``driven_node`` missing
        or ``is_blend_shape(driven_node)`` or empty ``driven_attrs``
        the list is filled with :data:`IDENTITY_LOCAL_TRANSFORM`.
    """
    n_poses = len(poses)
    if not _exists(driven_node):
        return [IDENTITY_LOCAL_TRANSFORM] * n_poses
    if is_blend_shape(driven_node):
        # blendShape has no local Transform concept — see addendum
        # §M2.3 decision (C)①.
        return [IDENTITY_LOCAL_TRANSFORM] * n_poses
    if not driven_attrs:
        cmds.warning(
            "capture_per_pose_local_transforms: driven_attrs is empty; "
            "skipping local Transform capture.")
        return [IDENTITY_LOCAL_TRANSFORM] * n_poses

    # === single sever (before loop) ===
    saved_conns = []
    saved_values = []
    for attr in driven_attrs:
        plug = "{}.{}".format(driven_node, attr)
        conn = _safe_disconnect_incoming(plug)
        saved_conns.append((plug, conn))
        try:
            saved_values.append(cmds.getAttr(plug))
        except Exception:
            saved_values.append(None)

    results = []
    try:
        # === replay loop: only setAttr + read matrix, never disconnect ===
        for pose in poses:
            for i, attr in enumerate(driven_attrs):
                if i >= len(pose.values):
                    break
                plug = "{}.{}".format(driven_node, attr)
                try:
                    cmds.setAttr(plug, pose.values[i])
                except Exception as exc:
                    cmds.warning(
                        "capture_per_pose_local_transforms: setAttr {} "
                        "failed: {}".format(plug, exc))
            mat = get_local_matrix(driven_node)
            results.append(decompose_matrix_quat(mat))
    finally:
        # === single restore (after loop, even on exception) ===
        for (plug, conn), orig in zip(saved_conns, saved_values):
            if orig is not None:
                try:
                    cmds.setAttr(plug, orig)
                except Exception as exc:
                    cmds.warning(
                        "capture_per_pose_local_transforms: restore "
                        "setAttr {} failed: {}".format(plug, exc))
            if conn is not None:
                try:
                    cmds.connectAttr(conn[0], conn[1])
                except Exception as exc:
                    cmds.warning(
                        "capture_per_pose_local_transforms: reconnect "
                        "{} -> {} failed: {}".format(conn[0], conn[1], exc))

    # Pad if the replay bailed early for any reason.
    while len(results) < n_poses:
        results.append(IDENTITY_LOCAL_TRANSFORM)
    return results


def write_pose_local_transforms(node, local_transforms):
    """Write per-pose Transform snapshots to shape.poses[p].poseLocalTransform.*."""
    shape = get_shape(node)
    if not _exists(shape):
        return
    for p, xf in enumerate(local_transforms):
        t = xf.get("translate", IDENTITY_LOCAL_TRANSFORM["translate"])
        q = xf.get("quat",      IDENTITY_LOCAL_TRANSFORM["quat"])
        s = xf.get("scale",     IDENTITY_LOCAL_TRANSFORM["scale"])
        try:
            cmds.setAttr(
                "{}.poses[{}].poseLocalTransform.poseLocalTranslate".format(shape, p),
                float(t[0]), float(t[1]), float(t[2]), type="double3")
        except Exception as exc:
            cmds.warning("write_pose_local_transforms: translate[{}] "
                         "failed: {}".format(p, exc))
        try:
            # double4 has no native compound setAttr — set each child.
            for i, v in enumerate(q):
                cmds.setAttr(
                    "{}.poses[{}].poseLocalTransform.poseLocalQuat{}".format(
                        shape, p, i), float(v))
        except Exception:
            # Fall back: write as 4-tuple if Maya accepts it.
            try:
                cmds.setAttr(
                    "{}.poses[{}].poseLocalTransform.poseLocalQuat".format(shape, p),
                    float(q[0]), float(q[1]), float(q[2]), float(q[3]),
                    type="double4")
            except Exception as exc:
                cmds.warning("write_pose_local_transforms: quat[{}] "
                             "failed: {}".format(p, exc))
        try:
            cmds.setAttr(
                "{}.poses[{}].poseLocalTransform.poseLocalScale".format(shape, p),
                float(s[0]), float(s[1]), float(s[2]), type="double3")
        except Exception as exc:
            cmds.warning("write_pose_local_transforms: scale[{}] "
                         "failed: {}".format(p, exc))


def read_pose_local_transforms(node):
    """Read back per-pose local Transforms. Returns empty list when the
    node has no poseLocalTransform data (v4 rig / fresh node).
    """
    shape = get_shape(node)
    if not _exists(shape):
        return []
    try:
        ids = cmds.getAttr(shape + ".poses", multiIndices=True) or []
    except Exception:
        return []
    if not ids:
        return []
    out = []
    for p in sorted(ids):
        try:
            t = cmds.getAttr(
                "{}.poses[{}].poseLocalTransform.poseLocalTranslate".format(
                    shape, p))[0]
        except Exception:
            t = IDENTITY_LOCAL_TRANSFORM["translate"]
        try:
            q = cmds.getAttr(
                "{}.poses[{}].poseLocalTransform.poseLocalQuat".format(
                    shape, p))[0]
        except Exception:
            q = IDENTITY_LOCAL_TRANSFORM["quat"]
        try:
            s = cmds.getAttr(
                "{}.poses[{}].poseLocalTransform.poseLocalScale".format(
                    shape, p))[0]
        except Exception:
            s = IDENTITY_LOCAL_TRANSFORM["scale"]
        out.append({"translate": tuple(t), "quat": tuple(q),
                    "scale": tuple(s)})
    return out


def read_driver_rotate_orders(node):
    """Return ``driverInputRotateOrder[]`` as a dense list (M2.1a).

    Sparse indices are densified by reading the highest existing
    index + 1 and filling missing slots with 0 (xyz default).
    Returns empty list when the multi has no entries.
    """
    shape = get_shape(node)
    if not _exists(shape):
        return []
    try:
        ids = cmds.getAttr(
            shape + ".driverInputRotateOrder", multiIndices=True) or []
    except Exception:
        return []
    if not ids:
        return []
    out = [0] * (max(ids) + 1)
    for i in ids:
        try:
            out[i] = int(cmds.getAttr(
                "{}.driverInputRotateOrder[{}]".format(shape, i)))
        except Exception:
            pass
    return out


def write_driver_rotate_orders(node, values):
    """Write a dense list of rotate-order ints to the multi.

    Reuses :func:`set_node_multi_attr` (transactional clear-then-write
    per addendum §M2.4a)."""
    set_node_multi_attr(node, "driverInputRotateOrder", list(values or []))


def read_quat_group_starts(node):
    """Return ``outputQuaternionGroupStart[]`` as an ordered int list."""
    shape = get_shape(node)
    if not _exists(shape):
        return []
    try:
        ids = cmds.getAttr(
            shape + ".outputQuaternionGroupStart",
            multiIndices=True) or []
    except Exception:
        return []
    out = []
    for i in sorted(ids):
        try:
            out.append(int(cmds.getAttr(
                "{}.outputQuaternionGroupStart[{}]".format(shape, i))))
        except Exception:
            pass
    return out


def write_quat_group_starts(node, starts):
    """Write a list of quat-group leader indices to the multi."""
    set_node_multi_attr(node, "outputQuaternionGroupStart",
                        list(starts or []))


def auto_alias_outputs(node, driver_attrs, driven_attrs, force=False):
    """Generate human-readable aliases on the shape's input[]/output[]
    multi plugs (Milestone 3.7).

    Default-mode (``force=False``) preserves user-set aliases by only
    clearing those classified as RBFtools-managed via
    :func:`core_alias.is_rbftools_managed_alias` (E.1 contract).

    Force-mode (``force=True``) wipes every alias on the shape before
    regenerating — meant for the "Force Regenerate" Tools menu entry
    behind a confirm dialog.

    Quat-group leaders (output indices in ``outputQuaternionGroupStart[]``)
    receive the ``<base>QX/QY/QZ/QW`` quartet instead of the standard
    ``out_<x>`` form.

    See addendum §M3.7 for the driven/driver write-boundary contract:
    aliases are written to the **shape**'s plugs, NOT to the
    driver/driven scene nodes themselves.

    Parameters
    ----------
    node : str
        Transform or shape of the RBFtools node.
    driver_attrs, driven_attrs : list[str]
        Ordered attribute names — must match the input[]/output[]
        index ordering. Pass empty list to skip a side.
    force : bool, optional
        Clear ALL aliases (managed + user-set) before regenerating.
        Default False.

    Returns
    -------
    dict
        ``{"input": {idx: alias}, "output": {idx: alias}}``.
    """
    from RBFtools import core_alias

    shape = get_shape(node)
    if not _exists(shape):
        return {"input": {}, "output": {}}

    quat_starts = []
    try:
        ids = cmds.getAttr(
            shape + ".outputQuaternionGroupStart",
            multiIndices=True) or []
        for i in ids:
            quat_starts.append(int(cmds.getAttr(
                "{}.outputQuaternionGroupStart[{}]".format(shape, i))))
    except Exception:
        quat_starts = []

    with undo_chunk("RBFtools: auto-alias outputs"):
        return core_alias.apply_aliases(
            shape,
            driver_attrs or [],
            driven_attrs or [],
            quat_group_starts=quat_starts,
            force=force,
        )


def write_pose_swing_twist_cache(node, poses):
    """Initialise the M2.5 per-pose SwingTwist decomposition cache
    to its **unpopulated default** state for every pose.

    M2.5 ships the cache **schema** plus this Apply-time
    initialiser. The actual decomposition values are populated by
    a follow-up commit (M2.5b / M5) once a mayapy benchmark
    environment is available to verify both the C++ compute()
    consumer and the Python decomposition path against real Maya
    behaviour.

    Defaults written per pose:

      * ``poseSwingQuat``   = ``(0, 0, 0, 1)`` (identity quat)
      * ``poseTwistAngle``  = 0.0
      * ``poseSwingWeight`` = 1.0
      * ``poseTwistWeight`` = 1.0
      * ``poseSigma``       = -1.0 — sentinel meaning "cache NOT
        populated" AND "use global radius" (v5 PART E.10
        forward-compat). Future compute() consumer treats
        ``poseSigma == -1.0`` as cache miss → falls back to live
        :func:`decomposeSwingTwist`.

    Cache vs Schema Boundary (addendum §M2.5.4):
      Cache values are derived runtime state — **NOT** part of
      the JSON schema. ``core_json.py`` never reads or writes
      these fields; T_M2_5_CACHE_NOT_IN_SCHEMA permanent guard
      scans core_json / core_mirror / core_alias to enforce the
      boundary across all three "schema-adjacent" layers.
    """
    shape = get_shape(node)
    if not _exists(shape):
        return

    for seq_idx in range(len(poses)):
        base = "{}.poses[{}].poseSwingTwistCache".format(shape, seq_idx)
        try:
            cmds.setAttr(base + ".poseSwingQuat",
                         0.0, 0.0, 0.0, 1.0, type="double4")
            cmds.setAttr(base + ".poseTwistAngle", 0.0)
            cmds.setAttr(base + ".poseSwingWeight", 1.0)
            cmds.setAttr(base + ".poseTwistWeight", 1.0)
            cmds.setAttr(base + ".poseSigma", -1.0)  # sentinel
        except Exception as exc:
            cmds.warning(
                "write_pose_swing_twist_cache: pose[{}] setAttr "
                "failed: {} (cache stays unpopulated; compute() will "
                "fall back to live decompose)".format(seq_idx, exc))


def read_pose_swing_twist_cache(node):
    """Read back per-pose SwingTwist cache. Returns a list of dicts:
    ``[{"swing_quat": (sx,sy,sz,sw), "twist_angle": float,
        "swing_weight": float, "twist_weight": float, "sigma": float}, ...]``.

    Empty list when the node has no poses or is not a v5+ node.
    Used by future M3.5 Profiler / M5 perf analysis; M2.5 itself
    does not consume this read path."""
    shape = get_shape(node)
    if not _exists(shape):
        return []
    try:
        ids = cmds.getAttr(shape + ".poses", multiIndices=True) or []
    except Exception:
        return []
    out = []
    for p in sorted(ids):
        base = "{}.poses[{}].poseSwingTwistCache".format(shape, p)
        try:
            sq = cmds.getAttr(base + ".poseSwingQuat")[0]
        except Exception:
            sq = (0.0, 0.0, 0.0, 1.0)
        out.append({
            "swing_quat":   tuple(sq),
            "twist_angle":  float(safe_get(base + ".poseTwistAngle", 0.0)),
            "swing_weight": float(safe_get(base + ".poseSwingWeight", 1.0)),
            "twist_weight": float(safe_get(base + ".poseTwistWeight", 1.0)),
            "sigma":        float(safe_get(base + ".poseSigma", -1.0)),
        })
    return out


def apply_poses(node, driver_node, driven_node,
                driver_attrs, driven_attrs, poses):
    """Write pose data onto the solver node (no connections).

    This is the **Apply** button path.  It:

    1. Clears all existing multi-instance data on the node.
    2. Writes each :class:`PoseData` into ``shape.poses[p]``.
    3. Triggers a solver evaluation cycle.

    Connections are handled separately by :func:`connect_node`
    via the **Connect** button.

    Parameters
    ----------
    node : str
        Transform or shape of the ``RBFtools``.
    driver_node, driven_node : str
        The source and destination scene objects.
    driver_attrs, driven_attrs : list[str]
        Ordered attribute names on driver / driven.
    poses : list[PoseData]
        Ordered pose data from the UI table.
    """
    shape = get_shape(node)
    if not _exists(shape):
        return

    # v4 → v5 upgrade notice: a node with poses but no baseline array is
    # about to be re-applied under the v5 schema. Log only, never block.
    had_poses = False
    try:
        had_poses = bool(cmds.getAttr(shape + ".poses", multiIndices=True) or [])
    except Exception:
        had_poses = False
    if had_poses and not _node_has_baseline_schema(node):
        cmds.warning(
            "Upgrading node {} to v5 baseline schema".format(shape))

    with undo_chunk("RBFtools: apply poses"):
        # 1 — clear stale data (including any prior baseline arrays)
        clear_node_data(node)

        # 2 — write pose data (packed sequential indices)
        for seq_idx, pose in enumerate(poses):
            _write_pose_to_node(shape, seq_idx, pose)

        # 3 — M2.5: per-pose SwingTwist decomposition cache. Populated
        # for SwingTwist-encoded nodes (encoding == 4); other encodings
        # write defaults (poseSigma = -1.0 sentinel = "cache not
        # populated"). Cache is derived state — NOT in the JSON schema
        # (addendum §M2.5 Cache vs Schema Boundary Contract).
        # Failures emit warnings; cache miss falls back to live decompose
        # in compute() (forward-compat to the M2.5b/M5 consumer).
        try:
            write_pose_swing_twist_cache(node, poses)
        except Exception as exc:
            cmds.warning(
                "apply_poses: SwingTwist cache step failed: {} "
                "(continuing — cache miss falls back to live decompose)"
                .format(exc))

        # 4 — capture + write per-output baselines. pose[0] is the
        # preferred source when it is a rest row (all driver inputs 0);
        # otherwise the current scene value is used. Scale channels
        # always anchor at 1.0. See v5 addendum 2026-04-24 §M1.2.
        baselines = capture_output_baselines(
            driven_node, driven_attrs, poses=poses)
        write_output_baselines(node, baselines)

        # 5 — M2.3: replay each pose through driven_node and snapshot
        # its local Transform for engine-side consumption (PART D.5 /
        # 铁律 B10). Single-sever / single-restore lifecycle keeps the
        # scene clean. Non-driven channels are frozen at Apply-time
        # scene state — users should reset driven_node to rest before
        # Apply. See v5 addendum 2026-04-24 §M2.3.
        local_xforms = capture_per_pose_local_transforms(
            driven_node, driven_attrs, poses)
        write_pose_local_transforms(node, local_xforms)

        # 6 — M3.7: auto-generate human-readable aliases on input[] /
        # output[] multi plugs. Preserves user-set aliases (E.1).
        # Failures emit warnings but never break the Apply chain — see
        # core_alias module docstring for the write-boundary contract.
        try:
            auto_alias_outputs(node, driver_attrs, driven_attrs,
                               force=False)
        except Exception as exc:
            cmds.warning(
                "apply_poses: auto-alias step failed: {} "
                "(continuing — aliases are advisory)".format(exc))

        # 7 — trigger evaluation cycle
        cmds.setAttr(shape + ".evaluate", 0)
        cmds.setAttr(shape + ".evaluate", 1)


def connect_poses(node, driver_node, driven_node,
                  driver_attrs, driven_attrs, objects):
    """Wire poses by **connecting** selected objects' attributes directly.

    This is the **Connect** button path.  Instead of baking static
    float values, each pose slot is live-connected to a scene object::

        objects[p].driver_attr  →  shape.poses[p].poseInput[i]
        objects[p].driven_attr  →  shape.poses[p].poseValue[i]

    This enables live-updating setups where the solver re-reads pose
    data every evaluation.

    Parameters
    ----------
    node : str
        Transform or shape of the ``RBFtools``.
    driver_node, driven_node : str
        Source / destination objects for ``input[]`` / ``output[]`` wiring.
    driver_attrs, driven_attrs : list[str]
        Attribute names.
    objects : list[str]
        Selected scene objects — one per pose.
    """
    shape = get_shape(node)
    if not _exists(shape) or not objects:
        return

    with undo_chunk("RBFtools: connect poses"):
        # Clear existing data
        clear_node_data(node)

        # Wire driver inputs (same as apply)
        wire_driver_inputs(node, driver_node, driver_attrs)

        # Connect each object as a pose source
        for p, obj in enumerate(objects):
            if not _exists(obj):
                cmds.warning("connect_poses: object '{}' does not exist, "
                             "skipping pose {}".format(obj, p))
                continue
            for i, attr in enumerate(driver_attrs):
                src = "{}.{}".format(obj, attr)
                dst = "{}.poses[{}].poseInput[{}]".format(shape, p, i)
                try:
                    cmds.connectAttr(src, dst, force=True)
                except Exception as exc:
                    cmds.warning("connect_poses: {} → {} failed: {}".format(
                        src, dst, exc))

            for i, attr in enumerate(driven_attrs):
                src = "{}.{}".format(obj, attr)
                dst = "{}.poses[{}].poseValue[{}]".format(shape, p, i)
                try:
                    cmds.connectAttr(src, dst, force=True)
                except Exception as exc:
                    cmds.warning("connect_poses: {} → {} failed: {}".format(
                        src, dst, exc))

        # Wire driven outputs
        wire_driven_outputs(node, driven_node, driven_attrs)

        # Trigger evaluation
        cmds.setAttr(shape + ".evaluate", 0)
        cmds.setAttr(shape + ".evaluate", 1)


_RBF_SUBSCRIPT_RE = re.compile(r"\[(\d+)\]$")


def _occupied_input_subscripts(shape):
    """Return the set of subscripts where ``shape.input[i]`` currently
    has an incoming connection. Walked via ``cmds.listConnections``
    on the parent multi-attr with ``connections=True, plugs=True``;
    pairs come back as ``[shape.input[i], src_plug, ...]``."""
    conns = cmds.listConnections(
        shape + ".input", source=True, destination=False,
        plugs=True, connections=True) or []
    out = set()
    for k in range(0, len(conns), 2):
        m = _RBF_SUBSCRIPT_RE.search(conns[k])
        if m:
            out.add(int(m.group(1)))
    return out


def _occupied_output_subscripts(shape):
    """Twin of :func:`_occupied_input_subscripts` for the driven side
    — ``shape.output[i]`` driving an external attr."""
    conns = cmds.listConnections(
        shape + ".output", source=False, destination=True,
        plugs=True, connections=True) or []
    out = set()
    for k in range(0, len(conns), 2):
        m = _RBF_SUBSCRIPT_RE.search(conns[k])
        if m:
            out.add(int(m.group(1)))
    return out


def _next_free_subscript(occupied):
    """Return the smallest non-negative int not in ``occupied``."""
    i = 0
    while i in occupied:
        i += 1
    return i


def _subscript_of_existing_input(bone_plug, shape):
    """If ``bone_plug`` is already connected to some
    ``shape.input[i]``, return ``i``; else None.

    M_UNITCONV_PURGE (2026-04-28): ``skipConversionNodes=True`` is
    REQUIRED here. Maya silently inserts a ``unitConversion`` node
    between rotation/dimensionless plug pairs (e.g. ``bone.rotateX``
    in degrees -> ``input[i]`` in radians). Without skipConv,
    ``listConnections`` returns the conversion node's input plug
    instead of ``shape.input[i]`` — the prefix match misses, the
    function falsely reports "not connected", and connect_routed
    appends a NEW slot leaving a ghost wire at the old subscript.
    Setting skipConv=True asks Maya to look THROUGH the conversion
    node and surface the real downstream destination."""
    conns = cmds.listConnections(
        bone_plug, source=False, destination=True,
        plugs=True, skipConversionNodes=True) or []
    prefix = "{}.input[".format(shape)
    for plug in conns:
        if plug.startswith(prefix):
            m = _RBF_SUBSCRIPT_RE.search(plug)
            if m:
                return int(m.group(1))
    return None


def _subscript_of_existing_output(shape, dst_plug):
    """Twin: if ``dst_plug`` is driven by some ``shape.output[i]``,
    return ``i``; else None. Same skipConversionNodes contract as
    :func:`_subscript_of_existing_input`."""
    conns = cmds.listConnections(
        dst_plug, source=True, destination=False,
        plugs=True, skipConversionNodes=True) or []
    prefix = "{}.output[".format(shape)
    for plug in conns:
        if plug.startswith(prefix):
            m = _RBF_SUBSCRIPT_RE.search(plug)
            if m:
                return int(m.group(1))
    return None


def _direct_node_at_subscript(shape, side, idx):
    """Return the immediate (non-skipConv) connected node name at
    ``shape.<side>[idx]`` — i.e. what is PHYSICALLY wired to that
    multi slot, which may be a unitConversion node that the
    skipConv-flavoured queries hide. Returns None when nothing is
    connected (or on query failure)."""
    plug = "{}.{}[{}]".format(shape, side, idx)
    if side == "input":
        nodes = cmds.listConnections(
            plug, source=True, destination=False,
            plugs=False, connections=False) or []
    else:
        nodes = cmds.listConnections(
            plug, source=False, destination=True,
            plugs=False, connections=False) or []
    return nodes[0] if nodes else None


def _disconnect_or_purge(shape, side, idx, other_plug):
    """斩草除根 — sever the wire at ``shape.<side>[idx]`` AND drop
    the multi-subscript itself so the array stays packed.

    Three-step sever protocol:
      1. If a ``unitConversion`` node sits between the bone and the
         RBF multi (Maya's silent rotation-channel insertion),
         ``cmds.delete()`` that conversion node — this severs both
         legs of the conversion in one shot.
      2. Otherwise issue a plain ``cmds.disconnectAttr`` on the
         direct (bone <-> shape) pair.
      3. M_REMOVE_MULTI (2026-04-28): regardless of which path
         severed the wire, fire
         ``cmds.removeMultiInstance(shape.<side>[idx], b=True)``
         to physically destroy the multi-array slot. Without this,
         the subscript lingers as an "empty index" — visually noisy
         in Node Editor + future occupied-subscript queries can be
         tricked into thinking the slot is still in use.

    Returns True iff the wire was successfully torn down (either
    via delete or disconnectAttr); the slot-removal step is best-
    effort and never blocks the return value.
    """
    direct = _direct_node_at_subscript(shape, side, idx)
    severed = False
    if direct is not None:
        try:
            ntype = cmds.nodeType(direct)
        except Exception:
            ntype = ""
        if ntype == "unitConversion":
            cmds.warning(
                "disconnect: deleting unitConversion {!r} at "
                "{}.{}[{}]".format(direct, shape, side, idx))
            try:
                cmds.delete(direct)
                severed = True
            except Exception as exc:
                cmds.warning(
                    "disconnect: failed to delete unitConversion "
                    "{!r}: {}".format(direct, exc))
                # Fall through to plain disconnect attempt below.
    if not severed:
        # Direct wire — straightforward disconnect.
        if side == "input":
            src_plug = other_plug
            dst_plug = "{}.input[{}]".format(shape, idx)
        else:
            src_plug = "{}.output[{}]".format(shape, idx)
            dst_plug = other_plug
        cmds.warning(
            "disconnect: trying {} -> {}".format(
                src_plug, dst_plug))
        try:
            cmds.disconnectAttr(src_plug, dst_plug)
            severed = True
        except Exception as exc:
            cmds.warning(
                "disconnect: {} -> {} FAILED: {}".format(
                    src_plug, dst_plug, exc))
    # M_REMOVE_MULTI: physically drop the now-empty multi subscript
    # so the array stays packed. b=True forces the removal even if
    # Maya thinks the index still has stale connection bookkeeping
    # (belt-and-suspenders against the unitConversion-delete path
    # leaving partial state). Best-effort: a removeMultiInstance
    # failure logs a warning but does NOT change the return value.
    if severed:
        target_plug = "{}.{}[{}]".format(shape, side, idx)
        try:
            cmds.removeMultiInstance(target_plug, b=True)
            cmds.warning(
                "disconnect: removeMultiInstance({}) cleared the "
                "empty slot".format(target_plug))
        except Exception as exc:
            cmds.warning(
                "disconnect: removeMultiInstance({}) failed: "
                "{}".format(target_plug, exc))
    return severed


def _resolved_pairs_at(shape, side):
    """For Scene-B "clear all wires for this bone": return
    ``[(idx, other_node, other_plug), ...]`` for every occupied
    subscript on ``shape.<side>[]``. ``skipConversionNodes=True``
    so ``other_node`` is the actual driver/driven bone (not the
    intermediate conversion node)."""
    plug = "{}.{}".format(shape, side)
    if side == "input":
        conns = cmds.listConnections(
            plug, source=True, destination=False,
            plugs=True, connections=True,
            skipConversionNodes=True) or []
    else:
        conns = cmds.listConnections(
            plug, source=False, destination=True,
            plugs=True, connections=True,
            skipConversionNodes=True) or []
    out = []
    for k in range(0, len(conns), 2):
        shape_plug = conns[k]
        other_plug = conns[k + 1]
        m = _RBF_SUBSCRIPT_RE.search(shape_plug)
        if m:
            idx = int(m.group(1))
            other_node = other_plug.split(".")[0]
            out.append((idx, other_node, other_plug))
    return out


def _src_already_drives_node(src_plug, target_node):
    """2026-04-28 (M_IDEMPOTENT_CONNECT): True iff ``src_plug`` is
    already connected (in any form) to ANY plug on the RBF target.
    Walks ``cmds.listConnections(src, destination=True, plugs=True)``
    and matches both the transform and shape names so an existing
    wire to ``shape.input[X]`` blocks a fresh wire to
    ``shape.input[Y]`` — same source must NEVER feed two slots."""
    target_shape = get_shape(target_node) or target_node
    conns = cmds.listConnections(
        src_plug, source=False, destination=True, plugs=True) or []
    for dst_plug in conns:
        dst_node = dst_plug.split(".")[0]
        if dst_node == target_node or dst_node == target_shape:
            return True
    return False


def _node_already_drives_dst(target_node, dst_plug):
    """2026-04-28 (M_IDEMPOTENT_CONNECT): True iff ``dst_plug``
    (a driven attribute, e.g. ``boneX.rotateY``) is already driven
    by ANY ``output[i]`` on the RBF target. Symmetric to
    :func:`_src_already_drives_node` for the driven side."""
    target_shape = get_shape(target_node) or target_node
    conns = cmds.listConnections(
        dst_plug, source=True, destination=False, plugs=True) or []
    for src_plug in conns:
        src_node = src_plug.split(".")[0]
        if src_node == target_node or src_node == target_shape:
            return True
    return False


def _flatten_targets(targets):
    """Normalise ``[(node, [attr, ...]), ...]`` → flat list of
    ``"node.attr"`` plug strings, **dropping pairs where the node /
    attr does not actually exist on the scene**. Each rejection is
    logged via cmds.warning so the failure is never silent."""
    plugs = []
    for entry in (targets or []):
        if entry is None:
            continue
        node, attrs = entry
        if not node or not _exists(node):
            cmds.warning(
                "M_BATCH_ROUTING: skipping target with missing "
                "node {!r}".format(node))
            continue
        for a in (attrs or []):
            if not cmds.attributeQuery(a, node=node, exists=True):
                cmds.warning(
                    "M_BATCH_ROUTING: {}.{} does not exist; "
                    "skipping".format(node, a))
                continue
            plugs.append("{}.{}".format(node, a))
    return plugs


@contextlib.contextmanager
def _node_state_frozen(shape):
    """2026-04-28 (M_CRASH_FIX defense 2): freeze the solver node's
    DG compute for the duration of a batch wire/unwire storm.

    Setting ``nodeState`` to 1 (``HasNoEffect``) tells Maya to skip
    ``compute()`` on the node entirely. Without this, every single
    ``cmds.connectAttr`` against ``shape.input[i]`` /
    ``shape.output[i]`` triggers DG dirty propagation, the C++
    ``compute()`` runs with a half-wired ``input[]`` array, and any
    array-bound assertion in the kernel build (M1.4 / M2.1a /
    M2.2 paths) explodes -> CTD.

    Restoration is in ``finally`` so an exception inside the loop
    cannot leave a node permanently disabled. Failure to read or
    restore the prior state surfaces via ``cmds.warning`` rather
    than the silent state corruption it would be otherwise.
    """
    plug = "{}.nodeState".format(shape)
    prev_state = 0
    captured = False
    try:
        prev_state = int(cmds.getAttr(plug))
        captured = True
    except Exception as exc:
        cmds.warning(
            "_node_state_frozen: could not read {} ({}); proceeding "
            "WITHOUT freeze (crash-risk path).".format(plug, exc))
    if captured:
        try:
            cmds.setAttr(plug, 1)   # 1 == HasNoEffect
        except Exception as exc:
            cmds.warning(
                "_node_state_frozen: could not set {}=1 ({}); "
                "proceeding without freeze".format(plug, exc))
            captured = False
    try:
        yield
    finally:
        if captured:
            try:
                cmds.setAttr(plug, prev_state)
            except Exception as exc:
                cmds.warning(
                    "_node_state_frozen: failed to restore {} -> "
                    "{}: {}".format(plug, prev_state, exc))


def connect_routed(node, driver_targets, driven_targets):
    """2026-04-28 (M_BATCH_ROUTING): tab-aware Connect.

    ``driver_targets`` / ``driven_targets`` are lists of
    ``(node_name, [attr, ...])`` produced by main_window's
    :func:`_gather_routed_targets`. Each list is FLATTENED via
    :func:`_flatten_targets` (with per-attr ``attributeQuery``
    existence checks + ``cmds.warning`` on miss) before wiring.

    Wires sequentially:

      driver_plugs[i]  ──→  shape.input[i]
      shape.output[i]  ──→  driven_plugs[i]

    M_CRASH_FIX defense 2 (2026-04-28): the entire connectAttr loop
    runs INSIDE :func:`_node_state_frozen` — the solver's nodeState
    is forced to ``HasNoEffect`` so the half-wired ``input[]`` array
    cannot trigger ``compute()`` mid-construction. Restoration is in
    ``finally``; exceptions cannot leak a permanent freeze.
    """
    shape = get_shape(node)
    if not _exists(shape):
        cmds.warning("connect_routed: solver shape missing for "
                     "{!r}".format(node))
        return

    drv_plugs = _flatten_targets(driver_targets)
    dvn_plugs = _flatten_targets(driven_targets)

    with undo_chunk("RBFtools: connect routed"), \
         _node_state_frozen(shape):
        # M_BREAK_REBUILD (2026-04-28): per-attr per-bone
        # break-then-rebuild. For every (bone, attr) in the
        # blueprint scope:
        #   1. If bone.attr is already wired to shape.input[X],
        #      cmds.warning + disconnect it (frees slot X).
        #   2. Find the lowest-numbered free subscript on
        #      shape.input[].
        #   3. Connect bone.attr -> shape.input[free].
        # The "break" step eliminates cross-click stacking
        # (the same source CANNOT end up driving two slots);
        # the "next free slot" step keeps the wires packed
        # contiguously and matches user blueprint order.
        for src in drv_plugs:
            existing = _subscript_of_existing_input(src, shape)
            if existing is not None:
                cmds.warning(
                    "connect_routed: {} already at {}.input[{}]; "
                    "resetting (root-and-branch).".format(
                        src, shape, existing))
                # M_UNITCONV_PURGE: route the break through
                # _disconnect_or_purge so any unitConversion is
                # deleted, not left dangling.
                _disconnect_or_purge(shape, "input", existing, src)
            occupied = _occupied_input_subscripts(shape)
            free_idx = _next_free_subscript(occupied)
            dst = "{}.input[{}]".format(shape, free_idx)
            try:
                cmds.connectAttr(src, dst, force=True)
            except Exception as exc:
                cmds.warning(
                    "connect_routed: {} → {} failed: {}".format(
                        src, dst, exc))

        for dst in dvn_plugs:
            existing = _subscript_of_existing_output(shape, dst)
            if existing is not None:
                cmds.warning(
                    "connect_routed: {} already driven by "
                    "{}.output[{}]; resetting (root-and-branch)."
                    .format(dst, shape, existing))
                _disconnect_or_purge(shape, "output", existing, dst)
            occupied = _occupied_output_subscripts(shape)
            free_idx = _next_free_subscript(occupied)
            src = "{}.output[{}]".format(shape, free_idx)
            try:
                cmds.connectAttr(src, dst, force=True)
            except Exception as exc:
                cmds.warning(
                    "connect_routed: {} → {} failed: {}".format(
                        src, dst, exc))
    # nodeState restored by the context manager exit. Trigger a
    # SINGLE consolidated re-evaluation outside the freeze window so
    # the solver runs exactly once with the FINAL fully-wired array,
    # not N partial computes during the storm.
    try:
        cmds.setAttr(shape + ".evaluate", 0)
        cmds.setAttr(shape + ".evaluate", 1)
    except Exception as exc:
        cmds.warning(
            "connect_routed: post-freeze evaluate toggle failed: "
            "{}".format(exc))


def _disconnect_bone_specific(shape, bone, attr, side):
    """Scene-A precision disconnect of ``bone.attr`` from
    ``shape.<side>[]``. Returns the count of edges actually broken
    (0 or 1).

    M_UNITCONV_PURGE (2026-04-28): subscript lookup uses
    skipConversionNodes=True so a unitConversion-mediated rotation
    channel is correctly identified; the actual sever runs through
    :func:`_disconnect_or_purge` which DELETES the unitConversion
    node when present (root-and-branch cleanup)."""
    if not _exists(bone):
        cmds.warning(
            "disconnect: bone {!r} missing; skipping".format(bone))
        return 0
    if not cmds.attributeQuery(attr, node=bone, exists=True):
        cmds.warning(
            "disconnect: {}.{} does not exist; skipping".format(
                bone, attr))
        return 0
    bone_plug = "{}.{}".format(bone, attr)
    if side == "input":
        idx = _subscript_of_existing_input(bone_plug, shape)
    else:
        idx = _subscript_of_existing_output(shape, bone_plug)
    if idx is None:
        return 0
    return 1 if _disconnect_or_purge(shape, side, idx, bone_plug) else 0


def _disconnect_bone_all(shape, bone, side):
    """Scene-B: disconnect EVERY wire between ``bone`` and
    ``shape.<side>[]``. Returns the count of edges actually broken.

    M_UNITCONV_PURGE: walks ``_resolved_pairs_at`` (skipConversion
    on) so each (idx, bone, plug) triple identifies the REAL bone
    behind any unitConversion. Each matching idx is severed via
    :func:`_disconnect_or_purge`, deleting orphan unitConversion
    nodes along the way."""
    if not _exists(bone):
        cmds.warning(
            "disconnect: bone {!r} missing; skipping".format(bone))
        return 0
    count = 0
    for idx, other_node, other_plug in _resolved_pairs_at(shape, side):
        if other_node != bone:
            continue
        if _disconnect_or_purge(shape, side, idx, other_plug):
            count += 1
    return count


def disconnect_routed(node, driver_targets, driven_targets):
    """2026-04-28 (M_BREAK_REBUILD): tab-aware Disconnect — Scene
    A / B / C dispatch.

      * Scene A — ``attrs`` is non-empty: precision-disconnect each
        listed (bone, attr) pair from the RBF input/output multi.
      * Scene B — ``attrs`` is empty: clear EVERY wire between this
        bone and the RBF input/output multi (the "select tab, hit
        Disconnect with no attrs highlighted" UX = clear the bone).
      * Scene C — across the entire scope, zero wires are broken:
        return ``{"disconnected_count": 0}`` so main_window can
        surface a confirmDialog informing the user.

    Returns ``{"disconnected_count": int}`` so callers can dispatch
    the Scene-C UI dialog without coupling core to Qt.
    """
    shape = get_shape(node)
    if not _exists(shape):
        cmds.warning(
            "disconnect_routed: solver shape missing for "
            "{!r}".format(node))
        return {"disconnected_count": 0}

    total = 0
    with undo_chunk("RBFtools: disconnect routed"), \
         _node_state_frozen(shape):
        for bone, attrs in (driver_targets or []):
            if not bone:
                continue
            if attrs:
                for attr in attrs:
                    total += _disconnect_bone_specific(
                        shape, bone, attr, "input")
            else:
                total += _disconnect_bone_all(
                    shape, bone, "input")

        for bone, attrs in (driven_targets or []):
            if not bone:
                continue
            if attrs:
                for attr in attrs:
                    total += _disconnect_bone_specific(
                        shape, bone, attr, "output")
            else:
                total += _disconnect_bone_all(
                    shape, bone, "output")

    if total == 0:
        cmds.warning(
            "disconnect_routed: scope produced 0 disconnects "
            "(Scene C — caller should surface a UI hint).")
    return {"disconnected_count": int(total)}


def connect_node(node, driver_node, driven_node,
                 driver_attrs, driven_attrs):
    """Wire driver inputs and driven outputs on the solver node.

    This is the **Connect** button path:

    1. ``driver_node.attr → shape.input[i]``
    2. ``shape.output[i] → driven_node.attr``
    3. Triggers evaluation.

    Call this after :func:`apply_poses` has written the pose data.

    Parameters
    ----------
    node : str
        Transform or shape of the ``RBFtools``.
    driver_node, driven_node : str
        The source and destination scene objects.
    driver_attrs, driven_attrs : list[str]
        Ordered attribute names on driver / driven.
    """
    shape = get_shape(node)
    if not _exists(shape):
        return

    with undo_chunk("RBFtools: connect node"):
        wire_driver_inputs(node, driver_node, driver_attrs)
        wire_driven_outputs(node, driven_node, driven_attrs)
        cmds.setAttr(shape + ".evaluate", 0)
        cmds.setAttr(shape + ".evaluate", 1)


# =====================================================================
#  12. Pose recall — restore a saved pose to the scene
# =====================================================================

def _safe_disconnect_incoming(plug):
    """Disconnect any **incoming** connection to *plug*, return it.

    Returns
    -------
    (str, str) or None
        ``(source_plug, destination_plug)`` that was disconnected,
        or ``None`` if no incoming connection existed.

    Used by :func:`recall_pose` to temporarily break connections,
    set the stored value, then reconnect.

    Connection temporarily broken::

        source_node.attr ─✕→ target_node.attr
                              ↑
                              setAttr(stored_value)
        source_node.attr ──→ target_node.attr   (re-connected)
    """
    conns = cmds.listConnections(
        plug,
        source=True, destination=False,
        plugs=True, connections=True,
        skipConversionNodes=True,
    ) or []
    if len(conns) >= 2:
        dst, src = conns[0], conns[1]
        try:
            cmds.disconnectAttr(src, dst)
        except Exception:
            return None
        return (src, dst)
    return None


def recall_pose(driver_node, driven_node,
                driver_attrs, driven_attrs, pose):
    """Restore driver and driven attributes to a saved pose snapshot.

    For each attribute:

    1. **Disconnect** any incoming connection (so ``setAttr`` succeeds).
    2. **Set** the stored value from :class:`PoseData`.
    3. **Reconnect** the original connection.

    This allows the user to "preview" a recorded pose without
    permanently breaking the rig.

    Parameters
    ----------
    driver_node, driven_node : str
        Scene objects.
    driver_attrs, driven_attrs : list[str]
        Attribute names (must match the pose dimensionality).
    pose : PoseData
        The pose to recall.

    Math note — value injection under live connections
    --------------------------------------------------
    When a plug ``P`` has an incoming connection ``S → P``, Maya ignores
    ``setAttr P`` because the DG overwrites it on the next evaluation.
    We must temporarily sever ``S → P``, set the value, then restore:

    .. math::

        P_{value} = \\text{pose.inputs}[i] \\quad \\text{while } S \\not\\to P

    Then ``S → P`` is restored.  The visible result persists until the
    next DG evaluation propagates ``S`` again.
    """
    if not _exists(driver_node) or not _exists(driven_node):
        return

    with undo_chunk("RBFtools: recall pose {}".format(pose.index)):
        # Driver attributes
        for i, attr in enumerate(driver_attrs):
            if i >= len(pose.inputs):
                break
            plug = "{}.{}".format(driver_node, attr)
            saved = _safe_disconnect_incoming(plug)
            try:
                cmds.setAttr(plug, pose.inputs[i])
            except Exception as exc:
                cmds.warning("recall_pose: setAttr {} failed: {}".format(
                    plug, exc))
            if saved:
                try:
                    cmds.connectAttr(saved[0], saved[1])
                except Exception as exc:
                    cmds.warning("recall_pose: reconnect {} -> {} failed: {}".format(
                        saved[0], saved[1], exc))

        # Driven attributes
        for i, attr in enumerate(driven_attrs):
            if i >= len(pose.values):
                break
            plug = "{}.{}".format(driven_node, attr)
            saved = _safe_disconnect_incoming(plug)
            try:
                cmds.setAttr(plug, pose.values[i])
            except Exception as exc:
                cmds.warning("recall_pose: setAttr {} failed: {}".format(
                    plug, exc))
            if saved:
                try:
                    cmds.connectAttr(saved[0], saved[1])
                except Exception as exc:
                    cmds.warning("recall_pose: reconnect {} -> {} failed: {}".format(
                        saved[0], saved[1], exc))


# =====================================================================
#  13. BlendShape auto-fill vector generation
# =====================================================================

def is_blendshape(node):
    """Return ``True`` if *node* is a ``blendShape`` deformer."""
    return _exists(node) and cmds.nodeType(node) == "blendShape"


def generate_rest_outputs(n_driven):
    """Generate a zero-vector rest pose (all outputs = 0).

    Used as ``pose[0]`` for BlendShape auto-fill.

    Parameters
    ----------
    n_driven : int
        Number of driven attributes.

    Returns
    -------
    list[float]
        ``[0.0, 0.0, ..., 0.0]`` of length *n_driven*.
    """
    return [0.0] * n_driven


def generate_onehot_outputs(n_driven, pose_index, has_rest_pose):
    r"""Generate a one-hot output vector for BlendShape auto-fill.

    When driving a blendShape node, each pose after the rest pose
    activates exactly one target at weight 1.0:

    .. math::

        \mathbf{v}[i] = \begin{cases}
            1.0 & \text{if } i = p - \delta \\
            0.0 & \text{otherwise}
        \end{cases}

    where :math:`p` is the ``pose_index`` and
    :math:`\delta = 1` if a rest pose exists, else 0.

    Parameters
    ----------
    n_driven : int
        Number of driven (blendShape target) attributes.
    pose_index : int
        The pose number being added.
    has_rest_pose : bool
        Whether pose 0 (rest) already exists in the model.

    Returns
    -------
    list[float]
        One-hot vector of length *n_driven*.
    """
    position = pose_index - (1 if has_rest_pose else 0)
    if position < 0 or position >= n_driven:
        cmds.warning("generate_onehot_outputs: position {} out of range "
                     "for {} driven attrs".format(position, n_driven))
    return [1.0 if i == position else 0.0 for i in range(n_driven)]


# =====================================================================
#  14. Spatial matrix utilities  (OpenMaya 2 — precision-critical)
# =====================================================================


def _dag_path(node):
    """Return an ``om2.MDagPath`` for *node*, or ``None`` on failure."""
    import maya.api.OpenMaya as om2
    sel = om2.MSelectionList()
    try:
        sel.add(node)
        return sel.getDagPath(0)
    except Exception:
        return None


def get_world_matrix(node):
    r"""Return the **world-space** transformation matrix of *node*.

    Uses ``MDagPath.inclusiveMatrix()`` which corresponds to the
    ``worldMatrix[0]`` plug but avoids DG evaluation overhead.

    Returns
    -------
    om2.MMatrix
        4x4 row-major transformation matrix.

    Maya convention (row vectors, post-multiply)::

        v' = v * M
    """
    import maya.api.OpenMaya as om2
    dag = _dag_path(node)
    if dag is None:
        return om2.MMatrix()
    return dag.inclusiveMatrix()


def get_local_matrix(node):
    r"""Return the **local-space** (parent-relative) matrix of *node*.

    .. math::

        M_{local} = M_{world} \times M_{parent}^{-1}

    This is the matrix that, when applied to a point in parent space,
    produces the same result as the node's translate / rotate / scale
    channels combined.

    Returns
    -------
    om2.MMatrix

    Notes
    -----
    * For a root-level node (no parent), ``M_{parent} = I`` so
      ``M_{local} = M_{world}``.
    * Uses OpenMaya 2 (``maya.api.OpenMaya``) for double-precision
      arithmetic.  ``cmds.getAttr("node.matrix")`` returns a flat
      tuple that must be manually repacked — ``MDagPath`` is both
      cleaner and faster.
    """
    import maya.api.OpenMaya as om2
    dag = _dag_path(node)
    if dag is None:
        return om2.MMatrix()

    world = dag.inclusiveMatrix()

    # Parent world matrix = exclusiveMatrix (everything *above* this node)
    parent_world = dag.exclusiveMatrix()

    # M_local = M_world * M_parent^{-1}
    return world * parent_world.inverse()


# M2.3: identity local-Transform fallback. Used for blendShape driven
# nodes (no local Transform concept) and as the safe default when the
# Apply-time replay is skipped entirely. Layout matches the C++
# poseLocalTransform compound: t(3) + q(4, q_w >= 0 canonical) + s(3).
IDENTITY_LOCAL_TRANSFORM = {
    "translate": (0.0, 0.0, 0.0),
    "quat":      (0.0, 0.0, 0.0, 1.0),
    "scale":     (1.0, 1.0, 1.0),
}


def decompose_matrix_quat(matrix):
    r"""Decompose an ``MMatrix`` into ``translate / quat / scale``.

    Returns
    -------
    dict
        ``{"translate": (tx, ty, tz),
           "quat":      (qx, qy, qz, qw),   # q_w >= 0 canonical
           "scale":     (sx, sy, sz)}``

    Differs from :func:`decompose_matrix` in two ways:

    * Rotation is returned as a **unit quaternion**, not Euler angles.
      This is rotateOrder-independent by construction — the caller
      does NOT need to know the driven_node's rotateOrder (v5 addendum
      §M2.3 A).
    * The quaternion is canonicalised to the ``q_w >= 0`` hemisphere,
      matching the sign convention used by M2.1b (SwingTwist encoding)
      and M2.2 (QWA output).

    Shear handling: ``MTransformationMatrix.scale()`` returns only the
    3-D scale component; any shear in the input matrix is **silently
    dropped**. M2.3 explicitly does not represent shear (v5 addendum
    §M2.3 T7). Rigs that depend on driven-node shear should bake it
    before Apply.
    """
    import maya.api.OpenMaya as om2
    xform = om2.MTransformationMatrix(matrix)
    t = xform.translation(om2.MSpace.kTransform)
    q = xform.rotation(asQuaternion=True)
    s = xform.scale(om2.MSpace.kTransform)
    qx, qy, qz, qw = q.x, q.y, q.z, q.w
    if qw < 0.0:
        qx, qy, qz, qw = -qx, -qy, -qz, -qw
    return {
        "translate": (t.x, t.y, t.z),
        "quat":      (qx, qy, qz, qw),
        "scale":     (s[0], s[1], s[2]),
    }


def decompose_matrix(matrix):
    r"""Decompose an ``MMatrix`` into translate / rotate / scale.

    Uses ``MTransformationMatrix`` for numerically stable extraction.

    Returns
    -------
    dict
        ``{"translate": (tx, ty, tz),
           "rotate":    (rx, ry, rz),   # radians, XYZ order
           "scale":     (sx, sy, sz)}``

    Math — the decomposition factors ``M`` as:

    .. math::

        M = S \times R \times T

    where *S* is a diagonal scale matrix, *R* is an orthogonal
    rotation matrix, and *T* is a translation matrix.
    Rotation is extracted as Euler angles in XYZ order (radians).
    """
    import maya.api.OpenMaya as om2
    xform = om2.MTransformationMatrix(matrix)
    t = xform.translation(om2.MSpace.kTransform)
    r = xform.rotation(asQuaternion=False)   # MEulerRotation
    s = xform.scale(om2.MSpace.kTransform)
    return {
        "translate": (t.x, t.y, t.z),
        "rotate":    (r.x, r.y, r.z),
        "scale":     (s[0], s[1], s[2]),
    }
