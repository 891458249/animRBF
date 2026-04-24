# -*- coding: utf-8 -*-
"""
PoseDelegate — custom styled-item delegate for the pose QTableView.

Responsibilities
----------------
* **Column colouring** — driver columns get a deep-blue tint,
  driven columns get a deep-green tint, making input vs. output
  immediately distinguishable at a glance.
* **Float editor** — double-click spawns a QDoubleSpinBox with
  sensible range / precision instead of a raw QLineEdit.
* **Label column** — column 0 is painted with a slight accent
  and rendered non-editable (enforced by the model's ``flags()``).

No ``maya.cmds`` — pure Qt.
"""

from __future__ import absolute_import

from RBFtools.ui.compat import QtWidgets, QtCore, QtGui
from RBFtools.ui.style import COLOR_DRIVER_BG, COLOR_DRIVEN_BG


# Pre-parse colours once at import time
_DRIVER_COLOR = QtGui.QColor(COLOR_DRIVER_BG)
_DRIVEN_COLOR = QtGui.QColor(COLOR_DRIVEN_BG)
_LABEL_COLOR  = QtGui.QColor("#3a3a3a")
_SEL_COLOR    = QtGui.QColor("#5285a6")


class PoseDelegate(QtWidgets.QStyledItemDelegate):
    """Custom delegate that tints driver / driven columns differently.

    Parameters
    ----------
    n_inputs : int
        Number of driver (input) columns.  Columns ``1 .. n_inputs``
        are tinted with the driver colour.
    parent : QObject or None
    """

    def __init__(self, n_inputs=0, parent=None):
        super(PoseDelegate, self).__init__(parent)
        self._n_inputs = n_inputs

    def set_input_count(self, n):
        """Update the driver column count (called when columns change)."""
        self._n_inputs = n

    # -----------------------------------------------------------------
    #  Paint
    # -----------------------------------------------------------------

    def paint(self, painter, option, index):
        """Override to inject column-specific background colours.

        The strategy is:
        1. Determine which colour band the column belongs to.
        2. Fill the cell rect with that colour (respecting selection).
        3. Call the base ``paint`` to render text on top.
        """
        col = index.column()

        # Determine base background colour
        if option.state & QtWidgets.QStyle.State_Selected:
            bg = _SEL_COLOR
        elif col == 0:
            bg = _LABEL_COLOR
        elif 1 <= col <= self._n_inputs:
            bg = _DRIVER_COLOR
        else:
            bg = _DRIVEN_COLOR

        # Fill background
        painter.save()
        painter.fillRect(option.rect, bg)
        painter.restore()

        # Let the base class draw text, focus rect, etc.
        super(PoseDelegate, self).paint(painter, option, index)

    # -----------------------------------------------------------------
    #  Editor — QDoubleSpinBox for numeric cells
    # -----------------------------------------------------------------

    def createEditor(self, parent, option, index):
        """Spawn a QDoubleSpinBox for data columns, nothing for col 0."""
        if index.column() == 0:
            return None                 # label column: read-only

        editor = QtWidgets.QDoubleSpinBox(parent)
        editor.setDecimals(4)
        editor.setRange(-1e6, 1e6)
        editor.setSingleStep(0.01)
        editor.setFrame(False)
        return editor

    def setEditorData(self, editor, index):
        """Populate the spinbox from the model's current value."""
        if isinstance(editor, QtWidgets.QDoubleSpinBox):
            try:
                val = float(index.data(QtCore.Qt.EditRole))
            except (ValueError, TypeError):
                val = 0.0
            editor.setValue(val)
        else:
            super(PoseDelegate, self).setEditorData(editor, index)

    def setModelData(self, editor, model, index):
        """Write the spinbox value back into the model."""
        if isinstance(editor, QtWidgets.QDoubleSpinBox):
            model.setData(index, editor.value(), QtCore.Qt.EditRole)
        else:
            super(PoseDelegate, self).setModelData(editor, model, index)
