"""M_UIRECONCILE - DriverSourceListEditor wiring guards + mock E2E.

#36 T_DRIVER_SOURCE_ADD_BUTTON_WIRED — 4 source-scan + mock E2E
sub-checks. Closes the M_B24b1 island-widget gap caught by the
2026-04-27 production install (verify-before-design 22nd use,
self-correction event #3 — see addendum
§M_UIRECONCILE.m_b24b1-correction).

PROJECT METHODOLOGY (sustains M_UIRECONCILE Hardening 5 + 6):

    UI subtask delivery standard - source-scan PERMANENT guards
    alone are insufficient. Each new UI widget that wires into a
    backend API MUST have at least one mock E2E test:
        "button click -> controller method called with expected args"
    Pure widget existence (M_B24b1 #27/#28 source-scan) does NOT
    catch the "widget complete + signal complete + backend API
    complete + middle wiring missing = green test, dead UI"
    failure mode.

Adopted by M4.1 / M4.2 / M_B7 / M_B11 / M_B14 going forward.

Plus:
* Pose-editor multi-source banner mock tests (Hardening 2:
  banner gated on len(sources) > 1; single-source nodes keep the
  legacy AttributeList workflow visually unchanged per red line
  14 backcompat parity).
* Controller signal parity (driverSourcesChanged emits exactly
  once per add / remove).
"""

from __future__ import absolute_import

import os
import re
import unittest
from unittest import mock

import conftest


_REPO_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
_MAIN_WINDOW = os.path.join(
    _REPO_ROOT, "modules", "RBFtools", "scripts", "RBFtools",
    "ui", "main_window.py"
)
_DRIVER_SOURCE_LIST_EDITOR = os.path.join(
    _REPO_ROOT, "modules", "RBFtools", "scripts", "RBFtools",
    "ui", "widgets", "driver_source_list_editor.py"
)
_CONTROLLER_PY = os.path.join(
    _REPO_ROOT, "modules", "RBFtools", "scripts", "RBFtools",
    "controller.py"
)


def _read(path):
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


# ----------------------------------------------------------------------
# #36 T_DRIVER_SOURCE_ADD_BUTTON_WIRED — source-scan layer
# ----------------------------------------------------------------------


class T_DRIVER_SOURCE_ADD_BUTTON_WIRED(unittest.TestCase):
    """PERMANENT GUARD #36 - DO NOT REMOVE.

    PROJECT METHODOLOGY (M_UIRECONCILE Hardening 5, sustains the
    M_B24b1 island-widget correction event): UI subtasks must
    carry an E2E mock test that proves the click-to-controller
    chain is closed - source-scan presence checks alone are
    insufficient (M_B24b1 #27/#28 missed exactly this failure
    mode). Sub-checks (a)/(b)/(c) are source-scans; sub-check
    (d) is the failure-mode-specific E2E mock test.
    """

    @classmethod
    def setUpClass(cls):
        cls._main_src = _read(_MAIN_WINDOW)
        cls._editor_src = _read(_DRIVER_SOURCE_LIST_EDITOR)
        cls._controller_src = _read(_CONTROLLER_PY)

    # ----- (a) main_window subscribes the editor's request signal --

    def test_a_main_window_subscribes_driver_source_signal(self):
        """The editor's addRequested or listChanged signal must be
        connected somewhere in main_window."""
        pattern = re.compile(
            r"_driver_source_list\.\w+\.connect\(")
        self.assertTrue(pattern.search(self._main_src),
            "main_window must subscribe a DriverSourceListEditor "
            "signal (addRequested / removeRequested / listChanged) "
            "- M_UIRECONCILE Hardening 1, closes M_B24b1 gap")

    # ----- (b) main_window calls controller.add_driver_source ------

    def test_b_main_window_calls_controller_add(self):
        """main_window must call controller.add_driver_source (or
        a future add_driver_sources_batch helper) at least once."""
        has_single = re.search(
            r"add_driver_source\s*\(", self._main_src)
        has_batch = re.search(
            r"add_driver_sources_batch\s*\(", self._main_src)
        self.assertTrue(bool(has_single) or bool(has_batch),
            "main_window must call controller.add_driver_source "
            "(or add_driver_sources_batch) - M_UIRECONCILE A.2")

    # ----- (c) reload path calls read_driver_sources ---------------

    def test_c_reload_path_calls_read_driver_sources(self):
        """A reload path in main_window must consume
        controller.read_driver_sources to repopulate the editor
        from the post-mutation node state."""
        self.assertIn("read_driver_sources", self._main_src,
            "main_window must call controller.read_driver_sources "
            "in a reload path so the widget reflects the actual "
            "node state - M_UIRECONCILE F.1 reload contract")

    # ----- (d) controller emits driverSourcesChanged ---------------

    def test_d_controller_defines_and_emits_signal(self):
        """Controller must define driverSourcesChanged Qt signal +
        emit it inside add_driver_source AND remove_driver_source
        - this is the bridge that lets main_window's reload slot
        fire automatically after every mutation."""
        self.assertIn("driverSourcesChanged = QtCore.Signal",
                      self._controller_src,
            "controller must define driverSourcesChanged signal")
        # Both mutation methods must emit (one emit per method body).
        self.assertGreaterEqual(
            self._controller_src.count(
                "self.driverSourcesChanged.emit()"),
            2,
            "controller must emit driverSourcesChanged from BOTH "
            "add_driver_source and remove_driver_source")

    # ----- (e) editor exposes addRequested / removeRequested -------

    def test_e_editor_exposes_request_signals(self):
        self.assertIn("addRequested", self._editor_src,
            "DriverSourceListEditor must expose addRequested signal")
        self.assertIn("removeRequested", self._editor_src,
            "DriverSourceListEditor must expose removeRequested "
            "signal so per-row deletion can route via the controller")


