# -*- coding: utf-8 -*-
"""Commit 3 (M_BASE_POSE + C2 semantic signals).

Coverage:

* Source-scan: BasePoseEditor present, PoseRowWidget gains is_base_pose,
  V2 signal forms wired through main_window, legacy poseValueChanged
  fully removed.
* Mock E2E: V2 slot maps (source_idx, attr_name) -> flat_idx correctly
  across multi-source layouts; BasePose dispatches to
  controller.set_base_pose_value rather than corrupting pose[0].
* Controller: set_pose_radius / set_base_pose_value / read_base_pose_values
  / recall_base_pose surfaces present; pose_model.update_pose_radius
  rounds out the per-pose σ live-edit path.
"""

from __future__ import absolute_import

import os
import unittest
from unittest import mock

import conftest


_REPO_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
_BASE_PY = os.path.join(
    _REPO_ROOT, "modules", "RBFtools", "scripts", "RBFtools",
    "ui", "widgets", "base_pose_editor.py")
_ROW_PY = os.path.join(
    _REPO_ROOT, "modules", "RBFtools", "scripts", "RBFtools",
    "ui", "widgets", "pose_row_widget.py")
_GRID_PY = os.path.join(
    _REPO_ROOT, "modules", "RBFtools", "scripts", "RBFtools",
    "ui", "widgets", "pose_grid_editor.py")
_MAIN_WINDOW = os.path.join(
    _REPO_ROOT, "modules", "RBFtools", "scripts", "RBFtools",
    "ui", "main_window.py")
_CONTROLLER = os.path.join(
    _REPO_ROOT, "modules", "RBFtools", "scripts", "RBFtools",
    "controller.py")
_POSE_MODEL = os.path.join(
    _REPO_ROOT, "modules", "RBFtools", "scripts", "RBFtools",
    "ui", "pose_model.py")


def _read(p):
    with open(p, "r", encoding="utf-8") as fh:
        return fh.read()


# ----------------------------------------------------------------------
# Source-scan
# ----------------------------------------------------------------------


