# -*- coding: utf-8 -*-
"""Phase 16 hierarchy e2e check (mayapy): scenario B round-trip + A defaults.

Run:  mayapy.exe rbf_e2e_phase16_roundtrip.py <path-to-RBFtools.mll>
Exit code 0 = all PASS, 1 = any FAIL.
"""
import os
import sys
import tempfile
import traceback

MLL = sys.argv[1] if len(sys.argv) > 1 else None
RESULTS = []


def check(label, cond, detail=""):
    RESULTS.append((label, bool(cond), detail))
    print("[{}] {} {}".format("PASS" if cond else "FAIL", label, detail))


def main():
    import maya.standalone
    maya.standalone.initialize(name="python")
    import maya.cmds as cmds

    cmds.loadPlugin(MLL)
    check("plugin loaded", cmds.pluginInfo("RBFtools", q=True, loaded=True))

    # ----------------------------------------------------------------
    # Scenario B -- set parent/mask -> save .ma -> reopen -> fields kept
    # ----------------------------------------------------------------
    cmds.file(new=True, force=True)
    shape = cmds.createNode("RBFtools")
    cmds.setAttr(shape + ".type", 1)

    # three poses: pose 0/2 base, pose 1 delta of 0 with mask [0]
    for p in range(3):
        for i in range(2):
            cmds.setAttr("{}.poses[{}].poseInput[{}]".format(shape, p, i),
                         0.5 * p + 0.1 * i)
        cmds.setAttr("{}.poses[{}].poseValue[0]".format(shape, p), 1.0 * p)
    cmds.setAttr("{}.poses[1].poseParentIndex".format(shape), 0)
    cmds.setAttr("{}.poses[1].poseDriverMask".format(shape), [0],
                 type="Int32Array")

    # pre-save sanity
    check("B.pre parent set", cmds.getAttr(
        "{}.poses[1].poseParentIndex".format(shape)) == 0)

    ma_path = os.path.join(tempfile.gettempdir(),
                           "rbf_e2e_phase16_roundtrip.ma")
    if os.path.exists(ma_path):
        os.remove(ma_path)
    cmds.file(rename=ma_path)
    cmds.file(save=True, type="mayaAscii")
    cmds.file(new=True, force=True)
    cmds.file(ma_path, open=True, force=True)

    nodes = cmds.ls(type="RBFtools") or []
    check("B.reopen node exists", len(nodes) == 1, str(nodes))
    shape2 = nodes[0]

    parent_rt = cmds.getAttr("{}.poses[1].poseParentIndex".format(shape2))
    check("B.parent round-trip == 0", parent_rt == 0, "got {}".format(parent_rt))

    mask_rt = cmds.getAttr("{}.poses[1].poseDriverMask".format(shape2))
    flat = list(mask_rt[0]) if (mask_rt and isinstance(mask_rt[0], (list, tuple))) \
        else list(mask_rt or [])
    check("B.mask round-trip == [0]", flat == [0], "got {}".format(flat))

    p0 = cmds.getAttr("{}.poses[0].poseParentIndex".format(shape2))
    p2 = cmds.getAttr("{}.poses[2].poseParentIndex".format(shape2))
    check("B.untouched poses stay -1", p0 == -1 and p2 == -1,
          "p0={} p2={}".format(p0, p2))

    # pose values survived too (sanity that the .ma carries the compound)
    v1 = cmds.getAttr("{}.poses[1].poseValue[0]".format(shape2))
    check("B.poseValue survives", abs(v1 - 1.0) < 1e-9, "got {}".format(v1))

    # ----------------------------------------------------------------
    # Scenario A -- legacy-style node: nothing written -> defaults
    # ----------------------------------------------------------------
    cmds.file(new=True, force=True)
    shapeA = cmds.createNode("RBFtools")
    cmds.setAttr(shapeA + ".type", 1)
    for p in range(2):
        cmds.setAttr("{}.poses[{}].poseInput[0]".format(shapeA, p), float(p))
        cmds.setAttr("{}.poses[{}].poseValue[0]".format(shapeA, p), float(p))

    pa = cmds.getAttr("{}.poses[0].poseParentIndex".format(shapeA))
    check("A.default parent == -1", pa == -1, "got {}".format(pa))
    maskA = cmds.getAttr("{}.poses[0].poseDriverMask".format(shapeA))
    flatA = list(maskA[0]) if (maskA and isinstance(maskA[0], (list, tuple))) \
        else list(maskA or [])
    check("A.default mask empty", flatA == [], "got {}".format(flatA))

    # round-trip a legacy node (no hierarchy writes at all)
    ma2 = os.path.join(tempfile.gettempdir(), "rbf_e2e_phase16_legacy.ma")
    if os.path.exists(ma2):
        os.remove(ma2)
    cmds.file(rename=ma2)
    cmds.file(save=True, type="mayaAscii")
    # the .ma must NOT contain hierarchy attrs (defaults not serialized)
    with open(ma2, "r") as fh:
        ma_text = fh.read()
    check("A.legacy .ma has no ppi/pdm spam",
          ".ppi" not in ma_text and ".pdm" not in ma_text
          and "poseParentIndex" not in ma_text)

    # while we're here: scenario-B .ma SHOULD contain the explicit write
    with open(ma_path, "r") as fh:
        ma_b = fh.read()
    check("B..ma carries explicit parent",
          ("poseParentIndex" in ma_b) or (".ppi" in ma_b))


try:
    main()
except Exception:
    traceback.print_exc()
    RESULTS.append(("script crashed", False, ""))

n_fail = sum(1 for _, ok, _ in RESULTS if not ok)
print("=" * 60)
print("TOTAL {} checks, {} failed".format(len(RESULTS), n_fail))
sys.exit(1 if n_fail else 0)
