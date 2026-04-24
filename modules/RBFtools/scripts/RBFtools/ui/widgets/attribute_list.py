# -*- coding: utf-8 -*-
"""
Attribute list widget — QListWidget with right-click filter popup.

Signals only; the parent wires ``filtersChanged`` to a core call that
returns the filtered attribute names.
"""

from __future__ import absolute_import

from RBFtools.ui.compat import QtWidgets, QtCore
from RBFtools.ui.i18n import tr
from RBFtools.constants import FILTER_DEFAULTS

# i18n key → filter dict key
_FILTER_ITEMS = [
    ("show_keyable",      "Keyable"),
    ("show_non_keyable",  "NonKeyable"),
    None,
    ("show_readable",     "Readable"),
    ("show_writable",     "Writable"),
    None,
    ("show_connected",    "Connected"),
    ("show_hidden",       "Hidden"),
    ("show_user_defined", "UserDefined"),
]


class AttributeList(QtWidgets.QWidget):
    """A labelled text field + attribute list with right-click filter menu.

    Parameters
    ----------
    role : str
        ``'driver'`` or ``'driven'``.
    """

    selectNodeRequested = QtCore.Signal()          # "Select" button
    filtersChanged = QtCore.Signal(str, dict)      # (role, {key: 0|1})
    selectionChanged = QtCore.Signal()             # list selection changed

    def __init__(self, role, parent=None):
        super(AttributeList, self).__init__(parent)
        self._role = role
        self._filters = dict(FILTER_DEFAULTS)
        self._build()

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _build(self):
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)

        # Top row: label + field + Select btn
        top = QtWidgets.QHBoxLayout()
        tr_key = "driver" if self._role == "driver" else "driven"
        self._lbl = QtWidgets.QLabel(tr(tr_key))
        self._field = QtWidgets.QLineEdit()
        self._field.setReadOnly(True)
        self._btn_sel = QtWidgets.QPushButton(tr("select"))
        self._btn_sel.setFixedWidth(55)
        self._btn_sel.clicked.connect(self.selectNodeRequested)
        top.addWidget(self._lbl)
        top.addWidget(self._field, 1)
        top.addWidget(self._btn_sel)
        lay.addLayout(top)

        # Attribute label
        self._lbl_attrs = QtWidgets.QLabel(tr("attributes"))
        lay.addWidget(self._lbl_attrs)

        # List
        self._list = QtWidgets.QListWidget()
        self._list.setSelectionMode(
            QtWidgets.QAbstractItemView.ExtendedSelection)
        self._list.itemSelectionChanged.connect(self.selectionChanged)
        lay.addWidget(self._list, 1)

        # Context menu
        self._list.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._show_filter_menu)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def role(self):
        return self._role

    def set_node_name(self, name):
        self._field.setText(name)

    def node_name(self):
        return self._field.text()

    def set_attributes(self, attrs):
        self._list.clear()
        for a in attrs:
            self._list.addItem(a)

    def selected_attributes(self):
        return [it.text() for it in self._list.selectedItems()]

    def select_attributes(self, names):
        """Programmatically select items by name."""
        self._list.clearSelection()
        for i in range(self._list.count()):
            item = self._list.item(i)
            if item.text() in names:
                item.setSelected(True)

    def set_filters(self, filters):
        """Set filter dict (e.g. loaded from optionVar)."""
        self._filters.update(filters)

    def filters(self):
        return dict(self._filters)

    def retranslate(self):
        tr_key = "driver" if self._role == "driver" else "driven"
        self._lbl.setText(tr(tr_key))
        self._btn_sel.setText(tr("select"))
        self._lbl_attrs.setText(tr("attributes"))

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _show_filter_menu(self, pos):
        menu = QtWidgets.QMenu(self)
        actions = []
        for item in _FILTER_ITEMS:
            if item is None:
                menu.addSeparator()
                continue
            tr_key, filt_key = item
            act = menu.addAction(tr(tr_key))
            act.setCheckable(True)
            act.setChecked(bool(self._filters.get(filt_key, 0)))
            act.setProperty("_fk", filt_key)
            actions.append(act)

        for act in actions:
            act.toggled.connect(self._on_filter_toggle)

        menu.exec_(self._list.mapToGlobal(pos))

    def _on_filter_toggle(self, checked):
        sender = self.sender()
        fk = sender.property("_fk")
        self._filters[fk] = int(checked)
        self.filtersChanged.emit(self._role, dict(self._filters))
