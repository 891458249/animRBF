# -*- coding: utf-8 -*-
"""M_BATCH_PATH_A_WIRE (2026-04-28) — wire the bottom-of-panel
"Batch All * Tabs" checkbox into the path-A button click flow.

User report — checking ``Batch All Driver Tabs`` /
``Batch All Driven Tabs`` had ZERO effect on the panel-level
Connect / Disconnect buttons. Click in Driver 0 with batch
checked → only Driver 0's source was modified; the other tabs
stayed silent.

Root cause: the panel buttons (``_on_connect_clicked`` /
``_on_disconnect_clicked``) emitted ``attrsApplyRequested(idx,
attrs)`` / ``attrsClearRequested(idx, attrs)`` UNCONDITIONALLY
without consulting ``_chk_batch.isChecked()``. The
``is_batch_mode()`` getter existed (path B / pose-editor flow
used it via ``_gather_routed_targets``) but path A was wired
directly to button.click → single-tab signal, batch flag
ignored entirely.

Fix:
  1. tabbed_source_editor — _on_*_clicked dispatch on
     is_batch_mode(): batch -> attrs*BatchRequested(attrs);
     single -> attrs*Requested(idx, attrs).
  2. main_window — 4 new slots (driver+driven × apply+clear)
     iterate every tab in the panel and reuse the controller's
     M_REBUILD_REFACTOR-locked single-source APIs (incremental
     diff + atomic protocol).
  3. Confirm dialog gates each batch operation (multi-tab
     destructive — TD must explicitly accept).

PERMANENT GUARDS — T_BATCH_PATH_A_WIRED.
Mock E2E — 8 scenarios (Driver+Driven × Connect+Disconnect ×
batch on+off + dialog Yes+No paths).
"""

from __future__ import absolute_import

import os
import unittest
from unittest import mock

import conftest


_REPO_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
_TABBED_PY = os.path.join(
    _REPO_ROOT, "modules", "RBFtools", "scripts", "RBFtools",
    "ui", "widgets", "tabbed_source_editor.py")
_MAIN_WINDOW = os.path.join(
    _REPO_ROOT, "modules", "RBFtools", "scripts", "RBFtools",
    "ui", "main_window.py")
_I18N_PY = os.path.join(
    _REPO_ROOT, "modules", "RBFtools", "scripts", "RBFtools",
    "ui", "i18n.py")


def _read(p):
    with open(p, "r", encoding="utf-8") as fh:
        return fh.read()


# ----------------------------------------------------------------------
# PERMANENT GUARD T_BATCH_PATH_A_WIRED
# ----------------------------------------------------------------------


