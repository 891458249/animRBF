# -*- coding: utf-8 -*-
"""M_CONNECT_DISCONNECT_FIX (2026-04-28) — Connect/Disconnect P0 fix.

Bug 1 — Connect was unconditionally blocked when the source already
had any attrs connected (legacy M_TABBED_CONNECT_GUARD behavior).
The user spec 1.3 requires the Connect call to PROCEED so the
controller's set_*_source_attrs handles the overlap (break-then-
rebuild via _disconnect_or_purge) AND append flow uniformly.

Bug 2 — _on_disconnect_clicked silently dropped the selected attrs
list, so the downstream disconnect always fell back to "full
source" semantics. The user spec 2 requires Scene A (precise
disconnect when attrs selected) vs Scene B (full source when no
selection) vs Scene C (info dialog when nothing connected).

Coverage:
* PERMANENT GUARD #37 — T_CONNECT_GUARD_OVERLAP_AWARE: Bug 1 fix
  is locked. Source-scan + 3 mock E2E.
* PERMANENT GUARD #38 — T_DISCONNECT_PRECISE_ATTRS: Bug 2 fix is
  locked. Source-scan + 5 mock E2E.
* Driver/Driven symmetric mock E2E (5 scenes × 2 sides = 10 E2E).
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
_CTRL_PY = os.path.join(
    _REPO_ROOT, "modules", "RBFtools", "scripts", "RBFtools",
    "controller.py")
_CORE_PY = os.path.join(
    _REPO_ROOT, "modules", "RBFtools", "scripts", "RBFtools",
    "core.py")


def _read(p):
    with open(p, "r", encoding="utf-8") as fh:
        return fh.read()


# ----------------------------------------------------------------------
# PERMANENT GUARD #37 — T_CONNECT_GUARD_OVERLAP_AWARE
# ----------------------------------------------------------------------


class T_CONNECT_GUARD_OVERLAP_AWARE(unittest.TestCase):
    """PERMANENT GUARD #37 — DO NOT REMOVE.

    Bug 1 (M_CONNECT_DISCONNECT_FIX 2026-04-28): _guard_attrs_apply
    must NOT unconditionally block when the source already has any
    attrs connected. It must split overlapping vs new and let the
    Connect call PROCEED so the controller's set_*_source_attrs
    routes overlapping wires through _disconnect_or_purge (atomic
    protocol reuse) and appends pure-new wires.
    """

    @classmethod
    def setUpClass(cls):
        cls._main = _read(_MAIN_WINDOW)
        cls._core = _read(_CORE_PY)

    def test_PERMANENT_a_guard_returns_plan_dict(self):
        body = self._main.split(
            "def _guard_attrs_apply(self, role")[1].split(
            "\n    def ")[0]
        # Must compute overlapping + new lists.
        self.assertIn("overlapping", body)
        self.assertIn("new", body)
        # Must return a dict (not bool).
        self.assertIn("\"overlapping\":", body)

    def test_PERMANENT_b_guard_no_unconditional_block(self):
        body = self._main.split(
            "def _guard_attrs_apply(self, role")[1].split(
            "\n    def ")[0]
        # Legacy behavior: `if existing: ... return False` — MUST
        # be gone. Pin the precise removed pattern.
        self.assertNotIn("title_already_connected", body,
            "_guard_attrs_apply must NOT short-circuit on already-"
            "connected; the dialog title key was the legacy block "
            "marker — its presence here means Bug 1 has regressed.")

    def test_PERMANENT_c_set_attrs_uses_disconnect_or_purge(self):
        for fn in ("def set_driver_source_attrs",
                   "def set_driven_source_attrs"):
            body = self._core.split(fn)[1].split("\ndef ")[0]
            self.assertIn("_disconnect_or_purge", body,
                "{} must pre-clean overlapping wires via "
                "_disconnect_or_purge so unitConversion ghosts are "
                "purged before the rebuild fires (atomic protocol "
                "reuse — 加固 1).".format(fn))


@unittest.skipIf(conftest._REAL_MAYA,
    "mock-dependent (PySide / cmds stubs)")
class T_CONNECT_GUARD_OVERLAP_AWARE_E2E(unittest.TestCase):

    def _src(self, attrs):
        from RBFtools.core import DriverSource
        return DriverSource(node="drv1", attrs=tuple(attrs),
                            weight=1.0, encoding=0)

    def _dvn(self, attrs):
        from RBFtools.core import DrivenSource
        return DrivenSource(node="dvn1", attrs=tuple(attrs))

    def _make_window(self, driver_sources=None, driven_sources=None):
        from RBFtools.ui.main_window import RBFToolsWindow
        win = RBFToolsWindow.__new__(RBFToolsWindow)
        win._ctrl = mock.MagicMock()
        win._ctrl.read_driver_sources.return_value = (
            driver_sources or [])
        win._ctrl.read_driven_sources.return_value = (
            driven_sources or [])
        return win

    def test_E2E_driver_connect_proceeds_when_already_connected(self):
        from RBFtools.ui.main_window import RBFToolsWindow
        win = self._make_window(
            driver_sources=[self._src(["tx", "ty"])])
        with mock.patch(
                "RBFtools.ui.main_window.QtWidgets.QMessageBox"
        ) as mb:
            RBFToolsWindow._on_driver_source_attrs_apply(
                win, 0, ["tx", "ty", "rx"])
        # Guard MUST NOT surface a dialog (Bug 1 regression check).
        mb.information.assert_not_called()
        # Controller call MUST proceed with the full new attrs list.
        win._ctrl.set_driver_source_attrs.assert_called_once_with(
            0, ["tx", "ty", "rx"])

    def test_E2E_driven_connect_proceeds_when_already_connected(self):
        from RBFtools.ui.main_window import RBFToolsWindow
        win = self._make_window(
            driven_sources=[self._dvn(["ty"])])
        with mock.patch(
                "RBFtools.ui.main_window.QtWidgets.QMessageBox"
        ) as mb:
            RBFToolsWindow._on_driven_source_attrs_apply(
                win, 0, ["ty", "tz"])
        mb.information.assert_not_called()
        win._ctrl.set_driven_source_attrs.assert_called_once_with(
            0, ["ty", "tz"])

    def test_E2E_overlap_detection_in_plan_dict(self):
        from RBFtools.ui.main_window import RBFToolsWindow
        win = self._make_window(
            driver_sources=[self._src(["tx", "ty"])])
        plan = RBFToolsWindow._guard_attrs_apply(
            win, "driver", 0, ["tx", "rx"])
        self.assertIsNotNone(plan)
        self.assertEqual(plan["overlapping"], ["tx"])
        self.assertEqual(plan["new"], ["rx"])
        self.assertEqual(plan["existing"], ["tx", "ty"])


# ----------------------------------------------------------------------
# PERMANENT GUARD #38 — T_DISCONNECT_PRECISE_ATTRS
# ----------------------------------------------------------------------


class T_DISCONNECT_PRECISE_ATTRS(unittest.TestCase):
    """PERMANENT GUARD #38 — DO NOT REMOVE.

    Bug 2 (M_CONNECT_DISCONNECT_FIX 2026-04-28): the disconnect
    payload must travel from tab → signal → main_window slot →
    controller → core, carrying the user's selected attrs all the
    way. attrsClearRequested signal upgraded to Signal(int, list);
    4 layers extended to accept the attrs list; core's
    disconnect_*_source_attrs accepts attrs=None (Scene B) or a
    list (Scene A) and routes through _disconnect_or_purge.
    """

    @classmethod
    def setUpClass(cls):
        cls._tab = _read(_TABBED_PY)
        cls._main = _read(_MAIN_WINDOW)
        cls._ctrl = _read(_CTRL_PY)
        cls._core = _read(_CORE_PY)

    def test_PERMANENT_a_signal_payload_int_list(self):
        # The class-level Signal definition MUST be (int, list)
        # so the disconnect payload mirrors the connect payload.
        self.assertIn(
            "attrsClearRequested = QtCore.Signal(int, list)",
            self._tab,
            "attrsClearRequested MUST be Signal(int, list) per "
            "Bug 2 fix; Signal(int) was the pre-fix shape that "
            "silently dropped the attrs list.")

    def test_PERMANENT_b_disconnect_clicked_reads_attrs(self):
        body = self._tab.split(
            "def _on_disconnect_clicked(self):")[1].split(
            "\n    def ")[0]
        # Mirror _on_connect_clicked — read selected_attrs() then
        # emit with a 2-arg payload.
        self.assertIn("content.selected_attrs()", body)
        self.assertIn(
            "self.attrsClearRequested.emit(idx, list(attrs))", body)

    def test_PERMANENT_c_main_slot_signature_extended(self):
        for slot in ("def _on_driver_source_attrs_clear(self, index, attrs)",
                     "def _on_driven_source_attrs_clear(self, index, attrs)"):
            self.assertIn(slot, self._main,
                "main_window slot signature must accept attrs "
                "param; missing: {}".format(slot))

    def test_PERMANENT_d_controller_signature_extended(self):
        for sig in ("def disconnect_driver_source_attrs(self, index, attrs=None)",
                    "def disconnect_driven_source_attrs(self, index, attrs=None)"):
            self.assertIn(sig, self._ctrl,
                "controller signature must accept attrs=None; "
                "missing: {}".format(sig))

    def test_PERMANENT_e_core_signature_extended(self):
        for sig in ("def disconnect_driver_source_attrs(node, index, attrs=None)",
                    "def disconnect_driven_source_attrs(node, index, attrs=None)"):
            self.assertIn(sig, self._core,
                "core signature must accept attrs=None; "
                "missing: {}".format(sig))

    def test_PERMANENT_f_core_calls_disconnect_or_purge(self):
        for fn in ("def disconnect_driver_source_attrs",
                   "def disconnect_driven_source_attrs"):
            body = self._core.split(fn)[1].split("\ndef ")[0]
            self.assertIn("_disconnect_or_purge", body,
                "{} body must call _disconnect_or_purge (atomic "
                "protocol reuse) — 加固 1".format(fn))


@unittest.skipIf(conftest._REAL_MAYA,
    "mock-dependent (PySide / cmds stubs)")
class T_DISCONNECT_PRECISE_ATTRS_E2E(unittest.TestCase):

    def _src(self, attrs):
        from RBFtools.core import DriverSource
        return DriverSource(node="drv1", attrs=tuple(attrs),
                            weight=1.0, encoding=0)

    def _dvn(self, attrs):
        from RBFtools.core import DrivenSource
        return DrivenSource(node="dvn1", attrs=tuple(attrs))

    def _make_window(self, driver_sources=None, driven_sources=None):
        from RBFtools.ui.main_window import RBFToolsWindow
        win = RBFToolsWindow.__new__(RBFToolsWindow)
        win._ctrl = mock.MagicMock()
        win._ctrl.read_driver_sources.return_value = (
            driver_sources or [])
        win._ctrl.read_driven_sources.return_value = (
            driven_sources or [])
        return win

    # ----- Driver side: Scene A / B / C -----

    def test_E2E_driver_scene_A_precise_attrs_forwarded(self):
        # D.1: attrs non-empty -> precise disconnect.
        from RBFtools.ui.main_window import RBFToolsWindow
        win = self._make_window(
            driver_sources=[self._src(["tx", "ty", "tz"])])
        with mock.patch(
                "RBFtools.ui.main_window.QtWidgets.QMessageBox"):
            RBFToolsWindow._on_driver_source_attrs_clear(
                win, 0, ["ty", "tz"])
        win._ctrl.disconnect_driver_source_attrs.\
            assert_called_once_with(0, ["ty", "tz"])

    def test_E2E_driver_scene_B_full_disconnect_when_attrs_empty(self):
        # D.2: empty attrs payload -> attrs=None forwarded for full
        # source disconnect.
        from RBFtools.ui.main_window import RBFToolsWindow
        win = self._make_window(
            driver_sources=[self._src(["tx", "ty"])])
        with mock.patch(
                "RBFtools.ui.main_window.QtWidgets.QMessageBox"):
            RBFToolsWindow._on_driver_source_attrs_clear(
                win, 0, [])
        win._ctrl.disconnect_driver_source_attrs.\
            assert_called_once_with(0, None)

    def test_E2E_driver_scene_C_dialog_when_no_connections(self):
        # D.3: source has 0 attrs -> info dialog + no controller call.
        from RBFtools.ui.main_window import RBFToolsWindow
        win = self._make_window(
            driver_sources=[self._src([])])
        with mock.patch(
                "RBFtools.ui.main_window.QtWidgets.QMessageBox"
        ) as mb:
            RBFToolsWindow._on_driver_source_attrs_clear(
                win, 0, [])
        mb.information.assert_called_once()
        win._ctrl.disconnect_driver_source_attrs.assert_not_called()

    # ----- Driven side: Scene A / B / C -----

    def test_E2E_driven_scene_A_precise_attrs_forwarded(self):
        from RBFtools.ui.main_window import RBFToolsWindow
        win = self._make_window(
            driven_sources=[self._dvn(["tx", "ty"])])
        with mock.patch(
                "RBFtools.ui.main_window.QtWidgets.QMessageBox"):
            RBFToolsWindow._on_driven_source_attrs_clear(
                win, 0, ["tx"])
        win._ctrl.disconnect_driven_source_attrs.\
            assert_called_once_with(0, ["tx"])

    def test_E2E_driven_scene_B_full_disconnect_when_attrs_empty(self):
        from RBFtools.ui.main_window import RBFToolsWindow
        win = self._make_window(
            driven_sources=[self._dvn(["ry", "rz"])])
        with mock.patch(
                "RBFtools.ui.main_window.QtWidgets.QMessageBox"):
            RBFToolsWindow._on_driven_source_attrs_clear(
                win, 0, [])
        win._ctrl.disconnect_driven_source_attrs.\
            assert_called_once_with(0, None)

    def test_E2E_driven_scene_C_dialog_when_no_connections(self):
        from RBFtools.ui.main_window import RBFToolsWindow
        win = self._make_window(
            driven_sources=[self._dvn([])])
        with mock.patch(
                "RBFtools.ui.main_window.QtWidgets.QMessageBox"
        ) as mb:
            RBFToolsWindow._on_driven_source_attrs_clear(
                win, 0, [])
        mb.information.assert_called_once()
        win._ctrl.disconnect_driven_source_attrs.assert_not_called()


# ----------------------------------------------------------------------
# Core path A vs path B atomic-protocol reuse evidence (F2 fix)
# ----------------------------------------------------------------------


class T_PATH_A_ATOMIC_PROTOCOL_REUSE(unittest.TestCase):
    """F2-fix evidence: path A (set/disconnect_*_source_attrs) is no
    longer a parallel wiring track that bypasses the
    M_BREAK_REBUILD / M_UNITCONV_PURGE / M_REMOVE_MULTI /
    M_SWEEP_EMPTY atomic protocol. Source-scan asserts every path-A
    function body now references _disconnect_or_purge."""

    @classmethod
    def setUpClass(cls):
        cls._core = _read(_CORE_PY)

    def test_path_A_disconnect_drivers_uses_purge(self):
        body = self._core.split(
            "def disconnect_driver_source_attrs")[1].split(
            "\ndef ")[0]
        self.assertIn("_disconnect_or_purge", body)
        # And the M_SWEEP_EMPTY chaser ensures orphans are cleaned.
        self.assertIn("_sweep_empty_subscripts(shape, \"input\")", body)

    def test_path_A_disconnect_driven_uses_purge(self):
        body = self._core.split(
            "def disconnect_driven_source_attrs")[1].split(
            "\ndef ")[0]
        self.assertIn("_disconnect_or_purge", body)
        self.assertIn(
            "_sweep_empty_subscripts(shape, \"output\")", body)

    def test_path_A_set_drivers_pre_cleans_overlap_via_purge(self):
        body = self._core.split(
            "def set_driver_source_attrs")[1].split("\ndef ")[0]
        self.assertIn("overlapping", body)
        self.assertIn("_disconnect_or_purge", body)

    def test_path_A_set_driven_pre_cleans_overlap_via_purge(self):
        body = self._core.split(
            "def set_driven_source_attrs")[1].split("\ndef ")[0]
        self.assertIn("overlapping", body)
        self.assertIn("_disconnect_or_purge", body)


class T_PATH_A_NODE_STATE_FROZEN_HOTFIX(unittest.TestCase):
    """PERMANENT GUARD — 2026-04-28 hotfix.

    User report: Driven-side Connect caused Maya CTD. Root cause —
    the path-A set/disconnect_*_source_attrs functions ran their
    wiring storm (cmds.delete(unitConv) + remove-all + re-add-all)
    OUTSIDE _node_state_frozen, so DG kept evaluating compute() on
    a transient half-broken graph and segfaulted in the C++ kernel.

    All 4 path-A functions MUST wrap their body in
    _node_state_frozen(shape) — same protocol as connect_routed /
    disconnect_routed (M_CRASH_FIX defense 2)."""

    @classmethod
    def setUpClass(cls):
        cls._core = _read(_CORE_PY)

    def test_set_driver_uses_node_state_frozen(self):
        body = self._core.split(
            "def set_driver_source_attrs")[1].split("\ndef ")[0]
        self.assertIn("_node_state_frozen(shape)", body,
            "set_driver_source_attrs MUST wrap its rebuild storm "
            "in _node_state_frozen — DG mid-evaluate during "
            "cmds.delete(unitConv) is the documented CTD trigger.")

    def test_set_driven_uses_node_state_frozen(self):
        body = self._core.split(
            "def set_driven_source_attrs")[1].split("\ndef ")[0]
        self.assertIn("_node_state_frozen(shape)", body,
            "set_driven_source_attrs CTD repro fix — wrap in freeze.")

    def test_disconnect_driver_uses_node_state_frozen(self):
        body = self._core.split(
            "def disconnect_driver_source_attrs")[1].split(
            "\ndef ")[0]
        self.assertIn("_node_state_frozen(shape)", body)

    def test_disconnect_driven_uses_node_state_frozen(self):
        body = self._core.split(
            "def disconnect_driven_source_attrs")[1].split(
            "\ndef ")[0]
        self.assertIn("_node_state_frozen(shape)", body)


if __name__ == "__main__":
    unittest.main()
