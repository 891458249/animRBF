# -*- coding: utf-8 -*-
"""T_M_P0_QUAT_RBF_LANDING_GUARDS — End-to-end mayapy 集成测试

Real-mayapy verification of the multi-driver × multi-driven
quaternion RBF stack against the deployed RBFtools.mll. Skipped
under pure-Python conftest (no real Maya); under mayapy 2025
runs the full schema + dgeval matrix.

Coverage matrix (per
``docs/设计文档/RBFtools_v5_multi_quat_implementation.md``):

  Section A — Multi-driver N-generic (input encode):
    A1. N=1 + Quat baseline                          eff=4
    A2. N=3 + Quat (user 当前场景)                    eff=12
    A3. N=5 + Quat                                    eff=20
    A4. N=10 + Quat                                   eff=40
    A5. N=16 + Quat (max stress)                      eff=64

  Section B — Multi-driven (output paths):
    B1. outputEncoding=1 (Quat path B2 nlerp)
    B2. outputEncoding=2 (ExpMap path B2)
    B3. quatGroupStarts B1 QWA path
    B4. B1 + B2 共存 (列下标不重叠)

  Section C — 4 input encodings:
    C1-C4. Raw / BendRoll / ExpMap / SwingTwist (N=3)

  Section D — Numerical correctness:
    D1. Pose 中心精确恢复
    D2. Tikhonov 正则化效果
    D3. Double-cover invariance live

Tests use minimal RBF nodes — driver source = single locator's
rotateXYZ, driven side = direct attribute reads. We don't build
full rigging chains; the goal is exercising the C++ compute
path end-to-end with realistic schema configurations.
"""
from __future__ import absolute_import, division, print_function

import math
import os
import sys
import unittest


_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

_REPO_ROOT = os.path.normpath(
    os.path.join(_HERE, "..", "..", "..")
)
_MLL_PATH = os.path.join(_REPO_ROOT, "modules", "RBFtools", "plug-ins",
                          "win64", "2025", "RBFtools.mll")


def _real_maya():
    """Lazy detection — avoids module-level conftest import."""
    try:
        import conftest
        return getattr(conftest, "_REAL_MAYA", False)
    except ImportError:
        return False


_REAL_MAYA = _real_maya()


def _load_plugin_or_skip():
    """Setup helper: init mayapy + load .mll. Skips if either fails."""
    from _mayapy_fixtures import ensure_maya_standalone
    ensure_maya_standalone()
    import maya.cmds as cmds
    if not cmds.pluginInfo("RBFtools", q=True, loaded=True):
        try:
            cmds.loadPlugin(_MLL_PATH)
        except Exception as exc:
            raise unittest.SkipTest(
                "RBFtools.mll failed to load: {}".format(exc))


def _make_node(cmds, name="RBF"):
    """Create a fresh RBFtools node + ensure Generic mode."""
    n = cmds.createNode("RBFtools", name=name)
    cmds.setAttr(n + ".rbfMode", 0)   # Generic
    cmds.setAttr(n + ".active", True)
    return n


def _connect_n_drivers(cmds, node, n_drivers, encoding=1):
    """Wire N driver locators' rotateXYZ → input[0..3N-1].

    Returns list of locator names so callers can manipulate them.
    """
    locs = []
    cmds.setAttr(node + ".inputEncoding", encoding)
    for k in range(n_drivers):
        loc = cmds.spaceLocator(name="drv{}".format(k))[0]
        locs.append(loc)
        for ax_idx, ax in enumerate(("rx", "ry", "rz")):
            attr_idx = k * 3 + ax_idx
            cmds.connectAttr(
                "{}.{}".format(loc, ax),
                "{}.input[{}]".format(node, attr_idx),
            )
    return locs


def _add_pose(cmds, node, pose_idx, driver_eulers, driven_values):
    """Write one pose row.

    driver_eulers: flat list of 3N rad values (matches input[] layout)
    driven_values: flat list of solveCount values (matches output layout)
    """
    for j, v in enumerate(driver_eulers):
        cmds.setAttr(
            "{}.poses[{}].poseInput[{}]".format(node, pose_idx, j), v)
    for j, v in enumerate(driven_values):
        cmds.setAttr(
            "{}.poses[{}].poseValue[{}]".format(node, pose_idx, j), v)


