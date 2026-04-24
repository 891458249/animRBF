# -*- coding: utf-8 -*-
"""
PoseTableModel — Qt Model/View data layer for the RBF pose grid.

This module implements ``QAbstractTableModel`` so the pose table can
use Qt's Model/View architecture instead of manual QTableWidget
manipulation.  Benefits:

* **Single source of truth** — the ``PoseData`` list lives here, not
  scattered across QTableWidgetItem texts.
* **Automatic UI refresh** — ``beginInsertRows`` / ``endInsertRows``
  (and their remove/reset counterparts) tell all attached views to
  update themselves.  No manual row-by-row UI sync.
* **Undo-friendly** — the controller can snapshot the model, call
  ``core.apply_poses``, and roll back without touching the view.

Zero ``maya.cmds`` — this file only imports Qt via :mod:`compat`.
"""

from __future__ import absolute_import

from RBFtools.ui.compat import QtCore
from RBFtools.core import PoseData, float_eq


# =====================================================================
#  Column layout enum
# =====================================================================
#
#  | 0      | 1 .. N_in | N_in+1 .. N_in+N_out |
#  | Pose # | driver_0  | driven_0             |
#
#  Column 0 is read-only (pose label).
#  Columns 1+ are editable float cells.
# =====================================================================

_POSE_LABEL_COL = 0


