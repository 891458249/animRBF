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

    Signals (Commit 3 — C2 semantic refactor)
    -------
    poseValueChangedV2(int pose_idx, str side, int source_idx,
                       str attr_name, float new_value)
        Spinbox edit. ``side`` is ``"input"`` (driver) or ``"value"``
        (driven). ``source_idx`` indexes into the side's source list;
        ``attr_name`` is the literal attr (``"rotateX"`` etc.). The
        legacy flat_attr_idx form was dropped per the user's hard
        decree — semantic-arg form is the single supported contract.
        ``pose_idx == -1`` is the BasePose sentinel: the row was
        constructed with ``is_base_pose=True`` and edits should write
        to ``shape.basePoseValue[]`` rather than ``shape.poses[]``.
    poseRadiusChanged(int pose_idx, float new_radius)
        The green Radius spinbox was edited (suppressed in BasePose
        mode — radius has no semantic on the rest pose).
    poseRecallRequested(int pose_idx)
        "Go to Pose" clicked. ``pose_idx == -1`` => recall basePose.
    poseDeleteRequested(int pose_idx)
        Right-click → Delete (suppressed in BasePose mode).
    """

    # C2 semantic signal — replaces legacy poseValueChanged.
    poseValueChangedV2  = QtCore.Signal(int, str, int, str, float)
    poseRadiusChanged   = QtCore.Signal(int, float)
    poseRecallRequested = QtCore.Signal(int)
    poseDeleteRequested = QtCore.Signal(int)

    BASE_POSE_SENTINEL = -1

    def __init__(self, pose_index, driver_sources, driven_sources,
                 inputs, values, radius=5.0, parent=None,
                 is_base_pose=False):
        super(PoseRowWidget, self).__init__(parent)
        self._pose_index = int(pose_index)
        self._is_base_pose = bool(is_base_pose)
        self._driver_sources = list(driver_sources or [])
        self._driven_sources = list(driven_sources or [])

        h = QtWidgets.QHBoxLayout(self)
        h.setContentsMargins(COL_MARGIN, COL_SPACING,
                             COL_MARGIN, COL_SPACING)
        h.setSpacing(COL_SPACING)

        # Pose label. BasePose mode: literal "Base Pose" instead of
        # the indexed format, so the UI is self-explanatory and the
        # right-click "Delete" affordance is suppressed.
        if self._is_base_pose:
            label_text = tr("base_pose_label_fallback")
        else:
            label_text = tr("pose_grid_row_label").format(
                idx=self._pose_index)
        self._lbl_pose = QtWidgets.QLabel(label_text)
        self._lbl_pose.setFixedWidth(POSE_LABEL_W)
        if not self._is_base_pose:
            self._lbl_pose.setContextMenuPolicy(
                QtCore.Qt.CustomContextMenu)
            self._lbl_pose.customContextMenuRequested.connect(
                self._show_row_menu)
        h.addWidget(self._lbl_pose)

        # Driver-side bare clusters. Each cluster's local valueChanged
        # is mapped to the C2 semantic signal carrying the source_idx
        # + attr_name pair (no more flat_attr_idx). In BasePose mode
        # the driver clusters are visible (so the Header sits over
        # *something*) but disabled — basePose has no driver semantic;
        # only the driven-side baseline is meaningful.
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
            h.addWidget(cluster)

        # Go to Pose.
        self._btn_go = QtWidgets.QPushButton(tr("pose_grid_go_to_pose"))
        self._btn_go.setToolTip(tr("pose_grid_go_to_pose_tip"))
        self._btn_go.setFixedWidth(GO_BTN_W)
        self._btn_go.clicked.connect(
            lambda _checked=False:
                self.poseRecallRequested.emit(self._pose_index))
        h.addWidget(self._btn_go)

        # Driven-side bare clusters. Always editable — driven side is
        # the meaningful axis for both regular poses and the BasePose
        # baseline.
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
            h.addWidget(cluster)

        # Green Radius spin (per-pose σ — wired through Commit 0/1
        # schema). Hidden in BasePose mode per user spec: BasePose has
        # no influence-radius concept (it is a single fixed baseline,
        # not a kernel center).
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
        if self._is_base_pose:
            self._radius_box.setVisible(False)

        # Actions: Update (re-capture this pose, semantics match the
        # legacy "Edit" affordance) + Delete. Hidden in BasePose mode
        # per user spec: rest pose is unique and cannot be deleted.
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
        if self._is_base_pose:
            self._btn_edit.setVisible(False)
            self._btn_del.setVisible(False)

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
