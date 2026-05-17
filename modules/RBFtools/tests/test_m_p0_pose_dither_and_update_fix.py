# -*- coding: utf-8 -*-
"""M_P0_POSE_DITHER_AND_UPDATE_FIX (2026-05-12) -- Phase 14 pose
dither + global radius + Update button fix tests.

Ten unit cases per brief sec.6:
  Dither cases (Part A+B):
    1. test_dither_driver_simple
    2. test_dither_driver_seed_reproducible
    3. test_dither_driven_simple
    4. test_dither_no_cluster_returns_zero
    5. test_dither_pose0_untouched

  Update button (Part C):
    6. test_update_pose_writes_plug
    7. test_update_pose_triggers_grid_signal

  Global radius (Part C-bis):
    8. test_set_all_poses_radius_writes_all_plugs
    9. test_set_all_poses_radius_returns_count
   10. test_set_all_poses_radius_negative_clamps_to_default

The tests run under the pure-Python conftest (mocked maya.cmds).
"""

from __future__ import absolute_import

import io
import os
import sys
import unittest
from unittest import mock

# Allow `import conftest` at sweep root.
_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
if _TESTS_DIR not in sys.path:
    sys.path.insert(0, _TESTS_DIR)

import conftest  # noqa: E402


_REPO_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
_CORE_PY = os.path.join(
    _REPO_ROOT, "modules", "RBFtools", "scripts", "RBFtools",
    "core.py")
_CTRL_PY = os.path.join(
    _REPO_ROOT, "modules", "RBFtools", "scripts", "RBFtools",
    "controller.py")
_MAIN_PY = os.path.join(
    _REPO_ROOT, "modules", "RBFtools", "scripts", "RBFtools",
    "ui", "main_window.py")


def _read(path):
    with io.open(path, "r", encoding="utf-8") as fh:
        return fh.read()


# ----------------------------------------------------------------------
# Shared cmds fake -- in-memory plug store backing the mocked cmds.
# ----------------------------------------------------------------------


class _FakePlugStore(object):
    """Tiny in-memory replacement for the Maya plug store. Tracks
    multi-instance arrays (e.g. shape.poses[0].poseInput[0]) and
    served via the mocked cmds.setAttr / getAttr / listConnections."""

    def __init__(self):
        self.plugs = {}        # "shape.poses[0].poseInput[0]" -> 1.23
        self.multi_index = {}  # "shape.poses" -> [0, 1, 2]
        # Pre-populated connections per dst plug (incoming source).
        self.connections = {}  # dst -> [src,...]
        # Track disconnect calls for assertion.
        self.disconnects = []

    def set(self, plug, value):
        self.plugs[plug] = float(value)

    def get(self, plug):
        return self.plugs.get(plug, 0.0)


def _install_cmds_for_dither(store):
    """Patch maya.cmds with the closures backed by *store*."""
    import maya.cmds as cmds

    def _setAttr(plug, *args, **kwargs):
        # Accept core's "{plug}", value signature (single positional).
        if args:
            store.set(plug, args[0])

    def _getAttr(plug, **kwargs):
        if kwargs.get("multiIndices"):
            return list(store.multi_index.get(plug, []))
        return store.get(plug)

    def _listConnections(plug, **kwargs):
        return list(store.connections.get(plug, []))

    def _disconnectAttr(src, dst):
        store.disconnects.append((src, dst))

    # Reset the MagicMock's side_effects to our closures.
    cmds.setAttr.side_effect = _setAttr
    cmds.setAttr.reset_mock()
    cmds.getAttr.side_effect = _getAttr
    cmds.getAttr.reset_mock()
    cmds.listConnections.side_effect = _listConnections
    cmds.listConnections.reset_mock()
    cmds.disconnectAttr.side_effect = _disconnectAttr
    cmds.disconnectAttr.reset_mock()


# ----------------------------------------------------------------------
# Source introspection guards
# ----------------------------------------------------------------------


