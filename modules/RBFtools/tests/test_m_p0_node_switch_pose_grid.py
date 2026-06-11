# -*- coding: utf-8 -*-
"""M_P0_NODE_SWITCH_POSE_GRID (2026-04-30) — switching the
active RBF node leaves the pose grid blank.

User report 2026-04-30: when the user picks a different node in
the node-selector combo, the driver / driven tab editors
correctly rebuild from the new node, but the pose grid stays
blank — even though ``controller.pose_model`` already holds the
new node's pose rows. Clicking Refresh does not help (Refresh
goes through ``ctrl.refresh_nodes`` which only rebuilds the
combo list, not the pose grid).

Root cause (4-leg editorLoaded cascade missing one leg):

  ctrl.on_node_changed -> ctrl._load_editor -> emits
  editorLoaded. The signal has THREE main_window subscribers:

    1. _on_editor_loaded (line 2147) — only updates the legacy
       QTableView delegate's input count + resize mode. Does
       NOT call _refresh_pose_grid.
    2. _reload_driver_sources (line 1249) — rebuilds the
       driver tabs. ✓
    3. _reload_driven_sources (line 1270) — rebuilds the
       driven tabs. ✓

  The view-side PoseGridEditor is rebuilt by
  ``_refresh_pose_grid`` (which reads pose_model +
  read_driver/driven_sources and feeds PoseGridEditor.set_data).
  No editorLoaded subscriber currently calls it, so the grid
  rows never repaint after a node switch.

Fix (1-line addition to _on_editor_loaded):

The slot now ends with ``self._refresh_pose_grid()`` so the
pose grid rebuilds in lock-step with the rest of the cascade.
Empty-node path is safe: _refresh_pose_grid feeds [] / [] / []
into PoseGridEditor.set_data which clears the rows.

The seven existing _refresh_pose_grid call sites (after
add_pose, add/remove driver, connect, row actions, language
switch, etc.) are untouched — this commit only closes the
node-switch leg of the cascade.

PERMANENT GUARD T_M_P0_NODE_SWITCH_POSE_GRID.
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


def _read(p):
    with open(p, "r", encoding="utf-8") as fh:
        return fh.read()


# ----------------------------------------------------------------------
# PERMANENT GUARD T_M_P0_NODE_SWITCH_POSE_GRID
# ----------------------------------------------------------------------


class T_M_P0_NODE_SWITCH_POSE_GRID(unittest.TestCase):
    """PERMANENT GUARD — DO NOT REMOVE.

    Locks the _on_editor_loaded slot's tail call to
    _refresh_pose_grid so the editorLoaded cascade rebuilds the
    pose grid in lock-step with the driver / driven tab
    rebuilds."""

    @classmethod
    def setUpClass(cls):
        cls._mw = _read(_MAIN_WINDOW_PY)

    def _slot_body(self):
        idx = self._mw.find("def _on_editor_loaded(self):")
        self.assertGreater(idx, 0,
            "_on_editor_loaded slot MUST exist.")
        end = self._mw.find("\n    def ", idx + 1)
        return self._mw[idx:end if end > 0 else idx + 4000]

    def test_PERMANENT_a_slot_calls_refresh_pose_grid(self):
        body = self._slot_body()
        self.assertIn(
            "self._refresh_pose_grid()", body,
            "_on_editor_loaded MUST call self._refresh_pose_grid() "
            "so the pose grid rebuilds on node switch — without "
            "this the user-reported P0 returns (driver / driven "
            "tabs rebuild but pose grid stays blank).")

    def test_PERMANENT_b_ast_guard_refresh_call_present(self):
        # AST walk: the slot's FunctionDef MUST contain a
        # self._refresh_pose_grid() Call. Lesson #6 reapplied —
        # static grep can drift if a future refactor renames the
        # method or routes through a sibling call.
        tree = ast.parse(self._mw)
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            if node.name != "_on_editor_loaded":
                continue
            sees_call = False
            for sub in ast.walk(node):
                if not isinstance(sub, ast.Call):
                    continue
                func = sub.func
                if not isinstance(func, ast.Attribute):
                    continue
                if func.attr != "_refresh_pose_grid":
                    continue
                sees_call = True
                break
            self.assertTrue(
                sees_call,
                "AST guard: _on_editor_loaded MUST contain a "
                "self._refresh_pose_grid() call (lesson #6).")
            return
        self.fail("_on_editor_loaded FunctionDef not found.")

    def test_PERMANENT_c_existing_callsites_preserved(self):
        # Defence-in-depth: the seven pre-fix _refresh_pose_grid
        # call sites must still be present (the bug fix only
        # ADDS a new caller; removing any existing trigger
        # would re-introduce a different symptom — e.g. add_pose
        # not refreshing the row count). Count: definition (1) +
        # callers (>= 7).
        defs = self._mw.count("def _refresh_pose_grid")
        callers = self._mw.count("self._refresh_pose_grid()")
        self.assertEqual(defs, 1,
            "Exactly one _refresh_pose_grid definition "
            "expected; got {}.".format(defs))
        self.assertGreaterEqual(
            callers, 8,
            "Expected >= 8 self._refresh_pose_grid() callers "
            "(7 pre-existing + 1 new from the bug fix); got "
            "{}. A pre-existing trigger may have been "
            "accidentally dropped.".format(callers))

    def test_PERMANENT_d_editorLoaded_subscribers_complete(self):
        # The editorLoaded signal MUST keep its three main_window
        # subscribers — _on_editor_loaded handles the legacy
        # QTableView delegate plus the new pose grid rebuild;
        # _reload_driver_sources + _reload_driven_sources handle
        # the tab editors. Removing any of the three would
        # re-fragment the cascade.
        self.assertIn(
            "ctrl.editorLoaded.connect(self._on_editor_loaded)",
            self._mw)
        self.assertIn(
            "ctrl.editorLoaded.connect(self._reload_driver_sources)",
            self._mw)
        self.assertIn(
            "ctrl.editorLoaded.connect(self._reload_driven_sources)",
            self._mw)


# ----------------------------------------------------------------------
# Mock E2E — runtime: _on_editor_loaded triggers grid rebuild.
# ----------------------------------------------------------------------


@unittest.skipIf(conftest._REAL_MAYA,
    "mock-dependent (Qt minimal shim + controller stub)")
class TestM_P0_NODE_SWITCH_POSE_GRID_RuntimeBehavior(unittest.TestCase):

    def _make_window(self, n_inputs=3, columns=5):
        """Build a partial RBFToolsWindow stub with just the
        attributes _on_editor_loaded reads."""
        from RBFtools.ui.main_window import RBFToolsWindow
        win = RBFToolsWindow.__new__(RBFToolsWindow)
        # Pose model stub.
        model = mock.MagicMock()
        model.n_inputs = int(n_inputs)
        model.columnCount.return_value = int(columns)
        ctrl = mock.MagicMock()
        ctrl.pose_model = model
        win._ctrl = ctrl
        # Delegate stub.
        win._delegate = mock.MagicMock()
        # PoseEditor + table view + header stub.
        header = mock.MagicMock()
        tv = mock.MagicMock()
        tv.horizontalHeader.return_value = header
        win._pose_editor = mock.MagicMock()
        win._pose_editor.table_view = tv
        # _refresh_pose_grid spy.
        win._refresh_pose_grid = mock.MagicMock()
        return win, ctrl, model, header

    def test_node_switch_triggers_pose_grid_rebuild(self):
        from RBFtools.ui.main_window import RBFToolsWindow
        win, ctrl, model, header = self._make_window()
        RBFToolsWindow._on_editor_loaded(win)
        win._refresh_pose_grid.assert_called_once_with()

    def test_delegate_input_count_still_set(self):
        # Defence-in-depth: the new _refresh_pose_grid call must
        # NOT bypass the existing delegate / header setup.
        from RBFtools.ui.main_window import RBFToolsWindow
        win, ctrl, model, header = self._make_window(
            n_inputs=7, columns=4)
        RBFToolsWindow._on_editor_loaded(win)
        win._delegate.set_input_count.assert_called_once_with(7)
        # 4 columns -> 4 setSectionResizeMode calls.
        self.assertEqual(
            header.setSectionResizeMode.call_count, 4)

    def test_empty_node_path_does_not_crash(self):
        # current_node = "" path: pose_model.n_inputs = 0,
        # columnCount = 0 -> no header.setSectionResizeMode
        # calls; _refresh_pose_grid still fires for symmetry.
        from RBFtools.ui.main_window import RBFToolsWindow
        win, ctrl, model, header = self._make_window(
            n_inputs=0, columns=0)
        try:
            RBFToolsWindow._on_editor_loaded(win)
        except Exception as exc:
            self.fail(
                "Empty-node editorLoaded MUST NOT raise. "
                "Got: {}".format(exc))
        win._refresh_pose_grid.assert_called_once()

    def test_repeated_node_switches_idempotent(self):
        # 5 sequential editorLoaded firings — each must trigger
        # exactly one grid rebuild, no accumulation.
        from RBFtools.ui.main_window import RBFToolsWindow
        win, ctrl, model, header = self._make_window()
        for _ in range(5):
            RBFToolsWindow._on_editor_loaded(win)
        self.assertEqual(
            win._refresh_pose_grid.call_count, 5,
            "5 node switches must trigger exactly 5 grid "
            "rebuilds (one per editorLoaded firing).")

    def test_dual_node_switch_each_rebuilds_with_own_columns(self):
        # nodeA (3 driver columns) -> nodeB (5) -> nodeA. The
        # delegate sees the matching n_inputs each time.
        from RBFtools.ui.main_window import RBFToolsWindow

        # nodeA pass.
        win, ctrl, model, header = self._make_window(
            n_inputs=3, columns=3)
        RBFToolsWindow._on_editor_loaded(win)
        self.assertEqual(
            win._delegate.set_input_count.call_args.args, (3,))

        # nodeB pass — same window, swap model state.
        ctrl.pose_model.n_inputs = 5
        ctrl.pose_model.columnCount.return_value = 5
        RBFToolsWindow._on_editor_loaded(win)
        self.assertEqual(
            win._delegate.set_input_count.call_args.args, (5,))

        # nodeA pass again.
        ctrl.pose_model.n_inputs = 3
        ctrl.pose_model.columnCount.return_value = 3
        RBFToolsWindow._on_editor_loaded(win)
        self.assertEqual(
            win._delegate.set_input_count.call_args.args, (3,))
        # 3 firings -> 3 grid rebuilds.
        self.assertEqual(win._refresh_pose_grid.call_count, 3)


if __name__ == "__main__":
    unittest.main()
