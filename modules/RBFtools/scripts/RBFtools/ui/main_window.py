# -*- coding: utf-8 -*-
"""
Main window — final assembly of all widgets, controller binding and
signal wiring.

Architecture
------------
::

    ┌─────────────────────────────────────────────────────────────┐
    │  RBFToolsWindow (QMainWindow)                               │
    │  ┌──────────────────────────────────────────────────────┐   │
    │  │ NodeSelector                                          │   │
    │  └──────────────────────────────────────────────────────┘   │
    │  ┌──────────────────────────────────────────────────────┐   │
    │  │ QScrollArea                                           │   │
    │  │  ┌─ GeneralSection ─────────────────────────────────┐ │   │
    │  │  ├─ VectorAngleSection ─────────────────────────────┤ │   │
    │  │  ├─ RBFSection ─────────────────────────────────────┤ │   │
    │  │  ├─ PoseEditorPanel ────────────────────────────────┤ │   │
    │  │  │   ├─ AttributeList (driver) │ AttributeList (driven) │ │
    │  │  │   ├─ QTableView + PoseDelegate                   │ │   │
    │  │  │   └─ [Add] [Apply] [Connect] [Reload]           │ │   │
    │  │  └──────────────────────────────────────────────────┘ │   │
    │  └──────────────────────────────────────────────────────┘   │
    │  ┌──────────────────────────────────────────────────────┐   │
    │  │ StatusBar:  QProgressBar + QLabel                     │   │
    │  └──────────────────────────────────────────────────────┘   │
    └─────────────────────────────────────────────────────────────┘

**The view never calls ``maya.cmds`` for scene mutation.**
All scene interaction is routed through :class:`MainController`.
"""

from __future__ import absolute_import

import maya.cmds as cmds
import maya.utils as mutils

from RBFtools.ui.compat import QtWidgets, QtCore, QtGui, maya_main_window
from RBFtools.ui.style import STYLESHEET
from RBFtools.ui.i18n import tr, current_language, set_language
from RBFtools.ui.pose_delegate import PoseDelegate
from RBFtools.constants import WINDOW_OBJECT, WINDOW_TITLE, WINDOW_WIDTH, WINDOW_HEIGHT

from RBFtools.controller import MainController
from RBFtools.ui.widgets.node_selector import NodeSelector
from RBFtools.ui.widgets.driver_source_list_editor import (
    DriverSourceListEditor,
)
# M_TABBED_EDITOR (2026-04-27): tabbed Driver/Driven editor matching
# the Tekken-8 AnimaRbfSolver paradigm. Replaces the M_B24b1 /
# M_DRIVEN_MULTI list-row editors in the inspector layout (the legacy
# widget classes remain importable for backcompat / tests).
from RBFtools.ui.widgets.tabbed_source_editor import (
    TabbedDriverSourceEditor,
    TabbedDrivenSourceEditor,
)
from RBFtools.ui.widgets.general_section import GeneralSection
from RBFtools.ui.widgets.output_encoding_combo import OutputEncodingCombo
from RBFtools.ui.widgets.vector_angle_section import VectorAngleSection
from RBFtools.ui.widgets.rbf_section import RBFSection
from RBFtools.ui.widgets.collapsible import CollapsibleFrame
from RBFtools.ui.widgets.attribute_list import AttributeList
from RBFtools.ui.widgets.help_button import HelpButton, ComboHelpButton


# =====================================================================
#  Pose editor panel (internal composite widget)
# =====================================================================

class _PoseEditorPanel(CollapsibleFrame):
    """Composes the driver/driven attribute lists, the QTableView and
    the action buttons into a single collapsible section.

    All user interactions are forwarded as signals — the main window
    wires them to the controller.
    """

    selectNodeRequested  = QtCore.Signal(str)           # role
    filtersChanged       = QtCore.Signal(str, dict)     # role, filters
    addPoseRequested     = QtCore.Signal()
    applyRequested       = QtCore.Signal()
    connectRequested     = QtCore.Signal()
    disconnectRequested  = QtCore.Signal()
    reloadRequested      = QtCore.Signal()
    autoFillChanged      = QtCore.Signal(bool)
    # Phase 2 PoseGridEditor signals re-emitted at the panel level.
    # Commit 3 (C2): poseValueChanged was replaced by the semantic
    # poseValueChangedV2 form carrying source_idx + attr_name (no
    # more flat_attr_idx). poseRadiusChanged + BasePose triplet
    # added for the M_PER_POSE_SIGMA + M_BASE_POSE wires.
    poseRecallRequested      = QtCore.Signal(int)
    # M_P0_UPDATE_BUTTON_REVERSED (2026-04-30): per-row Update button
    # forwards through the panel as a distinct channel — pre-fix
    # the click was misrouted through poseRecallRequested.
    poseUpdateRequested      = QtCore.Signal(int)
    poseDeleteRequested      = QtCore.Signal(int)
    poseDeleteAllRequested   = QtCore.Signal()
    poseValueChangedV2       = QtCore.Signal(int, str, int, str, float)
    poseRadiusChanged        = QtCore.Signal(int, float)
    baseValueChangedV2       = QtCore.Signal(int, str, int, str, float)
    basePoseRecallRequested  = QtCore.Signal()

    def __init__(self, parent=None):
        super(_PoseEditorPanel, self).__init__(
            title=tr("rbf_pose_editor"), parent=parent)
        # M3.0-spillover: M3.x sub-tasks register pose-row actions
        # via add_pose_row_action; populated tuples are
        # (label_key, callback, danger_bool). _show_row_menu reads
        # this list every right-click so additions take effect
        # immediately without a window rebuild.
        self._extra_row_actions = []
        self._build()

    def _build(self):
        lay = self.content_layout()

        # M_TABBED_EDITOR_REWRITE (user strict spec 2026-04-27):
        # Outermost element is a QTabWidget. The active tab is
        # "DriverDriven" containing two QGroupBox-wrapped panels
        # (Driver / Driven side-by-side). The second tab "Pose"
        # hosts the auto-fill toggle + per-driven scale flags +
        # the pose table + the Add/Apply/Connect/Disconnect/Reload
        # action buttons.
        self._outer_tabs = QtWidgets.QTabWidget()
        # M_HELPBUBBLE_BATCH: top-right corner HelpButton describing
        # the three outer tabs together (DriverDriven / BaseDrivenPose
        # / Pose). One bubble covers the navigation overview; the
        # per-button HelpButtons inside each tab cover the widgets.
        self._outer_tabs.setCornerWidget(
            HelpButton("outer_tabs_overview"),
            QtCore.Qt.TopRightCorner)
        lay.addWidget(self._outer_tabs, 1)

        # ---- Tab 1: DriverDriven ---------------------------------
        # Commit 2b (M_UI_SPLITTER): the driver/driven panels live
        # inside a horizontal QSplitter so the user can drag the
        # divider to reallocate width when one side has long bone
        # names. Initial stretch 1:1; the splitter's children are
        # NOT collapsible so a careless drag cannot zero-width
        # either editor.
        dd_widget = QtWidgets.QWidget()
        dd_layout = QtWidgets.QHBoxLayout(dd_widget)
        dd_layout.setContentsMargins(4, 4, 4, 4)
        dd_layout.setSpacing(0)
        self._driver_editor = TabbedDriverSourceEditor()
        self._driven_editor = TabbedDrivenSourceEditor()
        self._dd_splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        self._dd_splitter.setChildrenCollapsible(False)
        self._dd_splitter.addWidget(self._driver_editor)
        self._dd_splitter.addWidget(self._driven_editor)
        self._dd_splitter.setStretchFactor(0, 1)
        self._dd_splitter.setStretchFactor(1, 1)
        dd_layout.addWidget(self._dd_splitter, 1)
        self._outer_tabs.addTab(dd_widget, tr("tab_driver_driven"))

        # ---- Tab 2: Pose -----------------------------------------
        # Phase 2 (2026-04-27): the pose tab is now a multi-source-
        # aware grid (PoseGridEditor) instead of the legacy
        # QTableView + PoseTableModel. The grid renders one row per
        # pose with column groups derived from the active node's
        # driverSource[] + drivenSource[] entries.
        pose_widget = QtWidgets.QWidget()
        pose_layout = QtWidgets.QVBoxLayout(pose_widget)
        pose_layout.setContentsMargins(4, 4, 4, 4)
        pose_layout.setSpacing(4)

        # Auto-fill row.
        row_auto = QtWidgets.QHBoxLayout()
        self._cb_auto = QtWidgets.QCheckBox(tr("auto_fill_bs"))
        self._cb_auto.toggled.connect(self.autoFillChanged)
        row_auto.addWidget(self._cb_auto)
        row_auto.addStretch()
        row_auto.addWidget(HelpButton("auto_fill_bs"))
        pose_layout.addLayout(row_auto)
        pose_layout.addWidget(_hline())

        # Pose label.
        self._lbl_poses = QtWidgets.QLabel(tr("poses"))
        self._lbl_poses.setStyleSheet("font-weight: bold;")
        pose_layout.addWidget(self._lbl_poses)

        # PoseGridEditor (replaces QTableView).
        from RBFtools.ui.widgets.pose_grid_editor import PoseGridEditor
        self._pose_grid = PoseGridEditor()
        self._pose_grid.setMinimumHeight(180)
        pose_layout.addWidget(self._pose_grid, 1)

        # Legacy QTableView kept hidden (PoseTableModel still backs
        # the controller's add_pose / update_pose paths via
        # _gather_role_info; the table is the model's view of last
        # resort during the migration). Hidden + zero-size so it
        # doesn't take any visual real estate.
        self._table = QtWidgets.QTableView()
        self._table.setVisible(False)
        self._table.setMaximumHeight(0)
        self._table.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self._table.customContextMenuRequested.connect(
            self._show_row_menu)
        pose_layout.addWidget(self._table)

        pose_layout.addWidget(_hline())

        # Bottom action buttons (pose-level Apply/Connect/Disconnect/
        # Reload). The Add Pose / Delete Poses pair lives inside the
        # grid widget itself - we surface only Apply/Connect/Disc/Reload
        # here. (The legacy _btn_add reference is preserved for
        # backcompat with set_buttons_enabled + retranslate paths.)
        btn_row = QtWidgets.QHBoxLayout()
        self._btn_add        = QtWidgets.QPushButton(tr("add_pose"))
        self._btn_add.setVisible(False)   # add lives in pose grid
        self._btn_apply      = QtWidgets.QPushButton(tr("apply"))
        self._btn_connect    = QtWidgets.QPushButton(tr("connect"))
        self._btn_disconnect = QtWidgets.QPushButton(tr("disconnect"))
        self._btn_reload     = QtWidgets.QPushButton(tr("reload"))

        for btn, key in [
            (self._btn_apply, "apply_poses"),
            (self._btn_connect, "connect_poses"),
            (self._btn_disconnect, "disconnect_poses"),
            (self._btn_reload, "reload_poses"),
        ]:
            btn_row.addWidget(btn)
            btn_row.addWidget(HelpButton(key))

        self._btn_add.clicked.connect(self.addPoseRequested)
        self._btn_apply.clicked.connect(self.applyRequested)
        self._btn_connect.clicked.connect(self.connectRequested)
        self._btn_disconnect.clicked.connect(self.disconnectRequested)
        self._btn_reload.clicked.connect(self.reloadRequested)
        pose_layout.addLayout(btn_row)

        # PoseGridEditor signals -> panel-level signals.
        # Add Pose / Delete Poses live INSIDE the grid; surface them
        # via the pose-editor panel signal interface for
        # main_window slot wiring.
        self._pose_grid.addPoseRequested.connect(self.addPoseRequested)
        self._pose_grid.deleteAllPosesRequested.connect(
            self._on_grid_delete_all_poses)
        self._pose_grid.poseRecallRequested.connect(
            self._on_grid_recall_pose)
        self._pose_grid.poseUpdateRequested.connect(
            self._on_grid_update_pose)
        self._pose_grid.poseDeleteRequested.connect(
            self._on_grid_delete_pose)
        self._pose_grid.poseValueChangedV2.connect(
            self._on_grid_pose_value_changed_v2)
        self._pose_grid.poseRadiusChanged.connect(
            self.poseRadiusChanged)

        # Commit 3 (M_BASE_POSE): BaseDrivenPose tab. Inserted at
        # index 1 BETWEEN DriverDriven (0) and Pose (2) per the user's
        # spec ordering. Reuses PoseHeaderWidget + a single
        # PoseRowWidget(is_base_pose=True) — see widgets/base_pose_editor.
        from RBFtools.ui.widgets.base_pose_editor import BasePoseEditor
        self._base_pose_editor = BasePoseEditor()
        self._base_pose_editor.poseValueChangedV2.connect(
            self._on_base_pose_value_changed_v2)
        self._base_pose_editor.poseRecallRequested.connect(
            self._on_base_pose_recall_requested)
        self._outer_tabs.addTab(
            self._base_pose_editor, tr("tab_base_drv_pose"))

        self._outer_tabs.addTab(pose_widget, tr("tab_pose"))

        # Default to the DriverDriven tab being active.
        self._outer_tabs.setCurrentIndex(0)

    # -- public --

    @property
    def table_view(self):
        return self._table

    # ----- Phase 2 grid signal forwarding ----------------------------

    def _on_grid_recall_pose(self, pose_index):
        self.poseRecallRequested.emit(int(pose_index))

    def _on_grid_update_pose(self, pose_index):
        # M_P0_UPDATE_BUTTON_REVERSED (2026-04-30): re-emit the
        # per-row Update button click at the panel level so
        # main_window can dispatch ctrl.update_pose. Distinct
        # channel from poseRecallRequested.
        self.poseUpdateRequested.emit(int(pose_index))

    def _on_grid_delete_pose(self, pose_index):
        self.poseDeleteRequested.emit(int(pose_index))

    def _on_grid_delete_all_poses(self):
        self.poseDeleteAllRequested.emit()

    def _on_grid_pose_value_changed_v2(self, pose_idx, side,
                                       source_idx, attr_name, value):
        # C2 semantic: re-emit at the panel level for main_window.
        self.poseValueChangedV2.emit(
            int(pose_idx), str(side),
            int(source_idx), str(attr_name), float(value))

    def _on_base_pose_value_changed_v2(self, pose_idx, side,
                                       source_idx, attr_name, value):
        # BasePose row's pose_idx is the sentinel (-1); main_window
        # dispatches to write_base_pose_values rather than the regular
        # pose write path.
        self.baseValueChangedV2.emit(
            int(pose_idx), str(side),
            int(source_idx), str(attr_name), float(value))

    def _on_base_pose_recall_requested(self, _pose_idx):
        # BasePose's "Go to Pose" semantics: apply the baseline values
        # to the driven node attrs. main_window slot does the work.
        self.basePoseRecallRequested.emit()

    def reload_pose_grid(self, driver_sources, driven_sources, poses):
        """Public hook for main_window: push the latest source +
        pose state into the embedded PoseGridEditor so its rows
        rebuild after each editorLoaded /
        driver/drivenSourcesChanged signal cascade."""
        try:
            self._pose_grid.set_data(
                driver_sources, driven_sources, poses)
        except AttributeError:
            pass

    def reload_base_pose(self, driver_sources, driven_sources,
                         base_values):
        """Commit 3 (M_BASE_POSE): twin of :meth:`reload_pose_grid`
        for the BaseDrivenPose tab. ``base_values`` is the flat list
        of per-output baselines from
        :func:`core.read_base_pose_values`."""
        try:
            self._base_pose_editor.set_data(
                driver_sources, driven_sources, base_values)
        except AttributeError:
            pass

    @property
    def pose_grid(self):
        """Read-only accessor for the embedded PoseGridEditor."""
        return self._pose_grid

    @property
    def driver_editor(self):
        """M_TABBED_EDITOR_INTEGRATION (2026-04-27): the embedded
        multi-source driver editor. Replaces the legacy
        AttributeList ``driver_list`` accessor as the source of
        truth for driver bones + attributes."""
        return self._driver_editor

    @property
    def driven_editor(self):
        """Twin of :py:attr:`driver_editor` for the driven side."""
        return self._driven_editor

    def set_auto_fill(self, checked):
        self._cb_auto.blockSignals(True)
        self._cb_auto.setChecked(checked)
        self._cb_auto.blockSignals(False)

    def auto_fill(self):
        return self._cb_auto.isChecked()

    def set_buttons_enabled(self, enabled):
        """Enable or disable action buttons to prevent re-entrant calls."""
        for btn in (self._btn_add, self._btn_apply,
                    self._btn_connect, self._btn_disconnect,
                    self._btn_reload):
            btn.setEnabled(enabled)

    def retranslate(self):
        self.set_title(tr("rbf_pose_editor"))
        self._cb_auto.setText(tr("auto_fill_bs"))
        self._lbl_poses.setText(tr("poses"))
        # M_TABBED_EDITOR_REWRITE: refresh outer tab labels +
        # delegate to embedded tabbed editors.
        try:
            self._outer_tabs.setTabText(0, tr("tab_driver_driven"))
            self._outer_tabs.setTabText(1, tr("tab_pose"))
        except (AttributeError, TypeError):
            pass
        try:
            self._driver_editor.retranslate()
        except AttributeError:
            pass
        try:
            self._driven_editor.retranslate()
        except AttributeError:
            pass
        self._btn_add.setText(tr("add_pose"))
        self._btn_apply.setText(tr("apply"))
        self._btn_connect.setText(tr("connect"))
        self._btn_disconnect.setText(tr("disconnect"))
        self._btn_reload.setText(tr("reload"))

    # -- row context menu (Recall / Update / Delete + M3.x extensions) --

    def add_pose_row_action(self, label_key, callback, danger=False):
        """M3.0-spillover (added in M3.2 commit per addendum §M3.0.5):
        register an extra action on the pose-table right-click menu.

        M3.x sub-tasks call this from their controller wiring; the
        callback receives ``(row_idx)``. Future Pruner / Mirror /
        any other per-pose action goes through this — direct edits
        to ``_show_row_menu`` are forbidden after M3.2.
        """
        self._extra_row_actions.append((label_key, callback, danger))

    def _show_row_menu(self, pos):
        idx = self._table.indexAt(pos)
        if not idx.isValid():
            return
        row = idx.row()
        menu = QtWidgets.QMenu(self)
        act_recall = menu.addAction(tr("recall"))
        act_update = menu.addAction(tr("update"))
        menu.addSeparator()
        act_delete = menu.addAction(tr("delete"))
        act_delete.setProperty("cssClass", "danger")

        # M3.0-spillover: append M3.x-registered actions in order.
        extra_actions = []
        if getattr(self, "_extra_row_actions", None):
            menu.addSeparator()
            for label_key, _cb, danger in self._extra_row_actions:
                act = menu.addAction(tr(label_key))
                if danger:
                    act.setProperty("cssClass", "danger")
                extra_actions.append((act, _cb))

        action = menu.exec_(self._table.viewport().mapToGlobal(pos))
        if action == act_recall:
            self._on_row_action("recall", row)
        elif action == act_update:
            self._on_row_action("update", row)
        elif action == act_delete:
            self._on_row_action("delete", row)
        else:
            for act, cb in extra_actions:
                if action == act:
                    try:
                        cb(row)
                    except Exception as exc:
                        # Don't let a broken extra action break the
                        # pose table's interaction.
                        from maya import cmds as _cmds
                        _cmds.warning(
                            "pose-row action {!r} failed: {}".format(
                                label_key, exc))
                    break

    def _on_row_action(self, action, row):
        """Emit a signal that the window can catch."""
        # Store as a dynamic property so the window can read it
        self.setProperty("_last_action", action)
        self.setProperty("_last_row", row)
        # Use a generic signal via the parent window's handler
        # (connected in RBFToolsWindow._connect_signals)
        if hasattr(self, "_row_action_callback"):
            self._row_action_callback(action, row)


