# -*- coding: utf-8 -*-
"""Commit 2 (M_UIRECONCILE2) + Commit 2b (M_UI_SPLITTER): Header +
Row composers for the Pose / BaseDrivenPose tabs.

Layout (Commit 2b — *Header-Driven Sync*):

  ┌─ PoseHeaderWidget ─────────────────────────────────────────────┐
  │ ┌── QSplitter(H), children-non-collapsible ──────────────────┐ │
  │ │ DriverContainer│ DrivenContainer │ TailContainer (Radius)  │ │
  │ │ pose_lbl + N×  │ go_btn + N×     │ radius_hdr + acts_ph    │ │
  │ │ BoneDataGrpBox │ BoneDataGrpBox  │                         │ │
  │ └──────^─────────────────^────────────────^──────────────────┘ │
  │  user-draggable column boundaries (the only QSplitter on tab)  │
  └────────|──splitterMoved───|────────────────|──────────────────┘
           ▼                  ▼                ▼
  ┌─ PoseRowWidget (one per pose; NO splitter inside) ─────────────┐
  │  driver_container│  driven_container│  tail_container          │
  │  width-locked from header pane sizes via set_container_widths()│
  └────────────────────────────────────────────────────────────────┘

Width sync contract: PoseGridEditor (and BasePoseEditor) listen to
the header's :attr:`splitterMoved` signal, query
:meth:`PoseHeaderWidget.splitter_sizes`, and call
:meth:`PoseRowWidget.set_container_widths` on every row so the three
column tracks line up across header + N rows. An initial sync runs
after every :meth:`PoseGridEditor.set_data` rebuild + a one-shot
``QTimer.singleShot(0, ...)`` so Qt has time to compute the splitter's
default geometry.
"""

from __future__ import absolute_import

from RBFtools.ui.compat import QtCore, QtWidgets
from RBFtools.ui.i18n import tr
from RBFtools.ui.widgets.bone_data_widgets import (
    BoneDataGroupBox, BoneRowDataWidget,
    COL_SPACING, COL_MARGIN,
    RADIUS_COLOR,
)


# Minimum widths (Commit 2b: hints, not absolute pins). The Header
# QSplitter drives runtime sizes; these establish floors so the user
# can't drag a column into oblivion.
POSE_LABEL_MIN_W = 60
GO_BTN_MIN_W     = 70
RADIUS_MIN_W     = 80
ACTIONS_MIN_W    = 110


# ----------------------------------------------------------------------
# Header — instantiated ONCE per Pose / BaseDrivenPose tab
# ----------------------------------------------------------------------


