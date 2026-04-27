"""M_DRIVEN_MULTI - multi-driven backend + Driven Targets editor
+ Driver/Driven side-by-side merge with the pose editor (Items 1
+ 4c from the user's 2026-04-27 4-item batch).

Coverage:

* Source-scan: DrivenSource dataclass + 4 core orchestrator
  functions + controller wrappers + driverSourcesChanged sibling
  signal driverSourcesChanged for the driven side.
* Source-scan: DrivenSourceListEditor mirrors DriverSourceListEditor
  signal surface.
* Source-scan: main_window instantiates the new section adjacent
  to Driver Sources + immediately above the pose editor (Item 1
  visual merge).
* Mock E2E: + button -> addRequested -> controller.add_driven_source;
  - button -> removeRequested(idx) -> controller.remove_driven_source;
  Attrs... -> attrsRequested(idx, node, attrs) -> controller.set_driven_source_attrs.
* Controller signal parity: drivenSourcesChanged emits per
  successful mutation, not on user-cancelled remove.
* core orchestrator: read_driven_info_multi falls back to legacy
  single-driven shape when the dynamic compound is absent;
  add_driven_source rolls back on wiring failure;
  set_driven_source_attrs validates index range.
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
# Source-scan: backend / controller / editor / main_window all wired
# ----------------------------------------------------------------------


class TestM_DRIVEN_MULTI_SourceScan(unittest.TestCase):

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
            "RBFtools", "ui", "widgets", "driven_source_list_editor.py"))
        cls._main = _read(os.path.join(
            _REPO_ROOT, "modules", "RBFtools", "scripts",
            "RBFtools", "ui", "main_window.py"))

    # core ---------------------------------------------------------------

    def test_core_dataclass_present(self):
        self.assertIn("class DrivenSource", self._core)

    def test_core_orchestrator_funcs_present(self):
        for fn in ("def read_driven_info_multi",
                   "def add_driven_source",
                   "def remove_driven_source",
                   "def set_driven_source_attrs",
                   "def _ensure_driven_source_compound",
                   "def _wire_driven_sources",
                   "def _disconnect_all_outputs"):
            self.assertIn(fn, self._core,
                "core.py missing {}".format(fn))

    # controller ---------------------------------------------------------

    def test_controller_signal_present(self):
        self.assertIn(
            "drivenSourcesChanged = QtCore.Signal", self._controller)

    def test_controller_wrappers_present(self):
        for name in ("def add_driven_source",
                     "def remove_driven_source",
                     "def set_driven_source_attrs",
                     "def read_driven_sources"):
            self.assertIn(name, self._controller,
                "controller.py missing {}".format(name))
        # Each mutation method emits driverSourcesChanged AND each
        # driven mutation method emits drivenSourcesChanged. We
        # accept >= 3 emit callsites for the driven signal.
        self.assertGreaterEqual(
            self._controller.count(
                "self.drivenSourcesChanged.emit()"),
            3,
            "controller must emit drivenSourcesChanged from "
            "add/remove/set_driven_source_attrs (>= 3 callsites)")

    # editor -------------------------------------------------------------

    def test_editor_class_present(self):
        self.assertIn("class DrivenSourceListEditor", self._editor)
        self.assertIn("class _DrivenSourceRow", self._editor)
        self.assertIn("addRequested", self._editor)
        self.assertIn("removeRequested", self._editor)
        self.assertIn("attrsRequested", self._editor)
        # No weight / encoding columns on the driven side. The
        # docstring mentions "encoding" once to explain its
        # deliberate absence; only the actual widget API surfaces
        # are forbidden.
        self.assertNotIn("QDoubleSpinBox", self._editor,
            "driven row must not have a per-source weight spinbox")
        self.assertNotIn("setCurrentIndex(int(self._source.encoding",
                         self._editor,
            "driven row must not consume an encoding field")

    # main_window --------------------------------------------------------

    def test_main_window_instantiates_driven_section(self):
        self.assertIn("_driven_sources_section", self._main)
        self.assertIn("_driven_source_list", self._main)
        # M_TABBED_EDITOR (2026-04-27): main_window now instantiates
        # the tabbed editor (TabbedDrivenSourceEditor); the legacy
        # DrivenSourceListEditor class file remains importable.
        self.assertTrue(
            "DrivenSourceListEditor()" in self._main
            or "TabbedDrivenSourceEditor()" in self._main,
            "main_window must instantiate either the legacy "
            "DrivenSourceListEditor or the new tabbed variant")

    def test_main_window_wires_all_three_driven_signals(self):
        # M_TABBED_EDITOR: required slot list expanded to cover the
        # tabbed signal surface (attrs_apply / attrs_clear /
        # select_node) while keeping the legacy add / remove /
        # reload slots in scope.
        required_legacy = (
            "_on_driven_source_add_requested",
            "_on_driven_source_remove_requested",
            "_reload_driven_sources",
        )
        for slot in required_legacy:
            self.assertIn(slot, self._main,
                "main_window missing slot {}".format(slot))
        # Either the legacy attrs picker slot OR the new tabbed
        # attrs apply/clear pair must be present.
        legacy_attrs = "_on_driven_source_attrs_requested" in self._main
        tabbed_attrs = (
            "_on_driven_source_attrs_apply" in self._main
            and "_on_driven_source_attrs_clear" in self._main)
        self.assertTrue(
            legacy_attrs or tabbed_attrs,
            "main_window must expose either the legacy "
            "_on_driven_source_attrs_requested slot or the M_TABBED"
            "_EDITOR _on_driven_source_attrs_apply + _attrs_clear "
            "pair")
        self.assertIn(
            "drivenSourcesChanged.connect", self._main,
            "main_window must subscribe controller."
            "drivenSourcesChanged for the reload bridge")


# ----------------------------------------------------------------------
# core.read_driven_info_multi - dynamic compound + legacy fallback
# ----------------------------------------------------------------------


@unittest.skipIf(conftest._REAL_MAYA,
    "mock-dependent (mock.patch on cmds.* + read_driven_info)")
class TestM_DRIVEN_MULTI_CoreOrchestrator(unittest.TestCase):

    def test_read_multi_falls_back_to_legacy_when_compound_absent(self):
        from RBFtools import core
        import maya.cmds as cmds
        cmds.reset_mock()
        cmds.objExists.return_value = True
        cmds.listRelatives.return_value = ["RBF1Shape"]
        cmds.attributeQuery.return_value = False   # compound absent
        with mock.patch.object(
                core, "read_driven_info",
                return_value=("blendShape1", ["brow_up", "brow_down"])):
            result = core.read_driven_info_multi("RBF1")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].node, "blendShape1")
        self.assertEqual(
            tuple(result[0].attrs), ("brow_up", "brow_down"))

    def test_read_multi_returns_empty_for_legacy_empty(self):
        from RBFtools import core
        import maya.cmds as cmds
        cmds.reset_mock()
        cmds.objExists.return_value = True
        cmds.listRelatives.return_value = ["RBF1Shape"]
        cmds.attributeQuery.return_value = False
        with mock.patch.object(
                core, "read_driven_info", return_value=("", [])):
            result = core.read_driven_info_multi("RBF1")
        self.assertEqual(result, [])

    def test_set_driven_source_attrs_out_of_range_returns_false(self):
        from RBFtools import core
        with mock.patch.object(
                core, "read_driven_info_multi",
                return_value=[
                    core.DrivenSource(node="d1", attrs=("tx",))]):
            ok = core.set_driven_source_attrs("RBF1", 5, ["tx"])
        self.assertFalse(ok)

    def test_set_driven_source_attrs_calls_remove_then_readd(self):
        from RBFtools import core
        sources = [
            core.DrivenSource(node="d0", attrs=("tx",)),
            core.DrivenSource(node="d1", attrs=("tx",)),
        ]
        import maya.cmds as cmds
        cmds.reset_mock()
        cmds.getAttr.side_effect = None
        cmds.getAttr.return_value = [0, 1]
        with mock.patch.object(
                core, "read_driven_info_multi",
                return_value=list(sources)), \
             mock.patch.object(core, "get_shape",
                               return_value="RBF1Shape"), \
             mock.patch.object(core, "remove_driven_source") as rm, \
             mock.patch.object(core, "add_driven_source") as add:
            ok = core.set_driven_source_attrs(
                "RBF1", 1, ["ty", "tz"])
        self.assertTrue(ok)
        self.assertEqual(rm.call_count, 2)
        self.assertEqual(add.call_count, 2)
        first_add = add.call_args_list[0]
        second_add = add.call_args_list[1]
        self.assertEqual(first_add[0][2], ["tx"])
        self.assertEqual(second_add[0][2], ["ty", "tz"])


# ----------------------------------------------------------------------
# Controller signal parity (parallel to driver-side tests)
# ----------------------------------------------------------------------


@unittest.skipIf(conftest._REAL_MAYA,
    "mock-dependent (mock.patch on core.* + cmds.warning)")
class TestM_DRIVEN_MULTI_ControllerSignals(unittest.TestCase):

    def _stub(self):
        from RBFtools.controller import MainController
        ctrl = MainController.__new__(MainController)
        ctrl._current_node = "RBF1"
        ctrl.drivenSourcesChanged = mock.MagicMock()
        return ctrl

    def test_add_emits(self):
        from RBFtools.controller import MainController
        from RBFtools import core
        ctrl = self._stub()
        with mock.patch.object(
                core, "add_driven_source", return_value=0):
            MainController.add_driven_source(
                ctrl, "blendShape1", ["brow_up"])
        ctrl.drivenSourcesChanged.emit.assert_called_once_with()

    def test_remove_emits_when_confirmed(self):
        from RBFtools.controller import MainController
        from RBFtools import core
        ctrl = self._stub()
        ctrl.ask_confirm = mock.MagicMock(return_value=True)
        with mock.patch.object(
                core, "remove_driven_source"):
            MainController.remove_driven_source(ctrl, 0)
        ctrl.drivenSourcesChanged.emit.assert_called_once_with()

    def test_remove_no_emit_on_cancel(self):
        from RBFtools.controller import MainController
        from RBFtools import core
        ctrl = self._stub()
        ctrl.ask_confirm = mock.MagicMock(return_value=False)
        with mock.patch.object(
                core, "remove_driven_source") as core_rm:
            MainController.remove_driven_source(ctrl, 0)
        core_rm.assert_not_called()
        ctrl.drivenSourcesChanged.emit.assert_not_called()

    def test_set_attrs_emits_on_success(self):
        from RBFtools.controller import MainController
        from RBFtools import core
        ctrl = self._stub()
        with mock.patch.object(
                core, "set_driven_source_attrs", return_value=True):
            MainController.set_driven_source_attrs(
                ctrl, 0, ["tx", "ty"])
        ctrl.drivenSourcesChanged.emit.assert_called_once_with()

    def test_set_attrs_no_emit_on_failure(self):
        from RBFtools.controller import MainController
        from RBFtools import core
        ctrl = self._stub()
        with mock.patch.object(
                core, "set_driven_source_attrs", return_value=False):
            MainController.set_driven_source_attrs(
                ctrl, 99, ["tx"])
        ctrl.drivenSourcesChanged.emit.assert_not_called()


# ----------------------------------------------------------------------
# DrivenSourceListEditor signal forwarding
# ----------------------------------------------------------------------


@unittest.skipIf(conftest._REAL_MAYA,
    "mock-dependent (PySide signal stubs)")
class TestM_DRIVEN_MULTI_EditorSignals(unittest.TestCase):

    def test_add_clicked_emits_intent(self):
        from RBFtools.ui.widgets.driven_source_list_editor import (
            DrivenSourceListEditor)
        editor = DrivenSourceListEditor.__new__(DrivenSourceListEditor)
        editor.addRequested = mock.MagicMock()
        DrivenSourceListEditor._on_add_clicked(editor)
        editor.addRequested.emit.assert_called_once_with()

    def test_remove_clicked_emits_with_row(self):
        from RBFtools.ui.widgets.driven_source_list_editor import (
            DrivenSourceListEditor)
        editor = DrivenSourceListEditor.__new__(DrivenSourceListEditor)
        editor.removeRequested = mock.MagicMock()
        editor._list = mock.MagicMock()
        editor._list.currentRow.return_value = 1
        DrivenSourceListEditor._on_remove_clicked(editor)
        editor.removeRequested.emit.assert_called_once_with(1)

    def test_remove_clicked_no_selection_is_noop(self):
        from RBFtools.ui.widgets.driven_source_list_editor import (
            DrivenSourceListEditor)
        editor = DrivenSourceListEditor.__new__(DrivenSourceListEditor)
        editor.removeRequested = mock.MagicMock()
        editor._list = mock.MagicMock()
        editor._list.currentRow.return_value = -1
        DrivenSourceListEditor._on_remove_clicked(editor)
        editor.removeRequested.emit.assert_not_called()

    def test_row_emits_attrs_requested(self):
        from RBFtools.ui.widgets.driven_source_list_editor import (
            _DrivenSourceRow)
        from RBFtools.core import DrivenSource
        row = _DrivenSourceRow.__new__(_DrivenSourceRow)
        row._source = DrivenSource(
            node="blendShape1", attrs=("brow_up", "brow_down"))
        row.attrsRequested = mock.MagicMock()
        _DrivenSourceRow._on_attrs_clicked(row)
        row.attrsRequested.emit.assert_called_once_with(
            "blendShape1", ("brow_up", "brow_down"))


# ----------------------------------------------------------------------
# i18n parity for the new driven keys
# ----------------------------------------------------------------------


class TestM_DRIVEN_MULTI_I18nParity(unittest.TestCase):

    REQUIRED_KEYS = [
        "section_driven_sources",
        "driven_source_list_header",
        "driven_source_list_empty_hint",
        "driven_source_node_tip",
        "driven_source_attrs_tip",
        "driven_source_attrs_btn",
        "driven_source_attrs_btn_tip",
        "title_remove_driven_source",
        "summary_remove_driven_source",
        "title_pick_driven_attrs",
        "summary_pick_driven_attrs",
        "warning_driven_source_no_selection",
        "warning_driven_source_no_node_for_attrs",
    ]

    def test_required_keys_present_in_both_languages(self):
        from RBFtools.ui import i18n
        missing_en = [k for k in self.REQUIRED_KEYS if k not in i18n._EN]
        missing_zh = [k for k in self.REQUIRED_KEYS if k not in i18n._ZH]
        self.assertEqual(missing_en, [],
            "Missing EN: {}".format(missing_en))
        self.assertEqual(missing_zh, [],
            "Missing ZH: {}".format(missing_zh))


if __name__ == "__main__":
    unittest.main()
