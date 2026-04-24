# -*- coding: utf-8 -*-
"""
General section — Active checkbox, Type dropdown, Icon Size slider.
"""

from __future__ import absolute_import

from RBFtools.ui.compat import QtWidgets, QtCore
from RBFtools.ui.i18n import tr
from RBFtools.ui.widgets.collapsible import CollapsibleFrame
from RBFtools.ui.widgets.help_button import HelpButton, ComboHelpButton
from RBFtools.constants import TYPE_LABELS


class GeneralSection(CollapsibleFrame):
    """General settings: active, type, iconSize."""

    # (attr_name, value)
    attributeChanged = QtCore.Signal(str, object)
    typeChanged = QtCore.Signal(int)

    def __init__(self, parent=None):
        super(GeneralSection, self).__init__(title=tr("general"), parent=parent)
        self._build()

    def _build(self):
        lay = self.content_layout()

        # Active
        row_active = QtWidgets.QHBoxLayout()
        self._cb_active = QtWidgets.QCheckBox(tr("active"))
        self._cb_active.setChecked(True)
        self._cb_active.toggled.connect(
            lambda v: self.attributeChanged.emit("active", v))
        row_active.addWidget(self._cb_active)
        row_active.addStretch()
        row_active.addWidget(HelpButton("active"))
        lay.addLayout(row_active)

        # Type
        row_type = QtWidgets.QHBoxLayout()
        self._lbl_type = QtWidgets.QLabel(tr("type"))
        self._cmb_type = QtWidgets.QComboBox()
        for t in TYPE_LABELS:
            self._cmb_type.addItem(t)
        self._cmb_type.currentIndexChanged.connect(self._on_type)
        row_type.addWidget(self._lbl_type)
        row_type.addWidget(self._cmb_type, 1)
        row_type.addWidget(ComboHelpButton(
            self._cmb_type, ["type_vector_angle", "type_rbf"],
            fallback_key="type"))
        lay.addLayout(row_type)

        # Icon Size (wrapped in a widget for visibility toggle)
        self._icon_row = QtWidgets.QWidget()
        row_icon = QtWidgets.QHBoxLayout(self._icon_row)
        row_icon.setContentsMargins(0, 0, 0, 0)
        self._lbl_icon = QtWidgets.QLabel(tr("icon_size"))
        self._sld_icon = QtWidgets.QDoubleSpinBox()
        self._sld_icon.setRange(0.01, 10.0)
        self._sld_icon.setSingleStep(0.1)
        self._sld_icon.setValue(1.0)
        self._sld_icon.valueChanged.connect(
            lambda v: self.attributeChanged.emit("iconSize", v))
        row_icon.addWidget(self._lbl_icon)
        row_icon.addWidget(self._sld_icon, 1)
        row_icon.addWidget(HelpButton("icon_size"))
        lay.addWidget(self._icon_row)

    # -- Public --

    def load(self, data):
        """Load from a settings dict (from ``core.get_all_settings``)."""
        if data is None:
            return
        self._cb_active.setChecked(data.get("active", True))
        self._cmb_type.setCurrentIndex(data.get("type", 0))
        self._sld_icon.setValue(data.get("iconSize", 1.0))

    def set_icon_size_visible(self, visible):
        """Show or hide the Icon Size row."""
        self._icon_row.setVisible(visible)

    def current_type(self):
        return self._cmb_type.currentIndex()

    def retranslate(self):
        self.set_title(tr("general"))
        self._cb_active.setText(tr("active"))
        self._lbl_type.setText(tr("type"))
        self._lbl_icon.setText(tr("icon_size"))

    # -- Private --

    def _on_type(self, idx):
        self.attributeChanged.emit("type", idx)
        self.typeChanged.emit(idx)
