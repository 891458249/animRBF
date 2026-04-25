# -*- coding: utf-8 -*-
"""Mirror math + naming-rule helpers for the Mirror Tool (M3.2).

Lives in its own module to keep `core.py` lean and to expose pure-
function APIs that are testable without Maya. Everything here is a
**pure function** of inputs — no Maya calls, no side effects.

The high-level orchestrator that wires these into actual node
creation lives in ``core.py:mirror_node`` (which uses ``cmds`` and
``undo_chunk``); this module is the math + naming kernel.

Mirror axes:
  * 0 — YZ plane (flip X)   ← default for character rigs
  * 1 — XZ plane (flip Y)
  * 2 — XY plane (flip Z)

See addendum §M3.2 for full LaTeX derivations of the quaternion
flip rule and the Maya raw-attr mirror table.
"""

from __future__ import absolute_import

import re


# ----------------------------------------------------------------------
# Mirror axis enum
# ----------------------------------------------------------------------

AXIS_X = 0   # YZ plane
AXIS_Y = 1   # XZ plane
AXIS_Z = 2   # XY plane

AXIS_LABELS = ["YZ plane (flip X)", "XZ plane (flip Y)", "XY plane (flip Z)"]


# ----------------------------------------------------------------------
# Translate / Quaternion / ExpMap / SwingTwist (vector primitives)
# ----------------------------------------------------------------------


def mirror_translate(t, axis):
    """Mirror a 3-D translation across a coordinate plane.

    YZ plane (axis=X) flips x; XZ flips y; XY flips z.
    """
    tx, ty, tz = t
    if axis == AXIS_X:
        return (-tx, ty, tz)
    if axis == AXIS_Y:
        return (tx, -ty, tz)
    return (tx, ty, -tz)


def mirror_quaternion(q, axis):
    """Mirror a unit quaternion (qx, qy, qz, qw) across a coord plane.

    Derivation (addendum §M3.2.2): for reflection across plane
    perpendicular to *axis*, R' = M R M^{-1}; in quat form this
    flips the two non-axis xyz components and keeps the axis-aligned
    component + qw. Returns (q'_x, q'_y, q'_z, q'_w).
    """
    qx, qy, qz, qw = q
    if axis == AXIS_X:
        return (qx, -qy, -qz, qw)
    if axis == AXIS_Y:
        return (-qx, qy, -qz, qw)
    return (-qx, -qy, qz, qw)


def mirror_expmap(l, axis):
    """Mirror a log-quaternion ∈ ℝ³.

    Same sign rules as the xyz components of :func:`mirror_quaternion`
    (because log is an odd function of the rotation and the rotation
    itself flips its non-axis xyz parts).
    """
    lx, ly, lz = l
    if axis == AXIS_X:
        return (lx, -ly, -lz)
    if axis == AXIS_Y:
        return (-lx, ly, -lz)
    return (-lx, -ly, lz)


def mirror_swingtwist(st, axis):
    """Mirror a SwingTwist 5-tuple (sx, sy, sz, sw, twist).

    Swing portion uses the quaternion mirror; twist scalar is negated
    (rotation direction reverses about the mirrored twist axis).
    """
    sx, sy, sz, sw, twist = st
    msx, msy, msz, msw = mirror_quaternion((sx, sy, sz, sw), axis)
    return (msx, msy, msz, msw, -twist)


# ----------------------------------------------------------------------
# Raw transform-attr mirror table (Maya behavioural convention)
# ----------------------------------------------------------------------

# Behavioural mirror per axis: the SET below names attrs whose value
# gets sign-flipped when mirrored across the perpendicular plane.
# Rotates that LIE IN the mirror plane (i.e., perpendicular axes)
# flip; the rotate ALONG the mirror axis itself does NOT flip.
# Translates flip ONLY along the mirror axis. Scales never flip.
_FLIP_BY_AXIS = {
    AXIS_X: frozenset({"tx", "translatex", "ry", "rotatey", "rz", "rotatez"}),
    AXIS_Y: frozenset({"ty", "translatey", "rx", "rotatex", "rz", "rotatez"}),
    AXIS_Z: frozenset({"tz", "translatez", "rx", "rotatex", "ry", "rotatey"}),
}

_RECOGNIZED_ATTRS = frozenset({
    "tx", "ty", "tz", "translatex", "translatey", "translatez",
    "rx", "ry", "rz", "rotatex", "rotatey", "rotatez",
    "sx", "sy", "sz", "scalex", "scaley", "scalez",
})