class PoseHeaderWidget(QtWidgets.QWidget):
    """Top-of-list bone-name + attr-name strip.

    Outer layout is a horizontal QSplitter with three panes:

      0. driver_container — pose-label placeholder + per-driver-source
         BoneDataGroupBox (red).
      1. driven_container — go-button placeholder + per-driven-source
         BoneDataGroupBox (blue).
      2. tail_container   — radius-column header + actions placeholder.

    Re-emits ``splitterMoved(int pos, int index)`` so PoseGridEditor /
    BasePoseEditor can keep the row containers width-locked to the
    header's pane sizes.
    """

    splitterMoved = QtCore.Signal(int, int)

    def __init__(self, driver_sources, driven_sources, parent=None):
        super(PoseHeaderWidget, self).__init__(parent)
        self._driver_sources = list(driver_sources or [])
        self._driven_sources = list(driven_sources or [])

        outer = QtWidgets.QHBoxLayout(self)
        outer.setContentsMargins(COL_MARGIN, COL_MARGIN,
                                 COL_MARGIN, COL_MARGIN)
        outer.setSpacing(0)

        self._splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        self._splitter.setChildrenCollapsible(False)
        self._splitter.splitterMoved.connect(self.splitterMoved)
        outer.addWidget(self._splitter, 1)

        # Pane 0: Driver header.
        drv_c = QtWidgets.QWidget()
        drv_l = QtWidgets.QHBoxLayout(drv_c)
        drv_l.setContentsMargins(0, 0, 0, 0)
        drv_l.setSpacing(COL_SPACING)
        ph_pose = QtWidgets.QLabel("")
        ph_pose.setMinimumWidth(POSE_LABEL_MIN_W)
        drv_l.addWidget(ph_pose)
        for src in self._driver_sources:
            box = BoneDataGroupBox(
                src.node, list(src.attrs), side="driver")
            drv_l.addWidget(box, 1)
        drv_l.addStretch(1)
        self._splitter.addWidget(drv_c)

        # Pane 1: Driven header.
        dvn_c = QtWidgets.QWidget()
        dvn_l = QtWidgets.QHBoxLayout(dvn_c)
        dvn_l.setContentsMargins(0, 0, 0, 0)
        dvn_l.setSpacing(COL_SPACING)
        ph_go = QtWidgets.QLabel("")
        ph_go.setMinimumWidth(GO_BTN_MIN_W)
        dvn_l.addWidget(ph_go)
        for src in self._driven_sources:
            box = BoneDataGroupBox(
                src.node, list(src.attrs), side="driven")
            dvn_l.addWidget(box, 1)
        dvn_l.addStretch(1)
        self._splitter.addWidget(dvn_c)

        # Pane 2: Tail (Radius header + Actions placeholder).
        tail_c = QtWidgets.QWidget()
        tail_l = QtWidgets.QHBoxLayout(tail_c)
        tail_l.setContentsMargins(0, 0, 0, 0)
        tail_l.setSpacing(COL_SPACING)
        ph_rad = QtWidgets.QLabel(tr("radius"))
        ph_rad.setAlignment(QtCore.Qt.AlignCenter)
        ph_rad.setMinimumWidth(RADIUS_MIN_W)
        ph_rad.setStyleSheet(
            "color: {color}; font-weight: bold;"
            "border: 1px solid {color}; border-radius: 3px;"
            "padding: 2px;".format(color=RADIUS_COLOR))
        tail_l.addWidget(ph_rad)
        ph_act = QtWidgets.QLabel("")
        ph_act.setMinimumWidth(ACTIONS_MIN_W)
        tail_l.addWidget(ph_act)
        tail_l.addStretch(1)
        self._splitter.addWidget(tail_c)

        # Initial stretch — driver / driven get the bulk; tail compact.
        self._splitter.setStretchFactor(0, 3)
        self._splitter.setStretchFactor(1, 3)
        self._splitter.setStretchFactor(2, 1)

    def splitter_sizes(self):
        """Return ``[drv_w, dvn_w, tail_w]`` (current Splitter pane
        sizes). Used by PoseGridEditor / BasePoseEditor to width-lock
        every row's matching containers."""
        return list(self._splitter.sizes())


# ----------------------------------------------------------------------
# Row — one instance per pose
# ----------------------------------------------------------------------


