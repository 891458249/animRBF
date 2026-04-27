# -*- coding: utf-8 -*-
"""DriverSourceListEditor — multi-source driver list editor (M_B24b1).

The UI primary deliverable per user override 2026-04-26. Renders a
list of DriverSource entries, each row being a composite widget with
4 fields matching the C++ M_B24a1 schema:

  driverSource[d].driverSource_node     <- node-selector widget
  driverSource[d].driverSource_attrs    <- attrs list (comma-joined)
  driverSource[d].driverSource_weight   <- QDoubleSpinBox
  driverSource[d].driverSource_encoding <- QComboBox enum

Inherits :class:`_OrderedListEditorBase` (M2.4b). The base's
``listChanged`` signal payload is the list of DriverSource dataclass
instances - the docstring on the base says ``int`` but the implementation
is type-erased and works for any picklable value (verify-before-design
16th use F1 finding).

See addendum #M_B24b1 for the full design rationale, especially the
node_name() vs node_names() dual-path strategy (Hardening 5 of M_B24b
plan): the legacy single-driver property routes to drivers[0] with a
DeprecationWarning to keep all 14 read_driver_info call-sites
zero-modification (M_B24a2-1 backcompat extended to UI layer).
"""

from __future__ import absolute_import

import warnings

from RBFtools.ui.compat import QtCore, QtWidgets
from RBFtools.ui.i18n import tr
from RBFtools.ui.widgets._ordered_list_editor_base import (
    _OrderedListEditorBase,
)

# Keep imports of core lazy/local where possible so the M2.4b widget-
# layer-no-core-import boundary isn't violated. We import DriverSource
# from core because the dataclass IS the data contract — both layers
# need to agree on the type. This is the same surgical exception the
# tests at test_m_b24a2_migration.py make.
from RBFtools.core import DriverSource


# Encoding enum labels — keys mirror inputEncoding C++ enum (M2.1a) and
# driverSource_encoding (M_B24a1 §3.2).
_ENCODING_LABELS = [
    ("Raw",        0),
    ("Quaternion", 1),
    ("BendRoll",   2),
    ("ExpMap",     3),
    ("SwingTwist", 4),
]


