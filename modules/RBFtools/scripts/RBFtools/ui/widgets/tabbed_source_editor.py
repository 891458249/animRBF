# -*- coding: utf-8 -*-
"""TabbedSourceEditor — QTabWidget paradigm for driver / driven multi-source.

Replaces the M_B24b1 / M_DRIVEN_MULTI list-row editors with a tabbed
layout matching the Tekken-8 AnimaRbfSolver reference UX (user request
2026-04-27): each driver / driven entry is a `Driver N` / `Driven N`
tab, and within each tab the TD picks the source node + selects
attributes via the same Select-button + multi-select QListWidget
surface as the legacy `AttributeList` widget.

Two concrete subclasses are exposed:

* :class:`TabbedDriverSourceEditor` - drives `controller.add_driver_source`,
  `remove_driver_source`, `set_driver_source_attrs`. Per-tab content
  includes the M_B24b1 weight + encoding combo so a TD can configure
  per-source weight / encoding without opening another panel.
* :class:`TabbedDrivenSourceEditor` - drives `controller.add_driven_source`,
  `remove_driven_source`, `set_driven_source_attrs`. No per-tab weight /
  encoding (those concepts are driver-only).

MVC red line preserved: the widget never imports `cmds`. The tab
content emits intent signals (`addRequested`, `removeRequested(int)`,
`attrsApplyRequested(int, list)`, `selectNodeRequested(int)`,
`weightChanged(int, float)`, `encodingChanged(int, int)`) that
`main_window` translates into controller calls.
"""

from __future__ import absolute_import

from RBFtools.ui.compat import QtCore, QtWidgets
from RBFtools.ui.i18n import tr


# ----------------------------------------------------------------------
# Encoding labels (mirrors driver_source_list_editor.py)
# ----------------------------------------------------------------------

_ENCODING_LABELS = [
    ("Raw",        0),
    ("Quaternion", 1),
    ("BendRoll",   2),
    ("ExpMap",     3),
    ("SwingTwist", 4),
]


# ----------------------------------------------------------------------
# Per-tab content widget
# ----------------------------------------------------------------------


