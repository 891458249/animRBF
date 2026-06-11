"""M_DISCONNECT_FIX + M_SELECT_SEMANTIC_FIX (Phase 1, P0 + P1
2026-04-27).

Two related TD-reported bugs:

1. Disconnect button on a Driver tab was observed to leave the
   selected attrs WIRED to input[]. Root cause: the previous
   path went through set_*_source_attrs(idx, []) which does
   remove-all + re-add-all via add_*_source - heavy + reliant on
   `cmds.setAttr(plug, 0, type="stringArray")` round-tripping
   cleanly. The fix introduces dedicated
   `disconnect_*_source_attrs` core fns that directly
   disconnectAttr the source's input[]/output[] slice + clear
   the attrs metadata, without rebuilding any other source.

2. The Select button on each tab used to act as
   "rebind from current Maya selection" (cmds.ls(selection)
   filter + remove + re-add). The new semantic is "select the
   bone in the Maya viewport" (cmds.select(node, replace=True))
   so the TD can jump to the bone's location in the scene -
   matches the AnimaRbfSolver reference UX.

Coverage:

* core: disconnect_driver_source_attrs / disconnect_driven_source_attrs
  - happy path: directly disconnects the source's wires
  - empty source: idempotent True return (no-op)
  - out-of-range: False return + warning
* controller: wrappers emit *SourcesChanged on success only
* main_window: Disconnect slot calls the new direct-disconnect
  controller method (NOT the legacy set_*_source_attrs path);
  Select slot calls cmds.select(node, replace=True) instead of
  rebinding via cmds.ls(selection)
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
_CORE_PY = os.path.join(
    _REPO_ROOT, "modules", "RBFtools", "scripts", "RBFtools", "core.py")
_CONTROLLER_PY = os.path.join(
    _REPO_ROOT, "modules", "RBFtools", "scripts", "RBFtools",
    "controller.py")


def _read(p):
    with open(p, "r", encoding="utf-8") as fh:
        return fh.read()


# ----------------------------------------------------------------------
# Source-scan: API surface across the four layers
# ----------------------------------------------------------------------


class TestM_DISCONNECT_FIX_SourceScan(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._core = _read(_CORE_PY)
        cls._controller = _read(_CONTROLLER_PY)
        cls._main = _read(_MAIN_WINDOW)

    def test_core_direct_disconnect_fns_present(self):
        for fn in ("def disconnect_driver_source_attrs",
                   "def disconnect_driven_source_attrs"):
            self.assertIn(fn, self._core,
                "core.py missing {}".format(fn))

    def test_controller_wrappers_present(self):
        for fn in ("def disconnect_driver_source_attrs",
                   "def disconnect_driven_source_attrs"):
            self.assertIn(fn, self._controller,
                "controller.py missing {}".format(fn))

    def test_main_window_slots_call_direct_disconnect(self):
        # The Disconnect slot now invokes the direct-disconnect
        # controller method, not the legacy set_*_source_attrs(idx, []).
        self.assertIn(
            "self._ctrl.disconnect_driver_source_attrs(",
            self._main,
            "_on_driver_source_attrs_clear must call "
            "controller.disconnect_driver_source_attrs (P0 fix)")
        self.assertIn(
            "self._ctrl.disconnect_driven_source_attrs(",
            self._main,
            "_on_driven_source_attrs_clear must call "
            "controller.disconnect_driven_source_attrs (P0 fix)")


class TestM_SELECT_SEMANTIC_FIX_SourceScan(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._main = _read(_MAIN_WINDOW)

    def test_select_helper_replaces_rebind_helper(self):
        self.assertIn(
            "def _select_source_node_in_viewport", self._main,
            "main_window must define the new viewport-select helper")
        self.assertNotIn(
            "def _bind_source_node_from_selection", self._main,
            "the legacy rebind helper must be removed - Select "
            "now means 'select bone in viewport', not 'rebind "
            "from current selection'")

    def test_select_uses_cmds_select_replace(self):
        # cmds.select(node, replace=True) is the AnimaRbfSolver
        # semantic.
        self.assertIn("cmds.select(", self._main)
        self.assertIn("replace=True", self._main)

    def test_select_slot_calls_helper(self):
        for slot in ("_on_driver_source_select_node",
                     "_on_driven_source_select_node"):
            self.assertIn(slot, self._main)
        self.assertIn(
            "self._select_source_node_in_viewport(", self._main)


# ----------------------------------------------------------------------
# core.disconnect_driver_source_attrs lifecycle
# ----------------------------------------------------------------------


@unittest.skipIf(conftest._REAL_MAYA,
    "mock-dependent (mock.patch on cmds + read_driver_info_multi)")
class TestM_DISCONNECT_FIX_CoreDriver(unittest.TestCase):

    def test_out_of_range_returns_false(self):
        from RBFtools import core
        with mock.patch.object(
                core, "read_driver_info_multi",
                return_value=[
                    core.DriverSource(
                        node="d1", attrs=("tx",),
                        weight=1.0, encoding=0)]):
            ok = core.disconnect_driver_source_attrs("RBF1", 5)
        self.assertFalse(ok)

    def test_empty_attrs_returns_true_noop(self):
        """Idempotent path: source already empty -> True, no
        cmds.disconnectAttr / setAttr calls."""
        from RBFtools import core
        import maya.cmds as cmds
        cmds.reset_mock()
        cmds.disconnectAttr.reset_mock()
        cmds.setAttr.reset_mock()
        with mock.patch.object(
                core, "read_driver_info_multi",
                return_value=[
                    core.DriverSource(
                        node="d1", attrs=tuple(),
                        weight=1.0, encoding=0)]), \
             mock.patch.object(core, "_exists",
                               return_value=True), \
             mock.patch.object(core, "get_shape",
                               return_value="RBF1Shape"):
            ok = core.disconnect_driver_source_attrs("RBF1", 0)
        self.assertTrue(ok)
        cmds.disconnectAttr.assert_not_called()
        cmds.setAttr.assert_not_called()

    def test_happy_path_disconnects_each_input_wire(self):
        """M_CONNECT_DISCONNECT_FIX (2026-04-28): the disconnect
        path now routes through _disconnect_or_purge (atomic
        protocol reuse). Assert the public contract — function
        returns True + each attr triggers exactly one purge call —
        instead of locking the bare cmds.disconnectAttr shape."""
        from RBFtools import core
        import maya.cmds as cmds
        cmds.reset_mock()
        with mock.patch.object(
                core, "read_driver_info_multi",
                return_value=[
                    core.DriverSource(
                        node="drv1", attrs=("tx", "ty"),
                        weight=1.0, encoding=0)]), \
             mock.patch.object(core, "_exists",
                               return_value=True), \
             mock.patch.object(core, "get_shape",
                               return_value="RBF1Shape"), \
             mock.patch.object(core, "_subscript_of_existing_input",
                               side_effect=[0, 1]), \
             mock.patch.object(core, "_disconnect_or_purge",
                               return_value=True) as purge:
            ok = core.disconnect_driver_source_attrs("RBF1", 0)
        self.assertTrue(ok)
        self.assertEqual(purge.call_count, 2)
        first = purge.call_args_list[0].args
        second = purge.call_args_list[1].args
        self.assertEqual(first[1], "input")
        self.assertEqual(first[2], 0)
        self.assertEqual(first[3], "drv1.tx")
        self.assertEqual(second[2], 1)
        self.assertEqual(second[3], "drv1.ty")
        # MStringArray cleared on driverSource[0].
        clear_calls = [
            c for c in cmds.setAttr.call_args_list
            if "driverSource[0].driverSource_attrs" in c[0][0]
        ]
        self.assertGreaterEqual(len(clear_calls), 1)
        self.assertEqual(clear_calls[0][0][1], 0)
        self.assertEqual(clear_calls[0][1].get("type"), "stringArray")

    def test_base_offset_correct_with_prior_sources(self):
        """M_CONNECT_DISCONNECT_FIX: with the atomic-helper refactor,
        the input[] subscript is no longer computed locally — it
        comes from _subscript_of_existing_input. The test mocks
        that helper to return the correct offset (2) so source[1]
        with attrs ('rx',) reaches input[2] via _disconnect_or_purge."""
        from RBFtools import core
        import maya.cmds as cmds
        cmds.reset_mock()
        with mock.patch.object(
                core, "read_driver_info_multi",
                return_value=[
                    core.DriverSource(
                        node="drv0", attrs=("tx", "ty"),
                        weight=1.0, encoding=0),
                    core.DriverSource(
                        node="drv1", attrs=("rx",),
                        weight=1.0, encoding=0)]), \
             mock.patch.object(core, "_exists",
                               return_value=True), \
             mock.patch.object(core, "get_shape",
                               return_value="RBF1Shape"), \
             mock.patch.object(core, "_subscript_of_existing_input",
                               side_effect=[2]), \
             mock.patch.object(core, "_disconnect_or_purge",
                               return_value=True) as purge:
            ok = core.disconnect_driver_source_attrs("RBF1", 1)
        self.assertTrue(ok)
        self.assertEqual(purge.call_count, 1)
        args = purge.call_args_list[0].args
        self.assertEqual(args[1], "input")
        self.assertEqual(args[2], 2)
        self.assertEqual(args[3], "drv1.rx")


# ----------------------------------------------------------------------
# core.disconnect_driven_source_attrs lifecycle
# ----------------------------------------------------------------------


@unittest.skipIf(conftest._REAL_MAYA,
    "mock-dependent (mock.patch on cmds + read_driven_info_multi)")
class TestM_DISCONNECT_FIX_CoreDriven(unittest.TestCase):

    def test_happy_path_disconnects_output_wires(self):
        # M_CONNECT_DISCONNECT_FIX Bug 2 (2026-04-28): the disconnect
        # path now routes through _disconnect_or_purge (atomic
        # protocol reuse). We assert the public contract — the
        # function returns True on success — without locking the
        # internal cmds.disconnectAttr call shape (the internals
        # are now subject to skipConversionNodes resolution +
        # _purge_unit_conversion delete-vs-disconnect dispatch which
        # is exercised by test_m_unitconv_purge / test_m_remove_multi).
        from RBFtools import core
        import maya.cmds as cmds
        cmds.reset_mock()
        cmds.attributeQuery.return_value = True
        with mock.patch.object(
                core, "read_driven_info_multi",
                return_value=[
                    core.DrivenSource(
                        node="dvn1",
                        attrs=("translateX", "translateY"))]), \
             mock.patch.object(core, "_exists",
                               return_value=True), \
             mock.patch.object(core, "get_shape",
                               return_value="RBF1Shape"), \
             mock.patch.object(core, "_subscript_of_existing_output",
                               side_effect=[0, 1]), \
             mock.patch.object(core, "_disconnect_or_purge",
                               return_value=True) as purge:
            ok = core.disconnect_driven_source_attrs("RBF1", 0)
        self.assertTrue(ok)
        # Each attr triggers exactly one _disconnect_or_purge call.
        self.assertEqual(purge.call_count, 2)
        # First call -> output[0] for translateX; second -> output[1]
        # for translateY. (idx, plug) come back via the side_effect
        # mock.
        first_args = purge.call_args_list[0].args
        second_args = purge.call_args_list[1].args
        self.assertEqual(first_args[0], "RBF1Shape")
        self.assertEqual(first_args[1], "output")
        self.assertEqual(first_args[2], 0)
        self.assertEqual(first_args[3], "dvn1.translateX")
        self.assertEqual(second_args[2], 1)
        self.assertEqual(second_args[3], "dvn1.translateY")


# ----------------------------------------------------------------------
# controller wrappers emit signal on success
# ----------------------------------------------------------------------


@unittest.skipIf(conftest._REAL_MAYA,
    "mock-dependent (mock.patch on core.*)")
class TestM_DISCONNECT_FIX_ControllerSignals(unittest.TestCase):

    def _stub_controller(self):
        from RBFtools.controller import MainController
        ctrl = MainController.__new__(MainController)
        ctrl._current_node = "RBF1"
        ctrl.driverSourcesChanged = mock.MagicMock()
        ctrl.drivenSourcesChanged = mock.MagicMock()
        # M_P0_TAB_REMOVE_SPARSE_FIX passthrough.
        ctrl._list_idx_to_sparse = lambda role, idx: int(idx)
        return ctrl

    def test_driver_disconnect_emits_on_success(self):
        from RBFtools.controller import MainController
        from RBFtools import core
        ctrl = self._stub_controller()
        with mock.patch.object(
                core, "disconnect_driver_source_attrs",
                return_value=True):
            MainController.disconnect_driver_source_attrs(ctrl, 0)
        ctrl.driverSourcesChanged.emit.assert_called_once_with()

    def test_driver_disconnect_no_emit_on_failure(self):
        from RBFtools.controller import MainController
        from RBFtools import core
        ctrl = self._stub_controller()
        with mock.patch.object(
                core, "disconnect_driver_source_attrs",
                return_value=False):
            MainController.disconnect_driver_source_attrs(ctrl, 99)
        ctrl.driverSourcesChanged.emit.assert_not_called()

    def test_driven_disconnect_emits_on_success(self):
        from RBFtools.controller import MainController
        from RBFtools import core
        ctrl = self._stub_controller()
        with mock.patch.object(
                core, "disconnect_driven_source_attrs",
                return_value=True):
            MainController.disconnect_driven_source_attrs(ctrl, 0)
        ctrl.drivenSourcesChanged.emit.assert_called_once_with()


# ----------------------------------------------------------------------
# Select button -> cmds.select(node, replace=True)
# ----------------------------------------------------------------------


@unittest.skipIf(conftest._REAL_MAYA,
    "mock-dependent (mock.patch on cmds + controller stubs)")
class TestM_SELECT_SEMANTIC_FIX_Lifecycle(unittest.TestCase):

    def _make_window(self, driver_sources=None, driven_sources=None):
        from RBFtools.ui.main_window import RBFToolsWindow
        win = RBFToolsWindow.__new__(RBFToolsWindow)
        win._ctrl = mock.MagicMock()
        win._ctrl.read_driver_sources.return_value = (
            driver_sources or [])
        win._ctrl.read_driven_sources.return_value = (
            driven_sources or [])
        return win

    def test_select_calls_cmds_select_replace_true(self):
        from RBFtools.ui.main_window import RBFToolsWindow
        from RBFtools.core import DriverSource
        win = self._make_window(
            driver_sources=[DriverSource(
                node="drv1", attrs=tuple(),
                weight=1.0, encoding=0)])
        import maya.cmds as cmds
        cmds.reset_mock()
        cmds.objExists.return_value = True
        RBFToolsWindow._on_driver_source_select_node(win, 0)
        cmds.select.assert_called_once_with("drv1", replace=True)

    def test_select_warns_when_node_missing(self):
        from RBFtools.ui.main_window import RBFToolsWindow
        from RBFtools.core import DriverSource
        win = self._make_window(
            driver_sources=[DriverSource(
                node="drv1", attrs=tuple(),
                weight=1.0, encoding=0)])
        import maya.cmds as cmds
        cmds.reset_mock()
        cmds.objExists.return_value = False
        RBFToolsWindow._on_driver_source_select_node(win, 0)
        cmds.select.assert_not_called()
        cmds.warning.assert_called_once()

    def test_select_warns_when_node_empty(self):
        from RBFtools.ui.main_window import RBFToolsWindow
        from RBFtools.core import DriverSource
        win = self._make_window(
            driver_sources=[DriverSource(
                node="", attrs=tuple(),
                weight=1.0, encoding=0)])
        import maya.cmds as cmds
        cmds.reset_mock()
        RBFToolsWindow._on_driver_source_select_node(win, 0)
        cmds.select.assert_not_called()

    def test_select_does_not_rebind_or_remove(self):
        """The new Select must not rebuild source state - no
        remove_*_source / add_*_source / set_*_source_attrs
        controller calls."""
        from RBFtools.ui.main_window import RBFToolsWindow
        from RBFtools.core import DriverSource
        win = self._make_window(
            driver_sources=[DriverSource(
                node="drv1", attrs=("tx",),
                weight=1.0, encoding=0)])
        import maya.cmds as cmds
        cmds.reset_mock()
        cmds.objExists.return_value = True
        RBFToolsWindow._on_driver_source_select_node(win, 0)
        win._ctrl.remove_driver_source.assert_not_called()
        win._ctrl.add_driver_source.assert_not_called()
        win._ctrl.set_driver_source_attrs.assert_not_called()

    def test_driven_select_uses_cmds_select(self):
        from RBFtools.ui.main_window import RBFToolsWindow
        from RBFtools.core import DrivenSource
        win = self._make_window(
            driven_sources=[DrivenSource(
                node="dvn1", attrs=tuple())])
        import maya.cmds as cmds
        cmds.reset_mock()
        cmds.objExists.return_value = True
        RBFToolsWindow._on_driven_source_select_node(win, 0)
        cmds.select.assert_called_once_with("dvn1", replace=True)


# ----------------------------------------------------------------------
# i18n parity for the new warning keys
# ----------------------------------------------------------------------


class TestM_SELECT_SEMANTIC_FIX_I18nParity(unittest.TestCase):

    def test_required_keys(self):
        from RBFtools.ui import i18n
        for k in ("warning_source_node_empty",
                  "warning_source_node_missing"):
            self.assertIn(k, i18n._EN, "missing EN key {}".format(k))
            self.assertIn(k, i18n._ZH, "missing ZH key {}".format(k))


if __name__ == "__main__":
    unittest.main()
