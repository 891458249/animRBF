# -*- coding: utf-8 -*-
"""Pose Profiler — read-only diagnostic + split suggestion (Milestone 3.5).

============================================================
Verify-before-design findings (addendum §M3.5)
============================================================

  F1 — ``lastSolveMethod`` is a C++ instance member of the
       ``RBFtools`` shape (source/RBFtools.cpp:137), NOT a Maya
       attribute. Python cannot read which solver was actually
       used on the last evaluation. The profile report shows the
       configured ``solverMethod`` (Auto / ForceGE) with an
       explicit caveat — see :func:`format_report`. Honouring
       the M3 "0 C++ changes" red line is absolute; we do not
       expose this field by adding a new MObject just for
       diagnostics.

  F2 — Milestone 1.4 has no machine-calibrated benchmark data.
       Solve-time estimates therefore use CONCEPTUAL constants
       (``_K_CHOL`` / ``_K_GE`` / ``_K_QWA``) sized for a modern
       x64 CPU. The report shows estimates with a HIGHLY VISIBLE
       caveat (T_CAVEAT_VISIBLE permanent guard). Users tune the
       constants in this module to fit their hardware. M5 will
       replace these with real benchmarks, keeping the symbol
       names as a forward-compat interface.

  F3 — :class:`CollapsibleFrame` API is sufficient; ToolsSection
       is a thin lazy subclass.

  F4 — :func:`core_prune.analyse_node` is read-only and returns
       all the health-check counts the profiler needs. We REUSE
       it rather than re-implement the scans (T_REUSE_PRUNE).

============================================================
Read-only contract (addendum §M3.5)
============================================================

:func:`profile_node` is read-only — body must NOT contain any
``cmds.*`` mutation call or ``undo_chunk`` wrapper.
T_PROFILE_READ_ONLY (PERMANENT GUARD) source-scans for the
forbidden symbols.
"""

from __future__ import absolute_import

import maya.cmds as cmds

from RBFtools import core, core_prune


# =====================================================================
#  Concept-grade timing constants (F2 — tune for your hardware)
# =====================================================================
#
# These are deliberately CONCEPTUAL. They scale with the cube of the
# kernel-matrix side for Cholesky / GE and per-iteration for QWA,
# sized to land in the right order of magnitude on a modern x64 CPU
# (one double FLOP ~1 ns). Replace with real benchmark fits in M5.
#
# Symbol names are part of the M5 forward-compat interface.

_K_CHOL = 1e-9   # sec / cell^3   Cholesky O(N^3 / 3)
_K_GE   = 3e-9   # sec / cell^3   GE      O(N^3) ≈ 3x Cholesky
_K_QWA  = 1e-7   # sec / iteration on a 4x4 SPD power-iteration


# Split-suggestion thresholds (D.3 decision).
_THRESH_N_POSES   = 80
_THRESH_CELLS     = 500
_THRESH_CHOL_MS   = 5.0


# =====================================================================
#  Pure helpers
# =====================================================================


def _estimate_memory(n_poses, n_inputs, n_outputs):
    """Approximate per-node memory footprint in bytes.

    Pure function — no Maya cmds. Pose-data is dense
    ``n_poses * n_inputs * 8``; weight matrix is
    ``n_poses * n_outputs * 8``; working memory is the Cholesky
    workspace ``n_poses^2 * 8``.
    """
    pose_bytes = n_poses * n_inputs * 8
    weight_bytes = n_poses * n_outputs * 8
    work_bytes = n_poses * n_poses * 8
    total = pose_bytes + weight_bytes + work_bytes
    return {
        "pose_data": pose_bytes,
        "weight_matrix": weight_bytes,
        "working_memory": work_bytes,
        "total": total,
    }


def _estimate_solve_times(n_poses, has_quat_groups):
    """Approximate per-evaluation solve times in seconds.

    Pure function. Uses the conceptual constants documented at
    the top of this module (F2). Returns ``None`` for
    ``qwa_iter`` when the node has no quat groups.
    """
    n3 = n_poses ** 3
    return {
        "cholesky_sec": _K_CHOL * n3,
        "ge_sec":       _K_GE   * n3,
        "qwa_iter_sec": (_K_QWA if has_quat_groups else None),
    }


