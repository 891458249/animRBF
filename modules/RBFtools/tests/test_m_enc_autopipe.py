# -*- coding: utf-8 -*-
"""M_ENC_AUTOPIPE (2026-04-29) — Generic-mode inputEncoding switch
auto-derives ``driverInputRotateOrder[]`` from connected drivers.

User report (2026-04-29): "切 Input Encoding -> 后端自动按选中编码处理
driver 数据 -> RBF compute 用新编码后的输入向量"; TD expects zero
manual configuration. F1/F2 现状核查 confirmed:

  * C++ ``compute()`` already dispatches all 5 encodings
    (RBFtools.cpp:2606-2609) AND consumes
    ``driverInputRotateOrder[]`` (cpp:1182-1209 + 2447-2624 +
    encodeEulerToQuaternion at 3135). No C++ change needed.

  * ``core._resolve_driver_rotate_order`` already implements the
    per-driver rotateOrder connection but is wired ONLY in the
    Matrix-mode branch of ``add_driver_source`` (core.py:1264).
    Generic mode (the v5 default for non-Raw inputEncoding) has
    NO auto-derive path — switching to ExpMap / SwingTwist
    leaves ``driverInputRotateOrder[]`` empty, the C++ falls back
    to xyz=0 for every driver, silently mis-encoding any
    non-XYZ joint.

Fix:

  * ``core.auto_resolve_generic_rotate_orders(node, encoding)``
    — public helper that walks ``driverSource[]`` and reuses
    ``_resolve_driver_rotate_order`` per entry when encoding
    consumes rotateOrder (BendRoll / ExpMap / SwingTwist).
    Encodings 0 / 1 (Raw / Quaternion) clear the multi so a
    subsequent encoding switch rederives from the live driver
    topology rather than reusing stale entries.

  * ``controller.on_input_encoding_changed(idx)`` — side-effect
    slot that runs the auto-derive after the regular
    ``set_attribute("inputEncoding", idx)`` write, then re-emits
    ``settingsLoaded`` + ``driverSourcesChanged`` so the UI
    repopulates the rotate-order list editor.

  * ``rbf_section.inputEncodingChanged`` signal — emitted
    alongside the existing ``attributeChanged("inputEncoding")``
    so the controller side-effect runs without overloading
    generic ``set_attribute`` dispatch.

  * ``rbf_section._update_encoding_visibility`` now hides the
    rotate-order editor for BOTH Raw (0) AND Quaternion (1)
    since neither consumes rotateOrder.

  * ``main_window`` wires
    ``rbf_section.inputEncodingChanged ->
    ctrl.on_input_encoding_changed``.

PERMANENT GUARDS — T_INPUT_ENCODING_AUTOPIPE.
"""

from __future__ import absolute_import

import os
import unittest
from unittest import mock

import conftest


_REPO_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
_CORE_PY = os.path.join(
    _REPO_ROOT, "modules", "RBFtools", "scripts", "RBFtools",
    "core.py")
_CTRL_PY = os.path.join(
    _REPO_ROOT, "modules", "RBFtools", "scripts", "RBFtools",
    "controller.py")
_RBF_SECTION_PY = os.path.join(
    _REPO_ROOT, "modules", "RBFtools", "scripts", "RBFtools",
    "ui", "widgets", "rbf_section.py")
_MAIN_WINDOW_PY = os.path.join(
    _REPO_ROOT, "modules", "RBFtools", "scripts", "RBFtools",
    "ui", "main_window.py")


def _read(p):
    with open(p, "r", encoding="utf-8") as fh:
        return fh.read()


# ----------------------------------------------------------------------
# PERMANENT GUARD T_INPUT_ENCODING_AUTOPIPE
# ----------------------------------------------------------------------


