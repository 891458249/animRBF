# -*- coding: utf-8 -*-
"""
Vector Angle section — direction, rotation, twist, translation,
interpolation and cone display sub-sections.
"""

from __future__ import absolute_import

from RBFtools.ui.compat import QtWidgets, QtCore
from RBFtools.ui.i18n import tr
from RBFtools.ui.widgets.collapsible import CollapsibleFrame
from RBFtools.ui.widgets.help_button import HelpButton, ComboHelpButton
from RBFtools.constants import (
    DIRECTION_LABELS, INTERPOLATION_LABELS,
)


class VectorAngleSection(CollapsibleFrame):
    """All Vector-Angle–mode controls in a single collapsible section."""

    attributeChanged = QtCore.Signal(str, object)

    def __init__(self, parent=None):
        super(VectorAngleSection, self).__init__(
            title=tr("vector_angle"), parent=parent)
        self._build()

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _build(self):
        lay = self.content_layout()

        # Direction
        row_dir = QtWidgets.QHBoxLayout()
        self._lbl_dir = QtWidgets.QLabel(tr("direction"))
        self._cmb_dir = QtWidgets.QComboBox()
        for d in DIRECTION_LABELS:
            self._cmb_dir.addItem(d)
        self._cmb_dir.currentIndexChanged.connect(
            lambda v: self.attributeChanged.emit("direction", v))
        row_dir.addWidget(self._lbl_dir)
        row_dir.addWidget(self._cmb_dir, 1)
        row_dir.addWidget(ComboHelpButton(
            self._cmb_dir,
            ["direction_x", "direction_y", "direction_z"],
            fallback_key="direction"))
        lay.addLayout(row_dir)

        # Invert
        row_inv = QtWidgets.QHBoxLayout()
        self._cb_invert = QtWidgets.QCheckBox(tr("invert"))
        self._cb_invert.toggled.connect(
            lambda v: self.attributeChanged.emit("invert", v))
        row_inv.addWidget(self._cb_invert)
        row_inv.addStretch()
        row_inv.addWidget(HelpButton("invert"))
        lay.addLayout(row_inv)

        lay.addWidget(self._separator())

        # -- Rotation --
        self._lbl_rotation = QtWidgets.QLabel(tr("rotation"))
        self._lbl_rotation.setStyleSheet("font-weight: bold;")
        lay.addWidget(self._lbl_rotation)

        row_ur = QtWidgets.QHBoxLayout()
        self._cb_use_rotate = QtWidgets.QCheckBox(tr("use_rotate"))
        self._cb_use_rotate.toggled.connect(
            lambda v: self.attributeChanged.emit("useRotate", v))
        row_ur.addWidget(self._cb_use_rotate)
        row_ur.addStretch()
        row_ur.addWidget(HelpButton("use_rotate"))
        lay.addLayout(row_ur)

        self._spn_angle = self._make_float_row(
            "angle", tr("angle"), 0.01, 180.0, 45.0, "angle")
        self._spn_center = self._make_float_row(
            "centerAngle", tr("center_angle"), 0.0, 180.0, 0.0, "center_angle")

        # Twist
        row_tw = QtWidgets.QHBoxLayout()
        self._cb_twist = QtWidgets.QCheckBox(tr("twist"))
        self._cb_twist.toggled.connect(
            lambda v: self.attributeChanged.emit("twist", v))
        row_tw.addWidget(self._cb_twist)
        row_tw.addStretch()
        row_tw.addWidget(HelpButton("twist"))
        lay.addLayout(row_tw)

        self._spn_twist_angle = self._make_float_row(
            "twistAngle", tr("twist_angle"), 0.01, 180.0, 90.0, "twist_angle")

        lay.addWidget(self._separator())

        # -- Translation --
        self._lbl_translation = QtWidgets.QLabel(tr("translation"))
        self._lbl_translation.setStyleSheet("font-weight: bold;")
        lay.addWidget(self._lbl_translation)

        row_ut = QtWidgets.QHBoxLayout()
        self._cb_use_translate = QtWidgets.QCheckBox(tr("use_translate"))
        self._cb_use_translate.toggled.connect(
            lambda v: self.attributeChanged.emit("useTranslate", v))
        row_ut.addWidget(self._cb_use_translate)
        row_ut.addStretch()
        row_ut.addWidget(HelpButton("use_translate"))
        lay.addLayout(row_ut)

        row_gr = QtWidgets.QHBoxLayout()
        self._cb_grow = QtWidgets.QCheckBox(tr("grow"))
        self._cb_grow.toggled.connect(
            lambda v: self.attributeChanged.emit("grow", v))
        row_gr.addWidget(self._cb_grow)
        row_gr.addStretch()
        row_gr.addWidget(HelpButton("grow"))
        lay.addLayout(row_gr)

        self._spn_trans_min = self._make_float_row(
            "translateMin", tr("translate_min"), -1e6, 1e6, 0.0, "translate_min")
        self._spn_trans_max = self._make_float_row(
            "translateMax", tr("translate_max"), -1e6, 1e6, 0.0, "translate_max")

        lay.addWidget(self._separator())

        # Interpolation
        row_interp = QtWidgets.QHBoxLayout()
        self._lbl_interp = QtWidgets.QLabel(tr("interpolation"))
        self._cmb_interp = QtWidgets.QComboBox()
        for lbl in INTERPOLATION_LABELS:
            self._cmb_interp.addItem(lbl)
        self._cmb_interp.currentIndexChanged.connect(
            lambda v: self.attributeChanged.emit("interpolation", v))
        row_interp.addWidget(self._lbl_interp)
        row_interp.addWidget(self._cmb_interp, 1)
        row_interp.addWidget(ComboHelpButton(
            self._cmb_interp, [
                "interp_linear", "interp_slow", "interp_fast",
                "interp_smooth1", "interp_smooth2", "interp_curve",
            ], fallback_key="interpolation"))
        lay.addLayout(row_interp)

        lay.addWidget(self._separator())

        # -- Cone Display --
        self._cone_frame = CollapsibleFrame(tr("cone_display"), collapsed=True)
        cone = self._cone_frame.content_layout()

        row_dc = QtWidgets.QHBoxLayout()
        self._cb_draw_cone = QtWidgets.QCheckBox(tr("draw_cone"))
        self._cb_draw_cone.toggled.connect(
            lambda v: self.attributeChanged.emit("drawCone", v))
        row_dc.addWidget(self._cb_draw_cone)
        row_dc.addStretch()
        row_dc.addWidget(HelpButton("draw_cone"))
        cone.addLayout(row_dc)

        row_dcc = QtWidgets.QHBoxLayout()
        self._cb_draw_center = QtWidgets.QCheckBox(tr("draw_center_cone"))
        self._cb_draw_center.toggled.connect(
            lambda v: self.attributeChanged.emit("drawCenterCone", v))
        row_dcc.addWidget(self._cb_draw_center)
        row_dcc.addStretch()
        row_dcc.addWidget(HelpButton("draw_center_cone"))
        cone.addLayout(row_dcc)

        row_dw = QtWidgets.QHBoxLayout()
        self._cb_draw_weight = QtWidgets.QCheckBox(tr("draw_weight"))
        self._cb_draw_weight.toggled.connect(
            lambda v: self.attributeChanged.emit("drawWeight", v))
        row_dw.addWidget(self._cb_draw_weight)
        row_dw.addStretch()
        row_dw.addWidget(HelpButton("draw_weight"))
        cone.addLayout(row_dw)

        lay.addWidget(self._cone_frame)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _make_float_row(self, attr, label, mn, mx, default, help_key=None):
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
        self.content_layout().addLayout(row)
        # store label ref for retranslate
        spn.setProperty("_lbl", lbl)
        spn.setProperty("_tr_key", label)
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
        """Populate controls from a settings dict."""
        if data is None:
            return
        idx = min(data.get("direction", 0), len(DIRECTION_LABELS) - 1)
        self._cmb_dir.setCurrentIndex(idx)
        self._cb_invert.setChecked(data.get("invert", False))
        self._cb_use_rotate.setChecked(data.get("useRotate", True))
        self._spn_angle.setValue(data.get("angle", 45.0))
        self._spn_center.setValue(data.get("centerAngle", 0.0))
        self._cb_twist.setChecked(data.get("twist", False))
        self._spn_twist_angle.setValue(data.get("twistAngle", 90.0))
        self._cb_use_translate.setChecked(data.get("useTranslate", False))
        self._cb_grow.setChecked(data.get("grow", False))
        self._spn_trans_min.setValue(data.get("translateMin", 0.0))
        self._spn_trans_max.setValue(data.get("translateMax", 0.0))
        self._cmb_interp.setCurrentIndex(data.get("interpolation", 0))
        self._cb_draw_cone.setChecked(data.get("drawCone", True))
        self._cb_draw_center.setChecked(data.get("drawCenterCone", False))
        self._cb_draw_weight.setChecked(data.get("drawWeight", False))

    def retranslate(self):
        self.set_title(tr("vector_angle"))
        self._lbl_dir.setText(tr("direction"))
        self._cb_invert.setText(tr("invert"))
        self._lbl_rotation.setText(tr("rotation"))
        self._cb_use_rotate.setText(tr("use_rotate"))
        self._cb_twist.setText(tr("twist"))
        self._lbl_translation.setText(tr("translation"))
        self._cb_use_translate.setText(tr("use_translate"))
        self._cb_grow.setText(tr("grow"))
        self._lbl_interp.setText(tr("interpolation"))
        self._cone_frame.set_title(tr("cone_display"))
        self._cb_draw_cone.setText(tr("draw_cone"))
        self._cb_draw_center.setText(tr("draw_center_cone"))
        self._cb_draw_weight.setText(tr("draw_weight"))
