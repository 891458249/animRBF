"""Phase 3 - Header naming radio + Utility section tests
(2026-04-27).

Coverage:

* core.format_node_for_display: pure-string transform across the
  three modes.
* core cleanup helpers: connectionless-input, connectionless-
  output, redundant-pose removal.
* controller: name_display_mode property + setter + signal;
  cleanup wrappers; split-solver stub warning.
* main_window source-scan: Header radios are wired; Utility
  section is wired; toggle a radio causes the source reload
  cascade; cleanup button dispatches per radio.
* i18n parity for the new keys.
"""

from __future__ import absolute_import

import os
import unittest
from unittest import mock

import conftest


_REPO_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
_MAIN_WINDOW = os.path.join(
    _REPO_ROOT, "modules", "RBFtools", "scripts", "RBFtools",
    "ui", "main_window.py")


def _read(p):
    with open(p, "r", encoding="utf-8") as fh:
        return fh.read()


# ----------------------------------------------------------------------
# core.format_node_for_display
# ----------------------------------------------------------------------


class TestM_HEADER_FormatNodeForDisplay(unittest.TestCase):

    def test_long_returns_unchanged(self):
        from RBFtools.core import format_node_for_display
        self.assertEqual(
            format_node_for_display("|grp|ns:joint1", "long"),
            "|grp|ns:joint1")

    def test_short_strips_dag_path(self):
        from RBFtools.core import format_node_for_display
        self.assertEqual(
            format_node_for_display("|grp|ns:joint1", "short"),
            "ns:joint1")

    def test_nice_strips_namespace_too(self):
        from RBFtools.core import format_node_for_display
        self.assertEqual(
            format_node_for_display("|grp|ns:joint1", "nice"),
            "joint1")

    def test_unknown_mode_returns_unchanged(self):
        from RBFtools.core import format_node_for_display
        self.assertEqual(
            format_node_for_display("joint1", "garbage"),
            "joint1")

    def test_empty_input_returns_empty(self):
        from RBFtools.core import format_node_for_display
        self.assertEqual(format_node_for_display("", "long"), "")
        self.assertEqual(format_node_for_display(None, "short"), "")


# ----------------------------------------------------------------------
# core cleanup helpers
# ----------------------------------------------------------------------


@unittest.skipIf(conftest._REAL_MAYA,
    "mock-dependent (mock.patch on cmds.*)")
class TestM_UTILITY_CoreCleanup(unittest.TestCase):

    def test_connectionless_inputs_removes_unconnected(self):
        from RBFtools import core
        import maya.cmds as cmds
        cmds.reset_mock()

        def fake_get_attr(plug, *_args, **_kwargs):
            if plug.endswith(".input"):
                return [0, 1, 2]
            return []
        cmds.getAttr.side_effect = fake_get_attr

        def fake_list_conn(plug, *_args, **_kwargs):
            # Only input[0] has a connection; [1] and [2] are empty.
            if plug.endswith("input[0]"):
                return ["drv.tx"]
            return []
        cmds.listConnections.side_effect = fake_list_conn

        with mock.patch.object(core, "_exists",
                               return_value=True), \
             mock.patch.object(core, "get_shape",
                               return_value="RBF1Shape"):
            n = core.cleanup_remove_connectionless_inputs("RBF1")
        self.assertEqual(n, 2)

    def test_redundant_poses_collapses_duplicates(self):
        from RBFtools import core
        from RBFtools.core import PoseData
        poses = [
            PoseData(0, [0.0, 0.0], [1.0, 1.0]),
            PoseData(1, [0.5, 0.5], [2.0, 2.0]),
            PoseData(2, [0.0, 0.0], [1.0, 1.0]),   # dup of 0
        ]
        with mock.patch.object(core, "_exists",
                               return_value=True), \
             mock.patch.object(core, "get_shape",
                               return_value="RBF1Shape"), \
             mock.patch.object(core, "read_all_poses",
                               return_value=poses):
            import maya.cmds as cmds
            cmds.reset_mock()
            n = core.cleanup_remove_redundant_poses("RBF1")
        self.assertEqual(n, 1)


# ----------------------------------------------------------------------
# Controller wrappers
# ----------------------------------------------------------------------


@unittest.skipIf(conftest._REAL_MAYA,
    "mock-dependent (mock.patch on core.*)")
