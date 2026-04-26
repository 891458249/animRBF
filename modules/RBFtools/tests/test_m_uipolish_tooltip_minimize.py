"""M_UIPOLISH - tooltip coverage + HelpBubble minimize-aware tests.

Two new permanent guards land in this module:

* **#34 T_TOOLTIP_COVERAGE_PRESENT** - source-scan for a precise
  hardcoded list of key interactive widgets. Each must expose at
  least one tooltip surface (Qt-native ``setToolTip(`` OR a
  ``HelpButton(`` / ``ComboHelpButton(`` companion). The list is
  pinned by the Hardening 1 / Hardening 5 evidence table - new
  widgets join the list in the SAME commit that introduces them.

* **#35 T_HELPBUBBLE_MINIMIZE_AWARE** - source-scan for the
  ``WindowStateChange`` + ``Hide`` event handling and the
  ``QApplication.applicationStateChanged`` fallback in
  ``ui/widgets/help_button.py``. This locks the M_UIPOLISH C.2
  fix against future regression.

Plus mock-pattern tests for the lifecycle wiring that exercise:

* The Move/Resize legacy path stays intact (Hardening 2 backcompat
  parity).
* WindowStateChange / Hide events trigger the un-pin path.
* Idempotence (Hardening 4): repeated minimize while bubble is
  already hidden does NOT re-toggle pinned state.
"""

from __future__ import absolute_import

import inspect
import os
import re
import unittest
from unittest import mock

import conftest


_REPO_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
_HELP_BUTTON_PY = os.path.join(
    _REPO_ROOT, "modules", "RBFtools", "scripts", "RBFtools",
    "ui", "widgets", "help_button.py"
)
_WIDGETS_DIR = os.path.join(
    _REPO_ROOT, "modules", "RBFtools", "scripts", "RBFtools",
    "ui", "widgets"
)


# ----------------------------------------------------------------------
# #34 T_TOOLTIP_COVERAGE_PRESENT — Hardening 5 hardcoded list
# ----------------------------------------------------------------------
#
# Each entry must carry at least ONE of:
#   - setToolTip(...) call
#   - HelpButton(...) instantiation
#   - ComboHelpButton(...) instantiation
#
# The list reflects the Hardening 1 evidence table (see addendum
# §M_UIPOLISH.tooltip-coverage-decision). Future widgets MUST be
# added in the same commit that introduces them.
KEY_INTERACTIVE_WIDGETS = [
    # Newly covered by M_UIPOLISH (B.3 micro):
    "attribute_list.py",
    "import_dialog.py",
    "live_edit_widget.py",
    "mirror_dialog.py",
    "node_selector.py",
    "pose_editor.py",
    "prune_dialog.py",
    "profile_widget.py",
    # Already covered pre-M_UIPOLISH (HelpButton or setToolTip):
    "_ordered_list_editor_base.py",
    "driver_source_list_editor.py",
    "general_section.py",
    "ordered_int_list_editor.py",
    "output_encoding_combo.py",
    "output_scale_editor.py",
    "rbf_section.py",
    "vector_angle_section.py",
]


_TOOLTIP_SURFACE_PATTERN = re.compile(
    r"setToolTip\(|HelpButton\(|ComboHelpButton\("
)


class TestTooltipCoveragePresent(unittest.TestCase):
    """#34 PERMANENT GUARD - DO NOT REMOVE.

    Each KEY_INTERACTIVE_WIDGETS file must have at least one tooltip
    surface. New widgets get added to this list in the same commit
    that introduces them (atomicity per PROJECT-CONSTITUTIONAL-EVENT
    pattern).
    """

    def test_each_key_widget_has_tooltip_surface(self):
        missing = []
        for w in KEY_INTERACTIVE_WIDGETS:
            path = os.path.join(_WIDGETS_DIR, w)
            self.assertTrue(os.path.exists(path),
                "key interactive widget {!r} not found - update the "
                "KEY_INTERACTIVE_WIDGETS list when widgets are renamed "
                "or removed".format(w))
            with open(path, "r", encoding="utf-8") as fh:
                body = fh.read()
            if not _TOOLTIP_SURFACE_PATTERN.search(body):
                missing.append(w)
        self.assertEqual(missing, [],
            "Key interactive widgets missing tooltip surface "
            "(setToolTip / HelpButton / ComboHelpButton): {}".format(
                missing))


