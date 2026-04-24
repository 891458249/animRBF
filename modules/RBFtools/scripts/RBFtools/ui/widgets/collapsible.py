# -*- coding: utf-8 -*-
"""
Collapsible frame widget — replaces Maya's ``frameLayout`` in Qt.
"""

from __future__ import absolute_import

from RBFtools.ui.compat import QtWidgets, QtCore


class CollapsibleFrame(QtWidgets.QWidget):
    """A titled frame that can expand / collapse its content area."""

    def __init__(self, title="", collapsed=False, parent=None):
        super(CollapsibleFrame, self).__init__(parent)

        self._toggle = QtWidgets.QToolButton()
        self._toggle.setStyleSheet("QToolButton { border: none; font-weight: bold; }")
        self._toggle.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        self._toggle.setArrowType(
            QtCore.Qt.RightArrow if collapsed else QtCore.Qt.DownArrow)
        self._toggle.setText(title)
        self._toggle.setCheckable(True)
        self._toggle.setChecked(not collapsed)
        self._toggle.toggled.connect(self._on_toggled)

        self._content = QtWidgets.QWidget()
        self._content_layout = QtWidgets.QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(10, 4, 4, 4)
        self._content_layout.setSpacing(4)
        self._content.setVisible(not collapsed)

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self._toggle)
        lay.addWidget(self._content)

    # -- public API --

    def content_layout(self):
        """Return the layout inside the collapsible area."""
        return self._content_layout

    def add_widget(self, widget):
        self._content_layout.addWidget(widget)

    def add_layout(self, layout):
        self._content_layout.addLayout(layout)

    def set_title(self, title):
        self._toggle.setText(title)

    def set_visible_content(self, visible):
        self._toggle.setChecked(visible)

    # -- private --

    def _on_toggled(self, checked):
        self._toggle.setArrowType(
            QtCore.Qt.DownArrow if checked else QtCore.Qt.RightArrow)
        self._content.setVisible(checked)
