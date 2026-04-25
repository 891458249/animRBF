# -*- coding: utf-8 -*-
"""Auto-alias generation for RBFtools shape input[]/output[] multi plugs
(Milestone 3.7).

Lives in its own module because:
  * core.py is already 2200+ lines (M3.2 made it heavier)
  * alias logic is logically distinct from DG ops and JSON I/O
  * M3.3 (JSON Import/Export) is the next consumer and benefits from
    a small focused module.

============================================================
M3.7 DRIVEN/DRIVER NODE WRITE-BOUNDARY CONTRACT (addendum §M3.7)
============================================================

Auto-alias generation invokes ``cmds.aliasAttr`` on the **RBFtools shape**
itself (``input[i]`` / ``output[i]`` are plugs on the shape, not on the
driver / driven scene nodes). The shape is owned end-to-end by RBFtools,
so writing aliases there is fully internal.

What is touched:
  - <shape>.input[i]   for i in range(len(driver_attrs))
  - <shape>.output[k]  for k in range(len(driven_attrs))

What is NOT touched (NEVER):
  - any attribute on the driver_node or driven_node themselves
  - any attribute on third-party scene nodes
  - any user-managed alias on the shape (E.1 protection — see
    :func:`is_rbftools_managed_alias`)

Compare with M3.2 mirror tool's "never modify source node" contract.
M3.7 is the first M3.x sub-task that performs an aliasAttr write on a
node that already had pre-existing aliases (potentially user-set);
hence the explicit boundary contract above and the precise managed-
alias detector below.

============================================================
M3.3 FORWARD-COMPAT API CONTRACT
============================================================
The following symbols are stable and consumed by M3.3 (JSON
Import/Export):

  * :func:`generate_alias_name(attr_name, idx, role,
                               is_quat_group_leader=False)`
  * :func:`read_aliases(shape)` — reverse lookup
  * :data:`MANAGED_PREFIX_INPUT`  / :data:`MANAGED_PREFIX_OUTPUT`
  * Alias schema: ``{role}_<sanitised>``, plus quat-group leader
    spawns the four sibling names ``<base>QX/QY/QZ/QW`` (no role
    prefix on quat siblings — they live alongside ``out_*`` aliases
    and are still detected by :func:`is_rbftools_managed_alias`).

Signature stability is required: M3.3 imports these directly.
Any future evolution must add new APIs alongside, never break these.
"""

from __future__ import absolute_import

import re

import maya.cmds as cmds


# === Public constants (M3.3 forward-compat contract) ===

MANAGED_PREFIX_INPUT  = "in_"
MANAGED_PREFIX_OUTPUT = "out_"

# Quat-group sibling suffix set. A quat-group leader generates four
# aliases: <base>QX, <base>QY, <base>QZ, <base>QW. The base is the
# sanitised driven-attr name of the LEADER index only; siblings k+1..k+3
# do NOT independently sanitise their attr names.
QUAT_SUFFIXES = ("QX", "QY", "QZ", "QW")

# Maximum alias length (Maya silently truncates above ~64; we leave a
# small margin for the 4-suffix variants and the optional _<idx> tail).
_MAX_ALIAS_LEN = 56

# Identifier-safe regex.
_IDENTIFIER_RE = re.compile(r"[^A-Za-z0-9_]")


# =====================================================================
#  1. Pure helpers — sanitisation + name generation (M3.3 stable)
# =====================================================================

def _sanitize(name):
    """Map an arbitrary Maya attr name to a valid alias identifier.

    Steps:
      1. Replace any non ``[A-Za-z0-9_]`` with ``_``.
      2. If empty after sanitisation, return ``"x"`` placeholder.
      3. If first char is a digit, prefix ``a_``.
      4. Truncate to ``_MAX_ALIAS_LEN`` keeping a 12-char tail when
         truncation happens (preserves attr suffix specificity).
    """
    if not name:
        return "x"
    s = _IDENTIFIER_RE.sub("_", name)
    if not s:
        return "x"
    if s[0].isdigit():
        s = "a_" + s
    if len(s) > _MAX_ALIAS_LEN:
        head = s[: _MAX_ALIAS_LEN - 13]
        tail = s[-12:]
        s = head + "_" + tail
    return s


