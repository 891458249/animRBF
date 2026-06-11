# -*- coding: utf-8 -*-
"""M_P0_REFRESH_KEEPS_CURRENT (2026-04-30) — Refresh button
collapses the node combo to <None>.

User report 2026-04-30: clicking the node-selector Refresh
button while a node is active drops the combo display back to
<None>, even though ``controller._current_node`` still holds
the right name. Every downstream operation that consults
``node_selector.current_node()`` then misreads the active node
as "none".

Root cause (5-step trace, all source-grep verified):

  1. node_selector.refreshRequested -> main_window._on_refresh
  2. ctrl.refresh_nodes() -> emits nodesRefreshed(names);
     _current_node is NOT touched (intentional — controller
     state is authoritative).
  3. main_window._on_nodes_refreshed(names) ->
     self._node_sel.set_nodes(names).
  4. node_selector.set_nodes runs ``self._combo.clear() +
     addItem(<None>) + for n addItem(n)`` under blockSignals,
     so currentIndex defaults to 0 (<None>) without notifying
     anyone.
  5. The slot returns. The combo stays at <None>; the
     controller still has _current_node = "RBFnode2"; the UI
     and the controller drift.

Fix (Path A, 1-line restore + signal-block carve-out):

The slot now calls ``set_current_node(ctrl.current_node)``
after the rebuild so the visual selection tracks the
controller's authoritative state. The restore is wrapped in
``_combo.blockSignals(True)`` so ``setCurrentIndex`` does not
fire a redundant ``currentTextChanged ->
ctrl.on_node_changed`` — that callback re-runs
``_load_settings + _load_editor`` and is the wrong contract
for "the user clicked Refresh, not the combo".

Idempotent fail-soft: when the saved name is no longer in the
rebuilt list (user deleted the node in the outliner mid-
session), ``findText`` returns -1 and ``set_current_node`` is
a no-op. The combo correctly falls back to <None>; the
controller only learns about the deletion through the next
user-initiated node action.

PERMANENT GUARD T_M_P0_REFRESH_KEEPS_CURRENT.
"""

from __future__ import absolute_import

import ast
import os
import unittest
from unittest import mock

import conftest


_REPO_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
_MAIN_WINDOW_PY = os.path.join(
    _REPO_ROOT, "modules", "RBFtools", "scripts", "RBFtools",
    "ui", "main_window.py")
_NODE_SEL_PY = os.path.join(
    _REPO_ROOT, "modules", "RBFtools", "scripts", "RBFtools",
    "ui", "widgets", "node_selector.py")
_CTRL_PY = os.path.join(
    _REPO_ROOT, "modules", "RBFtools", "scripts", "RBFtools",
    "controller.py")


def _read(p):
    with open(p, "r", encoding="utf-8") as fh:
        return fh.read()


def _slice_method(src, signature):
    idx = src.find(signature)
    assert idx >= 0, "{} not found".format(signature)
    end = src.find("\n    def ", idx + 1)
    return src[idx:end if end > 0 else len(src)]


# ----------------------------------------------------------------------
# PERMANENT GUARD T_M_P0_REFRESH_KEEPS_CURRENT
# ----------------------------------------------------------------------


