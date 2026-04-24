# -*- coding: utf-8 -*-
"""
RBF section — kernel, radius, scale, generic-RBF, matrix-RBF and solver display.
"""

from __future__ import absolute_import

from RBFtools.ui.compat import QtWidgets, QtCore
from RBFtools.ui.i18n import tr
from RBFtools.ui.widgets.collapsible import CollapsibleFrame
from RBFtools.ui.widgets.help_button import HelpButton, ComboHelpButton
from RBFtools.constants import (
    KERNEL_LABELS, RADIUS_TYPE_LABELS, DISTANCE_TYPE_LABELS,
    TWIST_AXIS_LABELS, RBF_MODE_LABELS,
)


class RBFSection(CollapsibleFrame):
    """All RBF-mode controls in a single collapsible section."""

    attributeChanged = QtCore.Signal(str, object)
    kernelChanged = QtCore.Signal(int)
    radiusTypeChanged = QtCore.Signal(int)
    radiusEdited = QtCore.Signal(float)

    def __init__(self, parent=None):
        super(RBFSection, self).__init__(
            title=tr("rbf"), parent=parent)
        self._build()

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _build(self):
        lay = self.content_layout()

        # Kernel
        row_k = QtWidgets.QHBoxLayout()
        self._lbl_kernel = QtWidgets.QLabel(tr("kernel"))
        self._cmb_kernel = QtWidgets.QComboBox()
        for k in KERNEL_LABELS:
            self._cmb_kernel.addItem(k)
        self._cmb_kernel.currentIndexChanged.connect(self._on_kernel)
        row_k.addWidget(self._lbl_kernel)
        row_k.addWidget(self._cmb_kernel, 1)
        row_k.addWidget(ComboHelpButton(
            self._cmb_kernel, [
                "kernel_linear", "kernel_gaussian1", "kernel_gaussian2",
                "kernel_thin_plate", "kernel_multi_quadratic",
                "kernel_inv_multi_quadratic",
            ], fallback_key="kernel"))
        lay.addLayout(row_k)

        # Radius type
        row_rt = QtWidgets.QHBoxLayout()
        self._lbl_rtype = QtWidgets.QLabel(tr("radius_type"))
        self._cmb_rtype = QtWidgets.QComboBox()
        for r in RADIUS_TYPE_LABELS:
            self._cmb_rtype.addItem(r)
        self._cmb_rtype.currentIndexChanged.connect(self._on_rtype)
        row_rt.addWidget(self._lbl_rtype)
        row_rt.addWidget(self._cmb_rtype, 1)
        row_rt.addWidget(ComboHelpButton(
            self._cmb_rtype, [
                "rtype_mean_distance", "rtype_variance",
                "rtype_std_dev", "rtype_custom",
            ], fallback_key="radius_type"))
        lay.addLayout(row_rt)

        # Radius
        row_r = QtWidgets.QHBoxLayout()
        self._lbl_radius = QtWidgets.QLabel(tr("radius"))
        self._spn_radius = QtWidgets.QDoubleSpinBox()
        self._spn_radius.setRange(0.0, 9999.0)
        self._spn_radius.setDecimals(4)
        self._spn_radius.valueChanged.connect(self._on_radius_edit)
        row_r.addWidget(self._lbl_radius)
        row_r.addWidget(self._spn_radius, 1)
        row_r.addWidget(HelpButton("radius"))
        lay.addLayout(row_r)

        # Allow negative weights
        row_neg = QtWidgets.QHBoxLayout()
        self._cb_neg = QtWidgets.QCheckBox(tr("allow_neg"))
        self._cb_neg.setChecked(True)
        self._cb_neg.toggled.connect(
            lambda v: self.attributeChanged.emit("allowNegativeWeights", v))
        row_neg.addWidget(self._cb_neg)
        row_neg.addStretch()
        row_neg.addWidget(HelpButton("allow_neg"))
        lay.addLayout(row_neg)

        # Scale
        row_s = QtWidgets.QHBoxLayout()
        self._lbl_scale = QtWidgets.QLabel(tr("scale"))
        self._spn_scale = QtWidgets.QDoubleSpinBox()
        self._spn_scale.setRange(0.0, 100.0)
        self._spn_scale.setDecimals(3)
        self._spn_scale.setValue(1.0)
        self._spn_scale.valueChanged.connect(
            lambda v: self.attributeChanged.emit("scale", v))
        row_s.addWidget(self._lbl_scale)
        row_s.addWidget(self._spn_scale, 1)
        row_s.addWidget(HelpButton("rbf_scale"))
        lay.addLayout(row_s)

        # RBF Mode
        row_m = QtWidgets.QHBoxLayout()
        self._lbl_mode = QtWidgets.QLabel(tr("rbf_mode"))
        self._cmb_mode = QtWidgets.QComboBox()
        for m in RBF_MODE_LABELS:
            self._cmb_mode.addItem(m)
        self._cmb_mode.currentIndexChanged.connect(self._on_rbf_mode)
        row_m.addWidget(self._lbl_mode)
        row_m.addWidget(self._cmb_mode, 1)
        row_m.addWidget(ComboHelpButton(
            self._cmb_mode, [
                "rbf_mode_generic", "rbf_mode_matrix",
            ], fallback_key="rbf_mode"))
        lay.addLayout(row_m)

        lay.addWidget(self._separator())

        # -- Generic RBF --
        self._generic_frame = CollapsibleFrame(tr("generic_rbf"), collapsed=True)
        glay = self._generic_frame.content_layout()

        row_dt = QtWidgets.QHBoxLayout()
        self._lbl_dist = QtWidgets.QLabel(tr("distance_type"))
        self._cmb_dist = QtWidgets.QComboBox()
        for d in DISTANCE_TYPE_LABELS:
            self._cmb_dist.addItem(d)
        self._cmb_dist.currentIndexChanged.connect(
            lambda v: self.attributeChanged.emit("distanceType", v))
        row_dt.addWidget(self._lbl_dist)
        row_dt.addWidget(self._cmb_dist, 1)
        row_dt.addWidget(ComboHelpButton(
            self._cmb_dist, [
                "dist_euclidean", "dist_angle",
            ], fallback_key="distance_type"))
        glay.addLayout(row_dt)

        lay.addWidget(self._generic_frame)

        # -- Matrix RBF --
        self._matrix_frame = CollapsibleFrame(tr("matrix_rbf"), collapsed=True)
        mlay = self._matrix_frame.content_layout()

        row_ta = QtWidgets.QHBoxLayout()
        self._lbl_taxis = QtWidgets.QLabel(tr("twist_axis"))
        self._cmb_taxis = QtWidgets.QComboBox()
        for t in TWIST_AXIS_LABELS:
            self._cmb_taxis.addItem(t)
        self._cmb_taxis.currentIndexChanged.connect(
            lambda v: self.attributeChanged.emit("twistAxis", v))
        row_ta.addWidget(self._lbl_taxis)
        row_ta.addWidget(self._cmb_taxis, 1)
        row_ta.addWidget(ComboHelpButton(
            self._cmb_taxis, [
                "twist_axis_x", "twist_axis_y", "twist_axis_z",
            ], fallback_key="twist_axis"))
        mlay.addLayout(row_ta)

        # -- Solver Display (nested inside matrix) --
        self._solver_frame = CollapsibleFrame(tr("solver_display"), collapsed=True)
        slay = self._solver_frame.content_layout()

        row_do = QtWidgets.QHBoxLayout()
        self._cb_origin = QtWidgets.QCheckBox(tr("draw_origin"))
        self._cb_origin.toggled.connect(
            lambda v: self.attributeChanged.emit("drawOrigin", v))
        row_do.addWidget(self._cb_origin)
        row_do.addStretch()
        row_do.addWidget(HelpButton("draw_origin"))
        slay.addLayout(row_do)

        row_dp = QtWidgets.QHBoxLayout()
        self._cb_poses = QtWidgets.QCheckBox(tr("draw_poses"))
        self._cb_poses.toggled.connect(
            lambda v: self.attributeChanged.emit("drawPoses", v))
        row_dp.addWidget(self._cb_poses)
        row_dp.addStretch()
        row_dp.addWidget(HelpButton("draw_poses"))
        slay.addLayout(row_dp)

        self._spn_pose_len = self._add_float_to(
            slay, "poseLength", tr("pose_length"), 0.01, 10.0, 1.0,
            "pose_length")

        row_di2 = QtWidgets.QHBoxLayout()
        self._cb_indices = QtWidgets.QCheckBox(tr("draw_indices"))
        self._cb_indices.toggled.connect(
            lambda v: self.attributeChanged.emit("drawIndices", v))
        row_di2.addWidget(self._cb_indices)
        row_di2.addStretch()
        row_di2.addWidget(HelpButton("draw_indices"))
        slay.addLayout(row_di2)

        self._spn_idx_dist = self._add_float_to(
            slay, "indexDistance", tr("index_distance"), 0.0, 100.0, 0.0,
            "index_distance")

        row_dtw = QtWidgets.QHBoxLayout()
        self._cb_draw_twist = QtWidgets.QCheckBox(tr("draw_twist"))
        self._cb_draw_twist.toggled.connect(
            lambda v: self.attributeChanged.emit("drawTwist", v))
        row_dtw.addWidget(self._cb_draw_twist)
        row_dtw.addStretch()
        row_dtw.addWidget(HelpButton("draw_twist"))
        slay.addLayout(row_dtw)

        row_opp = QtWidgets.QHBoxLayout()
        self._cb_opposite = QtWidgets.QCheckBox(tr("opposite"))
        self._cb_opposite.toggled.connect(
            lambda v: self.attributeChanged.emit("opposite", v))
        row_opp.addWidget(self._cb_opposite)
        row_opp.addStretch()
        row_opp.addWidget(HelpButton("opposite"))
        slay.addLayout(row_opp)

        # Driver index
        row_di = QtWidgets.QHBoxLayout()
        self._lbl_dridx = QtWidgets.QLabel(tr("driver_index"))
        self._spn_dridx = QtWidgets.QSpinBox()
        self._spn_dridx.setRange(0, 99)
        self._spn_dridx.valueChanged.connect(
            lambda v: self.attributeChanged.emit("driverIndex", v))
        row_di.addWidget(self._lbl_dridx)
        row_di.addWidget(self._spn_dridx, 1)
        row_di.addWidget(HelpButton("driver_index"))
        slay.addLayout(row_di)

        mlay.addWidget(self._solver_frame)
        lay.addWidget(self._matrix_frame)

        # Initial visibility: Generic mode (0) by default
        self._update_mode_visibility(0)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _add_float_to(self, parent_lay, attr, label, mn, mx, default,
                      help_key=None):
        row = QtWidgets.QHBoxLayout()
        lbl = QtWidgets.QLabel(label)
        spn = QtWidgets.QDoubleSpinBox()
        spn.setRange(mn, mx)
        spn.setDecimals(3)
        spn.setValue(default)
        spn.valueChanged.connect(
            lambda v, a=attr: self.attributeChanged.emit(a, v))
        row.addWidget(lbl)
        row.addWidget(spn, 1)
        if help_key:
            row.addWidget(HelpButton(help_key))
        parent_lay.addLayout(row)
        spn.setProperty("_lbl", lbl)
        return spn

    @staticmethod
    def _separator():
        line = QtWidgets.QFrame()
        line.setFrameShape(QtWidgets.QFrame.HLine)
        line.setFrameShadow(QtWidgets.QFrame.Sunken)
        return line

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self, data):
        if data is None:
            return
        self._cmb_kernel.setCurrentIndex(data.get("kernel", 0))
        self._cmb_rtype.setCurrentIndex(data.get("radiusType", 0))
        self._spn_radius.setValue(data.get("radius", 0.0))
        self._cb_neg.setChecked(data.get("allowNegativeWeights", True))
        self._spn_scale.setValue(data.get("scale", 1.0))
        self._cmb_mode.setCurrentIndex(data.get("rbfMode", 0))
        self._cmb_dist.setCurrentIndex(data.get("distanceType", 0))
        self._cmb_taxis.setCurrentIndex(data.get("twistAxis", 0))
        self._cb_origin.setChecked(data.get("drawOrigin", False))
        self._cb_poses.setChecked(data.get("drawPoses", False))
        self._spn_pose_len.setValue(data.get("poseLength", 1.0))
        self._cb_indices.setChecked(data.get("drawIndices", False))
        self._spn_idx_dist.setValue(data.get("indexDistance", 0.0))
        self._cb_draw_twist.setChecked(data.get("drawTwist", False))
        self._cb_opposite.setChecked(data.get("opposite", False))
        self._spn_dridx.setValue(data.get("driverIndex", 0))
        self._update_radius_state()
        self._update_mode_visibility(self._cmb_mode.currentIndex())

    def set_radius_value(self, value):
        """Update radius display without emitting."""
        blocked = self._spn_radius.blockSignals(True)
        self._spn_radius.setValue(value)
        self._spn_radius.blockSignals(blocked)

    def set_radius_enabled(self, enabled):
        self._spn_radius.setEnabled(enabled)

    def set_radius_type_enabled(self, enabled):
        self._cmb_rtype.setEnabled(enabled)

    def retranslate(self):
        self.set_title(tr("rbf"))
        self._lbl_kernel.setText(tr("kernel"))
        self._lbl_rtype.setText(tr("radius_type"))
        self._lbl_radius.setText(tr("radius"))
        self._cb_neg.setText(tr("allow_neg"))
        self._lbl_scale.setText(tr("scale"))
        self._lbl_mode.setText(tr("rbf_mode"))
        self._generic_frame.set_title(tr("generic_rbf"))
        self._lbl_dist.setText(tr("distance_type"))
        self._matrix_frame.set_title(tr("matrix_rbf"))
        self._lbl_taxis.setText(tr("twist_axis"))
        self._solver_frame.set_title(tr("solver_display"))
        self._cb_origin.setText(tr("draw_origin"))
        self._cb_poses.setText(tr("draw_poses"))
        self._cb_indices.setText(tr("draw_indices"))
        self._cb_draw_twist.setText(tr("draw_twist"))
        self._cb_opposite.setText(tr("opposite"))
        self._lbl_dridx.setText(tr("driver_index"))

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _on_rbf_mode(self, idx):
        self.attributeChanged.emit("rbfMode", idx)
        self._update_mode_visibility(idx)

    def _update_mode_visibility(self, idx):
        """Show Generic sub-section for mode 0, Matrix sub-section for mode 1."""
        self._generic_frame.setVisible(idx == 0)
        self._matrix_frame.setVisible(idx == 1)

    def _on_kernel(self, idx):
        self.attributeChanged.emit("kernel", idx)
        self.kernelChanged.emit(idx)

    def _on_rtype(self, idx):
        self.attributeChanged.emit("radiusType", idx)
        self.radiusTypeChanged.emit(idx)

    def _on_radius_edit(self, val):
        # Only forward edits when radius type is Custom (3)
        if self._cmb_rtype.currentIndex() == 3:
            self.radiusEdited.emit(val)

    def _update_radius_state(self):
        is_custom = self._cmb_rtype.currentIndex() == 3
        self._spn_radius.setEnabled(is_custom)
        self._cmb_rtype.setEnabled(self._cmb_kernel.currentIndex() != 0)