class T_M_P0_POSE_DITHER_AND_UPDATE_FIX_Source(unittest.TestCase):
    """Quick structural guards on top of the runtime tests below --
    catches accidental signature drift on a re-edit."""

    @classmethod
    def setUpClass(cls):
        cls._core = _read(_CORE_PY)
        cls._ctrl = _read(_CTRL_PY)
        cls._main = _read(_MAIN_PY)

    def test_PERMANENT_dither_helpers_present(self):
        self.assertIn("def dither_driver_poses(node, base_pose_index=0",
                      self._core)
        self.assertIn("def dither_driven_poses(node, base_pose_index=0",
                      self._core)
        self.assertIn("def set_all_poses_radius(node, radius):",
                      self._core)
        self.assertIn(
            "def write_pose_inputs_to_node(shape, sequential_idx, "
            "inputs):", self._core)
        self.assertIn(
            "def write_pose_values_to_node(shape, sequential_idx, "
            "values):", self._core)

    def test_PERMANENT_update_pose_writes_plugs(self):
        self.assertIn(
            "core.write_pose_inputs_to_node(", self._ctrl,
            "controller.update_pose MUST call "
            "core.write_pose_inputs_to_node to push captured values "
            "into Maya plugs (Part C plug-write fix)")
        self.assertIn(
            "core.write_pose_values_to_node(", self._ctrl,
            "controller.update_pose MUST also call "
            "core.write_pose_values_to_node for the driven side")

    def test_PERMANENT_on_pose_grid_update_refreshes(self):
        # Locate the slot body via simple substring scope -- both
        # _refresh_pose_grid() and the M_P0_POSE_DITHER marker MUST
        # appear in close proximity.
        idx = self._main.find("def _on_pose_grid_update(self, pose_index):")
        self.assertGreater(idx, 0,
            "_on_pose_grid_update must exist in main_window")
        # Slice until the next "def " in the same class.
        end = self._main.find("\n    def ", idx + 1)
        body = self._main[idx:end if end > 0 else len(self._main)]
        self.assertIn(
            "self._refresh_pose_grid()", body,
            "Part C UI fix: _on_pose_grid_update MUST call "
            "self._refresh_pose_grid() after ctrl.update_pose")


# ----------------------------------------------------------------------
# Runtime tests -- dither_driver_poses
# ----------------------------------------------------------------------


@unittest.skipIf(conftest._REAL_MAYA,
    "mock-dependent (cmds + core helpers stubbed)")