class T_M_P0_REFRESH_KEEPS_CURRENT(unittest.TestCase):
    """PERMANENT GUARD — DO NOT REMOVE.

    Locks the restore-call inside _on_nodes_refreshed plus the
    blockSignals carve-out that keeps the redundant
    on_node_changed cascade silent."""

    @classmethod
    def setUpClass(cls):
        cls._mw = _read(_MAIN_WINDOW_PY)
        cls._sel = _read(_NODE_SEL_PY)
        cls._ctrl = _read(_CTRL_PY)

    def test_PERMANENT_a_slot_calls_set_current_node(self):
        body = _slice_method(
            self._mw, "def _on_nodes_refreshed(self, names):")
        self.assertIn(
            "self._node_sel.set_current_node(", body,
            "_on_nodes_refreshed MUST restore the combo "
            "selection by calling set_current_node — without "
            "this the Refresh click silently blanks the combo "
            "and the user-reported P0 returns.")
        self.assertIn(
            "self._ctrl.current_node", body,
            "Restore source MUST be the controller's "
            "authoritative current_node @property.")

    def test_PERMANENT_b_signal_block_around_restore(self):
        body = _slice_method(
            self._mw, "def _on_nodes_refreshed(self, names):")
        self.assertIn(
            "blockSignals(True)", body,
            "Restore call MUST be wrapped in "
            "blockSignals(True) so setCurrentIndex does not "
            "trip currentTextChanged -> on_node_changed and "
            "trigger a spurious _load_settings cascade on "
            "every Refresh click.")
        self.assertIn(
            "blockSignals(blocked)", body,
            "blockSignals MUST be restored in finally with "
            "the original 'blocked' value (not unconditionally "
            "False) so a future caller that already had "
            "signals blocked is not unblocked by this slot.")

    def test_PERMANENT_c_set_nodes_unchanged(self):
        # Defence-in-depth: node_selector.set_nodes contract is
        # untouched. Pre-fix it cleared the combo and rebuilt;
        # the restore lives in main_window because that's the
        # MVC seam where the controller's authoritative
        # _current_node is reachable.
        self.assertIn(
            "def set_nodes(self, names):", self._sel)
        self.assertIn(
            "def set_current_node(self, name):", self._sel)
        # The two methods MUST stay public so the main_window
        # restore call has a stable target.

    def test_PERMANENT_d_controller_current_node_property(self):
        self.assertIn(
            "def current_node(self):", self._ctrl,
            "controller.current_node @property MUST stay "
            "exposed — the restore call relies on it.")

    def test_PERMANENT_e_ast_guard_restore_call_present(self):
        # AST walk: the slot's body MUST contain a
        # self._node_sel.set_current_node(...) Call. Lesson #6
        # reapplied — static grep can drift because both
        # set_current_node + set_nodes are valid identifiers,
        # and a future refactor that swapped the two would not
        # surface as a substring miss.
        tree = ast.parse(self._mw)
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            if node.name != "_on_nodes_refreshed":
                continue
            sees_set_current = False
            for sub in ast.walk(node):
                if not isinstance(sub, ast.Call):
                    continue
                func = sub.func
                if not isinstance(func, ast.Attribute):
                    continue
                if func.attr != "set_current_node":
                    continue
                sees_set_current = True
                break
            self.assertTrue(
                sees_set_current,
                "AST guard: _on_nodes_refreshed MUST contain a "
                "set_current_node call (lesson #6).")
            return
        self.fail("_on_nodes_refreshed FunctionDef not found.")


# ----------------------------------------------------------------------
# Mock E2E — runtime: refresh restores combo + suppresses cascade.
# ----------------------------------------------------------------------


@unittest.skipIf(conftest._REAL_MAYA,
    "mock-dependent (Qt minimal shim + controller stub)")