class T_BATCH_PATH_A_WIRED(unittest.TestCase):
    """PERMANENT GUARD — Bug fix locks. DO NOT REMOVE.

    The path-A button click flow MUST consult is_batch_mode() and
    dispatch to dedicated batch signals. main_window MUST expose
    apply_batch / clear_batch slots for both driver + driven."""

    @classmethod
    def setUpClass(cls):
        cls._tab = _read(_TABBED_PY)
        cls._mw = _read(_MAIN_WINDOW)
        cls._i18n = _read(_I18N_PY)

    def test_PERMANENT_a_batch_signals_present(self):
        for sig in ("attrsApplyBatchRequested = QtCore.Signal(list)",
                    "attrsClearBatchRequested = QtCore.Signal(list)"):
            self.assertIn(sig, self._tab,
                "tabbed_source_editor missing batch signal: "
                "{}".format(sig))

    def test_PERMANENT_b_connect_clicked_reads_batch_flag(self):
        body = self._tab.split(
            "def _on_connect_clicked(self):")[1].split(
            "\n    def ")[0]
        self.assertIn("self.is_batch_mode()", body,
            "_on_connect_clicked MUST consult is_batch_mode() — "
            "the bug repro was unconditional emit of the single-"
            "tab signal regardless of the checkbox state.")
        self.assertIn("self.attrsApplyBatchRequested.emit(attrs)",
                      body)
        self.assertIn("self.attrsApplyRequested.emit(idx, attrs)",
                      body)

    def test_PERMANENT_c_disconnect_clicked_reads_batch_flag(self):
        body = self._tab.split(
            "def _on_disconnect_clicked(self):")[1].split(
            "\n    def ")[0]
        self.assertIn("self.is_batch_mode()", body)
        self.assertIn("self.attrsClearBatchRequested.emit(attrs)",
                      body)
        self.assertIn("self.attrsClearRequested.emit(idx, attrs)",
                      body)

    def test_PERMANENT_d_main_window_has_4_batch_slots(self):
        for slot in ("def _on_driver_source_attrs_apply_batch",
                     "def _on_driver_source_attrs_clear_batch",
                     "def _on_driven_source_attrs_apply_batch",
                     "def _on_driven_source_attrs_clear_batch"):
            self.assertIn(slot, self._mw,
                "main_window missing batch slot: {}".format(slot))

    def test_PERMANENT_e_signal_chain_wiring(self):
        # Both panels' apply + clear batch signals must be
        # connected to the matching slot.
        for line in (
                "self._driver_source_list.attrsApplyBatchRequested",
                "self._driver_source_list.attrsClearBatchRequested",
                "self._driven_source_list.attrsApplyBatchRequested",
                "self._driven_source_list.attrsClearBatchRequested"):
            self.assertIn(line, self._mw,
                "Missing batch signal connect: {}".format(line))

    def test_PERMANENT_f_confirm_dialog_present(self):
        # Both _batch_apply + _batch_clear MUST surface a confirm
        # dialog before iterating sources (multi-tab destructive
        # operation must be explicit — red line 6).
        for fn in ("def _batch_apply", "def _batch_clear"):
            body = self._mw.split(fn)[1].split("\n    def ")[0]
            self.assertIn("QMessageBox.question", body,
                "{} MUST surface a confirm dialog before iterating "
                "sources".format(fn))

    def test_PERMANENT_g_i18n_keys_present(self):
        for key in ("title_batch_apply_confirm",
                    "msg_batch_apply_confirm",
                    "title_batch_clear_confirm",
                    "msg_batch_clear_confirm",
                    "all_attrs"):
            self.assertGreaterEqual(
                self._i18n.count('"{}":'.format(key)), 2,
                "i18n key {} missing EN/ZH parity".format(key))


# ----------------------------------------------------------------------
# Mock E2E — tabbed_source_editor click dispatch
# ----------------------------------------------------------------------


@unittest.skipIf(conftest._REAL_MAYA,
    "mock-dependent (PySide signal stubs)")
