# -*- coding: utf-8 -*-
"""JSON I/O utilities for v5 RBFtools schema (Milestone 3.0).

Lives in its own module because:
  * core.py is already 1860+ lines (M2.3 made it heavy)
  * I/O serialization is logically distinct from node DG ops
  * M3.3 will extend this file with export_solver_to_json /
    import_solver_from_json (~200+ lines), which would push core.py
    past 2000 lines if appended there

============================================================
SCHEMA_VERSION IMMUTABILITY CONTRACT (v5 addendum §M3.0)
============================================================
The string ``SCHEMA_VERSION`` defined below is a permanent invariant.
Changing it BREAKS downstream engine integration's compatibility
gate — engine-side runtime components use this string to decide
whether they can consume an exported JSON.

Any future schema evolution MUST:

  1. Introduce a NEW version string (e.g. "rbftools.v5.m3.1" or
     "rbftools.v6") — never modify the existing string while
     leaving field semantics drifting underneath it.
  2. Extend the reader to support BOTH the old and new versions
     (multi-version dispatcher in read_json_with_schema_check).
  3. Document the change in a new addendum sub-section
     ``§M3.x-extension-YYYYMMDD``.

Three-layer guard (addendum §M3.0):
  - This source comment   (you are reading layer 1)
  - The contract paragraph in addendum §M3.0
  - The permanent test ``test_schema_version_unchanged_M3_0``
    in tests/test_m3_0_infrastructure.py
"""

from __future__ import absolute_import

import json
import os
import tempfile


# === Schema version (addendum §M3.0 + §M_B24a2 — bump protocol) ===
# Changing this string breaks downstream engine integration's
# compatibility gate. Any schema evolution MUST introduce a new
# version string AND extend LEGACY_SCHEMA_VERSIONS atomically in
# the SAME commit, with PERMANENT guard updates (T6 / T_M3_3_SCHEMA_FIELDS
# / T_FLOAT_ROUND_TRIP) flipped to dual-version form. See addendum
# §M_B24a2 PROJECT-CONSTITUTIONAL-EVENT for the precedent.
SCHEMA_VERSION = "rbftools.v5.m_per_pose_sigma"

# M_B24a2 — versions older than SCHEMA_VERSION that this loader can
# upgrade in-memory. PERMANENT inclusion: removing entries here would
# orphan legacy fixtures (T_VERSIONED_SCHEMA_PRESENT #26.b).
LEGACY_SCHEMA_VERSIONS = frozenset({
    "rbftools.v5.m3",
    "rbftools.v5.m_b24",  # Commit 1: per-pose σ + base pose are
                          # additive; legacy m_b24 dicts (no
                          # base_pose_values, no per-pose radius)
                          # round-trip via key-defaults.
})


class SchemaVersionError(Exception):
    """Raised by :func:`read_json_with_schema_check` when the file's
    ``schema_version`` field does not equal :data:`SCHEMA_VERSION`.

    M3.3 will extend the reader with multi-version dispatch; for M3.0
    the contract is strict equality.
    """


def atomic_write_json(path, data):
    """Write *data* to *path* atomically.

    Strategy: stage to a temp file in the **same directory**, then
    ``os.replace`` to the final path. This eliminates partial-write
    visibility (a crash mid-write leaves either the old file or the
    new file, never a half-written one) — important for engine-side
    consumers that poll the file or react to filesystem watchers.

    Same-directory staging is required because ``os.replace`` is
    atomic only within a single filesystem; a cross-mount tempdir
    would degrade to copy + unlink with a brief partial state.

    Parameters
    ----------
    path : str
        Final destination filesystem path.
    data : Any (JSON-serialisable)
        Object passed to :func:`json.dump`. Must include a
        ``"schema_version"`` field set to :data:`SCHEMA_VERSION` if
        it is meant to be readable by :func:`read_json_with_schema_check`.
    """
    dir_name = os.path.dirname(os.path.abspath(path)) or "."
    fd, tmp = tempfile.mkstemp(prefix=".rbftools_", suffix=".json.tmp",
                                dir=dir_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2,
                      sort_keys=False)
        os.replace(tmp, path)
    except Exception:
        # Best-effort cleanup of the staged temp file.
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def read_json_with_schema_check(path):
    """Read JSON from *path* and verify ``schema_version`` matches.

    Parameters
    ----------
    path : str
        Filesystem path to a JSON document previously written by
        :func:`atomic_write_json`.

    Returns
    -------
    dict
        The parsed JSON document.

    Raises
    ------
    SchemaVersionError
        If the file's ``schema_version`` field is missing or differs
        from :data:`SCHEMA_VERSION`. M3.3 may extend this with multi-
        version dispatch; for M3.0 strict equality is the contract.
    """
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    got = data.get("schema_version") if isinstance(data, dict) else None
    if got == SCHEMA_VERSION:
        return data
    if got in LEGACY_SCHEMA_VERSIONS:
        # M_B24a2 versioned dispatch — in-memory upgrade.
        return _upgrade_legacy_dict(data)
    raise SchemaVersionError(
        "Schema mismatch: expected {!r} (or LEGACY {}), got {!r}".format(
            SCHEMA_VERSION, sorted(LEGACY_SCHEMA_VERSIONS), got))


