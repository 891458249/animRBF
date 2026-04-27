# -*- coding: utf-8 -*-
"""TabbedSourceEditor — strict-spec rewrite (2026-04-27 user directive).

Layout per the user's strict UI spec:

  [QGroupBox / QFrame border]
    QVBoxLayout:
      Inner QTabWidget (Driver 0 | Driver 1 | ...)  - per-source tabs
        per-tab content:
          Object Selection Row:
            QLabel "Driver/Driven"   QLineEdit (stretch)   [Select]
          Attributes Row:
            QLabel "Attributes"  (top-aligned)   QListWidget
              - DRIVER:  single-selection
              - DRIVEN:  extended (multi) selection
      [Connect]  [Disconnect]   <- panel-level, operates on current tab
      [Add Driver / Add Driven]  <- panel-level, full width

The per-tab weight + encoding controls from the previous iteration
are removed per user directive (defaults: weight=1.0, encoding=0
when adding new sources).

MVC red line preserved: the widget never imports `cmds`. The
panel emits intent signals (`addRequested`, `removeRequested(int)`,
`attrsApplyRequested(int, list[str])`, `attrsClearRequested(int)`,
`selectNodeRequested(int)`); main_window owns the cmds.* calls
and forwards to the controller.
"""

from __future__ import absolute_import

from RBFtools.ui.compat import QtCore, QtWidgets
from RBFtools.ui.i18n import tr


# ----------------------------------------------------------------------
# Per-tab content widget
# ----------------------------------------------------------------------


class _SourceTabContent(QtWidgets.QWidget):
    """Content for one tab in either driver or driven panel.

    Per the user's 2026-04-27 strict UI spec the per-tab layout is:

      Driver/Driven: <node_field> [Select]
      Attributes:    [QListWidget]   <- single-sel for driver, multi for driven

    Connect / Disconnect / Add buttons live at the panel level
    (above the QGroupBox border) - they are NOT part of the per-tab
    content.
    """

    selectNodeRequested = QtCore.Signal()

    def __init__(self, role, parent=None):
        super(_SourceTabContent, self).__init__(parent)
        self._role = role  # "driver" or "driven"
        self._build()

    def _build(self):
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(4)

        # Object Selection Row.
        row_node = QtWidgets.QHBoxLayout()
        lbl_key = "driver" if self._role == "driver" else "driven"
        self._lbl_node = QtWidgets.QLabel(tr(lbl_key))
        self._lbl_node.setMinimumWidth(50)
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

        # Attributes Row: QLabel left (vertical-align top) + QListWidget
        # right that fills the remaining vertical space.
        row_attrs = QtWidgets.QHBoxLayout()
        self._lbl_attrs = QtWidgets.QLabel(tr("attributes"))
        self._lbl_attrs.setMinimumWidth(50)
        self._lbl_attrs.setAlignment(
            QtCore.Qt.AlignTop | QtCore.Qt.AlignLeft)
        row_attrs.addWidget(self._lbl_attrs)
        self._list = QtWidgets.QListWidget()
        # Selection mode per role (user strict spec):
        #   driver -> single ; driven -> multi (extended).
        if self._role == "driver":
            self._list.setSelectionMode(
                QtWidgets.QAbstractItemView.SingleSelection)
        else:
            self._list.setSelectionMode(
                QtWidgets.QAbstractItemView.ExtendedSelection)
        self._list.setVerticalScrollBarPolicy(
            QtCore.Qt.ScrollBarAsNeeded)
        self._list.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Expanding)
        row_attrs.addWidget(self._list, 1)
        lay.addLayout(row_attrs, 1)

    # -- public API used by the panel --

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

    def retranslate(self):
        lbl_key = "driver" if self._role == "driver" else "driven"
        self._lbl_node.setText(tr(lbl_key))
        self._btn_select.setText(tr("select"))
        self._btn_select.setToolTip(tr("attribute_list_select_tip"))
        self._lbl_attrs.setText(tr("attributes"))


# ----------------------------------------------------------------------
# Panel base (QGroupBox-wrapped inner QTabWidget + bottom buttons)
# ----------------------------------------------------------------------


