# -*- coding: utf-8 -*-
"""PHASE17 engine-exact e2e (mayapy): scenarios C/D/E/G/H + regression A.

Semantics under M_P0_HIERARCHICAL_ENGINE_EXACT:
  D -- quat group: delta now BLENDS via so(3) (Phase 17b): near the
       child pose output moves TOWARD the child quat; far driver
       returns exactly the base QWA. Unit norm always.
  E -- scale channel: multiplicative delta (Phase 17a).
  G -- additive channel at the child pose: output lies strictly
       between base-only prediction and the actual child value
       (alpha-gated convex blend), and far drivers return base.
  H -- mask-only rig: output independent of masked-out driver.

Run:  mayapy.exe rbf_e2e_phase17_engine.py <path-to-RBFtools.mll>
"""
import math
import sys
import traceback

RESULTS = []


def check(label, cond, detail=""):
    RESULTS.append((label, bool(cond), detail))
    print("[{}] {} {}".format("PASS" if cond else "FAIL", label, detail))


def build_rig(cmds, name, n_in, n_out, poses, parents=None, masks=None,
              scale_channels=(), quat_start=None, clamp=True):
    shape = cmds.createNode("RBFtools", name=name + "Shape")
    cmds.setAttr(shape + ".type", 1)
    if not clamp:
        cmds.setAttr(shape + ".outputClampEnabled", 0)
    drv = cmds.spaceLocator(name=name + "_drv")[0]
    for i, a in enumerate(["tx", "ty", "tz"][:n_in]):
        cmds.connectAttr("{}.{}".format(drv, a),
                         "{}.input[{}]".format(shape, i))
    out_attrs = []
    n_locs = (n_out + 2) // 3
    for k in range(n_locs):
        loc = cmds.spaceLocator(name="{}_out{}".format(name, k))[0]
        for a in ("tx", "ty", "tz"):
            if len(out_attrs) >= n_out:
                break
            cmds.connectAttr(
                "{}.output[{}]".format(shape, len(out_attrs)),
                "{}.{}".format(loc, a))
            out_attrs.append("{}.{}".format(loc, a))
    for p, (ins, vals) in enumerate(poses):
        for i, v in enumerate(ins):
            cmds.setAttr("{}.poses[{}].poseInput[{}]".format(shape, p, i), v)
        for i, v in enumerate(vals):
            cmds.setAttr("{}.poses[{}].poseValue[{}]".format(shape, p, i), v)
    for p, v in (parents or {}).items():
        cmds.setAttr("{}.poses[{}].poseParentIndex".format(shape, p), v)
    for p, m in (masks or {}).items():
        cmds.setAttr("{}.poses[{}].poseDriverMask".format(shape, p),
                     list(m), type="Int32Array")
    for c in scale_channels:
        cmds.setAttr("{}.outputIsScale[{}]".format(shape, c), 1)
    if quat_start is not None:
        cmds.setAttr("{}.outputQuaternionGroupStart[0]".format(shape),
                     quat_start)
    cmds.setAttr(shape + ".evaluate", 1)
    return shape, drv, out_attrs


def read_outputs(cmds, drv, driver_vals, out_attrs):
    for i, a in enumerate(["tx", "ty", "tz"][:len(driver_vals)]):
        cmds.setAttr("{}.{}".format(drv, a), driver_vals[i])
    return [cmds.getAttr(a) for a in out_attrs]


def qnorm(q):
    return math.sqrt(sum(x * x for x in q))


def qdot(a, b):
    return sum(x * y for x, y in zip(a, b))