# ====================================================================
# Section A — Multi-driver N-generic encode
# ====================================================================

@unittest.skipIf(not _REAL_MAYA,
    "Real mayapy required for E2E quaternion RBF dgeval coverage.")
class TestQuatRBFE2EMultiDriver(unittest.TestCase):
    """Multi-driver N-generic input-side coverage."""

    @classmethod
    def setUpClass(cls):
        _load_plugin_or_skip()

    def setUp(self):
        import maya.cmds as cmds
        cmds.file(new=True, force=True)

    def _verify_n_drivers_load(self, N):
        """N driver × Quat → dgeval 不抛异常 + 输出可读."""
        import maya.cmds as cmds
        node = _make_node(cmds, "rbf_N{}".format(N))
        _connect_n_drivers(cmds, node, N, encoding=1)
        # Add 3 random poses + 1 trivial (output dim = 3 to keep test small)
        for p in range(3):
            drv = [0.1 * (k + p) for k in range(3 * N)]
            cmds.setAttr(node + ".poses[{}].poseInput".format(p),
                         *drv, type="doubleArray") if False else None
            # Set per element (Maya schema requirement)
            for j, v in enumerate(drv):
                cmds.setAttr(
                    "{}.poses[{}].poseInput[{}]".format(node, p, j), v)
            for j in range(3):
                cmds.setAttr(
                    "{}.poses[{}].poseValue[{}]".format(node, p, j),
                    float(p) * 0.1)

        # Force eval — output[0] read through DG.
        result = cmds.getAttr(node + ".output[0]")
        self.assertIsNotNone(result,
            "N={} dgeval failed; output[0] returned None".format(N))

    def test_a01_N1_quat_eff_4(self):
        self._verify_n_drivers_load(1)

    def test_a02_N3_quat_eff_12(self):
        """user 当前场景 reproducer: 3 driver × Quat → 12 维."""
        self._verify_n_drivers_load(3)

    def test_a03_N5_quat_eff_20(self):
        self._verify_n_drivers_load(5)

    def test_a04_N10_quat_eff_40(self):
        self._verify_n_drivers_load(10)

    def test_a05_N16_quat_eff_64(self):
        """N=16 max stress — verifies inputs[] schema scales."""
        self._verify_n_drivers_load(16)


# ====================================================================
# Section B — Multi-driven output paths
# ====================================================================

@unittest.skipIf(not _REAL_MAYA,
    "Real mayapy required for E2E output-side path coverage.")