# =====================================================================
#  Milestone 3.3 — Import / Export
# =====================================================================
#
# All M3.3 logic lives below. Keep the M3.0 surface above untouched.
#
# Decisions (addendum §M3.3):
#   A.1 nodes:[] array at the top level (single-node = length 1)
#   B.1 full settings export (no "non-default only" trimming)
#   C.1 abort + detailed error when scene nodes / attrs are missing
#   D.2 Add (default) + Replace (confirm-gated, action_id=import_replace)
#   E.2 two-phase dry-run + execute
#   F.3 strict + collect-all errors (no fail-fast on first)
#   G.2 import writes poseLocalTransform directly — bypasses M2.3
#       capture path. THIS IS THE ONLY LEGAL BYPASS (addendum §M3.3.G).
#   H.2 import does NOT setAttr aliases — M3.7 auto_alias_outputs
#       runs at the end and is the single source of truth.
#   I.2 output_quaternion_groups[].alias_base is NOT stored — caller
#       reverses it from driven.attrs[start].alias on demand.
#   J.2 meta block exists but is READ-ONLY (T_META_READ_ONLY guard).
#   K.3 core_json holds the heavy lifting; controller only wires.
#
# Permanent guards (DO NOT REMOVE):
#   T1a — _ATTR_NAME_TO_JSON_KEY completeness vs EXPECTED_SETTINGS_KEYS
#   T1b — _ATTR_NAME_TO_JSON_KEY bijection (no duplicate JSON values)
#   T6  — schema_version unchanged ("rbftools.v5.m3")
#   T16 — meta block is read-only (source-scan dict_to_node + dry_run)
#   T_M3_3_SCHEMA_FIELDS — node_to_dict key set frozen
#   T_FLOAT_ROUND_TRIP — dump(load(dump(d))) byte-stable

import maya.cmds as cmds

# Hoisted module-level imports so test-time mock.patch can target
# ``RBFtools.core_json.core`` / ``.core_alias`` without exercising
# the lazy-inside-function pattern. No circular risk: neither core.py
# nor core_alias.py imports core_json at load time.
from RBFtools import core, core_alias


class SchemaValidationError(Exception):
    """Raised by :func:`dry_run` and :func:`import_path` when the
    JSON document fails per-node validation. Carries a list of
    human-readable error strings; consumers should display them all
    rather than only the first (F.3 contract)."""

    def __init__(self, errors):
        self.errors = list(errors)
        super(SchemaValidationError, self).__init__(
            "Schema validation failed ({} error{}):\n  {}".format(
                len(self.errors),
                "" if len(self.errors) == 1 else "s",
                "\n  ".join(self.errors)))


# Maya scalar attr name (camelCase) <-> JSON key (snake_case) bijection.
# Locked by SCHEMA_VERSION; see addendum §M3.3.1.
_ATTR_NAME_TO_JSON_KEY = {
    # General
    "active":               "active",
    "iconSize":             "icon_size",
    # Vector Angle
    "direction":            "direction",
    "invert":               "invert",
    "useRotate":            "use_rotate",
    "angle":                "angle",
    "centerAngle":          "center_angle",
    "twist":                "twist",
    "twistAngle":           "twist_angle",
    "useTranslate":         "use_translate",
    "grow":                 "grow",
    "translateMin":         "translate_min",
    "translateMax":         "translate_max",
    "interpolation":        "interpolation",
    "drawCone":             "draw_cone",
    "drawCenterCone":       "draw_center_cone",
    "drawWeight":           "draw_weight",
    # RBF
    "kernel":               "kernel",
    "radiusType":           "radius_type",
    "radius":               "radius",
    "allowNegativeWeights": "allow_negative_weights",
    "scale":                "scale",
    "rbfMode":              "rbf_mode",
    "distanceType":         "distance_type",
    "twistAxis":            "twist_axis",
    # Solver display
    "drawOrigin":           "draw_origin",
    "drawPoses":            "draw_poses",
    "poseLength":           "pose_length",
    "drawIndices":          "draw_indices",
    "indexDistance":        "index_distance",
    "drawTwist":            "draw_twist",
    "opposite":             "opposite",
    "driverIndex":          "driver_index",
    # M1.4 — solver
    "regularization":       "regularization",
    "solverMethod":         "solver_method",
    # M2.1a — input encoding
    "inputEncoding":        "input_encoding",
    # M1.3 — clamp
    "clampEnabled":         "clamp_enabled",
    "clampInflation":       "clamp_inflation",
}