def generate_alias_name(attr_name, idx, role, is_quat_group_leader=False):
    """Build the canonical alias name for one ``input[idx]`` /
    ``output[idx]`` plug.

    Parameters
    ----------
    attr_name : str
        Source attribute on the driver / driven scene node, e.g.
        ``"translateX"`` or ``"shoulderL_blend"``.
    idx : int
        Multi-instance index.
    role : str
        ``"input"`` (driver) or ``"output"`` (driven).
    is_quat_group_leader : bool, optional
        When True, the returned name is the **base** for the four quat
        siblings — caller appends ``QX/QY/QZ/QW``. Only meaningful for
        ``role == "output"``.

    Returns
    -------
    str
        For non-quat: ``"in_<x>"`` / ``"out_<x>"`` (role prefix lower).
        For quat leader: ``"<x>"`` (caller appends suffix to form the
        four sibling names).
    """
    base = _sanitize(attr_name)
    if is_quat_group_leader and role == "output":
        # Quat siblings do NOT carry the role prefix to keep names short
        # and preserve the standard <base>QX/QY/QZ/QW convention shared
        # with the rest of the rigging community.
        return base
    if role == "input":
        return MANAGED_PREFIX_INPUT + base
    if role == "output":
        return MANAGED_PREFIX_OUTPUT + base
    raise ValueError("generate_alias_name: invalid role {!r}".format(role))


def quat_group_alias_names(leader_attr_name):
    """Return the 4 sibling alias names for a quat-group leader.

    Used by both ``apply_aliases`` and the managed-alias detector.
    """
    base = _sanitize(leader_attr_name)
    return tuple(base + suffix for suffix in QUAT_SUFFIXES)


def is_rbftools_managed_alias(name):
    """Return True iff *name* looks like an RBFtools-generated alias.

    Detection rules (must stay STRICT to avoid clobbering user aliases):
      1. Starts with ``"in_"`` or ``"out_"``  → managed.
      2. Ends with one of ``QX/QY/QZ/QW`` AND has a non-empty base       (quat-group sibling) → managed.
      3. Otherwise → NOT managed (user alias / external).

    Rule 2 is intentionally narrow: a user attr literally named e.g.
    ``"someThingQX"`` and aliased manually would also match. This is
    the documented trade-off (addendum §M3.7) — RBFtools owns the
    ``<base>QX/QY/QZ/QW`` quartet convention; users who alias their
    own ``QX``-suffixed names accept the collision risk. The Tools
    menu "Force regenerate aliases" entry behind a confirm dialog is
    the escape hatch.
    """
    if not name:
        return False
    if name.startswith(MANAGED_PREFIX_INPUT) and len(name) > len(MANAGED_PREFIX_INPUT):
        return True
    if name.startswith(MANAGED_PREFIX_OUTPUT) and len(name) > len(MANAGED_PREFIX_OUTPUT):
        return True
    if len(name) > 2 and name[-2:] in QUAT_SUFFIXES:
        # Sibling pattern: <non-empty-base><QX|QY|QZ|QW>.
        return True
    return False


# =====================================================================
#  2. Maya-touching helpers (apply / clear / read)
# =====================================================================

def _query_existing_aliases(shape):
    """Return ``[(alias, real_plug_short), ...]`` for the shape.

    Maya's ``cmds.aliasAttr(node, query=True)`` returns a flat
    ``[alias1, real1, alias2, real2, ...]`` list (or ``None``). We
    pair them up and keep only the short attr name (no node prefix)
    for ``real_plug_short``.
    """
    flat = cmds.aliasAttr(shape, query=True) or []
    pairs = []
    for i in range(0, len(flat) - 1, 2):
        pairs.append((flat[i], flat[i + 1]))
    return pairs


def clear_managed_aliases(shape):
    """Remove every alias on *shape* that :func:`is_rbftools_managed_alias`
    classifies as managed. User-set aliases are preserved (E.1).

    Failures on individual aliases are logged via ``cmds.warning`` and
    do not halt the loop — partial cleanup is preferable to crashing
    in the middle of an Apply.
    """
    if not shape:
        return
    pairs = _query_existing_aliases(shape)
    for alias, _real in pairs:
        if not is_rbftools_managed_alias(alias):
            continue
        try:
            cmds.aliasAttr("{}.{}".format(shape, alias), remove=True)
        except Exception as exc:
            cmds.warning(
                "core_alias: failed to clear stale alias {!r}: {}".format(
                    alias, exc))


def _set_one_alias(shape, alias, plug_path, used_names):
    """Apply a single alias with conflict-aware fallback (C.3.a / c).

    Strategy:
      1. If *alias* not in *used_names* and not already on the shape,
         set it directly.
      2. Else suffix ``_<idx>`` (idx parsed off plug_path tail) for a
         best-effort second attempt.
      3. Re-raise as warning + skip on continued failure (no
         kFailure — addendum §M3 red line).

    *used_names* is mutated in place to track the names we've written
    in this batch so two indices producing the same sanitised base
    don't collide silently.
    """
    candidate = alias
    if candidate in used_names:
        # Append the multi-index from plug_path's "[N]" tail when present.
        m = re.search(r"\[(\d+)\]$", plug_path)
        suffix = "_" + m.group(1) if m else "_dup"
        candidate = alias + suffix
    try:
        cmds.aliasAttr(candidate, plug_path)
        used_names.add(candidate)
        return candidate
    except Exception as exc:
        cmds.warning(
            "core_alias: failed to set alias {!r} on {}: {}".format(
                candidate, plug_path, exc))
        return None


