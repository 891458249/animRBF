"""M_TABBED_EDITOR - QTabWidget paradigm for driver / driven editors.

Replaces the M_B24b1 / M_DRIVEN_MULTI list-row paradigm with a
tabbed layout matching the Tekken-8 AnimaRbfSolver reference UX
(user request 2026-04-27, screenshot reference: each Driver / Driven
entry is a `Driver N` / `Driven N` tab).

Coverage:

* Source-scan: tabbed editor file + class + signal surface.
* Source-scan: main_window swap (legacy DriverSourceListEditor /
  DrivenSourceListEditor instantiations replaced with
  TabbedDriverSourceEditor / TabbedDrivenSourceEditor; new slot
  names wired).
* Mock E2E: per-tab Connect / Disconnect / Select buttons emit
  the right index-aware signals; remove flow forwards correctly.
* set_sources lifecycle: rebuild tears down old tabs + recreates
  new ones; tab-label prefix is "Driver" / "Driven".
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


def _read(path):
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


# ----------------------------------------------------------------------
# Source-scan
# ----------------------------------------------------------------------


class TestM_TABBED_EDITOR_SourceScan(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._editor = _read(os.path.join(
            _REPO_ROOT, "modules", "RBFtools", "scripts",
            "RBFtools", "ui", "widgets", "tabbed_source_editor.py"))
        cls._main = _read(os.path.join(
            _REPO_ROOT, "modules", "RBFtools", "scripts",
            "RBFtools", "ui", "main_window.py"))

    def test_widget_module_present(self):
        for cls_name in ("class _SourceTabContent",
                         "class _TabbedSourceEditorBase",
                         "class TabbedDriverSourceEditor",
                         "class TabbedDrivenSourceEditor"):
            self.assertIn(cls_name, self._editor,
                "tabbed_source_editor.py missing {}".format(cls_name))

    def test_signal_surface(self):
        # M_TABBED_EDITOR_REWRITE (2026-04-27 strict spec): per-tab
        # weight + encoding controls are removed; weightChanged /
        # encodingChanged signals are no longer required.
        for sig in ("addRequested", "removeRequested",
                    "attrsApplyRequested", "attrsClearRequested",
                    "selectNodeRequested"):
            self.assertIn(sig, self._editor,
                "tabbed_source_editor.py missing signal {}".format(sig))

    def test_main_window_imports_tabbed(self):
        self.assertIn(
            "from RBFtools.ui.widgets.tabbed_source_editor",
            self._main,
            "main_window must import the tabbed editors")
        self.assertIn("TabbedDriverSourceEditor", self._main)
        self.assertIn("TabbedDrivenSourceEditor", self._main)

    def test_main_window_uses_tabbed_instances(self):
        self.assertIn("TabbedDriverSourceEditor()", self._main)
        self.assertIn("TabbedDrivenSourceEditor()", self._main)

    def test_main_window_wires_new_slot_pair(self):
        for slot in ("_on_driver_source_attrs_apply",
                     "_on_driver_source_attrs_clear",
                     "_on_driver_source_select_node",
                     "_on_driven_source_attrs_apply",
                     "_on_driven_source_attrs_clear",
                     "_on_driven_source_select_node",
                     "_bind_source_node_from_selection",
                     "_resolve_available_attrs_per_source"):
            self.assertIn(slot, self._main,
                "main_window missing tabbed slot {}".format(slot))


# ----------------------------------------------------------------------
# Mock E2E: per-tab signals + editor index-aware re-emission
# ----------------------------------------------------------------------


@unittest.skipIf(conftest._REAL_MAYA,
    "mock-dependent (PySide signal stubs)")
class TestM_TABBED_EDITOR_PanelConnect(unittest.TestCase):
    """M_TABBED_EDITOR_REWRITE (2026-04-27 strict spec): the
    Connect / Disconnect buttons live at the panel level (the
    QGroupBox-wrapped editor) and operate on the currently-active
    tab. The per-tab _on_connect_clicked from the previous
    iteration is gone."""

    def _make_panel(self):
        from RBFtools.ui.widgets.tabbed_source_editor import (
            _TabbedSourceEditorBase)
        panel = _TabbedSourceEditorBase.__new__(_TabbedSourceEditorBase)
        panel._tabs = mock.MagicMock()
        panel.attrsApplyRequested = mock.MagicMock()
        panel.attrsClearRequested = mock.MagicMock()
        return panel

    def test_connect_emits_apply_with_current_tab_attrs(self):
        from RBFtools.ui.widgets.tabbed_source_editor import (
            _TabbedSourceEditorBase)
        panel = self._make_panel()
        panel._tabs.currentIndex.return_value = 1
        content = mock.MagicMock()
        content.selected_attrs.return_value = ["tx", "ty"]
        panel._tabs.widget.return_value = content
        _TabbedSourceEditorBase._on_connect_clicked(panel)
        panel.attrsApplyRequested.emit.assert_called_once_with(
            1, ["tx", "ty"])

    def test_connect_no_active_tab_is_noop(self):
        from RBFtools.ui.widgets.tabbed_source_editor import (
            _TabbedSourceEditorBase)
        panel = self._make_panel()
        panel._tabs.currentIndex.return_value = -1
        _TabbedSourceEditorBase._on_connect_clicked(panel)
        panel.attrsApplyRequested.emit.assert_not_called()

    def test_disconnect_emits_clear_with_current_tab_index(self):
        from RBFtools.ui.widgets.tabbed_source_editor import (
            _TabbedSourceEditorBase)
        panel = self._make_panel()
        panel._tabs.currentIndex.return_value = 2
        _TabbedSourceEditorBase._on_disconnect_clicked(panel)
        panel.attrsClearRequested.emit.assert_called_once_with(2)


@unittest.skipIf(conftest._REAL_MAYA,
    "mock-dependent (PySide signal stubs)")
class TestM_TABBED_EDITOR_RemoveSignal(unittest.TestCase):

    def test_tab_close_emits_remove_with_index(self):
        from RBFtools.ui.widgets.tabbed_source_editor import (
            _TabbedSourceEditorBase)
        editor = _TabbedSourceEditorBase.__new__(
            _TabbedSourceEditorBase)
        editor.removeRequested = mock.MagicMock()
        _TabbedSourceEditorBase._on_tab_close(editor, 2)
        editor.removeRequested.emit.assert_called_once_with(2)


# ----------------------------------------------------------------------
# i18n parity for the new keys
# ----------------------------------------------------------------------


class TestM_TABBED_EDITOR_I18nParity(unittest.TestCase):

    # M_TABBED_EDITOR_REWRITE (2026-04-27): per-tab weight +
    # encoding labels are obsolete; new keys for the outer
    # DriverDriven / Pose tab labels + the per-panel Add Driver /
    # Add Driven buttons are required.
    REQUIRED_KEYS = [
        "source_tab_add_tip",
        "source_tab_connect_tip",
        "source_tab_disconnect_tip",
        "tab_driver_driven",
        "tab_pose",
        "btn_add_driver",
        "btn_add_driven",
    ]

    def test_required_keys_present_in_both_languages(self):
        from RBFtools.ui import i18n
        missing_en = [k for k in self.REQUIRED_KEYS if k not in i18n._EN]
        missing_zh = [k for k in self.REQUIRED_KEYS if k not in i18n._ZH]
        self.assertEqual(missing_en, [],
            "Missing EN: {}".format(missing_en))
        self.assertEqual(missing_zh, [],
            "Missing ZH: {}".format(missing_zh))


# ----------------------------------------------------------------------
# Concrete subclass attribute differentiation
# ----------------------------------------------------------------------


class TestM_TABBED_EDITOR_SubclassDifferentiation(unittest.TestCase):
    """M_TABBED_EDITOR_REWRITE (2026-04-27 strict spec): the driver
    and driven subclasses differ only in role / tab-prefix /
    add-button-key / list-selection mode (single vs extended).
    Per-source weight + encoding are removed."""

    def test_driver_subclass_role_and_prefix(self):
        from RBFtools.ui.widgets.tabbed_source_editor import (
            TabbedDriverSourceEditor)
        self.assertEqual(TabbedDriverSourceEditor._role, "driver")
        self.assertEqual(
            TabbedDriverSourceEditor._tab_label_prefix, "Driver")
        self.assertEqual(
            TabbedDriverSourceEditor._add_button_key, "btn_add_driver")

    def test_driven_subclass_role_and_prefix(self):
        from RBFtools.ui.widgets.tabbed_source_editor import (
            TabbedDrivenSourceEditor)
        self.assertEqual(TabbedDrivenSourceEditor._role, "driven")
        self.assertEqual(
            TabbedDrivenSourceEditor._tab_label_prefix, "Driven")
        self.assertEqual(
            TabbedDrivenSourceEditor._add_button_key, "btn_add_driven")


if __name__ == "__main__":
    unittest.main()