# Reverse map (rebuilt at module load — bijection guarded by T1b).
_JSON_KEY_TO_ATTR_NAME = {v: k for k, v in _ATTR_NAME_TO_JSON_KEY.items()}

# Frozen key set for permanent guard T_M3_3_SCHEMA_FIELDS.
# M_B24a2-2: drivers (plural list, M_B24 multi-source) replaces driver
# (singular) and output_encoding is added at the node-dict top level.
EXPECTED_NODE_DICT_KEYS = frozenset({
    "name", "type_mode", "settings",
    "drivers",                    # was "driver" pre-M_B24
    "driven",
    "output_quaternion_groups",
    "output_encoding",            # NEW M_B24a2-2 (node-level enum 0..2)
    "poses",
    "base_pose_values",           # NEW Commit 1 (M_BASE_POSE) per-output baseline
})

# M_B24a2-2: PERMANENT — keys for legacy v5.0-pre-M_B24 schema.
# Used by _upgrade_legacy_dict + permanent guards. DO NOT shrink:
# removal would orphan legacy fixtures.
LEGACY_NODE_DICT_KEYS_M3 = frozenset({
    "name", "type_mode", "settings",
    "driver", "driven",
    "output_quaternion_groups",
    "poses",
})
EXPECTED_SETTINGS_KEYS = frozenset(_ATTR_NAME_TO_JSON_KEY.values())

# Top-level mode strings for type_mode (J/enum decision: integer at
# the wire level, string label is metadata only).
_TYPE_MODE_INT = {"VectorAngle": 0, "RBF": 1}
_TYPE_MODE_LABEL = {0: "VectorAngle", 1: "RBF"}


# =====================================================================
#  Export — node_to_dict + dump entrypoints
# =====================================================================

def _upgrade_legacy_node(ndata):
    """In-memory upgrade of a single legacy v5.0-pre-M_B24 node dict
    to the new M_B24 shape. One-way (加固 5): the result NEVER carries
    legacy keys. Unknown / unrecognized fields are preserved verbatim
    so a caller adding meta data is not silently stripped, but the
    well-known legacy keys are translated.

    Translation:
      driver: {node, attrs, rotate_orders}     ->
        drivers: [{node, attrs, rotate_orders, weight: 1.0, encoding: 0}]
      (no output_encoding in legacy)           ->
        output_encoding: 0  (Euler default; matches C++ M_B24a1 default)
    """
    if not isinstance(ndata, dict):
        return ndata
    # Already new shape — pass-through.
    if "drivers" in ndata and "output_encoding" in ndata:
        return ndata
    out = dict(ndata)  # shallow copy; nested dicts/lists are shared
    legacy_driver = out.pop("driver", None)
    if legacy_driver is None:
        legacy_driver = {"node": "", "attrs": [], "rotate_orders": []}
    legacy_driver = dict(legacy_driver)
    legacy_driver["weight"] = 1.0
    legacy_driver["encoding"] = 0
    out["drivers"] = [legacy_driver]
    out.setdefault("output_encoding", 0)
    return out


def _upgrade_legacy_dict(data):
    """In-memory upgrade of a top-level v5.0-pre-M_B24 document dict
    to the M_B24 shape. Idempotent: if data is already new, returns
    a shallow copy with schema_version forced to current. One-way
    only (加固 5): callers that dump the result MUST write the new
    SCHEMA_VERSION; there is no inverse transform.

    Drops _comment field at the top level (fixture-only metadata,
    not part of the runtime schema; 加固 5).
    """
    if not isinstance(data, dict):
        return data
    out = dict(data)
    out.pop("_comment", None)         # fixture-only metadata
    out["schema_version"] = SCHEMA_VERSION
    nodes = out.get("nodes")
    if isinstance(nodes, list):
        out["nodes"] = [_upgrade_legacy_node(n) for n in nodes]
    return out


