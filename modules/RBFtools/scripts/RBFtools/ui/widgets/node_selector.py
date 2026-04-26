# -*- coding: utf-8 -*-
"""
Node selector bar — QComboBox + action buttons + settings gear.

Signals only — no ``maya.cmds`` calls.
"""

from __future__ import absolute_import

from RBFtools.ui.compat import QtWidgets, QtCore, QtGui
from RBFtools.ui.i18n import tr


class NodeSelector(QtWidgets.QWidget):
    """Top toolbar: node dropdown, Refresh / Pick Sel / New / Delete, gear."""

    # Signals
    nodeChanged = QtCore.Signal(str)
    refreshRequested = QtCore.Signal()
    pickSelRequested = QtCore.Signal()
    newRequested = QtCore.Signal()
    deleteRequested = QtCore.Signal()
    languageChangeRequested = QtCore.Signal(str)

    NONE_ITEM = "< None >"

    def __init__(self, parent=None):
        super(NodeSelector, self).__init__(parent)
        self._build_ui()

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _build_ui(self):
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(4, 2, 4, 2)
        lay.setSpacing(4)

        self._label = QtWidgets.QLabel(tr("node"))
        lay.addWidget(self._label)

        self._combo = QtWidgets.QComboBox()
        self._combo.setToolTip(tr("node_selector_combo_tip"))
        self._combo.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        self._combo.addItem(self.NONE_ITEM)
        self._combo.currentTextChanged.connect(self._on_combo_changed)
        lay.addWidget(self._combo)

        self._btn_refresh = QtWidgets.QPushButton(tr("refresh"))
        self._btn_refresh.setToolTip(tr("node_selector_refresh_tip"))
        self._btn_pick = QtWidgets.QPushButton(tr("pick_sel"))
        self._btn_pick.setToolTip(tr("node_selector_pick_tip"))
        self._btn_new = QtWidgets.QPushButton(tr("new"))
        self._btn_new.setToolTip(tr("node_selector_new_tip"))
        self._btn_delete = QtWidgets.QPushButton(tr("delete"))
        self._btn_delete.setToolTip(tr("node_selector_delete_tip"))

        for btn in (self._btn_refresh, self._btn_pick,
                    self._btn_new, self._btn_delete):
            btn.setFixedHeight(24)
            lay.addWidget(btn)

        self._btn_refresh.clicked.connect(self.refreshRequested)
        self._btn_pick.clicked.connect(self.pickSelRequested)
        self._btn_new.clicked.connect(self.newRequested)
        self._btn_delete.clicked.connect(self.deleteRequested)

        # Gear button with language popup
        self._gear = QtWidgets.QToolButton()
        self._gear.setIcon(QtGui.QIcon(":/gear.png"))
        self._gear.setFixedSize(24, 24)
        self._gear.setPopupMode(QtWidgets.QToolButton.InstantPopup)

        self._gear_menu = QtWidgets.QMenu(self._gear)
        self._lang_menu = self._gear_menu.addMenu(tr("language"))
        self._ag = QtWidgets.QActionGroup(self._lang_menu)
        self._act_en = QtWidgets.QAction(tr("english"), self._ag)
        self._act_en.setCheckable(True)
        self._ag.addAction(self._act_en)
        self._lang_menu.addAction(self._act_en)
        self._act_zh = QtWidgets.QAction(tr("chinese"), self._ag)
        self._act_zh.setCheckable(True)
        self._ag.addAction(self._act_zh)
        self._lang_menu.addAction(self._act_zh)

        self._act_en.triggered.connect(lambda: self.languageChangeRequested.emit("en"))
        self._act_zh.triggered.connect(lambda: self.languageChangeRequested.emit("zh"))

        self._gear.setMenu(self._gear_menu)
        lay.addWidget(self._gear)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_nodes(self, names):
        """Replace the entire dropdown list."""
        blocked = self._combo.blockSignals(True)
        self._combo.clear()
        self._combo.addItem(self.NONE_ITEM)
        for n in names:
            self._combo.addItem(n)
        self._combo.blockSignals(blocked)

    def set_current_node(self, name):
        idx = self._combo.findText(name)
        if idx >= 0:
            self._combo.setCurrentIndex(idx)

    def current_node(self):
        text = self._combo.currentText()
        return "" if text == self.NONE_ITEM else text

    def set_language_checked(self, lang):
        try:
            self._act_en.setChecked(lang == "en")
            self._act_zh.setChecked(lang == "zh")
        except RuntimeError:
            pass  # C++ object already deleted (window closing)

    def retranslate(self):
        self._label.setText(tr("node"))
        self._btn_refresh.setText(tr("refresh"))
        self._btn_pick.setText(tr("pick_sel"))
        self._btn_new.setText(tr("new"))
        self._btn_delete.setText(tr("delete"))
        # Rebuild gear menu
        gear_menu = self._gear.menu()
        if gear_menu:
            gear_menu.clear()
            self._lang_menu = gear_menu.addMenu(tr("language"))
            self._ag = QtWidgets.QActionGroup(self._lang_menu)
            self._act_en = QtWidgets.QAction(tr("english"), self._ag)
            self._act_en.setCheckable(True)
            self._ag.addAction(self._act_en)
            self._lang_menu.addAction(self._act_en)
            self._act_zh = QtWidgets.QAction(tr("chinese"), self._ag)
            self._act_zh.setCheckable(True)
            self._ag.addAction(self._act_zh)
            self._lang_menu.addAction(self._act_zh)
            self._act_en.triggered.connect(lambda: self.languageChangeRequested.emit("en"))
            self._act_zh.triggered.connect(lambda: self.languageChangeRequested.emit("zh"))

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _on_combo_changed(self, text):
        node = "" if text == self.NONE_ITEM else text
        self.nodeChanged.emit(node)