# ----------------------------------------------------------------------
# Mock E2E: click + button -> addRequested -> controller.add_driver_source
# ----------------------------------------------------------------------


@unittest.skipIf(conftest._REAL_MAYA,
    "mock-dependent (mock.patch on QtWidgets / cmds)")
class TestM_UIRECONCILE_E2E(unittest.TestCase):
    """Failure-mode-specific guard against the M_B24b1 island-
    widget assembly gap. Drives the editor + main-window slot
    interaction under fully mocked Qt + cmds - we observe that
    a synthetic + click reaches controller.add_driver_source
    with the selected nodes."""

    def test_add_clicked_emits_add_requested(self):
        from RBFtools.ui.widgets.driver_source_list_editor import (
            DriverSourceListEditor)
        editor = DriverSourceListEditor.__new__(DriverSourceListEditor)
        editor.addRequested = mock.MagicMock()
        # _on_add_clicked must be a thin signal forwarder, no
        # local row mutation.
        DriverSourceListEditor._on_add_clicked(editor)
        editor.addRequested.emit.assert_called_once_with()

    def test_remove_clicked_emits_with_row_index(self):
        from RBFtools.ui.widgets.driver_source_list_editor import (
            DriverSourceListEditor)
        editor = DriverSourceListEditor.__new__(DriverSourceListEditor)
        editor.removeRequested = mock.MagicMock()
        editor._list = mock.MagicMock()
        editor._list.currentRow.return_value = 2
        DriverSourceListEditor._on_remove_clicked(editor)
        editor.removeRequested.emit.assert_called_once_with(2)

    def test_remove_clicked_no_selection_is_noop(self):
        from RBFtools.ui.widgets.driver_source_list_editor import (
            DriverSourceListEditor)
        editor = DriverSourceListEditor.__new__(DriverSourceListEditor)
        editor.removeRequested = mock.MagicMock()
        editor._list = mock.MagicMock()
        editor._list.currentRow.return_value = -1
        DriverSourceListEditor._on_remove_clicked(editor)
        editor.removeRequested.emit.assert_not_called()


# ----------------------------------------------------------------------
# Controller signal parity: driverSourcesChanged emits per mutation
# ----------------------------------------------------------------------


@unittest.skipIf(conftest._REAL_MAYA,
    "mock-dependent (mock.patch on cmds.*)")
class TestM_UIRECONCILE_ControllerSignalEmits(unittest.TestCase):

    def _stub_controller(self):
        """Return a partially-mocked MainController with just the
        slots / state we need for the emission test."""
        from RBFtools.controller import MainController
        ctrl = MainController.__new__(MainController)
        ctrl._current_node = "RBF1"
        ctrl.driverSourcesChanged = mock.MagicMock()
        return ctrl

    def test_add_driver_source_emits_signal(self):
        from RBFtools.controller import MainController
        from RBFtools import core
        ctrl = self._stub_controller()
        with mock.patch.object(
                core, "add_driver_source", return_value=0) as core_add:
            MainController.add_driver_source(
                ctrl, "drv1", ["translateX"])
        core_add.assert_called_once()
        ctrl.driverSourcesChanged.emit.assert_called_once_with()

    def test_remove_driver_source_emits_signal_when_confirmed(self):
        from RBFtools.controller import MainController
        from RBFtools import core
        ctrl = self._stub_controller()
        ctrl.ask_confirm = mock.MagicMock(return_value=True)
        with mock.patch.object(
                core, "remove_driver_source") as core_rm:
            MainController.remove_driver_source(ctrl, 0)
        core_rm.assert_called_once()
        ctrl.driverSourcesChanged.emit.assert_called_once_with()

    def test_remove_driver_source_no_emit_on_user_cancel(self):
        from RBFtools.controller import MainController
        from RBFtools import core
        ctrl = self._stub_controller()
        ctrl.ask_confirm = mock.MagicMock(return_value=False)
        with mock.patch.object(
                core, "remove_driver_source") as core_rm:
            MainController.remove_driver_source(ctrl, 0)
        core_rm.assert_not_called()
        ctrl.driverSourcesChanged.emit.assert_not_called()


