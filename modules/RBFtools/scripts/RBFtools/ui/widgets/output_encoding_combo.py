# -*- coding: utf-8 -*-
"""OutputEncodingCombo — node-level outputEncoding enum widget (M_B24b1).

Thin wrapper around QComboBox exposing the three M_B24a1 outputEncoding
enum values: 0=Euler (default), 1=Quaternion, 2=ExpMap. Lives at the
inspector folding panel per (B.3) decision; not embedded in the
per-driver row (driverSource_encoding is a separate per-source enum).
"""

from __future__ import absolute_import

from RBFtools.ui.compat import QtCore, QtWidgets
from RBFtools.ui.i18n import tr


_OUTPUT_ENCODING_LABELS = [
    ("output_encoding_euler",      0),
    ("output_encoding_quaternion", 1),
    ("output_encoding_expmap",     2),
]


class OutputEncodingCombo(QtWidgets.QComboBox):
    """Node-level outputEncoding enum combo. Emits :attr:`encodingChanged`
    with the new int value when the user picks a different option."""

    encodingChanged = QtCore.Signal(int)

    def __init__(self, parent=None):
        super(OutputEncodingCombo, self).__init__(parent)
        for tr_key, value in _OUTPUT_ENCODING_LABELS:
            self.addItem(tr(tr_key), value)
        self.setToolTip(tr("output_encoding_combo_tip"))
        self.currentIndexChanged.connect(self._on_changed)

    def _on_changed(self, _idx):
        self.encodingChanged.emit(int(self.currentData()))

    def encoding(self):
        """Return the current enum value (0..2)."""
        return int(self.currentData())

    def set_encoding(self, value):
        """Programmatically set the current enum. Does NOT emit
        encodingChanged (the controller is the originator)."""
        self.blockSignals(True)
        try:
            for i in range(self.count()):
                if int(self.itemData(i)) == int(value):
                    self.setCurrentIndex(i)
                    break
        finally:
            self.blockSignals(False)

    def retranslate(self):
        """M_QUICKWINS Item 2: refresh combo item labels +
        tooltip on language switch."""
        current_value = self.encoding()
        self.blockSignals(True)
        try:
            for i, (tr_key, _value) in enumerate(_OUTPUT_ENCODING_LABELS):
                self.setItemText(i, tr(tr_key))
            self.setToolTip(tr("output_encoding_combo_tip"))
        finally:
            self.blockSignals(False)
        self.set_encoding(current_value)