# ----------------------------------------------------------------------
# #35 T_HELPBUBBLE_MINIMIZE_AWARE — source-scan help_button.py
# ----------------------------------------------------------------------


class TestHelpBubbleMinimizeAware(unittest.TestCase):
    """#35 PERMANENT GUARD - DO NOT REMOVE.

    help_button.py must keep the M_UIPOLISH C.2 fix wired:
    eventFilter handles WindowStateChange + Hide on the Maya main
    window, and QApplication.applicationStateChanged is connected
    as the alt-tab fallback. All three signals are required - any
    one missing leaves the production minimise bug uncovered.
    """

    @classmethod
    def setUpClass(cls):
        with open(_HELP_BUTTON_PY, "r", encoding="utf-8") as f:
            cls._src = f.read()

    def test_eventfilter_handles_window_state_change(self):
        self.assertIn("WindowStateChange", self._src,
            "help_button.py must handle QEvent.WindowStateChange "
            "(M_UIPOLISH C.2 - Maya minimise -> hide pinned bubble)")

    def test_eventfilter_handles_hide(self):
        self.assertIn("QtCore.QEvent.Hide", self._src,
            "help_button.py must handle QEvent.Hide (M_UIPOLISH C.2 "
            "- Maya main window hides -> hide pinned bubble)")

    def test_application_state_fallback_wired(self):
        self.assertIn("applicationStateChanged", self._src,
            "help_button.py must connect QApplication."
            "applicationStateChanged for the alt-tab fallback "
            "(M_UIPOLISH Hardening 4)")
        self.assertIn("ApplicationInactive", self._src,
            "fallback handler must check Qt.ApplicationInactive")

    def test_legacy_move_resize_path_preserved(self):
        """Hardening 2 / red line 14 backcompat parity: the existing
        Move/Resize reposition path must remain in place."""
        self.assertIn("QtCore.QEvent.Move", self._src,
            "help_button.py must keep the legacy Move event "
            "handler (red line 14 backcompat parity)")
        self.assertIn("QtCore.QEvent.Resize", self._src,
            "help_button.py must keep the legacy Resize event "
            "handler (red line 14 backcompat parity)")
        self.assertIn("reposition", self._src,
            "Move/Resize handler must still reposition the bubble")

    def test_eventfilter_returns_false(self):
        """Red line 14: eventFilter must remain non-consuming so
        Maya's normal event flow is undisturbed."""
        m = re.search(
            r"def eventFilter\(self.*?return\s+False",
            self._src, re.S)
        self.assertIsNotNone(m,
            "eventFilter must return False (non-consuming) "
            "- red line 14 backcompat parity")


# ----------------------------------------------------------------------
# Mock-pattern: lifecycle wiring (Hardening 2 + Hardening 4)
# ----------------------------------------------------------------------


@unittest.skipIf(conftest._REAL_MAYA,
    "mock-dependent (mock.patch on QtWidgets / QApplication)")
