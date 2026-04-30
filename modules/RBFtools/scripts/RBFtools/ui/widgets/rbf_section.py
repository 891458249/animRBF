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
    SOLVER_METHOD_LABELS, INPUT_ENCODING_LABELS,   # M2.4a
    DRIVER_INPUT_ROTATE_ORDER_LABELS,              # M2.4b
)
from RBFtools.ui.widgets.ordered_int_list_editor import (
    OrderedIntListEditor,
)
# M_ROTORDER_UI_REFACTOR (2026-04-29): rotate-order editor swapped
# from the legacy add/remove/reorder OrderedEnumListEditor to the
# driver-tab-synced DriverRotateOrderEditor. The legacy class is
# kept (not imported here) for OrderedIntListEditor's quat-group
# editor which still needs the 4-button shared base behaviour.
from RBFtools.ui.widgets.driver_rotate_order_editor import (
    DriverRotateOrderEditor,
)


class RBFSection(CollapsibleFrame):
    """All RBF-mode controls in a single collapsible section."""

    attributeChanged = QtCore.Signal(str, object)
    kernelChanged = QtCore.Signal(int)
    radiusTypeChanged = QtCore.Signal(int)
    radiusEdited = QtCore.Signal(float)
    # M_ENC_AUTOPIPE: emitted alongside attributeChanged("inputEncoding")
    # so the controller can run the rotateOrder auto-derive side-effect
    # without overloading the generic set_attribute dispatch.
    inputEncodingChanged = QtCore.Signal(int)

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

        # M2.4a: M1.4 regularization (Tikhonov λ).
        row_reg = QtWidgets.QHBoxLayout()
        self._lbl_reg = QtWidgets.QLabel(tr("regularization"))
        self._spn_reg = QtWidgets.QDoubleSpinBox()
        self._spn_reg.setRange(0.0, 1.0)
        self._spn_reg.setDecimals(10)
        self._spn_reg.setSingleStep(1.0e-9)
        self._spn_reg.setValue(1.0e-8)
        self._spn_reg.valueChanged.connect(
            lambda v: self.attributeChanged.emit("regularization", v))
        row_reg.addWidget(self._lbl_reg)
        row_reg.addWidget(self._spn_reg, 1)
        row_reg.addWidget(HelpButton("regularization"))
        lay.addLayout(row_reg)

        # M2.4a: M1.4 solverMethod {Auto, ForceGE}.
        row_slv = QtWidgets.QHBoxLayout()
        self._lbl_slvm = QtWidgets.QLabel(tr("solver_method"))
        self._cmb_slvm = QtWidgets.QComboBox()
        for m in SOLVER_METHOD_LABELS:
            self._cmb_slvm.addItem(m)
        self._cmb_slvm.currentIndexChanged.connect(
            lambda v: self.attributeChanged.emit("solverMethod", v))
        row_slv.addWidget(self._lbl_slvm)
        row_slv.addWidget(self._cmb_slvm, 1)
        row_slv.addWidget(ComboHelpButton(
            self._cmb_slvm, [
                "solver_auto", "solver_force_ge",
            ], fallback_key="solver_method"))
        lay.addLayout(row_slv)

        # M2.4a: M1.3 clampEnabled + clampInflation. Inflation is
        # disabled when clamp is off (visual cue that it has no effect).
        row_cle = QtWidgets.QHBoxLayout()
        self._cb_clamp = QtWidgets.QCheckBox(tr("clamp_enabled"))
        self._cb_clamp.toggled.connect(self._on_clamp_toggled)
        row_cle.addWidget(self._cb_clamp)
        row_cle.addStretch()
        row_cle.addWidget(HelpButton("clamp_enabled"))
        lay.addLayout(row_cle)

        row_cli = QtWidgets.QHBoxLayout()
        self._lbl_clinf = QtWidgets.QLabel(tr("clamp_inflation"))
        self._spn_clamp_inflation = QtWidgets.QDoubleSpinBox()
        self._spn_clamp_inflation.setRange(0.0, 1.0)
        self._spn_clamp_inflation.setDecimals(4)
        self._spn_clamp_inflation.setSingleStep(0.01)
        self._spn_clamp_inflation.setValue(0.0)
        self._spn_clamp_inflation.setEnabled(False)
        self._spn_clamp_inflation.valueChanged.connect(
            lambda v: self.attributeChanged.emit("clampInflation", v))
        row_cli.addWidget(self._lbl_clinf)
        row_cli.addWidget(self._spn_clamp_inflation, 1)
        row_cli.addWidget(HelpButton("clamp_inflation"))
        lay.addLayout(row_cli)

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

        # M2.4b: outputQuaternionGroupStart[] editor. Sits at top-level
        # (not in Generic subsection) because QWA is an output-side
        # concept that applies to both Generic and Matrix modes — though
        # M2.2 only acts in Generic, the schema is shared. Always
        # visible (no encoding-driven gating).
        self._quat_group_editor = OrderedIntListEditor(
            value_min=0, value_max=9999)
        self._quat_group_editor.set_label(tr("quat_group_start_label"))
        self._quat_group_editor.set_empty_hint(tr("quat_group_empty_hint"))
        self._quat_group_editor.listChanged.connect(
            lambda lst: self.attributeChanged.emit(
                "outputQuaternionGroupStart", lst))
        lay.addWidget(self._quat_group_editor)

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

        # M2.4a: Input Encoding (M2.1a / M2.1b). Visibility hook for
        # M2.4b's per-driver-group rotateOrder editor uses hasattr()
        # so this stays safe pre-M2.4b.
        row_ienc = QtWidgets.QHBoxLayout()
        self._lbl_ienc = QtWidgets.QLabel(tr("input_encoding"))
        self._cmb_ienc = QtWidgets.QComboBox()
        for e in INPUT_ENCODING_LABELS:
            self._cmb_ienc.addItem(e)
        self._cmb_ienc.currentIndexChanged.connect(self._on_input_encoding)
        row_ienc.addWidget(self._lbl_ienc)
        row_ienc.addWidget(self._cmb_ienc, 1)
        row_ienc.addWidget(ComboHelpButton(
            self._cmb_ienc, [
                "enc_raw", "enc_quaternion", "enc_bendroll",
                "enc_expmap", "enc_swingtwist",
            ], fallback_key="input_encoding"))
        glay.addLayout(row_ienc)

        # M2.4b: per-driver-group rotateOrder editor. Lives in the
        # Generic subsection because rotateOrder is irrelevant to
        # Matrix mode. Visibility is gated by inputEncoding via
        # `_update_encoding_visibility`; default Raw → hidden.
        # M_ROTORDER_UI_REFACTOR (2026-04-29): editor type swapped
        # from OrderedEnumListEditor to DriverRotateOrderEditor —
        # rows are now a strict projection of the driver-source
        # tabs (one row per driver, label "Driver N (joint_name)";
        # the user can only edit the per-row enum combo, not
        # add / remove / reorder rows). Driver tabs are the single
        # source of truth; main_window's _reload_driver_sources
        # pushes the live driver name list via
        # set_driver_sources_for_rotate_order on every tab change.
        # DRIVER_INPUT_ROTATE_ORDER_LABELS no longer flows through
        # the constructor — the new widget reads it directly from
        # constants.py.
        self._rotate_order_editor = DriverRotateOrderEditor()
        self._rotate_order_editor.set_label(tr("driver_rotate_order_label"))
        self._rotate_order_editor.set_empty_hint(tr("rotate_order_empty_hint"))
        self._rotate_order_editor.listChanged.connect(
            lambda lst: self.attributeChanged.emit(
                "driverInputRotateOrder", lst))
        self._rotate_order_editor.setVisible(False)
        glay.addWidget(self._rotate_order_editor)

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
        # M2.4a: load M1.3 / M1.4 / M2.1a values with safe defaults
        # so v4 / v5-pre-M2.4 rigs show the C++ default exactly.
        self._spn_reg.setValue(data.get("regularization", 1.0e-8))
        self._cmb_slvm.setCurrentIndex(data.get("solverMethod", 0))
        clamp_on = data.get("clampEnabled", False)
        self._cb_clamp.setChecked(clamp_on)
        self._spn_clamp_inflation.setValue(data.get("clampInflation", 0.0))
        self._spn_clamp_inflation.setEnabled(clamp_on)
        ienc = data.get("inputEncoding", 0)
        self._cmb_ienc.setCurrentIndex(ienc)
        # M2.4b: rotateOrder + quat-group multi editors. set_values()
        # is signal-suspended internally — never round-trips back into
        # the controller (addendum §M2.4b refinement / contract).
        if hasattr(self, "_rotate_order_editor"):
            self._rotate_order_editor.set_values(
                data.get("driverInputRotateOrder", []))
        if hasattr(self, "_quat_group_editor"):
            self._quat_group_editor.set_values(
                data.get("outputQuaternionGroupStart", []))
        # Sync visibility AFTER set_values so the v5 rig opening with
        # encoding=2 sees the populated editor visible immediately
        # (addendum §M2.4b Q2).
        self._update_encoding_visibility(ienc)
        self._update_radius_state()
        self._update_mode_visibility(self._cmb_mode.currentIndex())

    def set_driver_sources_for_rotate_order(self, names):
        """M_ROTORDER_UI_REFACTOR (2026-04-29): public entry-point
        called from main_window's ``_reload_driver_sources`` slot
        whenever the driver-source tab list changes (add / remove /
        node load). The widget rebuilds its rows from *names*
        (length owned by the driver tabs); previously-set rotate-
        order values are preserved by row index when the new length
        permits.

        ``hasattr`` guard preserves the M2.4b §D① contract."""
        if hasattr(self, "_rotate_order_editor"):
            self._rotate_order_editor.set_driver_sources(
                list(names or []))

    def set_rotate_order_values(self, values):
        """M_P1_ENC_COMBO_FIX (2026-04-29): narrow public entry-point
        for the rotate-order editor; called from main_window in
        response to the controller's ``rotateOrderEditorReload``
        signal (the post-encoding-switch auto-derive path) so the
        editor refreshes from live driverInputRotateOrder[] without
        round-tripping through settingsLoaded -> load() — that wider
        path triggered the inputEncoding combo bounce-back regression.

        ``hasattr`` guard preserves the M2.4b §D① contract
        (defends against future _build reordering)."""
        if hasattr(self, "_rotate_order_editor"):
            self._rotate_order_editor.set_values(list(values or []))

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
        # M2.4a additions
        self._lbl_reg.setText(tr("regularization"))
        self._lbl_slvm.setText(tr("solver_method"))
        self._cb_clamp.setText(tr("clamp_enabled"))
        self._lbl_clinf.setText(tr("clamp_inflation"))
        self._lbl_ienc.setText(tr("input_encoding"))
        # M2.4b: multi list editors — push label / hint / button text
        # through the editor's own retranslate plus the per-instance
        # set_label / set_empty_hint helpers (the editor's retranslate
        # only re-translates the +/-/up/down button strings).
        if hasattr(self, "_rotate_order_editor"):
            self._rotate_order_editor.set_label(tr("driver_rotate_order_label"))
            self._rotate_order_editor.set_empty_hint(
                tr("rotate_order_empty_hint"))
            self._rotate_order_editor.retranslate()
        if hasattr(self, "_quat_group_editor"):
            self._quat_group_editor.set_label(tr("quat_group_start_label"))
            self._quat_group_editor.set_empty_hint(tr("quat_group_empty_hint"))
            self._quat_group_editor.retranslate()

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _on_rbf_mode(self, idx):
        self.attributeChanged.emit("rbfMode", idx)
        self._update_mode_visibility(idx)

    def _on_input_encoding(self, idx):
        """Emit attr + side-effect signal + sync visibility.

        Two signals fire on user-initiated combo change:
          1. ``attributeChanged("inputEncoding", idx)`` -> generic
             set_attribute dispatch writes the schema field.
          2. ``inputEncodingChanged(idx)`` (M_ENC_AUTOPIPE) -> the
             controller runs the rotateOrder auto-derive side-effect
             so Generic-mode TDs get "select-encoding -> works"
             without manually filling the rotate-order editor.

        :func:`_update_encoding_visibility` is also called from
        load() so a v5 rig opening with encoding != Raw shows the
        rotateOrder editor immediately.
        """
        self.attributeChanged.emit("inputEncoding", idx)
        self.inputEncodingChanged.emit(int(idx))
        self._update_encoding_visibility(idx)

    def _update_encoding_visibility(self, idx):
        """Single source of truth for the rotateOrder editor visibility.

        ``hasattr`` guard preserved per addendum §M2.4b (D)①: defends
        against future ``_build`` reordering that might construct the
        editor after a callback fires.

        M_ENC_AUTOPIPE: the editor is hidden for both Raw (0) and
        Quaternion (1) since neither encoding consumes
        ``driverInputRotateOrder[]`` in C++ applyEncodingToBlock
        (cpp:2606-2624). BendRoll (2) / ExpMap (3) / SwingTwist (4)
        show the editor.
        """
        if hasattr(self, "_rotate_order_editor"):
            needs_rotate_order = int(idx) in (2, 3, 4)
            self._rotate_order_editor.setVisible(needs_rotate_order)

    def _on_clamp_toggled(self, checked):
        self.attributeChanged.emit("clampEnabled", checked)
        # Visual cue: inflation has no effect when clamp is off.
        self._spn_clamp_inflation.setEnabled(checked)

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
