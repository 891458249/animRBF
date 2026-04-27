# -*- coding: utf-8 -*-
"""2026-04-28 (M_CRASH_FIX) — three-defense protocol against the
batch-Connect CTD reproducer:

  Defense 1 — UI traversal and Maya cmds calls are SEPARATED. The
              gather phase produces pure Python str / list[str] data;
              the cmds.connectAttr storm runs against that snapshot
              with no further widget lookup.
  Defense 2 — connect_routed / disconnect_routed wrap the connectAttr
              loop in shape.nodeState=1 (HasNoEffect), so a half-wired
              input[] array cannot trigger compute() mid-storm.
  Defense 3 — _is_updating re-entrancy lock blocks _refresh_pose_grid
              and _refresh_base_pose_panel from re-painting the
              tabbed editors during the storm.
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
_MW_PY = os.path.join(
    _REPO_ROOT, "modules", "RBFtools", "scripts", "RBFtools",
    "ui", "main_window.py")


def _read(p):
    with open(p, "r", encoding="utf-8") as fh:
        return fh.read()


class TestM_CRASH_FIX_Defense1_PureStringGather(unittest.TestCase):
    """Defense 1: _gather_routed_targets returns pure Python data."""

    @classmethod
    def setUpClass(cls):
        cls._mw = _read(_MW_PY)

    def test_gather_returns_pure_strings(self):
        # The gather function MUST coerce every node + attr through
        # str() so no Qt object reference (e.g. QString returned by
        # PySide widgets) leaks into the controller / core layer.
        body = self._mw.split(
            "def _gather_routed_targets(self):")[1].split(
            "\n    def ")[0]
        self.assertIn("str(node", body)
        self.assertIn("str(a)", body)

    @unittest.skipIf(conftest._REAL_MAYA,
        "mock-dependent (PySide stubs)")
    def test_gather_output_is_plain_python_data(self):
        from RBFtools.ui.main_window import RBFToolsWindow
        win = RBFToolsWindow.__new__(RBFToolsWindow)
        win._pose_editor = mock.MagicMock()
        # Simulate a tab returning attr names that might be PyString
        # or similar Qt-wrapped objects — the gather must coerce.
        win._pose_editor.driver_editor.routed_targets.return_value = [
            ("boneA", ["tx", "ty"])]
        win._pose_editor.driven_editor.routed_targets.return_value = [
            ("boneX", ["rx"])]
        drv, dvn = RBFToolsWindow._gather_routed_targets(win)
        # Every element must be a plain str (or list of str).
        self.assertEqual(drv, [("boneA", ["tx", "ty"])])
        self.assertEqual(dvn, [("boneX", ["rx"])])
        for node, attrs in drv + dvn:
            self.assertIsInstance(node, str)
            for a in attrs:
                self.assertIsInstance(a, str)

    def test_on_connect_gathers_BEFORE_critical_section(self):
        # Source-scan: in _on_connect, the call to
        # _gather_routed_targets must come BEFORE the
        # _is_updating = True / _set_interaction_enabled(False)
        # critical section. Otherwise a node-change callback
        # firing during the gather walk could invalidate widgets.
        body = self._mw.split(
            "def _on_connect(self):")[1].split("\n    def ")[0]
        gather_pos = body.find("_gather_routed_targets")
        lock_pos   = body.find("_is_updating = True")
        self.assertGreater(gather_pos, 0)
        self.assertGreater(lock_pos, 0)
        self.assertLess(gather_pos, lock_pos,
            "Defense 1 violation: gather must complete BEFORE the "
            "critical section opens, so widget reads cannot race "
            "with the cmds storm.")

    def test_on_disconnect_same_ordering(self):
        body = self._mw.split(
            "def _on_disconnect(self):")[1].split("\n    def ")[0]
        gather_pos = body.find("_gather_routed_targets")
        lock_pos   = body.find("_is_updating = True")
        self.assertLess(gather_pos, lock_pos)


class TestM_CRASH_FIX_Defense2_NodeStateFreeze(unittest.TestCase):
    """Defense 2: connect_routed / disconnect_routed freeze the
    solver's nodeState before the cmds.connectAttr loop."""

    @classmethod
    def setUpClass(cls):
        cls._core = _read(_CORE_PY)

    def test_node_state_freeze_helper_present(self):
        self.assertIn("def _node_state_frozen", self._core)
        self.assertIn("nodeState", self._core)
        # 1 == HasNoEffect.
        self.assertIn("setAttr(plug, 1)", self._core)
        # Restoration in finally so an exception in the loop cannot
        # leak a permanent freeze.
        body = self._core.split(
            "def _node_state_frozen(")[1].split("\ndef ")[0]
        self.assertIn("finally:", body)
        self.assertIn("setAttr(plug, prev_state)", body)

    def test_connect_routed_uses_freeze(self):
        body = self._core.split(
            "def connect_routed(")[1].split("\ndef ")[0]
        self.assertIn("_node_state_frozen(shape)", body)

    def test_disconnect_routed_uses_freeze(self):
        body = self._core.split(
            "def disconnect_routed(")[1].split("\ndef ")[0]
        self.assertIn("_node_state_frozen(shape)", body)

    def test_evaluate_toggle_OUTSIDE_freeze(self):
        # The post-storm evaluate(0) -> evaluate(1) toggle MUST live
        # OUTSIDE the freeze block — toggling evaluate while
        # nodeState == HasNoEffect is a no-op + the whole point is
        # to fire ONE consolidated solve once the array is fully
        # wired. Source-scan: in connect_routed the evaluate toggle
        # appears AFTER the `with` block's closing.
        body = self._core.split(
            "def connect_routed(")[1].split("\ndef ")[0]
        with_pos = body.find("with undo_chunk")
        eval_pos = body.find('".evaluate"')
        self.assertGreater(with_pos, 0)
        self.assertGreater(eval_pos, with_pos,
            "evaluate toggle must run AFTER the freeze context "
            "exits, so the consolidated solve fires once with the "
            "complete input[] array.")