class _DriverSourceRow(QtWidgets.QWidget):
    """Composite row widget. Emits ``rowChanged`` whenever any of the
    four fields mutates so the parent base can re-emit ``listChanged``.

    M_UIRECONCILE_PLUS (Item 4b): adds an in-row "Attrs..." button +
    ``attrsRequested`` signal so the TD can pick the source's
    attribute list per-row. The button payload carries the source's
    current node name + current attrs so the parent's slot can
    pre-populate the picker dialog."""

    rowChanged    = QtCore.Signal()
    attrsRequested = QtCore.Signal(str, tuple)   # (node, current_attrs)

    def __init__(self, source, parent=None):
        super(_DriverSourceRow, self).__init__(parent)
        self._source = source if isinstance(source, DriverSource) else \
            DriverSource(node="", attrs=tuple())
        self._build()

    def _build(self):
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(2, 2, 2, 2)
        lay.setSpacing(4)

        # Node label (read-only — set via controller path A).
        self._lbl_node = QtWidgets.QLabel(self._source.node or "<unset>")
        self._lbl_node.setMinimumWidth(120)
        self._lbl_node.setToolTip(tr("driver_source_node_tip"))
        lay.addWidget(self._lbl_node, 1)

        # Attrs joined preview (read-only label - editing is via
        # the Attrs... button below).
        attrs_text = ", ".join(self._source.attrs) if self._source.attrs else ""
        self._lbl_attrs = QtWidgets.QLabel(attrs_text)
        self._lbl_attrs.setMinimumWidth(160)
        self._lbl_attrs.setToolTip(tr("driver_source_attrs_tip"))
        lay.addWidget(self._lbl_attrs, 2)

        # M_UIRECONCILE_PLUS Item 4b: in-row Attrs picker button.
        self._btn_attrs = QtWidgets.QPushButton(tr("driver_source_attrs_btn"))
        self._btn_attrs.setToolTip(tr("driver_source_attrs_btn_tip"))
        self._btn_attrs.setMaximumWidth(70)
        self._btn_attrs.clicked.connect(self._on_attrs_clicked)
        lay.addWidget(self._btn_attrs)

        # Weight (editable).
        self._spin_weight = QtWidgets.QDoubleSpinBox()
        self._spin_weight.setRange(0.0, 1000.0)
        self._spin_weight.setDecimals(3)
        self._spin_weight.setSingleStep(0.1)
        self._spin_weight.setValue(float(self._source.weight))
        self._spin_weight.setToolTip(tr("driver_source_weight_tip"))
        self._spin_weight.valueChanged.connect(self._on_changed)
        lay.addWidget(self._spin_weight)

        # Encoding (editable enum combo).
        self._combo_enc = QtWidgets.QComboBox()
        for label, value in _ENCODING_LABELS:
            self._combo_enc.addItem(label, value)
        self._combo_enc.setCurrentIndex(int(self._source.encoding))
        self._combo_enc.setToolTip(tr("driver_source_encoding_tip"))
        self._combo_enc.currentIndexChanged.connect(self._on_changed)
        lay.addWidget(self._combo_enc)

    def _on_changed(self, *args, **kwargs):
        self.rowChanged.emit()

    def _on_attrs_clicked(self):
        """M_UIRECONCILE_PLUS Item 4b: emit a request for the parent
        slot to open the attribute picker dialog for this source.
        The slot owns the cmds.* call (MVC red line)."""
        self.attrsRequested.emit(
            self._source.node or "", tuple(self._source.attrs))

    def value(self):
        """Read the current widget state as a DriverSource dataclass."""
        return DriverSource(
            node=self._source.node,
            attrs=self._source.attrs,
            weight=float(self._spin_weight.value()),
            encoding=int(self._combo_enc.currentData()),
        )


