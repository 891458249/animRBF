# -*- coding: utf-8 -*-
"""Commit 2 (M_UIRECONCILE2): PoseHeaderWidget + PoseRowWidget.

Implements the *Header Separation* layout the user specified for the
Pose tab refactor:

  ┌─ PoseHeaderWidget (instantiated ONCE at top of list) ─────────────┐
  │  [PoseLabel ph]  [DriverBoneBox]…  [GoBtn ph]  [DrivenBoneBox]…   │
  │                                                  [Radius ph][Acts]│
  └────────────────────────────────────────────────────────────────────┘
  ┌─ PoseRowWidget (one per pose) ────────────────────────────────────┐
  │  "Pose 0"  [drv spins]…  [Go]  [drvn spins]…  [Radius]  [Edit][X] │
  └────────────────────────────────────────────────────────────────────┘

Column widths are pinned by :data:`bone_data_widgets.COL_WIDTH` so
the bare row spinboxes sit directly under their matching header
attr labels.
"""

from __future__ import absolute_import

from RBFtools.ui.compat import QtCore, QtWidgets
from RBFtools.ui.i18n import tr
from RBFtools.ui.widgets.bone_data_widgets import (
    BoneDataGroupBox, BoneRowDataWidget,
    COL_WIDTH, COL_SPACING, COL_MARGIN,
    RADIUS_COLOR,
)


# Geometry pins so Header / Row / footer columns align across all
# instantiated rows.
POSE_LABEL_W = 70
GO_BTN_W     = 90
RADIUS_W     = 90
ACTIONS_W    = 130


# ----------------------------------------------------------------------
# Header — instantiated ONCE per Pose tab
# ----------------------------------------------------------------------


class PoseHeaderWidget(QtWidgets.QWidget):
    """Top-of-list bone-name + attr-name strip.

    Builds one :class:`BoneDataGroupBox` per driver source (red), then
    a Go-button-shaped placeholder, then one per driven source (blue),
    then a Radius / Actions placeholder pair. Column widths are pinned
    so :class:`PoseRowWidget` rows sit underneath without manual
    calibration.
    """

    def __init__(self, driver_sources, driven_sources, parent=None):
        super(PoseHeaderWidget, self).__init__(parent)
        self._driver_sources = list(driver_sources or [])
        self._driven_sources = list(driven_sources or [])

        h = QtWidgets.QHBoxLayout(self)
        h.setContentsMargins(COL_MARGIN, COL_MARGIN,
                             COL_MARGIN, COL_MARGIN)
        h.setSpacing(COL_SPACING)

        # Pose label column placeholder.
        ph_pose = QtWidgets.QLabel("")
        ph_pose.setFixedWidth(POSE_LABEL_W)
        h.addWidget(ph_pose)

        # Driver side header boxes.
        for src in self._driver_sources:
            box = BoneDataGroupBox(
                src.node, list(src.attrs), side="driver")
            h.addWidget(box)

        # Go-button column placeholder.
        ph_go = QtWidgets.QLabel("")
        ph_go.setFixedWidth(GO_BTN_W)
        h.addWidget(ph_go)

        # Driven side header boxes.
        for src in self._driven_sources:
            box = BoneDataGroupBox(
                src.node, list(src.attrs), side="driven")
            h.addWidget(box)

        # Radius column placeholder.
        ph_rad = QtWidgets.QLabel(tr("radius"))
        ph_rad.setAlignment(QtCore.Qt.AlignCenter)
        ph_rad.setFixedWidth(RADIUS_W)
        ph_rad.setStyleSheet(
            "color: {color}; font-weight: bold;"
            "border: 1px solid {color}; border-radius: 3px;"
            "padding: 2px;".format(color=RADIUS_COLOR))
        h.addWidget(ph_rad)

        # Actions column placeholder.
        ph_act = QtWidgets.QLabel("")
        ph_act.setFixedWidth(ACTIONS_W)
        h.addWidget(ph_act)

        h.addStretch(1)


# ----------------------------------------------------------------------
# Row — one instance per pose
# ----------------------------------------------------------------------


