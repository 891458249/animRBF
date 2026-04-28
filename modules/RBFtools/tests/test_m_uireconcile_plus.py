"""M_UIRECONCILE_PLUS - Item 4b per-driver-source attribute picker.

Closes the M_UIRECONCILE half-completion gap: the + button correctly
batch-creates driverSource entries (M_UIRECONCILE), but every entry
lands with empty `attrs=[]` because the previous commit had no UI
surface for picking attributes per source. Item 4b adds an
in-row "Attrs..." button that opens a multi-select dialog and
forwards the chosen list to ``controller.set_driver_source_attrs``.

Coverage:

* Source-scan: core / controller / editor / main_window all carry
  the new wiring.
* Mock E2E: per-row Attrs button click emits ``attrsRequested``;
  the editor forwards to ``DriverSourceListEditor.attrsRequested``
  with the resolved row index.
* Controller signal parity: ``set_driver_source_attrs`` emits
  ``driverSourcesChanged`` on success and skips on failure.
* core.set_driver_source_attrs orchestrator: out-of-range index +
  remove/re-add sweep behaviour.
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


def _read(path):
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


# ----------------------------------------------------------------------
# Source-scan: orchestrator API exists across every layer
# ----------------------------------------------------------------------


class TestM_UIRECONCILE_PLUS_SourceScan(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._core = _read(os.path.join(
            _REPO_ROOT, "modules", "RBFtools", "scripts",
            "RBFtools", "core.py"))
        cls._controller = _read(os.path.join(
            _REPO_ROOT, "modules", "RBFtools", "scripts",
            "RBFtools", "controller.py"))
        cls._editor = _read(os.path.join(
            _REPO_ROOT, "modules", "RBFtools", "scripts",
            "RBFtools", "ui", "widgets", "driver_source_list_editor.py"))
        cls._main = _read(os.path.join(
            _REPO_ROOT, "modules", "RBFtools", "scripts",
            "RBFtools", "ui", "main_window.py"))

    def test_core_orchestrator_present(self):
        self.assertIn("def set_driver_source_attrs", self._core,
            "core.set_driver_source_attrs must exist (Item 4b)")

    def test_controller_wrapper_present(self):
        self.assertIn("def set_driver_source_attrs", self._controller,
            "controller.set_driver_source_attrs must exist (Item 4b)")
        self.assertIn(
            "self.driverSourcesChanged.emit()", self._controller,
            "controller.set_driver_source_attrs must emit "
            "driverSourcesChanged on success (Item 4b)")

    def test_editor_exposes_attrs_requested_signal(self):
        self.assertIn("attrsRequested", self._editor)
        self.assertIn("def _on_attrs_clicked", self._editor)
        self.assertIn("def _forward_attrs_request", self._editor)

    def test_main_window_picker_dialog_present(self):
        # The legacy _DriverAttrPickerDialog class remains in
        # main_window for backcompat (M_UIRECONCILE_PLUS dialog
        # surface); M_TABBED_EDITOR (2026-04-27) replaces the
        # invocation site with the tabbed editor's per-tab Connect
        # button + a slot pair (_attrs_apply / _attrs_clear). The
        # test now accepts either the legacy
        # _on_driver_source_attrs_requested slot OR the new
        # tabbed _on_driver_source_attrs_apply slot.
        self.assertIn(
            "class _DriverAttrPickerDialog", self._main,
            "main_window must define the modal picker dialog "
            "(Item 4b backcompat - kept for the M_UIRECONCILE_PLUS "
            "API surface)")
        legacy_slot = "_on_driver_source_attrs_requested" in self._main
        tabbed_slot = "_on_driver_source_attrs_apply" in self._main
        self.assertTrue(legacy_slot or tabbed_slot,
            "main_window must wire either the legacy "
            "_on_driver_source_attrs_requested slot or the "
            "M_TABBED_EDITOR _on_driver_source_attrs_apply slot")
        self.assertIn(
            "set_driver_source_attrs", self._main,
            "main_window slot must call "
            "controller.set_driver_source_attrs (Item 4b)")
        self.assertIn(
            "cmds.listAttr(", self._main,
            "main_window must use cmds.listAttr somewhere - either "
            "to seed the picker dialog (M_UIRECONCILE_PLUS) or to "
            "pre-resolve per-tab available attrs (M_TABBED_EDITOR)")


# ----------------------------------------------------------------------
# core.set_driver_source_attrs orchestrator
# ----------------------------------------------------------------------


@unittest.skipIf(conftest._REAL_MAYA,
    "mock-dependent (mock.patch on cmds.* + read_driver_info_multi)")
class TestM_UIRECONCILE_PLUS_CoreOrchestrator(unittest.TestCase):

    def test_out_of_range_returns_false(self):
        from RBFtools import core
        with mock.patch.object(
                core, "read_driver_info_multi",
                return_value=[
                    core.DriverSource(
                        node="drv1", attrs=("tx",),
                        weight=1.0, encoding=0)]):
            ok = core.set_driver_source_attrs("RBF1", 5, ["tx"])
        self.assertFalse(ok,
            "out-of-range index must yield False (Item 4b)")

    def test_empty_source_list_returns_false(self):
        from RBFtools import core
        with mock.patch.object(
                core, "read_driver_info_multi", return_value=[]):
            ok = core.set_driver_source_attrs("RBF1", 0, ["tx"])
        self.assertFalse(ok,
            "empty source list must yield False (Item 4b)")

    def test_in_range_index_uses_incremental_diff(self):
        """M_REBUILD_REFACTOR (2026-04-28): the legacy "remove all
        + re-add all" flow was Bug B's root cause (input[]
        accumulation + duplicate connections). The new path uses
        incremental diff — disconnect source[index..end] via
        _disconnect_or_purge, reconnect at base. NO
        remove_driver_source / add_driver_source calls inside
        set_driver_source_attrs."""
        from RBFtools import core
        sources = [
            core.DriverSource(node="drv0", attrs=("tx",),
                              weight=1.0, encoding=0),
            core.DriverSource(node="drv1", attrs=("tx",),
                              weight=0.5, encoding=1),
        ]
        import maya.cmds as cmds
        cmds.reset_mock()
        cmds.attributeQuery.return_value = True
        with mock.patch.object(
                core, "read_driver_info_multi",
                return_value=list(sources)), \
             mock.patch.object(core, "get_shape",
                               return_value="RBF1Shape"), \
             mock.patch.object(core, "_exists",
                               return_value=True), \
             mock.patch.object(core, "_subscript_of_existing_input",
                               return_value=None), \
             mock.patch.object(core, "_disconnect_or_purge"), \
             mock.patch.object(core, "_sweep_empty_subscripts"), \
             mock.patch.object(core, "remove_driver_source") as rm, \
             mock.patch.object(core, "add_driver_source") as add:
            ok = core.set_driver_source_attrs(
                "RBF1", 1, ["ty", "tz"])
        self.assertTrue(ok)
        # Bug B regression check.
        rm.assert_not_called()
        add.assert_not_called()


# ----------------------------------------------------------------------
# Controller signal parity
# ----------------------------------------------------------------------


@unittest.skipIf(conftest._REAL_MAYA,
    "mock-dependent (mock.patch on core.* + cmds.warning)")
class TestM_UIRECONCILE_PLUS_ControllerSignal(unittest.TestCase):

    def _stub(self):
        from RBFtools.controller import MainController
        ctrl = MainController.__new__(MainController)
        ctrl._current_node = "RBF1"
        ctrl.driverSourcesChanged = mock.MagicMock()
        return ctrl

    def test_emits_signal_on_success(self):
        from RBFtools.controller import MainController
        from RBFtools import core
        ctrl = self._stub()
        with mock.patch.object(
                core, "set_driver_source_attrs",
                return_value=True) as core_set:
            MainController.set_driver_source_attrs(
                ctrl, 0, ["tx", "ty"])
        core_set.assert_called_once()
        ctrl.driverSourcesChanged.emit.assert_called_once_with()

    def test_no_emit_on_failure(self):
        from RBFtools.controller import MainController
        from RBFtools import core
        ctrl = self._stub()
        with mock.patch.object(
                core, "set_driver_source_attrs",
                return_value=False):
            MainController.set_driver_source_attrs(
                ctrl, 99, ["tx"])
        ctrl.driverSourcesChanged.emit.assert_not_called()

    def test_no_emit_when_no_current_node(self):
        from RBFtools.controller import MainController
        ctrl = self._stub()
        ctrl._current_node = ""
        ok = MainController.set_driver_source_attrs(
            ctrl, 0, ["tx"])
        self.assertFalse(ok)
        ctrl.driverSourcesChanged.emit.assert_not_called()


# ----------------------------------------------------------------------
# Editor row signal: Attrs button click forwards correctly
# ----------------------------------------------------------------------


@unittest.skipIf(conftest._REAL_MAYA,
    "mock-dependent (PySide signal stubs)")
class TestM_UIRECONCILE_PLUS_RowSignal(unittest.TestCase):

    def test_row_emits_attrs_requested(self):
        from RBFtools.ui.widgets.driver_source_list_editor import (
            _DriverSourceRow, DriverSource)
        row = _DriverSourceRow.__new__(_DriverSourceRow)
        row._source = DriverSource(
            node="drv1", attrs=("tx", "ty"),
            weight=1.0, encoding=0)
        row.attrsRequested = mock.MagicMock()
        _DriverSourceRow._on_attrs_clicked(row)
        row.attrsRequested.emit.assert_called_once_with(
            "drv1", ("tx", "ty"))


if __name__ == "__main__":
    unittest.main()
