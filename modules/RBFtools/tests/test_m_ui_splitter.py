# -*- coding: utf-8 -*-
"""Commit 2b (M_UI_SPLITTER) — draggable column widths +
Header-Driven Sync.

Coverage:
* Source-scan: DriverDriven QSplitter, PoseHeaderWidget QSplitter +
  splitterMoved re-emit, PoseRowWidget 3-container layout +
  set_container_widths API, sync wiring in PoseGridEditor and
  BasePoseEditor (showEvent + post-rebuild + signal hookup).
"""

from __future__ import absolute_import

import os
import unittest


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
_BASE_PY = os.path.join(
    _REPO_ROOT, "modules", "RBFtools", "scripts", "RBFtools",
    "ui", "widgets", "base_pose_editor.py")
_MAIN_WINDOW = os.path.join(
    _REPO_ROOT, "modules", "RBFtools", "scripts", "RBFtools",
    "ui", "main_window.py")


def _read(p):
    with open(p, "r", encoding="utf-8") as fh:
        return fh.read()


class TestM_UI_SPLITTER_DriverDrivenTab(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._mw = _read(_MAIN_WINDOW)

    def test_dd_uses_qsplitter_horizontal(self):
        # The DriverDriven tab no longer wires editors via a flat
        # QHBoxLayout — they live inside a horizontal QSplitter so
        # the user can drag the divider.
        self.assertIn("QSplitter(QtCore.Qt.Horizontal)", self._mw)
        self.assertIn("self._dd_splitter", self._mw)
        self.assertIn("self._dd_splitter.addWidget(self._driver_editor)",
                      self._mw)
        self.assertIn("self._dd_splitter.addWidget(self._driven_editor)",
                      self._mw)

    def test_dd_splitter_initial_stretch_balanced(self):
        # User spec: 1:1 starting ratio.
        self.assertIn(
            "self._dd_splitter.setStretchFactor(0, 1)", self._mw)
        self.assertIn(
            "self._dd_splitter.setStretchFactor(1, 1)", self._mw)

    def test_dd_splitter_no_collapse(self):
        # Children must not collapse to zero width on aggressive drag.
        self.assertIn(
            "self._dd_splitter.setChildrenCollapsible(False)",
            self._mw)


class TestM_UI_SPLITTER_PoseHeaderSplitter(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._row = _read(_ROW_PY)

    def test_header_uses_internal_splitter(self):
        self.assertIn("class PoseHeaderWidget", self._row)
        self.assertIn("QtWidgets.QSplitter", self._row)
        self.assertIn("setChildrenCollapsible(False)", self._row)

    def test_header_reemits_splitter_moved(self):
        # PoseHeaderWidget.splitterMoved is the canonical sync trigger.
        self.assertIn("splitterMoved = QtCore.Signal(int, int)",
                      self._row)
        self.assertIn(
            "self._splitter.splitterMoved.connect(self.splitterMoved)",
            self._row)

    def test_header_three_panes(self):
        # Driver + Driven + Tail (radius / actions). Source-scan via
        # the addWidget call count on _splitter.
        self.assertEqual(
            self._row.count("self._splitter.addWidget("), 3,
            "PoseHeaderWidget must add exactly 3 panes (driver / "
            "driven / tail) to its internal QSplitter.")

    def test_header_splitter_sizes_api(self):
        self.assertIn("def splitter_sizes(self):", self._row)


class TestM_UI_SPLITTER_PoseRowContainers(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._row = _read(_ROW_PY)

    def test_row_has_three_containers(self):
        for name in ("self._driver_container",
                     "self._driven_container",
                     "self._tail_container"):
            self.assertIn(name, self._row,
                "PoseRowWidget missing {}".format(name))

    def test_row_has_no_internal_splitter(self):
        # The user spec is explicit: PoseRowWidget MUST NOT wrap
        # contents in its own QSplitter (would tank perf + alignment).
        # Exactly ONE QSplitter constructor call in the file — the one
        # inside PoseHeaderWidget. Adding another (per-row) would make
        # this count >= 2.
        self.assertEqual(
            self._row.count("QtWidgets.QSplitter("), 1,
            "Only PoseHeaderWidget may instantiate a QSplitter; "
            "PoseRowWidget MUST mirror its widths via "
            "set_container_widths(), not its own splitter.")

    def test_row_set_container_widths_api(self):
        self.assertIn("def set_container_widths", self._row)
        # And it must use setMinimumWidth + setMaximumWidth (or
        # setFixedWidth) on each container so widths actually pin.
        self.assertIn("setMaximumWidth", self._row)
        self.assertIn("setMinimumWidth", self._row)


class TestM_UI_SPLITTER_GridEditorSync(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._grid = _read(_GRID_PY)
        cls._base = _read(_BASE_PY)

    def test_grid_listens_to_splitter_moved(self):
        self.assertIn(
            "self._header_widget.splitterMoved.connect(",
            self._grid)
        self.assertIn("def _sync_column_widths", self._grid)

    def test_grid_initial_sync_after_rebuild(self):
        # Belt-and-suspenders: explicit call + QTimer.singleShot for
        # the case where Qt hasn't yet sized the splitter.
        self.assertIn(
            "QtCore.QTimer.singleShot(0, self._sync_column_widths)",
            self._grid)

    def test_grid_show_event_sync(self):
        self.assertIn("def showEvent", self._grid)

    def test_base_pose_editor_listens_to_splitter_moved(self):
        # Same Header-Driven Sync wiring as PoseGridEditor.
        self.assertIn(
            "self._header_widget.splitterMoved.connect(",
            self._base)
        self.assertIn("def _sync_column_widths", self._base)
        self.assertIn(
            "QtCore.QTimer.singleShot(0, self._sync_column_widths)",
            self._base)
        self.assertIn("def showEvent", self._base)


if __name__ == "__main__":
    unittest.main()