class TestM_P0_REFRESH_KEEPS_CURRENT_RuntimeBehavior(unittest.TestCase):

    def _make_window(self, current_node="RBFnode2"):
        from RBFtools.ui.main_window import RBFToolsWindow
        win = RBFToolsWindow.__new__(RBFToolsWindow)
        # Controller stub — current_node @property returns the
        # active name; on_node_changed counts spurious triggers.
        ctrl = mock.MagicMock()
        ctrl.current_node = current_node
        ctrl.on_node_changed = mock.MagicMock()
        win._ctrl = ctrl
        # node_selector stub with a tiny combo facade.
        ns = mock.MagicMock()
        ns._combo = mock.MagicMock()
        ns._combo.blockSignals = mock.MagicMock(return_value=False)
        ns.set_nodes = mock.MagicMock()
        ns.set_current_node = mock.MagicMock()
        win._node_sel = ns
        return win, ctrl, ns

    def test_refresh_restores_combo_to_current_node(self):
        from RBFtools.ui.main_window import RBFToolsWindow
        win, ctrl, ns = self._make_window(current_node="RBFnode2")
        RBFToolsWindow._on_nodes_refreshed(
            win, ["RBFnode1", "RBFnode2", "RBFnode3"])
        ns.set_nodes.assert_called_once_with(
            ["RBFnode1", "RBFnode2", "RBFnode3"])
        ns.set_current_node.assert_called_once_with("RBFnode2")

    def test_refresh_blocks_signals_around_restore(self):
        from RBFtools.ui.main_window import RBFToolsWindow
        win, ctrl, ns = self._make_window(current_node="RBFnode2")
        RBFToolsWindow._on_nodes_refreshed(
            win, ["RBFnode2"])
        # blockSignals(True) called once before set_current_node;
        # blockSignals(blocked) called once in finally with the
        # original return value (False, per the stub).
        calls = ns._combo.blockSignals.call_args_list
        self.assertGreaterEqual(
            len(calls), 2,
            "blockSignals MUST be called twice (suspend + "
            "restore). Got {} calls: {}".format(
                len(calls), calls))
        self.assertEqual(calls[0].args, (True,),
            "First blockSignals call MUST be True (suspend).")
        self.assertEqual(calls[-1].args, (False,),
            "Last blockSignals call MUST restore the original "
            "blocked state (False, per the stub).")

    def test_refresh_does_not_invoke_controller_on_node_changed(self):
        # The whole point of the blockSignals wrap: ctrl.on_node_
        # changed MUST NOT fire as a side-effect of the slot.
        # Under the mock, set_current_node never actually fires
        # currentTextChanged — but the test still serves as a
        # contract assertion: the slot itself does not invoke
        # the callback, regardless of Qt signal plumbing.
        from RBFtools.ui.main_window import RBFToolsWindow
        win, ctrl, ns = self._make_window()
        RBFToolsWindow._on_nodes_refreshed(
            win, ["RBFnode2"])
        ctrl.on_node_changed.assert_not_called()

    def test_refresh_idempotent_when_node_deleted(self):
        # Ghost scenario: controller still thinks it has
        # "RBFnode2" but the rebuilt list does not include it.
        # set_current_node's findText returns -1 and the
        # internal setCurrentIndex is skipped — combo falls back
        # to <None>. Slot MUST NOT raise.
        from RBFtools.ui.main_window import RBFToolsWindow
        win, ctrl, ns = self._make_window(current_node="RBFnode2")
        # set_current_node is a MagicMock — it does not actually
        # check the rebuilt list. The contract here is: the
        # slot calls set_current_node with the controller's
        # name; node_selector handles fail-soft internally.
        # This test asserts the slot completes without raising
        # even when the saved name does not match anything.
        try:
            RBFToolsWindow._on_nodes_refreshed(win, ["RBFnode99"])
        except Exception as exc:
            self.fail(
                "_on_nodes_refreshed MUST NOT raise even when "
                "the saved name is missing from the new list. "
                "Got: {}".format(exc))
        ns.set_current_node.assert_called_once_with("RBFnode2")

    def test_refresh_repeated_clicks_idempotent(self):
        # 5 sequential refreshes: each should restore the same
        # selection without accumulating state.
        from RBFtools.ui.main_window import RBFToolsWindow
        win, ctrl, ns = self._make_window(current_node="RBFnode2")
        for _ in range(5):
            RBFToolsWindow._on_nodes_refreshed(
                win, ["RBFnode1", "RBFnode2", "RBFnode3"])
        self.assertEqual(ns.set_nodes.call_count, 5)
        self.assertEqual(ns.set_current_node.call_count, 5)
        # Every restore call MUST carry the same argument.
        for call in ns.set_current_node.call_args_list:
            self.assertEqual(call.args, ("RBFnode2",))
        # ctrl.on_node_changed MUST NOT fire across all five.
        ctrl.on_node_changed.assert_not_called()

    def test_refresh_no_current_node_passes_empty_string(self):
        # When the controller has no active node, current_node
        # @property returns "" (empty). The restore call passes
        # the empty string through; node_selector's findText("")
        # returns -1; combo stays at <None>. No crash.
        from RBFtools.ui.main_window import RBFToolsWindow
        win, ctrl, ns = self._make_window(current_node="")
        RBFToolsWindow._on_nodes_refreshed(
            win, ["RBFnode1"])
        ns.set_current_node.assert_called_once_with("")


if __name__ == "__main__":
    unittest.main()