def node_to_dict(node):
    """Read a fully-loaded RBFtools node into a JSON-ready dict.

    Pure-ish: only Maya read calls (no DG mutation). Output keys are
    locked by ``EXPECTED_NODE_DICT_KEYS`` / ``EXPECTED_SETTINGS_KEYS``
    — adding/removing keys requires a SCHEMA_VERSION bump.
    """

    shape = core.get_shape(node)
    if not core._exists(shape):
        raise SchemaValidationError(
            ["node_to_dict: shape not found for {!r}".format(node)])

    type_int = int(core.safe_get(shape + ".type", 0))
    type_mode = _TYPE_MODE_LABEL.get(type_int, "Unknown")

    # ---- settings (flat scalar block, ordered to match
    # EXPECTED_SETTINGS_KEYS for byte-stable export) ----
    settings = {}
    for maya_attr, json_key in _ATTR_NAME_TO_JSON_KEY.items():
        settings[json_key] = core.safe_get(
            "{}.{}".format(shape, maya_attr),
            _attr_default(maya_attr))

    # ---- driver / driven wiring + per-attr alias ----
    driver_node, driver_attrs = core.read_driver_info(node)
    driven_node, driven_attrs = core.read_driven_info(node)
    aliases = core_alias.read_aliases(shape)

    # Driver rotate orders (multi int).
    rotate_orders = core.read_driver_rotate_orders(node)

    # Driven baselines + isScale (parallel arrays from M1.2 helpers).
    baselines = core.read_output_baselines(node)
    # baselines is list[(base_value, is_scale)] aligned to output[k] idx.

    # M_B24a2-2: drivers[] list (single-element until M_B24b UI exposes
    # multi-source editing). The legacy single-driver shape is the
    # element at index 0; weight/encoding are M_B24a1 schema defaults.
    driver_block_legacy = {
        "node": driver_node or "",
        "attrs": [
            {"index": i, "name": name,
             "alias": aliases["input"].get(i)}
            for i, name in enumerate(driver_attrs)
        ],
        "rotate_orders": list(rotate_orders),
        "weight": 1.0,
        "encoding": 0,
    }
    drivers_block = [driver_block_legacy]

    driven_block = {
        "node": driven_node or "",
        "attrs": [
            {"index": i, "name": name,
             "alias": aliases["output"].get(i),
             "is_scale": bool(baselines[i][1]) if i < len(baselines) else False,
             "base_value": (float(baselines[i][0]) if i < len(baselines)
                            else (1.0 if core_alias and False else 0.0))}
            for i, name in enumerate(driven_attrs)
        ],
    }

    # ---- output_quaternion_groups[] (M2.2 multi int) ----
    quat_starts = core.read_quat_group_starts(node)
    quat_groups = [{"start": int(s)} for s in quat_starts]

    # ---- poses + per-pose local transform ----
    poses = core.read_all_poses(node)
    local_xforms = core.read_pose_local_transforms(node)

    pose_dicts = []
    for i, pose in enumerate(poses):
        lx = (local_xforms[i] if i < len(local_xforms)
              else core.IDENTITY_LOCAL_TRANSFORM)
        pose_dicts.append({
            "index": int(pose.index),
            "inputs": [float(x) for x in pose.inputs],
            "values": [float(x) for x in pose.values],
            # Commit 1 (M_PER_POSE_SIGMA): JSON forward-compat field.
            # Older import paths that don't know "radius" silently drop
            # it; PoseData defaults to DEFAULT_POSE_RADIUS on read so
            # round-trip through old exporter is loss-tolerant.
            "radius": float(getattr(pose, "radius",
                                    core.DEFAULT_POSE_RADIUS)),
            "local_transform": {
                "translate": [float(x) for x in lx["translate"]],
                "quat":      [float(x) for x in lx["quat"]],
                "scale":     [float(x) for x in lx["scale"]],
            },
        })

    # M_B24a2-2: read node-level outputEncoding (M_B24a1 schema field)
    output_encoding = int(core.safe_get(shape + ".outputEncoding", 0))

    # Commit 1 (M_BASE_POSE): export the per-output additive baseline
    # vector. Empty list when the user has not configured one (legacy
    # nodes); importer defaults the same way.
    base_pose_values = core.read_base_pose_values(node)

    return {
        "name": str(node),
        "type_mode": type_mode,
        "settings": settings,
        "drivers": drivers_block,
        "driven": driven_block,
        "output_quaternion_groups": quat_groups,
        "output_encoding": output_encoding,
        "poses": pose_dicts,
        "base_pose_values": base_pose_values,
    }


