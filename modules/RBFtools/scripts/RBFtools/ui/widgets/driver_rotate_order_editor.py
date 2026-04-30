# -*- coding: utf-8 -*-
"""DriverRotateOrderEditor — driver-tab-synced rotate-order editor
(M_ROTORDER_UI_REFACTOR, 2026-04-29).

The legacy ``OrderedEnumListEditor`` exposed +/- / up / down buttons
that let the user manually grow / shrink / reorder the
``driverInputRotateOrder[]`` list independently of the actual
``driverSource[]`` count. That decoupling produced mismatched scenes
(e.g. 3 drivers vs 5 rotate-order rows) that silently mis-encoded
the C++ ``applyEncodingToBlock`` reads (RBFtools.cpp:2624).

Path B redesign (per planner ratification): driver tabs are the
single source of truth; the rotate-order list is a strict
projection of them. Rows can ONLY have their per-row enum combo
edited (xyz / yzx / zxy / xzy / yxz / zyx). Add / remove / reorder
controls are NOT exposed.

Public API (intentionally mirrors OrderedEnumListEditor where it
makes sense, so the rbf_section integration keeps the
``listChanged`` Qt signal contract):

  * ``set_driver_sources(names)`` — rebuild rows from the driver
    name list (length and ordering owned by the driver tabs).
    Existing per-row values are preserved by row index when the
    new length permits; new rows take the default (xyz=0).
  * ``set_values(values)`` — update existing combos in place;
    does NOT change row count. Values longer than the current
    row count are silently truncated; shorter pad with default.
  * ``get_values()`` — list of int, length == current row count.
  * ``listChanged(list)`` — emitted whenever any row combo changes.
  * ``setVisible`` / ``isVisible`` — inherited from QWidget; the
    rbf_section visibility logic (Raw / Quaternion hide vs
    BendRoll / ExpMap / SwingTwist show) drives the editor.
  * ``set_label`` / ``set_empty_hint`` / ``retranslate`` — present
    so rbf_section.retranslate cascade keeps working unchanged
    relative to the legacy widget API.

Each row is rendered as:

    ``QLabel("Driver {idx} ({driver.node})")  QComboBox(6 enum items)``

A QLabel "empty hint" is shown when the driver list is empty,
mirroring the legacy widget UX so the rbf_section's hint key
(``rotate_order_empty_hint``) remains a single source of truth.
"""

from __future__ import absolute_import

from RBFtools.ui.compat import QtCore, QtWidgets
from RBFtools.ui.i18n import tr
from RBFtools.constants import DRIVER_INPUT_ROTATE_ORDER_LABELS


