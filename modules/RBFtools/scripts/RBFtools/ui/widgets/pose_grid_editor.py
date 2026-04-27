# -*- coding: utf-8 -*-
"""PoseGridEditor — multi-source-aware Pose tab grid (Phase 2 of the
2026-04-27 user audit).

Replaces the legacy QTableView (PoseTableModel) inside the Pose
outer tab with a dynamic grid that mirrors the AnimaRbfSolver
reference layout:

  | Pose # | Driver headers (per source: node + attr) | Go to Pose |
  | Pose # | Driver value spinboxes per attr          | [Btn]      |
                                                      |
  ... separator ...
                                                      |
  | Driven headers (per source: node + attr) | radius (future)
  | Driven value spinboxes per attr           |

Single-source nodes degrade gracefully (one column group on each
side). Multi-source nodes get one column group per source on each
side. Live edits to a spinbox emit ``poseValueChanged`` so the
controller can write the new value back to the node + the pose
data model.

MVC red line preserved: this widget never imports cmds. It receives
already-resolved DriverSource / DrivenSource / PoseData instances
via :py:meth:`set_data` and emits intent signals up to main_window.
"""

from __future__ import absolute_import

from RBFtools.ui.compat import QtCore, QtWidgets
from RBFtools.ui.i18n import tr


# ----------------------------------------------------------------------
# PoseGridEditor
# ----------------------------------------------------------------------