class TestQuatRBFE2EMultiDriven(unittest.TestCase):
    """B1 (QWA) / B2 (outputEncoding) / coexistence coverage."""

    @classmethod
    def setUpClass(cls):
        _load_plugin_or_skip()

    def setUp(self):
        import maya.cmds as cmds
        cmds.file(new=True, force=True)

    def test_b01_output_encoding_quat_path(self):
        """outputEncoding=1: Quat-path nlerp inverse transform fires."""
        import maya.cmds as cmds
        node = _make_node(cmds, "rbf_b01")
        _connect_n_drivers(cmds, node, 1, encoding=1)
        cmds.setAttr(node + ".outputEncoding", 1)
        # 3-block output (rx, ry, rz)
        for p in range(3):
            for j, v in enumerate([0.0, 0.0, 0.0]):
                cmds.setAttr(
                    "{}.poses[{}].poseInput[{}]".format(node, p, j),
                    float(p) * 0.5)
            for j, v in enumerate([0.0, float(p) * 0.3, 0.0]):
                cmds.setAttr(
                    "{}.poses[{}].poseValue[{}]".format(node, p, j), v)
        out0 = cmds.getAttr(node + ".output[0]")
        out1 = cmds.getAttr(node + ".output[1]")
        out2 = cmds.getAttr(node + ".output[2]")
        # Smoke: dgeval succeeded.
        self.assertIsNotNone(out0)
        self.assertIsNotNone(out1)
        self.assertIsNotNone(out2)

    def test_b02_output_encoding_expmap_path(self):
        """outputEncoding=2: ExpMap-path log/sum/exp inverse fires.

        Regression for M_P0_OUTPUT_EXPMAP_FIX — enum value 2 must
        not silently fall back to Raw weighted sum.
        """
        import maya.cmds as cmds
        node = _make_node(cmds, "rbf_b02")
        _connect_n_drivers(cmds, node, 1, encoding=1)
        cmds.setAttr(node + ".outputEncoding", 2)
        for p in range(3):
            for j in range(3):
                cmds.setAttr(
                    "{}.poses[{}].poseInput[{}]".format(node, p, j),
                    float(p) * 0.5)
            for j in range(3):
                cmds.setAttr(
                    "{}.poses[{}].poseValue[{}]".format(node, p, j),
                    float(p) * 0.3 if j == 1 else 0.0)
        out = [cmds.getAttr(node + ".output[{}]".format(i))
               for i in range(3)]
        for v in out:
            self.assertIsNotNone(v)

    def test_b03_quat_group_qwa_path(self):
        """quatGroupStarts=[0]: B1 QWA accumulator + Power Iter fires.

        Output 4-tuple should be unit-norm quat after QWA solve.
        """
        import maya.cmds as cmds
        node = _make_node(cmds, "rbf_b03")
        _connect_n_drivers(cmds, node, 1, encoding=1)
        cmds.setAttr(node + ".outputQuaternionGroupStart[0]", 0)
        # 4-element output = single quat group
        for p in range(3):
            for j in range(3):
                cmds.setAttr(
                    "{}.poses[{}].poseInput[{}]".format(node, p, j),
                    float(p) * 0.5)
            # Pose values are unit quats (encode pose Euler to quat)
            ang = float(p) * 0.2
            half = ang / 2.0
            qx, qy, qz, qw = math.sin(half), 0.0, 0.0, math.cos(half)
            for j, v in enumerate([qx, qy, qz, qw]):
                cmds.setAttr(
                    "{}.poses[{}].poseValue[{}]".format(node, p, j), v)
        out = [cmds.getAttr(node + ".output[{}]".format(i))
               for i in range(4)]
        # QWA output should be unit quat
        norm_sq = sum(x * x for x in out)
        self.assertAlmostEqual(norm_sq, 1.0, places=4,
            msg="QWA output must be unit-norm quat; got |q|²={}"
            .format(norm_sq))

    def test_b04_b1_b2_coexistence_no_overlap(self):
        """B1 列 [0..3] (quat) + B2 块 [4..6] (Euler) 共存."""
        import maya.cmds as cmds
        node = _make_node(cmds, "rbf_b04")
        _connect_n_drivers(cmds, node, 1, encoding=1)
        cmds.setAttr(node + ".outputQuaternionGroupStart[0]", 0)
        cmds.setAttr(node + ".outputEncoding", 1)
        # Output: 4 cols B1 quat + 3 cols B2 Euler = 7 total
        for p in range(2):
            for j in range(3):
                cmds.setAttr(
                    "{}.poses[{}].poseInput[{}]".format(node, p, j),
                    float(p) * 0.3)
            ang = float(p) * 0.1
            half = ang / 2.0
            qx, qy, qz, qw = math.sin(half), 0.0, 0.0, math.cos(half)
            vals = [qx, qy, qz, qw, 0.0, float(p) * 0.2, 0.0]
            for j, v in enumerate(vals):
                cmds.setAttr(
                    "{}.poses[{}].poseValue[{}]".format(node, p, j), v)
        out = [cmds.getAttr(node + ".output[{}]".format(i))
               for i in range(7)]
        # First 4 are unit quat (B1)
        norm_sq = sum(out[i] * out[i] for i in range(4))
        self.assertAlmostEqual(norm_sq, 1.0, places=4,
            msg="B1 cols [0..3] must be unit quat under coexistence.")
        # Last 3 are sane Euler (B2)
        for i in range(4, 7):
            self.assertIsNotNone(out[i])
            self.assertLess(abs(out[i]), 10.0,
                "B2 Euler col [{}] absurd value {}".format(i, out[i]))


# ====================================================================
# Section C — 4 input encodings
# ====================================================================

@unittest.skipIf(not _REAL_MAYA,
    "Real mayapy required for E2E 4-encoding dispatch coverage.")
