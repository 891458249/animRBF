# -*- coding: utf-8 -*-
"""PoseGridEditor — Commit 2 (M_UIRECONCILE2) rewrite.

Replaces the legacy QGridLayout flat-grid implementation with the
*Header Separation* layout per the user's 2026-04-27 audit:

  ┌─ PoseHeaderWidget                  ─┐  ← red driver / blue driven
  │ ┌─ QScrollArea (global, h+v) ──────┐│
  │ │  PoseRowWidget                   ││  ← bare spinboxes,
  │ │  PoseRowWidget                   ││    width-locked to header
  │ │  ...                             ││
  │ └──────────────────────────────────┘│
  │ [Add Pose] [Delete Poses]            │
  └──────────────────────────────────────┘

Public signal contract preserved bit-for-bit so main_window slots
keep working without modification (Commit 3 will add the
semantic-signal sibling for the per-source / attr-name refactor).
The new ``poseRadiusChanged(int pose_idx, float)`` signal is added
on top of the legacy contract for consumption by Commit 3.

MVC red line preserved: never imports cmds. Receives DriverSource /
DrivenSource / PoseData via :py:meth:`set_data`; emits intent
signals for main_window to translate into core operations.
"""

from __future__ import absolute_import

from RBFtools.ui.compat import QtCore, QtWidgets
from RBFtools.ui.i18n import tr
from RBFtools.ui.widgets.bone_data_widgets import (
    COL_SPACING, COL_MARGIN,
)
from RBFtools.ui.widgets.pose_row_widget import (
    PoseHeaderWidget, PoseRowWidget,
)