def _format_bytes(n):
    if n < 1024:
        return "{} B".format(n)
    if n < 1024 * 1024:
        return "~{:.1f} KB".format(n / 1024.0)
    return "~{:.2f} MB".format(n / (1024.0 * 1024))


def _format_ms(secs):
    if secs is None:
        return "—"
    ms = secs * 1000.0
    if ms < 0.01:
        return "<0.01 ms"
    return "~{:.2f} ms".format(ms)


# =====================================================================
#  profile_node — read-only data gathering
# =====================================================================


def profile_node(node):
    """Read-only diagnostic snapshot of *node*.

    Returns a flat dict consumed by :func:`format_report` (and by
    callers that want to feed the data into other reporters).
    Body MUST NOT mutate the scene — T_PROFILE_READ_ONLY guard.
    """
    shape = core.get_shape(node)
    if not core._exists(shape):
        return None

    # ---- Topology ----
    poses = core.read_all_poses(node)
    # M_B24b2: multi-source aggregation. Legacy single-driver auto-
    # migrates to a single-element list, preserving byte-equivalent
    # behavior for the n_inputs / drv_attrs derived values below.
    drv_sources = core.read_driver_info_multi(node)
    drv_node = drv_sources[0].node if drv_sources else ""
    drv_attrs = [a for src in drv_sources for a in src.attrs]
    drvn_node, drvn_attrs = core.read_driven_info(node)
    quat_starts = core.read_quat_group_starts(node)

    n_poses = len(poses)
    n_inputs = len(drv_attrs)
    n_outputs = len(drvn_attrs)
    cells_full = n_poses * n_poses
    cells_sym = n_poses * (n_poses + 1) // 2

    # ---- Configuration (read-only display) ----
    # F1 reminder: solver_method is the CONFIGURED value; the
    # actually-used solver per evaluation lives in a C++ instance
    # member that is not bridged to a Maya plug.
    g = core.safe_get
    config = {
        "type_mode":      "RBF" if g(shape + ".type", 0) == 1
                          else "VectorAngle",
        "rbf_mode":       int(g(shape + ".rbfMode", 0)),
        "kernel":         int(g(shape + ".kernel", 1)),
        "input_encoding": int(g(shape + ".inputEncoding", 0)),
        "distance_type":  int(g(shape + ".distanceType", 0)),
        "radius":         float(g(shape + ".radius", 0.0)),
        "regularization": float(g(shape + ".regularization", 1e-08)),
        "solver_method":  int(g(shape + ".solverMethod", 0)),
    }

    # ---- Estimates ----
    mem = _estimate_memory(n_poses, n_inputs, n_outputs)
    times = _estimate_solve_times(n_poses, bool(quat_starts))

    # ---- Health checks (E.2 — reuse M3.1 analyse_node) ----
    health = core_prune.analyse_node(node, core_prune.PruneOptions())

    # ---- Split-suggestion trigger ----
    cholesky_ms = times["cholesky_sec"] * 1000.0
    triggers = []
    if n_poses > _THRESH_N_POSES:
        triggers.append("n_poses = {} > {}".format(
            n_poses, _THRESH_N_POSES))
    if n_inputs * n_outputs > _THRESH_CELLS:
        triggers.append("n_inputs * n_outputs = {} > {}".format(
            n_inputs * n_outputs, _THRESH_CELLS))
    if cholesky_ms > _THRESH_CHOL_MS:
        triggers.append("cholesky_time ~ {:.2f} ms > {} ms".format(
            cholesky_ms, _THRESH_CHOL_MS))

    return {
        "node_name": str(node),
        "topology": {
            "n_poses": n_poses,
            "n_inputs": n_inputs,
            "n_outputs": n_outputs,
            "cells_full": cells_full,
            "cells_sym": cells_sym,
            "quat_groups": len(quat_starts),
        },
        "configuration": config,
        "wiring": {
            "driver_node": drv_node or "",
            "driven_node": drvn_node or "",
            # M_B24b2: per-source list (B.2 5-column table).
            "driver_sources": [
                {"index": i, "node": s.node,
                 "attrs": list(s.attrs),
                 "weight": float(s.weight),
                 "encoding": int(s.encoding)}
                for i, s in enumerate(drv_sources)
            ],
        },
        "memory": mem,
        "performance": {
            "cholesky_sec": times["cholesky_sec"],
            "ge_sec": times["ge_sec"],
            "qwa_iter_sec": times["qwa_iter_sec"],
            "estimated_per_eval_sec": times["cholesky_sec"],
        },
        "health": {
            "duplicate_poses":  len(health.duplicate_pose_indices),
            "redundant_inputs": len(health.redundant_input_indices),
            "constant_outputs": len(health.constant_output_indices),
            "conflict_pairs":   len(health.conflict_pairs),
        },
        "split_triggers": triggers,
    }