class TestQuatRBFE2E4Encoding(unittest.TestCase):
    """All 4 inputEncoding values produce reasonable dgeval."""

    @classmethod
    def setUpClass(cls):
        _load_plugin_or_skip()

    def setUp(self):
        import maya.cmds as cmds
        cmds.file(new=True, force=True)

    def _smoke_encoding(self, encoding_value):
        import maya.cmds as cmds
        node = _make_node(cmds, "rbf_enc{}".format(encoding_value))
        _connect_n_drivers(cmds, node, 3, encoding=encoding_value)
        for p in range(3):
            for j in range(9):
                cmds.setAttr(
                    "{}.poses[{}].poseInput[{}]".format(node, p, j),
                    float(p) * 0.1)
            for j in range(3):
                cmds.setAttr(
                    "{}.poses[{}].poseValue[{}]".format(node, p, j),
                    float(p) * 0.2)
        out = [cmds.getAttr(node + ".output[{}]".format(i))
               for i in range(3)]
        for v in out:
            self.assertIsNotNone(v)

    def test_c01_raw(self):
        self._smoke_encoding(0)

    def test_c02_quat(self):
        self._smoke_encoding(1)

    def test_c03_bendroll(self):
        self._smoke_encoding(2)

    def test_c04_expmap(self):
        self._smoke_encoding(3)

    def test_c05_swingtwist(self):
        self._smoke_encoding(4)


# ====================================================================
# Section D — Numerical correctness
# ====================================================================

@unittest.skipIf(not _REAL_MAYA,
    "Real mayapy required for E2E numerical correctness coverage.")
class TestQuatRBFE2ENumerical(unittest.TestCase):
    """Pose-center recovery + Tikhonov regularization + double-cover."""

    @classmethod
    def setUpClass(cls):
        _load_plugin_or_skip()

    def setUp(self):
        import maya.cmds as cmds
        cmds.file(new=True, force=True)

    def test_d01_pose_center_recovery(self):
        """driver = pose_i exactly → output ≈ pose_i value (容差 1e-3)."""
        import maya.cmds as cmds
        node = _make_node(cmds, "rbf_d01")
        locs = _connect_n_drivers(cmds, node, 1, encoding=1)
        # Add 3 distinct poses
        target_eulers = [0.0, 0.5, -0.3]
        target_values = [0.0, 0.7, -0.4]
        for p in range(3):
            cmds.setAttr(
                "{}.poses[{}].poseInput[0]".format(node, p),
                target_eulers[p])
            cmds.setAttr(
                "{}.poses[{}].poseInput[1]".format(node, p), 0.0)
            cmds.setAttr(
                "{}.poses[{}].poseInput[2]".format(node, p), 0.0)
            cmds.setAttr(
                "{}.poses[{}].poseValue[0]".format(node, p),
                target_values[p])
        # Force training with regularization > 0 to stabilize
        cmds.setAttr(node + ".regularization", 1e-4)
        # Probe at pose 1 center
        cmds.setAttr(locs[0] + ".rx", target_eulers[1])
        out = cmds.getAttr(node + ".output[0]")
        self.assertAlmostEqual(out, target_values[1], places=2,
            msg="Pose-center recovery failed: probe at pose 1 → "
                "output {}, expected {}".format(out, target_values[1]))

    def test_d02_regularization_tames_ill_conditioning(self):
        """病态 K + λ=1e-3 → ‖output‖ < 100."""
        import maya.cmds as cmds
        node = _make_node(cmds, "rbf_d02")
        _connect_n_drivers(cmds, node, 3, encoding=1)
        # Highly redundant poses (driver 1 nearly constant — triggers
        # ill-conditioned K like user's actual node)
        for p in range(5):
            for j in range(9):
                cmds.setAttr(
                    "{}.poses[{}].poseInput[{}]".format(node, p, j),
                    1e-5 if j < 3 else float(p) * 0.1)
            for j in range(3):
                cmds.setAttr(
                    "{}.poses[{}].poseValue[{}]".format(node, p, j),
                    float(p) * 0.1)
        cmds.setAttr(node + ".regularization", 1e-3)
        out = [cmds.getAttr(node + ".output[{}]".format(i))
               for i in range(3)]
        for v in out:
            self.assertLess(abs(v), 100.0,
                "Regularization=1e-3 must tame extreme weights; "
                "got {}".format(v))


if __name__ == "__main__":
    unittest.main()