# =====================================================================
#  Helper
# =====================================================================

def _hline():
    line = QtWidgets.QFrame()
    line.setFrameShape(QtWidgets.QFrame.HLine)
    line.setFrameShadow(QtWidgets.QFrame.Sunken)
    return line


# =====================================================================
#  M_UIRECONCILE_PLUS Item 4b — Driver attribute picker dialog
# =====================================================================

class _DriverAttrPickerDialog(QtWidgets.QDialog):
    """Modal dialog for picking the keyable attributes that feed a
    single driver source's RBF input vector.

    MVC-clean: the dialog never imports cmds; the calling slot in
    RBFToolsWindow resolves the available attribute list via
    cmds.listAttr and passes it in. The dialog returns the
    user-selected list (or None on cancel)."""

    def __init__(self, parent, node, available_attrs, preselected):
        super(_DriverAttrPickerDialog, self).__init__(parent)
        self.setWindowTitle(tr("title_pick_driver_attrs"))
        self.setModal(True)

        layout = QtWidgets.QVBoxLayout(self)
        summary = tr("summary_pick_driver_attrs").format(node=node)
        self._lbl = QtWidgets.QLabel(summary)
        self._lbl.setWordWrap(True)
        layout.addWidget(self._lbl)

        self._list = QtWidgets.QListWidget()
        self._list.setSelectionMode(
            QtWidgets.QAbstractItemView.MultiSelection)
        preselected_set = set(preselected or [])
        for attr in available_attrs or []:
            item = QtWidgets.QListWidgetItem(attr)
            self._list.addItem(item)
            if attr in preselected_set:
                item.setSelected(True)
        layout.addWidget(self._list, 1)

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch(1)
        self._btn_ok = QtWidgets.QPushButton(tr("btn_ok"))
        self._btn_ok.setDefault(True)
        self._btn_ok.clicked.connect(self.accept)
        self._btn_cancel = QtWidgets.QPushButton(tr("cancel"))
        self._btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(self._btn_ok)
        btn_row.addWidget(self._btn_cancel)
        layout.addLayout(btn_row)

        self.resize(360, 380)

    def selected_attrs(self):
        """Return the list of selected attribute names in display
        order."""
        return [
            self._list.item(i).text()
            for i in range(self._list.count())
            if self._list.item(i).isSelected()
        ]

    @classmethod
    def pick(cls, parent, node, available_attrs, preselected):
        """Convenience: open the dialog modally + return the
        selected attribute list, or None on cancel."""
        dlg = cls(parent, node, available_attrs, preselected)
        if dlg.exec_() != QtWidgets.QDialog.Accepted:
            return None
        return dlg.selected_attrs()


# =====================================================================
#  Main Window
# =====================================================================

class StatusProgressController(object):
    """Encapsulates the 3-state status-bar progress lifecycle (M3.0).

    Decouples M3.x sub-tasks from the private QProgressBar attribute on
    the main window: callers go through ``MainController.progress()``
    which returns this object, then ``begin / step / end``. Future
    migration to a different progress widget is one place.

    States:
      * ``begin(message)`` — show the bar in indeterminate mode (range
        0,0 sweep), set status label.
      * ``step(current, total, message)`` — switch to determinate mode
        and update fill + label.
      * ``end(message)`` — hide the bar, restore status label to
        *message* (or empty).
    """

    def __init__(self, progress_bar, status_label):
        self._bar = progress_bar
        self._label = status_label

    def begin(self, message=""):
        self._bar.setRange(0, 0)
        self._bar.setVisible(True)
        if message:
            self._label.setText(message)

    def step(self, current, total, message=""):
        self._bar.setRange(0, max(1, int(total)))
        self._bar.setValue(int(current))
        if message:
            self._label.setText(message)

    def end(self, message=""):
        self._bar.setVisible(False)
        self._bar.setRange(0, 0)
        self._label.setText(message or "")