class PoseTableModel(QtCore.QAbstractTableModel):
    """Tabular model backed by a ``list[PoseData]``.

    Parameters
    ----------
    parent : QObject or None
        Owning QObject (usually the controller).

    After construction the model is empty.  Call :meth:`setup_columns`
    before inserting any data.
    """

    def __init__(self, parent=None):
        super(PoseTableModel, self).__init__(parent)

        self._poses = []               # list[PoseData]
        self._driver_headers = []      # list[str]  — driver attr names
        self._driven_headers = []      # list[str]  — driven attr names

    # =================================================================
    #  Column configuration
    # =================================================================

    def setup_columns(self, driver_attrs, driven_attrs):
        """Define the column layout.

        Must be called before any data insertion.  Resets the model
        if it already contained data.

        Parameters
        ----------
        driver_attrs : list[str]
            Ordered driver attribute names  (become column headers).
        driven_attrs : list[str]
            Ordered driven attribute names.
        """
        self.beginResetModel()
        self._poses = []
        self._driver_headers = list(driver_attrs)
        self._driven_headers = list(driven_attrs)
        self.endResetModel()

    @property
    def n_inputs(self):
        """Number of driver (input) columns."""
        return len(self._driver_headers)

    @property
    def n_outputs(self):
        """Number of driven (output) columns."""
        return len(self._driven_headers)

    # =================================================================
    #  QAbstractTableModel — required overrides
    # =================================================================

    def rowCount(self, parent=QtCore.QModelIndex()):
        """Number of poses."""
        if parent.isValid():
            return 0                    # flat table, no tree children
        return len(self._poses)

    def columnCount(self, parent=QtCore.QModelIndex()):
        """1 (label) + n_inputs + n_outputs."""
        if parent.isValid():
            return 0
        return 1 + self.n_inputs + self.n_outputs

    def data(self, index, role=QtCore.Qt.DisplayRole):
        """Return cell data for the given *index* and *role*.

        Column mapping
        --------------
        * Col 0            → ``"Pose <index>"``  (read-only label)
        * Col 1 .. N_in    → ``pose.inputs[col-1]`` as ``"{:.4f}"``
        * Col N_in+1 .. end→ ``pose.values[col-1-N_in]`` as ``"{:.4f}"``

        ``Qt.UserRole`` on col 0 stores the ``pose.index`` integer.
        """
        if not index.isValid():
            return None

        row = index.row()
        col = index.column()
        if row < 0 or row >= len(self._poses):
            return None

        pose = self._poses[row]

        # -- Display / Edit role --
        if role in (QtCore.Qt.DisplayRole, QtCore.Qt.EditRole):
            if col == _POSE_LABEL_COL:
                return "Pose {}".format(pose.index)
            data_col = col - 1
            if data_col < self.n_inputs:
                return "{:.4f}".format(pose.inputs[data_col])
            out_col = data_col - self.n_inputs
            if out_col < self.n_outputs:
                return "{:.4f}".format(pose.values[out_col])

        # -- UserRole on label column → pose index (int) --
        if role == QtCore.Qt.UserRole and col == _POSE_LABEL_COL:
            return pose.index

        # -- TextAlignment: right-align numeric columns --
        if role == QtCore.Qt.TextAlignmentRole and col > _POSE_LABEL_COL:
            return int(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)

        return None

    def setData(self, index, value, role=QtCore.Qt.EditRole):
        """Allow in-place editing of numeric cells.

        The user can double-click a cell in the pose table and type
        a new float value.  This updates the underlying ``PoseData``
        and emits ``dataChanged`` so all views refresh.
        """
        if role != QtCore.Qt.EditRole or not index.isValid():
            return False

        row = index.row()
        col = index.column()
        if col == _POSE_LABEL_COL:
            return False                # label column is read-only

        try:
            fval = float(value)
        except (ValueError, TypeError):
            return False

        pose = self._poses[row]
        data_col = col - 1
        if data_col < self.n_inputs:
            pose.inputs[data_col] = fval
        else:
            out_col = data_col - self.n_inputs
            if out_col < self.n_outputs:
                pose.values[out_col] = fval
            else:
                return False

        self.dataChanged.emit(index, index, [role])
        return True

    def flags(self, index):
        """Column 0 is read-only; all others are editable."""
        base = super(PoseTableModel, self).flags(index)
        if index.column() == _POSE_LABEL_COL:
            return base & ~QtCore.Qt.ItemIsEditable
        return base | QtCore.Qt.ItemIsEditable

    def headerData(self, section, orientation, role=QtCore.Qt.DisplayRole):
        """Horizontal headers: 'Pose', then driver attrs, then driven attrs."""
        if role != QtCore.Qt.DisplayRole:
            return None
        if orientation == QtCore.Qt.Horizontal:
            if section == _POSE_LABEL_COL:
                return "Pose"
            data_col = section - 1
            if data_col < self.n_inputs:
                return self._driver_headers[data_col]
            out_col = data_col - self.n_inputs
            if out_col < self.n_outputs:
                return self._driven_headers[out_col]
        elif orientation == QtCore.Qt.Vertical:
            return str(section)
        return None

    # =================================================================
    #  CRUD — public API for the controller
    # =================================================================

    def add_pose(self, pose):
        """Append one :class:`PoseData` and notify attached views.

        Parameters
        ----------
        pose : PoseData

        Raises
        ------
        ValueError
            If ``pose.inputs`` / ``pose.values`` dimensions do not
            match the configured column counts.
        """
        if self.n_inputs and len(pose.inputs) != self.n_inputs:
            raise ValueError(
                "Input dimension mismatch: expected {}, got {}".format(
                    self.n_inputs, len(pose.inputs)))
        if self.n_outputs and len(pose.values) != self.n_outputs:
            raise ValueError(
                "Output dimension mismatch: expected {}, got {}".format(
                    self.n_outputs, len(pose.values)))

        row = len(self._poses)
        self.beginInsertRows(QtCore.QModelIndex(), row, row)
        self._poses.append(pose)
        self.endInsertRows()

    def remove_pose(self, row):
        """Remove the pose at *row* and notify attached views.

        Parameters
        ----------
        row : int
            Row index (0-based).  Out-of-range is silently ignored.
        """
        if row < 0 or row >= len(self._poses):
            return
        self.beginRemoveRows(QtCore.QModelIndex(), row, row)
        del self._poses[row]
        self.endRemoveRows()

    def update_pose_values(self, row, inputs, outputs):
        """Replace the numeric data of an existing pose at *row*.

        Emits ``dataChanged`` for the affected columns only.

        Parameters
        ----------
        row : int
        inputs : list[float]
        outputs : list[float]
        """
        if row < 0 or row >= len(self._poses):
            return
        pose = self._poses[row]
        pose.inputs = list(inputs)
        pose.values = list(outputs)

        left  = self.index(row, 1)
        right = self.index(row, self.columnCount() - 1)
        self.dataChanged.emit(left, right, [QtCore.Qt.DisplayRole])

    def clear(self):
        """Remove all poses and reset column headers."""
        self.beginResetModel()
        self._poses = []
        self._driver_headers = []
        self._driven_headers = []
        self.endResetModel()

    # =================================================================
    #  Query helpers
    # =================================================================

    def get_pose(self, row):
        """Return the :class:`PoseData` at *row*, or ``None``."""
        if 0 <= row < len(self._poses):
            return self._poses[row]
        return None

    def all_poses(self):
        """Return a **shallow copy** of the internal pose list.

        The controller passes this to ``core.apply_poses``.
        """
        return list(self._poses)

    def pose_index_at(self, row):
        """Return the ``PoseData.index`` at *row*, or -1."""
        if 0 <= row < len(self._poses):
            return self._poses[row].index
        return -1

    def find_row_by_pose_index(self, pose_idx):
        """Reverse-lookup: pose index → model row.  Returns -1 if absent."""
        for r, p in enumerate(self._poses):
            if p.index == pose_idx:
                return r
        return -1

    def next_pose_index(self):
        """Return the next available pose index (max + 1, or 0)."""
        if not self._poses:
            return 0
        return max(p.index for p in self._poses) + 1

    def has_rest_pose(self):
        """True if pose index 0 exists and its outputs are all zero.

        The C++ solver treats pose 0 as the "rest" (neutral) state.
        BlendShape auto-fill logic depends on this check.
        """
        row = self.find_row_by_pose_index(0)
        if row < 0:
            return False
        pose = self._poses[row]
        return all(float_eq(v, 0.0) for v in pose.values)
