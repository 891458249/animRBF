# -*- coding: utf-8 -*-
"""M_P0_KERNEL_SWITCH_ROLLBACK — Phase 5 数据等价性诊断脚本.

[Renamed 2026-05-11 from diag_kernel_switch.py per Planner Step 0
+ ROLLBACK_6 spec; underlying Maya capture logic preserved verbatim.
The rename reflects the ROLLBACK chain's "Phase 5 verify" framing
rather than the original "Phase 1 baseline capture" framing.]

用法 (Maya GUI Script Editor 或 mayapy):

    # 在 oracle 跑 (X:\\RBFtools 模块加载, 切到 RBFnode_shoulder_LShape)
    exec(open(r"X:\\Plugins\\RBFtools\\modules\\RBFtools\\tests\\scratch\\diag_kernel_rollback.py").read())
    diag(which="oracle", out_dir=r"X:\\temp")
    # → X:\\temp\\diag_kernel_switch_oracle.csv

    # 在 current 跑 (worktree 部署的 .mll 加载, 同 rig)
    exec(open(...).read())
    diag(which="current", out_dir=r"X:\\temp")
    # → X:\\temp\\diag_kernel_switch_current.csv

    # 普通 Python 端 (mayapy 之外) 对比:
    python diag_kernel_rollback.py --baseline X:/temp/diag_kernel_switch_oracle.csv \\
                                    --compare  X:/temp/diag_kernel_switch_current.csv \\
                                    --tol 1e-3

CSV columns:
    kernel_idx, kernel_name, pose_idx, joint, attr, observed, target, delta

Each cell:
  observed = current driven attr value at pose-i driver center under kernel k
  target   = stored poseValue[i, c] (training-point ground truth)
  delta    = observed - target (training-point drift; should ≈ 0 for correct kernel)

For each (kernel, pose i):
  1. Drive every connected source attribute to pose i's stored
     ``poseInput[j]`` value (sets rig EXACTLY at training pose i).
  2. Toggle ``shape.evaluate`` 0→1 to force C++ retrain under the
     current kernel choice (current build path; harmless on oracle).
  3. ``cmds.dgdirty(shape + ".output")`` + ``cmds.getAttr`` on every
     driven joint × attr → record the inferred value.
  4. Training-point identity: ``∀i: Σ_j w_j φ(d(p_i, p_j); σ) = y_i``
     under the *correct* kernel; deviations > 1e-3 indicate drift.

Phase 5 完成判据:

    max |Δ| < 1e-3   over   6 kernel × 20 pose × 10 joint × 9 attr
                            = 10800 cells

If diff_csvs() prints any row, those (kernel × pose × joint × attr)
cells are the regression locations and ROLLBACK_1/2/5 fix is incomplete.

ROLLBACK chain reference:
  - c924b1c  ROLLBACK_1  TPS r<=0 → value
  - 91adfc9  ROLLBACK_2  remove λ retry loop
  - 7e6c25f  ROLLBACK_5  dual .mll deploy (183,296 B)
  - (this commit) ROLLBACK_6  docs + parity guard + diag rename
  - Oracle anchor: e249ec0 (= 156af4c~1)
  - Detail: docs/排查/M_P0_KERNEL_SWITCH_ROLLBACK_index.md

NOT a pytest test. Lives in tests/scratch/ so collection skips it.
"""
from __future__ import absolute_import, division, print_function

import csv
import os
import sys


# ----------------------------------------------------------------------
# Diag entry point — RUN INSIDE MAYA
# ----------------------------------------------------------------------

KERNEL_NAMES = [
    "Linear",                     # 0
    "Gaussian 1",                 # 1
    "Gaussian 2",                 # 2
    "Thin Plate",                 # 3
    "Multi-Quadratic Biharmonic", # 4
    "Inverse Multi-Quadratic Biharmonic",  # 5
]