class _TabbedSourceEditorBase(QtWidgets.QGroupBox):
    """One Driver/Driven panel - QGroupBox-wrapped inner QTabWidget +
    Connect/Disconnect row + full-width Add button.

    Subclass virtuals:
      _role                    -> "driver" / "driven"
      _tab_label_prefix        -> "Driver" / "Driven"
      _header_key              -> i18n key for the QGroupBox title
      _add_button_key          -> i18n key for the Add button label
      _empty_hint_key          -> i18n key for the empty-state hint

    Signal surface (panel-level; index is the tab index resolved
    at emit time so reorder operations stay correct):

      addRequested()                              <- bottom Add btn
      removeRequested(int)                        <- tab close X
      attrsApplyRequested(int, list[str])         <- Connect btn
      attrsClearRequested(int)                    <- Disconnect btn
      selectNodeRequested(int)                    <- per-tab Select
    """

    addRequested        = QtCore.Signal()
    removeRequested     = QtCore.Signal(int)
    attrsApplyRequested = QtCore.Signal(int, list)
    attrsClearRequested = QtCore.Signal(int)
    selectNodeRequested = QtCore.Signal(int)

    _role                 = "driver"
    _tab_label_prefix     = "Driver"
    _header_key           = "driver_source_list_header"
    _add_button_key       = "btn_add_driver"
    _empty_hint_key       = "driver_source_list_empty_hint"

    def __init__(self, parent=None):
        super(_TabbedSourceEditorBase, self).__init__(
            tr(self._header_key), parent)
        self._build()

    def _build(self):
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(6, 12, 6, 6)
        lay.setSpacing(4)

        # Inner QTabWidget hosting per-source _SourceTabContent.
        self._tabs = QtWidgets.QTabWidget()
        self._tabs.setTabsClosable(True)
        self._tabs.tabCloseRequested.connect(self._on_tab_close)
        lay.addWidget(self._tabs, 1)

        # Empty hint shown below the tab widget when there are no
        # tabs yet.
        self._lbl_empty_hint = QtWidgets.QLabel(tr(self._empty_hint_key))
        self._lbl_empty_hint.setStyleSheet(
            "color: gray; font-style: italic;")
        self._lbl_empty_hint.setWordWrap(True)
        self._lbl_empty_hint.setVisible(True)
        lay.addWidget(self._lbl_empty_hint)

        # Connect / Disconnect row (panel-level - operates on the
        # currently-active tab).
        row_cd = QtWidgets.QHBoxLayout()
        self._btn_connect = QtWidgets.QPushButton(tr("connect"))
        self._btn_connect.setToolTip(tr("source_tab_connect_tip"))
        self._btn_connect.clicked.connect(self._on_connect_clicked)
        self._btn_disconnect = QtWidgets.QPushButton(tr("disconnect"))
        self._btn_disconnect.setToolTip(tr("source_tab_disconnect_tip"))
        self._btn_disconnect.clicked.connect(self._on_disconnect_clicked)
        row_cd.addWidget(self._btn_connect, 1)
        row_cd.addWidget(self._btn_disconnect, 1)
        lay.addLayout(row_cd)

        # Full-width Add Driver / Add Driven button.
        self._btn_add = QtWidgets.QPushButton(tr(self._add_button_key))
        self._btn_add.setToolTip(tr("source_tab_add_tip"))
        self._btn_add.clicked.connect(self.addRequested)
        lay.addWidget(self._btn_add)

        self._update_empty_hint()

    # -- internals --

    def _on_tab_close(self, index):
        self.removeRequested.emit(int(index))

    def _on_connect_clicked(self):
        idx = self._tabs.currentIndex()
        if idx < 0:
            return
        content = self._tabs.widget(idx)
        if content is None:
            return
        attrs = content.selected_attrs()
        self.attrsApplyRequested.emit(idx, list(attrs))

    def _on_disconnect_clicked(self):
        idx = self._tabs.currentIndex()
        if idx < 0:
            return
        self.attrsClearRequested.emit(idx)

    def _update_empty_hint(self):
        empty = (self._tabs.count() == 0)
        self._lbl_empty_hint.setVisible(empty)
        # Connect / Disconnect are only meaningful with an active
        # tab - disable them in the empty state but always keep
        # them visible so the layout stays stable.
        self._btn_connect.setEnabled(not empty)
        self._btn_disconnect.setEnabled(not empty)

    def _wire_tab_signals(self, content, index_resolver):
        """Wire a tab content's per-tab signals to the panel-level
        re-emission. ``index_resolver`` is a callable returning the
        tab's current index (resolved at emit time so tab reorder
        stays correct)."""
        content.selectNodeRequested.connect(
            lambda: self.selectNodeRequested.emit(index_resolver()))

    # -- public API --

    def current_index(self):
        return self._tabs.currentIndex()

    def set_sources(self, sources, available_attrs_per_source=None):
        """Programmatic rebuild from list[DriverSource | DrivenSource].

        ``available_attrs_per_source`` (optional list of list[str])
        seeds the attr picker for each tab so the TD can edit the
        source's attrs without re-clicking Select. If omitted each
        tab will only show the source's *currently-selected* attrs.
        """
        prev_idx = self._tabs.currentIndex()
        # Tear down all existing tabs cleanly.
        while self._tabs.count() > 0:
            w = self._tabs.widget(0)
            self._tabs.removeTab(0)
            if w is not None:
                w.deleteLater()
        for i, src in enumerate(sources or []):
            self._add_source_tab(
                src, i,
                available_attrs=(available_attrs_per_source[i]
                                 if available_attrs_per_source
                                 and i < len(available_attrs_per_source)
                                 else None))
        if 0 <= prev_idx < self._tabs.count():
            self._tabs.setCurrentIndex(prev_idx)
        self._update_empty_hint()

    def _add_source_tab(self, src, index, available_attrs=None):
        content = _SourceTabContent(role=self._role)
        node = getattr(src, "node", "") or ""
        attrs = list(getattr(src, "attrs", ()) or ())
        content.set_node_name(node)
        if available_attrs is not None:
            content.set_available_attrs(available_attrs, preselected=attrs)
        else:
            content.set_available_attrs(attrs, preselected=attrs)
        label = "{} {}".format(self._tab_label_prefix, index)
        self._tabs.addTab(content, label)
        self._wire_tab_signals(
            content,
            lambda _content=content: self._tabs.indexOf(_content))

    def populate_tab_attrs(self, index, available_attrs, preselected=None):
        """Public slot for main_window to push a fresh cmds.listAttr
        result into a tab after the user clicks Select."""
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

    # -- i18n --

    def retranslate(self):
        self.setTitle(tr(self._header_key))
        self._lbl_empty_hint.setText(tr(self._empty_hint_key))
        self._btn_add.setText(tr(self._add_button_key))
        self._btn_add.setToolTip(tr("source_tab_add_tip"))
        self._btn_connect.setText(tr("connect"))
        self._btn_connect.setToolTip(tr("source_tab_connect_tip"))
        self._btn_disconnect.setText(tr("disconnect"))
        self._btn_disconnect.setToolTip(tr("source_tab_disconnect_tip"))
        for i in range(self._tabs.count()):
            content = self._tabs.widget(i)
            if hasattr(content, "retranslate"):
                content.retranslate()
            self._tabs.setTabText(
                i, "{} {}".format(self._tab_label_prefix, i))


# ----------------------------------------------------------------------
# Concrete subclasses
# ----------------------------------------------------------------------


class TabbedDriverSourceEditor(_TabbedSourceEditorBase):
    """Driver-side tabbed editor (M_TABBED_EDITOR_REWRITE)."""

    _role             = "driver"
    _tab_label_prefix = "Driver"
    _header_key       = "driver_source_list_header"
    _add_button_key   = "btn_add_driver"
    _empty_hint_key   = "driver_source_list_empty_hint"


class TabbedDrivenSourceEditor(_TabbedSourceEditorBase):
    """Driven-side tabbed editor (M_TABBED_EDITOR_REWRITE)."""

    _role             = "driven"
    _tab_label_prefix = "Driven"
    _header_key       = "driven_source_list_header"
    _add_button_key   = "btn_add_driven"
    _empty_hint_key   = "driven_source_list_empty_hint"
