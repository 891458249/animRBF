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
from RBFtools.ui.widgets.general_section import GeneralSection
from RBFtools.ui.widgets.output_encoding_combo import OutputEncodingCombo
from RBFtools.ui.widgets.vector_angle_section import VectorAngleSection
from RBFtools.ui.widgets.rbf_section import RBFSection
from RBFtools.ui.widgets.collapsible import CollapsibleFrame
from RBFtools.ui.widgets.attribute_list import AttributeList
from RBFtools.ui.widgets.help_button import HelpButton


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

        # Auto-fill
        row_auto = QtWidgets.QHBoxLayout()
        self._cb_auto = QtWidgets.QCheckBox(tr("auto_fill_bs"))
        self._cb_auto.toggled.connect(self.autoFillChanged)
        row_auto.addWidget(self._cb_auto)
        row_auto.addStretch()
        row_auto.addWidget(HelpButton("auto_fill_bs"))
        lay.addLayout(row_auto)

        lay.addWidget(_hline())

        # Driver / Driven split via QSplitter
        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        self._driver_list = AttributeList("driver")
        self._driven_list = AttributeList("driven")
        splitter.addWidget(self._driver_list)
        splitter.addWidget(self._driven_list)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        lay.addWidget(splitter)

        self._driver_list.selectNodeRequested.connect(
            lambda: self.selectNodeRequested.emit("driver"))
        self._driven_list.selectNodeRequested.connect(
            lambda: self.selectNodeRequested.emit("driven"))
        self._driver_list.filtersChanged.connect(self.filtersChanged)
        self._driven_list.filtersChanged.connect(self.filtersChanged)

        lay.addWidget(_hline())

        # Pose label
        self._lbl_poses = QtWidgets.QLabel(tr("poses"))
        self._lbl_poses.setStyleSheet("font-weight: bold;")
        lay.addWidget(self._lbl_poses)

        # QTableView (bound to PoseTableModel by the window)
        self._table = QtWidgets.QTableView()
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectRows)
        self._table.setSelectionMode(
            QtWidgets.QAbstractItemView.SingleSelection)
        self._table.verticalHeader().setVisible(False)
        hdr = self._table.horizontalHeader()
        hdr.setStretchLastSection(True)
        hdr.setDefaultSectionSize(70)
        self._table.setMinimumHeight(160)
        lay.addWidget(self._table, 1)

        # Per-row action buttons are handled by the delegate / context
        # menu rather than embedded widgets — keeps the model clean.
        # Context menu on right-click:
        self._table.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._show_row_menu)

        lay.addWidget(_hline())

        # Bottom buttons
        btn_row = QtWidgets.QHBoxLayout()
        self._btn_add        = QtWidgets.QPushButton(tr("add_pose"))
        self._btn_apply      = QtWidgets.QPushButton(tr("apply"))
        self._btn_connect    = QtWidgets.QPushButton(tr("connect"))
        self._btn_disconnect = QtWidgets.QPushButton(tr("disconnect"))
        self._btn_reload     = QtWidgets.QPushButton(tr("reload"))

        for btn, key in [
            (self._btn_add, "add_pose"),
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
        lay.addLayout(btn_row)

    # -- public --

    @property
    def table_view(self):
        return self._table

    @property
    def driver_list(self):
        return self._driver_list

    @property
    def driven_list(self):
        return self._driven_list

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
        self._driver_list.retranslate()
        self._driven_list.retranslate()
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
        # M_B24b1: multi-source driver section (B2 + B4 UI primary
        # deliverable per user override 2026-04-26).
        # M_UIRECONCILE (decision C.1 + D.1): default to expanded so
        # the wired multi-source editor is the first thing the TD
        # sees; the section header label dropped the "(preview)"
        # qualifier in the i18n dictionary.
        self._driver_sources_section = CollapsibleFrame(
            tr("section_driver_sources"), collapsed=False)
        self._driver_source_list = DriverSourceListEditor()
        self._output_encoding_combo = OutputEncodingCombo()
        self._driver_sources_section.add_widget(self._driver_source_list)
        _oe_row = QtWidgets.QHBoxLayout()
        _oe_row.addWidget(QtWidgets.QLabel(tr("output_encoding_label")))
        _oe_row.addWidget(self._output_encoding_combo, 1)
        self._driver_sources_section.add_layout(_oe_row)
        self._pose_editor = _PoseEditorPanel()

        self._sections.addWidget(self._general)
        self._sections.addWidget(self._va_section)
        self._sections.addWidget(self._rbf_section)
        self._sections.addWidget(self._driver_sources_section)
        self._sections.addWidget(self._pose_editor)
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

        # Row context-menu callback
        pe._row_action_callback = self._on_pose_row_action

        # ---- M_UIRECONCILE: DriverSourceListEditor wiring -----------
        # Closes the M_B24b1 island-widget gap (see addendum
        # §M_UIRECONCILE.m_b24b1-correction). The widget emits
        # request signals; main_window owns the cmds.ls call and
        # delegates to controller.add_driver_source /
        # remove_driver_source, then reloads via the controller's
        # driverSourcesChanged signal (decision F.1, MVC clean).
        self._driver_source_list.addRequested.connect(
            self._on_driver_source_add_requested)
        self._driver_source_list.removeRequested.connect(
            self._on_driver_source_remove_requested)
        ctrl.driverSourcesChanged.connect(self._reload_driver_sources)
        ctrl.editorLoaded.connect(self._reload_driver_sources)
        ctrl.nodesRefreshed.connect(
            lambda _names: self._reload_driver_sources())

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
        # Load filter states
        for al in (self._pose_editor.driver_list,
                   self._pose_editor.driven_list):
            al.set_filters(self._ctrl.get_filters(al.role))

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
        self._node_sel.set_nodes(names)

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
        sel = cmds.ls(selection=True) or []
        if not sel:
            return
        al = (self._pose_editor.driver_list if role == "driver"
              else self._pose_editor.driven_list)
        al.set_node_name(sel[0])
        self._refresh_attr_list(role)

    # =================================================================
    #  M_UIRECONCILE — DriverSourceListEditor slot wiring
    # =================================================================

    def _on_driver_source_add_requested(self):
        """M_UIRECONCILE (decision A.2 + Hardening 3): batch-add
        every transform in the current Maya selection as a
        driverSource entry on the active node. Driver attrs are
        left empty - the TD configures them per-row via the
        widget once the row is materialised by the post-mutation
        reload. The current RBFtools shape is filtered out so a
        node never wires itself as its own driver."""
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
        for node in sel_filtered:
            self._ctrl.add_driver_source(
                node, [], weight=1.0, encoding=0)
        # The controller emits driverSourcesChanged inside each
        # add_driver_source call - the reload slot fires
        # automatically; no explicit call needed here.

    def _on_driver_source_remove_requested(self, index):
        """M_UIRECONCILE: forward the row index to controller's
        path-A confirm + remove flow."""
        self._ctrl.remove_driver_source(int(index))

    def _reload_driver_sources(self):
        """M_UIRECONCILE: reload DriverSourceListEditor + maintain
        the pose-editor multi-source banner (decision C.1 +
        Hardening 2 - banner gated on len(sources) > 1, single
        source keeps the legacy AttributeList workflow visually
        unchanged per red line 14 backcompat parity)."""
        try:
            sources = list(self._ctrl.read_driver_sources())
        except Exception:
            sources = []
        self._driver_source_list.set_sources(sources)
        try:
            if len(sources) > 1:
                self._pose_editor.show_multi_source_banner(
                    tr("banner_multi_source_detected"))
            else:
                self._pose_editor.hide_multi_source_banner()
        except AttributeError:
            # pose_editor banner support is added by P2 below; this
            # branch keeps the wiring forward-compatible if the
            # banner methods land in a follow-up commit.
            pass

    def _on_filters_changed(self, role, filters):
        for k, v in filters.items():
            self._ctrl.set_filter(role, k, v)
        al = (self._pose_editor.driver_list if role == "driver"
              else self._pose_editor.driven_list)
        al.set_filters(filters)
        self._refresh_attr_list(role)

    def _refresh_attr_list(self, role):
        al = (self._pose_editor.driver_list if role == "driver"
              else self._pose_editor.driven_list)
        node_name = al.node_name()
        if not node_name:
            al.set_attributes([])
            return
        attrs = self._ctrl.list_attributes(node_name, al.filters())
        al.set_attributes(attrs)

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

    # =================================================================
    #  Pose CRUD (gather UI state → controller)
    # =================================================================

    def _gather_role_info(self):
        """Read driver/driven nodes + selected attrs from the UI."""
        pe = self._pose_editor
        drv_node  = pe.driver_list.node_name()
        dvn_node  = pe.driven_list.node_name()
        drv_attrs = pe.driver_list.selected_attributes()
        dvn_attrs = pe.driven_list.selected_attributes()
        return drv_node, dvn_node, drv_attrs, dvn_attrs

    def _on_add_pose(self):
        drv_node, dvn_node, drv_attrs, dvn_attrs = self._gather_role_info()
        pose = self._ctrl.add_pose(
            drv_node, dvn_node, drv_attrs, dvn_attrs)
        if pose is not None:
            self._delegate.set_input_count(self._ctrl.pose_model.n_inputs)

    def _on_apply(self):
        self._set_interaction_enabled(False)
        try:
            drv_node, dvn_node, drv_attrs, dvn_attrs = self._gather_role_info()
            self._ctrl.apply_poses(
                drv_node, dvn_node, drv_attrs, dvn_attrs)
        finally:
            self._set_interaction_enabled(True)

    def _on_connect(self):
        self._set_interaction_enabled(False)
        try:
            drv_node, dvn_node, drv_attrs, dvn_attrs = self._gather_role_info()
            self._ctrl.connect_poses(
                drv_node, dvn_node, drv_attrs, dvn_attrs)
        finally:
            self._set_interaction_enabled(True)

    def _on_disconnect(self):
        self._set_interaction_enabled(False)
        try:
            self._ctrl.disconnect_outputs()
        finally:
            self._set_interaction_enabled(True)

    def _on_reload(self):
        result = self._ctrl.reload_editor()
        if result:
            driver_node, driver_attrs, driven_node, driven_attrs = result
            pe = self._pose_editor
            pe.driver_list.set_node_name(driver_node)
            pe.driven_list.set_node_name(driven_node)
            if driver_node:
                self._refresh_attr_list("driver")
                pe.driver_list.select_attributes(driver_attrs)
            if driven_node:
                self._refresh_attr_list("driven")
                pe.driven_list.select_attributes(driven_attrs)

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
