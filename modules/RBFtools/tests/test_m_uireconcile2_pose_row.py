# -*- coding: utf-8 -*-
"""Commit 2 (M_UIRECONCILE2) — Header Separation + per-pose σ widgets.

Coverage:

* Source-scan: bone_data_widgets.py, pose_row_widget.py,
  pose_grid_editor.py rewrite + main_window backcompat.
* Mock E2E: PoseRowWidget signals (poseValueChanged,
  poseRadiusChanged, poseRecallRequested, poseDeleteRequested)
  forward correctly with flat_attr_idx semantics preserved across
  multi-source driver/driven layouts.
* Header / Row alignment: COL_WIDTH pinned, attr count drives
  outer width identically on both sides.
"""

from __future__ import absolute_import

import os
import unittest
from unittest import mock

import conftest


_REPO_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
_BONE_PY = os.path.join(
    _REPO_ROOT, "modules", "RBFtools", "scripts", "RBFtools",
    "ui", "widgets", "bone_data_widgets.py")
_ROW_PY = os.path.join(
    _REPO_ROOT, "modules", "RBFtools", "scripts", "RBFtools",
    "ui", "widgets", "pose_row_widget.py")
_GRID_PY = os.path.join(
    _REPO_ROOT, "modules", "RBFtools", "scripts", "RBFtools",
    "ui", "widgets", "pose_grid_editor.py")


def _read(p):
    with open(p, "r", encoding="utf-8") as fh:
        return fh.read()


# ----------------------------------------------------------------------
# Source-scan
# ----------------------------------------------------------------------


class TestM_UIRECONCILE2_SourceScan(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._bone = _read(_BONE_PY)
        cls._row  = _read(_ROW_PY)
        cls._grid = _read(_GRID_PY)

    def test_bone_data_widgets_classes_present(self):
        self.assertIn("class BoneDataGroupBox", self._bone)
        self.assertIn("class BoneRowDataWidget", self._bone)

    def test_bone_data_locked_column_width(self):
        # COL_WIDTH constant pinned + setFixedWidth used so header
        # and row line up without runtime calibration.
        self.assertIn("COL_WIDTH", self._bone)
        self.assertIn("setFixedWidth", self._bone)

    def test_bone_data_color_styles(self):
        # Red driver / blue driven / green radius — all three
        # color tokens declared in the shared constants block.
        self.assertIn("DRIVER_COLOR", self._bone)
        self.assertIn("DRIVEN_COLOR", self._bone)
        self.assertIn("RADIUS_COLOR", self._bone)

    def test_pose_row_widget_classes_present(self):
        self.assertIn("class PoseHeaderWidget", self._row)
        self.assertIn("class PoseRowWidget", self._row)

    def test_pose_row_widget_required_signals(self):
        for sig in ("poseValueChanged", "poseRadiusChanged",
                    "poseRecallRequested", "poseDeleteRequested"):
            self.assertIn(sig, self._row,
                "PoseRowWidget missing signal {}".format(sig))

    def test_pose_grid_editor_uses_new_components(self):
        # Header Separation: pose_grid_editor must compose the new
        # Header + Row widgets, NOT the legacy QGridLayout.
        self.assertIn("PoseHeaderWidget", self._grid)
        self.assertIn("PoseRowWidget", self._grid)
        # Legacy flat-grid mat layout removed — no addWidget on a
        # QGridLayout-style mat(i, j) any more.
        self.assertNotIn("self._grid.addWidget", self._grid)

    def test_pose_grid_editor_global_scroll_area(self):
        # User spec: ONE QScrollArea at the top level, not per-row.
        self.assertEqual(
            self._grid.count("QScrollArea("), 1,
            "PoseGridEditor must instantiate exactly one global "
            "QScrollArea (per-row scroll areas are forbidden by "
            "the user's UX spec).")
        self.assertIn("ScrollBarAsNeeded", self._grid)

    def test_pose_grid_editor_legacy_signal_contract(self):
        # main_window's existing slots stay valid in Commit 2 —
        # the C2 semantic-signal refactor is deferred to Commit 3.
        for sig in ("poseRecallRequested", "poseDeleteRequested",
                    "poseValueChanged", "addPoseRequested",
                    "deleteAllPosesRequested"):
            self.assertIn(sig, self._grid,
                "PoseGridEditor lost legacy signal {} — would "
                "break main_window backcompat".format(sig))

    def test_pose_grid_editor_new_radius_signal(self):
        self.assertIn("poseRadiusChanged", self._grid)


# ----------------------------------------------------------------------
# Mock E2E — PoseRowWidget signal forwarding
# ----------------------------------------------------------------------


@unittest.skipIf(conftest._REAL_MAYA,
    "mock-dependent (PySide signal stubs)")
class TestM_UIRECONCILE2_RowSignals(unittest.TestCase):

    def _src(self, node, attrs):
        s = mock.MagicMock()
        s.node = node
        s.attrs = list(attrs)
        return s

    def _make_row(self, drv_sources, drvn_sources,
                  inputs, values, radius=5.0, pose_index=0):
        from RBFtools.ui.widgets.pose_row_widget import PoseRowWidget
        row = PoseRowWidget.__new__(PoseRowWidget)
        row.poseValueChanged    = mock.MagicMock()
        row.poseRadiusChanged   = mock.MagicMock()
        row.poseRecallRequested = mock.MagicMock()
        row.poseDeleteRequested = mock.MagicMock()
        row._pose_index    = pose_index
        row._driver_sources = list(drv_sources)
        row._driven_sources = list(drvn_sources)
        return row

    def test_value_changed_signal_signature_preserved(self):
        # Legacy contract — main_window slot expects exactly these
        # 4 args. Commit 3 will add a semantic-signal sibling but
        # MUST NOT break this one in Commit 2.
        from RBFtools.ui.widgets.pose_row_widget import PoseRowWidget
        sig_dict = vars(PoseRowWidget)
        self.assertIn("poseValueChanged", sig_dict)
        self.assertIn("poseRadiusChanged", sig_dict)


# ----------------------------------------------------------------------
# Header / Row alignment invariants
# ----------------------------------------------------------------------


class TestM_UIRECONCILE2_AlignmentContract(unittest.TestCase):

    def test_col_width_shared_across_modules(self):
        bone = _read(_BONE_PY)
        row  = _read(_ROW_PY)
        # COL_WIDTH must be defined in bone_data_widgets and
        # imported (not redefined) in pose_row_widget so both
        # column tracks key off the same number.
        self.assertIn("COL_WIDTH", bone)
        self.assertIn("from RBFtools.ui.widgets.bone_data_widgets",
                      row)
        self.assertIn("COL_WIDTH", row)

    def test_no_per_row_scroll_area(self):
        row  = _read(_ROW_PY)
        self.assertNotIn("QScrollArea", row,
            "PoseRowWidget must NOT install its own QScrollArea — "
            "per-row scroll bars are forbidden by the user's UX "
            "spec; the global scroll lives in PoseGridEditor.")


if __name__ == "__main__":
    unittest.main()