def _attr_default(maya_attr):
    """Return the export-time default for *maya_attr* — used only as
    fall-back when ``safe_get`` cannot read the plug. Mirrors the
    defaults in :func:`core.get_all_settings`."""
    bool_attrs = {"active", "invert", "useRotate", "twist",
                  "useTranslate", "grow", "drawCone", "drawCenterCone",
                  "drawWeight", "drawOrigin", "drawPoses", "drawIndices",
                  "drawTwist", "opposite", "allowNegativeWeights",
                  "clampEnabled"}
    if maya_attr in bool_attrs:
        return True if maya_attr in ("active", "useRotate",
                                     "allowNegativeWeights",
                                     "drawCone", "clampEnabled") else False
    if maya_attr in ("iconSize", "scale", "poseLength"):
        return 1.0
    if maya_attr == "angle":
        return 45.0
    if maya_attr == "twistAngle":
        return 90.0
    if maya_attr == "kernel":
        return 1
    if maya_attr == "regularization":
        return 1e-08
    if maya_attr == "clampInflation":
        return 0.0
    return 0


def export_nodes_to_path(node_names, path, meta=None):
    """Bake *node_names* (list of transform names) into a single JSON
    file at *path* using :func:`atomic_write_json`.

    *meta* is an optional dict written verbatim under the top-level
    ``"meta"`` key. The writer does not validate or branch on meta —
    it is read-only metadata (J.2 + addendum §M3.3.J).
    """
    payload = {
        "schema_version": SCHEMA_VERSION,
        "nodes": [node_to_dict(n) for n in node_names],
    }
    if meta is not None:
        payload["meta"] = dict(meta)
    atomic_write_json(path, payload)


# =====================================================================
#  Validation — dry_run (read-only)
# =====================================================================

class PerNodeReport(object):
    """One row of the dry-run report shown to the user before execute.

    Attributes
    ----------
    name : str
        Target node name from JSON (may collide with existing scene).
    ok : bool
        True iff this node can be imported safely.
    errors : list[str]
        Human-readable error strings (empty when ok).
    warnings : list[str]
        Non-fatal advisories (e.g. "node will be created with suffix").
    will_overwrite : bool
        True when an existing same-name RBFtools shape will be removed.
    """

    __slots__ = ("name", "ok", "errors", "warnings", "will_overwrite",
                 "data")

    def __init__(self, name, data):
        self.name = name
        self.data = data
        self.ok = True
        self.errors = []
        self.warnings = []
        self.will_overwrite = False

    def fail(self, msg):
        self.errors.append(msg)
        self.ok = False

    def warn(self, msg):
        self.warnings.append(msg)


def dry_run(data, mode="add"):
    """Validate a parsed JSON document without touching the scene.

    DOES NOT read ``data["meta"]`` for any decision (T16 contract).

    Returns
    -------
    list[PerNodeReport]
        One per nodes[] entry, in document order.

    Raises
    ------
    SchemaValidationError
        Top-level schema_version / nodes[] structure violations
        (collected; never fail-fast on the first one).
    """
    fatal = []
    if not isinstance(data, dict):
        fatal.append("top-level: expected JSON object, got {}".format(
            type(data).__name__))
    else:
        sv = data.get("schema_version")
        if sv != SCHEMA_VERSION and sv not in LEGACY_SCHEMA_VERSIONS:
            fatal.append(
                "schema_version: expected {!r} (or LEGACY {}), "
                "got {!r}".format(
                    SCHEMA_VERSION, sorted(LEGACY_SCHEMA_VERSIONS), sv))
        if "nodes" not in data:
            fatal.append("top-level: required field 'nodes' missing")
        elif not isinstance(data["nodes"], list):
            fatal.append("top-level: 'nodes' must be a list")
    if fatal:
        raise SchemaValidationError(fatal)

    reports = []
    for i, ndata in enumerate(data["nodes"]):
        rpt = PerNodeReport(
            name=ndata.get("name", "<nodes[{}]>".format(i)),
            data=ndata)
        _validate_node_dict(ndata, rpt, mode=mode, idx=i)
        reports.append(rpt)
    return reports


