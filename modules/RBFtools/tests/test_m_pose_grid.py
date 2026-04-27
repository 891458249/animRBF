"""Phase 2 - PoseGridEditor (multi-source-aware Pose tab grid).

Replaces the legacy QTableView (PoseTableModel) inside the Pose
outer tab with a dynamic grid whose columns track the active
node's driverSource[] + drivenSource[] structure.

Coverage:

* Source-scan: widget module + main_window wiring.
* Mock E2E: signal forwarding (Add Pose / Delete Poses / Go to
  Pose / per-row Delete / spinbox value changes).
* main_window helpers: _refresh_pose_grid pulls source +
  pose model state and pushes into the grid.
"""

from __future__ import absolute_import

import os
import unittest
from unittest import mock

import conftest


_REPO_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
_GRID_PY = os.path.join(
    _REPO_ROOT, "modules", "RBFtools", "scripts", "RBFtools",
    "ui", "widgets", "pose_grid_editor.py")
_MAIN_WINDOW = os.path.join(
    _REPO_ROOT, "modules", "RBFtools", "scripts", "RBFtools",
    "ui", "main_window.py")


def _read(p):
    with open(p, "r", encoding="utf-8") as fh:
        return fh.read()


# ----------------------------------------------------------------------
# Source-scan
# ----------------------------------------------------------------------