class PoseGridEditor(QtWidgets.QWidget):
    """Multi-source-aware pose grid editor.

    Columns are rebuilt every time :py:meth:`set_data` is called -
    typically on controller editorLoaded / driverSourcesChanged /
    drivenSourcesChanged signal cascades. The widget never queries
    Maya directly; main_window resolves the DriverSource /
    DrivenSource / PoseData payload and pushes it in.
    """

    # Per-row Go to Pose button -> recall this pose.
    poseRecallRequested  = QtCore.Signal(int)
    # Per-row delete affordance (right-click menu).
    poseDeleteRequested  = QtCore.Signal(int)
    # A spinbox changed - payload (pose_index, side, flat_attr_idx, new_value).
    # side is "input" (driver) or "value" (driven).
    poseValueChanged     = QtCore.Signal(int, str, int, float)
    # Bottom Add Pose button.
    addPoseRequested     = QtCore.Signal()
    # Bottom Delete Poses button (clear all).
    deleteAllPosesRequested = QtCore.Signal()

    def __init__(self, parent=None):
        super(PoseGridEditor, self).__init__(parent)
        self._driver_sources = []
        self._driven_sources = []
        self._poses          = []
        # Per-row tracking lists so spinbox edits can resolve back to
        # (pose_index, side, flat_attr_idx).
        self._row_widgets    = []   # list[dict] keyed by row data
        self._build()

    # ------------------------------------------------------------------
    # Build (one-shot)
    # ------------------------------------------------------------------

    def _build(self):
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)

        # Empty hint shown when there are no driver/driven sources or
        # no poses yet.
        self._lbl_empty_hint = QtWidgets.QLabel(
            tr("pose_grid_empty_hint"))
        self._lbl_empty_hint.setStyleSheet(
            "color: gray; font-style: italic;")
        self._lbl_empty_hint.setWordWrap(True)
        self._lbl_empty_hint.setVisible(True)
        lay.addWidget(self._lbl_empty_hint)

        # Scroll area containing the dynamic grid.
        self._scroll = QtWidgets.QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        self._grid_widget = QtWidgets.QWidget()
        self._grid = QtWidgets.QGridLayout(self._grid_widget)
        self._grid.setContentsMargins(4, 4, 4, 4)
        self._grid.setHorizontalSpacing(4)
        self._grid.setVerticalSpacing(4)
        self._scroll.setWidget(self._grid_widget)
        lay.addWidget(self._scroll, 1)

        # Bottom action row: Add Pose + Delete Poses.
        btn_row = QtWidgets.QHBoxLayout()
        self._btn_add = QtWidgets.QPushButton(tr("add_pose"))
        self._btn_add.setToolTip(tr("pose_grid_add_pose_tip"))
        self._btn_add.clicked.connect(self.addPoseRequested)
        self._btn_delete_all = QtWidgets.QPushButton(
            tr("delete_poses"))
        self._btn_delete_all.setToolTip(
            tr("pose_grid_delete_all_tip"))
        self._btn_delete_all.clicked.connect(
            self.deleteAllPosesRequested)
        btn_row.addWidget(self._btn_add)
        btn_row.addWidget(self._btn_delete_all)
        lay.addLayout(btn_row)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_data(self, driver_sources, driven_sources, poses):
        """Rebuild the grid from the supplied sources + poses.

        Called by main_window after each
        controller.driverSourcesChanged / drivenSourcesChanged /
        editorLoaded signal cascade."""
        self._driver_sources = list(driver_sources or [])
        self._driven_sources = list(driven_sources or [])
        self._poses = list(poses or [])
        self._rebuild()

    def retranslate(self):
        self._lbl_empty_hint.setText(tr("pose_grid_empty_hint"))
        self._btn_add.setText(tr("add_pose"))
        self._btn_add.setToolTip(tr("pose_grid_add_pose_tip"))
        self._btn_delete_all.setText(tr("delete_poses"))
        self._btn_delete_all.setToolTip(tr("pose_grid_delete_all_tip"))

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _clear_grid(self):
        while self._grid.count() > 0:
            item = self._grid.takeAt(0)
            w = item.widget() if item is not None else None
            if w is not None:
                w.deleteLater()
        self._row_widgets = []

    def _rebuild(self):
        self._clear_grid()
        # Show empty hint when there are no sources at all.
        no_sources = (
            not self._driver_sources and not self._driven_sources)
        self._lbl_empty_hint.setVisible(
            no_sources or not self._poses)
        self._scroll.setVisible(not (no_sources and not self._poses))
        if no_sources and not self._poses:
            return
        self._build_header_rows()
        self._build_pose_rows()

    # ----- Column index plan -----------------------------------------
    # Col 0: pose label
    # Col 1..n_drv: driver value spinboxes (1 column per attr, attrs
    #               grouped by driver source)
    # Col n_drv+1: Go to Pose button
    # Col n_drv+2: vertical divider
    # Col n_drv+3..end: driven value spinboxes (1 column per attr)

    def _driver_attr_total(self):
        return sum(len(s.attrs) for s in self._driver_sources)

    def _driven_attr_total(self):
        return sum(len(s.attrs) for s in self._driven_sources)

    def _col_pose_label(self):
        return 0

    def _col_driver_start(self):
        return 1

    def _col_driver_end(self):
        return self._col_driver_start() + self._driver_attr_total()

    def _col_go_button(self):
        return self._col_driver_end()

    def _col_divider(self):
        return self._col_go_button() + 1

    def _col_driven_start(self):
        return self._col_divider() + 1

    def _col_driven_end(self):
        return self._col_driven_start() + self._driven_attr_total()

    # ----- Header rows -----------------------------------------------

    def _build_header_rows(self):
        # Row 0: source-name headers (each spans the source's attr count)
        # Row 1: per-attr name headers
        col = self._col_driver_start()
        for src in self._driver_sources:
            n = max(1, len(src.attrs))
            lbl_node = QtWidgets.QLabel(src.node or "<unset>")
            lbl_node.setStyleSheet(
                "color: #b03a48; font-weight: bold;"
                "padding: 2px 4px;"
                "border: 1px solid #b03a48;"
                "border-radius: 3px;")
            lbl_node.setAlignment(QtCore.Qt.AlignLeft)
            self._grid.addWidget(lbl_node, 0, col, 1, n)
            for i, attr in enumerate(src.attrs):
                lbl_attr = QtWidgets.QLabel(attr)
                lbl_attr.setStyleSheet(
                    "color: #b03a48; padding: 1px 4px;")
                self._grid.addWidget(lbl_attr, 1, col + i)
            col += n
        # Driven side headers.
        col = self._col_driven_start()
        for src in self._driven_sources:
            n = max(1, len(src.attrs))
            lbl_node = QtWidgets.QLabel(src.node or "<unset>")
            lbl_node.setStyleSheet(
                "color: #3a7a8c; font-weight: bold;"
                "padding: 2px 4px;"
                "border: 1px solid #3a7a8c;"
                "border-radius: 3px;")
            lbl_node.setAlignment(QtCore.Qt.AlignLeft)
            self._grid.addWidget(lbl_node, 0, col, 1, n)
            for i, attr in enumerate(src.attrs):
                lbl_attr = QtWidgets.QLabel(attr)
                lbl_attr.setStyleSheet(
                    "color: #3a7a8c; padding: 1px 4px;")
                self._grid.addWidget(lbl_attr, 1, col + i)
            col += n

    # ----- Pose rows -------------------------------------------------

    def _build_pose_rows(self):
        for i, pose in enumerate(self._poses):
            row = i + 2   # +2 for the two header rows
            # Pose label.
            lbl_pose = QtWidgets.QLabel(
                tr("pose_grid_row_label").format(idx=i))
            lbl_pose.setStyleSheet(
                "padding: 2px 4px; min-width: 60px;")
            self._grid.addWidget(
                lbl_pose, row, self._col_pose_label())
            # Driver value spinboxes.
            inputs = list(getattr(pose, "inputs", []) or [])
            col = self._col_driver_start()
            n_drv = self._driver_attr_total()
            for j in range(n_drv):
                val = inputs[j] if j < len(inputs) else 0.0
                sb = self._make_spinbox(val)
                sb.valueChanged.connect(
                    lambda v, _i=i, _j=j:
                        self.poseValueChanged.emit(
                            _i, "input", _j, float(v)))
                self._grid.addWidget(sb, row, col + j)
            # Go to Pose button.
            btn_go = QtWidgets.QPushButton(tr("pose_grid_go_to_pose"))
            btn_go.setToolTip(tr("pose_grid_go_to_pose_tip"))
            btn_go.clicked.connect(
                lambda _checked=False, _i=i:
                    self.poseRecallRequested.emit(_i))
            self._grid.addWidget(btn_go, row, self._col_go_button())
            # Vertical divider.
            divider = QtWidgets.QFrame()
            divider.setFrameShape(QtWidgets.QFrame.VLine)
            divider.setFrameShadow(QtWidgets.QFrame.Sunken)
            self._grid.addWidget(divider, row, self._col_divider())
            # Driven value spinboxes.
            values = list(getattr(pose, "values", []) or [])
            col = self._col_driven_start()
            n_dvn = self._driven_attr_total()
            for j in range(n_dvn):
                val = values[j] if j < len(values) else 0.0
                sb = self._make_spinbox(val)
                sb.valueChanged.connect(
                    lambda v, _i=i, _j=j:
                        self.poseValueChanged.emit(
                            _i, "value", _j, float(v)))
                self._grid.addWidget(sb, row, col + j)
            # Right-click context menu on the pose label for delete.
            lbl_pose.setContextMenuPolicy(
                QtCore.Qt.CustomContextMenu)
            lbl_pose.customContextMenuRequested.connect(
                lambda _pos, _i=i:
                    self._show_row_menu(_i))

    @staticmethod
    def _make_spinbox(initial):
        sb = QtWidgets.QDoubleSpinBox()
        sb.setRange(-1e9, 1e9)
        sb.setDecimals(3)
        sb.setMinimumWidth(70)
        try:
            sb.setValue(float(initial))
        except (TypeError, ValueError):
            sb.setValue(0.0)
        return sb

    def _show_row_menu(self, pose_index):
        menu = QtWidgets.QMenu(self)
        act_recall = menu.addAction(tr("recall"))
        act_delete = menu.addAction(tr("delete"))
        chosen = menu.exec_(QtCore.QCursor.pos()
                            if hasattr(QtCore, "QCursor")
                            else None)
        if chosen is act_recall:
            self.poseRecallRequested.emit(pose_index)
        elif chosen is act_delete:
            self.poseDeleteRequested.emit(pose_index)