def mirror_raw_attr_value(attr_name, value, axis):
    """Mirror a single Maya transform-attr value.

    Returns
    -------
    (mirrored_value : float, recognized : bool)
        ``recognized`` is False when *attr_name* is not a known Maya
        transform attr — caller may emit a once-per-rig warning so
        the user knows the value was passed through unchanged.
    """
    leaf = attr_name.lower().split(".")[-1]
    if leaf in _FLIP_BY_AXIS.get(axis, set()):
        return -value, True
    if leaf in _RECOGNIZED_ATTRS:
        return value, True
    return value, False


# ----------------------------------------------------------------------
# Naming-rule presets
# ----------------------------------------------------------------------

# Each preset = (forward_pattern, forward_replacement,
#                reverse_pattern, reverse_replacement, i18n_label_key)
# Pattern syntax is `re` regex; matching is case-sensitive (the user
# can switch to Custom for case-insensitive needs).
NAMING_PRESETS = [
    (r"^L_",     "R_",     r"^R_",     "L_",     "naming_rule_l_r"),
    (r"_L$",     "_R",     r"_R$",     "_L",     "naming_rule_xl_xr"),
    (r"^Left_",  "Right_", r"^Right_", "Left_",  "naming_rule_left_right"),
    (r"_l$",     "_r",     r"_r$",     "_l",     "naming_rule_xl_lc"),
    (r"_lf$",    "_rt",    r"_rt$",    "_lf",    "naming_rule_lf_rt"),
    (r"^lf_",    "rt_",    r"^rt_",    "lf_",    "naming_rule_lflf"),
]
# Custom rule lives at index == len(NAMING_PRESETS).
CUSTOM_RULE_INDEX = len(NAMING_PRESETS)


def apply_naming_rule(name, rule_index, custom=None, direction="auto"):
    """Apply a naming rule to *name* and return ``(new_name, status)``.

    Parameters
    ----------
    name : str
        Source name (e.g. ``"L_arm_jnt"``).
    rule_index : int
        Index into :data:`NAMING_PRESETS`, or :data:`CUSTOM_RULE_INDEX`
        for user-supplied custom pattern.
    custom : tuple[str, str] or None
        ``(pattern, replacement)`` regex pair, used only when
        ``rule_index == CUSTOM_RULE_INDEX``.
    direction : str
        ``"auto"`` (detect by which pattern matches), ``"forward"``,
        or ``"reverse"``.

    Returns
    -------
    (new_name : str, status : str)
        ``status`` ∈ {``"ok"``, ``"both_match"``, ``"unchanged"``,
        ``"no_match"``}. Caller (UI) translates the status to user
        feedback per addendum §M3.2 naming-rule edge contract.
    """
    if rule_index == CUSTOM_RULE_INDEX:
        if not custom:
            return name, "no_match"
        pattern, replacement = custom
        try:
            new_name = re.sub(pattern, replacement, name)
        except re.error:
            return name, "no_match"
        if new_name == name:
            return name, "unchanged"
        return new_name, "ok"

    if rule_index < 0 or rule_index >= len(NAMING_PRESETS):
        return name, "no_match"

    fp, fr, rp, rr, _label = NAMING_PRESETS[rule_index]
    fwd_match = bool(re.search(fp, name))
    rev_match = bool(re.search(rp, name))

    if direction == "forward":
        if not fwd_match:
            return name, "no_match"
        new_name = re.sub(fp, fr, name)
        return (name, "unchanged") if new_name == name else (new_name, "ok")

    if direction == "reverse":
        if not rev_match:
            return name, "no_match"
        new_name = re.sub(rp, rr, name)
        return (name, "unchanged") if new_name == name else (new_name, "ok")

    # auto
    if fwd_match and rev_match:
        # Both directions match — default to forward, flag warning.
        new_name = re.sub(fp, fr, name)
        if new_name == name:
            return name, "unchanged"
        return new_name, "both_match"
    if fwd_match:
        new_name = re.sub(fp, fr, name)
        return (name, "unchanged") if new_name == name else (new_name, "ok")
    if rev_match:
        new_name = re.sub(rp, rr, name)
        return (name, "unchanged") if new_name == name else (new_name, "ok")
    return name, "no_match"


# ----------------------------------------------------------------------
# Per-pose mirror dispatch (driver inputs + driven values)
# ----------------------------------------------------------------------