def main():
    import maya.standalone
    maya.standalone.initialize(name="python")
    import maya.cmds as cmds
    import maya.api.OpenMaya as om

    cmds.loadPlugin(sys.argv[1])
    cmds.file(new=True, force=True)

    warnings = []

    def _cb(msg, msg_type, _data):
        if msg_type == om.MCommandMessage.kWarning:
            warnings.append(msg)

    cb_id = om.MCommandMessage.addCommandOutputCallback(_cb)

    # ----------------------------------------------------------------
    # C -- sibling mask inconsistency warn (regression)
    # ----------------------------------------------------------------
    poses_c = [
        ([0.0, 0.0], [0.0]),
        ([1.0, 0.0], [1.0]),
        ([1.0, 0.5], [1.5]),
        ([1.0, 1.0], [2.0]),
    ]
    shape_c, drv_c, outs_c = build_rig(
        cmds, "rbfC", 2, 1, poses_c,
        parents={2: 1, 3: 1}, masks={2: [1], 3: [0, 1]})
    warnings[:] = []
    out_c = read_outputs(cmds, drv_c, [1.0, 0.25], outs_c)
    check("C.sibling mask warning",
          any(("sibling" in w and "union" in w) for w in warnings),
          (" | ".join(warnings))[:200])
    check("C.finite output", all(abs(v) < 1e6 for v in out_c), str(out_c))

    # ----------------------------------------------------------------
    # G -- additive channel: convex blend at child pose; base at far
    # driver. Clamp OFF so the raw math is visible.
    # ----------------------------------------------------------------
    base_poses = [
        ([0.0, 0.0], [0.0]),
        ([1.0, 0.0], [1.0]),
    ]
    full_poses = base_poses + [([1.0, 1.0], [3.0])]
    shape_g0, drv_g0, outs_g0 = build_rig(
        cmds, "rbfG0", 2, 1, base_poses, clamp=False)
    shape_g1, drv_g1, outs_g1 = build_rig(
        cmds, "rbfG1", 2, 1, full_poses, parents={2: 1}, clamp=False)

    child_drv = [1.0, 1.0]
    y_base = read_outputs(cmds, drv_g0, child_drv, outs_g0)[0]
    y_full = read_outputs(cmds, drv_g1, child_drv, outs_g1)[0]
    actual = 3.0
    lo, hi = sorted((y_base, actual))
    check("G.child-pose output between base and actual",
          lo - 1e-9 <= y_full <= hi + 1e-9,
          "base={:.6f} full={:.6f} actual={}".format(y_base, y_full, actual))
    check("G.delta engages (moves toward actual)",
          abs(y_full - actual) < abs(y_base - actual) - 1e-6,
          "base={:.6f} full={:.6f}".format(y_base, y_full))

    far_drv = [40.0, 40.0]
    yb_far = read_outputs(cmds, drv_g0, far_drv, outs_g0)[0]
    yf_far = read_outputs(cmds, drv_g1, far_drv, outs_g1)[0]
    check("G.far driver returns base (anti-leak)",
          abs(yf_far - yb_far) < 1e-6,
          "base={:.9f} full={:.9f}".format(yb_far, yf_far))

    # ----------------------------------------------------------------
    # E -- multiplicative scale delta (Phase 17a). Channel 0 is scale.
    # ----------------------------------------------------------------
    scale_base = [
        ([0.0, 0.0], [1.0]),
        ([1.0, 0.0], [2.0]),
    ]
    scale_full = scale_base + [([1.0, 1.0], [3.0])]
    shape_e0, drv_e0, outs_e0 = build_rig(
        cmds, "rbfE0", 2, 1, scale_base, scale_channels=(0,), clamp=False)
    shape_e1, drv_e1, outs_e1 = build_rig(
        cmds, "rbfE1", 2, 1, scale_full, parents={2: 1},
        scale_channels=(0,), clamp=False)

    s_base = read_outputs(cmds, drv_e0, child_drv, outs_e0)[0]
    s_full = read_outputs(cmds, drv_e1, child_drv, outs_e1)[0]
    lo, hi = sorted((s_base, 3.0))
    check("E.scale child-pose output between base and actual",
          lo - 1e-9 <= s_full <= hi + 1e-9,
          "base={:.6f} full={:.6f} actual=3.0".format(s_base, s_full))
    check("E.scale delta engages",
          abs(s_full - 3.0) < abs(s_base - 3.0) - 1e-6,
          "base={:.6f} full={:.6f}".format(s_base, s_full))
    sb_far = read_outputs(cmds, drv_e0, far_drv, outs_e0)[0]
    sf_far = read_outputs(cmds, drv_e1, far_drv, outs_e1)[0]
    check("E.scale far driver returns base",
          abs(sf_far - sb_far) < 1e-6,
          "base={:.9f} full={:.9f}".format(sb_far, sf_far))

    # ----------------------------------------------------------------
    # D -- quat group so(3) delta (Phase 17b). 7 outputs, quat @ 3.
    # ----------------------------------------------------------------
    pose_rest = ([0.0, 0.0], [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0])
    pose_base = ([1.0, 0.0], [1.0, 0.5, 0.2, 0.1, 0.0, 0.0, 0.995])
    q_child = [0.3, 0.1, 0.0, 0.95]
    nrm = qnorm(q_child)
    q_child = [x / nrm for x in q_child]
    pose_delta = ([1.0, 1.0], [2.0, 1.0, 0.4] + q_child)

    shape_d0, drv_d0, outs_d0 = build_rig(
        cmds, "rbfD0", 2, 7, [pose_rest, pose_base],
        quat_start=3, clamp=False)
    shape_d1, drv_d1, outs_d1 = build_rig(
        cmds, "rbfD1", 2, 7, [pose_rest, pose_base, pose_delta],
        parents={2: 1}, quat_start=3, clamp=False)

    o0 = read_outputs(cmds, drv_d0, child_drv, outs_d0)
    o1 = read_outputs(cmds, drv_d1, child_drv, outs_d1)
    qb, qf = o0[3:7], o1[3:7]
    check("D.quat unit norm", abs(qnorm(qf) - 1.0) < 1e-6,
          "norm={:.9f}".format(qnorm(qf)))
    check("D.quat delta engages (toward child quat)",
          abs(qdot(qf, q_child)) > abs(qdot(qb, q_child)) + 1e-9,
          "dot(base,qa)={:.6f} dot(full,qa)={:.6f}".format(
              qdot(qb, q_child), qdot(qf, q_child)))
    o0f = read_outputs(cmds, drv_d0, far_drv, outs_d0)
    o1f = read_outputs(cmds, drv_d1, far_drv, outs_d1)
    check("D.quat far driver == base QWA (anti-leak)",
          all(abs(a - b) < 1e-7 for a, b in zip(o0f[3:7], o1f[3:7])),
          "base={} full={}".format(o0f[3:7], o1f[3:7]))

    # ----------------------------------------------------------------
    # H -- mask-only rig: masked-out driver must not affect output.
    # Both poses vary on BOTH drivers (hull non-degenerate) but the
    # mask says "driver 0 only".
    # ----------------------------------------------------------------
    poses_h = [
        ([0.0, 0.0], [0.0]),
        ([1.0, 1.0], [1.0]),
    ]
    shape_h, drv_h, outs_h = build_rig(
        cmds, "rbfH", 2, 1, poses_h,
        masks={0: [0], 1: [0]}, clamp=False)
    y_h1 = read_outputs(cmds, drv_h, [0.5, 0.0], outs_h)[0]
    y_h2 = read_outputs(cmds, drv_h, [0.5, 0.9], outs_h)[0]
    check("H.mask-only: masked driver ignored",
          abs(y_h1 - y_h2) < 1e-9,
          "y(d1=0)={:.9f} y(d1=0.9)={:.9f}".format(y_h1, y_h2))

    # ----------------------------------------------------------------
    # A -- regression: plain rig (no parent, no mask) unchanged
    # behavior + no hierarchy warnings.
    # ----------------------------------------------------------------
    warnings[:] = []
    shape_a, drv_a, outs_a = build_rig(
        cmds, "rbfA", 2, 1,
        [([0.0, 0.0], [0.0]), ([1.0, 0.0], [1.0])])
    y_a = read_outputs(cmds, drv_a, [0.5, 0.0], outs_a)[0]
    check("A.plain rig sane interpolation", 0.0 < y_a < 1.0,
          "y={:.6f}".format(y_a))
    check("A.no hierarchy warnings on plain rig",
          not any("HIERARCH" in w or "PHASE17" in w for w in warnings),
          (" | ".join(warnings))[:200])

    om.MMessage.removeCallback(cb_id)


try:
    main()
except Exception:
    traceback.print_exc()
    RESULTS.append(("script crashed", False, ""))

n_fail = sum(1 for _, ok, _ in RESULTS if not ok)
print("=" * 60)
print("TOTAL {} checks, {} failed".format(len(RESULTS), n_fail))
sys.exit(1 if n_fail else 0)