class TestDitherDriver(unittest.TestCase):
    """Cases 1, 2, 4, 5, 7 (dither_driver_poses)."""

    def _make_node(self, pose_inputs):
        """*pose_inputs* is dict {pose_idx: [(slot, value), ...]}."""
        store = _FakePlugStore()
        SHAPE = "rbfShape"
        store.multi_index[SHAPE + ".poses"] = sorted(pose_inputs.keys())
        for p, row in pose_inputs.items():
            store.multi_index[
                "{}.poses[{}].poseInput".format(SHAPE, p)] = [
                    slot for slot, _v in row]
            for slot, val in row:
                store.set(
                    "{}.poses[{}].poseInput[{}]".format(SHAPE, p, slot),
                    val)
        return store, SHAPE

    def _patched(self, store, shape):
        from RBFtools import core
        patches = [
            mock.patch.object(core, "_exists", return_value=True),
            mock.patch.object(core, "get_shape", return_value=shape),
            mock.patch.object(core, "undo_chunk",
                              return_value=_dummy_ctx()),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        _install_cmds_for_dither(store)

    def test_dither_driver_simple(self):
        """Case 1: pose 1 and pose 2 share value 0.3 on slot 0.
        Dither perturbs both within +/-magnitude, leaves pose 0 alone."""
        from RBFtools import core
        pose_inputs = {
            0: [(0, 0.0)],          # base pose
            1: [(0, 0.3)],          # cluster with pose 2
            2: [(0, 0.3)],          # cluster with pose 1
        }
        store, shape = self._make_node(pose_inputs)
        self._patched(store, shape)
        n = core.dither_driver_poses(
            "rbfNode", base_pose_index=0,
            magnitude=0.005, seed=42)
        self.assertEqual(n, 2,
            "Both pose 1 + pose 2 slot 0 should be perturbed")
        v1 = store.get(shape + ".poses[1].poseInput[0]")
        v2 = store.get(shape + ".poses[2].poseInput[0]")
        self.assertNotEqual(v1, 0.3,
            "Pose 1 slot 0 must be perturbed (was 0.3)")
        self.assertNotEqual(v2, 0.3,
            "Pose 2 slot 0 must be perturbed (was 0.3)")
        self.assertLessEqual(abs(v1 - 0.3), 0.005 + 1e-9,
            "Perturbation must stay within +/-magnitude")
        self.assertLessEqual(abs(v2 - 0.3), 0.005 + 1e-9,
            "Perturbation must stay within +/-magnitude")
        # Pose 0 untouched.
        self.assertEqual(store.get(shape + ".poses[0].poseInput[0]"),
                          0.0)

    def test_dither_driver_seed_reproducible(self):
        """Case 2: same seed produces identical perturbations."""
        from RBFtools import core
        pose_inputs = {
            0: [(0, 0.0)],
            1: [(0, 0.7), (1, 0.5)],
            2: [(0, 0.7), (1, 0.5)],
        }

        store_a, shape = self._make_node(pose_inputs)
        self._patched(store_a, shape)
        n_a = core.dither_driver_poses(
            "rbfNode", base_pose_index=0, magnitude=0.005, seed=99)
        captured_a = {
            k: v for k, v in store_a.plugs.items()
            if "poseInput" in k
        }

        # Re-mock for the second pass so the patches stack cleanly.
        store_b, shape = self._make_node(pose_inputs)
        _install_cmds_for_dither(store_b)
        n_b = core.dither_driver_poses(
            "rbfNode", base_pose_index=0, magnitude=0.005, seed=99)
        captured_b = {
            k: v for k, v in store_b.plugs.items()
            if "poseInput" in k
        }
        self.assertEqual(n_a, n_b)
        self.assertEqual(captured_a, captured_b,
            "Same seed must produce identical perturbations")

    def test_dither_no_cluster_returns_zero(self):
        """Case 4: all unique values -> no perturbation."""
        from RBFtools import core
        pose_inputs = {
            0: [(0, 0.0)],
            1: [(0, 0.1)],
            2: [(0, 0.7)],
        }
        store, shape = self._make_node(pose_inputs)
        self._patched(store, shape)
        n = core.dither_driver_poses(
            "rbfNode", base_pose_index=0, magnitude=0.005, seed=42)
        self.assertEqual(n, 0,
            "No clusters -> dither must report 0 perturbations")
        # And the values are unchanged.
        self.assertEqual(store.get(shape + ".poses[1].poseInput[0]"),
                          0.1)
        self.assertEqual(store.get(shape + ".poses[2].poseInput[0]"),
                          0.7)

    def test_dither_pose0_untouched(self):
        """Case 7: base pose is NEVER perturbed even if it shares a
        cluster value with another pose."""
        from RBFtools import core
        pose_inputs = {
            0: [(0, 0.3)],          # base pose, would otherwise cluster
            1: [(0, 0.3)],          # cluster with pose 2
            2: [(0, 0.3)],          # cluster with pose 1
        }
        store, shape = self._make_node(pose_inputs)
        self._patched(store, shape)
        core.dither_driver_poses(
            "rbfNode", base_pose_index=0, magnitude=0.005, seed=42)
        self.assertEqual(store.get(shape + ".poses[0].poseInput[0]"),
                          0.3,
            "Base pose (index 0) MUST NOT be perturbed.")


# ----------------------------------------------------------------------
# Runtime tests -- dither_driven_poses (Case 3)
# ----------------------------------------------------------------------


@unittest.skipIf(conftest._REAL_MAYA,
    "mock-dependent (cmds + core helpers stubbed)")
class TestDitherDriven(unittest.TestCase):

    def test_dither_driven_simple(self):
        """Case 3: driven-side cluster on poseValue[0] is perturbed."""
        from RBFtools import core
        SHAPE = "rbfShape"
        store = _FakePlugStore()
        store.multi_index[SHAPE + ".poses"] = [0, 1, 2]
        for p in (0, 1, 2):
            store.multi_index[
                "{}.poses[{}].poseValue".format(SHAPE, p)] = [0]
        store.set(SHAPE + ".poses[0].poseValue[0]", 0.0)
        store.set(SHAPE + ".poses[1].poseValue[0]", 0.5)
        store.set(SHAPE + ".poses[2].poseValue[0]", 0.5)

        patches = [
            mock.patch.object(core, "_exists", return_value=True),
            mock.patch.object(core, "get_shape", return_value=SHAPE),
            mock.patch.object(core, "undo_chunk",
                              return_value=_dummy_ctx()),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        _install_cmds_for_dither(store)

        n = core.dither_driven_poses(
            "rbfNode", base_pose_index=0,
            magnitude=0.005, seed=42)
        self.assertEqual(n, 2)
        # Base pose untouched.
        self.assertEqual(store.get(SHAPE + ".poses[0].poseValue[0]"),
                          0.0)
        # Both cluster poses perturbed within magnitude.
        for p in (1, 2):
            v = store.get(SHAPE + ".poses[{}].poseValue[0]".format(p))
            self.assertNotEqual(v, 0.5)
            self.assertLessEqual(abs(v - 0.5), 0.005 + 1e-9)


# ----------------------------------------------------------------------
# Runtime tests -- update_pose plug write (Cases 5, 6)
# ----------------------------------------------------------------------


@unittest.skipIf(conftest._REAL_MAYA,
    "mock-dependent (cmds + core helpers stubbed)")
class TestUpdatePosePlugWrite(unittest.TestCase):

    def _make_controller(self):
        from RBFtools.controller import MainController
        ctrl = MainController.__new__(MainController)
        ctrl._current_node = "rbfNode"
        ctrl._auto_fill = False
        ctrl._pose_model = mock.MagicMock()
        ctrl._pose_model.rowCount.return_value = 0
        return ctrl

    def test_update_pose_writes_plug(self):
        """Case 5: controller.update_pose pushes captured inputs/
        outputs into the Maya plug store via the new core helpers.
        """
        from RBFtools import core
        from RBFtools.controller import MainController
        SHAPE = "rbfShape"
        store = _FakePlugStore()

        with mock.patch.object(core, "get_shape", return_value=SHAPE):
            import maya.cmds as cmds
            cmds.objExists.return_value = True

            # Capture helpers feed deterministic input/output vectors.
            ctrl = self._make_controller()
            ctrl._capture_multi_inputs = mock.MagicMock(
                return_value=[1.1, 2.2, 3.3])
            ctrl._capture_multi_outputs = mock.MagicMock(
                return_value=[7.7, 8.8])

            # cmds.setAttr writes go into the store.
            _install_cmds_for_dither(store)

            MainController.update_pose(
                ctrl, 4, "driverBone", "drivenBone",
                ["rx", "ry", "rz"], ["tx", "ty"])

        # Verify every input + value slot landed.
        self.assertEqual(
            store.get(SHAPE + ".poses[4].poseInput[0]"), 1.1)
        self.assertEqual(
            store.get(SHAPE + ".poses[4].poseInput[1]"), 2.2)
        self.assertEqual(
            store.get(SHAPE + ".poses[4].poseInput[2]"), 3.3)
        self.assertEqual(
            store.get(SHAPE + ".poses[4].poseValue[0]"), 7.7)
        self.assertEqual(
            store.get(SHAPE + ".poses[4].poseValue[1]"), 8.8)

    def test_update_pose_triggers_grid_signal(self):
        """Case 6: pose_model.update_pose_values is invoked exactly
        once with the captured vectors, so the model emits its
        dataChanged signal for the downstream grid refresh."""
        from RBFtools import core
        from RBFtools.controller import MainController
        SHAPE = "rbfShape"

        with mock.patch.object(core, "get_shape", return_value=SHAPE):
            import maya.cmds as cmds
            cmds.objExists.return_value = True
            ctrl = self._make_controller()
            ctrl._capture_multi_inputs = mock.MagicMock(
                return_value=[0.5])
            ctrl._capture_multi_outputs = mock.MagicMock(
                return_value=[0.9])
            store = _FakePlugStore()
            _install_cmds_for_dither(store)
            MainController.update_pose(
                ctrl, 2, "driverBone", "drivenBone",
                ["rx"], ["ty"])
            ctrl._pose_model.update_pose_values.assert_called_once_with(
                2, [0.5], [0.9])


# ----------------------------------------------------------------------
# Runtime tests -- set_all_poses_radius (Cases 8, 9, 10)
# ----------------------------------------------------------------------


@unittest.skipIf(conftest._REAL_MAYA,
    "mock-dependent (cmds + core helpers stubbed)")
class TestSetAllPosesRadius(unittest.TestCase):

    def _patched(self, store, shape):
        from RBFtools import core
        patches = [
            mock.patch.object(core, "_exists", return_value=True),
            mock.patch.object(core, "get_shape", return_value=shape),
            mock.patch.object(core, "undo_chunk",
                              return_value=_dummy_ctx()),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        _install_cmds_for_dither(store)

    def test_set_all_poses_radius_writes_all_plugs(self):
        """Case 8: every pose subscript gets the new radius written."""
        from RBFtools import core
        SHAPE = "rbfShape"
        store = _FakePlugStore()
        store.multi_index[SHAPE + ".poses"] = [0, 1, 2, 3, 4]
        self._patched(store, SHAPE)
        core.set_all_poses_radius("rbfNode", 8.5)
        for p in (0, 1, 2, 3, 4):
            self.assertEqual(
                store.get("{}.poseRadius[{}]".format(SHAPE, p)),
                8.5)

    def test_set_all_poses_radius_returns_count(self):
        """Case 9: return value equals the number of plugs written."""
        from RBFtools import core
        SHAPE = "rbfShape"
        store = _FakePlugStore()
        store.multi_index[SHAPE + ".poses"] = [0, 1, 2]
        self._patched(store, SHAPE)
        n = core.set_all_poses_radius("rbfNode", 3.0)
        self.assertEqual(n, 3)

    def test_set_all_poses_radius_negative_clamps_to_default(self):
        """Case 10: radius <= 0 falls back to DEFAULT_POSE_RADIUS so
        the kernel sigma stays valid."""
        from RBFtools import core
        SHAPE = "rbfShape"
        store = _FakePlugStore()
        store.multi_index[SHAPE + ".poses"] = [0, 1]
        self._patched(store, SHAPE)
        core.set_all_poses_radius("rbfNode", -1.0)
        for p in (0, 1):
            self.assertEqual(
                store.get("{}.poseRadius[{}]".format(SHAPE, p)),
                core.DEFAULT_POSE_RADIUS)


# ----------------------------------------------------------------------
# Helper: dummy context manager so `with undo_chunk(...)` no-ops.
# ----------------------------------------------------------------------


class _dummy_ctx(object):
    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


if __name__ == "__main__":
    unittest.main()