def apply_aliases(shape, driver_attrs, driven_attrs,
                  quat_group_starts=None, force=False):
    """Apply aliases to *shape*'s ``input[]`` / ``output[]`` plugs.

    Parameters
    ----------
    shape : str
        RBFtools shape node.
    driver_attrs : list[str]
        Driver attribute names — ordered same as ``input[]`` indices.
    driven_attrs : list[str]
        Driven attribute names — ordered same as ``output[]`` indices.
    quat_group_starts : list[int] or None, optional
        Output indices that are quat-group leaders (M2.2). For each
        leader k, outputs k..k+3 receive aliases
        ``<base>QX/QY/QZ/QW`` instead of the per-output ``out_<x>``.
    force : bool, optional
        When True, clears ALL aliases on the shape (managed AND
        user-set) before regenerating. Default False — only managed
        aliases are cleared (E.1 protection).

    Returns
    -------
    dict
        ``{"input": {idx: alias, ...}, "output": {idx: alias, ...}}``
        — the names actually written, after conflict-fallback. Entries
        absent on failure.
    """
    if not shape:
        return {"input": {}, "output": {}}

    if force:
        # Wipe everything (still skip non-aliases — `existing` only has
        # alias entries by construction).
        for alias, _real in _query_existing_aliases(shape):
            try:
                cmds.aliasAttr("{}.{}".format(shape, alias), remove=True)
            except Exception as exc:
                cmds.warning(
                    "core_alias: force clear failed on {!r}: {}".format(
                        alias, exc))
    else:
        clear_managed_aliases(shape)

    # Track names already used (managed + remaining user aliases) so the
    # conflict resolver can step around all of them.
    used_names = {a for a, _ in _query_existing_aliases(shape)}
    result = {"input": {}, "output": {}}

    # ----- Inputs (driver attrs → in_<x>) -----
    for i, attr in enumerate(driver_attrs):
        alias = generate_alias_name(attr, i, role="input")
        plug = "{}.input[{}]".format(shape, i)
        applied = _set_one_alias(shape, alias, plug, used_names)
        if applied is not None:
            result["input"][i] = applied

    # ----- Outputs (driven attrs → out_<x> + quat siblings) -----
    quat_starts = set(quat_group_starts or [])
    # Pre-compute which output indices are quat *siblings* (not leaders)
    # so they receive the leader-derived QX/QY/QZ/QW name.
    sibling_of = {}
    for s in quat_starts:
        leader_attr = (driven_attrs[s] if 0 <= s < len(driven_attrs)
                       else "quat{}".format(s))
        sib_names = quat_group_alias_names(leader_attr)
        for offset in range(4):
            tgt = s + offset
            if tgt < len(driven_attrs):
                sibling_of[tgt] = sib_names[offset]

    for k, attr in enumerate(driven_attrs):
        if k in sibling_of:
            alias = sibling_of[k]
        else:
            alias = generate_alias_name(attr, k, role="output")
        plug = "{}.output[{}]".format(shape, k)
        applied = _set_one_alias(shape, alias, plug, used_names)
        if applied is not None:
            result["output"][k] = applied

    return result


def read_aliases(shape):
    """Return ``{"input": {idx: alias}, "output": {idx: alias}}`` —
    the inverse of :func:`apply_aliases`. Used by M3.3 export.

    Only entries whose *real plug* ends with ``input[N]`` /
    ``output[N]`` are reported; foreign aliases (e.g. user-set on
    other shape attrs) are ignored. Both managed and user-set aliases
    on input/output plugs ARE included — exporters should not assume
    everything they see is RBFtools-generated.
    """
    out = {"input": {}, "output": {}}
    if not shape:
        return out
    for alias, real in _query_existing_aliases(shape):
        m = re.search(r"\.?(input|output)\[(\d+)\]$", real)
        if not m:
            # `real` may be the bare attr name "input[0]" without node
            # prefix, depending on Maya version.
            m = re.match(r"(input|output)\[(\d+)\]$", real)
        if not m:
            continue
        role = m.group(1)
        idx = int(m.group(2))
        out[role][idx] = alias
    return out