def _validate_node_dict(ndata, rpt, mode, idx):
    """Per-node validation — collects errors into *rpt* (F.3).

    DOES NOT read ``data["meta"]`` (T16 contract).
    """
    prefix = "nodes[{}]".format(idx)

    # ---- shape check ----
    if not isinstance(ndata, dict):
        rpt.fail(prefix + ": expected object")
        return
    # M_B24a2-2: defensive upgrade. dry_run is also called by user code
    # paths that may pass a still-legacy ndata; idempotent on new dicts.
    if "driver" in ndata and "drivers" not in ndata:
        upgraded = _upgrade_legacy_node(ndata)
        ndata.clear()
        ndata.update(upgraded)
        rpt.data = ndata     # keep PerNodeReport in sync
    for required in ("name", "type_mode", "settings",
                     "drivers", "driven",
                     "output_quaternion_groups", "poses"):
        if required not in ndata:
            rpt.fail(prefix + ": required field {!r} missing".format(
                required))
    if not rpt.ok:
        return

    # ---- name + mode ----
    name = ndata["name"]
    if not isinstance(name, str) or not name:
        rpt.fail(prefix + ".name: must be non-empty string")
    if ndata["type_mode"] not in _TYPE_MODE_INT:
        rpt.fail(prefix + ".type_mode: expected one of {}, got {!r}".format(
            sorted(_TYPE_MODE_INT.keys()), ndata["type_mode"]))

    # ---- existing-node clash (Add vs Replace) ----
    if core._exists(name):
        if mode == "replace":
            rpt.will_overwrite = True
        elif mode == "add":
            rpt.warn("name {!r} already exists; will be created with "
                     "_imported suffix".format(name))
        else:
            rpt.fail("unknown import mode {!r}".format(mode))

    # ---- driver / driven scene presence ----
    # M_B24a2-2: pull first driver from new "drivers" list. Backend
    # validation stays single-driver until M_B24b multi-source UI;
    # extra entries (if any) get a sanity check below.
    drivers_list = ndata.get("drivers", []) or []
    drv = drivers_list[0] if drivers_list else {}
    drvn_ = ndata.get("driven", {})
    drv_node = drv.get("node", "")
    drvn_node = drvn_.get("node", "")
    if not drv_node:
        rpt.fail(prefix + ".driver.node: missing")
    elif not core._exists(drv_node):
        rpt.fail(prefix + ".driver.node {!r} not found in scene".format(
            drv_node))
    if not drvn_node:
        rpt.fail(prefix + ".driven.node: missing")
    elif not core._exists(drvn_node):
        rpt.fail(prefix + ".driven.node {!r} not found in scene".format(
            drvn_node))

    # ---- attr-array shape + sparse-index consistency (red line #5) ----
    drv_attrs = drv.get("attrs", [])
    drvn_attrs = drvn_.get("attrs", [])
    _validate_attr_array(drv_attrs, prefix + ".driver.attrs",
                         drv_node, rpt)
    _validate_attr_array(drvn_attrs, prefix + ".driven.attrs",
                         drvn_node, rpt)

    # ---- settings keys frozen ----
    s = ndata.get("settings", {})
    if not isinstance(s, dict):
        rpt.fail(prefix + ".settings: expected object")
    else:
        unknown = set(s.keys()) - EXPECTED_SETTINGS_KEYS
        # _label-suffix keys are meta-only (red line #4); strip them
        # before flagging unknowns.
        unknown = {k for k in unknown if not k.endswith("_label")}
        if unknown:
            rpt.fail(prefix + ".settings: unknown key(s) {}".format(
                sorted(unknown)))
        missing = EXPECTED_SETTINGS_KEYS - set(s.keys())
        if missing:
            rpt.fail(prefix + ".settings: required key(s) missing: "
                     "{}".format(sorted(missing)))

    # ---- pose dimension consistency ----
    n_in = len(drv_attrs)
    n_out = len(drvn_attrs)
    for j, p in enumerate(ndata.get("poses", [])):
        if not isinstance(p, dict):
            rpt.fail(prefix + ".poses[{}]: expected object".format(j))
            continue
        ins = p.get("inputs", [])
        outs = p.get("values", [])
        if len(ins) != n_in:
            rpt.fail(prefix + ".poses[{}].inputs: expected {} items, "
                     "got {}".format(j, n_in, len(ins)))
        if len(outs) != n_out:
            rpt.fail(prefix + ".poses[{}].values: expected {} items, "
                     "got {}".format(j, n_out, len(outs)))
        lx = p.get("local_transform", {})
        if not isinstance(lx, dict) or \
           len(lx.get("translate", [])) != 3 or \
           len(lx.get("quat", [])) != 4 or \
           len(lx.get("scale", [])) != 3:
            rpt.fail(prefix + ".poses[{}].local_transform: shape "
                     "must be {{translate[3], quat[4], scale[3]}}".format(j))