class T_INPUT_ENCODING_AUTOPIPE(unittest.TestCase):
    """PERMANENT GUARD — DO NOT REMOVE.

    Locks the four-file wiring chain that turns inputEncoding
    selection into a self-configuring rotateOrder pipe in
    Generic mode."""

    @classmethod
    def setUpClass(cls):
        cls._core = _read(_CORE_PY)
        cls._ctrl = _read(_CTRL_PY)
        cls._rbf = _read(_RBF_SECTION_PY)
        cls._mw = _read(_MAIN_WINDOW_PY)

    def test_PERMANENT_a_core_helper_present(self):
        self.assertIn(
            "def auto_resolve_generic_rotate_orders(node, encoding):",
            self._core,
            "core.py missing public helper "
            "auto_resolve_generic_rotate_orders.")

    def test_PERMANENT_b_core_helper_walks_driver_source(self):
        body = self._core.split(
            "def auto_resolve_generic_rotate_orders("
        )[1].split("\ndef ")[0]
        self.assertIn(".driverSource", body,
            "auto_resolve_generic_rotate_orders MUST walk "
            "driverSource[] sparse multi indices.")
        self.assertIn("_resolve_driver_rotate_order(", body,
            "auto_resolve_generic_rotate_orders MUST reuse the "
            "existing _resolve_driver_rotate_order helper to "
            "stay in lock-step with the Matrix-mode branch.")

    def test_PERMANENT_c_core_helper_clears_for_raw_and_quat(self):
        body = self._core.split(
            "def auto_resolve_generic_rotate_orders("
        )[1].split("\ndef ")[0]
        # Raw / Quat must result in clearing the multi (no stale
        # entries when later switching to ExpMap).
        self.assertIn("write_driver_rotate_orders(node, [])", body,
            "Raw (0) / Quaternion (1) branch MUST clear the "
            "driverInputRotateOrder multi via "
            "write_driver_rotate_orders([]).")
        # Encoding membership tuple covers exactly 2/3/4.
        self.assertIn("_ENCODINGS_NEED_ROTATE_ORDER", body,
            "Helper MUST gate via the canonical encoding-set "
            "constant so the rule stays single-sourced.")

    def test_PERMANENT_d_controller_slot_present(self):
        # M_P1_ENC_COMBO_FIX (2026-04-29) updated this guard: the
        # original M_ENC_AUTOPIPE contract called self._load_settings()
        # to round-trip through settingsLoaded -> rbf_section.load,
        # but that path triggered a setCurrentIndex() on the
        # inputEncoding combo from the (then-incomplete)
        # get_all_settings dict, bouncing the user's pick back to
        # Raw. The P1 fix replaced the cascade with a NARROW signal
        # carrying just the rotate-order list values, leaving the
        # combo selection alone.
        self.assertIn(
            "def on_input_encoding_changed(self, idx):",
            self._ctrl,
            "controller missing on_input_encoding_changed slot.")
        body = self._ctrl.split(
            "def on_input_encoding_changed(self, idx):"
        )[1].split("\n    def ")[0]
        self.assertIn(
            "core.auto_resolve_generic_rotate_orders(", body,
            "Slot MUST call the core helper.")
        self.assertNotIn(
            "self._load_settings()", body,
            "P1 regression-fix contract: slot MUST NOT call "
            "_load_settings — that cascade caused the inputEncoding "
            "combo bounce-back. Use the narrow rotateOrderEditorReload"
            " signal instead.")
        self.assertIn(
            "self.rotateOrderEditorReload.emit(", body,
            "Slot MUST emit the narrow rotateOrderEditorReload "
            "signal carrying the freshly read rotate-order values.")
        self.assertIn(
            "self.driverSourcesChanged.emit()", body,
            "Slot MUST emit driverSourcesChanged to keep the "
            "tabbed editors in sync (mirrors add/remove driver "
            "flows).")

    def test_PERMANENT_e_rbf_section_signal_emit(self):
        self.assertIn(
            "inputEncodingChanged = QtCore.Signal(int)",
            self._rbf,
            "rbf_section MUST declare inputEncodingChanged "
            "Qt signal.")
        body = self._rbf.split(
            "def _on_input_encoding(self, idx):"
        )[1].split("\n    def ")[0]
        self.assertIn(
            "self.inputEncodingChanged.emit(", body,
            "_on_input_encoding MUST emit inputEncodingChanged "
            "alongside the generic attributeChanged write so "
            "the controller side-effect runs.")

    def test_PERMANENT_f_visibility_quat_hidden(self):
        body = self._rbf.split(
            "def _update_encoding_visibility(self, idx):"
        )[1].split("\n    def ")[0]
        # The visibility rule MUST gate on the same set the C++
        # consumes (2/3/4). Both Raw (0) and Quat (1) hide.
        self.assertIn("(2, 3, 4)", body,
            "_update_encoding_visibility MUST hide for both "
            "Raw (0) AND Quaternion (1); only encodings that "
            "consume rotateOrder in C++ applyEncodingToBlock "
            "show the editor.")

    def test_PERMANENT_g_main_window_wires_signal(self):
        self.assertIn(
            "self._rbf_section.inputEncodingChanged.connect(",
            self._mw,
            "main_window MUST wire inputEncodingChanged to "
            "the controller side-effect slot.")
        self.assertIn(
            "ctrl.on_input_encoding_changed",
            self._mw,
            "main_window MUST wire to "
            "ctrl.on_input_encoding_changed.")