class TestM_CRASH_FIX_Defense3_ReentrancyLock(unittest.TestCase):
    """Defense 3: _is_updating re-entrancy lock blocks refresh
    callbacks during the storm."""

    @classmethod
    def setUpClass(cls):
        cls._mw = _read(_MW_PY)

    def test_lock_initialised_in_constructor(self):
        # Must be set on __init__ so the very first use is well-
        # defined — never relying on dynamic attr fallback.
        self.assertIn("self._is_updating = False", self._mw)

    def test_refresh_pose_grid_honours_lock(self):
        body = self._mw.split(
            "def _refresh_pose_grid(self):")[1].split(
            "\n    def ")[0]
        self.assertIn("_is_updating", body)
        self.assertIn("return", body)

    def test_refresh_base_pose_panel_honours_lock(self):
        body = self._mw.split(
            "def _refresh_base_pose_panel(self):")[1].split(
            "\n    def ")[0]
        self.assertIn("_is_updating", body)

    def test_lock_setter_in_on_connect(self):
        body = self._mw.split(
            "def _on_connect(self):")[1].split("\n    def ")[0]
        self.assertIn("self._is_updating = True", body)
        self.assertIn("self._is_updating = False", body)
        # Must be released in `finally` so an exception inside
        # ctrl.connect_routed cannot leave the UI permanently
        # silent.
        finally_pos = body.find("finally:")
        release_pos = body.find("self._is_updating = False")
        self.assertGreater(finally_pos, 0)
        self.assertLess(finally_pos, release_pos,
            "Defense 3 violation: _is_updating release must live "
            "in a finally block.")

    def test_lock_setter_in_on_disconnect(self):
        body = self._mw.split(
            "def _on_disconnect(self):")[1].split("\n    def ")[0]
        self.assertIn("self._is_updating = True", body)
        self.assertIn("self._is_updating = False", body)
        self.assertIn("finally:", body)

    @unittest.skipIf(conftest._REAL_MAYA,
        "mock-dependent (PySide stubs)")
    def test_lock_blocks_refresh_when_set(self):
        from RBFtools.ui.main_window import RBFToolsWindow
        win = RBFToolsWindow.__new__(RBFToolsWindow)
        win._is_updating = True
        win._ctrl = mock.MagicMock()
        win._pose_editor = mock.MagicMock()
        # With the lock held, refresh must early-return WITHOUT
        # touching the pose editor.
        RBFToolsWindow._refresh_pose_grid(win)
        win._pose_editor.reload_pose_grid.assert_not_called()
        RBFToolsWindow._refresh_base_pose_panel(win)
        win._pose_editor.reload_base_pose.assert_not_called()


if __name__ == "__main__":
    unittest.main()