class PoseRowWidget(QtWidgets.QWidget):
    """A single pose row.

    Outer is a single QHBoxLayout (NO splitter — only the header has a
    splitter; rows mirror its sizes via :meth:`set_container_widths`).
    Three containers mirror the header's three panes:

      ``driver_container`` — pose-label + driver BoneRowDataWidgets
      ``driven_container`` — go-button + driven BoneRowDataWidgets
      ``tail_container``   — green Radius spin + Update + Delete

    Signals — see module docstring of base_pose_editor.py for the
    BasePose sentinel contract; otherwise:

      poseValueChangedV2(int pose_idx, str side, int source_idx,
                         str attr_name, float new_value)
      poseRadiusChanged(int pose_idx, float new_radius)
      poseRecallRequested(int pose_idx)
      poseUpdateRequested(int pose_idx)   # M_P0_UPDATE_BUTTON_REVERSED
      poseDeleteRequested(int pose_idx)

    M_P0_UPDATE_BUTTON_REVERSED (2026-04-30): the per-row "Update"
    button (``self._btn_edit``) emits ``poseUpdateRequested`` —
    the controller-side path that snapshots the current viewport
    driver/driven values into the existing pose row. This is the
    INVERSE of ``poseRecallRequested`` (which is the "Go to Pose"
    path: pose data -> viewport). The right-click menu Recall +
    the row double-click both still emit ``poseRecallRequested``;
    those channels are independent of the Update button.
    """

    poseValueChangedV2  = QtCore.Signal(int, str, int, str, float)
    poseRadiusChanged   = QtCore.Signal(int, float)
    poseRecallRequested = QtCore.Signal(int)
    poseUpdateRequested = QtCore.Signal(int)
    poseDeleteRequested = QtCore.Signal(int)

    BASE_POSE_SENTINEL = -1

    def __init__(self, pose_index, driver_sources, driven_sources,
                 inputs, values, radius=5.0, parent=None,
                 is_base_pose=False):
        super(PoseRowWidget, self).__init__(parent)
        self._pose_index   = int(pose_index)
        self._is_base_pose = bool(is_base_pose)
        self._driver_sources = list(driver_sources or [])
        self._driven_sources = list(driven_sources or [])

        outer = QtWidgets.QHBoxLayout(self)
        outer.setContentsMargins(COL_MARGIN, COL_SPACING,
                                 COL_MARGIN, COL_SPACING)
        outer.setSpacing(0)

        # ----- driver_container -------------------------------------
        self._driver_container = QtWidgets.QWidget()
        drv_l = QtWidgets.QHBoxLayout(self._driver_container)
        drv_l.setContentsMargins(0, 0, 0, 0)
        drv_l.setSpacing(COL_SPACING)

        if self._is_base_pose:
            label_text = tr("base_pose_label_fallback")
        else:
            label_text = tr("pose_grid_row_label").format(
                idx=self._pose_index)
        self._lbl_pose = QtWidgets.QLabel(label_text)
        self._lbl_pose.setMinimumWidth(POSE_LABEL_MIN_W)
        if not self._is_base_pose:
            self._lbl_pose.setContextMenuPolicy(
                QtCore.Qt.CustomContextMenu)
            self._lbl_pose.customContextMenuRequested.connect(
                self._show_row_menu)
        drv_l.addWidget(self._lbl_pose)

        for src_idx, src in enumerate(self._driver_sources):
            attrs = list(src.attrs)
            attr_offset = sum(
                len(s.attrs) for s in self._driver_sources[:src_idx])
            slice_vals = (inputs[attr_offset:attr_offset + len(attrs)]
                          if inputs else [])
            cluster = BoneRowDataWidget(attrs, slice_vals)
            if self._is_base_pose:
                cluster.setEnabled(False)
            else:
                cluster.valueChanged.connect(
                    lambda local_i, val, _src=src_idx, _attrs=attrs:
                        self.poseValueChangedV2.emit(
                            self._pose_index, "input",
                            int(_src),
                            str(_attrs[int(local_i)]),
                            float(val)))
            drv_l.addWidget(cluster, 1)
        drv_l.addStretch(1)
        outer.addWidget(self._driver_container)

        # ----- driven_container -------------------------------------
        self._driven_container = QtWidgets.QWidget()
        dvn_l = QtWidgets.QHBoxLayout(self._driven_container)
        dvn_l.setContentsMargins(0, 0, 0, 0)
        dvn_l.setSpacing(COL_SPACING)

        self._btn_go = QtWidgets.QPushButton(tr("pose_grid_go_to_pose"))
        self._btn_go.setToolTip(tr("pose_grid_go_to_pose_tip"))
        self._btn_go.setMinimumWidth(GO_BTN_MIN_W)
        self._btn_go.clicked.connect(
            lambda _checked=False:
                self.poseRecallRequested.emit(self._pose_index))
        dvn_l.addWidget(self._btn_go)

        for src_idx, src in enumerate(self._driven_sources):
            attrs = list(src.attrs)
            attr_offset = sum(
                len(s.attrs) for s in self._driven_sources[:src_idx])
            slice_vals = (values[attr_offset:attr_offset + len(attrs)]
                          if values else [])
            cluster = BoneRowDataWidget(attrs, slice_vals)
            cluster.valueChanged.connect(
                lambda local_i, val, _src=src_idx, _attrs=attrs:
                    self.poseValueChangedV2.emit(
                        self._pose_index, "value",
                        int(_src),
                        str(_attrs[int(local_i)]),
                        float(val)))
            dvn_l.addWidget(cluster, 1)
        dvn_l.addStretch(1)
        outer.addWidget(self._driven_container)

        # ----- tail_container (Radius + Actions) ---------------------
        self._tail_container = QtWidgets.QWidget()
        tail_l = QtWidgets.QHBoxLayout(self._tail_container)
        tail_l.setContentsMargins(0, 0, 0, 0)
        tail_l.setSpacing(COL_SPACING)

        self._radius_box = QtWidgets.QGroupBox()
        self._radius_box.setStyleSheet(
            "QGroupBox {{ border: 1px solid {color}; border-radius: 3px;"
            "padding: 1px; margin: 0px; }}"
            "QDoubleSpinBox {{ color: {color}; }}".format(
                color=RADIUS_COLOR))
        self._radius_box.setMinimumWidth(RADIUS_MIN_W)
        rb_l = QtWidgets.QHBoxLayout(self._radius_box)
        rb_l.setContentsMargins(2, 2, 2, 2)
        rb_l.setSpacing(0)
        self._spin_radius = QtWidgets.QDoubleSpinBox()
        self._spin_radius.setRange(0.0, 1e6)
        self._spin_radius.setDecimals(3)
        self._spin_radius.setSingleStep(0.5)
        try:
            self._spin_radius.setValue(float(radius))
        except (TypeError, ValueError):
            self._spin_radius.setValue(5.0)
        self._spin_radius.valueChanged.connect(
            lambda v: self.poseRadiusChanged.emit(
                self._pose_index, float(v)))
        rb_l.addWidget(self._spin_radius)
        tail_l.addWidget(self._radius_box)
        if self._is_base_pose:
            self._radius_box.setVisible(False)

        self._btn_edit = QtWidgets.QPushButton(tr("update"))
        self._btn_edit.setMinimumWidth(ACTIONS_MIN_W // 2 - 4)
        # M_P0_UPDATE_BUTTON_REVERSED (2026-04-30): the button text
        # is "Update" — emit poseUpdateRequested (snapshot viewport
        # -> pose model). The original wiring sent poseRecallRequested
        # (pose -> viewport) which is the literal inverse and made
        # the button effectively a "Go to Pose" duplicate of the
        # right-click menu. The right-click Recall + row double-
        # click still use poseRecallRequested independently.
        self._btn_edit.clicked.connect(
            lambda _checked=False:
                self.poseUpdateRequested.emit(self._pose_index))
        tail_l.addWidget(self._btn_edit)
        self._btn_del = QtWidgets.QPushButton(tr("delete"))
        self._btn_del.setMinimumWidth(ACTIONS_MIN_W // 2 - 4)
        self._btn_del.clicked.connect(
            lambda _checked=False:
                self.poseDeleteRequested.emit(self._pose_index))
        tail_l.addWidget(self._btn_del)
        if self._is_base_pose:
            self._btn_edit.setVisible(False)
            self._btn_del.setVisible(False)
        tail_l.addStretch(1)
        outer.addWidget(self._tail_container)

        outer.addStretch(0)

    # -- Header-Driven Sync API ----------------------------------------

    def set_container_widths(self, drv_w, dvn_w, tail_w):
        """Commit 2b: width-lock the three row containers to the
        header's QSplitter pane sizes. Called by the parent
        PoseGridEditor / BasePoseEditor on splitterMoved + once
        after every set_data() rebuild."""
        for c, w in ((self._driver_container, drv_w),
                     (self._driven_container, dvn_w),
                     (self._tail_container,   tail_w)):
            wi = max(int(w), 0)
            c.setMinimumWidth(wi)
            c.setMaximumWidth(wi)

    # -- internal --

    def _show_row_menu(self, _pos):
        menu = QtWidgets.QMenu(self)
        act_recall = menu.addAction(tr("recall"))
        act_delete = menu.addAction(tr("delete"))
        chosen = menu.exec_(QtCore.QCursor.pos()
                            if hasattr(QtCore, "QCursor")
                            else None)
        if chosen is act_recall:
            self.poseRecallRequested.emit(self._pose_index)
        elif chosen is act_delete:
            self.poseDeleteRequested.emit(self._pose_index)