class DriverRotateOrderEditor(QtWidgets.QWidget):
    """Read-only-row, driver-tab-synced rotate-order list."""

    listChanged = QtCore.Signal(list)

    def __init__(self, parent=None):
        super(DriverRotateOrderEditor, self).__init__(parent)
        # Row state: parallel lists kept in sync. self._rows[i] is the
        # combo for the i-th driver source; self._labels[i] is its
        # left-side QLabel. self._driver_names[i] is the driver.node
        # string used to render the label text.
        self._rows = []
        self._labels = []
        self._driver_names = []
        # Section title + empty-hint plumbing — matches the legacy
        # OrderedEnumListEditor surface so rbf_section's set_label /
        # set_empty_hint / retranslate calls keep working unchanged.
        self._label_text = ""
        self._empty_hint_text = ""
        # Build static layout. Rows are appended dynamically into
        # self._rows_layout; the title + empty hint sit above it.
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(2)
        self._lbl_title = QtWidgets.QLabel("")
        self._lbl_title.setVisible(False)
        outer.addWidget(self._lbl_title)
        self._lbl_empty = QtWidgets.QLabel("")
        self._lbl_empty.setStyleSheet(
            "color: gray; font-style: italic;")
        self._lbl_empty.setVisible(True)
        outer.addWidget(self._lbl_empty)
        self._rows_layout = QtWidgets.QVBoxLayout()
        self._rows_layout.setContentsMargins(0, 0, 0, 0)
        self._rows_layout.setSpacing(2)
        outer.addLayout(self._rows_layout)

    # ------------------------------------------------------------------
    # Public API — mirrors OrderedEnumListEditor where it makes sense.
    # ------------------------------------------------------------------

    def set_label(self, text):
        self._label_text = str(text or "")
        self._lbl_title.setText(self._label_text)
        self._lbl_title.setVisible(bool(self._label_text))

    def set_empty_hint(self, text):
        self._empty_hint_text = str(text or "")
        self._refresh_empty_hint()

    def set_driver_sources(self, names):
        """Rebuild rows from *names*. Existing per-row values are
        preserved by row index when the new length permits; rows
        beyond the new length are dropped, new rows added at the
        tail use the default (xyz=0).

        ``names`` is a list of driver-node strings (sourced from
        ``DriverSource.node``). The row label is computed as
        ``tr("driver_rotate_order_row_label").format(idx=i+1, name=...)``
        so the user sees ``"Driver 1 (joint_arm_L)"`` per row.
        """
        names = [str(n or "") for n in (names or [])]
        # Capture existing values so we can carry them forward.
        existing = self.get_values()
        # Tear down current rows.
        for combo in self._rows:
            combo.blockSignals(True)
            combo.deleteLater()
        for lbl in self._labels:
            lbl.deleteLater()
        self._rows = []
        self._labels = []
        self._driver_names = list(names)
        # Build new rows.
        for idx, drv_name in enumerate(names):
            row = QtWidgets.QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(4)
            lbl = QtWidgets.QLabel(self._format_row_label(idx, drv_name))
            row.addWidget(lbl)
            combo = QtWidgets.QComboBox()
            for label in DRIVER_INPUT_ROTATE_ORDER_LABELS:
                combo.addItem(label)
            # Carry existing value forward when possible.
            value = existing[idx] if idx < len(existing) else 0
            try:
                value = int(value)
            except (TypeError, ValueError):
                value = 0
            if 0 <= value < combo.count():
                combo.setCurrentIndex(value)
            else:
                combo.setCurrentIndex(0)
            combo.currentIndexChanged.connect(
                self._on_any_row_changed)
            row.addWidget(combo, 1)
            container = QtWidgets.QWidget()
            container.setLayout(row)
            # Track widgets for teardown / retranslate.
            self._labels.append(lbl)
            self._rows.append(combo)
            self._rows_layout.addWidget(container)
        self._refresh_empty_hint()

    def set_values(self, values):
        """Update existing combos in place. Does NOT change row count
        (driver tabs are the source of truth for that). Values longer
        than the current row count are silently truncated; shorter
        pad with the default (xyz=0)."""
        values = list(values or [])
        for i, combo in enumerate(self._rows):
            combo.blockSignals(True)
            try:
                value = int(values[i]) if i < len(values) else 0
            except (TypeError, ValueError):
                value = 0
            if 0 <= value < combo.count():
                combo.setCurrentIndex(value)
            else:
                combo.setCurrentIndex(0)
            combo.blockSignals(False)

    def get_values(self):
        return [int(c.currentIndex()) for c in self._rows]

    def driver_names(self):
        """Return the current driver-name list as last set by
        :meth:`set_driver_sources`. Test-friendly accessor."""
        return list(self._driver_names)

    def row_count(self):
        return len(self._rows)

    def retranslate(self):
        """Re-render row labels (driver name + idx template) on
        language switch. Title text is also refreshed because
        rbf_section calls set_label(tr(...)) directly during its
        own retranslate cycle — that path keeps working too."""
        for idx, lbl in enumerate(self._labels):
            drv_name = (
                self._driver_names[idx]
                if idx < len(self._driver_names) else "")
            lbl.setText(self._format_row_label(idx, drv_name))
        self._refresh_empty_hint()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _format_row_label(self, idx, name):
        """Render the per-row label using the i18n template. Falls
        back to a plain ``"Driver N (name)"`` shape if the template
        key is unavailable for any reason."""
        template = tr("driver_rotate_order_row_label")
        try:
            return template.format(idx=idx + 1, name=name)
        except (KeyError, IndexError, AttributeError):
            return "Driver {} ({})".format(idx + 1, name)

    def _refresh_empty_hint(self):
        empty = not self._rows
        self._lbl_empty.setText(self._empty_hint_text if empty else "")
        self._lbl_empty.setVisible(empty)

    def _on_any_row_changed(self, _idx):
        self.listChanged.emit(self.get_values())
