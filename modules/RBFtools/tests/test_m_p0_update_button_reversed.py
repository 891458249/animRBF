# -*- coding: utf-8 -*-
"""M_P0_UPDATE_BUTTON_REVERSED (2026-04-30) — per-row Update button
fired the Go-to-Pose path instead of the Update path.

User report 2026-04-30: clicking the per-pose-row "Update" button
behaves like the right-click "Go to Pose" item — driver / driven
viewport values jump to the stored pose, instead of the stored
pose values being overwritten with the current viewport values.

Root cause: ``pose_row_widget.py`` declared only one channel for
button-driven actions on the row (``poseRecallRequested``). The
"Update" QPushButton's ``.clicked`` lambda emitted that same
signal — the literal inverse of what the button label says. Four
signal layers (PoseRowWidget -> PoseGridEditor ->
_PoseEditorPanel -> main_window) all forwarded the misrouted
emission, and main_window's ``_on_pose_grid_recall`` slot called
``ctrl.recall_pose`` (Go-to-Pose). The user pressed Update and
got Recall.

Fix (4-layer signal chain + 1 main_window slot):

  * pose_row_widget.PoseRowWidget gains ``poseUpdateRequested``
    Qt signal; the ``self._btn_edit.clicked`` lambda emits it
    instead of ``poseRecallRequested``. The right-click menu
    Recall + the row double-click still emit
    ``poseRecallRequested`` independently.
  * pose_grid_editor.PoseGridEditor gains
    ``poseUpdateRequested`` and forwards each child row's signal.
  * base_pose_editor.BasePoseEditor gains the symmetric forward
    (the BasePose row hides the Update button so the channel
    never fires today, but the symmetry future-proofs the API).
  * main_window._PoseEditorPanel gains panel-level
    ``poseUpdateRequested`` + ``_on_grid_update_pose`` re-emit.
  * main_window.RBFToolsWindow gains ``_on_pose_grid_update``
    slot wired to ``ctrl.update_pose``.

PERMANENT GUARD T_M_P0_UPDATE_BUTTON_REVERSED locks each layer
of the chain and the per-button emission.
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
_POSE_ROW_PY = os.path.join(
    _REPO_ROOT, "modules", "RBFtools", "scripts", "RBFtools",
    "ui", "widgets", "pose_row_widget.py")
_POSE_GRID_PY = os.path.join(
    _REPO_ROOT, "modules", "RBFtools", "scripts", "RBFtools",
    "ui", "widgets", "pose_grid_editor.py")
_BASE_POSE_PY = os.path.join(
    _REPO_ROOT, "modules", "RBFtools", "scripts", "RBFtools",
    "ui", "widgets", "base_pose_editor.py")
_MAIN_WINDOW_PY = os.path.join(
    _REPO_ROOT, "modules", "RBFtools", "scripts", "RBFtools",
    "ui", "main_window.py")


def _read(p):
    with open(p, "r", encoding="utf-8") as fh:
        return fh.read()


# ----------------------------------------------------------------------
# PERMANENT GUARD T_M_P0_UPDATE_BUTTON_REVERSED
# ----------------------------------------------------------------------


class T_M_P0_UPDATE_BUTTON_REVERSED(unittest.TestCase):
    """PERMANENT GUARD — DO NOT REMOVE.

    Locks the 4-layer signal chain that wires the per-row Update
    button to ``ctrl.update_pose`` (snapshot viewport -> pose
    model), distinct from the Go-to-Pose recall path."""

    @classmethod
    def setUpClass(cls):
        cls._row = _read(_POSE_ROW_PY)
        cls._grid = _read(_POSE_GRID_PY)
        cls._base = _read(_BASE_POSE_PY)
        cls._mw = _read(_MAIN_WINDOW_PY)

    def test_PERMANENT_a_pose_row_signal_declared(self):
        self.assertIn(
            "poseUpdateRequested = QtCore.Signal(int)", self._row,
            "pose_row_widget MUST declare poseUpdateRequested.")

    def test_PERMANENT_b_pose_grid_signal_declared_and_forwarded(self):
        self.assertIn(
            "poseUpdateRequested  = QtCore.Signal(int)", self._grid,
            "pose_grid_editor MUST declare poseUpdateRequested.")
        self.assertIn(
            "row.poseUpdateRequested.connect(self.poseUpdateRequested)",
            self._grid,
            "pose_grid_editor MUST forward each row's "
            "poseUpdateRequested up to its own panel-level signal.")

    def test_PERMANENT_c_base_pose_signal_declared_and_forwarded(self):
        self.assertIn(
            "poseUpdateRequested = QtCore.Signal(int)", self._base,
            "base_pose_editor MUST declare poseUpdateRequested for "
            "symmetry with pose_grid_editor (BasePose row hides "
            "the button today; forward future-proofs the API).")
        self.assertIn(
            "self._row_widget.poseUpdateRequested.connect(",
            self._base)

    def test_PERMANENT_d_main_window_signal_declared(self):
        self.assertIn(
            "poseUpdateRequested      = QtCore.Signal(int)", self._mw,
            "_PoseEditorPanel MUST declare poseUpdateRequested at "
            "the panel level so RBFToolsWindow can subscribe.")

    def test_PERMANENT_e_main_window_panel_forwards_grid(self):
        self.assertIn(
            "self._pose_grid.poseUpdateRequested.connect(",
            self._mw,
            "_PoseEditorPanel MUST connect "
            "_pose_grid.poseUpdateRequested to its own re-emit slot.")
        self.assertIn(
            "self.poseUpdateRequested.emit(int(pose_index))", self._mw,
            "Panel re-emit MUST forward the pose index through "
            "self.poseUpdateRequested.emit.")

    def test_PERMANENT_f_main_window_subscribes_panel(self):
        self.assertIn(
            "pe.poseUpdateRequested.connect(self._on_pose_grid_update)",
            self._mw,
            "RBFToolsWindow MUST subscribe to the panel-level "
            "poseUpdateRequested with its _on_pose_grid_update slot.")

    def test_PERMANENT_g_main_window_slot_calls_ctrl_update(self):
        idx = self._mw.find("def _on_pose_grid_update(self, pose_index):")
        self.assertGreater(idx, 0,
            "RBFToolsWindow MUST define _on_pose_grid_update slot.")
        # Slice to next def.
        end = self._mw.find("\n    def ", idx + 1)
        body = self._mw[idx:end if end > 0 else idx + 4000]
        self.assertIn(
            "self._ctrl.update_pose(", body,
            "_on_pose_grid_update MUST dispatch to "
            "ctrl.update_pose (snapshot viewport -> pose model). "
            "Calling ctrl.recall_pose here would re-introduce the "
            "Bug (button label says Update, behaviour was Recall).")
        self.assertNotIn(
            "self._ctrl.recall_pose(", body,
            "_on_pose_grid_update MUST NOT call ctrl.recall_pose — "
            "that's the Go-to-Pose path, the literal inverse of "
            "what the Update button label says.")

    def test_PERMANENT_h_btn_edit_lambda_emits_update_not_recall(self):
        # AST guard (lesson #6 reapplied): walk the pose_row_widget
        # source for the assignment to self._btn_edit.clicked.connect
        # and assert the lambda body contains poseUpdateRequested,
        # NOT poseRecallRequested. The original bug shape was a
        # one-character difference in signal name inside that
        # lambda — static grep alone is fragile because both
        # signals are valid identifiers; the AST walk pins the
        # specific call site.
        tree = ast.parse(self._row)
        violations = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            # Looking for `self._btn_edit.clicked.connect(<lambda>)`.
            if not isinstance(func, ast.Attribute):
                continue
            if func.attr != "connect":
                continue
            # connect() target is the .clicked attribute.
            if not (isinstance(func.value, ast.Attribute) and
                    func.value.attr == "clicked"):
                continue
            # And the source object is self._btn_edit.
            if not (isinstance(func.value.value, ast.Attribute) and
                    func.value.value.attr == "_btn_edit"):
                continue
            # Inspect the lambda passed in.
            if not (node.args and
                    isinstance(node.args[0], ast.Lambda)):
                continue
            lam_body_src = ast.dump(node.args[0].body)
            if "poseRecallRequested" in lam_body_src:
                violations.append(
                    "_btn_edit.clicked lambda still emits "
                    "poseRecallRequested at lineno {}".format(
                        node.lineno))
            if "poseUpdateRequested" not in lam_body_src:
                violations.append(
                    "_btn_edit.clicked lambda does NOT emit "
                    "poseUpdateRequested at lineno {}".format(
                        node.lineno))
        self.assertEqual(
            violations, [],
            "AST guard: _btn_edit.clicked lambda must emit "
            "poseUpdateRequested (NOT poseRecallRequested). "
            "Violations:\n{}".format("\n".join(violations)))

    def test_PERMANENT_i_recall_paths_unchanged(self):
        # The right-click menu Recall + the row double-click MUST
        # still emit poseRecallRequested — those are independent
        # of the Update button. Source-scan asserts both sites
        # remain.
        # Right-click menu (line ~346 region):
        self.assertIn(
            "self.poseRecallRequested.emit(self._pose_index)",
            self._row,
            "Right-click Recall + row double-click MUST still "
            "emit poseRecallRequested — those channels are "
            "independent of the Update button refactor.")
        # Pose grid still forwards recall.
        self.assertIn(
            "row.poseRecallRequested.connect(self.poseRecallRequested)",
            self._grid)


# ----------------------------------------------------------------------
# Mock E2E — runtime: Update emits update, Recall emits recall.
# ----------------------------------------------------------------------


@unittest.skipIf(conftest._REAL_MAYA,
    "mock-dependent (controller stub)")
class TestM_P0_UPDATE_BUTTON_REVERSED_RuntimeBehavior(unittest.TestCase):

    def test_main_window_slot_dispatches_to_update_pose(self):
        # Imitate the panel-level signal dispatch by calling the
        # slot directly with mock state.
        from RBFtools.ui.main_window import RBFToolsWindow
        win = RBFToolsWindow.__new__(RBFToolsWindow)
        win._gather_role_info = mock.MagicMock(
            return_value=("drv", "dvn", ["rx"], ["tx"]))
        win._ctrl = mock.MagicMock()
        # Invoke via the unbound method to avoid touching Qt init.
        RBFToolsWindow._on_pose_grid_update(win, 2)
        win._ctrl.update_pose.assert_called_once_with(
            2, "drv", "dvn", ["rx"], ["tx"])
        win._ctrl.recall_pose.assert_not_called()

    def test_main_window_recall_slot_unchanged(self):
        # Sibling slot still routes to ctrl.recall_pose so the
        # right-click menu / row-dblclick behaviour is preserved.
        from RBFtools.ui.main_window import RBFToolsWindow
        win = RBFToolsWindow.__new__(RBFToolsWindow)
        win._gather_role_info = mock.MagicMock(
            return_value=("drv", "dvn", ["rx"], ["tx"]))
        win._ctrl = mock.MagicMock()
        RBFToolsWindow._on_pose_grid_recall(win, 5)
        win._ctrl.recall_pose.assert_called_once_with(
            5, "drv", "dvn", ["rx"], ["tx"])
        win._ctrl.update_pose.assert_not_called()


if __name__ == "__main__":
    unittest.main()