# ----------------------------------------------------------------------
# Mock E2E — runtime auto-derive behavior
# ----------------------------------------------------------------------


@unittest.skipIf(conftest._REAL_MAYA,
    "mock-dependent (cmds + core stubs)")
class TestM_ENC_AUTOPIPE_RuntimeBehavior(unittest.TestCase):
    """Mock E2E catches the d01a964 'false-green' lesson: source-scan
    alone doesn't prove the runtime lookup chain works. Here we
    drive the helper with a fake cmds and assert the actual
    connectAttr / multi-clear calls land on the right plugs."""

    def _make_cmds_mock(self, driver_indices, drivers_by_idx,
                        existing_rotate_orders=None):
        """Build a cmds mock that answers:

        * shape = get_shape(node) -> "RBF1Shape"
        * driverSource multiIndices -> driver_indices
        * driverSource[d].driverSource_node listConnections ->
          [drivers_by_idx[d]]
        * driverInputRotateOrder multiIndices ->
          existing_rotate_orders or []
        * attributeQuery("rotateOrder", node=...) -> True
        """
        m = mock.MagicMock()
        # _exists() helper trip: ls and objExists must say Yes.
        m.objExists.return_value = True
        m.ls.return_value = ["RBF1Shape"]
        m.listRelatives.return_value = ["RBF1Shape"]
        m.nodeType.return_value = "RBFtools"

        def _multi_indices(plug, multiIndices=False):
            if not multiIndices:
                return None
            if plug.endswith(".driverSource"):
                return list(driver_indices)
            if plug.endswith(".driverInputRotateOrder"):
                return list(existing_rotate_orders or [])
            return []

        m.getAttr.side_effect = _multi_indices

        def _list_conns(plug, source=False, destination=False,
                        plugs=False):
            if ".driverSource_node" in plug:
                # Extract index from "...driverSource[d]....".
                d = int(
                    plug.split("driverSource[")[1].split("]")[0])
                drv = drivers_by_idx.get(d)
                return [drv] if drv else []
            if ".driverInputRotateOrder[" in plug:
                # Existing upstream feeders for the clear path.
                return ["someDriver.rotateOrder"]
            return []

        m.listConnections.side_effect = _list_conns
        m.attributeQuery.return_value = True
        m.connectAttr = mock.MagicMock()
        m.disconnectAttr = mock.MagicMock()
        m.warning = mock.MagicMock()
        return m

    def test_expmap_walks_drivers_and_connects_rotate_order(self):
        from RBFtools import core
        cmds_mock = self._make_cmds_mock(
            driver_indices=[0, 1, 2],
            drivers_by_idx={
                0: "ctrlArm", 1: "ctrlForearm", 2: "ctrlHand",
            },
        )
        with mock.patch.object(core, "cmds", cmds_mock):
            core.auto_resolve_generic_rotate_orders("RBF1", 3)
        # 3 connectAttr calls — one per driverSource entry.
        rotate_connects = [
            call for call in cmds_mock.connectAttr.call_args_list
            if ".rotateOrder" in str(call)
            and "driverInputRotateOrder" in str(call)
        ]
        self.assertEqual(len(rotate_connects), 3,
            "ExpMap (encoding=3) should auto-connect "
            "rotateOrder for ALL 3 driverSource entries; "
            "got {}: {}".format(
                len(rotate_connects), rotate_connects))
        # Slot index alignment: driverSource[d] -> rotateOrder[d].
        connect_strs = " ".join(
            str(c) for c in cmds_mock.connectAttr.call_args_list)
        for idx in (0, 1, 2):
            self.assertIn(
                "driverInputRotateOrder[{}]".format(idx),
                connect_strs,
                "Slot {} missing from connectAttr calls — "
                "driverSource[{}] -> driverInputRotateOrder[{}] "
                "alignment broken.".format(idx, idx, idx))

    def test_swingtwist_walks_drivers_same_as_expmap(self):
        # Encoding 4 (SwingTwist) takes the same auto-derive path
        # as 3 — the C++ math chain shares applyEncodingToBlock.
        from RBFtools import core
        cmds_mock = self._make_cmds_mock(
            driver_indices=[0],
            drivers_by_idx={0: "ctrlSpine"},
        )
        with mock.patch.object(core, "cmds", cmds_mock):
            core.auto_resolve_generic_rotate_orders("RBF1", 4)
        rotate_connects = [
            call for call in cmds_mock.connectAttr.call_args_list
            if ".rotateOrder" in str(call)
            and "driverInputRotateOrder[0]" in str(call)
        ]
        self.assertEqual(len(rotate_connects), 1)

    def test_raw_clears_existing_rotate_orders(self):
        from RBFtools import core
        cmds_mock = self._make_cmds_mock(
            driver_indices=[0, 1],
            drivers_by_idx={0: "ctrlA", 1: "ctrlB"},
            existing_rotate_orders=[0, 1],
        )
        # write_driver_rotate_orders calls set_node_multi_attr;
        # patch that path to verify the clear payload.
        with mock.patch.object(core, "cmds", cmds_mock):
            with mock.patch.object(
                    core, "set_node_multi_attr") as snma:
                core.auto_resolve_generic_rotate_orders("RBF1", 0)
        # set_node_multi_attr called with empty list = clear.
        snma.assert_called_once()
        args = snma.call_args[0]
        self.assertEqual(args[1], "driverInputRotateOrder")
        self.assertEqual(list(args[2]), [],
            "Raw (encoding=0) MUST clear "
            "driverInputRotateOrder by writing []; got "
            "{!r}".format(args[2]))

    def test_quaternion_clears_existing_rotate_orders(self):
        # Quaternion (1) is also a no-rotateOrder encoding.
        from RBFtools import core
        cmds_mock = self._make_cmds_mock(
            driver_indices=[0],
            drivers_by_idx={0: "ctrlA"},
            existing_rotate_orders=[0],
        )
        with mock.patch.object(core, "cmds", cmds_mock):
            with mock.patch.object(
                    core, "set_node_multi_attr") as snma:
                core.auto_resolve_generic_rotate_orders("RBF1", 1)
        snma.assert_called_once()
        self.assertEqual(list(snma.call_args[0][2]), [])

    def test_raw_with_no_existing_orders_is_noop(self):
        # No multi entries = no-op (no spurious clear write).
        from RBFtools import core
        cmds_mock = self._make_cmds_mock(
            driver_indices=[],
            drivers_by_idx={},
            existing_rotate_orders=[],
        )
        with mock.patch.object(core, "cmds", cmds_mock):
            with mock.patch.object(
                    core, "set_node_multi_attr") as snma:
                core.auto_resolve_generic_rotate_orders("RBF1", 0)
        snma.assert_not_called()

    def test_expmap_with_no_drivers_is_noop(self):
        from RBFtools import core
        cmds_mock = self._make_cmds_mock(
            driver_indices=[],
            drivers_by_idx={},
        )
        with mock.patch.object(core, "cmds", cmds_mock):
            core.auto_resolve_generic_rotate_orders("RBF1", 3)
        # No connectAttr for rotateOrder.
        rotate_connects = [
            call for call in cmds_mock.connectAttr.call_args_list
            if ".rotateOrder" in str(call)
        ]
        self.assertEqual(len(rotate_connects), 0)

    def test_controller_slot_calls_core_and_emits(self):
        # M_P1_ENC_COMBO_FIX: contract updated — slot now emits
        # the narrow rotateOrderEditorReload signal carrying the
        # freshly-read rotate-order list, instead of round-tripping
        # through _load_settings -> settingsLoaded -> rbf_section.load.
        from RBFtools import core
        from RBFtools.controller import MainController
        ctrl = MainController.__new__(MainController)
        ctrl._current_node = "RBF1"
        ctrl.rotateOrderEditorReload = mock.MagicMock()
        ctrl.driverSourcesChanged = mock.MagicMock()
        with mock.patch.object(
                core, "auto_resolve_generic_rotate_orders") as h:
            with mock.patch.object(
                    core, "read_driver_rotate_orders",
                    return_value=[2, 0, 5]):
                MainController.on_input_encoding_changed(ctrl, 3)
        h.assert_called_once_with("RBF1", 3)
        ctrl.rotateOrderEditorReload.emit.assert_called_once_with(
            [2, 0, 5])
        ctrl.driverSourcesChanged.emit.assert_called_once()

    def test_controller_slot_no_op_without_node(self):
        from RBFtools import core
        from RBFtools.controller import MainController
        ctrl = MainController.__new__(MainController)
        ctrl._current_node = None
        ctrl.rotateOrderEditorReload = mock.MagicMock()
        ctrl.driverSourcesChanged = mock.MagicMock()
        with mock.patch.object(
                core, "auto_resolve_generic_rotate_orders") as h:
            MainController.on_input_encoding_changed(ctrl, 3)
        h.assert_not_called()
        ctrl.rotateOrderEditorReload.emit.assert_not_called()


if __name__ == "__main__":
    unittest.main()
