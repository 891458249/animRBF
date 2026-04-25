# -*- coding: utf-8 -*-
"""OrderedIntListEditor — int spinbox rows (M2.4b).

Used for ``outputQuaternionGroupStart[]`` (M2.2). Each row is a
``QSpinBox`` constrained to [value_min, value_max].
"""

from __future__ import absolute_import

from RBFtools.ui.compat import QtWidgets
from RBFtools.ui.i18n import tr
from RBFtools.ui.widgets._ordered_list_editor_base import (
    _OrderedListEditorBase,
)


class OrderedIntListEditor(_OrderedListEditorBase):
    """Editable ordered list of ints. Used for outputQuaternionGroupStart."""

    def __init__(self, value_min=0, value_max=9999, parent=None):
        self._value_min = int(value_min)
        self._value_max = int(value_max)
        super(OrderedIntListEditor, self).__init__(parent)

    def _create_row_widget(self, initial_value):
        spin = QtWidgets.QSpinBox()
        spin.setRange(self._value_min, self._value_max)
        try:
            spin.setValue(int(initial_value))
        except (TypeError, ValueError):
            spin.setValue(self._default_value())
        spin.setToolTip(tr("quat_group_start_value_tip"))
        spin.valueChanged.connect(self._on_any_row_changed)
        return spin

    def _read_row_value(self, widget):
        return int(widget.value())

    def _default_value(self):
        return self._value_min
