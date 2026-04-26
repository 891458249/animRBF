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

    Read-only "node" / "attrs" mirror — the rich editing happens via
    controller path A (Hardening C.2), not in-row. The row exposes
    plain Q widgets that reflect the current DriverSource dataclass."""

    rowChanged = QtCore.Signal()

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

        # Attrs joined preview (read-only).
        attrs_text = ", ".join(self._source.attrs) if self._source.attrs else ""
        self._lbl_attrs = QtWidgets.QLabel(attrs_text)
        self._lbl_attrs.setMinimumWidth(160)
        self._lbl_attrs.setToolTip(tr("driver_source_attrs_tip"))
        lay.addWidget(self._lbl_attrs, 2)

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
    pose_editor.py / controller.py keep working unchanged."""

    def __init__(self, parent=None):
        super(DriverSourceListEditor, self).__init__(parent)
        self.set_label(tr("driver_source_list_header"))
        self.set_empty_hint(tr("driver_source_list_empty_hint"))

    # --- _OrderedListEditorBase virtuals -------------------------------

    def _create_row_widget(self, initial_value):
        row = _DriverSourceRow(initial_value)
        row.rowChanged.connect(self._on_any_row_changed)
        return row

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
