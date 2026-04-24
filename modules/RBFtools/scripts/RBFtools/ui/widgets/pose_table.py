# -*- coding: utf-8 -*-
"""
Pose table — QTableWidget that displays RBF poses.

Each row = one pose with input columns, output columns and action buttons.
Signals only — no scene access.
"""

from __future__ import absolute_import

from RBFtools.ui.compat import QtWidgets, QtCore
from RBFtools.ui.i18n import tr


class PoseTable(QtWidgets.QWidget):
    """Scrollable pose grid with Recall / Update / Delete per row."""

    recallPose = QtCore.Signal(int)       # pose index
    updatePose = QtCore.Signal(int)       # pose index
    deletePose = QtCore.Signal(int)       # pose index

    def __init__(self, parent=None):
        super(PoseTable, self).__init__(parent)
        self._n_inputs = 0
        self._n_outputs = 0
        self._build()

    def _build(self):
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)

        self._lbl = QtWidgets.QLabel(tr("poses"))
        self._lbl.setStyleSheet("font-weight: bold;")
        lay.addWidget(self._lbl)

        self._table = QtWidgets.QTableWidget()
        self._table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectRows)
        self._table.setSelectionMode(
            QtWidgets.QAbstractItemView.SingleSelection)
        self._table.verticalHeader().setVisible(False)
        self._table.setAlternatingRowColors(True)
        lay.addWidget(self._table, 1)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def clear(self):
        self._table.setRowCount(0)
        self._table.setColumnCount(0)
        self._n_inputs = 0
        self._n_outputs = 0

    def setup_columns(self, input_names, output_names):
        """Configure column headers from driver/driven attribute names."""
        self._n_inputs = len(input_names)
        self._n_outputs = len(output_names)
        cols = ["Pose"] + list(input_names) + list(output_names) + ["", "", ""]
        self._table.setColumnCount(len(cols))
        self._table.setHorizontalHeaderLabels(cols)
        # Stretch data columns
        header = self._table.horizontalHeader()
        header.setStretchLastSection(False)
        for i in range(1, 1 + self._n_inputs + self._n_outputs):
            header.setSectionResizeMode(
                i, QtWidgets.QHeaderView.Stretch)
        # Fixed width for button columns
        for i in range(len(cols) - 3, len(cols)):
            self._table.setColumnWidth(i, 60)

    def add_pose(self, index, inputs, outputs):
        """Append one pose row."""
        row = self._table.rowCount()
        self._table.insertRow(row)

        # Pose label
        label_item = QtWidgets.QTableWidgetItem("Pose {}".format(index))
        label_item.setFlags(label_item.flags() & ~QtCore.Qt.ItemIsEditable)
        label_item.setData(QtCore.Qt.UserRole, index)
        self._table.setItem(row, 0, label_item)

        col = 1
        for v in inputs:
            item = QtWidgets.QTableWidgetItem("{:.3f}".format(v))
            self._table.setItem(row, col, item)
            col += 1
        for v in outputs:
            item = QtWidgets.QTableWidgetItem("{:.3f}".format(v))
            self._table.setItem(row, col, item)
            col += 1

        # Action buttons
        self._add_btn(row, col, tr("recall"), self.recallPose, index)
        self._add_btn(row, col + 1, tr("update"), self.updatePose, index)
        self._add_btn(row, col + 2, tr("delete"), self.deletePose, index)

    def set_row_values(self, row, inputs, outputs):
        """Update an existing row's numeric values."""
        col = 1
        for v in inputs:
            item = self._table.item(row, col)
            if item:
                item.setText("{:.3f}".format(v))
            col += 1
        for v in outputs:
            item = self._table.item(row, col)
            if item:
                item.setText("{:.3f}".format(v))
            col += 1

    def remove_row(self, row):
        self._table.removeRow(row)

    def row_count(self):
        return self._table.rowCount()

    def pose_index_at(self, row):
        """Return the pose index stored in column 0."""
        item = self._table.item(row, 0)
        if item:
            return item.data(QtCore.Qt.UserRole)
        return -1

    def find_row_by_pose_index(self, pose_idx):
        for r in range(self._table.rowCount()):
            if self.pose_index_at(r) == pose_idx:
                return r
        return -1

    def all_pose_indices(self):
        return [self.pose_index_at(r) for r in range(self._table.rowCount())]

    def next_pose_index(self):
        indices = self.all_pose_indices()
        return (max(indices) + 1) if indices else 0

    def read_row_data(self, row):
        """Return ``(inputs, outputs)`` floats for a given row."""
        inputs = []
        for c in range(1, 1 + self._n_inputs):
            item = self._table.item(row, c)
            try:
                inputs.append(float(item.text()))
            except (ValueError, AttributeError):
                inputs.append(0.0)
        outputs = []
        for c in range(1 + self._n_inputs, 1 + self._n_inputs + self._n_outputs):
            item = self._table.item(row, c)
            try:
                outputs.append(float(item.text()))
            except (ValueError, AttributeError):
                outputs.append(0.0)
        return inputs, outputs

    def retranslate(self):
        self._lbl.setText(tr("poses"))

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _add_btn(self, row, col, text, signal, pose_idx):
        btn = QtWidgets.QPushButton(text)
        btn.setFixedHeight(22)
        btn.clicked.connect(lambda: signal.emit(pose_idx))
        self._table.setCellWidget(row, col, btn)
