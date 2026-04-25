# -*- coding: utf-8 -*-
"""
MainController — the **sole bridge** between the UI layer and
:mod:`RBFtools.core`.

Responsibilities
----------------
* Holds application state (current node, auto-fill toggle).
* Owns the :class:`PoseTableModel` instance.
* Exposes **public methods** that UI signal handlers call.
* Calls ``core.*`` functions and updates the model accordingly.
* Emits Qt signals so the view can react (e.g. refresh node list).

The UI (main_window + widgets) must **never** import ``core`` directly.
Everything flows through this controller.

Thread safety
-------------
All methods are designed to run on Maya's main thread.
``maya.cmds`` is not thread-safe; the controller does **not** spawn
background threads.
"""

from __future__ import absolute_import

import maya.cmds as cmds

from RBFtools.ui.compat import QtCore
from RBFtools.ui.pose_model import PoseTableModel
from RBFtools import core
from RBFtools.constants import (
    AUTO_FILL_OPT_VAR,
    NODE_TYPE,
)


class MainController(QtCore.QObject):
    """Central business-logic dispatcher.

    Signals
    -------
    nodesRefreshed(list)
        Emitted after the scene is scanned for RBFtools nodes.
        Payload is the ordered list of transform names.
    settingsLoaded(dict)
        Emitted with the full settings dict (from ``core.get_all_settings``).
        ``None`` when no node is selected.
    radiusUpdated(float, bool, bool)
        ``(radius_value, radius_enabled, radius_type_enabled)``
        Emitted after kernel / radiusType changes so the view can
        update its spinbox state.
    editorLoaded()
        Emitted after the pose editor has been fully populated from
        the current node.
    statusMessage(str)
        Optional HUD / status-bar message forwarding.
    """

    nodesRefreshed  = QtCore.Signal(list)
    settingsLoaded  = QtCore.Signal(object)       # dict or None
    radiusUpdated   = QtCore.Signal(float, bool, bool)
    editorLoaded    = QtCore.Signal()
    statusMessage   = QtCore.Signal(str)

    def __init__(self, parent=None):
        super(MainController, self).__init__(parent)

        self._current_node = ""
        self._auto_fill    = False

        # The single pose data model — shared with the QTableView
        self._pose_model = PoseTableModel(self)

        self._init_auto_fill()

    # =================================================================
    #  Properties
    # =================================================================

    @property
    def pose_model(self):
        """The :class:`PoseTableModel` instance that the view binds to."""
        return self._pose_model

    @property
    def current_node(self):
        return self._current_node

    @property
    def auto_fill(self):
        return self._auto_fill

    # =================================================================
    #  Initialisation
    # =================================================================

    def _init_auto_fill(self):
        try:
            self._auto_fill = bool(
                cmds.optionVar(query=AUTO_FILL_OPT_VAR))
        except Exception:
            self._auto_fill = False

    def init(self):
        """Run after the controller and view are fully wired.

        Loads the plugin and emits the first ``nodesRefreshed``.
        """
        core.ensure_plugin()
        self.refresh_nodes()

    # =================================================================
    #  1. Node selector actions
    # =================================================================

    def refresh_nodes(self):
        """Re-scan the scene and emit :signal:`nodesRefreshed`."""
        nodes = core.list_all_nodes()
        self.nodesRefreshed.emit(nodes)
        return nodes

    def on_node_changed(self, name):
        """Called when the user picks a different node in the combo."""
        self._current_node = name
        self._load_settings()
        self._load_editor()

    def pick_selected(self):
        """Pick the first selected RBFtools from the viewport.

        Returns
        -------
        str or None
            The transform name that was selected, or ``None``.
        """
        sel = cmds.ls(selection=True) or []
        for s in sel:
            shape = core.get_shape(s)
            if (shape and cmds.objExists(shape)
                    and cmds.nodeType(shape) == NODE_TYPE):
                nodes = self.refresh_nodes()
                transform = core.get_transform(shape)
                self._current_node = transform
                self._load_settings()
                self._load_editor()
                return transform
        cmds.warning("No RBFtools node selected.")
        return None

    def create_node(self):
        """Create a new RBFtools and select it.

        Returns
        -------
        str
            New transform name.
        """
        transform = core.create_node()
        self.refresh_nodes()
        self._current_node = transform
        self._load_settings()
        self._load_editor()
        return transform

    def delete_node(self):
        """Delete the current node."""
        if not self._current_node:
            return
        core.delete_node(self._current_node)
        self._current_node = ""
        self.refresh_nodes()
        self._load_settings()
        self._load_editor()

    # =================================================================
    #  2. Settings read / write
    # =================================================================

    def _load_settings(self):
        """Read all node attributes and emit ``settingsLoaded``."""
        data = core.get_all_settings(self._current_node)
        self.settingsLoaded.emit(data)

    # =================================================================
    #  M3.0 — Shared infrastructure access (addendum §M3.0 path A)
    # =================================================================
    #
    # M3.x sub-tasks reach the StatusProgressController and the
    # ConfirmDialog through the controller, NOT through main_window
    # private members. Keeps the MVC red line clean: sub-task widgets
    # only know the controller, never the window's private layout.

    def set_progress_controller(self, ctrl):
        """Inject the StatusProgressController. Called by main_window
        after ``_build_ui`` finishes (the progress widget is created
        there, AFTER MainController.__init__)."""
        self._status_progress = ctrl

    def progress(self):
        """Return the StatusProgressController, or None when running
        headlessly (no main window) — callers must guard against None
        in test / CI contexts."""
        return getattr(self, "_status_progress", None)

    # =================================================================
    #  M3.2 — Mirror Tool dispatcher (path A consumer)
    # =================================================================

    def mirror_current_node(self, config):
        """Mirror the current node per *config*. First real-world
        consumer of M3.0 path A (ask_confirm + progress).

        Parameters
        ----------
        config : dict
            ``{"target_name": str, "mirror_axis": int,
              "naming_rule_index": int, "custom": (pat, rep) or None,
              "naming_direction": "auto"/"forward"/"reverse"}``

        Returns
        -------
        dict or None
            ``mirror_node`` result on success, None on user-cancel /
            failure. Failures emit warnings; never raise to UI.
        """
        if not self._current_node:
            return None
        from RBFtools import core, core_mirror

        source = self._current_node
        target_name = config.get("target_name", "")
        if not target_name:
            cmds.warning("mirror_current_node: empty target_name")
            return None

        target_exists = core._exists(target_name)
        # Build preview text per addendum §M3.2.Q8.
        axis = int(config.get("mirror_axis", core_mirror.AXIS_X))
        axis_label = core_mirror.AXIS_LABELS[axis]
        rule_idx = int(config.get("naming_rule_index", 0))
        if rule_idx < len(core_mirror.NAMING_PRESETS):
            rule_label = core_mirror.NAMING_PRESETS[rule_idx][4]
        else:
            rule_label = "naming_rule_custom"

        src_driver, _dr_attrs = core.read_driver_info(source)
        src_driven, _dn_attrs = core.read_driven_info(source)
        new_driver, _ = core_mirror.apply_naming_rule(
            src_driver or "", rule_idx,
            config.get("custom"), config.get("naming_direction", "auto"))
        new_driven, _ = core_mirror.apply_naming_rule(
            src_driven or "", rule_idx,
            config.get("custom"), config.get("naming_direction", "auto"))

        n_poses = len(core.read_all_poses(source))

        preview_lines = [
            "Mirror Configuration:",
            "  Source Node:    {}".format(source),
            "  Target Node:    {}  ({})".format(
                target_name,
                "will OVERWRITE" if target_exists else "will be CREATED"),
            "  Mirror Axis:    {}".format(axis_label),
            "  Naming Rule:    {}".format(rule_label),
            "",
            "Driver:   {!s:<24}  ->  {!s:<24} {}".format(
                src_driver or "(none)",
                new_driver or "(none)",
                "(found)" if (new_driver and core._exists(new_driver))
                else "(MISSING)"),
            "Driven:   {!s:<24}  ->  {!s:<24} {}".format(
                src_driven or "(none)",
                new_driven or "(none)",
                "(found)" if (new_driven and core._exists(new_driven))
                else "(MISSING)"),
            "",
            "Poses ({} total) will be mirrored across {}.".format(
                n_poses, axis_label),
        ]
        preview = "\n".join(preview_lines)

        action_id = ("mirror_overwrite" if target_exists
                     else "mirror_create")
        proceed = self.ask_confirm(
            title="Mirror Node",
            summary="Mirror {} -> {}?".format(source, target_name),
            preview_text=preview,
            action_id=action_id,
        )
        if not proceed:
            return None

        prog = self.progress()
        try:
            return core.mirror_node(
                source_node=source,
                target_name=target_name,
                mirror_axis=axis,
                naming_rule_index=rule_idx,
                custom_naming=config.get("custom"),
                naming_direction=config.get("naming_direction", "auto"),
                progress=prog,
                overwrite=target_exists,
            )
        except Exception as exc:
            cmds.warning("mirror_current_node failed: {}".format(exc))
            if prog is not None:
                prog.end("Mirror failed")
            return None

    # =================================================================
    #  M3.1 — Pose Pruner (path A consumer; 4th real-world consumer)
    # =================================================================

    def prune_current_node(self, opts=None):
        """Two-phase prune: dry-run analysis -> path A confirm ->
        execute. Returns the result dict from
        :func:`core_prune.execute_prune`, or None on cancellation /
        no-op.
        """
        if not self._current_node:
            cmds.warning("prune_current_node: no current node")
            return None
        from RBFtools import core_prune
        from RBFtools.ui.i18n import tr

        action = core_prune.analyse_node(self._current_node, opts)
        if not action.has_changes() and not action.conflict_pairs:
            cmds.warning("Pose Pruner: nothing to prune.")
            return None

        preview = self._format_prune_report(self._current_node, action)
        if not action.has_changes():
            # Conflict pairs only — display warning, no actual action.
            cmds.warning(
                "Pose Pruner: conflict pairs reported (informational).\n"
                + preview)
            return None

        proceed = self.ask_confirm(
            title=tr("title_prune_poses"),
            summary=tr("summary_prune_poses"),
            preview_text=preview,
            action_id="prune_poses",
        )
        if not proceed:
            return None

        prog = self.progress()
        if prog is not None:
            prog.begin(tr("status_prune_starting"))
        try:
            result = core_prune.execute_prune(self._current_node, action)
        except Exception as exc:
            cmds.warning("prune_current_node failed: {}".format(exc))
            if prog is not None:
                prog.end(tr("status_prune_failed"))
            return None
        if prog is not None:
            prog.end(tr("status_prune_done"))
        # Pose count / column shape may have changed — refresh editor.
        self._load_editor()
        return result

    @staticmethod
    def _format_prune_report(node_name, action):
        """Render a :class:`core_prune.PruneAction` as ASCII for the
        ConfirmDialog preview pane."""
        lines = ["Pose Pruner Preview", "  Node:   {}".format(node_name), ""]

        if action.duplicate_pose_indices:
            lines.append("  Duplicate poses ({} found)".format(
                len(action.duplicate_pose_indices)))
            for idx in action.duplicate_pose_indices:
                lines.append("        pose[{}]  duplicate (same input AND value)"
                             .format(idx))
        if action.redundant_input_indices:
            lines.append("  Redundant driver dims ({} found)".format(
                len(action.redundant_input_indices)))
            for idx in action.redundant_input_indices:
                nm = (action.driver_attr_names[idx]
                      if idx < len(action.driver_attr_names) else "?")
                lines.append("        input[{}] ({}):  all poses same value"
                             .format(idx, nm))
        if action.constant_output_indices:
            lines.append("  Constant outputs ({} found)".format(
                len(action.constant_output_indices)))
            for idx in action.constant_output_indices:
                nm = (action.driven_attr_names[idx]
                      if idx < len(action.driven_attr_names) else "?")
                lines.append("        output[{}] ({}):  all poses same value"
                             .format(idx, nm))
        if action.conflict_pairs:
            lines.append("")
            lines.append("  ! Conflicting poses ({} pair(s), NOT auto-removed)"
                         .format(len(action.conflict_pairs)))
            for a, b in action.conflict_pairs:
                lines.append("        pose[{}] vs pose[{}]: same input, "
                             "different values".format(a, b))
            lines.append("        Manual review needed.")

        # Side effects on quat groups.
        invalid = [e for e in action.quat_group_effects if e.invalidated]
        shifted = [e for e in action.quat_group_effects
                   if not e.invalidated and e.new_start != e.old_start]
        if invalid or shifted:
            lines.append("")
            lines.append("  ! Side effects:")
            for e in shifted:
                lines.append(
                    "        quat group[{}]: start {} -> {} (index shift)"
                    .format(e.group_idx, e.old_start, e.new_start))
            for e in invalid:
                lines.append(
                    "        quat group[{}] (start={}): INVALID after prune; "
                    "C++ will silently skip".format(e.group_idx, e.old_start))

        # After-prune summary.
        lines.append("")
        lines.append("  After prune: {} poses -> {} poses".format(
            action.n_poses_before,
            action.n_poses_before - len(action.duplicate_pose_indices)))
        lines.append("               {} driver dims -> {} driver dims".format(
            action.n_inputs_before,
            action.n_inputs_before - len(action.redundant_input_indices)))
        lines.append("               {} driven dims -> {} driven dims".format(
            action.n_outputs_before,
            action.n_outputs_before - len(action.constant_output_indices)))
        return "\n".join(lines)

    # =================================================================
    #  M3.3 — JSON Import / Export (path A consumers)
    # =================================================================

    def export_current_to_path(self, path, meta=None):
        """Export the current node to a single-node JSON at *path*.
        Non-destructive — no confirm dialog, only progress feedback."""
        if not self._current_node:
            cmds.warning("export_current_to_path: no current node")
            return False
        from RBFtools import core_json
        from RBFtools.ui.i18n import tr
        prog = self.progress()
        if prog is not None:
            prog.begin(tr("status_export_starting"))
        try:
            core_json.export_nodes_to_path(
                [self._current_node], path, meta=meta)
        except Exception as exc:
            cmds.warning("export failed: {}".format(exc))
            if prog is not None:
                prog.end(tr("status_export_failed"))
            return False
        if prog is not None:
            prog.end(tr("status_export_done"))
        return True

    def export_all_to_path(self, path, meta=None):
        """Export every RBFtools node in the scene to a multi-node JSON."""
        from RBFtools import core, core_json
        from RBFtools.ui.i18n import tr
        nodes = core.list_all_nodes()
        if not nodes:
            cmds.warning("export_all_to_path: no RBFtools nodes in scene")
            return False
        prog = self.progress()
        if prog is not None:
            prog.begin(tr("status_export_starting"))
        try:
            core_json.export_nodes_to_path(nodes, path, meta=meta)
        except Exception as exc:
            cmds.warning("export_all failed: {}".format(exc))
            if prog is not None:
                prog.end(tr("status_export_failed"))
            return False
        if prog is not None:
            prog.end(tr("status_export_done"))
        return True

    def import_rbf_setup(self, path, mode="add"):
        """Two-phase import (path A): dry-run -> ask_confirm (only when
        mode='replace' will overwrite an existing node) -> execute.

        Returns the dict from :func:`core_json.import_path` or None on
        cancellation / total failure.
        """
        from RBFtools import core_json
        from RBFtools.ui.i18n import tr
        try:
            data = core_json.read_json_with_schema_check(path)
        except core_json.SchemaVersionError as exc:
            cmds.warning(
                "import_rbf_setup: {}".format(exc))
            return None
        try:
            reports = core_json.dry_run(data, mode=mode)
        except core_json.SchemaValidationError as exc:
            cmds.warning(
                "import_rbf_setup: dry-run failed:\n  {}".format(
                    "\n  ".join(exc.errors)))
            return None

        # Path A confirm only when at least one Replace overwrite is
        # imminent; pure-Add imports proceed without a prompt
        # (non-destructive — addendum §M3.3 D.2).
        will_overwrite_any = any(r.will_overwrite for r in reports)
        if mode == "replace" and will_overwrite_any:
            preview = self._format_dry_run_report(reports)
            proceed = self.ask_confirm(
                title=tr("title_import_replace"),
                summary=tr("summary_import_replace"),
                preview_text=preview,
                action_id="import_replace",
            )
            if not proceed:
                return None

        prog = self.progress()
        if prog is not None:
            prog.begin(tr("status_import_starting"))
        try:
            result = core_json.import_path(path, mode=mode)
        except Exception as exc:
            cmds.warning("import_rbf_setup failed: {}".format(exc))
            if prog is not None:
                prog.end(tr("status_import_failed"))
            return None
        if prog is not None:
            prog.end(tr("status_import_done"))
        self.refresh_nodes()
        return result

    @staticmethod
    def _format_dry_run_report(reports):
        """Render a dry-run report list as ASCII for ConfirmDialog."""
        lines = ["Import dry-run report ({} node(s)):".format(len(reports)),
                 ""]
        for r in reports:
            mark = "[OK]" if r.ok else "[XX]"
            ow = " (OVERWRITES existing)" if r.will_overwrite else ""
            lines.append("{} {}{}".format(mark, r.name, ow))
            for w in r.warnings:
                lines.append("    ! {}".format(w))
            for e in r.errors:
                lines.append("    X {}".format(e))
        return "\n".join(lines)

    # =================================================================
    #  M3.7 — auto-alias dispatchers (path A consumers)
    # =================================================================

    def regenerate_aliases_for_current_node(self):
        """Re-run alias generation in *preserve-user-aliases* mode
        (E.1 default). No confirm dialog — non-destructive.

        Returns the dict from :func:`core.auto_alias_outputs`, or None
        if there is no current node.
        """
        if not self._current_node:
            return None
        from RBFtools import core
        from RBFtools.ui.i18n import tr

        driver_node, driver_attrs = core.read_driver_info(self._current_node)
        driven_node, driven_attrs = core.read_driven_info(self._current_node)
        # driver_node / driven_node are unused at this layer — alias
        # writes target the shape only, not the rig nodes (write-
        # boundary contract, addendum §M3.7).
        del driver_node, driven_node

        prog = self.progress()
        if prog is not None:
            prog.begin(tr("status_alias_starting"))
        try:
            result = core.auto_alias_outputs(
                self._current_node, driver_attrs, driven_attrs,
                force=False)
        except Exception as exc:
            cmds.warning("regenerate_aliases failed: {}".format(exc))
            if prog is not None:
                prog.end(tr("status_alias_failed"))
            return None
        if prog is not None:
            prog.end(tr("status_alias_done"))
        return result

    def force_regenerate_aliases_for_current_node(self):
        """Re-run alias generation in *force* mode — wipes ALL aliases
        on the shape (managed AND user-set) before regenerating.

        Goes through :meth:`ask_confirm` (path A) with
        ``action_id="force_regenerate_aliases"`` because this is a
        destructive operation against any user-managed aliases.
        """
        if not self._current_node:
            return None
        from RBFtools import core, core_alias
        from RBFtools.ui.i18n import tr

        shape = core.get_shape(self._current_node)
        # Build preview: list every existing alias the user is about
        # to lose. Two sections so user-set vs managed are visible.
        existing_pairs = core_alias._query_existing_aliases(shape) if shape else []
        managed = [a for a, _ in existing_pairs
                   if core_alias.is_rbftools_managed_alias(a)]
        user_set = [a for a, _ in existing_pairs
                    if not core_alias.is_rbftools_managed_alias(a)]
        preview_lines = [
            "Force regenerate will WIPE all aliases on:",
            "  Shape:  {}".format(shape or "(none)"),
            "",
            "User-set aliases that will be LOST ({}):".format(len(user_set)),
        ]
        if user_set:
            preview_lines.extend("  - {}".format(a) for a in user_set)
        else:
            preview_lines.append("  (none)")
        preview_lines.extend([
            "",
            "RBFtools-managed aliases that will be regenerated ({}):".format(
                len(managed)),
        ])
        if managed:
            preview_lines.extend("  - {}".format(a) for a in managed)
        else:
            preview_lines.append("  (none)")
        preview = "\n".join(preview_lines)

        proceed = self.ask_confirm(
            title=tr("title_force_alias"),
            summary=tr("summary_force_alias"),
            preview_text=preview,
            action_id="force_regenerate_aliases",
        )
        if not proceed:
            return None

        driver_node, driver_attrs = core.read_driver_info(self._current_node)
        driven_node, driven_attrs = core.read_driven_info(self._current_node)
        del driver_node, driven_node

        prog = self.progress()
        if prog is not None:
            prog.begin(tr("status_alias_starting"))
        try:
            result = core.auto_alias_outputs(
                self._current_node, driver_attrs, driven_attrs,
                force=True)
        except Exception as exc:
            cmds.warning(
                "force_regenerate_aliases failed: {}".format(exc))
            if prog is not None:
                prog.end(tr("status_alias_failed"))
            return None
        if prog is not None:
            prog.end(tr("status_alias_done"))
        return result

    def ask_confirm(self, title, summary, preview_text, action_id):
        """Synchronous user-confirmation prompt (addendum §M3.0).

        Returns True if the user clicked OK (or had previously silenced
        this action via "Don't ask again"), False on Cancel / close.
        Sub-tasks call this instead of importing ConfirmDialog
        directly — keeps MVC clean and centralises the parent-widget
        wiring.
        """
        from RBFtools.ui.widgets.confirm_dialog import ConfirmDialog
        return ConfirmDialog.confirm(
            title, summary, preview_text, action_id,
            parent=self.parent())

    # =================================================================
    #  Generic attribute write
    # =================================================================

    def set_attribute(self, attr, value):
        """Write a single attribute on the current node.

        Dispatch by value type:
          * ``list`` / ``tuple`` → multi-instance write via
            :func:`core.set_node_multi_attr` (transactional;
            clear-then-write under a single undo chunk per
            v5 addendum §M2.4a refinement 2).
          * scalar (int / float / bool) → :func:`core.set_node_attr`.
        """
        if not self._current_node:
            return
        if isinstance(value, (list, tuple)):
            core.set_node_multi_attr(self._current_node, attr, value)
        else:
            core.set_node_attr(self._current_node, attr, value)

    # =================================================================
    #  3. Kernel / radius interactions
    # =================================================================

    def on_kernel_changed(self, idx):
        """Handle kernel dropdown change → lock radius type + refresh."""
        if not self._current_node:
            return
        core.lock_radius_type(self._current_node)
        self._emit_radius_state()

    def on_radius_type_changed(self, idx):
        """Handle radius-type dropdown change → recompute radius."""
        if not self._current_node:
            return
        core.compute_radius(self._current_node)
        self._emit_radius_state()

    def on_radius_edited(self, value):
        """User manually edits the radius (Custom type only)."""
        if not self._current_node:
            return
        core.set_node_attr(self._current_node, "radius", value)
        core.update_evaluation(self._current_node)

    def _emit_radius_state(self):
        """Read current radius state and emit ``radiusUpdated``."""
        shape = core.get_shape(self._current_node)
        if not shape or not cmds.objExists(shape):
            return
        radius_val   = core.safe_get(shape + ".radius",     0.0)
        radius_type  = core.safe_get(shape + ".radiusType",  0)
        kernel       = core.safe_get(shape + ".kernel",      1)
        self.radiusUpdated.emit(
            radius_val,
            radius_type == 3,         # radius spinbox enabled
            kernel != 0,              # radius-type combo enabled
        )

    # =================================================================
    #  4. Attribute filter persistence
    # =================================================================

    def get_filters(self, role):
        """Return persisted filter dict for *role*."""
        return core.get_all_filters(role)

    def set_filter(self, role, key, value):
        """Persist one filter toggle."""
        core.set_filter_state(role, key, value)

    def list_attributes(self, node, filters):
        """Return filtered attribute names for *node*."""
        return core.list_filtered_attributes(node, filters)

    # =================================================================
    #  5. Pose editor — load from node
    # =================================================================

    def _load_editor(self):
        """Populate the pose model from the current node's data."""
        self._pose_model.clear()

        node = self._current_node
        if not node:
            self.editorLoaded.emit()
            return

        shape = core.get_shape(node)
        if not shape or not cmds.objExists(shape):
            self.editorLoaded.emit()
            return

        if core.safe_get(shape + ".type", 0) != 1:
            self.editorLoaded.emit()
            return

        # Discover wiring
        driver_node, driver_attrs = core.read_driver_info(node)
        driven_node, driven_attrs = core.read_driven_info(node)

        # Configure columns (resets model)
        self._pose_model.setup_columns(driver_attrs, driven_attrs)

        # Load poses
        poses = core.read_all_poses(node)
        for p in poses:
            self._pose_model.add_pose(p)

        self.editorLoaded.emit()

        # Return info for the view to populate text fields
        return driver_node, driver_attrs, driven_node, driven_attrs

    def reload_editor(self):
        """Public wrapper for _load_editor (Reload button)."""
        return self._load_editor()

    # =================================================================
    #  6. Pose CRUD
    # =================================================================

    def add_pose(self, driver_node, driven_node,
                 driver_attrs, driven_attrs):
        """Capture current scene values and append a new pose.

        Handles BlendShape auto-fill logic when :attr:`auto_fill` is on.

        Parameters
        ----------
        driver_node, driven_node : str
            Scene node names.
        driver_attrs, driven_attrs : list[str]
            Currently selected attribute names.

        Returns
        -------
        PoseData or None
            The newly created pose, or None on validation failure.
        """
        if not driver_node or not driven_node:
            cmds.warning("Please set both driver and driven nodes.")
            return None
        if not driver_attrs or not driven_attrs:
            cmds.warning("Please select attributes for both driver and driven.")
            return None

        # Dimension consistency check
        model = self._pose_model
        if model.n_inputs and model.n_inputs != len(driver_attrs):
            cmds.warning(
                "Driver attribute count ({}) differs from existing "
                "poses ({}).".format(len(driver_attrs), model.n_inputs))
            return None
        if model.n_outputs and model.n_outputs != len(driven_attrs):
            cmds.warning(
                "Driven attribute count ({}) differs from existing "
                "poses ({}).".format(len(driven_attrs), model.n_outputs))
            return None

        # Set up columns on first pose
        if model.rowCount() == 0:
            model.setup_columns(driver_attrs, driven_attrs)

        pid = model.next_pose_index()

        # Snapshot current scene values
        inputs  = core.read_current_values(driver_node, driver_attrs)
        outputs = core.read_current_values(driven_node, driven_attrs)

        # ----- BlendShape auto-fill -----
        # Vector generation is delegated to core (pure math, no UI).
        if core.is_blendshape(driven_node) and self._auto_fill:
            if pid == 0:
                result = cmds.confirmDialog(
                    title="RBF Tools",
                    message="Add the first pose as the rest pose?",
                    button=["OK", "Cancel"],
                    defaultButton="OK", cancelButton="Cancel")
                if result == "OK":
                    outputs = core.generate_rest_outputs(len(driven_attrs))
            else:
                outputs = core.generate_onehot_outputs(
                    len(driven_attrs), pid, model.has_rest_pose())

        pose = core.PoseData(pid, inputs, outputs)
        model.add_pose(pose)
        return pose

    def update_pose(self, row, driver_node, driven_node,
                    driver_attrs, driven_attrs):
        """Re-capture current scene values into an existing pose row."""
        if not driver_node or not driven_node:
            return
        inputs  = core.read_current_values(driver_node, driver_attrs)
        outputs = core.read_current_values(driven_node, driven_attrs)
        self._pose_model.update_pose_values(row, inputs, outputs)

    def delete_pose(self, row):
        """Remove a pose from the model (does NOT touch the node yet)."""
        self._pose_model.remove_pose(row)

    def recall_pose(self, row, driver_node, driven_node,
                    driver_attrs, driven_attrs):
        """Restore a saved pose to the scene.

        Reads the :class:`PoseData` from the model and delegates to
        :func:`core.recall_pose`.
        """
        pose = self._pose_model.get_pose(row)
        if pose is None:
            return
        core.recall_pose(driver_node, driven_node,
                         driver_attrs, driven_attrs, pose)

    # =================================================================
    #  7. Apply / Connect
    # =================================================================

    def apply_poses(self, driver_node, driven_node,
                    driver_attrs, driven_attrs):
        """Apply button — write all model poses to the solver node.

        Flow
        ----
        1. Create or reuse the current ``RBFtools`` node.
        2. Call ``core.apply_poses`` with data from the model.
        3. Refresh the node selector and reload settings.
        """
        if not self._validate_apply_args(
                driver_node, driven_node, driver_attrs, driven_attrs):
            return

        node = self._current_node
        if not node or not cmds.objExists(node):
            core.ensure_plugin()
            node = core.create_node()
            core.set_node_attr(node, "type", 1)

        poses = self._pose_model.all_poses()
        core.apply_poses(
            node, driver_node, driven_node,
            driver_attrs, driven_attrs, poses)

        self._current_node = core.get_transform(core.get_shape(node))
        self.refresh_nodes()
        self._load_settings()
        # Do NOT reload editor — it would discard the user's pose rows.
        # The node may compact indices.  User clicks Reload when ready.

        self.statusMessage.emit("RBF data applied.")

    def connect_poses(self, driver_node, driven_node,
                      driver_attrs, driven_attrs):
        """Connect button — wire driver inputs and driven outputs."""
        if not self._validate_apply_args(
                driver_node, driven_node, driver_attrs, driven_attrs):
            return

        node = self._current_node
        if not node or not cmds.objExists(node):
            cmds.warning("No active RBFtools node. Apply poses first.")
            return

        core.connect_node(
            node, driver_node, driven_node,
            driver_attrs, driven_attrs)

        self._current_node = core.get_transform(core.get_shape(node))
        self._load_settings()

        self.statusMessage.emit("Connections established.")

    def disconnect_outputs(self):
        """Disconnect button — break output connections to driven node."""
        node = self._current_node
        if not node or not cmds.objExists(node):
            cmds.warning("No active RBFtools node.")
            return
        core.disconnect_outputs(node)
        self.statusMessage.emit("Output connections disconnected.")

    def _validate_apply_args(self, driver_node, driven_node,
                             driver_attrs, driven_attrs):
        """Common validation for apply / connect."""
        if not driver_node or not driven_node:
            cmds.warning("Please set both driver and driven nodes.")
            return False
        if not driver_attrs or not driven_attrs:
            cmds.warning("Please select driver and driven attributes.")
            return False
        return True

    # =================================================================
    #  8. Auto-fill toggle
    # =================================================================

    def set_auto_fill(self, checked):
        self._auto_fill = bool(checked)
        cmds.optionVar(iv=(AUTO_FILL_OPT_VAR, int(self._auto_fill)))