class TestM_BATCH_PATH_A_WIRE_ClickDispatch(unittest.TestCase):

    def _make_panel(self, batch_checked=False):
        from RBFtools.ui.widgets.tabbed_source_editor import (
            _TabbedSourceEditorBase)
        panel = _TabbedSourceEditorBase.__new__(
            _TabbedSourceEditorBase)
        panel._tabs = mock.MagicMock()
        panel.attrsApplyRequested = mock.MagicMock()
        panel.attrsClearRequested = mock.MagicMock()
        panel.attrsApplyBatchRequested = mock.MagicMock()
        panel.attrsClearBatchRequested = mock.MagicMock()
        panel._chk_batch = mock.MagicMock()
        panel._chk_batch.isChecked.return_value = batch_checked
        return panel

    def test_E2E_connect_batch_off_emits_single(self):
        # Bug-fix regression check: batch off -> single-tab signal.
        from RBFtools.ui.widgets.tabbed_source_editor import (
            _TabbedSourceEditorBase)
        panel = self._make_panel(batch_checked=False)
        panel._tabs.currentIndex.return_value = 1
        content = mock.MagicMock()
        content.selected_attrs.return_value = ["tx", "ty"]
        panel._tabs.widget.return_value = content
        _TabbedSourceEditorBase._on_connect_clicked(panel)
        panel.attrsApplyRequested.emit.assert_called_once_with(
            1, ["tx", "ty"])
        panel.attrsApplyBatchRequested.emit.assert_not_called()

    def test_E2E_connect_batch_on_emits_batch(self):
        # Bug repro path: batch on -> batch signal (no idx,
        # main_window iterates sources).
        from RBFtools.ui.widgets.tabbed_source_editor import (
            _TabbedSourceEditorBase)
        panel = self._make_panel(batch_checked=True)
        panel._tabs.currentIndex.return_value = 0
        content = mock.MagicMock()
        content.selected_attrs.return_value = ["translateX"]
        panel._tabs.widget.return_value = content
        _TabbedSourceEditorBase._on_connect_clicked(panel)
        panel.attrsApplyBatchRequested.emit.assert_called_once_with(
            ["translateX"])
        panel.attrsApplyRequested.emit.assert_not_called()

    def test_E2E_disconnect_batch_off_emits_single(self):
        from RBFtools.ui.widgets.tabbed_source_editor import (
            _TabbedSourceEditorBase)
        panel = self._make_panel(batch_checked=False)
        panel._tabs.currentIndex.return_value = 2
        content = mock.MagicMock()
        content.selected_attrs.return_value = ["rx"]
        panel._tabs.widget.return_value = content
        _TabbedSourceEditorBase._on_disconnect_clicked(panel)
        panel.attrsClearRequested.emit.assert_called_once_with(
            2, ["rx"])
        panel.attrsClearBatchRequested.emit.assert_not_called()

    def test_E2E_disconnect_batch_on_emits_batch(self):
        from RBFtools.ui.widgets.tabbed_source_editor import (
            _TabbedSourceEditorBase)
        panel = self._make_panel(batch_checked=True)
        panel._tabs.currentIndex.return_value = 0
        content = mock.MagicMock()
        content.selected_attrs.return_value = ["ty"]
        panel._tabs.widget.return_value = content
        _TabbedSourceEditorBase._on_disconnect_clicked(panel)
        panel.attrsClearBatchRequested.emit.assert_called_once_with(
            ["ty"])
        panel.attrsClearRequested.emit.assert_not_called()


# ----------------------------------------------------------------------
# Mock E2E — main_window batch slots iterate every source
# ----------------------------------------------------------------------


@unittest.skipIf(conftest._REAL_MAYA,
    "mock-dependent (PySide / cmds + ctrl stubs)")