# =====================================================================
#  format_report — pure ASCII renderer (T_CAVEAT_VISIBLE guard)
# =====================================================================


# Lookup tables for human-readable enum labels.
_KERNEL_LABELS = {
    0: "Linear", 1: "Gaussian1", 2: "Gaussian2", 3: "ThinPlate",
    4: "MultiQuadratic", 5: "InverseMultiQuadratic",
}
_RBF_MODE_LABELS = {0: "Generic", 1: "Matrix"}
_DIST_TYPE_LABELS = {0: "Euclidean", 1: "Angle"}
_INPUT_ENC_LABELS = {
    0: "Raw", 1: "Quaternion", 2: "BendRoll",
    3: "ExpMap", 4: "SwingTwist",
}
_SOLVER_METHOD_LABELS = {0: "Auto", 1: "ForceGE"}


def format_report(profile):
    """Render a :func:`profile_node` result as an ASCII report.

    Caveats are visually prominent: bracketed, on their own
    section-header line, AND repeated as a footer with the
    tunable-symbol identifiers. T_CAVEAT_VISIBLE guards the
    presence of these strings.
    """
    if not profile:
        return "(no profile data)"

    p = profile
    t = p["topology"]
    c = p["configuration"]
    w = p["wiring"]
    m = p["memory"]
    perf = p["performance"]
    h = p["health"]
    triggers = p.get("split_triggers", [])

    lines = []
    bar = "=" * 56
    lines.append(bar)
    lines.append("RBFtools Profile — {}".format(p["node_name"]))
    lines.append(bar)
    lines.append("")

    # ---- Topology ----
    lines.append("Topology")
    lines.append("  n_poses           : {}".format(t["n_poses"]))
    lines.append("  n_inputs          : {}".format(t["n_inputs"]))
    lines.append("  n_outputs         : {}".format(t["n_outputs"]))
    lines.append("  matrix_size       : {} x {}".format(
        t["n_poses"], t["n_poses"]))
    lines.append(
        "  matrix_cells      : {} (full) / {} (sym upper)".format(
            t["cells_full"], t["cells_sym"]))
    lines.append("  quat_groups       : {}".format(t["quat_groups"]))
    lines.append("")

    # ---- Configuration ----
    lines.append("Configuration")
    lines.append("  type_mode         : {}".format(c["type_mode"]))
    lines.append("  rbf_mode          : {}".format(
        _RBF_MODE_LABELS.get(c["rbf_mode"], c["rbf_mode"])))
    lines.append("  kernel            : {}".format(
        _KERNEL_LABELS.get(c["kernel"], c["kernel"])))
    lines.append("  input_encoding    : {}".format(
        _INPUT_ENC_LABELS.get(c["input_encoding"], c["input_encoding"])))
    lines.append("  distance_type     : {}".format(
        _DIST_TYPE_LABELS.get(c["distance_type"], c["distance_type"])))
    lines.append("  radius            : {}".format(c["radius"]))
    lines.append("  regularization    : {}".format(c["regularization"]))
    lines.append("  solver_method     : {}".format(
        _SOLVER_METHOD_LABELS.get(c["solver_method"], c["solver_method"])))
    lines.append("                      "
                 "[configured value; the actually-used solver per")
    lines.append("                       evaluation is held in a C++ "
                 "instance member and")
    lines.append("                       is not exposed to Python — "
                 "see addendum §M3.5.F1]")
    lines.append("")

    # ---- Wiring ----
    lines.append("Wiring")
    lines.append("  driver_node       : {}".format(
        w["driver_node"] or "(unconnected)"))
    lines.append("  driven_node       : {}".format(
        w["driven_node"] or "(unconnected)"))
    # M_B24b2: 5-column multi-source table (idx | node | attrs |
    # weight | encoding). Renders even for legacy single-driver
    # nodes (1-row table from auto-migrated drivers[0]).
    sources = w.get("driver_sources") or []
    if sources:
        lines.append("  Driver sources (multi):")
        lines.append("    idx | node           | attrs                   | "
                     "weight | enc")
        for s in sources:
            attrs_joined = ",".join(s["attrs"]) or "(none)"
            lines.append("     {:>2} | {:<14} | {:<23} | {:>6.3f} | {}".format(
                s["index"],
                (s["node"] or "(unset)")[:14],
                attrs_joined[:23],
                s["weight"],
                s["encoding"]))
    lines.append("")

    # ---- Memory ----
    lines.append("Memory estimates  (double-precision storage)")
    lines.append("  pose_data         : {}".format(
        _format_bytes(m["pose_data"])))
    lines.append("  weight_matrix     : {}".format(
        _format_bytes(m["weight_matrix"])))
    lines.append("  working_memory    : {}".format(
        _format_bytes(m["working_memory"])))
    lines.append("  total             : {}".format(
        _format_bytes(m["total"])))
    lines.append("")

    # ---- Performance (T_CAVEAT_VISIBLE — header caveat) ----
    lines.append("Performance estimates  "
                 "[CONCEPTUAL — no machine calibration]")
    lines.append("  cholesky_time     : {}".format(
        _format_ms(perf["cholesky_sec"])))
    lines.append("  ge_time           : {}".format(
        _format_ms(perf["ge_sec"])))
    lines.append("  qwa_iter_time     : {}".format(
        _format_ms(perf["qwa_iter_sec"])))
    lines.append("  estimated_per_eval: {}".format(
        _format_ms(perf["estimated_per_eval_sec"])))
    lines.append("")
    # T_CAVEAT_VISIBLE — footer caveat with tunable-symbol names so
    # users can grep their way to the calibration entry point.
    lines.append("  [tune _K_CHOL / _K_GE / _K_QWA in core_profile.py")
    lines.append("   for your hardware; see addendum §M3.5.F2]")
    lines.append("")

    # ---- Health checks (E.2 — reuses M3.1 analyse_node) ----
    lines.append("Health checks  [reuses M3.1 core_prune.analyse_node]")
    lines.append("  duplicate_poses   : {}".format(h["duplicate_poses"]))
    lines.append("  redundant_inputs  : {}".format(h["redundant_inputs"]))
    lines.append("  constant_outputs  : {}".format(h["constant_outputs"]))
    lines.append("  conflict_pairs    : {}".format(h["conflict_pairs"]))
    lines.append("")

    # ---- Recommendation ----
    lines.append("Recommendation")
    if triggers:
        lines.append("  [WARN] Node size triggers split suggestion:")
        for tr_msg in triggers:
            lines.append("           {}".format(tr_msg))
        # Magnitude table (C.2 — no semantic guesses).
        n_p = t["n_poses"]
        chol = perf["cholesky_sec"]
        if n_p > 0:
            lines.append("         If you split into N sub-nodes "
                         "(each ~M poses),")
            lines.append("         per-node Cholesky time scales "
                         "as O(M^3):")
            for n_split in (2, 3, 4):
                m_per = max(1, n_p // n_split)
                t_split = _K_CHOL * (m_per ** 3) * 1000.0
                lines.append("           N={} (M~{:>3}): ~{:.2f} ms / "
                             "node".format(n_split, m_per, t_split))
        lines.append("         Splitting strategy is rig-semantic "
                     "and must be")
        lines.append("         decided by the user — Profiler does "
                     "not auto-split")
        lines.append("         or suggest specific attribute "
                     "groupings.")
    else:
        lines.append("  [OK] Node size is healthy")

    lines.append(bar)
    return "\n".join(lines)


def profile_node_to_text(node):
    """Convenience wrapper: profile + format in one call. Used by
    the controller's "Profile to Script Editor" entry point."""
    return format_report(profile_node(node))