class RBFToolsWindow(QtWidgets.QMainWindow):
    """Singleton main window for RBF Tools."""

    def __init__(self, parent=None):
        super(RBFToolsWindow, self).__init__(parent)
        self.setObjectName(WINDOW_OBJECT)
        self.setWindowTitle(WINDOW_TITLE)
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setStyleSheet(STYLESHEET)

        # Controller
        self._ctrl = MainController(self)

        # Delegate (updated when columns change)
        self._delegate = PoseDelegate(n_inputs=0, parent=self)

        # M_CRASH_FIX defense 3 (2026-04-28): re-entrancy lock.
        # Set to True during a batch Connect/Disconnect storm so
        # _refresh_pose_grid + _refresh_base_pose_panel become
        # no-ops and node-change callbacks cannot re-paint the
        # tabbed editors mid-operation (which would invalidate
        # the very widget pointers the slot is iterating over -> CTD).
        self._is_updating = False

        self._build_ui()
        self._connect_signals()

        # Deferred init — lets Maya finish any pending UI work first
        mutils.executeDeferred(self._deferred_init)

    # =================================================================
    #  UI construction
    # =================================================================

    def _build_ui(self):
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)

        root = QtWidgets.QVBoxLayout(central)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(3)

        # ---- Node selector ----
        self._node_sel = NodeSelector()
        root.addWidget(self._node_sel)
        # Phase 3 (2026-04-27): header naming-mode radio group +
        # the LongName/ShortName/NiceName labels surfaced by the
        # AnimaRbfSolver reference. The picked mode drives how
        # node names render in the embedded tabbed editors +
        # pose grid headers via core.format_node_for_display.
        name_mode_row = QtWidgets.QHBoxLayout()
        name_mode_row.setContentsMargins(4, 0, 4, 0)
        self._rb_name_long = QtWidgets.QRadioButton(tr("name_long"))
        self._rb_name_short = QtWidgets.QRadioButton(tr("name_short"))
        self._rb_name_nice = QtWidgets.QRadioButton(tr("name_nice"))
        self._rb_name_long.setChecked(True)
        self._name_mode_group = QtWidgets.QButtonGroup(self)
        self._name_mode_group.addButton(self._rb_name_long, 0)
        self._name_mode_group.addButton(self._rb_name_short, 1)
        self._name_mode_group.addButton(self._rb_name_nice, 2)
        for rb in (self._rb_name_long,
                   self._rb_name_short,
                   self._rb_name_nice):
            name_mode_row.addWidget(rb)
        name_mode_row.addStretch(1)
        root.addLayout(name_mode_row)
        root.addWidget(_hline())

        # ---- Scrollable sections ----
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)

        scroll_widget = QtWidgets.QWidget()
        self._sections = QtWidgets.QVBoxLayout(scroll_widget)
        self._sections.setContentsMargins(0, 0, 0, 0)
        self._sections.setSpacing(3)

        self._general    = GeneralSection()
        self._va_section = VectorAngleSection()
        self._rbf_section = RBFSection()
        # M_TABBED_EDITOR_INTEGRATION (user directive 2026-04-27,
        # "驱动源这一栏UI删除"): the standalone Driver Sources +
        # Driven Targets sections are removed from the inspector.
        # The multi-source tabbed editors now live INSIDE the pose
        # editor (replacing the legacy AttributeList driver / driven
        # picker). The output-encoding combo + Hardening 1
        # collapsible header are moved into a smaller "Output
        # Encoding" section so the node-level enum is still
        # reachable.
        self._pose_editor = _PoseEditorPanel()
        # Aliases that preserve the M_UIRECONCILE / M_DRIVEN_MULTI
        # public attribute names (`_driver_source_list`,
        # `_driven_source_list`) so the existing signal wiring +
        # _retranslate_all + permanent-guard #36 source-scans all
        # continue to find them. They now point at the tabbed
        # editors embedded inside the pose-editor panel.
        self._driver_source_list = self._pose_editor.driver_editor
        self._driven_source_list = self._pose_editor.driven_editor
        # Output Encoding gets its own slim collapsible (it lives at
        # the node level, not per-source, and was previously hosted
        # inside the now-removed Driver Sources section).
        self._output_encoding_combo = OutputEncodingCombo()
        self._output_encoding_section = CollapsibleFrame(
            tr("section_output_encoding"), collapsed=True)
        _oe_row = QtWidgets.QHBoxLayout()
        _oe_row.addWidget(QtWidgets.QLabel(tr("output_encoding_label")))
        _oe_row.addWidget(self._output_encoding_combo, 1)
        # M_P1_ENC_COMBO_FIX (2026-04-29): per-encoding ComboHelpButton
        # so the bubble describes ONLY the currently-selected output
        # encoding (Euler / Quaternion / ExpMap) instead of the merged
        # 3-section blob. Mirrors the input-encoding combo paradigm
        # (rbf_section.py:237 + M_HELPTEXT_ENC_PER_KEY). The plain
        # HelpButton("output_encoding") added in M_HELPBUBBLE_BATCH
        # (enc-2 / 6528211) is replaced because the ComboHelpButton
        # constructor must receive the combo directly to subscribe
        # to its currentIndexChanged + highlighted signals — this is
        # only reachable as a sibling widget in the parent layout.
        _oe_row.addWidget(ComboHelpButton(
            self._output_encoding_combo, [
                "output_enc_euler",
                "output_enc_quaternion",
                "output_enc_expmap",
            ], fallback_key="output_encoding"))
        self._output_encoding_section.add_layout(_oe_row)

        # Phase 3 (Utility section 2026-04-27): below the pose
        # editor, expose the AnimaRbfSolver "Utility" panel -
        # Split RBFSolver For Each Joint + cleanup tools (Remove
        # Connectionless Input/Output, Remove Redundant Pose).
        self._utility_section = CollapsibleFrame(
            tr("section_utility"), collapsed=True)
        # M_HELPBUBBLE_BATCH: HelpButton next to Split RBFSolver.
        _split_row = QtWidgets.QHBoxLayout()
        self._btn_split_solver = QtWidgets.QPushButton(
            tr("btn_split_solver_per_joint"))
        self._btn_split_solver.setToolTip(
            tr("btn_split_solver_per_joint_tip"))
        _split_row.addWidget(self._btn_split_solver, 1)
        _split_row.addWidget(HelpButton("btn_split_solver_per_joint"))
        self._utility_section.add_layout(_split_row)
        # Cleanup mode radio group + execute button.
        # M_HELPBUBBLE_BATCH: ONE HelpButton at the end of the radio
        # row covers all 3 cleanup modes + the Run button (the
        # bubble walks through input / output / redundant-pose
        # semantics together — they share the same execute path).
        cleanup_row = QtWidgets.QHBoxLayout()
        self._rb_cleanup_in = QtWidgets.QRadioButton(
            tr("rb_remove_connectionless_input"))
        self._rb_cleanup_out = QtWidgets.QRadioButton(
            tr("rb_remove_connectionless_output"))
        self._rb_cleanup_pose = QtWidgets.QRadioButton(
            tr("rb_remove_redundant_pose"))
        self._rb_cleanup_in.setChecked(True)
        self._cleanup_group = QtWidgets.QButtonGroup(self)
        self._cleanup_group.addButton(self._rb_cleanup_in, 0)
        self._cleanup_group.addButton(self._rb_cleanup_out, 1)
        self._cleanup_group.addButton(self._rb_cleanup_pose, 2)
        cleanup_row.addWidget(self._rb_cleanup_in)
        cleanup_row.addWidget(self._rb_cleanup_out)
        cleanup_row.addWidget(self._rb_cleanup_pose)
        cleanup_row.addWidget(HelpButton("cleanup_modes_overview"))
        self._utility_section.add_layout(cleanup_row)
        _run_row = QtWidgets.QHBoxLayout()
        self._btn_run_cleanup = QtWidgets.QPushButton(
            tr("btn_remove_unnecessary_datas"))
        _run_row.addWidget(self._btn_run_cleanup, 1)
        _run_row.addWidget(HelpButton("btn_remove_unnecessary_datas"))
        self._utility_section.add_layout(_run_row)

        self._sections.addWidget(self._general)
        self._sections.addWidget(self._va_section)
        self._sections.addWidget(self._rbf_section)
        self._sections.addWidget(self._output_encoding_section)
        self._sections.addWidget(self._pose_editor)
        self._sections.addWidget(self._utility_section)
        self._sections.addStretch()

        scroll.setWidget(scroll_widget)
        root.addWidget(scroll, 1)

        # ---- Bind model + delegate to table view ----
        tv = self._pose_editor.table_view
        tv.setModel(self._ctrl.pose_model)
        tv.setItemDelegate(self._delegate)

        # ---- Status bar ----
        root.addWidget(_hline())
        status_row = QtWidgets.QHBoxLayout()
        status_row.setContentsMargins(0, 0, 0, 0)
        self._progress = QtWidgets.QProgressBar()
        self._progress.setTextVisible(False)
        self._progress.setFixedHeight(14)
        self._progress.setRange(0, 0)       # indeterminate
        self._progress.setVisible(False)
        self._status_label = QtWidgets.QLabel("")
        self._status_label.setStyleSheet("color: #888;")
        status_row.addWidget(self._progress)
        status_row.addWidget(self._status_label, 1)
        root.addLayout(status_row)

        # ---- M3.0: shared infrastructure wiring ----
        self._progress_ctrl = StatusProgressController(
            self._progress, self._status_label)
        # Hand the progress controller to the controller so M3.x
        # sub-tasks reach it via `controller.progress()` (addendum
        # §M3.0 access path A — the recommended MVC route).
        self._ctrl.set_progress_controller(self._progress_ctrl)

        # ---- M3.0: top-level menu bar ----
        self._build_menu_bar()

        # ---- M3.2: wire Mirror Tool entry points via M3.0-spillover ----
        # First real-world consumer of add_tools_action / add_pose_row_action
        # (addendum §M3.0.5).
        self.add_tools_action("menu_mirror_node", self._on_mirror_node)
        self._pose_editor.add_pose_row_action(
            "row_mirror_this", self._on_mirror_pose, danger=False)

        # ---- M3.3: File menu entries via M3.0-spillover §2 ----
        self.add_file_action("menu_import_rbf", self._on_import_rbf)
        self.add_file_action(
            "menu_export_selected", self._on_export_selected)
        self.add_file_action("menu_export_all", self._on_export_all)

        # ---- M3.6: Add Neutral Sample entry ----
        self.add_tools_action(
            "menu_add_neutral_sample", self._on_add_neutral_sample)
        # Edit-menu reset for the auto-neutral optionVar (mirrors
        # the M3.0 reset_all_skip_confirms pattern; no confirm
        # dialog because selecting the menu item is the user intent).
        self._act_reset_auto_neutral = QtWidgets.QAction(
            tr("menu_reset_auto_neutral"), self)
        self._act_reset_auto_neutral.triggered.connect(
            self._on_reset_auto_neutral)
        self._menu_edit.addAction(self._act_reset_auto_neutral)

        # ---- M3.5: Pose Profiler entries + ToolsSection panel ----
        # (M3.0-spillover §3 lazy creation happens inside the
        # add_tools_panel_widget call below.)
        from RBFtools.ui.widgets.profile_widget import ProfileWidget
        self._profile_widget = ProfileWidget(self._ctrl, parent=self)
        self.add_tools_panel_widget("profile_report", self._profile_widget)
        self.add_tools_action(
            "menu_profile_to_se", self._on_profile_to_script_editor)
        self._ctrl.editorLoaded.connect(self._profile_widget.on_node_changed)

        # ---- M3.4: Live Edit Mode toggle (spillover §3 second consumer)
        from RBFtools.ui.widgets.live_edit_widget import LiveEditWidget
        self._live_edit_widget = LiveEditWidget(
            self._ctrl, self._pose_editor.table_view, parent=self)
        self.add_tools_panel_widget(
            "live_edit_toggle", self._live_edit_widget)

        # ---- M3.1: Pose Pruner entry + single-pose row delete ----
        self.add_tools_action("menu_prune_poses", self._on_prune_poses)
        self._pose_editor.add_pose_row_action(
            "row_remove_this", self._on_remove_pose_row, danger=True)

        # ---- M3.7: alias regeneration entries via M3.0-spillover ----
        # Non-destructive (preserves user aliases) — no confirm dialog.
        self.add_tools_action(
            "menu_regenerate_aliases", self._on_regenerate_aliases)
        # Destructive (wipes user aliases) — confirm gate inside
        # controller.force_regenerate_aliases_for_current_node.
        self.add_tools_action(
            "menu_force_regenerate_aliases",
            self._on_force_regenerate_aliases)

    # =================================================================
    #  M3.0 — Menu bar
    # =================================================================

    def _build_menu_bar(self):
        """Create the top-level menu bar (M3.0 baseline + M3.x add-ons).

        Each M3.x sub-task adds its own actions to the appropriate
        menu (File / Edit / Tools / Help) — M3.0 only seeds the four
        empty top-level menus + the Tools → Reset confirm dialogs
        baseline action (addendum §M3.0).
        """
        mb = self.menuBar()
        self._menu_file  = mb.addMenu(tr("menu_file"))
        self._menu_edit  = mb.addMenu(tr("menu_edit"))
        self._menu_tools = mb.addMenu(tr("menu_tools"))
        self._menu_help  = mb.addMenu(tr("menu_help"))

        # Tools → Reset confirm dialogs.
        # No "are you sure" — selecting the menu item already
        # constitutes user intent (addendum §M3.0 (G)①).
        self._act_reset_confirms = QtWidgets.QAction(
            tr("menu_reset_confirms"), self)
        self._act_reset_confirms.triggered.connect(self._on_reset_confirms)
        self._menu_tools.addAction(self._act_reset_confirms)

    def _on_reset_confirms(self):
        # Lazy import keeps this menu callback decoupled from core
        # at module import time.
        from RBFtools import core
        core.reset_all_skip_confirms()
        if hasattr(self, "_progress_ctrl") and self._progress_ctrl:
            self._progress_ctrl.end(tr("reset_confirms_done"))

    def _on_mirror_node(self):
        """Tools -> Mirror Node... (M3.2 main entry)."""
        from RBFtools.ui.widgets.mirror_dialog import MirrorDialog
        node = self._ctrl.current_node()
        if not node:
            self._progress_ctrl.end(tr("status_no_node_selected")
                                    if False else "")
            return
        dlg = MirrorDialog(node, parent=self)
        if dlg.exec_() != QtWidgets.QDialog.Accepted:
            return
        config = dlg.get_config()
        # controller.mirror_current_node handles the path A confirm
        # dialog + progress feedback + actual core.mirror_node call.
        self._ctrl.mirror_current_node(config)
        # Refresh the UI so the newly created target shows up in the
        # node selector.
        self._on_refresh()

    # =================================================================
    #  M3.5 — Pose Profiler entry + ToolsSection spillover §3
    # =================================================================

    def _on_profile_to_script_editor(self):
        """Tools -> Profile to Script Editor. One-shot print of
        the current node's profile to the Script Editor."""
        self._ctrl.profile_to_script_editor()

    def _ensure_tools_section(self):
        """Lazily create the per-node ToolsSection collapsible.

        First call instantiates a CollapsibleFrame and inserts it
        into the section list right before the trailing stretch.
        Subsequent calls return the existing instance.

        Once created, the section persists for the session — even
        if every registered widget is removed (T_TOOLS_SECTION_PERSISTS
        permanent guard, addendum §M3.5 spillover §3 contract).
        """
        if getattr(self, "_tools_section", None) is None:
            from RBFtools.ui.widgets.collapsible import CollapsibleFrame
            self._tools_section = CollapsibleFrame(tr("section_tools"))
            self._tools_panel_widgets = {}
            # Insert just before the trailing addStretch() in the
            # _sections layout (count - 1 is the stretch item).
            self._sections.insertWidget(
                self._sections.count() - 1, self._tools_section)
        return self._tools_section

    def add_tools_panel_widget(self, widget_id, widget):
        """Register *widget* under *widget_id* in the per-node
        ToolsSection collapsible (M3.0-spillover §3, added in
        M3.5 commit). The collapsible is lazily created on first
        call.

        Raises RuntimeError when *widget_id* is already
        registered — caller must :meth:`remove_tools_panel_widget`
        first. Silent overwrite would risk M3.4 state leakage.

        Returns the registered widget on success.
        """
        section = self._ensure_tools_section()
        if widget_id in self._tools_panel_widgets:
            raise RuntimeError(
                "add_tools_panel_widget: widget_id {!r} already "
                "registered; call remove_tools_panel_widget "
                "first".format(widget_id))
        section.add_widget(widget)
        self._tools_panel_widgets[widget_id] = widget
        return widget

    def remove_tools_panel_widget(self, widget_id):
        """Unregister and detach a previously-added Tools panel
        widget. Returns True on success, False when *widget_id*
        is unknown.

        The ToolsSection itself is NOT destroyed even when the
        last widget is removed — once created, it persists for
        the session (T_TOOLS_SECTION_PERSISTS guard)."""
        widgets = getattr(self, "_tools_panel_widgets", None)
        if not widgets:
            return False
        w = widgets.pop(widget_id, None)
        if w is None:
            return False
        try:
            w.setParent(None)
            w.deleteLater()
        except Exception:
            pass
        return True

    # =================================================================
    #  M3.6 — Add Neutral Sample entry points
    # =================================================================

    def _on_add_neutral_sample(self):
        """Tools -> Add Neutral Sample. Delegates to controller's
        path A consumer (confirm only if existing poses)."""
        self._ctrl.add_neutral_sample_to_current_node()

    def _on_reset_auto_neutral(self):
        """Edit -> Reset auto-neutral default. Clears the optionVar
        so the next create_node falls back to default-True."""
        self._ctrl.reset_auto_neutral_default()
        if hasattr(self, "_progress_ctrl") and self._progress_ctrl:
            self._progress_ctrl.end(tr("reset_auto_neutral_done"))

    # =================================================================
    #  M3.1 — Pose Pruner entry points
    # =================================================================

    def _on_prune_poses(self):
        """Tools -> Prune Poses... opens PruneDialog. The dialog
        gathers the per-class checkbox state and delegates to
        controller.prune_current_node, which runs the path A
        confirm + execute. After execute the pose editor is
        repopulated so the table reflects the pruned shape."""
        from RBFtools.ui.widgets.prune_dialog import PruneDialog
        node = self._ctrl.current_node
        if not node:
            from maya import cmds as _cmds
            from RBFtools.ui.i18n import tr
            _cmds.warning(tr("warning_pose_pruner_no_node"))
            return
        dlg = PruneDialog(node, self._ctrl, parent=self)
        if dlg.exec_() != QtWidgets.QDialog.Accepted:
            return
        opts = dlg.get_options()
        self._ctrl.prune_current_node(opts)

    def _on_remove_pose_row(self, row_idx):
        """Right-click pose-table -> Remove this pose (M3.1 single
        pose path, addendum §M3.1 F.2). No confirm dialog — single
        pose removal is low-risk; warning gives the user basic
        expectation that the RBF will need re-Apply."""
        from maya import cmds as _cmds
        self._ctrl.delete_pose(row_idx)
        _cmds.warning(
            "Pose removed; you may want to re-Apply to retrain RBF.")

    # =================================================================
    #  M3.3 — File menu callbacks (path A consumers)
    # =================================================================

    def _on_import_rbf(self):
        """File -> Import RBF Setup..."""
        from RBFtools.ui.widgets.import_dialog import ImportDialog
        from maya import cmds as _cmds
        try:
            paths = _cmds.fileDialog2(fileMode=1, fileFilter="JSON (*.json)",
                                      caption=tr("title_import_replace"))
        except Exception:
            paths = None
        if not paths:
            return
        path = paths[0]
        # ImportDialog handles dry-run preview + Add/Replace radio
        # locally before delegating to controller.import_rbf_setup.
        dlg = ImportDialog(path, self._ctrl, parent=self)
        if dlg.exec_() != QtWidgets.QDialog.Accepted:
            return
        mode = dlg.get_mode()
        self._ctrl.import_rbf_setup(path, mode=mode)

    def _on_export_selected(self):
        """File -> Export Selected RBF..."""
        from maya import cmds as _cmds
        try:
            paths = _cmds.fileDialog2(fileMode=0, fileFilter="JSON (*.json)",
                                      caption=tr("menu_export_selected"))
        except Exception:
            paths = None
        if not paths:
            return
        self._ctrl.export_current_to_path(paths[0])

    def _on_export_all(self):
        """File -> Export All RBF..."""
        from maya import cmds as _cmds
        try:
            paths = _cmds.fileDialog2(fileMode=0, fileFilter="JSON (*.json)",
                                      caption=tr("menu_export_all"))
        except Exception:
            paths = None
        if not paths:
            return
        self._ctrl.export_all_to_path(paths[0])

    def add_file_action(self, label_key, callback):
        """M3.0-spillover §2 (added in M3.3 commit per addendum
        §M3.0-spillover §2): register an action on the File menu.

        Mirror of :meth:`add_tools_action` for the File menu. M3.x
        sub-tasks call this; direct edits to ``_build_menu_bar`` are
        forbidden after M3.3.
        """
        act = QtWidgets.QAction(tr(label_key), self)
        act.triggered.connect(callback)
        self._menu_file.addAction(act)
        if not hasattr(self, "_file_actions"):
            self._file_actions = []
        self._file_actions.append((act, label_key))
        return act

    def _on_regenerate_aliases(self):
        """Tools -> Regenerate Aliases (M3.7, non-destructive)."""
        self._ctrl.regenerate_aliases_for_current_node()

    def _on_force_regenerate_aliases(self):
        """Tools -> Force Regenerate Aliases (M3.7, destructive,
        confirm-gated). Walks path A via controller."""
        self._ctrl.force_regenerate_aliases_for_current_node()

    def _on_mirror_pose(self, row_idx):
        """Right-click pose-table -> Mirror this pose (M3.2 single-pose
        path; no confirm dialog per addendum §M3.2 (H)①)."""
        # Single-pose mirror in M3.2 is documented but the actual
        # implementation reuses controller.mirror_current_node with
        # a single-pose subset config — to avoid a parallel data path
        # that could drift from the orchestrator's contract. Future
        # extension can add a controller-level mirror_pose_at(row).
        # For now, fall back to a warning + suggest using the full
        # Mirror Node dialog.
        from maya import cmds as _cmds
        _cmds.warning(
            "Single-pose mirror (row {}) is reserved for the next "
            "M3.2 patch — please use Tools -> Mirror Node... for "
            "now.".format(row_idx))

    def add_tools_action(self, label_key, callback):
        """M3.0-spillover (added in M3.2 commit per addendum §M3.0.5):
        register an action on the Tools menu.

        Returns the QAction so callers can keep a reference (e.g. for
        enable/disable based on selection state). M3.x sub-tasks
        call this; direct edits to ``_build_menu_bar`` are forbidden
        after M3.2.
        """
        act = QtWidgets.QAction(tr(label_key), self)
        act.triggered.connect(callback)
        self._menu_tools.addAction(act)
        # Track for retranslate.
        if not hasattr(self, "_tools_actions"):
            self._tools_actions = []
        self._tools_actions.append((act, label_key))
        return act

    # =================================================================
    #  Signal wiring
    # =================================================================

    def _connect_signals(self):
        ctrl = self._ctrl
        ns   = self._node_sel

        # ---- Node selector → controller ----
        ns.nodeChanged.connect(ctrl.on_node_changed)
        ns.refreshRequested.connect(self._on_refresh)
        ns.pickSelRequested.connect(self._on_pick_sel)
        ns.newRequested.connect(self._on_create_node)
        ns.deleteRequested.connect(self._on_delete_node)
        ns.languageChangeRequested.connect(self._switch_language)

        # ---- Controller → view ----
        ctrl.nodesRefreshed.connect(self._on_nodes_refreshed)
        ctrl.settingsLoaded.connect(self._on_settings_loaded)
        ctrl.radiusUpdated.connect(self._on_radius_updated)
        ctrl.editorLoaded.connect(self._on_editor_loaded)
        ctrl.statusMessage.connect(self._show_status)

        # ---- General section → controller ----
        self._general.attributeChanged.connect(ctrl.set_attribute)
        self._general.typeChanged.connect(self._on_type_changed)

        # ---- Vector angle → controller ----
        self._va_section.attributeChanged.connect(ctrl.set_attribute)

        # ---- RBF section → controller ----
        self._rbf_section.attributeChanged.connect(ctrl.set_attribute)
        self._rbf_section.kernelChanged.connect(ctrl.on_kernel_changed)
        self._rbf_section.radiusTypeChanged.connect(ctrl.on_radius_type_changed)
        self._rbf_section.radiusEdited.connect(ctrl.on_radius_edited)
        # M_ENC_AUTOPIPE: post-write side-effect — auto-derive
        # driverInputRotateOrder[] from connected drivers when the
        # user picks BendRoll / ExpMap / SwingTwist.
        self._rbf_section.inputEncodingChanged.connect(
            ctrl.on_input_encoding_changed)
        # M_P1_ENC_COMBO_FIX: narrow rotate-order-editor reload that
        # replaces the prior _load_settings cascade. The controller
        # emits this signal AFTER auto_resolve_generic_rotate_orders
        # with the freshly read values; the rbf_section repopulates
        # only the OrderedEnumListEditor — combos and other M2.x
        # widgets stay untouched, eliminating the inputEncoding
        # combo bounce-back regression.
        ctrl.rotateOrderEditorReload.connect(
            self._rbf_section.set_rotate_order_values)

        # ---- Pose editor panel → handlers ----
        pe = self._pose_editor
        pe.selectNodeRequested.connect(self._on_select_node_for_role)
        pe.filtersChanged.connect(self._on_filters_changed)
        pe.addPoseRequested.connect(self._on_add_pose)
        pe.applyRequested.connect(self._on_apply)
        pe.connectRequested.connect(self._on_connect)
        pe.disconnectRequested.connect(self._on_disconnect)
        pe.reloadRequested.connect(self._on_reload)
        pe.autoFillChanged.connect(ctrl.set_auto_fill)
        # Phase 2 PoseGridEditor signals.
        pe.poseRecallRequested.connect(self._on_pose_grid_recall)
        # M_P0_UPDATE_BUTTON_REVERSED (2026-04-30): per-row Update
        # button click -> ctrl.update_pose (snapshot viewport ->
        # pose model). Distinct from poseRecallRequested
        # (Go-to-Pose; pose -> viewport).
        pe.poseUpdateRequested.connect(self._on_pose_grid_update)
        pe.poseDeleteRequested.connect(self._on_pose_grid_delete)
        pe.poseDeleteAllRequested.connect(
            self._on_pose_grid_delete_all)
        # Commit 3 (C2 semantic refactor): all 4 pose-grid slots now
        # carry source_idx + attr_name. flat_attr_idx form removed.
        pe.poseValueChangedV2.connect(
            self._on_pose_grid_value_changed_v2)
        pe.poseRadiusChanged.connect(
            self._on_pose_grid_radius_changed)
        # Commit 3 (M_BASE_POSE): BaseDrivenPose tab → core helpers.
        pe.baseValueChangedV2.connect(
            self._on_base_pose_value_changed)
        pe.basePoseRecallRequested.connect(
            self._on_base_pose_recall)

        # Row context-menu callback
        pe._row_action_callback = self._on_pose_row_action

        # ---- M_UIRECONCILE: DriverSourceListEditor wiring -----------
        # Closes the M_B24b1 island-widget gap (see addendum
        # §M_UIRECONCILE.m_b24b1-correction). The widget emits
        # request signals; main_window owns the cmds.ls call and
        # delegates to controller.add_driver_source /
        # remove_driver_source, then reloads via the controller's
        # driverSourcesChanged signal (decision F.1, MVC clean).
        # ---- M_TABBED_EDITOR: Driver tabbed editor wiring ----------
        # Each tab carries its own signal surface; the editor re-emits
        # with the tab's resolved index so reorder operations stay
        # correct.
        self._driver_source_list.addRequested.connect(
            self._on_driver_source_add_requested)
        self._driver_source_list.removeRequested.connect(
            self._on_driver_source_remove_requested)
        self._driver_source_list.attrsApplyRequested.connect(
            self._on_driver_source_attrs_apply)
        self._driver_source_list.attrsClearRequested.connect(
            self._on_driver_source_attrs_clear)
        # M_BATCH_PATH_A_WIRE (2026-04-28): cross-tab broadcast
        # slots. Fired only when _chk_batch on the panel is
        # checked at click time.
        self._driver_source_list.attrsApplyBatchRequested.connect(
            self._on_driver_source_attrs_apply_batch)
        self._driver_source_list.attrsClearBatchRequested.connect(
            self._on_driver_source_attrs_clear_batch)
        self._driver_source_list.selectNodeRequested.connect(
            self._on_driver_source_select_node)
        ctrl.driverSourcesChanged.connect(self._reload_driver_sources)
        ctrl.editorLoaded.connect(self._reload_driver_sources)
        ctrl.nodesRefreshed.connect(
            lambda _names: self._reload_driver_sources())

        # ---- M_TABBED_EDITOR: Driven tabbed editor wiring ----------
        self._driven_source_list.addRequested.connect(
            self._on_driven_source_add_requested)
        self._driven_source_list.removeRequested.connect(
            self._on_driven_source_remove_requested)
        self._driven_source_list.attrsApplyRequested.connect(
            self._on_driven_source_attrs_apply)
        self._driven_source_list.attrsClearRequested.connect(
            self._on_driven_source_attrs_clear)
        # M_BATCH_PATH_A_WIRE driven mirror.
        self._driven_source_list.attrsApplyBatchRequested.connect(
            self._on_driven_source_attrs_apply_batch)
        self._driven_source_list.attrsClearBatchRequested.connect(
            self._on_driven_source_attrs_clear_batch)
        self._driven_source_list.selectNodeRequested.connect(
            self._on_driven_source_select_node)
        ctrl.drivenSourcesChanged.connect(self._reload_driven_sources)
        ctrl.editorLoaded.connect(self._reload_driven_sources)
        ctrl.nodesRefreshed.connect(
            lambda _names: self._reload_driven_sources())

        # ---- Phase 3: Header naming radios + Utility section -------
        # Header naming radios drive controller.set_name_display_mode;
        # the controller emits nameDisplayModeChanged which causes a
        # source reload cascade so the tabbed editors + pose grid
        # re-render node labels through core.format_node_for_display.
        self._rb_name_long.toggled.connect(
            lambda checked: checked
            and ctrl.set_name_display_mode("long"))
        self._rb_name_short.toggled.connect(
            lambda checked: checked
            and ctrl.set_name_display_mode("short"))
        self._rb_name_nice.toggled.connect(
            lambda checked: checked
            and ctrl.set_name_display_mode("nice"))
        ctrl.nameDisplayModeChanged.connect(
            lambda _mode: (self._reload_driver_sources(),
                           self._reload_driven_sources()))
        # Utility section buttons.
        self._btn_split_solver.clicked.connect(
            self._on_split_solver_clicked)
        self._btn_run_cleanup.clicked.connect(
            self._on_run_cleanup_clicked)

    # =================================================================
    #  Deferred init
    # =================================================================

    def _deferred_init(self):
        """Runs after Maya's event queue is clear."""
        try:
            self._ctrl.init()
        except RuntimeError:
            return  # Window was closed before deferred init fired
        self._node_sel.set_language_checked(current_language())
        self._pose_editor.set_auto_fill(self._ctrl.auto_fill)
        # M_TABBED_EDITOR_INTEGRATION: filter persistence per
        # driver/driven role lived on the legacy AttributeList
        # widgets - the tabbed editors don't expose a per-role
        # filter dict (each tab's QListWidget is a flat keyable
        # multi-select). The filter optionVar state is preserved
        # by the controller; nothing to push into the UI here.

    # =================================================================
    #  Node selector handlers
    # =================================================================

    def _on_refresh(self):
        self._show_busy(True)
        self._ctrl.refresh_nodes()
        self._show_busy(False)

    def _on_pick_sel(self):
        result = self._ctrl.pick_selected()
        if result:
            self._node_sel.set_current_node(result)

    def _on_create_node(self):
        name = self._ctrl.create_node()
        self._node_sel.set_current_node(name)

    def _on_delete_node(self):
        self._ctrl.delete_node()

    def _on_nodes_refreshed(self, names):
        """M_P0_REFRESH_KEEPS_CURRENT (2026-04-30): the upstream
        ``set_nodes`` rebuilds the combo from scratch (clear + re-
        addItem with ``<None>`` at index 0), defaulting
        ``currentIndex`` to 0. Without the restore call below, the
        UI display drifts away from the controller's authoritative
        ``_current_node`` and the user sees the combo blank-out on
        every Refresh click — every downstream operation that
        consults ``node_selector.current_node()`` then misreads
        the active node as "none".

        Idempotent fail-soft: if the saved node name is no longer
        in the rebuilt list (e.g. the user deleted the node in the
        outliner before clicking Refresh), ``set_current_node``'s
        ``findText`` returns -1 and the call is a no-op. The combo
        falls back to ``<None>`` cleanly without touching the
        controller's ``_current_node`` — the controller only
        learns about the deletion through the next user-initiated
        node action.

        Signal suppression: ``set_current_node`` calls
        ``setCurrentIndex`` under the hood which would fire
        ``currentTextChanged -> ctrl.on_node_changed`` with a name
        that already equals ``ctrl._current_node`` — a spurious
        trigger that re-runs ``_load_settings + _load_editor``
        unnecessarily on every Refresh click. Wrapping the restore
        in ``_combo.blockSignals`` suppresses the redundant cascade
        without touching ``node_selector.py`` (the private access
        is the pragmatic carve-out — adding a ``set_current_node_
        silent`` public helper would be a wider API change).
        """
        self._node_sel.set_nodes(names)
        # Pragmatic private-member access (carve-out): keep
        # node_selector.py untouched while still suppressing the
        # currentTextChanged side-effect of the restore call.
        combo = self._node_sel._combo
        blocked = combo.blockSignals(True)
        try:
            self._node_sel.set_current_node(self._ctrl.current_node)
        finally:
            combo.blockSignals(blocked)

    # =================================================================
    #  Settings load
    # =================================================================

    def _on_settings_loaded(self, data):
        """Receive settings dict from controller, populate sections."""
        for w in (self._general, self._va_section, self._rbf_section):
            w.blockSignals(True)
        self._general.load(data)
        self._va_section.load(data)
        self._rbf_section.load(data)
        for w in (self._general, self._va_section, self._rbf_section):
            w.blockSignals(False)
        self._update_type_visibility(self._general.current_type())

    # =================================================================
    #  Type toggle (VA vs RBF visibility)
    # =================================================================

    def _on_type_changed(self, idx):
        self._ctrl.set_attribute("type", idx)
        self._update_type_visibility(idx)

    def _update_type_visibility(self, idx):
        """Show/hide VA and RBF sections based on the node type index."""
        is_va  = (idx == 0)
        is_rbf = (idx == 1)
        self._va_section.setVisible(is_va)
        self._rbf_section.setVisible(is_rbf)
        self._pose_editor.setVisible(is_rbf)
        self._general.set_icon_size_visible(is_va)

    # =================================================================
    #  Radius state
    # =================================================================

    def _on_radius_updated(self, value, radius_enabled, rtype_enabled):
        self._rbf_section.set_radius_value(value)
        self._rbf_section.set_radius_enabled(radius_enabled)
        self._rbf_section.set_radius_type_enabled(rtype_enabled)

    # =================================================================
    #  Pose editor — attribute list management
    # =================================================================

    def _on_select_node_for_role(self, role):
        """M_TABBED_EDITOR_INTEGRATION (2026-04-27): legacy slot
        kept as no-op. The tabbed driver / driven editors handle
        per-tab Select via their own selectNodeRequested signals
        (-> _bind_source_node_from_selection); the pose-editor
        panel no longer carries a single-source AttributeList
        whose Select button this slot used to service."""
        return

    # =================================================================
    #  M_UIRECONCILE — DriverSourceListEditor slot wiring
    # =================================================================

    def _on_driver_source_add_requested(self):
        """M_UIRECONCILE (decision A.2 + Hardening 3) +
        M_TABBED_ADD_GUARD (2026-04-27): batch-add every transform
        in the current Maya selection as a driverSource entry on
        the active node, **dedup-filtered against existing
        driverSource[]**. The current RBFtools shape is filtered
        out so a node never wires itself as its own driver. Driver
        attrs are left empty - the TD configures them per-tab via
        Connect once the tab is materialised by the post-mutation
        reload.

        Pre-flight check (M_TABBED_ADD_GUARD): selected transforms
        that are already in the active node's driverSource[] are
        skipped + surfaced in a notice dialog. If every selected
        transform is already a source, the operation short-
        circuits with the all-duplicate notice.
        """
        sel = cmds.ls(selection=True, type="transform") or []
        if not sel:
            cmds.warning(tr("warning_driver_source_no_selection"))
            return
        current = self._ctrl.current_node or ""
        current_shape = ""
        if current:
            try:
                from RBFtools import core as _core
                current_shape = _core.get_shape(current) or ""
            except Exception:
                current_shape = ""
        sel_filtered = [
            n for n in sel if n != current and n != current_shape]
        if not sel_filtered:
            cmds.warning(tr("warning_driver_source_self_excluded"))
            return
        new_nodes = self._guard_add_dedup(
            "driver", sel_filtered)
        if not new_nodes:
            return
        for node in new_nodes:
            self._ctrl.add_driver_source(
                node, [], weight=1.0, encoding=0)

    def _on_driver_source_remove_requested(self, index):
        """M_UIRECONCILE: forward the row index to controller's
        path-A confirm + remove flow."""
        self._ctrl.remove_driver_source(int(index))

    # =================================================================
    #  M_DRIVEN_MULTI - DrivenSourceListEditor slot wiring
    # =================================================================

    def _on_driven_source_add_requested(self):
        """M_DRIVEN_MULTI + M_TABBED_ADD_GUARD: batch-add every
        transform in the current Maya selection as a drivenSource
        entry, dedup-filtered against existing drivenSource[].
        Driven attrs left empty - the TD picks them per-tab via
        Connect."""
        sel = cmds.ls(selection=True, type="transform") or []
        if not sel:
            cmds.warning(tr("warning_driven_source_no_selection"))
            return
        current = self._ctrl.current_node or ""
        current_shape = ""
        if current:
            try:
                from RBFtools import core as _core
                current_shape = _core.get_shape(current) or ""
            except Exception:
                current_shape = ""
        sel_filtered = [
            n for n in sel if n != current and n != current_shape]
        if not sel_filtered:
            cmds.warning(tr("warning_driver_source_self_excluded"))
            return
        new_nodes = self._guard_add_dedup(
            "driven", sel_filtered)
        if not new_nodes:
            return
        for node in new_nodes:
            self._ctrl.add_driven_source(node, [])

    def _guard_add_dedup(self, role, candidates):
        """M_TABBED_ADD_GUARD shared helper. Returns the subset of
        *candidates* that are NOT already in the active node's
        {driver,driven}Source[] list. If ALL candidates are already
        sources, surfaces an all-duplicate notice and returns []
        (caller short-circuits). If only some are duplicates,
        surfaces a some-skipped notice and returns the new ones.
        If none are duplicates, returns the candidates unchanged
        (no dialog)."""
        try:
            existing = (self._ctrl.read_driver_sources()
                        if role == "driver"
                        else self._ctrl.read_driven_sources())
        except Exception:
            existing = []
        existing_nodes = {s.node for s in existing}
        already = [n for n in candidates if n in existing_nodes]
        new_nodes = [n for n in candidates if n not in existing_nodes]
        if not already:
            return new_nodes
        title_key = ("title_driver_already_added"
                     if role == "driver"
                     else "title_driven_already_added")
        if not new_nodes:
            msg_key = ("msg_driver_all_already_added"
                       if role == "driver"
                       else "msg_driven_all_already_added")
            QtWidgets.QMessageBox.information(
                self,
                tr(title_key),
                tr(msg_key).format(nodes=", ".join(already)))
            return []
        msg_key = ("msg_driver_some_already_added"
                   if role == "driver"
                   else "msg_driven_some_already_added")
        QtWidgets.QMessageBox.information(
            self,
            tr(title_key),
            tr(msg_key).format(
                skipped=", ".join(already),
                added=", ".join(new_nodes)))
        return new_nodes

    def _on_driven_source_remove_requested(self, index):
        self._ctrl.remove_driven_source(int(index))

    # M_CONNECT_DISCONNECT_FIX (2026-04-28): driven mirror of
    # _on_driver_source_attrs_apply / _clear. Same plan-dict
    # guard + 3-scene dispatcher; only the controller method
    # binding switches to the driven side.

    def _on_driven_source_attrs_apply(self, index, attrs):
        """M_CONNECT_DISCONNECT_FIX Bug 1 driven mirror — same
        overlap-aware dispatch as the driver side."""
        plan = self._guard_attrs_apply(
            "driven", int(index), list(attrs))
        if plan is None:
            return
        if plan["overlapping"]:
            cmds.warning(
                "Connect (driven[{}]): overlapping attrs {!r} will "
                "be re-bound in user selection order; new attrs "
                "{!r} will be appended.".format(
                    index, plan["overlapping"], plan["new"]))
        self._ctrl.set_driven_source_attrs(int(index), list(attrs))

    def _on_driven_source_attrs_clear(self, index, attrs):
        """M_CONNECT_DISCONNECT_FIX Bug 2 driven mirror — Scene
        A/B/C dispatch identical to the driver side."""
        sources = self._ctrl.read_driven_sources()
        if not (0 <= index < len(sources)):
            return
        existing_attrs = list(sources[int(index)].attrs)
        if not existing_attrs:
            QtWidgets.QMessageBox.information(
                self,
                tr("title_nothing_to_disconnect"),
                tr("msg_nothing_to_disconnect"))
            return
        target_attrs = list(attrs) if attrs else None
        self._ctrl.disconnect_driven_source_attrs(
            int(index), target_attrs)

    def _on_driven_source_select_node(self, index):
        """M_SELECT_SEMANTIC_FIX driven mirror. Selects the
        driven source's node in the Maya viewport."""
        self._select_source_node_in_viewport("driven", int(index))

    def _reload_driven_sources(self):
        """M_DRIVEN_MULTI / M_TABBED_EDITOR: reload the tabbed driven
        editor from the controller's current driven_sources state +
        pre-resolve each source's available attrs via cmds.listAttr."""
        try:
            sources = list(self._ctrl.read_driven_sources())
        except Exception:
            sources = []
        available_per_source = self._resolve_available_attrs_per_source(
            sources)
        try:
            self._driven_source_list.set_sources(
                sources, available_attrs_per_source=available_per_source)
        except AttributeError:
            pass
        # Phase 2: cascade into the pose grid as well.
        self._refresh_pose_grid()

    # ----- Phase 2 PoseGridEditor helpers + slots --------------------

    def _refresh_pose_grid(self):
        """Push the active node's driver / driven sources + poses
        into the embedded PoseGridEditor so its column structure
        + per-row spinboxes track the latest state."""
        # M_CRASH_FIX defense 3: skip during a batch storm. Caller
        # invokes a single consolidated refresh after the storm.
        if getattr(self, "_is_updating", False) is True:
            return
        try:
            drv_sources = list(self._ctrl.read_driver_sources())
        except Exception:
            drv_sources = []
        try:
            dvn_sources = list(self._ctrl.read_driven_sources())
        except Exception:
            dvn_sources = []
        # Pose data lives on the controller's pose model.
        poses = []
        try:
            for r in range(self._ctrl.pose_model.rowCount()):
                p = self._ctrl.pose_model.get_pose(r)
                if p is not None:
                    poses.append(p)
        except (AttributeError, Exception):
            poses = []
        self._pose_editor.reload_pose_grid(
            drv_sources, dvn_sources, poses)
        # Commit 3: BaseDrivenPose tab piggy-backs on the same
        # cascade so both tabs stay in lockstep with the active node.
        self._refresh_base_pose_panel()

    def _on_pose_grid_recall(self, pose_index):
        """Phase 2: PoseGridEditor row Go to Pose -> recall_pose."""
        drv_node, dvn_node, drv_attrs, dvn_attrs = (
            self._gather_role_info())
        self._ctrl.recall_pose(
            int(pose_index), drv_node, dvn_node, drv_attrs, dvn_attrs)

    def _on_pose_grid_update(self, pose_index):
        """M_P0_UPDATE_BUTTON_REVERSED (2026-04-30): per-row Update
        button click -> ctrl.update_pose (re-capture current
        viewport driver/driven values into the existing pose row).

        Sibling to :meth:`_on_pose_grid_recall` (the inverse
        Go-to-Pose path). Pre-fix the per-row Update button was
        misrouted through poseRecallRequested + this same slot's
        recall sibling, making the button literally function as a
        second "Go to Pose" instead of as an Update.

        Pose-index passes straight through to ctrl.update_pose's
        ``row`` arg — the pose model's row order matches the
        packed pose_index since :func:`apply_poses` writes
        sequential indices."""
        drv_node, dvn_node, drv_attrs, dvn_attrs = (
            self._gather_role_info())
        self._ctrl.update_pose(
            int(pose_index), drv_node, dvn_node, drv_attrs, dvn_attrs)

    def _on_pose_grid_delete(self, pose_index):
        """Phase 2: PoseGridEditor row delete (right-click menu)."""
        self._ctrl.delete_pose(int(pose_index))
        self._refresh_pose_grid()

    def _on_pose_grid_delete_all(self):
        """Phase 2: PoseGridEditor 'Delete Poses' button - clears
        every pose row from the model."""
        try:
            n = self._ctrl.pose_model.rowCount()
        except (AttributeError, Exception):
            n = 0
        for r in range(n - 1, -1, -1):
            self._ctrl.delete_pose(r)
        self._refresh_pose_grid()

    # Commit 3 (C2 semantic refactor) ---------------------------------

    def _flat_attr_index(self, sources, source_idx, attr_name):
        """Map (source_idx, attr_name) -> flat_idx in the side's flat
        concat. Returns -1 if the lookup fails (caller silently no-ops)."""
        try:
            base = sum(len(s.attrs) for s in sources[:int(source_idx)])
            local = list(sources[int(source_idx)].attrs).index(
                str(attr_name))
            return int(base) + int(local)
        except (IndexError, ValueError, AttributeError, TypeError):
            return -1

    def _on_pose_grid_value_changed_v2(self, pose_idx, side,
                                       source_idx, attr_name, value):
        """C2 semantic slot: live edit of a Pose-tab spinbox. Maps
        (source_idx, attr_name) onto the flat index expected by
        ``PoseData.inputs / values``, then pushes through the model."""
        if int(pose_idx) == -1:
            # BasePose sentinel — should arrive via baseValueChangedV2,
            # not here. Defensive: drop silently rather than corrupt
            # pose[0].
            return
        try:
            pose = self._ctrl.pose_model.get_pose(int(pose_idx))
        except (AttributeError, Exception):
            return
        if pose is None:
            return
        try:
            drv_sources = list(self._ctrl.read_driver_sources())
            dvn_sources = list(self._ctrl.read_driven_sources())
        except Exception:
            drv_sources, dvn_sources = [], []
        sources = drv_sources if side == "input" else dvn_sources
        flat_idx = self._flat_attr_index(
            sources, source_idx, attr_name)
        if flat_idx < 0:
            return
        new_inputs = list(pose.inputs)
        new_values = list(pose.values)
        if side == "input" and flat_idx < len(new_inputs):
            new_inputs[flat_idx] = float(value)
        elif side == "value" and flat_idx < len(new_values):
            new_values[flat_idx] = float(value)
        try:
            self._ctrl.pose_model.update_pose_values(
                int(pose_idx), new_inputs, new_values)
        except AttributeError:
            pass

    def _on_pose_grid_radius_changed(self, pose_idx, new_radius):
        """Commit 3 (M_PER_POSE_SIGMA): green Radius spin live edit ->
        ``shape.poseRadius[i]`` plug write + pose_model sync. Closes
        the loop with the C++ Commit 0/0b vectorised σ math."""
        try:
            self._ctrl.set_pose_radius(int(pose_idx), float(new_radius))
        except (AttributeError, Exception):
            pass

    def _on_base_pose_value_changed(self, _pose_idx, side,
                                    source_idx, attr_name, value):
        """Commit 3 (M_BASE_POSE): BasePose driven-side spinbox edit.
        Driver-side edits (``side == 'input'``) are filtered out — the
        BasePose row's driver clusters are disabled but we guard
        defensively.  Updates ``shape.basePoseValue[flat_idx]`` and
        the underlying scene attr stays in sync via the C++ post-solve
        add-back."""
        if side != "value":
            return
        try:
            dvn_sources = list(self._ctrl.read_driven_sources())
        except Exception:
            dvn_sources = []
        flat_idx = self._flat_attr_index(
            dvn_sources, source_idx, attr_name)
        if flat_idx < 0:
            return
        try:
            self._ctrl.set_base_pose_value(flat_idx, float(value))
        except (AttributeError, Exception):
            pass

    def _on_base_pose_recall(self):
        """Commit 3 (M_BASE_POSE): BasePose 'Go to Pose' -> apply
        baseline values to the active driven node attrs."""
        try:
            self._ctrl.recall_base_pose()
        except (AttributeError, Exception):
            pass

    def _refresh_base_pose_panel(self):
        """Push read_base_pose_values into the BasePoseEditor."""
        # M_CRASH_FIX defense 3: skip during a batch storm.
        if getattr(self, "_is_updating", False) is True:
            return
        try:
            drv_sources = list(self._ctrl.read_driver_sources())
        except Exception:
            drv_sources = []
        try:
            dvn_sources = list(self._ctrl.read_driven_sources())
        except Exception:
            dvn_sources = []
        try:
            base_values = list(self._ctrl.read_base_pose_values())
        except (AttributeError, Exception):
            base_values = []
        self._pose_editor.reload_base_pose(
            drv_sources, dvn_sources, base_values)

    # ----- Phase 3 Utility slot handlers -----------------------------

    def _on_split_solver_clicked(self):
        """Phase 3 Utility: forward to controller stub which surfaces
        a 'deferred' warning. UI is wired so the AnimaRbfSolver
        layout matches the reference; the splitter logic itself
        lands separately."""
        self._ctrl.split_solver_for_each_joint()

    def _on_run_cleanup_clicked(self):
        """Phase 3 Utility: dispatch to the active cleanup radio's
        controller method + surface a status message with the count
        removed."""
        idx = self._cleanup_group.checkedId()
        if idx == 0:
            n = self._ctrl.cleanup_remove_connectionless_inputs()
            key = "status_cleanup_input_removed"
        elif idx == 1:
            n = self._ctrl.cleanup_remove_connectionless_outputs()
            key = "status_cleanup_output_removed"
        elif idx == 2:
            n = self._ctrl.cleanup_remove_redundant_poses()
            key = "status_cleanup_pose_removed"
        else:
            return
        try:
            self._show_status(tr(key).format(n=int(n or 0)))
        except (AttributeError, KeyError):
            pass

    def _resolve_available_attrs_per_source(self, sources):
        """M_TABBED_EDITOR helper: for each source's node, resolve
        the keyable attribute list via cmds.listAttr (with the same
        scalar-then-keyable fallback used by the M_UIRECONCILE_PLUS
        picker). Returns a parallel list of attr-name lists."""
        out = []
        for src in sources or []:
            node = getattr(src, "node", "") or ""
            if not node:
                out.append([])
                continue
            try:
                attrs = cmds.listAttr(
                    node, keyable=True, scalar=True) or []
            except Exception:
                attrs = []
            if not attrs:
                try:
                    attrs = cmds.listAttr(node, keyable=True) or []
                except Exception:
                    attrs = []
            out.append(list(attrs))
        return out

    def _on_driver_source_attrs_apply(self, index, attrs):
        """M_CONNECT_DISCONNECT_FIX Bug 1 (2026-04-28): Connect
        button on a driver tab. Replaces the legacy
        M_TABBED_CONNECT_GUARD unconditional "already connected
        -> block" path with the user-spec A.3 / B.1 overlap-aware
        dispatch:

          * empty selection           -> info dialog + abort
          * any non-empty selection   -> proceed; controller's
            set_driver_source_attrs handles overlapping (break-then-
            rebuild via _disconnect_or_purge) AND pure-new (append)
            uniformly. The plan-dict surfaces overlapping attrs as
            cmds.warning trace so the TD can see what was reset.
        """
        plan = self._guard_attrs_apply(
            "driver", int(index), list(attrs))
        if plan is None:
            return  # blocked: empty selection
        if plan["overlapping"]:
            cmds.warning(
                "Connect (driver[{}]): overlapping attrs {!r} will "
                "be re-bound in user selection order; new attrs "
                "{!r} will be appended.".format(
                    index, plan["overlapping"], plan["new"]))
        self._ctrl.set_driver_source_attrs(int(index), list(attrs))

    def _on_driver_source_attrs_clear(self, index, attrs):
        """M_CONNECT_DISCONNECT_FIX Bug 2 (2026-04-28): Disconnect
        button on a driver tab. Three-scene dispatcher per user
        spec D.1 + D.2 + D.3 (加固 4):

          D.1 attrs non-empty       -> precise disconnect
          D.2 attrs empty           -> full-source disconnect
          D.3 source has 0 attrs    -> info dialog "nothing to
                                       disconnect"
        """
        sources = self._ctrl.read_driver_sources()
        if not (0 <= index < len(sources)):
            return
        existing_attrs = list(sources[int(index)].attrs)
        # D.3 — nothing currently connected.
        if not existing_attrs:
            QtWidgets.QMessageBox.information(
                self,
                tr("title_nothing_to_disconnect"),
                tr("msg_nothing_to_disconnect"))
            return
        # D.1 vs D.2: attrs list non-empty -> precise; empty -> None
        # so the controller / core path branches to full-source
        # disconnect.
        target_attrs = list(attrs) if attrs else None
        self._ctrl.disconnect_driver_source_attrs(
            int(index), target_attrs)

    # ----- M_CONNECT_DISCONNECT_FIX: shared guard helpers ------------

    # ----- M_BATCH_PATH_A_WIRE: cross-tab broadcast slots ------------
    # 2026-04-28 — fired by tabbed_source_editor when its bottom-
    # of-panel _chk_batch is checked. The slot iterates every tab
    # in the panel and applies the same attrs (a "blueprint"
    # broadcast — same pattern the path-B PoseGridEditor flow
    # already uses via _gather_routed_targets). Reuses the
    # M_REBUILD_REFACTOR-locked controller APIs (incremental diff +
    # _disconnect_or_purge atomic protocol — no path-A logic to
    # duplicate here).

    def _batch_apply(self, role, attrs):
        """Shared driver/driven Connect-batch implementation.

        ``role`` is ``"driver"`` or ``"driven"``; ``attrs`` is the
        blueprint attr list captured from the active tab. Empty
        attrs -> info dialog (parity with single-tab path).
        Otherwise surfaces a confirm dialog (batch is multi-tab
        destructive, must be explicit) before iterating sources.
        """
        if not attrs:
            QtWidgets.QMessageBox.information(
                self,
                tr("title_no_attrs_selected"),
                tr("msg_no_attrs_selected"))
            return
        sources = (self._ctrl.read_driver_sources()
                   if role == "driver"
                   else self._ctrl.read_driven_sources())
        if not sources:
            return
        proceed = QtWidgets.QMessageBox.question(
            self,
            tr("title_batch_apply_confirm"),
            tr("msg_batch_apply_confirm").format(
                count=len(sources),
                attrs=", ".join(attrs)),
            QtWidgets.QMessageBox.Yes |
            QtWidgets.QMessageBox.No)
        if proceed != QtWidgets.QMessageBox.Yes:
            return
        for idx in range(len(sources)):
            try:
                if role == "driver":
                    self._ctrl.set_driver_source_attrs(
                        idx, list(attrs))
                else:
                    self._ctrl.set_driven_source_attrs(
                        idx, list(attrs))
            except Exception as exc:
                cmds.warning(
                    "_batch_apply ({}[{}]): {}".format(
                        role, idx, exc))

    def _batch_clear(self, role, attrs):
        """Shared driver/driven Disconnect-batch implementation.

        attrs non-empty -> Scene A precise; empty -> Scene B full
        per-source clear. Confirm dialog gates the multi-tab
        destruction either way."""
        sources = (self._ctrl.read_driver_sources()
                   if role == "driver"
                   else self._ctrl.read_driven_sources())
        if not sources:
            QtWidgets.QMessageBox.information(
                self,
                tr("title_nothing_to_disconnect"),
                tr("msg_nothing_to_disconnect"))
            return
        attrs_label = (", ".join(attrs)
                       if attrs
                       else tr("all_attrs"))
        proceed = QtWidgets.QMessageBox.question(
            self,
            tr("title_batch_clear_confirm"),
            tr("msg_batch_clear_confirm").format(
                count=len(sources),
                attrs=attrs_label),
            QtWidgets.QMessageBox.Yes |
            QtWidgets.QMessageBox.No)
        if proceed != QtWidgets.QMessageBox.Yes:
            return
        target_attrs = list(attrs) if attrs else None
        for idx in range(len(sources)):
            try:
                if role == "driver":
                    self._ctrl.disconnect_driver_source_attrs(
                        idx, target_attrs)
                else:
                    self._ctrl.disconnect_driven_source_attrs(
                        idx, target_attrs)
            except Exception as exc:
                cmds.warning(
                    "_batch_clear ({}[{}]): {}".format(
                        role, idx, exc))

    def _on_driver_source_attrs_apply_batch(self, attrs):
        self._batch_apply("driver", list(attrs))

    def _on_driver_source_attrs_clear_batch(self, attrs):
        self._batch_clear("driver", list(attrs))

    def _on_driven_source_attrs_apply_batch(self, attrs):
        self._batch_apply("driven", list(attrs))

    def _on_driven_source_attrs_clear_batch(self, attrs):
        self._batch_clear("driven", list(attrs))

    def _guard_attrs_apply(self, role, index, attrs):
        """M_CONNECT_DISCONNECT_FIX 加固 2 (2026-04-28): plan-dict
        return form (not bool). The legacy unconditional
        "already_connected" -> False short-circuit was Bug 1: it
        prevented the user spec 1.3 overlap/append semantics.

        Returns
        -------
        None
            Empty selection — caller MUST short-circuit (an info
            dialog has been surfaced).
        dict
            ``{"overlapping": [...], "new": [...], "existing": [...]}``
            — caller proceeds; routes through
            controller.set_*_source_attrs which handles the
            overlapping vs new split internally (B.1 + 加固 6).
        """
        # Connect with empty selection — still blocks.
        if not attrs:
            QtWidgets.QMessageBox.information(
                self,
                tr("title_no_attrs_selected"),
                tr("msg_no_attrs_selected"))
            return None
        sources = (self._ctrl.read_driver_sources()
                   if role == "driver"
                   else self._ctrl.read_driven_sources())
        existing_attrs = []
        if 0 <= index < len(sources):
            existing_attrs = list(sources[index].attrs)
        overlapping = [a for a in attrs if a in existing_attrs]
        new = [a for a in attrs if a not in existing_attrs]
        return {
            "overlapping": overlapping,
            "new": new,
            "existing": existing_attrs,
        }

    def _on_driver_source_select_node(self, index):
        """M_SELECT_SEMANTIC_FIX (Phase 1, P1 2026-04-27): Select
        button on a driver tab now selects the source's bone in
        the Maya viewport (cmds.select replace=True), letting the
        TD jump to that bone in the scene. The previous behaviour
        was rebind-from-selection; rebind is now achieved by
        closing the tab + Add Driver from a fresh selection."""
        self._select_source_node_in_viewport("driver", int(index))

    def _select_source_node_in_viewport(self, role, index):
        """Shared helper: read the source's node name from the
        controller's current source list + cmds.select it."""
        if role == "driver":
            sources = self._ctrl.read_driver_sources()
        else:
            sources = self._ctrl.read_driven_sources()
        if not (0 <= index < len(sources)):
            return
        node = sources[index].node or ""
        if not node:
            cmds.warning(tr("warning_source_node_empty"))
            return
        if not cmds.objExists(node):
            cmds.warning(tr("warning_source_node_missing").format(
                node=node))
            return
        cmds.select(node, replace=True)

    def _reload_driver_sources(self):
        """M_UIRECONCILE / M_TABBED_EDITOR: reload the tabbed driver
        editor + maintain the pose-editor multi-source banner
        (decision C.1 + Hardening 2 - banner gated on len(sources)
        > 1, single source keeps the legacy AttributeList workflow
        visually unchanged per red line 14 backcompat parity).

        Per-source available attrs are pre-resolved via
        cmds.listAttr so each tab shows the source node's full
        keyable attribute list with the source's existing attrs
        pre-selected."""
        try:
            sources = list(self._ctrl.read_driver_sources())
        except Exception:
            sources = []
        available_per_source = self._resolve_available_attrs_per_source(
            sources)
        self._driver_source_list.set_sources(
            sources, available_attrs_per_source=available_per_source)
        # M_TABBED_EDITOR_INTEGRATION: the multi-source banner is
        # gone (the legacy AttributeList it warned about no longer
        # exists). The tabbed editor IS the multi-source UI - no
        # additional notice needed.
        # Phase 2: cascade the rebuild into the pose grid so its
        # column structure tracks the new driver source list.
        self._refresh_pose_grid()
        # M_ROTORDER_UI_REFACTOR (2026-04-29): driver tabs are the
        # single source of truth for the rotate-order list. Push
        # the live driver-name list into rbf_section + run a one-
        # shot self-heal to truncate / pad the persisted multi.
        self._ctrl._resync_rotate_order_length()
        self._rbf_section.set_driver_sources_for_rotate_order(
            [s.node for s in sources])

    def _on_filters_changed(self, role, filters):
        """M_TABBED_EDITOR_INTEGRATION: filter UX lived on the
        legacy AttributeList right-click menu (now removed). Filter
        state still persists in the controller's optionVar so we
        forward the dict for storage but no longer have a UI to
        repopulate."""
        for k, v in filters.items():
            self._ctrl.set_filter(role, k, v)

    def _refresh_attr_list(self, role):
        """M_TABBED_EDITOR_INTEGRATION: legacy slot kept as no-op.
        Per-tab attribute lists are pre-populated by
        _resolve_available_attrs_per_source during reload."""
        return

    # =================================================================
    #  Pose editor — editor loaded callback
    # =================================================================

    def _on_editor_loaded(self):
        """Called after controller populates the model from the node."""
        model = self._ctrl.pose_model
        # Update delegate column count
        self._delegate.set_input_count(model.n_inputs)
        # Resize columns to content
        tv = self._pose_editor.table_view
        header = tv.horizontalHeader()
        for c in range(model.columnCount()):
            header.setSectionResizeMode(
                c, QtWidgets.QHeaderView.Stretch)
        # M_P0_NODE_SWITCH_POSE_GRID (2026-04-30): controller's
        # _load_editor populates self._ctrl.pose_model from the new
        # node's poses but the view's PoseGridEditor still needs
        # an explicit rebuild to repaint rows. Without this call,
        # switching the active node leaves the pose grid blank
        # while the underlying model is correct — the user-
        # reported "切换节点 pose 行不刷新" P0. Empty-node path
        # (current_node="") is fine: _refresh_pose_grid passes
        # ([], [], []) through to PoseGridEditor.set_data which
        # clears the rows cleanly. The driver / driven editor
        # rebuilds are already wired separately at line 1249 +
        # 1270 (_reload_driver_sources / _reload_driven_sources);
        # this completes the third leg of the editorLoaded
        # cascade.
        self._refresh_pose_grid()

    # =================================================================
    #  Pose CRUD (gather UI state → controller)
    # =================================================================

    def _gather_role_info(self):
        """M_TABBED_EDITOR_INTEGRATION (2026-04-27): aggregate
        driver / driven node + attrs across ALL tabs. The legacy
        single-source AttributeList accessors are gone; the
        controller's multi-source readers are the source of truth.

        Returns the legacy 4-tuple shape (drv_node, dvn_node,
        drv_attrs, dvn_attrs) so existing Apply / Connect / Add
        Pose flows keep working unchanged. For multi-source nodes
        this returns the FIRST source's node + a flat concat of
        every source's attrs (matches the input[]/output[] index
        order produced by add_driver_source / add_driven_source).
        """
        try:
            drv_sources = list(self._ctrl.read_driver_sources())
        except Exception:
            drv_sources = []
        try:
            dvn_sources = list(self._ctrl.read_driven_sources())
        except Exception:
            dvn_sources = []
        drv_node  = drv_sources[0].node if drv_sources else ""
        dvn_node  = dvn_sources[0].node if dvn_sources else ""
        drv_attrs = [a for src in drv_sources for a in src.attrs]
        dvn_attrs = [a for src in dvn_sources for a in src.attrs]
        return drv_node, dvn_node, drv_attrs, dvn_attrs

    def _on_add_pose(self):
        drv_node, dvn_node, drv_attrs, dvn_attrs = self._gather_role_info()
        pose = self._ctrl.add_pose(
            drv_node, dvn_node, drv_attrs, dvn_attrs)
        if pose is not None:
            self._delegate.set_input_count(self._ctrl.pose_model.n_inputs)
            # Phase 2: refresh the grid so the new pose row appears.
            self._refresh_pose_grid()

    def _on_apply(self):
        self._set_interaction_enabled(False)
        try:
            drv_node, dvn_node, drv_attrs, dvn_attrs = self._gather_role_info()
            self._ctrl.apply_poses(
                drv_node, dvn_node, drv_attrs, dvn_attrs)
        finally:
            self._set_interaction_enabled(True)

    def _gather_routed_targets(self):
        """2026-04-28 (M_BATCH_ROUTING + M_CRASH_FIX defense 1 +
        M_LIVE_DEBUG): PURE-STRING UI READ + diagnostic prints.

        Returns ``([(drv_bone, [attr,...]), ...],
        [(dvn_bone, [attr,...]), ...])`` — plain Python data with
        no Qt object references and no cmds calls. Both lists are
        printed to the Script Editor before return so a live-Maya
        operator can confirm which scope reached the controller —
        if the prints do not appear when the Connect button is
        clicked, the user is running stale module cache and needs
        to ``importlib.reload(RBFtools.ui.main_window)`` (or
        relaunch Maya)."""
        drv_editor = self._pose_editor.driver_editor
        dvn_editor = self._pose_editor.driven_editor
        try:
            raw_drv = list(drv_editor.routed_targets())
        except (AttributeError, Exception):
            raw_drv = []
        try:
            raw_dvn = list(dvn_editor.routed_targets())
        except (AttributeError, Exception):
            raw_dvn = []
        driver_targets = [
            (str(node or ""), [str(a) for a in (attrs or [])])
            for node, attrs in raw_drv
        ]
        driven_targets = [
            (str(node or ""), [str(a) for a in (attrs or [])])
            for node, attrs in raw_dvn
        ]
        # M_LIVE_DEBUG: explicit Script-Editor traces so a live
        # operator can verify the new code path is loaded.
        print("[RBFtools] GATHERED DRIVERS: {}".format(driver_targets))
        print("[RBFtools] GATHERED DRIVENS: {}".format(driven_targets))
        return driver_targets, driven_targets

    def _on_connect(self):
        # M_LIVE_DEBUG (2026-04-28): top-of-slot trace so a live
        # operator can confirm the new code path is loaded. Goes
        # to cmds.warning so it appears in Script Editor with the
        # yellow icon even if 'Print all warnings' is off.
        try:
            cmds.warning(">>> ON_CONNECT TRIGGERED <<<")
        except Exception:
            print(">>> ON_CONNECT TRIGGERED <<<")
        # M_CRASH_FIX (2026-04-28) — three-defense protocol:
        #   1. Pure-string gather BEFORE any cmds.* call. Once
        #      _gather_routed_targets returns, the UI is no longer
        #      consulted for the duration of the storm.
        #   2. core.connect_routed wraps the connectAttr loop in
        #      _node_state_frozen so partial-wire compute() cannot
        #      crash the kernel.
        #   3. _is_updating lock blocks _refresh_pose_grid +
        #      _refresh_base_pose_panel re-entry from any node-
        #      change callback that fires mid-storm.
        # Step 1: pure-string gather.
        driver_targets, driven_targets = (
            self._gather_routed_targets())
        # Step 2: enter critical section.
        self._set_interaction_enabled(False)
        self._is_updating = True
        try:
            self._ctrl.connect_routed(
                driver_targets, driven_targets)
        finally:
            self._is_updating = False
            self._set_interaction_enabled(True)
        # Step 3: ONE consolidated refresh outside the lock.
        self._refresh_pose_grid()

    def _on_disconnect(self):
        # M_LIVE_DEBUG: top-of-slot trace. See _on_connect note.
        try:
            cmds.warning(">>> ON_DISCONNECT TRIGGERED <<<")
        except Exception:
            print(">>> ON_DISCONNECT TRIGGERED <<<")
        # M_CRASH_FIX symmetric protocol — same three defenses.
        driver_targets, driven_targets = (
            self._gather_routed_targets())
        self._set_interaction_enabled(False)
        self._is_updating = True
        result = {"disconnected_count": 0}
        try:
            result = self._ctrl.disconnect_routed(
                driver_targets, driven_targets) or result
        finally:
            self._is_updating = False
            self._set_interaction_enabled(True)
        self._refresh_pose_grid()
        # M_BREAK_REBUILD Scene C (2026-04-28): zero disconnects
        # surface a UI dialog so the user never sees "nothing
        # happened". cmds.confirmDialog is layered above Qt so it
        # survives any Qt event-loop quirk.
        if int(result.get("disconnected_count", 0)) == 0:
            try:
                cmds.confirmDialog(
                    title="RBFtools",
                    message=tr("disconnect_no_connections_found"),
                    button=["OK"], defaultButton="OK")
            except Exception:
                cmds.warning(tr(
                    "disconnect_no_connections_found"))

    def _on_reload(self):
        """M_TABBED_EDITOR_INTEGRATION: reload the tabbed driver +
        driven editors from the controller's multi-source state.
        The legacy AttributeList per-role set_node_name +
        select_attributes path is gone; the tabbed editors
        rebuild themselves from controller.read_driver_sources /
        read_driven_sources via the editorLoaded signal subscribed
        in the wiring section, so we only need to (re-)trigger
        the controller-side reload + let the signal cascade do
        the rest."""
        self._ctrl.reload_editor()
        # Reload signals (driverSourcesChanged + drivenSourcesChanged)
        # also fire from controller mutations; here we explicitly
        # call the slots so a manual Reload click rebuilds the
        # tabs even when the source state hasn't changed.
        self._reload_driver_sources()
        self._reload_driven_sources()

    def _on_pose_row_action(self, action, row):
        """Handle Recall / Update / Delete from the table context menu."""
        drv_node, dvn_node, drv_attrs, dvn_attrs = self._gather_role_info()
        if action == "recall":
            self._ctrl.recall_pose(
                row, drv_node, dvn_node, drv_attrs, dvn_attrs)
        elif action == "update":
            self._ctrl.update_pose(
                row, drv_node, dvn_node, drv_attrs, dvn_attrs)
        elif action == "delete":
            self._ctrl.delete_pose(row)

    # =================================================================
    #  Language switch
    # =================================================================

    def _switch_language(self, lang):
        set_language(lang)
        self._retranslate_all()
        self._node_sel.set_language_checked(lang)
        try:
            import RBFtoolsMenu
            RBFtoolsMenu.create()
        except Exception:
            pass

    def _retranslate_all(self):
        self.setWindowTitle(WINDOW_TITLE)
        self._node_sel.retranslate()
        self._general.retranslate()
        self._va_section.retranslate()
        self._rbf_section.retranslate()
        self._pose_editor.retranslate()
        # M_QUICKWINS Item 2: extend retranslate coverage to every
        # persistent widget that carries i18n-bound strings. This
        # closes the language-switch residue gap caught by the
        # 2026-04-27 user report.
        try:
            self._driver_sources_section.set_title(
                tr("section_driver_sources"))
        except (AttributeError, TypeError):
            pass
        try:
            self._driver_source_list.retranslate()
        except AttributeError:
            pass
        # M_DRIVEN_MULTI: refresh the Driven Targets section header +
        # editor on language switch.
        try:
            self._driven_sources_section.set_title(
                tr("section_driven_sources"))
        except (AttributeError, TypeError):
            pass
        try:
            self._driven_source_list.retranslate()
        except AttributeError:
            pass
        try:
            self._output_encoding_combo.retranslate()
        except AttributeError:
            pass
        # The multi-source banner text on the pose editor is set
        # dynamically by _reload_driver_sources; refresh it now if
        # the active node is multi-source.
        self._reload_driver_sources()
        # Live-edit + profile widgets live inside collapsible
        # subsections that may not be instantiated yet (lazy build);
        # try-skip pattern keeps the wiring forward-compatible.
        for attr in ("_live_edit_widget", "_profile_widget"):
            w = getattr(self, attr, None)
            if w is not None:
                try:
                    w.retranslate()
                except AttributeError:
                    pass

    # =================================================================
    #  Status / progress helpers
    # =================================================================

    def _show_status(self, msg):
        """Display a message in the status label (auto-clears after 4s)."""
        self._status_label.setText(msg)
        QtCore.QTimer.singleShot(4000, lambda: self._status_label.setText(""))

    def _set_interaction_enabled(self, enabled):
        """Disable/enable interactive controls to prevent re-entrant calls."""
        self._pose_editor.set_buttons_enabled(enabled)
        self._node_sel.setEnabled(enabled)

    def _show_busy(self, busy):
        """Show / hide the indeterminate progress bar."""
        self._progress.setVisible(busy)


# =====================================================================
#  Singleton management
# =====================================================================

_instance = None


def _is_alive(widget):
    """Return True if *widget* is a live, non-deleted Qt object."""
    if widget is None:
        return False
    try:
        # shiboken: isValid works for both PySide2 and PySide6
        from shiboken2 import isValid
    except ImportError:
        from shiboken6 import isValid
    return isValid(widget)


def show():
    """Show the RBF Tools window (**singleton** pattern).

    * First call  → create window and show.
    * Second call → raise the existing window to the front.
    * If the old C++ object was garbage-collected → recreate.

    Returns
    -------
    RBFToolsWindow
        The singleton window instance.
    """
    global _instance

    # Re-use existing window if it's still alive
    if _is_alive(_instance):
        _instance.show()
        _instance.raise_()
        _instance.activateWindow()
        return _instance

    # Create fresh
    parent = maya_main_window()
    _instance = RBFToolsWindow(parent)
    _instance.setAttribute(QtCore.Qt.WA_DeleteOnClose)
    _instance.show()
    return _instance


def close():
    """Programmatically close the singleton (e.g. for hot-reload)."""
    global _instance
    if _is_alive(_instance):
        _instance.close()
        _instance.deleteLater()
    _instance = None