def _validate_attr_array(arr, prefix, scene_node, rpt):
    """Validate sparse-multi-aware attr array (red line #5).

    Each entry must have explicit 'index' field; array order must
    match index ordering (no skipping required for sparse — but the
    array slot's index field MUST match the array position when seen
    densely). For sparse exports we still enumerate by array order
    but trust 'index' as authoritative.
    """
    if not isinstance(arr, list):
        rpt.fail(prefix + ": expected list")
        return
    seen = set()
    for j, entry in enumerate(arr):
        if not isinstance(entry, dict):
            rpt.fail("{}[{}]: expected object".format(prefix, j))
            continue
        for required in ("index", "name"):
            if required not in entry:
                rpt.fail("{}[{}]: required field {!r} missing".format(
                    prefix, j, required))
        if not isinstance(entry.get("index", None), int):
            rpt.fail("{}[{}].index: expected int".format(prefix, j))
            continue
        idx = entry["index"]
        if idx in seen:
            rpt.fail("{}[{}].index: duplicate {}".format(prefix, j, idx))
        seen.add(idx)
        # Scene-side attr existence check.
        nm = entry.get("name", "")
        if scene_node and core._exists(scene_node) and nm:
            if not _scene_attr_exists(scene_node, nm):
                rpt.fail("{}[{}]: attr {!r} not found on {}".format(
                    prefix, j, nm, scene_node))


def _scene_attr_exists(node, attr):
    try:
        return bool(cmds.attributeQuery(attr, node=node, exists=True))
    except Exception:
        return False


# =====================================================================
#  Import — dict_to_node + import_path
# =====================================================================

def import_path(path, mode="add"):
    """Two-phase import (E.2): dry-run all nodes first, then execute
    only those marked ok. Returns a dict
    ``{"reports": [...], "created": [str, ...], "failed": [str, ...]}``.

    Caller is expected to invoke :func:`dry_run` first and present the
    reports to the user (path A confirm) — :func:`import_path` re-runs
    dry_run defensively but does NOT itself prompt; the controller
    layer owns user interaction.

    DOES NOT read ``data["meta"]`` for any behavioural decision
    (T16 contract).
    """
    data = read_json_with_schema_check(path)
    reports = dry_run(data, mode=mode)
    created = []
    failed = []
    for rpt in reports:
        if not rpt.ok:
            failed.append(rpt.name)
            continue
        try:
            target = dict_to_node(rpt.data, mode=mode,
                                  will_overwrite=rpt.will_overwrite)
            created.append(target)
        except Exception as exc:
            cmds.warning("import_path: node {!r} failed: {}".format(
                rpt.name, exc))
            failed.append(rpt.name)
    return {"reports": reports, "created": created, "failed": failed}