class PoseRowWidget(QtWidgets.QWidget):
    """A single pose row.

    Layout (left → right):

        [Pose N label] [driver clusters…] [Go] [driven clusters…]
            [Radius spin (green)] [Edit] [Delete]

    Signals
    -------
    poseValueChanged(int pose_idx, str side, int flat_attr_idx, float)
        Spinbox edit. ``side`` is ``"input"`` (driver) or ``"value"``
        (driven). ``flat_attr_idx`` is the index in the pose's flat
        ``inputs[]`` / ``values[]`` list (matches Commit 0/1 PoseData
        contract — Commit 3 will introduce a semantic-signal sibling).
    poseRadiusChanged(int pose_idx, float new_radius)
        The green Radius spinbox was edited.
    poseRecallRequested(int pose_idx)
        "Go to Pose" clicked.
    poseDeleteRequested(int pose_idx)
        Right-click → Delete (or future Delete button).
    """

    poseValueChanged    = QtCore.Signal(int, str, int, float)
    poseRadiusChanged   = QtCore.Signal(int, float)
    poseRecallRequested = QtCore.Signal(int)
    poseDeleteRequested = QtCore.Signal(int)

    def __init__(self, pose_index, driver_sources, driven_sources,
                 inputs, values, radius=5.0, parent=None):
        super(PoseRowWidget, self).__init__(parent)
        self._pose_index = int(pose_index)
        self._driver_sources = list(driver_sources or [])
        self._driven_sources = list(driven_sources or [])

        h = QtWidgets.QHBoxLayout(self)
        h.setContentsMargins(COL_MARGIN, COL_SPACING,
                             COL_MARGIN, COL_SPACING)
        h.setSpacing(COL_SPACING)

        # Pose label.
        self._lbl_pose = QtWidgets.QLabel(
            tr("pose_grid_row_label").format(idx=self._pose_index))
        self._lbl_pose.setFixedWidth(POSE_LABEL_W)
        self._lbl_pose.setContextMenuPolicy(
            QtCore.Qt.CustomContextMenu)
        self._lbl_pose.customContextMenuRequested.connect(
            self._show_row_menu)
        h.addWidget(self._lbl_pose)

        # Driver-side bare clusters. Walk attr offsets so flat_attr_idx
        # increments correctly across multiple sources.
        flat = 0
        for src in self._driver_sources:
            attrs = list(src.attrs)
            slice_vals = inputs[flat:flat + len(attrs)] if inputs else []
            cluster = BoneRowDataWidget(attrs, slice_vals)
            cluster.valueChanged.connect(
                lambda local_i, val, _base=flat:
                    self.poseValueChanged.emit(
                        self._pose_index, "input",
                        _base + int(local_i), float(val)))
            h.addWidget(cluster)
            flat += len(attrs)

        # Go to Pose.
        self._btn_go = QtWidgets.QPushButton(tr("pose_grid_go_to_pose"))
        self._btn_go.setToolTip(tr("pose_grid_go_to_pose_tip"))
        self._btn_go.setFixedWidth(GO_BTN_W)
        self._btn_go.clicked.connect(
            lambda _checked=False:
                self.poseRecallRequested.emit(self._pose_index))
        h.addWidget(self._btn_go)

        # Driven-side bare clusters.
        flat = 0
        for src in self._driven_sources:
            attrs = list(src.attrs)
            slice_vals = values[flat:flat + len(attrs)] if values else []
            cluster = BoneRowDataWidget(attrs, slice_vals)
            cluster.valueChanged.connect(
                lambda local_i, val, _base=flat:
                    self.poseValueChanged.emit(
                        self._pose_index, "value",
                        _base + int(local_i), float(val)))
            h.addWidget(cluster)
            flat += len(attrs)

        # Green Radius spin (per-pose σ — wired through Commit 0/1 schema).
        self._radius_box = QtWidgets.QGroupBox()
        self._radius_box.setStyleSheet(
            "QGroupBox {{ border: 1px solid {color}; border-radius: 3px;"
            "padding: 1px; margin: 0px; }}"
            "QDoubleSpinBox {{ color: {color}; }}".format(
                color=RADIUS_COLOR))
        self._radius_box.setFixedWidth(RADIUS_W)
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
        h.addWidget(self._radius_box)

        # Actions: Update (re-capture this pose, semantics match the
        # legacy "Edit" affordance) + Delete. tr("update") and
        # tr("delete") already in i18n.
        self._btn_edit = QtWidgets.QPushButton(tr("update"))
        self._btn_edit.setFixedWidth(ACTIONS_W // 2 - 4)
        self._btn_edit.clicked.connect(
            lambda _checked=False:
                self.poseRecallRequested.emit(self._pose_index))
        h.addWidget(self._btn_edit)
        self._btn_del = QtWidgets.QPushButton(tr("delete"))
        self._btn_del.setFixedWidth(ACTIONS_W // 2 - 4)
        self._btn_del.clicked.connect(
            lambda _checked=False:
                self.poseDeleteRequested.emit(self._pose_index))
        h.addWidget(self._btn_del)

        h.addStretch(1)

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
