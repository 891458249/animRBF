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

import maya.cmds as cmds

from RBFtools.constants import (
    PLUGIN_NAME,
    NODE_TYPE,
    FILTER_DEFAULTS,
    FILTER_VAR_TEMPLATE,
    SCALE_ATTR_NAMES,
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

def read_driver_info(node):
    """Discover which node and attributes drive the *input[]* array.

    Traces connections into ``<shape>.input[i]`` and extracts the
    upstream node name plus each connected attribute.

    Parameters
    ----------
    node : str
        Transform or shape of a ``RBFtools`` node.

    Returns
    -------
    (str, list[str])
        ``(driver_node_name, [attr_1, attr_2, ...])``.
        Returns ``("", [])`` if nothing is connected.

    Connection topology::

        driver.translateX  →  RBFtoolsShape.input[0]
        driver.translateY  →  RBFtoolsShape.input[1]
        driver.translateZ  →  RBFtoolsShape.input[2]
    """
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
    # ``conns`` is a flat list: [dest_plug, src_plug, dest_plug, src_plug, ...]
    for i in range(0, len(conns), 2):
        src_plug = conns[i + 1]                # e.g. "pSphere1.translateX"
        parts = src_plug.split(".")
        if not driver:
            driver = parts[0]
        if len(parts) > 1:
            attrs.append(parts[1])

    return driver, attrs


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
    """
    ensure_plugin()
    with undo_chunk("RBFtools: create node"):
        sel = cmds.ls(selection=True) or []
        shape = cmds.createNode(NODE_TYPE)
        transform = get_transform(shape)
        transform = cmds.rename(transform, "RBFnode#")
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

    Design note
    -----------
    This is a **transport object** — it carries data between core
    functions and the UI layer.  It is intentionally not a ``dict``
    so that misspelled keys become immediate ``AttributeError`` s
    rather than silent ``KeyError`` / ``None`` bugs.
    """

    __slots__ = ("index", "inputs", "values")

    def __init__(self, index, inputs, values):
        self.index  = int(index)
        self.inputs = list(inputs)
        self.values = list(values)

    def __repr__(self):
        return "PoseData(index={}, inputs={}, values={})".format(
            self.index, self.inputs, self.values)

    def __eq__(self, other):
        """Tolerance-based equality (see :func:`float_eq`)."""
        if not isinstance(other, PoseData):
            return NotImplemented
        return (self.index == other.index
                and vector_eq(self.inputs, other.inputs)
                and vector_eq(self.values, other.values))

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
        poses.append(PoseData(0, [0.0] * n_inputs, [0.0] * n_outputs))

    for pid in pose_indices:
        inputs = [
            safe_get("{}.poses[{}].poseInput[{}]".format(shape, pid, i), 0.0)
            for i in range(n_inputs)
        ]
        values = [
            safe_get("{}.poses[{}].poseValue[{}]".format(shape, pid, i), 0.0)
            for i in range(n_outputs)
        ]
        poses.append(PoseData(pid, inputs, values))

    return poses


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

        # 3 — capture + write per-output baselines. pose[0] is the
        # preferred source when it is a rest row (all driver inputs 0);
        # otherwise the current scene value is used. Scale channels
        # always anchor at 1.0. See v5 addendum 2026-04-24 §M1.2.
        baselines = capture_output_baselines(
            driven_node, driven_attrs, poses=poses)
        write_output_baselines(node, baselines)

        # 4 — trigger evaluation cycle
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