class _SourceTabContent(QtWidgets.QWidget):
    """Content for one tab in either driver or driven editor.

    Layout matches the AnimaRbfSolver reference:

      Driver/Driven: <node_field> [Select]
      Attributes:
      [QListWidget multi-select]
      [Connect]      [Disconnect]
      [optional weight spinbox + encoding combo for driver tabs]
    """

    selectNodeRequested = QtCore.Signal()
    attrsApplyRequested = QtCore.Signal(list)   # list[str] new attrs
    attrsClearRequested = QtCore.Signal()
    weightChanged       = QtCore.Signal(float)
    encodingChanged     = QtCore.Signal(int)

    def __init__(self, role, with_weight_encoding=False, parent=None):
        super(_SourceTabContent, self).__init__(parent)
        self._role = role  # "driver" or "driven"
        self._with_we = with_weight_encoding
        self._build()

    def _build(self):
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(4)

        # Node row.
        row_node = QtWidgets.QHBoxLayout()
        lbl_key = "driver" if self._role == "driver" else "driven"
        self._lbl_node = QtWidgets.QLabel(tr(lbl_key))
        self._field_node = QtWidgets.QLineEdit()
        self._field_node.setReadOnly(True)
        self._btn_select = QtWidgets.QPushButton(tr("select"))
        self._btn_select.setToolTip(tr("attribute_list_select_tip"))
        self._btn_select.setFixedWidth(60)
        self._btn_select.clicked.connect(self.selectNodeRequested)
        row_node.addWidget(self._lbl_node)
        row_node.addWidget(self._field_node, 1)
        row_node.addWidget(self._btn_select)
        lay.addLayout(row_node)

        # Attrs label + list.
        self._lbl_attrs = QtWidgets.QLabel(tr("attributes"))
        lay.addWidget(self._lbl_attrs)
        self._list = QtWidgets.QListWidget()
        self._list.setSelectionMode(
            QtWidgets.QAbstractItemView.ExtendedSelection)
        lay.addWidget(self._list, 1)

        # Connect / Disconnect (apply / clear) button row.
        row_btn = QtWidgets.QHBoxLayout()
        self._btn_connect = QtWidgets.QPushButton(tr("connect"))
        self._btn_connect.setToolTip(tr("source_tab_connect_tip"))
        self._btn_connect.clicked.connect(self._on_connect_clicked)
        self._btn_disconnect = QtWidgets.QPushButton(tr("disconnect"))
        self._btn_disconnect.setToolTip(tr("source_tab_disconnect_tip"))
        self._btn_disconnect.clicked.connect(
            self.attrsClearRequested)
        row_btn.addWidget(self._btn_connect)
        row_btn.addWidget(self._btn_disconnect)
        lay.addLayout(row_btn)

        # Optional weight + encoding (driver tabs only).
        if self._with_we:
            row_we = QtWidgets.QHBoxLayout()
            row_we.addWidget(QtWidgets.QLabel(
                tr("driver_source_weight_label")))
            self._spin_weight = QtWidgets.QDoubleSpinBox()
            self._spin_weight.setRange(0.0, 1000.0)
            self._spin_weight.setDecimals(3)
            self._spin_weight.setSingleStep(0.1)
            self._spin_weight.setValue(1.0)
            self._spin_weight.setToolTip(
                tr("driver_source_weight_tip"))
            self._spin_weight.valueChanged.connect(self.weightChanged)
            row_we.addWidget(self._spin_weight)
            row_we.addSpacing(8)
            row_we.addWidget(QtWidgets.QLabel(
                tr("driver_source_encoding_label")))
            self._combo_enc = QtWidgets.QComboBox()
            for label, value in _ENCODING_LABELS:
                self._combo_enc.addItem(label, value)
            self._combo_enc.setToolTip(
                tr("driver_source_encoding_tip"))
            self._combo_enc.currentIndexChanged.connect(
                self._on_encoding_changed)
            row_we.addWidget(self._combo_enc)
            row_we.addStretch(1)
            lay.addLayout(row_we)

    # -- signal forwarders --

    def _on_connect_clicked(self):
        self.attrsApplyRequested.emit(self.selected_attrs())

    def _on_encoding_changed(self, _idx):
        self.encodingChanged.emit(int(self._combo_enc.currentData()))

    # -- public API --

    def set_node_name(self, name):
        self._field_node.setText(name or "")

    def node_name(self):
        return self._field_node.text()

    def set_available_attrs(self, attrs, preselected=None):
        """Repopulate the attribute list and optionally pre-select
        a subset (e.g. the source's existing attrs)."""
        preselected_set = set(preselected or [])
        self._list.blockSignals(True)
        try:
            self._list.clear()
            for a in attrs or []:
                item = QtWidgets.QListWidgetItem(a)
                self._list.addItem(item)
                if a in preselected_set:
                    item.setSelected(True)
        finally:
            self._list.blockSignals(False)

    def selected_attrs(self):
        return [it.text() for it in self._list.selectedItems()]

    def set_weight(self, value):
        if not self._with_we:
            return
        self._spin_weight.blockSignals(True)
        try:
            self._spin_weight.setValue(float(value))
        finally:
            self._spin_weight.blockSignals(False)

    def set_encoding(self, value):
        if not self._with_we:
            return
        self._combo_enc.blockSignals(True)
        try:
            for i in range(self._combo_enc.count()):
                if int(self._combo_enc.itemData(i)) == int(value):
                    self._combo_enc.setCurrentIndex(i)
                    break
        finally:
            self._combo_enc.blockSignals(False)

    def retranslate(self):
        lbl_key = "driver" if self._role == "driver" else "driven"
        self._lbl_node.setText(tr(lbl_key))
        self._btn_select.setText(tr("select"))
        self._btn_select.setToolTip(tr("attribute_list_select_tip"))
        self._lbl_attrs.setText(tr("attributes"))
        self._btn_connect.setText(tr("connect"))
        self._btn_connect.setToolTip(tr("source_tab_connect_tip"))
        self._btn_disconnect.setText(tr("disconnect"))
        self._btn_disconnect.setToolTip(tr("source_tab_disconnect_tip"))