def dict_to_node(ndata, mode="add", will_overwrite=False):
    """Materialise one node-dict into the scene.

    M_B24a2-2: defensive in-memory upgrade for legacy ndata. When
    callers pass a still-legacy node dict (driver singular, no
    output_encoding) it is transparently upgraded via
    :func:`_upgrade_legacy_node`. The upgrade is one-way (加固 5):
    once normalized, the result will be written/read as the M_B24
    schema only.

    META FIELD CONTRACT (addendum §M3.3.J):
      The 'meta' block is metadata only. This function MUST NOT read
      meta.* for any behavioural decision. Removing or modifying meta
      has no effect on the imported node. If you find yourself reading
      meta.exporter_version etc to branch logic, STOP — that is a
      SCHEMA_VERSION bump, not a meta hack.

    M2.3 BYPASS (addendum §M3.3.G):
      Import writes poseLocalTransform directly via
      ``core.write_pose_local_transforms`` and does NOT call
      ``capture_per_pose_local_transforms``. This is the ONLY legal
      bypass of the M2.3 auto-capture path — see addendum.
    """

    # M_B24a2-2 defensive upgrade — idempotent on new-shape input.
    if isinstance(ndata, dict) and "driver" in ndata and "drivers" not in ndata:
        ndata = _upgrade_legacy_node(ndata)

    name = ndata["name"]
    target = name
    if mode == "replace" and will_overwrite and core._exists(name):
        core.delete_node(name)
    elif mode == "add" and core._exists(name):
        target = name + "_imported"

    with core.undo_chunk("RBFtools: import node"):
        core.ensure_plugin()
        actual = core.create_node()
        if cmds.objExists(actual) and actual != target:
            try:
                actual = cmds.rename(actual, target)
            except Exception:
                pass
        target = actual

        # type_mode (top-level)
        type_int = _TYPE_MODE_INT.get(ndata["type_mode"], 1)
        core.set_node_attr(target, "type", type_int)

        # ---- scalar settings ----
        for json_key, value in (ndata.get("settings") or {}).items():
            if json_key.endswith("_label"):
                continue  # label fields are meta-only (red line #4)
            attr = _JSON_KEY_TO_ATTR_NAME.get(json_key)
            if attr is None:
                continue  # silently drop — validator already complained
            try:
                core.set_node_attr(target, attr, value)
            except Exception as exc:
                cmds.warning(
                    "dict_to_node: settings.{} -> {}.{} failed: {}".format(
                        json_key, target, attr, exc))

        # ---- driver / driven wiring ----
        # M_B24a2-2: drivers[] (plural). Take element 0 for the single-
        # driver wiring path; M_B24b will iterate all elements with the
        # multi-source UI / connectAttr flow.
        drivers_list = ndata.get("drivers", []) or []
        drv = drivers_list[0] if drivers_list else {}
        drvn = ndata.get("driven", {})
        drv_attrs = [a["name"] for a in drv.get("attrs", [])]
        drvn_attrs = [a["name"] for a in drvn.get("attrs", [])]
        if drv.get("node") and drv_attrs:
            core.wire_driver_inputs(target, drv["node"], drv_attrs)
        if drvn.get("node") and drvn_attrs:
            core.wire_driven_outputs(target, drvn["node"], drvn_attrs)

        # ---- driver rotate orders + quat group starts ----
        rotate_orders = drv.get("rotate_orders") or []
        if rotate_orders:
            core.write_driver_rotate_orders(target, rotate_orders)
        quat_starts = [g["start"]
                       for g in (ndata.get("output_quaternion_groups")
                                 or [])]
        if quat_starts:
            core.write_quat_group_starts(target, quat_starts)

        # ---- poses (G.2 — clear + write directly, no auto-capture) ----
        core.clear_node_data(target)
        shape = core.get_shape(target)
        for pose in ndata.get("poses", []):
            # Commit 1 (M_PER_POSE_SIGMA): legacy JSON (no "radius" key)
            # falls back to DEFAULT_POSE_RADIUS via PoseData ctor.
            core._write_pose_to_node(
                shape, int(pose["index"]),
                core.PoseData(int(pose["index"]),
                              list(pose["inputs"]),
                              list(pose["values"]),
                              radius=pose.get("radius")))

        # Commit 1 (M_BASE_POSE): restore per-output additive baseline.
        # Missing key (legacy JSON) leaves the plug untouched, which
        # the plugin treats as zero-baseline (bit-identical to v5-pre-
        # M_BASE_POSE).
        bpv = ndata.get("base_pose_values")
        if bpv:
            core.write_base_pose_values(target, bpv)

        # baselines (M1.2): pull base_value + is_scale per driven attr.
        baselines = []
        for entry in drvn.get("attrs", []):
            baselines.append((float(entry.get("base_value", 0.0)),
                              bool(entry.get("is_scale", False))))
        core.write_output_baselines(target, baselines)

        # poseLocalTransform direct-write (G.2 bypass).
        local_xforms = []
        for pose in ndata.get("poses", []):
            lx = pose.get("local_transform", {})
            local_xforms.append({
                "translate": tuple(lx.get("translate", (0.0, 0.0, 0.0))),
                "quat":      tuple(lx.get("quat", (0.0, 0.0, 0.0, 1.0))),
                "scale":     tuple(lx.get("scale", (1.0, 1.0, 1.0))),
            })
        if local_xforms:
            core.write_pose_local_transforms(target, local_xforms)

        # ---- alias regeneration via M3.7 (H.2 — single source) ----
        try:
            core.auto_alias_outputs(target, drv_attrs, drvn_attrs,
                                    force=False)
        except Exception as exc:
            cmds.warning(
                "dict_to_node: auto_alias_outputs failed: {} "
                "(continuing — aliases are advisory)".format(exc))

    return target