def diag(node_shape="RBFnode_shoulder_LShape",
         which="current",
         out_dir=None,
         tol_print=1e-3):
    """Sweep 6 kernels × poses × driven channels; write CSV.

    Args:
        node_shape: RBFtools shape node name (no transform).
        which: "current" or "oracle" — affects only the output filename.
        out_dir: where to write the CSV. Default: %USERPROFILE%.
        tol_print: print rows where |observed - target| > tol to
                   Script Editor for live feedback (does not affect CSV).
    """
    import maya.cmds as cmds  # only valid inside Maya

    if not cmds.objExists(node_shape):
        raise RuntimeError(
            "diag: node {!r} not found in current scene. "
            "Open the user's reproducer rig first.".format(node_shape))

    out_dir = out_dir or os.path.expanduser("~")
    out_path = os.path.join(
        out_dir, "diag_kernel_switch_{}.csv".format(which))

    # ---- snapshot the source attrs that drive `input[]` ----
    # M_B24a (driverSource[].driverSource_attrs) is the modern path;
    # legacy single-driver uses driverList[]. Cover both.
    drivers = _collect_driver_attrs(node_shape)
    if not drivers:
        raise RuntimeError(
            "diag: no driver source attrs found on {!r}. "
            "Did the rig finish loading?".format(node_shape))

    # ---- enumerate poses + their stored poseInput values ----
    poses = _collect_pose_inputs(node_shape)
    pose_count = len(poses)
    if pose_count == 0:
        raise RuntimeError(
            "diag: no poses on {!r}.".format(node_shape))

    # ---- enumerate driven (output) targets ----
    driven_channels = _collect_driven_channels(node_shape)
    if not driven_channels:
        raise RuntimeError(
            "diag: no driven output connections.")

    # ---- snapshot stored pose values per (pose_idx, output_idx) ----
    # The training-point identity says
    #     observed[i, c]  ==  poseValue[i, c]   (mod λ noise)
    # under the correct kernel. We compare observed against this.
    pose_values = _collect_pose_values(node_shape)

    print("[diag] node={} drivers={} poses={} driven_channels={}"
          .format(node_shape, len(drivers), pose_count,
                  len(driven_channels)))

    rows = []
    drift_count = 0
    for k in range(6):
        cmds.setAttr(node_shape + ".kernel", k)
        # Force C++ retrain under the new kernel: evaluate plug toggle.
        # Harmless on oracle (oracle has no prev-tracker, but Apply on
        # the user's part has same effect).
        try:
            cmds.setAttr(node_shape + ".evaluate", 0)
            cmds.setAttr(node_shape + ".evaluate", 1)
        except Exception:
            pass  # oracle may not expose evaluate; not fatal
        for i, pose_input in enumerate(poses):
            # Drive each source attr to pose i's value.
            for src_idx, val in enumerate(pose_input):
                if src_idx >= len(drivers):
                    break
                node, attr = drivers[src_idx]
                try:
                    cmds.setAttr(node + "." + attr, val)
                except Exception:
                    pass
            # Force compute.
            cmds.dgdirty(node_shape + ".output")
            # Read every driven channel.
            for c, (joint, attr) in enumerate(driven_channels):
                try:
                    observed = cmds.getAttr(joint + "." + attr)
                except Exception:
                    observed = float("nan")
                target = (pose_values[i][c]
                          if (i < len(pose_values)
                              and c < len(pose_values[i]))
                          else 0.0)
                rows.append((k, KERNEL_NAMES[k], i, joint, attr,
                             observed, target,
                             observed - target if isinstance(observed, float)
                             and observed == observed else float("nan")))
                if (isinstance(observed, float)
                        and observed == observed
                        and abs(observed - target) > tol_print):
                    drift_count += 1
                    if drift_count <= 30:  # cap log spam
                        print("[diag] DRIFT k={} pose={} {}.{} "
                              "obs={:.6f} tgt={:.6f} Δ={:+.6f}".format(
                                  KERNEL_NAMES[k], i, joint, attr,
                                  observed, target, observed - target))

    # ---- write CSV ----
    with open(out_path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["kernel_idx", "kernel_name", "pose_idx",
                    "joint", "attr", "observed", "target", "delta"])
        for r in rows:
            w.writerow(r)

    print("[diag] {} rows written to {}".format(len(rows), out_path))
    print("[diag] {} cells with |Δ| > {} (training-point drift)"
          .format(drift_count, tol_print))
    print("[diag] next: rerun in oracle Maya session, then "
          "`python {} --diff <current> <oracle>`"
          .format(__file__))
    return out_path


# ----------------------------------------------------------------------
# Helpers (Maya-only, called by diag())
# ----------------------------------------------------------------------

def _collect_driver_attrs(shape):
    """Return [(node, attr), ...] in input[] index order."""
    import maya.cmds as cmds
    out = []
    indices = cmds.getAttr(shape + ".input", multiIndices=True) or []
    for i in indices:
        plug = "{}.input[{}]".format(shape, i)
        srcs = cmds.listConnections(plug, source=True, destination=False,
                                    plugs=True) or []
        if srcs:
            node, attr = srcs[0].split(".", 1)
            out.append((node, attr))
    return out


def _collect_pose_inputs(shape):
    """Return [[float, ...], ...] one row per pose, in input[] order."""
    import maya.cmds as cmds
    pose_indices = cmds.getAttr(shape + ".poses", multiIndices=True) or []
    rows = []
    for pi in pose_indices:
        in_indices = cmds.getAttr(
            "{}.poses[{}].poseInput".format(shape, pi),
            multiIndices=True) or []
        if not in_indices:
            continue  # last sparse slot
        row = []
        for ii in in_indices:
            row.append(cmds.getAttr(
                "{}.poses[{}].poseInput[{}]".format(shape, pi, ii)))
        rows.append(row)
    return rows


