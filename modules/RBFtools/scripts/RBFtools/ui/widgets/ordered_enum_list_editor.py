# -*- coding: utf-8 -*-
"""OrderedEnumListEditor — enum combo rows (M2.4b).

Used for ``driverInputRotateOrder[]`` (M2.1a). Each row is a
``QComboBox`` whose item index maps to the Maya-native rotateOrder
enum (xyz=0 ... zyx=5).
"""

from __future__ import absolute_import

from RBFtools.ui.compat import QtWidgets
from RBFtools.ui.widgets._ordered_list_editor_base import (
    _OrderedListEditorBase,
)


class OrderedEnumListEditor(_OrderedListEditorBase):
    """Editable ordered list of enum-index ints. The labels passed at
    construction time must match the C++ eAttr.addField order — for
    rotateOrder that means lowercase ``xyz / yzx / zxy / xzy / yxz /
    zyx`` (addendum §M2.1a.B and Maya native rotateOrder convention).

    Labels are passed via the constructor as an opaque list — they
    are NOT routed through ``tr()`` because they are technical enum
    spellings that match the underlying engine value, not translatable
    user-facing text. Adding ``tr()`` would risk translating them and
    desyncing from the C++ enum.
    """

    def __init__(self, labels, parent=None):
        self._labels = list(labels)
        super(OrderedEnumListEditor, self).__init__(parent)

    def _create_row_widget(self, initial_value):
        combo = QtWidgets.QComboBox()
        for lab in self._labels:
            combo.addItem(lab)
        try:
            idx = int(initial_value)
        except (TypeError, ValueError):
            idx = self._default_value()
        if 0 <= idx < combo.count():
            combo.setCurrentIndex(idx)
        else:
            combo.setCurrentIndex(self._default_value())
        combo.currentIndexChanged.connect(self._on_any_row_changed)
        return combo

    def _read_row_value(self, widget):
        return int(widget.currentIndex())

    def _default_value(self):
        return 0