class TestM_BASE_POSE_SourceScan(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._base = _read(_BASE_PY)
        cls._row  = _read(_ROW_PY)
        cls._grid = _read(_GRID_PY)
        cls._mw   = _read(_MAIN_WINDOW)
        cls._ctrl = _read(_CONTROLLER)
        cls._pmod = _read(_POSE_MODEL)

    def test_base_pose_editor_class(self):
        self.assertIn("class BasePoseEditor", self._base)
        self.assertIn("PoseHeaderWidget", self._base)
        self.assertIn("PoseRowWidget", self._base)
        self.assertIn("BASE_POSE_SENTINEL", self._base)
        self.assertIn("is_base_pose=True", self._base)

    def test_pose_row_is_base_pose_kwarg(self):
        self.assertIn("is_base_pose=False", self._row)
        self.assertIn("is_base_pose=True", self._base)
        self.assertIn("BASE_POSE_SENTINEL", self._row)

    def test_legacy_signal_fully_removed(self):
        # The 4-arg flat_attr_idx form is gone everywhere — no
        # surface left for stale connect()s to silently accept.
        self.assertNotIn(
            "poseValueChanged     = QtCore.Signal(int, str, int, float)",
            self._row)
        self.assertNotIn(
            "poseValueChanged     = QtCore.Signal(int, str, int, float)",
            self._grid)
        self.assertNotIn(
            "poseValueChanged     = QtCore.Signal(int, str, int, float)",
            self._mw)

    def test_v2_signal_chain(self):
        # PoseRowWidget -> PoseGridEditor -> _PoseEditorPanel ->
        # main_window slot. Every link MUST surface poseValueChangedV2.
        self.assertIn("poseValueChangedV2", self._row)
        self.assertIn("poseValueChangedV2", self._grid)
        self.assertIn("poseValueChangedV2", self._mw)
        self.assertIn("_on_pose_grid_value_changed_v2", self._mw)

    def test_radius_signal_chain(self):
        self.assertIn("poseRadiusChanged", self._row)
        self.assertIn("poseRadiusChanged", self._grid)
        self.assertIn("poseRadiusChanged", self._mw)
        self.assertIn("_on_pose_grid_radius_changed", self._mw)

    def test_basedrvpose_tab_inserted_between_drvdrv_and_pose(self):
        # User spec ordering: DriverDriven [0], BaseDrivenPose [1],
        # Pose [2]. Source-scan lock: BaseDrivenPose addTab must
        # appear AFTER tab_driver_driven and BEFORE tab_pose.
        i_drv = self._mw.find("tab_driver_driven")
        i_bdp = self._mw.find("tab_base_drv_pose")
        i_pose = self._mw.find("tab_pose")
        self.assertGreater(i_bdp, i_drv,
            "BaseDrivenPose tab must come after DriverDriven")
        self.assertGreater(i_pose, i_bdp,
            "Pose tab must come after BaseDrivenPose")

    def test_controller_per_pose_sigma_apis(self):
        for fn in ("def set_pose_radius",
                   "def set_base_pose_value",
                   "def read_base_pose_values",
                   "def recall_base_pose"):
            self.assertIn(fn, self._ctrl,
                "controller missing {}".format(fn))

    def test_controller_writes_pose_radius_plug(self):
        # set_pose_radius MUST close the loop with the C++ Commit 0
        # vectorised σ math by calling cmds.setAttr on the parallel
        # poseRadius[] multi-attr.
        self.assertIn(".poseRadius[", self._ctrl)
        self.assertIn("setAttr", self._ctrl)

    def test_pose_model_radius_setter(self):
        self.assertIn("def update_pose_radius", self._pmod)


# ----------------------------------------------------------------------
# Mock E2E — V2 slot flat_idx mapping
# ----------------------------------------------------------------------


@unittest.skipIf(conftest._REAL_MAYA,
    "mock-dependent (controller stubs)")
class TestM_BASE_POSE_FlatIdxMapping(unittest.TestCase):

    def _make_window(self):
        from RBFtools.ui.main_window import RBFToolsWindow
        win = RBFToolsWindow.__new__(RBFToolsWindow)
        win._ctrl = mock.MagicMock()
        return win

    def test_flat_attr_index_multi_source(self):
        # 2 driver sources: src0 has [tx, ty]; src1 has [rx, ry, rz].
        # (src=1, "rz") -> 2 + 2 = 4.
        from RBFtools.ui.main_window import RBFToolsWindow
        win = self._make_window()
        s0 = mock.MagicMock(); s0.attrs = ["tx", "ty"]
        s1 = mock.MagicMock(); s1.attrs = ["rx", "ry", "rz"]
        flat = RBFToolsWindow._flat_attr_index(win, [s0, s1], 1, "rz")
        self.assertEqual(flat, 4)

    def test_flat_attr_index_unknown_attr_returns_minus_one(self):
        from RBFtools.ui.main_window import RBFToolsWindow
        win = self._make_window()
        s0 = mock.MagicMock(); s0.attrs = ["tx", "ty"]
        flat = RBFToolsWindow._flat_attr_index(
            win, [s0], 0, "scale_evil_attr")
        self.assertEqual(flat, -1)

    def test_v2_pose_idx_minus_one_skipped_in_pose_slot(self):
        # BasePose sentinel must NEVER reach update_pose_values —
        # would corrupt pose[0]. Slot returns silently.
        from RBFtools.ui.main_window import RBFToolsWindow
        win = self._make_window()
        win._ctrl.read_driver_sources.return_value = []
        win._ctrl.read_driven_sources.return_value = []
        RBFToolsWindow._on_pose_grid_value_changed_v2(
            win, -1, "value", 0, "rx", 1.5)
        win._ctrl.pose_model.update_pose_values.assert_not_called()

    def test_base_pose_value_dispatches_to_controller(self):
        from RBFtools.ui.main_window import RBFToolsWindow
        win = self._make_window()
        s0 = mock.MagicMock(); s0.attrs = ["rx", "ry", "rz"]
        win._ctrl.read_driven_sources.return_value = [s0]
        RBFToolsWindow._on_base_pose_value_changed(
            win, -1, "value", 0, "ry", 0.75)
        win._ctrl.set_base_pose_value.assert_called_once_with(
            1, 0.75)

    def test_base_pose_driver_side_edits_filtered_out(self):
        # side == "input" on BasePose is meaningless (clusters are
        # disabled). Defensive guard ensures stale events don't fire.
        from RBFtools.ui.main_window import RBFToolsWindow
        win = self._make_window()
        RBFToolsWindow._on_base_pose_value_changed(
            win, -1, "input", 0, "tx", 1.0)
        win._ctrl.set_base_pose_value.assert_not_called()

    def test_radius_slot_routes_to_controller(self):
        from RBFtools.ui.main_window import RBFToolsWindow
        win = self._make_window()
        RBFToolsWindow._on_pose_grid_radius_changed(win, 2, 7.5)
        win._ctrl.set_pose_radius.assert_called_once_with(2, 7.5)


if __name__ == "__main__":
    unittest.main()