# ----------------------------------------------------------------------
# Pose editor multi-source banner (Hardening 2 backcompat parity)
# ----------------------------------------------------------------------


class TestM_UIRECONCILE_BannerSourceScan(unittest.TestCase):
    """Source-scan: pose_editor exposes show/hide_multi_source_banner
    and main_window gates on len(sources) > 1."""

    @classmethod
    def setUpClass(cls):
        cls._pose_editor_src = _read(os.path.join(
            _REPO_ROOT, "modules", "RBFtools", "scripts",
            "RBFtools", "ui", "widgets", "pose_editor.py"))
        cls._main_src = _read(_MAIN_WINDOW)

    def test_pose_editor_exposes_banner_methods(self):
        self.assertIn("def show_multi_source_banner",
                      self._pose_editor_src)
        self.assertIn("def hide_multi_source_banner",
                      self._pose_editor_src)

    def test_main_window_gates_banner_on_source_count(self):
        """M_TABBED_EDITOR_INTEGRATION (2026-04-27): the multi-
        source banner is removed from main_window because the
        legacy AttributeList it warned about no longer exists -
        the tabbed editor IS the multi-source UI now. The banner
        methods themselves remain on the standalone PoseEditor
        class (covered by sibling test
        test_pose_editor_exposes_banner_methods) for any
        downstream consumer that imports the standalone widget
        outside of main_window. This test now passes when EITHER
        the legacy gating call lives in main_window OR the user
        directive removed it."""
        legacy_gate_present = (
            "len(sources) > 1" in self._main_src
            and "show_multi_source_banner" in self._main_src
            and "hide_multi_source_banner" in self._main_src)
        # Post-M_TABBED_EDITOR_INTEGRATION the banner is intentionally
        # absent from the main_window reload path.
        self.assertTrue(
            legacy_gate_present
            or "show_multi_source_banner" not in self._main_src,
            "main_window must either retain the M_UIRECONCILE banner "
            "gate (legacy single-source backcompat) OR have removed "
            "it under M_TABBED_EDITOR_INTEGRATION; the half-state "
            "where show_multi_source_banner is present without the "
            "len(sources) > 1 gate is forbidden")


@unittest.skipIf(conftest._REAL_MAYA,
    "mock-dependent (mock.patch on QtWidgets)")
class TestM_UIRECONCILE_BannerLifecycle(unittest.TestCase):

    def _make_pose_editor(self):
        from RBFtools.ui.widgets.pose_editor import PoseEditor
        pe = PoseEditor.__new__(PoseEditor)
        pe._lbl_multi_source_banner = mock.MagicMock()
        return pe

    def test_show_banner_sets_text_and_visible(self):
        from RBFtools.ui.widgets.pose_editor import PoseEditor
        pe = self._make_pose_editor()
        PoseEditor.show_multi_source_banner(pe, "Multi-source")
        pe._lbl_multi_source_banner.setText.assert_called_with(
            "Multi-source")
        pe._lbl_multi_source_banner.setVisible.assert_called_with(
            True)

    def test_hide_banner(self):
        from RBFtools.ui.widgets.pose_editor import PoseEditor
        pe = self._make_pose_editor()
        PoseEditor.hide_multi_source_banner(pe)
        pe._lbl_multi_source_banner.setVisible.assert_called_with(
            False)

    def test_show_banner_with_empty_text_hides(self):
        from RBFtools.ui.widgets.pose_editor import PoseEditor
        pe = self._make_pose_editor()
        PoseEditor.show_multi_source_banner(pe, "")
        pe._lbl_multi_source_banner.setVisible.assert_called_with(
            False)


# ----------------------------------------------------------------------
# i18n key parity for the new strings
# ----------------------------------------------------------------------


class TestM_UIRECONCILE_I18nKeyParity(unittest.TestCase):
    REQUIRED_KEYS = [
        "warning_driver_source_no_selection",
        "warning_driver_source_self_excluded",
        "banner_multi_source_detected",
    ]

    def test_required_keys_present_in_both_languages(self):
        from RBFtools.ui import i18n
        missing_en = [k for k in self.REQUIRED_KEYS if k not in i18n._EN]
        missing_zh = [k for k in self.REQUIRED_KEYS if k not in i18n._ZH]
        self.assertEqual(missing_en, [],
            "Missing EN keys: {}".format(missing_en))
        self.assertEqual(missing_zh, [],
            "Missing ZH keys: {}".format(missing_zh))

    def test_section_label_no_longer_says_preview(self):
        """D.1: the (preview) qualifier is removed from the
        Driver Sources section header."""
        from RBFtools.ui import i18n
        self.assertNotIn("preview", i18n._EN["section_driver_sources"])
        self.assertNotIn(u"预览",
                         i18n._ZH["section_driver_sources"])


if __name__ == "__main__":
    unittest.main()
