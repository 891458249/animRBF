# -*- coding: utf-8 -*-
"""DrivenSourceListEditor — multi-driven list editor (M_DRIVEN_MULTI Item 4c).

Sibling of :class:`DriverSourceListEditor` for the driven side. Each row
pairs a driven node label with an attrs preview + an Attrs... picker
button. Driven sources have neither a per-source weight nor an encoding
(those concepts are driver-only) so the row is simpler than the driver
counterpart.

Wiring is parallel to M_UIRECONCILE / M_UIRECONCILE_PLUS:

  + button click -> ``addRequested`` (payload-less; main_window owns
    the cmds.ls call, MVC red line)
  - button click -> ``removeRequested(int)`` with the row index
  Attrs... -> ``attrsRequested(int, str, tuple)`` payload (idx, node,
    current_attrs)

The editor never imports cmds; main_window.py owns the cmds.* calls
and forwards to controller.add_driven_source /
controller.remove_driven_source / controller.set_driven_source_attrs.
"""

from __future__ import absolute_import

from RBFtools.ui.compat import QtCore, QtWidgets
from RBFtools.ui.i18n import tr
from RBFtools.ui.widgets._ordered_list_editor_base import (
    _OrderedListEditorBase,
)

from RBFtools.core import DrivenSource


class _DrivenSourceRow(QtWidgets.QWidget):
    """Composite row widget for a single driven source. Read-only node
    + attrs labels + an Attrs... button that emits ``attrsRequested``
    so the parent's slot can open the attribute picker dialog."""

    rowChanged     = QtCore.Signal()
    attrsRequested = QtCore.Signal(str, tuple)   # (node, current_attrs)

    def __init__(self, source, parent=None):
        super(_DrivenSourceRow, self).__init__(parent)
        self._source = source if isinstance(source, DrivenSource) else \
            DrivenSource(node="", attrs=tuple())
        self._build()

    def _build(self):
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(2, 2, 2, 2)
        lay.setSpacing(4)

        self._lbl_node = QtWidgets.QLabel(self._source.node or "<unset>")
        self._lbl_node.setMinimumWidth(120)
        self._lbl_node.setToolTip(tr("driven_source_node_tip"))
        lay.addWidget(self._lbl_node, 1)

        attrs_text = ", ".join(self._source.attrs) \
            if self._source.attrs else ""
        self._lbl_attrs = QtWidgets.QLabel(attrs_text)
        self._lbl_attrs.setMinimumWidth(160)
        self._lbl_attrs.setToolTip(tr("driven_source_attrs_tip"))
        lay.addWidget(self._lbl_attrs, 2)

        self._btn_attrs = QtWidgets.QPushButton(
            tr("driven_source_attrs_btn"))
        self._btn_attrs.setToolTip(tr("driven_source_attrs_btn_tip"))
        self._btn_attrs.setMaximumWidth(70)
        self._btn_attrs.clicked.connect(self._on_attrs_clicked)
        lay.addWidget(self._btn_attrs)

    def _on_attrs_clicked(self):
        self.attrsRequested.emit(
            self._source.node or "", tuple(self._source.attrs))

    def value(self):
        """Return the current widget state as a DrivenSource."""
        return DrivenSource(
            node=self._source.node, attrs=self._source.attrs)

    def retranslate(self):
        """M_QUICKWINS Item 2 sibling: row-level i18n refresh."""
        self._lbl_node.setToolTip(tr("driven_source_node_tip"))
        self._lbl_attrs.setToolTip(tr("driven_source_attrs_tip"))
        self._btn_attrs.setText(tr("driven_source_attrs_btn"))
        self._btn_attrs.setToolTip(tr("driven_source_attrs_btn_tip"))


class DrivenSourceListEditor(_OrderedListEditorBase):
    """Editable ordered list of :class:`DrivenSource` entries.

    M_DRIVEN_MULTI primary deliverable. Mirrors
    :class:`DriverSourceListEditor` but without weight / encoding
    columns and using DrivenSource dataclasses."""

    addRequested    = QtCore.Signal()
    removeRequested = QtCore.Signal(int)
    attrsRequested  = QtCore.Signal(int, str, tuple)

    def __init__(self, parent=None):
        super(DrivenSourceListEditor, self).__init__(parent)
        self.set_label(tr("driven_source_list_header"))
        self.set_empty_hint(tr("driven_source_list_empty_hint"))

    # --- M_DRIVEN_MULTI: override base button handlers --------------

    def _on_add_clicked(self):
        self.addRequested.emit()

    def _on_remove_clicked(self):
        row = self._list.currentRow()
        if row < 0:
            return
        self.removeRequested.emit(row)

    # --- _OrderedListEditorBase virtuals -----------------------------

    def _create_row_widget(self, initial_value):
        row = _DrivenSourceRow(initial_value)
        row.rowChanged.connect(self._on_any_row_changed)
        row.attrsRequested.connect(
            lambda node, attrs, _row=row: self._forward_attrs_request(
                _row, node, attrs))
        return row

    def _forward_attrs_request(self, row_widget, node, current_attrs):
        for i in range(self._list.count()):
            item = self._list.item(i)
            if self._list.itemWidget(item) is row_widget:
                self.attrsRequested.emit(i, node, tuple(current_attrs))
                return

    def _read_row_value(self, widget):
        return widget.value()

    def _default_value(self):
        return DrivenSource(node="", attrs=tuple())

    # --- Public API --------------------------------------------------

    def set_sources(self, sources):
        """Programmatic rebuild from list[DrivenSource]. Suspends emit
        per the base contract."""
        self.set_values(list(sources))

    def retranslate(self):
        """M_QUICKWINS Item 2 sibling: language-switch hook."""
        super(DrivenSourceListEditor, self).retranslate()
        self.set_label(tr("driven_source_list_header"))
        self.set_empty_hint(tr("driven_source_list_empty_hint"))
        for i in range(self._list.count()):
            widget = self._list.itemWidget(self._list.item(i))
            if isinstance(widget, _DrivenSourceRow):
                widget.retranslate()