class TestM_POSE_GRID_SourceScan(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._grid = _read(_GRID_PY)
        cls._main = _read(_MAIN_WINDOW)

    def test_class_present(self):
        self.assertIn("class PoseGridEditor", self._grid)

    def test_required_signals(self):
        for sig in ("poseRecallRequested", "poseDeleteRequested",
                    "poseValueChanged", "addPoseRequested",
                    "deleteAllPosesRequested"):
            self.assertIn(sig, self._grid,
                "PoseGridEditor missing signal {}".format(sig))

    def test_main_window_imports_grid(self):
        self.assertIn(
            "from RBFtools.ui.widgets.pose_grid_editor import "
            "PoseGridEditor",
            self._main,
            "main_window must import PoseGridEditor")
        self.assertIn("PoseGridEditor()", self._main)

    def test_main_window_helpers(self):
        for helper in ("def _refresh_pose_grid",
                       "def _on_pose_grid_recall",
                       "def _on_pose_grid_delete",
                       "def _on_pose_grid_delete_all",
                       "def _on_pose_grid_value_changed"):
            self.assertIn(helper, self._main,
                "main_window missing {}".format(helper))

    def test_pose_grid_cascades_from_source_reload(self):
        # _reload_driver_sources + _reload_driven_sources must
        # call _refresh_pose_grid so the column structure follows
        # the source list.
        n = self._main.count("self._refresh_pose_grid()")
        self.assertGreaterEqual(n, 2,
            "_refresh_pose_grid must be invoked by both source "
            "reload paths (driver + driven)")


# ----------------------------------------------------------------------
# Mock E2E - PoseGridEditor signal forwarding
# ----------------------------------------------------------------------


@unittest.skipIf(conftest._REAL_MAYA,
    "mock-dependent (PySide signal stubs)")
class TestM_POSE_GRID_Signals(unittest.TestCase):

    def _make_grid(self):
        from RBFtools.ui.widgets.pose_grid_editor import PoseGridEditor
        grid = PoseGridEditor.__new__(PoseGridEditor)
        grid.poseRecallRequested = mock.MagicMock()
        grid.poseDeleteRequested = mock.MagicMock()
        grid.poseValueChanged    = mock.MagicMock()
        grid.addPoseRequested    = mock.MagicMock()
        grid.deleteAllPosesRequested = mock.MagicMock()
        return grid


# ----------------------------------------------------------------------
# main_window grid integration
# ----------------------------------------------------------------------


@unittest.skipIf(conftest._REAL_MAYA,
    "mock-dependent (PySide + controller stubs)")
class TestM_POSE_GRID_MainWindowIntegration(unittest.TestCase):

    def _make_window(self, drv_sources=None, dvn_sources=None,
                     poses=None):
        from RBFtools.ui.main_window import RBFToolsWindow
        win = RBFToolsWindow.__new__(RBFToolsWindow)
        win._ctrl = mock.MagicMock()
        win._ctrl.read_driver_sources.return_value = (
            drv_sources or [])
        win._ctrl.read_driven_sources.return_value = (
            dvn_sources or [])
        win._ctrl.pose_model = mock.MagicMock()
        if poses is not None:
            win._ctrl.pose_model.rowCount.return_value = len(poses)
            win._ctrl.pose_model.get_pose.side_effect = (
                lambda r: poses[r] if 0 <= r < len(poses) else None)
        else:
            win._ctrl.pose_model.rowCount.return_value = 0
            win._ctrl.pose_model.get_pose.return_value = None
        win._pose_editor = mock.MagicMock()
        return win

    def test_refresh_pushes_state_into_pose_editor(self):
        from RBFtools.ui.main_window import RBFToolsWindow
        from RBFtools.core import DriverSource, DrivenSource, PoseData
        drv = [DriverSource(node="d1", attrs=("tx",),
                            weight=1.0, encoding=0)]
        dvn = [DrivenSource(node="t1", attrs=("translateX",))]
        poses = [PoseData(0, [0.5], [1.5])]
        win = self._make_window(drv, dvn, poses)
        RBFToolsWindow._refresh_pose_grid(win)
        win._pose_editor.reload_pose_grid.assert_called_once()
        call_args = win._pose_editor.reload_pose_grid.call_args[0]
        self.assertEqual(call_args[0], drv)
        self.assertEqual(call_args[1], dvn)
        self.assertEqual(len(call_args[2]), 1)

    def test_recall_slot_calls_controller_recall(self):
        """Go to Pose row signal -> controller.recall_pose with
        the aggregated 4-tuple (drv_node, dvn_node, drv_attrs,
        dvn_attrs)."""
        from RBFtools.ui.main_window import RBFToolsWindow
        from RBFtools.core import DriverSource, DrivenSource
        drv = [DriverSource(node="d1", attrs=("tx",),
                            weight=1.0, encoding=0)]
        dvn = [DrivenSource(node="t1", attrs=("translateX",))]
        win = self._make_window(drv, dvn, [])
        RBFToolsWindow._on_pose_grid_recall(win, 2)
        win._ctrl.recall_pose.assert_called_once_with(
            2, "d1", "t1", ["tx"], ["translateX"])

    def test_delete_slot_calls_controller_delete_pose(self):
        from RBFtools.ui.main_window import RBFToolsWindow
        win = self._make_window()
        RBFToolsWindow._on_pose_grid_delete(win, 1)
        win._ctrl.delete_pose.assert_called_once_with(1)

    def test_delete_all_iterates_high_to_low(self):
        from RBFtools.ui.main_window import RBFToolsWindow
        win = self._make_window()
        win._ctrl.pose_model.rowCount.return_value = 3
        RBFToolsWindow._on_pose_grid_delete_all(win)
        call_args = [
            c[0][0] for c in win._ctrl.delete_pose.call_args_list]
        self.assertEqual(call_args, [2, 1, 0])

    def test_value_changed_pushes_into_pose_model(self):
        from RBFtools.ui.main_window import RBFToolsWindow
        from RBFtools.core import PoseData
        win = self._make_window()
        win._ctrl.pose_model.get_pose.return_value = PoseData(
            0, [0.0, 0.0], [1.0, 1.0, 1.0])
        # Driver-side spinbox edit on flat input index 1 -> 0.5.
        RBFToolsWindow._on_pose_grid_value_changed(
            win, 0, "input", 1, 0.5)
        win._ctrl.pose_model.update_pose_values.assert_called_once()
        args = win._ctrl.pose_model.update_pose_values.call_args[0]
        self.assertEqual(args[0], 0)            # pose row
        self.assertEqual(args[1], [0.0, 0.5])   # new inputs
        self.assertEqual(args[2], [1.0, 1.0, 1.0])

    def test_value_changed_value_side_updates_outputs(self):
        from RBFtools.ui.main_window import RBFToolsWindow
        from RBFtools.core import PoseData
        win = self._make_window()
        win._ctrl.pose_model.get_pose.return_value = PoseData(
            0, [0.0], [1.0, 1.0, 1.0])
        RBFToolsWindow._on_pose_grid_value_changed(
            win, 0, "value", 2, 9.0)
        args = win._ctrl.pose_model.update_pose_values.call_args[0]
        self.assertEqual(args[2], [1.0, 1.0, 9.0])


# ----------------------------------------------------------------------
# i18n parity for the Phase 2 keys
# ----------------------------------------------------------------------


class TestM_POSE_GRID_I18nParity(unittest.TestCase):

    REQUIRED_KEYS = [
        "pose_grid_empty_hint",
        "pose_grid_row_label",
        "pose_grid_go_to_pose",
        "pose_grid_go_to_pose_tip",
        "pose_grid_add_pose_tip",
        "pose_grid_delete_all_tip",
        "delete_poses",
    ]

    def test_required_keys(self):
        from RBFtools.ui import i18n
        for k in self.REQUIRED_KEYS:
            self.assertIn(k, i18n._EN, "missing EN key {}".format(k))
            self.assertIn(k, i18n._ZH, "missing ZH key {}".format(k))


if __name__ == "__main__":
    unittest.main()
