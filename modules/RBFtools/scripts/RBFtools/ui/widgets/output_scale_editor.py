# -*- coding: utf-8 -*-
"""
OutputScaleEditor — per-output ``isScale`` flag editor (M2.4a).

A small QListWidget where each row corresponds to one driven attribute
and carries a checkbox marking it as a scale channel (M1.2 anchor 1.0
contract). Lives on the driven side of pose_editor; the parent connects
``isScaleChanged`` to controller.set_attribute("outputIsScale", ...).

Signals only — never imports ``RBFtools.core`` (MVC red line).
"""

from __future__ import absolute_import

from RBFtools.ui.compat import QtWidgets, QtCore
from RBFtools.ui.i18n import tr
from RBFtools.ui.widgets.help_button import HelpButton


class OutputScaleEditor(QtWidgets.QWidget):
    """Per-driven-attribute checkbox list for the M1.2 outputIsScale flag.

    Signals
    -------
    isScaleChanged : Signal(list)
        Emitted with the full bool list whenever any row toggles. The
        receiver writes it via ``set_attribute("outputIsScale", lst)``
        which dispatches to ``core.set_node_multi_attr`` (transactional
        clear-then-write per addendum §M2.4a refinement 2).
    """

    isScaleChanged = QtCore.Signal(list)

    def __init__(self, parent=None):
        super(OutputScaleEditor, self).__init__(parent)
        self._build()

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _build(self):
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)

        hdr_row = QtWidgets.QHBoxLayout()
        self._lbl_hdr = QtWidgets.QLabel(tr("output_is_scale_hdr"))
        self._lbl_hdr.setStyleSheet("font-weight: bold;")
        hdr_row.addWidget(self._lbl_hdr, 1)
        hdr_row.addWidget(HelpButton("output_is_scale"))
        lay.addLayout(hdr_row)

        self._list = QtWidgets.QListWidget()
        self._list.setSelectionMode(
            QtWidgets.QAbstractItemView.NoSelection)
        lay.addWidget(self._list, 1)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_attributes(self, names, current_flags=None):
        """Populate rows from a list of driven attr names.

        Parameters
        ----------
        names : list[str]
            Driven attribute names in output[] order.
        current_flags : list[bool] or None
            Pre-existing isScale flags to seed the checkboxes. Length
            shorter than `names` defaults the missing tail to False.
        """
        if current_flags is None:
            current_flags = []
        self._list.clear()
        for i, name in enumerate(names):
            item = QtWidgets.QListWidgetItem(self._list)
            item.setData(QtCore.Qt.UserRole, i)
            cb = QtWidgets.QCheckBox(name)
            checked = (i < len(current_flags) and bool(current_flags[i]))
            cb.setChecked(checked)
            cb.toggled.connect(self._on_toggle)
            self._list.addItem(item)
            self._list.setItemWidget(item, cb)

    def get_is_scale_array(self):
        """Return the full bool list in output[] order."""
        out = []
        for i in range(self._list.count()):
            cb = self._list.itemWidget(self._list.item(i))
            if cb is None:
                out.append(False)
            else:
                out.append(bool(cb.isChecked()))
        return out

    def clear(self):
        self._list.clear()

    def retranslate(self):
        self._lbl_hdr.setText(tr("output_is_scale_hdr"))

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _on_toggle(self, _checked):
        # Re-emit the full list so the receiver doesn't have to track
        # individual indices — keeps controller.set_attribute simple.
        self.isScaleChanged.emit(self.get_is_scale_array())