def _collect_pose_values(shape):
    """Return [[float, ...], ...] one row per pose, in output index order."""
    import maya.cmds as cmds
    pose_indices = cmds.getAttr(shape + ".poses", multiIndices=True) or []
    rows = []
    for pi in pose_indices:
        v_indices = cmds.getAttr(
            "{}.poses[{}].poseValue".format(shape, pi),
            multiIndices=True) or []
        if not v_indices:
            continue
        row = []
        for vi in v_indices:
            row.append(cmds.getAttr(
                "{}.poses[{}].poseValue[{}]".format(shape, pi, vi)))
        rows.append(row)
    return rows


def _collect_driven_channels(shape):
    """Return [(joint, attr), ...] in output[] index order."""
    import maya.cmds as cmds
    out = []
    out_indices = cmds.getAttr(shape + ".output", multiIndices=True) or []
    for o in out_indices:
        plug = "{}.output[{}]".format(shape, o)
        dsts = cmds.listConnections(plug, source=False, destination=True,
                                    plugs=True) or []
        if dsts:
            node, attr = dsts[0].split(".", 1)
            out.append((node, attr))
    return out


# ----------------------------------------------------------------------
# Diff entry point — RUN OUTSIDE MAYA (regular Python)
# ----------------------------------------------------------------------

def diff_csvs(current_path, oracle_path, tol=1e-3, max_rows=200):
    """Compare two diag CSVs cell-by-cell. Print rows where
    |current - oracle| > tol (these are the regressions)."""
    cur = _load_csv(current_path)
    ora = _load_csv(oracle_path)
    keys = sorted(set(cur.keys()) | set(ora.keys()))
    diffs = []
    for k in keys:
        cv = cur.get(k, ("?", "?", float("nan"), float("nan"), float("nan")))
        ov = ora.get(k, ("?", "?", float("nan"), float("nan"), float("nan")))
        if cv[2] != cv[2] or ov[2] != ov[2]:
            # NaN
            if cv[2] != cv[2] and ov[2] != ov[2]:
                continue
            diffs.append((k, cv, ov, float("inf")))
            continue
        delta = cv[2] - ov[2]
        if abs(delta) > tol:
            diffs.append((k, cv, ov, delta))
    print("[diff] {} cells with |Δ| > {}".format(len(diffs), tol))
    for k, cv, ov, d in diffs[:max_rows]:
        kidx, pidx, joint, attr = k
        print("  k={:<35} pose={:<3} {}.{:<10} cur={:>+10.4f} "
              "ora={:>+10.4f} Δ={:>+10.4f}".format(
                  cv[0], pidx, joint, attr, cv[2], ov[2], d))
    if len(diffs) > max_rows:
        print("  ... ({} more)".format(len(diffs) - max_rows))


def _load_csv(path):
    """Return {(kernel_idx, pose_idx, joint, attr): (kname, kidx,
                observed, target, delta)}."""
    out = {}
    with open(path, "r") as fh:
        r = csv.reader(fh)
        next(r)  # header
        for row in r:
            kidx, kname, pidx, joint, attr = (int(row[0]), row[1],
                                              int(row[2]), row[3], row[4])
            obs = float(row[5]) if row[5] not in ("", "nan") else float("nan")
            tgt = float(row[6]) if row[6] not in ("", "nan") else float("nan")
            d = float(row[7]) if row[7] not in ("", "nan") else float("nan")
            out[(kidx, pidx, joint, attr)] = (kname, kidx, obs, tgt, d)
    return out


# ----------------------------------------------------------------------
# CLI — supports both legacy `--diff a b` and Planner-spec
# `--baseline path --compare path [--tol 1e-3]`
# ----------------------------------------------------------------------

def _parse_argv(argv):
    """Tiny arg parser (no argparse dep so the script stays
    drop-in for ancient mayapy embeddings)."""
    args = {"baseline": None, "compare": None, "tol": 1e-3}
    i = 1
    while i < len(argv):
        tok = argv[i]
        if tok == "--baseline" and i + 1 < len(argv):
            args["baseline"] = argv[i + 1]; i += 2
        elif tok == "--compare" and i + 1 < len(argv):
            args["compare"] = argv[i + 1]; i += 2
        elif tok == "--tol" and i + 1 < len(argv):
            args["tol"] = float(argv[i + 1]); i += 2
        elif tok == "--diff" and i + 2 < len(argv):
            # Legacy positional form (kept for back-compat with the
            # diag_kernel_switch.py callers that pre-date the rename).
            args["compare"]  = argv[i + 1]
            args["baseline"] = argv[i + 2]
            i += 3
        else:
            i += 1
    return args


if __name__ == "__main__":
    args = _parse_argv(sys.argv)
    if args["baseline"] and args["compare"]:
        # Convention: baseline = oracle, compare = current.
        # diff_csvs(current_path, oracle_path) so swap the call args.
        diff_csvs(args["compare"], args["baseline"], tol=args["tol"])
    else:
        print(__doc__)
        print("\nUsage:")
        print("  python diag_kernel_rollback.py "
              "--baseline <oracle.csv> --compare <current.csv> "
              "[--tol 1e-3]")
        print("\nOR (legacy):")
        print("  python diag_kernel_rollback.py "
              "--diff <current.csv> <oracle.csv>")
        sys.exit(0)
