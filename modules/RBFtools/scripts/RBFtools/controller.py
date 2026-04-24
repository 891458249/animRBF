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

    def set_attribute(self, attr, value):
        """Write a single attribute on the current node."""
        if not self._current_node:
            return
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