# ----------------------------------------------------------------------
# Tabbed editor base
# ----------------------------------------------------------------------


class _TabbedSourceEditorBase(QtWidgets.QWidget):
    """Common QTabWidget shell used by both driver + driven sides.

    Outer widgets:
      - Header label (set by subclass)
      - QTabWidget with closable tabs + a "+" corner widget
      - Empty hint shown when no tabs exist

    Subclass virtuals:
      - _role -> "driver" / "driven"
      - _with_weight_encoding -> bool
      - _tab_label_prefix -> "Driver" / "Driven"
    """

    addRequested        = QtCore.Signal()
    removeRequested     = QtCore.Signal(int)
    attrsApplyRequested = QtCore.Signal(int, list)
    attrsClearRequested = QtCore.Signal(int)
    selectNodeRequested = QtCore.Signal(int)
    weightChanged       = QtCore.Signal(int, float)
    encodingChanged     = QtCore.Signal(int, int)

    _role                 = "driver"
    _with_weight_encoding = False
    _tab_label_prefix     = "Driver"
    _header_key           = "driver_source_list_header"
    _empty_hint_key       = "driver_source_list_empty_hint"

    def __init__(self, parent=None):
        super(_TabbedSourceEditorBase, self).__init__(parent)
        self._build()

    def _build(self):
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)

        self._lbl_header = QtWidgets.QLabel(tr(self._header_key))
        self._lbl_header.setStyleSheet("font-weight: bold;")
        lay.addWidget(self._lbl_header)

        self._tabs = QtWidgets.QTabWidget()
        self._tabs.setTabsClosable(True)
        self._tabs.tabCloseRequested.connect(self._on_tab_close)
        # "+" corner widget acts as Add button.
        self._btn_add = QtWidgets.QToolButton()
        self._btn_add.setText("+")
        self._btn_add.setToolTip(tr("source_tab_add_tip"))
        self._btn_add.clicked.connect(self.addRequested)
        self._tabs.setCornerWidget(
            self._btn_add, QtCore.Qt.TopRightCorner)
        lay.addWidget(self._tabs, 1)

        self._lbl_empty_hint = QtWidgets.QLabel(tr(self._empty_hint_key))
        self._lbl_empty_hint.setStyleSheet(
            "color: gray; font-style: italic;")
        self._lbl_empty_hint.setWordWrap(True)
        self._lbl_empty_hint.setVisible(True)
        lay.addWidget(self._lbl_empty_hint)
        self._update_empty_hint()

    # -- internals --

    def _make_tab_content(self):
        """Override-friendly factory for the per-tab content widget."""
        return _SourceTabContent(
            role=self._role,
            with_weight_encoding=self._with_weight_encoding)

    def _on_tab_close(self, index):
        self.removeRequested.emit(int(index))

    def _update_empty_hint(self):
        empty = (self._tabs.count() == 0)
        self._lbl_empty_hint.setVisible(empty)
        self._tabs.setVisible(not empty)

    def _wire_tab_signals(self, content, index_resolver):
        """Wire a tab content's outbound signals to the editor's
        index-aware re-emission. ``index_resolver`` is a callable
        returning the current index (re-resolved on every emit so
        tab reorder operations stay correct)."""
        content.selectNodeRequested.connect(
            lambda: self.selectNodeRequested.emit(index_resolver()))
        content.attrsApplyRequested.connect(
            lambda attrs: self.attrsApplyRequested.emit(
                index_resolver(), list(attrs)))
        content.attrsClearRequested.connect(
            lambda: self.attrsClearRequested.emit(index_resolver()))
        if self._with_weight_encoding:
            content.weightChanged.connect(
                lambda v: self.weightChanged.emit(index_resolver(), float(v)))
            content.encodingChanged.connect(
                lambda v: self.encodingChanged.emit(index_resolver(), int(v)))

    # -- public API --

    def set_sources(self, sources, available_attrs_per_source=None):
        """Programmatic rebuild from list[DriverSource | DrivenSource].

        ``available_attrs_per_source`` (optional list of list[str])
        seeds the attr picker for each tab so the TD can edit the
        source's attrs without re-clicking Select. If omitted each
        tab will only show the source's *currently-selected* attrs.
        """
        # Preserve currently-selected tab if the source list still
        # contains that index.
        prev_idx = self._tabs.currentIndex()
        # Tear down all existing tabs cleanly.
        while self._tabs.count() > 0:
            w = self._tabs.widget(0)
            self._tabs.removeTab(0)
            if w is not None:
                w.deleteLater()
        for i, src in enumerate(sources or []):
            self._add_source_tab(src, i,
                available_attrs=(available_attrs_per_source[i]
                                 if available_attrs_per_source
                                 and i < len(available_attrs_per_source)
                                 else None))
        # Restore selection if still in range.
        if 0 <= prev_idx < self._tabs.count():
            self._tabs.setCurrentIndex(prev_idx)
        self._update_empty_hint()

    def _add_source_tab(self, src, index, available_attrs=None):
        content = self._make_tab_content()
        # Populate from the source dataclass.
        node = getattr(src, "node", "") or ""
        attrs = list(getattr(src, "attrs", ()) or ())
        content.set_node_name(node)
        # If we have an available-attrs list (from the controller),
        # populate the picker; otherwise just show the existing attrs.
        if available_attrs is not None:
            content.set_available_attrs(available_attrs, preselected=attrs)
        else:
            content.set_available_attrs(attrs, preselected=attrs)
        if self._with_weight_encoding:
            content.set_weight(getattr(src, "weight", 1.0))
            content.set_encoding(getattr(src, "encoding", 0))
        label = "{} {}".format(self._tab_label_prefix, index)
        self._tabs.addTab(content, label)
        # Resolve the current index at signal-emit time so tab
        # reorder / mid-list removal stays correct.
        self._wire_tab_signals(
            content,
            lambda _content=content: self._tabs.indexOf(_content))

    def populate_tab_attrs(self, index, available_attrs, preselected=None):
        """Public slot for main_window to push the resolved
        cmds.listAttr result into a tab after the user clicks
        Select."""
        if not (0 <= index < self._tabs.count()):
            return
        content = self._tabs.widget(index)
        if content is None:
            return
        content.set_available_attrs(
            available_attrs,
            preselected=(preselected
                         if preselected is not None
                         else content.selected_attrs()))

    def set_tab_node_name(self, index, name):
        if not (0 <= index < self._tabs.count()):
            return
        content = self._tabs.widget(index)
        if content is None:
            return
        content.set_node_name(name)

    def current_index(self):
        return self._tabs.currentIndex()

    # -- i18n --

    def retranslate(self):
        self._lbl_header.setText(tr(self._header_key))
        self._lbl_empty_hint.setText(tr(self._empty_hint_key))
        self._btn_add.setToolTip(tr("source_tab_add_tip"))
        for i in range(self._tabs.count()):
            content = self._tabs.widget(i)
            if hasattr(content, "retranslate"):
                content.retranslate()
            self._tabs.setTabText(
                i, "{} {}".format(self._tab_label_prefix, i))


# ----------------------------------------------------------------------
# Concrete editors
# ----------------------------------------------------------------------


class TabbedDriverSourceEditor(_TabbedSourceEditorBase):
    """Driver-side tabbed editor (M_TABBED_EDITOR)."""

    _role                 = "driver"
    _with_weight_encoding = True
    _tab_label_prefix     = "Driver"
    _header_key           = "driver_source_list_header"
    _empty_hint_key       = "driver_source_list_empty_hint"


class TabbedDrivenSourceEditor(_TabbedSourceEditorBase):
    """Driven-side tabbed editor (M_TABBED_EDITOR)."""

    _role                 = "driven"
    _with_weight_encoding = False
    _tab_label_prefix     = "Driven"
    _header_key           = "driven_source_list_header"
    _empty_hint_key       = "driven_source_list_empty_hint"