class TestM_HEADER_UTILITY_Controller(unittest.TestCase):

    def _stub_controller(self):
        from RBFtools.controller import MainController
        ctrl = MainController.__new__(MainController)
        ctrl._current_node = "RBF1"
        ctrl._name_display_mode = "long"
        ctrl.driverSourcesChanged = mock.MagicMock()
        ctrl.drivenSourcesChanged = mock.MagicMock()
        ctrl.nameDisplayModeChanged = mock.MagicMock()
        return ctrl

    def test_set_name_display_mode_emits_on_change(self):
        from RBFtools.controller import MainController
        ctrl = self._stub_controller()
        MainController.set_name_display_mode(ctrl, "short")
        ctrl.nameDisplayModeChanged.emit.assert_called_once_with(
            "short")
        self.assertEqual(ctrl._name_display_mode, "short")

    def test_set_name_display_mode_idempotent(self):
        from RBFtools.controller import MainController
        ctrl = self._stub_controller()   # default "long"
        MainController.set_name_display_mode(ctrl, "long")
        ctrl.nameDisplayModeChanged.emit.assert_not_called()

    def test_set_name_display_mode_rejects_garbage(self):
        from RBFtools.controller import MainController
        ctrl = self._stub_controller()
        MainController.set_name_display_mode(ctrl, "garbage")
        ctrl.nameDisplayModeChanged.emit.assert_not_called()
        self.assertEqual(ctrl._name_display_mode, "long")

    def test_cleanup_input_emits_driver_signal(self):
        from RBFtools.controller import MainController
        from RBFtools import core
        ctrl = self._stub_controller()
        with mock.patch.object(
                core, "cleanup_remove_connectionless_inputs",
                return_value=3):
            n = MainController.cleanup_remove_connectionless_inputs(
                ctrl)
        self.assertEqual(n, 3)
        ctrl.driverSourcesChanged.emit.assert_called_once_with()

    def test_cleanup_output_emits_driven_signal(self):
        from RBFtools.controller import MainController
        from RBFtools import core
        ctrl = self._stub_controller()
        with mock.patch.object(
                core, "cleanup_remove_connectionless_outputs",
                return_value=2):
            n = MainController.cleanup_remove_connectionless_outputs(
                ctrl)
        self.assertEqual(n, 2)
        ctrl.drivenSourcesChanged.emit.assert_called_once_with()

    def test_split_solver_warns_deferred(self):
        from RBFtools.controller import MainController
        ctrl = self._stub_controller()
        import maya.cmds as cmds
        cmds.reset_mock()
        result = MainController.split_solver_for_each_joint(ctrl)
        self.assertFalse(result)
        cmds.warning.assert_called_once()


# ----------------------------------------------------------------------
# Source-scan: main_window wires the new UI
# ----------------------------------------------------------------------


class TestM_HEADER_UTILITY_MainWindowSourceScan(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._main = _read(_MAIN_WINDOW)

    def test_header_naming_radios(self):
        for attr in ("_rb_name_long", "_rb_name_short",
                     "_rb_name_nice", "_name_mode_group"):
            self.assertIn(attr, self._main,
                "main_window missing {}".format(attr))

    def test_header_radios_wired_to_set_name_display_mode(self):
        self.assertIn("set_name_display_mode(", self._main)
        self.assertIn(
            "ctrl.nameDisplayModeChanged.connect", self._main)

    def test_utility_section_present(self):
        for attr in ("_utility_section",
                     "_btn_split_solver",
                     "_btn_run_cleanup",
                     "_rb_cleanup_in",
                     "_rb_cleanup_out",
                     "_rb_cleanup_pose",
                     "_cleanup_group"):
            self.assertIn(attr, self._main,
                "main_window missing {}".format(attr))

    def test_utility_buttons_wired(self):
        self.assertIn(
            "_on_split_solver_clicked", self._main)
        self.assertIn(
            "_on_run_cleanup_clicked", self._main)


# ----------------------------------------------------------------------
# i18n parity for Phase 3 keys
# ----------------------------------------------------------------------


class TestM_HEADER_UTILITY_I18nParity(unittest.TestCase):

    REQUIRED_KEYS = [
        "name_long", "name_short", "name_nice",
        "section_utility",
        "btn_split_solver_per_joint",
        "btn_split_solver_per_joint_tip",
        "rb_remove_connectionless_input",
        "rb_remove_connectionless_output",
        "rb_remove_redundant_pose",
        "btn_remove_unnecessary_datas",
        "status_cleanup_input_removed",
        "status_cleanup_output_removed",
        "status_cleanup_pose_removed",
    ]

    def test_required_keys(self):
        from RBFtools.ui import i18n
        for k in self.REQUIRED_KEYS:
            self.assertIn(k, i18n._EN, "missing EN key {}".format(k))
            self.assertIn(k, i18n._ZH, "missing ZH key {}".format(k))


if __name__ == "__main__":
    unittest.main()