class PoseGridEditor(QtWidgets.QWidget):
    """Header + scrollable list of :class:`PoseRowWidget`.

    Signal contract (Commit 3 — C2 semantic refactor):
      poseRecallRequested(int)
      poseDeleteRequested(int)
      poseValueChangedV2(int pose_idx, str side, int source_idx,
                         str attr_name, float new_value)
      poseRadiusChanged(int pose_idx, float new_radius)
      addPoseRequested()
      deleteAllPosesRequested()

    The legacy ``poseValueChanged(int, str, int, float)`` flat_attr_idx
    form was removed in Commit 3 per the user's hard decree.
    main_window slots were updated atomically.
    """

    poseRecallRequested  = QtCore.Signal(int)
    poseDeleteRequested  = QtCore.Signal(int)
    # C2 semantic signal — per-source / attr-name carriage.
    poseValueChangedV2   = QtCore.Signal(int, str, int, str, float)
    poseRadiusChanged    = QtCore.Signal(int, float)
    addPoseRequested     = QtCore.Signal()
    deleteAllPosesRequested = QtCore.Signal()

    def __init__(self, parent=None):
        super(PoseGridEditor, self).__init__(parent)
        self._driver_sources = []
        self._driven_sources = []
        self._poses          = []
        self._header_widget  = None
        self._row_widgets    = []
        self._build()

    # ------------------------------------------------------------------
    # Build (one-shot scaffold)
    # ------------------------------------------------------------------

    def _build(self):
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(COL_MARGIN, COL_MARGIN,
                                 COL_MARGIN, COL_MARGIN)
        outer.setSpacing(COL_SPACING)

        # Empty hint shown when there are no driver/driven sources.
        self._lbl_empty_hint = QtWidgets.QLabel(
            tr("pose_grid_empty_hint"))
        self._lbl_empty_hint.setStyleSheet(
            "color: gray; font-style: italic;")
        self._lbl_empty_hint.setWordWrap(True)
        outer.addWidget(self._lbl_empty_hint)

        # Global QScrollArea — single source of truth for horizontal +
        # vertical scrolling. Per the user's spec we MUST NOT install
        # per-row scroll areas (would yield N horizontal bars for N
        # poses; UX disaster).
        self._scroll = QtWidgets.QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(
            QtCore.Qt.ScrollBarAsNeeded)
        self._scroll.setVerticalScrollBarPolicy(
            QtCore.Qt.ScrollBarAsNeeded)
        self._scroll.setFrameShape(QtWidgets.QFrame.NoFrame)

        self._inner = QtWidgets.QWidget()
        self._inner_layout = QtWidgets.QVBoxLayout(self._inner)
        self._inner_layout.setContentsMargins(0, 0, 0, 0)
        self._inner_layout.setSpacing(COL_SPACING)
        self._inner_layout.addStretch(1)
        self._scroll.setWidget(self._inner)
        outer.addWidget(self._scroll, 1)

        # Bottom action row: Add Pose + Delete Poses.
        btn_row = QtWidgets.QHBoxLayout()
        self._btn_add = QtWidgets.QPushButton(tr("add_pose"))
        self._btn_add.setToolTip(tr("pose_grid_add_pose_tip"))
        self._btn_add.clicked.connect(self.addPoseRequested)
        self._btn_delete_all = QtWidgets.QPushButton(
            tr("delete_poses"))
        self._btn_delete_all.setToolTip(
            tr("pose_grid_delete_all_tip"))
        self._btn_delete_all.clicked.connect(
            self.deleteAllPosesRequested)
        btn_row.addWidget(self._btn_add)
        btn_row.addWidget(self._btn_delete_all)
        btn_row.addStretch(1)
        outer.addLayout(btn_row)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_data(self, driver_sources, driven_sources, poses):
        """Rebuild header + rows from the supplied sources + poses."""
        self._driver_sources = list(driver_sources or [])
        self._driven_sources = list(driven_sources or [])
        self._poses          = list(poses or [])
        self._rebuild()

    def retranslate(self):
        self._lbl_empty_hint.setText(tr("pose_grid_empty_hint"))
        self._btn_add.setText(tr("add_pose"))
        self._btn_add.setToolTip(tr("pose_grid_add_pose_tip"))
        self._btn_delete_all.setText(tr("delete_poses"))
        self._btn_delete_all.setToolTip(tr("pose_grid_delete_all_tip"))
        # Header + rows are torn down + rebuilt on each set_data, so
        # any tr() string changes pick up automatically the next
        # cascade. No need to walk the existing tree here.

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _clear_inner(self):
        # Remove header (if any) + every row, leaving the trailing
        # stretch in place at index 0.
        while self._inner_layout.count() > 1:
            item = self._inner_layout.takeAt(0)
            w = item.widget() if item is not None else None
            if w is not None:
                w.deleteLater()
        self._header_widget = None
        self._row_widgets = []

    def _rebuild(self):
        self._clear_inner()

        no_sources = (
            not self._driver_sources and not self._driven_sources)
        self._lbl_empty_hint.setVisible(
            no_sources or not self._poses)
        self._scroll.setVisible(not (no_sources and not self._poses))
        if no_sources and not self._poses:
            return

        # Header: one BoneDataGroupBox per driver source (red), one
        # per driven source (blue), Radius / Actions placeholders.
        # Commit 2b: header itself is a QSplitter; we listen to its
        # moves to width-lock every row's three containers.
        self._header_widget = PoseHeaderWidget(
            self._driver_sources, self._driven_sources)
        self._header_widget.splitterMoved.connect(
            self._sync_column_widths)
        self._inner_layout.insertWidget(
            self._inner_layout.count() - 1,  # before stretch
            self._header_widget)

        # One PoseRowWidget per pose. Signals re-emitted at the
        # editor level so main_window can keep its existing slot
        # connections.
        for i, pose in enumerate(self._poses):
            inputs = list(getattr(pose, "inputs", []) or [])
            values = list(getattr(pose, "values", []) or [])
            radius = float(getattr(pose, "radius", 5.0))
            row = PoseRowWidget(
                pose_index=i,
                driver_sources=self._driver_sources,
                driven_sources=self._driven_sources,
                inputs=inputs, values=values, radius=radius)
            row.poseValueChangedV2.connect(self.poseValueChangedV2)
            row.poseRadiusChanged.connect(self.poseRadiusChanged)
            row.poseRecallRequested.connect(self.poseRecallRequested)
            row.poseDeleteRequested.connect(self.poseDeleteRequested)
            self._row_widgets.append(row)
            self._inner_layout.insertWidget(
                self._inner_layout.count() - 1,  # before stretch
                row)

        # Initial sync — the splitter has not yet computed its
        # default geometry inside the freshly-built widget tree, so
        # defer to next event-loop tick. Direct call covers headless
        # / mock environments where singleShot is a no-op.
        QtCore.QTimer.singleShot(0, self._sync_column_widths)
        self._sync_column_widths()

    # ----- Header-Driven Sync (Commit 2b) ----------------------------

    def _sync_column_widths(self, *_args):
        """Width-lock every PoseRowWidget's three containers to the
        Header QSplitter's current pane sizes. Called on
        splitterMoved + once after each set_data() rebuild + once
        on showEvent so initial state is aligned without user
        interaction."""
        if self._header_widget is None:
            return
        try:
            sizes = self._header_widget.splitter_sizes()
        except AttributeError:
            return
        if len(sizes) < 3:
            return
        drv_w, dvn_w, tail_w = sizes[0], sizes[1], sizes[2]
        for row in self._row_widgets:
            try:
                row.set_container_widths(drv_w, dvn_w, tail_w)
            except AttributeError:
                pass

    def showEvent(self, event):
        super(PoseGridEditor, self).showEvent(event)
        # First show: splitter geometry is settled; re-sync so any
        # rows built in a hidden tab pick up the correct widths.
        QtCore.QTimer.singleShot(0, self._sync_column_widths)
