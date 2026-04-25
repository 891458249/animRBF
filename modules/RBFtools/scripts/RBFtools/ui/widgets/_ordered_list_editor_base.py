# -*- coding: utf-8 -*-
"""
Generic ordered-list editor base class (M2.4b).

Two concrete subclasses:

* :class:`OrderedIntListEditor` — rows are ``QSpinBox``,
  used for ``outputQuaternionGroupStart[]`` (M2.2).
* :class:`OrderedEnumListEditor` — rows are ``QComboBox``,
  used for ``driverInputRotateOrder[]`` (M2.1a).

Design (v5 addendum §M2.4b):

* **Single emit collector** — every inline-widget value-change signal
  routes to ``_on_any_row_changed`` which scans the full list and
  emits ``listChanged(values)`` once. Eliminates the stale-row-index
  bug that per-row ``lambda row=i: ...`` capture is prone to after
  reorder.
* **Destroy-and-rebuild on reorder** — ``move_up`` / ``move_down``
  ``takeItem`` then recreate the inline widget from the recorded
  value, avoiding short-lived widget-parent-orphan PySide warnings.
* **Programmatic ``set_values`` does NOT emit** — the ``_suspend_emit``
  guard prevents controller-initiated ``load(data)`` from firing
  ``listChanged`` back into the controller and creating a feedback
  loop. Only user interaction emits.
* **No keyboard Delete shortcut** — only the "−" button removes,
  consistent across macOS / Windows / Linux.
* **``item.setSizeHint(widget.sizeHint())`` after ``setItemWidget``**
  — required to keep the row from collapsing to 1 px in some PySide
  versions (addendum §M2.4b Q1d).

Signals only — never imports ``RBFtools.core`` (MVC red line).
"""

from __future__ import absolute_import

from RBFtools.ui.compat import QtWidgets, QtCore
from RBFtools.ui.i18n import tr