class TestHelpButtonLifecycleMock(unittest.TestCase):
    """Exercise the new eventFilter branches under a fully mocked
    PySide stack. We assert behaviour by observing _on_click side
    effects and bubble.hide() calls rather than spinning a real
    QApplication."""

    def _make_button(self):
        from RBFtools.ui.widgets import help_button
        btn = help_button.HelpButton.__new__(help_button.HelpButton)
        btn._help_key = "stub"
        btn._pinned = True
        btn._bubble = mock.MagicMock()
        btn._bubble.isVisible.return_value = True
        btn._main_window = None
        btn._on_click = mock.MagicMock()
        btn.mapToGlobal = mock.MagicMock(return_value=mock.MagicMock())
        btn.width = mock.MagicMock(return_value=18)
        return btn

    def test_window_state_change_unpins(self):
        btn = self._make_button()
        from RBFtools.ui.compat import QtCore
        evt = mock.MagicMock()
        evt.type.return_value = QtCore.QEvent.WindowStateChange
        from RBFtools.ui.widgets.help_button import HelpButton
        result = HelpButton.eventFilter(btn, mock.MagicMock(), evt)
        btn._on_click.assert_called_once()
        self.assertFalse(result,
            "eventFilter must return False (non-consuming)")

    def test_hide_event_unpins(self):
        btn = self._make_button()
        from RBFtools.ui.compat import QtCore
        evt = mock.MagicMock()
        evt.type.return_value = QtCore.QEvent.Hide
        from RBFtools.ui.widgets.help_button import HelpButton
        HelpButton.eventFilter(btn, mock.MagicMock(), evt)
        btn._on_click.assert_called_once()

    def test_idempotence_no_unpin_when_bubble_hidden(self):
        """Hardening 4: repeated minimise while the bubble is
        already hidden must NOT re-toggle pinned state."""
        btn = self._make_button()
        btn._bubble.isVisible.return_value = False
        from RBFtools.ui.compat import QtCore
        evt = mock.MagicMock()
        evt.type.return_value = QtCore.QEvent.WindowStateChange
        from RBFtools.ui.widgets.help_button import HelpButton
        HelpButton.eventFilter(btn, mock.MagicMock(), evt)
        btn._on_click.assert_not_called()

    def test_legacy_move_path_still_repositions(self):
        """Hardening 2 backcompat parity: a Move event on the main
        window still triggers bubble.reposition (legacy behaviour
        must be 0-modified)."""
        btn = self._make_button()
        from RBFtools.ui.compat import QtCore
        evt = mock.MagicMock()
        evt.type.return_value = QtCore.QEvent.Move
        from RBFtools.ui.widgets.help_button import HelpButton
        HelpButton.eventFilter(btn, mock.MagicMock(), evt)
        btn._bubble.reposition.assert_called_once()
        btn._on_click.assert_not_called()

    def test_application_state_inactive_unpins(self):
        btn = self._make_button()
        from RBFtools.ui.compat import QtCore
        from RBFtools.ui.widgets.help_button import HelpButton
        HelpButton._on_application_state_changed(
            btn, QtCore.Qt.ApplicationInactive)
        btn._on_click.assert_called_once()

    def test_application_state_active_does_not_unpin(self):
        btn = self._make_button()
        from RBFtools.ui.compat import QtCore
        from RBFtools.ui.widgets.help_button import HelpButton
        HelpButton._on_application_state_changed(
            btn, QtCore.Qt.ApplicationActive)
        btn._on_click.assert_not_called()


# ----------------------------------------------------------------------
# i18n key parity: every new tooltip key has an EN + ZH entry
# ----------------------------------------------------------------------


class TestM_UIPOLISH_I18nKeyParity(unittest.TestCase):
    """The 15 new tooltip keys + the warning_pose_pruner_no_node key
    must exist in BOTH the EN and ZH dictionaries (D.3 EN+ZH parity
    invariant inherited from M_B24b1)."""

    REQUIRED_KEYS = [
        "attribute_list_select_tip",
        "import_dialog_btn_tip",
        "live_edit_toggle_tip",
        "mirror_dialog_btn_tip",
        "mirror_dialog_pattern_tip",
        "mirror_dialog_replacement_tip",
        "node_selector_combo_tip",
        "node_selector_pick_tip",
        "node_selector_new_tip",
        "node_selector_delete_tip",
        "node_selector_refresh_tip",
        "pose_editor_apply_tip",
        "pose_editor_connect_tip",
        "prune_dialog_btn_tip",
        "profile_widget_refresh_tip",
        "warning_pose_pruner_no_node",
    ]

    def test_all_required_keys_in_both_languages(self):
        from RBFtools.ui import i18n
        missing_en = [k for k in self.REQUIRED_KEYS if k not in i18n._EN]
        missing_zh = [k for k in self.REQUIRED_KEYS if k not in i18n._ZH]
        self.assertEqual(missing_en, [],
            "Missing EN translations: {}".format(missing_en))
        self.assertEqual(missing_zh, [],
            "Missing ZH translations: {}".format(missing_zh))


if __name__ == "__main__":
    unittest.main()