class DriverSourceListEditor(_OrderedListEditorBase):
    """Editable ordered list of :class:`DriverSource` entries.

    M_B24b1 primary deliverable per user override 2026-04-26. The
    ``listChanged`` signal payload is ``list[DriverSource]``. Per
    Hardening 5, also exposes a deprecated single-driver mirror
    (:meth:`node_name`) so 14 legacy call-sites in main_window.py /
    pose_editor.py / controller.py keep working unchanged.

    M_UIRECONCILE wiring (decision A.2 + F.1): the ``+`` and ``-``
    buttons no longer mutate local widget state directly. They emit
    ``addRequested`` / ``removeRequested`` so the controller layer
    (via ``main_window``) drives the real ``core.add_driver_source``
    / ``core.remove_driver_source`` mutation, then reloads the
    widget from the resulting node state. This closes the
    M_B24b1 island-widget gap (see addendum
    §M_UIRECONCILE.m_b24b1-correction).
    """

    # M_UIRECONCILE: payload-less request signals - main_window owns
    # the cmds.ls call that resolves the current Maya selection, so
    # the widget stays free of `import maya.cmds` (MVC red line).
    addRequested    = QtCore.Signal()
    removeRequested = QtCore.Signal(int)
    # M_UIRECONCILE_PLUS Item 4b: per-row Attrs... button. Payload =
    # (row index, source node name, current attrs tuple). The
    # attribute picker dialog lives in main_window which owns the
    # cmds.listAttr call.
    attrsRequested  = QtCore.Signal(int, str, tuple)

    def __init__(self, parent=None):
        super(DriverSourceListEditor, self).__init__(parent)
        self.set_label(tr("driver_source_list_header"))
        self.set_empty_hint(tr("driver_source_list_empty_hint"))

    # --- M_UIRECONCILE: override base button handlers --------------

    def _on_add_clicked(self):
        """M_UIRECONCILE (decision A.2): replace the legacy
        ``base._add_row_internal(<unset>)`` behaviour. We forward
        the click to the controller layer via ``addRequested``.
        The widget will reload via ``set_sources`` once the
        controller emits ``driverSourcesChanged``."""
        self.addRequested.emit()

    def _on_remove_clicked(self):
        """M_UIRECONCILE: forward selected row index. Controller
        runs the path-A confirm + core.remove_driver_source +
        emits driverSourcesChanged for reload."""
        row = self._list.currentRow()
        if row < 0:
            return
        self.removeRequested.emit(row)

    # --- _OrderedListEditorBase virtuals -------------------------------

    def _create_row_widget(self, initial_value):
        row = _DriverSourceRow(initial_value)
        row.rowChanged.connect(self._on_any_row_changed)
        # M_UIRECONCILE_PLUS Item 4b: bridge per-row attrs request
        # to the editor-level signal. The QListWidget row index is
        # resolved at emit time so reorder operations stay correct.
        row.attrsRequested.connect(
            lambda node, attrs, _row=row: self._forward_attrs_request(
                _row, node, attrs))
        return row

    def _forward_attrs_request(self, row_widget, node, current_attrs):
        """Look up the row's current QListWidget index + re-emit
        upstream as ``attrsRequested(idx, node, current_attrs)``."""
        for i in range(self._list.count()):
            item = self._list.item(i)
            if self._list.itemWidget(item) is row_widget:
                self.attrsRequested.emit(i, node, tuple(current_attrs))
                return

    def _read_row_value(self, widget):
        # widget is a _DriverSourceRow; return the dataclass.
        return widget.value()

    def _default_value(self):
        return DriverSource(node="", attrs=tuple())

    # --- Public API + deprecated single-driver mirror (Hardening 5) ----

    def node_name(self):
        """DEPRECATED. Returns the first source's node, or empty string.

        Kept for 14 legacy call-sites that pre-date M_B24b multi-source.
        New code should use :meth:`node_names` (returns full list).
        Routes through ``warnings.warn`` so test sweeps can catch the
        usage via ``assertWarns(DeprecationWarning)``."""
        warnings.warn(
            "DriverSourceListEditor.node_name() is deprecated; "
            "use node_names() for multi-source",
            DeprecationWarning, stacklevel=2)
        sources = self.values()
        return sources[0].node if sources else ""

    def node_names(self):
        """Return the list of node names across all driver sources."""
        return [src.node for src in self.values()]

    def set_sources(self, sources):
        """Programmatic rebuild from list[DriverSource]. Suspends emit
        per the base contract — the controller is the originator."""
        self.set_values(list(sources))

    # --- M_QUICKWINS Item 2: retranslate hook ----------------------

    def retranslate(self):
        """M_QUICKWINS Item 2: re-apply current language to all
        i18n-bound surfaces. Called by main_window._retranslate_all
        on language switch so the editor's header / hint / action
        buttons / row tooltips refresh in-place rather than
        keeping the previous language frozen."""
        super(DriverSourceListEditor, self).retranslate()
        self.set_label(tr("driver_source_list_header"))
        self.set_empty_hint(tr("driver_source_list_empty_hint"))
        # Re-translate each row's tooltips. The row widgets are
        # composite QWidgets; we walk the QListWidget items + ask
        # each row to refresh its labels.
        for i in range(self._list.count()):
            widget = self._list.itemWidget(self._list.item(i))
            if isinstance(widget, _DriverSourceRow):
                widget.retranslate()


# Add a retranslate method on the row widget too so language switches
# refresh the per-row tooltips that DriverSourceListEditor.retranslate
# walks above.
def _row_retranslate(self):
    """M_QUICKWINS Item 2: row-level i18n refresh."""
    self._lbl_node.setToolTip(tr("driver_source_node_tip"))
    self._lbl_attrs.setToolTip(tr("driver_source_attrs_tip"))
    self._spin_weight.setToolTip(tr("driver_source_weight_tip"))
    self._combo_enc.setToolTip(tr("driver_source_encoding_tip"))


_DriverSourceRow.retranslate = _row_retranslate