# inputEncoding values (mirror M2.1a constants — duplicated here so
# core_mirror stays a leaf module with no upward import).
_ENC_RAW         = 0
_ENC_QUATERNION  = 1
_ENC_BENDROLL    = 2
_ENC_EXPMAP      = 3
_ENC_SWINGTWIST  = 4


def mirror_driver_inputs(inputs, encoding, axis, driver_attrs=None):
    """Mirror a flat list of driver-input values.

    Parameters
    ----------
    inputs : list[float]
        Raw driver-input values (one per ``input[i]`` slot).
    encoding : int
        v5 inputEncoding enum (0..4).
    axis : int
        Mirror axis (0/1/2).
    driver_attrs : list[str] or None
        Required for Raw encoding — used to identify per-slot semantic.
        Ignored for non-Raw encodings.

    Returns
    -------
    (mirrored : list[float], status : dict)
        ``status`` carries a ``"unsupported_encoding"`` flag when
        BendRoll fall-back triggers (caller emits warning) and an
        ``"unrecognized_attrs"`` list when Raw encounters unknown
        attr names.
    """
    n = len(inputs)
    status = {"unsupported_encoding": False, "unrecognized_attrs": []}

    if encoding == _ENC_RAW:
        out = list(inputs)
        if driver_attrs:
            for i in range(min(n, len(driver_attrs))):
                v, ok = mirror_raw_attr_value(driver_attrs[i],
                                              float(inputs[i]), axis)
                out[i] = v
                if not ok:
                    status["unrecognized_attrs"].append(driver_attrs[i])
        return out, status

    if encoding == _ENC_QUATERNION:
        if n % 4 == 0 and n > 0:
            out = []
            for g in range(n // 4):
                q = (inputs[g*4+0], inputs[g*4+1],
                     inputs[g*4+2], inputs[g*4+3])
                out.extend(mirror_quaternion(q, axis))
            return out, status
        return list(inputs), status   # defensive

    if encoding == _ENC_EXPMAP:
        if n % 3 == 0 and n > 0:
            out = []
            for g in range(n // 3):
                l = (inputs[g*3+0], inputs[g*3+1], inputs[g*3+2])
                out.extend(mirror_expmap(l, axis))
            return out, status
        return list(inputs), status

    if encoding == _ENC_SWINGTWIST:
        if n % 5 == 0 and n > 0:
            out = []
            for g in range(n // 5):
                st = (inputs[g*5+0], inputs[g*5+1], inputs[g*5+2],
                      inputs[g*5+3], inputs[g*5+4])
                out.extend(mirror_swingtwist(st, axis))
            return out, status
        return list(inputs), status

    if encoding == _ENC_BENDROLL:
        # Stereographic projection is non-linear — mirroring requires
        # decoding to swing/twist, mirroring, re-encoding. Out of M3.2
        # scope per addendum §M3.2 (E)①. Pass-through with flag.
        status["unsupported_encoding"] = True
        return list(inputs), status

    return list(inputs), status   # unknown encoding — defensive


def mirror_driven_values(values, driven_attrs, axis):
    """Mirror driven-side output values per Maya raw-attr conventions.

    driven_attrs is required because we identify per-slot semantic
    by attribute name (no "encoding" concept on the output side).
    Returns (mirrored : list[float], unrecognized : list[str]).
    """
    out = list(values)
    unrecognized = []
    if not driven_attrs:
        return out, unrecognized
    for i in range(min(len(values), len(driven_attrs))):
        v, ok = mirror_raw_attr_value(driven_attrs[i],
                                      float(values[i]), axis)
        out[i] = v
        if not ok:
            unrecognized.append(driven_attrs[i])
    return out, unrecognized


def mirror_pose_local_transform(local_xform, axis):
    """Mirror an M2.3 ``poseLocalTransform`` snapshot dict.

    Input dict has keys ``"translate"`` (3-tuple), ``"quat"`` (4-tuple),
    ``"scale"`` (3-tuple). Translate and quat mirror per primitives
    above; scale is unchanged (Maya behavioural mirror keeps positive
    scale).
    """
    t = local_xform.get("translate", (0.0, 0.0, 0.0))
    q = local_xform.get("quat",      (0.0, 0.0, 0.0, 1.0))
    s = local_xform.get("scale",     (1.0, 1.0, 1.0))
    return {
        "translate": mirror_translate(t, axis),
        "quat":      mirror_quaternion(q, axis),
        "scale":     tuple(s),
    }