class TestM_BATCH_PATH_A_WIRE_MainWindowSlots(unittest.TestCase):

    def _src(self, attrs):
        from RBFtools.core import DriverSource
        return DriverSource(node="drv", attrs=tuple(attrs),
                            weight=1.0, encoding=0)

    def _dvn(self, attrs):
        from RBFtools.core import DrivenSource
        return DrivenSource(node="dvn", attrs=tuple(attrs))

    def _make_window(self, drv_sources=None, dvn_sources=None):
        from RBFtools.ui.main_window import RBFToolsWindow
        win = RBFToolsWindow.__new__(RBFToolsWindow)
        win._ctrl = mock.MagicMock()
        win._ctrl.read_driver_sources.return_value = (
            drv_sources or [])
        win._ctrl.read_driven_sources.return_value = (
            dvn_sources or [])
        return win

    # --- Driver Connect batch ---

    def test_E2E_driver_apply_batch_yes_iterates_all_sources(self):
        from RBFtools.ui.main_window import RBFToolsWindow
        win = self._make_window(
            drv_sources=[self._src(["tx"]), self._src(["ty"]),
                         self._src(["tz"])])
        with mock.patch(
                "RBFtools.ui.main_window.QtWidgets.QMessageBox"
        ) as mb:
            mb.Yes = 16384  # match Qt enum truthy values
            mb.No = 65536
            mb.question.return_value = mb.Yes
            RBFToolsWindow._on_driver_source_attrs_apply_batch(
                win, ["translateX", "translateY"])
        # Confirm dialog surfaced once.
        mb.question.assert_called_once()
        # Controller called for every tab — Bug repro check.
        calls = win._ctrl.set_driver_source_attrs.call_args_list
        self.assertEqual(len(calls), 3)
        for idx, c in enumerate(calls):
            self.assertEqual(c.args[0], idx)
            self.assertEqual(c.args[1],
                             ["translateX", "translateY"])

    def test_E2E_driver_apply_batch_no_blocks_iteration(self):
        from RBFtools.ui.main_window import RBFToolsWindow
        win = self._make_window(
            drv_sources=[self._src(["tx"]), self._src(["ty"])])
        with mock.patch(
                "RBFtools.ui.main_window.QtWidgets.QMessageBox"
        ) as mb:
            mb.Yes = 16384
            mb.No = 65536
            mb.question.return_value = mb.No
            RBFToolsWindow._on_driver_source_attrs_apply_batch(
                win, ["tx"])
        win._ctrl.set_driver_source_attrs.assert_not_called()

    def test_E2E_driver_apply_batch_empty_attrs_blocks(self):
        # Empty selection → info dialog + abort (parity with
        # single-tab guard).
        from RBFtools.ui.main_window import RBFToolsWindow
        win = self._make_window(drv_sources=[self._src(["tx"])])
        with mock.patch(
                "RBFtools.ui.main_window.QtWidgets.QMessageBox"
        ) as mb:
            RBFToolsWindow._on_driver_source_attrs_apply_batch(
                win, [])
        mb.information.assert_called_once()
        win._ctrl.set_driver_source_attrs.assert_not_called()

    # --- Driver Disconnect batch ---

    def test_E2E_driver_clear_batch_yes_passes_attrs(self):
        from RBFtools.ui.main_window import RBFToolsWindow
        win = self._make_window(
            drv_sources=[self._src(["tx"]), self._src(["ty"])])
        with mock.patch(
                "RBFtools.ui.main_window.QtWidgets.QMessageBox"
        ) as mb:
            mb.Yes = 16384
            mb.No = 65536
            mb.question.return_value = mb.Yes
            RBFToolsWindow._on_driver_source_attrs_clear_batch(
                win, ["tx"])
        calls = win._ctrl.disconnect_driver_source_attrs.call_args_list
        self.assertEqual(len(calls), 2)
        for c in calls:
            self.assertEqual(c.args[1], ["tx"])

    def test_E2E_driver_clear_batch_empty_attrs_passes_None(self):
        # Empty attrs → Scene B (full per-tab clear) — controller
        # receives attrs=None.
        from RBFtools.ui.main_window import RBFToolsWindow
        win = self._make_window(
            drv_sources=[self._src(["tx", "ty"])])
        with mock.patch(
                "RBFtools.ui.main_window.QtWidgets.QMessageBox"
        ) as mb:
            mb.Yes = 16384
            mb.No = 65536
            mb.question.return_value = mb.Yes
            RBFToolsWindow._on_driver_source_attrs_clear_batch(
                win, [])
        calls = win._ctrl.disconnect_driver_source_attrs.call_args_list
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].args[1], None)

    # --- Driven mirror ---

    def test_E2E_driven_apply_batch_yes_iterates_all(self):
        from RBFtools.ui.main_window import RBFToolsWindow
        win = self._make_window(
            dvn_sources=[self._dvn(["rx"]), self._dvn(["ry"])])
        with mock.patch(
                "RBFtools.ui.main_window.QtWidgets.QMessageBox"
        ) as mb:
            mb.Yes = 16384
            mb.No = 65536
            mb.question.return_value = mb.Yes
            RBFToolsWindow._on_driven_source_attrs_apply_batch(
                win, ["translateZ"])
        calls = win._ctrl.set_driven_source_attrs.call_args_list
        self.assertEqual(len(calls), 2)
        for idx, c in enumerate(calls):
            self.assertEqual(c.args[0], idx)
            self.assertEqual(c.args[1], ["translateZ"])

    def test_E2E_driven_clear_batch_yes_iterates_all(self):
        from RBFtools.ui.main_window import RBFToolsWindow
        win = self._make_window(
            dvn_sources=[self._dvn(["tx"]), self._dvn(["ty"])])
        with mock.patch(
                "RBFtools.ui.main_window.QtWidgets.QMessageBox"
        ) as mb:
            mb.Yes = 16384
            mb.No = 65536
            mb.question.return_value = mb.Yes
            RBFToolsWindow._on_driven_source_attrs_clear_batch(
                win, ["tx"])
        calls = (win._ctrl.disconnect_driven_source_attrs
                 .call_args_list)
        self.assertEqual(len(calls), 2)


if __name__ == "__main__":
    unittest.main()