class _OrderedListEditorBase(QtWidgets.QWidget):
    """Abstract ordered-list editor with add / remove / reorder buttons.

    Subclass virtuals:
      * ``_create_row_widget(initial_value) -> QWidget``
      * ``_read_row_value(widget) -> int``
      * ``_default_value() -> int``  (override for non-zero default)
    """

    listChanged = QtCore.Signal(list)

    def __init__(self, parent=None):
        super(_OrderedListEditorBase, self).__init__(parent)
        # Suspend-emit guard for programmatic rebuilds. set_values
        # mutates _list internally and we must NOT re-emit listChanged
        # mid-rebuild — the controller is the originator and would
        # round-trip the value back into itself.
        self._suspend_emit = False
        self._build()

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _build(self):
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)

        # Optional header label set by subclass via set_label().
        self._lbl_header = QtWidgets.QLabel("")
        self._lbl_header.setStyleSheet("font-weight: bold;")
        self._lbl_header.setVisible(False)
        lay.addWidget(self._lbl_header)

        self._list = QtWidgets.QListWidget()
        self._list.setSelectionMode(
            QtWidgets.QAbstractItemView.SingleSelection)
        # NOTE: no Delete-key binding on the list. Removal is button-
        # only per addendum §M2.4b refinement 2.
        lay.addWidget(self._list, 1)

        # Empty hint shown when the list has 0 entries.
        self._lbl_empty_hint = QtWidgets.QLabel("")
        self._lbl_empty_hint.setStyleSheet("color: gray; font-style: italic;")
        self._lbl_empty_hint.setVisible(False)
        lay.addWidget(self._lbl_empty_hint)

        # Button row.
        btn_row = QtWidgets.QHBoxLayout()
        btn_row.setContentsMargins(0, 0, 0, 0)
        self._btn_add = QtWidgets.QToolButton()
        self._btn_add.setText(tr("list_editor_add"))
        self._btn_add.setToolTip(tr("list_editor_add_tip"))
        self._btn_add.clicked.connect(self._on_add_clicked)

        self._btn_remove = QtWidgets.QToolButton()
        self._btn_remove.setText(tr("list_editor_remove"))
        self._btn_remove.setToolTip(tr("list_editor_remove_tip"))
        self._btn_remove.clicked.connect(self._on_remove_clicked)

        self._btn_up = QtWidgets.QToolButton()
        self._btn_up.setText(tr("list_editor_move_up"))
        self._btn_up.setToolTip(tr("list_editor_move_up_tip"))
        self._btn_up.clicked.connect(self._on_move_up_clicked)

        self._btn_down = QtWidgets.QToolButton()
        self._btn_down.setText(tr("list_editor_move_down"))
        self._btn_down.setToolTip(tr("list_editor_move_down_tip"))
        self._btn_down.clicked.connect(self._on_move_down_clicked)

        btn_row.addWidget(self._btn_add)
        btn_row.addWidget(self._btn_remove)
        btn_row.addWidget(self._btn_up)
        btn_row.addWidget(self._btn_down)
        btn_row.addStretch()
        lay.addLayout(btn_row)

        self._update_empty_hint()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_label(self, text):
        """Configure the header label. Empty string hides the header."""
        if text:
            self._lbl_header.setText(text)
            self._lbl_header.setVisible(True)
        else:
            self._lbl_header.setVisible(False)

    def set_empty_hint(self, text):
        """Configure the placeholder text shown when the list is empty."""
        self._lbl_empty_hint.setText(text or "")
        self._update_empty_hint()

    def set_values(self, values):
        """Programmatically rebuild rows from *values*.

        CONTRACT (addendum §M2.4b refinement): emits ``listChanged``
        ZERO times. The controller is the originator of this call —
        re-emitting would round-trip back into the controller and
        create a feedback loop on every load.
        """
        self._suspend_emit = True
        try:
            self._list.clear()
            for v in values:
                self._add_row_internal(v)
        finally:
            self._suspend_emit = False
        self._update_empty_hint()

    def get_values(self):
        """Return the current ordered list of int values."""
        out = []
        for i in range(self._list.count()):
            item = self._list.item(i)
            widget = self._list.itemWidget(item)
            if widget is None:
                continue
            out.append(int(self._read_row_value(widget)))
        return out

    def clear(self):
        self.set_values([])

    def retranslate(self):
        self._btn_add.setText(tr("list_editor_add"))
        self._btn_add.setToolTip(tr("list_editor_add_tip"))
        self._btn_remove.setText(tr("list_editor_remove"))
        self._btn_remove.setToolTip(tr("list_editor_remove_tip"))
        self._btn_up.setText(tr("list_editor_move_up"))
        self._btn_up.setToolTip(tr("list_editor_move_up_tip"))
        self._btn_down.setText(tr("list_editor_move_down"))
        self._btn_down.setToolTip(tr("list_editor_move_down_tip"))

    # ------------------------------------------------------------------
    # Subclass virtuals
    # ------------------------------------------------------------------

    def _create_row_widget(self, initial_value):
        raise NotImplementedError

    def _read_row_value(self, widget):
        raise NotImplementedError

    def _default_value(self):
        return 0

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _add_row_internal(self, value):
        """Append a row without firing listChanged. Used by both
        set_values (suspended) and _on_add_clicked (which un-suspends
        right after to fire one collector emit)."""
        item = QtWidgets.QListWidgetItem(self._list)
        widget = self._create_row_widget(value)
        # Q1d: explicit sizeHint after setItemWidget — required across
        # PySide2 / PySide6 to prevent row collapse.
        item.setSizeHint(widget.sizeHint())
        self._list.addItem(item)
        self._list.setItemWidget(item, widget)

    def _rebuild_row(self, row_idx, value):
        """Destroy-and-rebuild pattern (addendum §M2.4b Q1b)."""
        item = self._list.item(row_idx)
        if item is None:
            return
        widget = self._create_row_widget(value)
        item.setSizeHint(widget.sizeHint())
        self._list.setItemWidget(item, widget)

    def _on_any_row_changed(self):
        """Single collector — every inline widget's value-change signal
        routes here. Re-scans the full list and fires listChanged once.
        Suppressed during set_values rebuilds."""
        if self._suspend_emit:
            return
        self.listChanged.emit(self.get_values())

    def _on_add_clicked(self):
        self._add_row_internal(self._default_value())
        self._update_empty_hint()
        self._on_any_row_changed()

    def _on_remove_clicked(self):
        row = self._list.currentRow()
        if row < 0:
            return
        self._list.takeItem(row)
        self._update_empty_hint()
        self._on_any_row_changed()

    def _on_move_up_clicked(self):
        row = self._list.currentRow()
        if row <= 0:
            return
        # Capture value, take, reinsert, rebuild widget.
        cur_widget = self._list.itemWidget(self._list.item(row))
        cur_value = self._read_row_value(cur_widget) if cur_widget else \
            self._default_value()
        self._list.takeItem(row)
        self._suspend_emit = True
        try:
            new_item = QtWidgets.QListWidgetItem()
            self._list.insertItem(row - 1, new_item)
            new_widget = self._create_row_widget(cur_value)
            new_item.setSizeHint(new_widget.sizeHint())
            self._list.setItemWidget(new_item, new_widget)
            self._list.setCurrentRow(row - 1)
        finally:
            self._suspend_emit = False
        self._on_any_row_changed()

    def _on_move_down_clicked(self):
        row = self._list.currentRow()
        if row < 0 or row >= self._list.count() - 1:
            return
        cur_widget = self._list.itemWidget(self._list.item(row))
        cur_value = self._read_row_value(cur_widget) if cur_widget else \
            self._default_value()
        self._list.takeItem(row)
        self._suspend_emit = True
        try:
            new_item = QtWidgets.QListWidgetItem()
            self._list.insertItem(row + 1, new_item)
            new_widget = self._create_row_widget(cur_value)
            new_item.setSizeHint(new_widget.sizeHint())
            self._list.setItemWidget(new_item, new_widget)
            self._list.setCurrentRow(row + 1)
        finally:
            self._suspend_emit = False
        self._on_any_row_changed()

    def _update_empty_hint(self):
        is_empty = (self._list.count() == 0)
        if is_empty and self._lbl_empty_hint.text():
            self._lbl_empty_hint.setVisible(True)
            self._list.setMaximumHeight(0)
        else:
            self._lbl_empty_hint.setVisible(False)
            self._list.setMaximumHeight(16777215)  # Qt default unbounded
