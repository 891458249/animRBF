# -*- coding: utf-8 -*-
"""
Internationalisation — English / Chinese string tables.

Usage::

    from RBFtools.ui.i18n import tr
    label = tr("active")  # returns "Active" or "启用"
"""

from __future__ import absolute_import

import maya.cmds as cmds

from RBFtools.constants import LANG_OPT_VAR

# ------------------------------------------------------------------
# String tables
# ------------------------------------------------------------------

_EN = {
    # -- top bar --
    "node":                "Node:",
    "refresh":             "Refresh",
    "pick_sel":            "Pick Sel",
    "new":                 "New",
    "delete":              "Delete",
    # -- general --
    "general":             "General",
    "active":              "Active",
    "type":                "Type:",
    "icon_size":           "Icon Size:",
    # -- vector angle --
    "vector_angle":        "Vector Angle",
    "direction":           "Direction:",
    "invert":              "Invert",
    "rotation":            "Rotation",
    "use_rotate":          "Use Rotate",
    "angle":               "Angle:",
    "center_angle":        "Center Angle:",
    "twist":               "Twist",
    "twist_angle":         "Twist Angle:",
    "translation":         "Translation",
    "use_translate":       "Use Translate",
    "grow":                "Grow",
    "translate_min":       "Translate Min:",
    "translate_max":       "Translate Max:",
    "interpolation":       "Interpolation:",
    "cone_display":        "Cone Display",
    "draw_cone":           "Draw Cone",
    "draw_center_cone":    "Draw Center Cone",
    "draw_weight":         "Draw Weight",
    # -- rbf --
    "rbf":                 "Radial Basis Function",
    "kernel":              "Kernel:",
    "radius_type":         "Radius Type:",
    "radius":              "Radius:",
    "allow_neg":           "Allow Negative Weights",
    "scale":               "Scale:",
    "rbf_mode":            "RBF Mode:",
    "generic_rbf":         "Generic RBF",
    "distance_type":       "Distance Type:",
    "matrix_rbf":          "Matrix RBF",
    "twist_axis":          "Twist Axis:",
    "solver_display":      "Solver Display",
    "draw_origin":         "Draw Origin",
    "draw_poses":          "Draw Poses",
    "pose_length":         "Pose Length:",
    "draw_indices":        "Draw Indices",
    "index_distance":      "Index Distance:",
    "draw_twist":          "Draw Twist",
    "opposite":            "Opposite",
    "driver_index":        "Driver Index:",
    # -- M2.4a: scalar / enum widgets for M1.3 / M1.4 / M2.1a --
    "regularization":      "Regularization (λ):",
    "solver_method":       "Solver:",
    "solver_auto":         "Auto",
    "solver_force_ge":     "Force GE",
    "input_encoding":      "Input Encoding:",
    "enc_raw":             "Raw",
    "enc_quaternion":      "Quaternion",
    "enc_bendroll":        "BendRoll",
    "enc_expmap":          "ExpMap",
    "enc_swingtwist":      "SwingTwist",
    # M_QUICKWINS Item 4a (2026-04-27): label rephrased to match the
    # TD-facing term "Limit" - same underlying clampEnabled /
    # clampInflation schema, more intuitive surface.
    "clamp_enabled":       "Limit Driver to Registered Pose Range",
    "clamp_inflation":     "Limit Inflation:",
    # -- M2.4a: per-output scale flag (OutputScaleEditor) --
    "output_is_scale":     "Output Is Scale",
    "output_is_scale_hdr": "Mark scale-channel outputs (M1.2 anchor 1.0)",
    # -- M2.4b: ordered-list editors for M2.1a / M2.2 multi attrs --
    "driver_rotate_order_label":   "Driver Input Rotate Order:",
    "rotate_order_empty_hint":     "No driver rotate orders defined.",
    "quat_group_start_label":      "Quaternion Group Starts (output index):",
    "quat_group_empty_hint":       "No quaternion groups defined.",
    "quat_group_start_value_tip":
        "Output start index — group spans 4 outputs (S, S+1, S+2, S+3)",
    "list_editor_add":             "+",
    "list_editor_remove":          u"\u2212",   # minus sign
    "list_editor_move_up":         u"\u2191",   # up arrow
    "list_editor_move_down":       u"\u2193",   # down arrow
    "list_editor_add_tip":         "Append a new entry",
    "list_editor_remove_tip":      "Remove selected entry",
    "list_editor_move_up_tip":     "Move selected up",
    "list_editor_move_down_tip":   "Move selected down",
    # -- M3.0: menus + confirm dialog --
    "menu_file":                   "File",
    "menu_edit":                   "Edit",
    "menu_tools":                  "Tools",
    "menu_help":                   "Help",
    "menu_reset_confirms":         "Reset confirm dialogs",
    "reset_confirms_done":         "Confirm dialog preferences cleared",
    "confirm_dont_ask":            "Don't ask again for this action",
    "ok":                          "OK",
    "cancel":                      "Cancel",
    # -- M3.2: Mirror Tool --
    "menu_mirror_node":            "Mirror Node...",
    "row_mirror_this":             "Mirror this pose",
    "title_mirror_node":           "Mirror Node",
    "label_source_node":           "Source Node:",
    "label_mirror_axis":            "Mirror Axis:",
    "label_naming_rule":            "Naming Rule:",
    "label_direction":              "Direction:",
    "dir_auto":                     "Auto",
    "dir_forward":                  "L -> R",
    "dir_reverse":                  "R -> L",
    "label_custom_pattern":         "Pattern:",
    "label_custom_replacement":     "Replacement:",
    "label_target_preview":         "Target Node:",
    "btn_mirror":                   "Mirror",
    "mirror_axis_yz":               "YZ plane (flip X)",
    "mirror_axis_xz":               "XZ plane (flip Y)",
    "mirror_axis_xy":               "XY plane (flip Z)",
    "naming_rule_l_r":              "L_xxx <-> R_xxx",
    "naming_rule_xl_xr":            "xxx_L <-> xxx_R",
    "naming_rule_left_right":       "Left_xxx <-> Right_xxx",
    "naming_rule_xl_lc":            "xxx_l <-> xxx_r (lowercase)",
    "naming_rule_lf_rt":            "xxx_lf <-> xxx_rt",
    "naming_rule_lflf":             "lf_xxx <-> rt_xxx",
    "naming_rule_custom":           "Custom...",
    "warn_both_directions_match":   "Both directions match - using forward",
    "warn_name_unchanged":          "Mirror would produce identical name - check rule",
    "warn_name_no_match":           "Source name does not match selected rule",
    "summary_mirror_node":          "Mirror node configuration:",
    # -- M3.3: JSON Import / Export --
    "menu_import_rbf":                 "Import RBF Setup...",
    "menu_export_selected":            "Export Selected RBF...",
    "menu_export_all":                 "Export All RBF...",
    "title_import_rbf":                "Import RBF Setup",
    "title_import_replace":            "Replace existing nodes?",
    "summary_import_replace":
        "Import in Replace mode will delete and recreate the listed nodes.",
    "label_import_mode":               "Mode:",
    "import_mode_add":                 "Add",
    "import_mode_replace":             "Replace",
    "label_import_preview":            "Dry-run preview:",
    "btn_import":                      "Import",
    "status_dry_run_loading":          "Running dry-run...",
    "status_dry_run_failed":           "Dry-run failed.",
    "status_schema_version_error":     "Schema version mismatch:",
    "status_export_starting":          "Exporting...",
    "status_export_done":              "Export complete.",
    "status_export_failed":            "Export failed.",
    "status_import_starting":          "Importing...",
    "status_import_done":              "Import complete.",
    "status_import_failed":            "Import failed.",
    # -- M3.4: Live Edit Mode --
    "live_edit_toggle_label":          "Live Edit",
    "live_edit_status_idle":           "idle",
    "live_edit_status_listening":      "listening on {n} attrs",
    "live_edit_warn_no_node":          "no current node — pick an RBF node first",
    "live_edit_warn_no_attrs":         "no driver attrs to listen on",
    "live_edit_warn_failed":           "Live Edit toggle failed",
    # -- M_B24b1: multi-source driver section + outputEncoding --
    "section_driver_sources":          "Driver Sources",
    "driver_source_list_header":       "Driver Sources",
    "driver_source_list_empty_hint":
        "No driver sources. Use Add to register one or more drivers.",
    "driver_source_node_tip":          "Driver node (read-only mirror).",
    "driver_source_attrs_tip":         "Driver attrs (comma-joined).",
    "driver_source_weight_tip":
        "Per-source weight; reserved for M_B24b downstream consumption.",
    "driver_source_encoding_tip":
        "Per-source input encoding (0=Raw, 1=Quat, 2=BendRoll, 3=ExpMap, 4=SwingTwist).",
    "output_encoding_label":           "Output encoding:",
    "output_encoding_combo_tip":
        "Node-level output encoding (forward-compat; M_B24b business consumption deferred).",
    "output_encoding_euler":           "Euler",
    "output_encoding_quaternion":      "Quaternion",
    "output_encoding_expmap":          "ExpMap",
    "title_remove_driver_source":      "Remove Driver Source",
    "summary_remove_driver_source":
        "Remove this driver source entry from the current node?",
    # -- M_B24c: Mirror multi-source informational notice
    #    (Generic mode supported; Matrix mode DEFERRED to M_B24c2) --
    "title_mirror_multi_source":       "Mirror — Multi-source node",
    "summary_mirror_multi_source":
        "This node has multiple Generic-mode driver sources. Mirror "
        "will iterate every source and apply the naming rule per "
        "source (sources whose name does not match the rule keep "
        "their original name + warning). Matrix-mode multi-source "
        "mirror remains deferred to M_B24c2 (addendum §M_B24c2-stub) "
        "and is blocked at the engine entry. Continue?",
    # -- M3.5: Pose Profiler + ToolsSection (spillover §3) --
    "section_tools":                   "Tools",
    "menu_profile_to_se":              "Profile to Script Editor",
    "btn_refresh_profile":             "Refresh Profile",
    "status_profile_pending":
        "Click 'Refresh Profile' to profile the current node.",
    "status_profile_failed":           "Profile failed.",
    # -- M3.6: Auto-neutral sample --
    "menu_add_neutral_sample":         "Add Neutral Sample",
    "menu_reset_auto_neutral":         "Reset auto-neutral default",
    "reset_auto_neutral_done":         "Auto-neutral preference cleared",
    "title_add_neutral":               "Add Neutral Sample",
    "summary_add_neutral":
        "A rest pose will be inserted at index 0; existing poses shift by 1.",
    "status_neutral_starting":         "Adding neutral sample...",
    "status_neutral_done":             "Neutral sample added.",
    "status_neutral_failed":           "Add neutral sample failed.",
    # -- M3.1: Pose Pruner --
    "menu_prune_poses":                "Prune Poses...",
    "row_remove_this":                 "Remove this pose",
    "title_prune_poses":               "Pose Pruner",
    "summary_prune_poses":
        "Pose Pruner will rebuild this RBF node with the selected reductions.",
    "prune_cb_duplicates":             "Remove duplicate poses",
    "prune_cb_redundant":              "Remove redundant driver dimensions",
    "prune_cb_constant":               "Remove constant outputs",
    "label_prune_preview":             "Dry-run preview:",
    "btn_prune":                       "Prune",
    "status_prune_starting":           "Pruning...",
    "status_prune_done":               "Prune complete.",
    "status_prune_failed":             "Prune failed.",
    # -- M3.7: aliasAttr auto-naming --
    "menu_regenerate_aliases":         "Regenerate Aliases",
    "menu_force_regenerate_aliases":   "Force Regenerate Aliases...",
    "title_force_alias":               "Force Regenerate Aliases",
    "summary_force_alias":
        "Force regenerate will WIPE user-set aliases on this shape.",
    "status_alias_starting":           "Regenerating aliases...",
    "status_alias_done":               "Aliases regenerated.",
    "status_alias_failed":             "Alias regeneration failed.",
    # -- pose editor --
    "rbf_pose_editor":     "RBF Pose Editor",
    "auto_fill_bs":        "Auto Fill BlendShape",
    "driver":              "Driver",
    "driven":              "Driven",
    "select":              "Select",
    "attributes":          "Attributes",
    "poses":               "Poses",
    "add_pose":            "Add Pose",
    "apply":               "Apply",
    "connect":             "Connect",
    "disconnect":          "Disconnect",
    "reload":              "Reload",
    "recall":              "Recall",
    "update":              "Update",
    # -- filter --
    "show_keyable":        "Show Keyable",
    "show_non_keyable":    "Show Non-Keyable",
    "show_readable":       "Show Readable",
    "show_writable":       "Show Writable",
    "show_connected":      "Show Connected Only",
    "show_hidden":         "Show Hidden",
    "show_user_defined":   "Show User Defined",
    # -- settings --
    "language":            "Language",
    "english":             "English",
    "chinese":             "Chinese",
    # -- menu --
    "open":                "Open RBF Tools",
    "settings":            "Settings",
    # -- M_UIPOLISH (B.3 micro): per-widget tooltips on the 8 widgets
    #    that have neither a HelpButton companion nor an existing
    #    setToolTip surface. EN/ZH parity (decision D.3, _tip suffix
    #    naming convention shared with the M_B24b1 batch). --
    "attribute_list_select_tip":
        "Pick the selected scene node + its attributes into this "
        "list. Use multi-selection in the channel box to add several "
        "attrs at once.",
    "import_dialog_btn_tip":
        "Import the JSON file using the chosen mode. Replace wipes "
        "the current node; Append adds new poses to it.",
    "live_edit_toggle_tip":
        "Toggle Live Edit. While ON, scene-level driver edits are "
        "captured into the active pose row in real time.",
    "mirror_dialog_btn_tip":
        "Run Mirror with the current configuration. Multi-source "
        "Generic mode is supported; Matrix-mode multi-source mirror "
        "is blocked at the engine entry (M_B24c2).",
    "mirror_dialog_pattern_tip":
        "Custom regex pattern (Python re syntax) matched against the "
        "source driver / driven names.",
    "mirror_dialog_replacement_tip":
        "Custom replacement applied when the pattern matches.",
    "node_selector_combo_tip":
        "Active RBFtools node. The list reflects every RBFtools "
        "shape in the scene.",
    "node_selector_pick_tip":
        "Set the active node from the current Maya selection.",
    "node_selector_new_tip":
        "Create a new RBFtools node + transform.",
    "node_selector_delete_tip":
        "Delete the active RBFtools node and its connections.",
    "node_selector_refresh_tip":
        "Re-scan the scene and rebuild the node list.",
    "pose_editor_apply_tip":
        "Write the table's pose data onto the node (Apply).",
    "pose_editor_connect_tip":
        "Wire driver / driven attributes to the node (Connect).",
    "prune_dialog_btn_tip":
        "Run the prune workflow with the selected categories.",
    "profile_widget_refresh_tip":
        "Re-compute the profile report for the active node.",
    # -- M_UIPOLISH cmds.warning string lifted out of main_window.py:660
    #    so the language toggle reaches the script-editor warning. --
    "warning_pose_pruner_no_node":
        "Pose Pruner: pick an RBF node first.",
    # -- M_UIRECONCILE: DriverSourceListEditor add-flow warnings +
    #    pose-editor multi-source banner. --
    "warning_driver_source_no_selection":
        "Driver Sources: select one or more transforms in the "
        "scene before clicking +.",
    "warning_driver_source_self_excluded":
        "Driver Sources: the current RBF node was excluded from "
        "the selection (a node cannot drive itself); nothing to "
        "add.",
    "banner_multi_source_detected":
        "Multi-source driver detected on this node. Use the "
        "Driver Sources editor above; the single-driver picker "
        "below shows the first source only.",
    # -- M_UIRECONCILE_PLUS Item 4b: per-driver-source attribute
    #    picker button + dialog --
    "driver_source_attrs_btn":
        "Attrs...",
    "driver_source_attrs_btn_tip":
        "Pick the keyable attributes that drive the RBF for this "
        "source. Updating the list shuffles input[] indices; the "
        "node is removed and re-added in order under the hood.",
    "title_pick_driver_attrs":
        "Pick Driver Attributes",
    "summary_pick_driver_attrs":
        "Select the attributes on '{node}' that should feed the "
        "RBF input vector for this driver source.",
    "btn_ok":              "OK",
    "warning_driver_source_no_node_for_attrs":
        "Driver Sources: this source has no node assigned yet; "
        "remove it and add a fresh source from a scene selection.",
    # -- M_DRIVEN_MULTI Item 4c: driven-side multi-source UX --
    "section_driven_sources":          "Driven Targets",
    "driven_source_list_header":       "Driven Targets",
    "driven_source_list_empty_hint":
        "No driven targets registered. Select transforms in the "
        "scene + click + to add.",
    "driven_source_node_tip":          "Driven node (read-only mirror).",
    "driven_source_attrs_tip":
        "Attrs that this driven node receives from the RBF "
        "output[] vector (comma-joined preview).",
    "driven_source_attrs_btn":         "Attrs...",
    "driven_source_attrs_btn_tip":
        "Pick the attributes on this driven node that receive the "
        "RBF output. Updating the list re-wires output[] indices "
        "across all driven sources.",
    "title_remove_driven_source":      "Remove Driven Target",
    "summary_remove_driven_source":
        "Remove this driven target entry from the current node?",
    "title_pick_driven_attrs":         "Pick Driven Attributes",
    "summary_pick_driven_attrs":
        "Select the attributes on '{node}' that should receive the "
        "RBF output for this driven target.",
    "warning_driven_source_no_selection":
        "Driven Targets: select one or more transforms in the "
        "scene before clicking +.",
    "warning_driven_source_no_node_for_attrs":
        "Driven Targets: this target has no node assigned yet; "
        "remove it and add a fresh one from a scene selection.",
    # -- M_TABBED_EDITOR (2026-04-27): tabbed Driver/Driven editor
    #    UX matching the Tekken-8 AnimaRbfSolver paradigm. Replaces
    #    the M_B24b1 / M_DRIVEN_MULTI list-row editors. --
    "source_tab_add_tip":
        "Add a new tab from the current Maya selection (transform "
        "nodes only).",
    "source_tab_connect_tip":
        "Apply the selected attributes to this source. The plugin "
        "re-wires input[]/output[] indices across all sources to "
        "stay contiguous.",
    "source_tab_disconnect_tip":
        "Clear this source's attribute list. The plugin removes the "
        "source's wiring from input[]/output[] and shifts later "
        "sources up.",
    "driver_source_weight_label":      "Weight:",
    "driver_source_encoding_label":    "Encoding:",
}

_ZH = {
    "node":                u"\u8282\u70b9:",
    "refresh":             u"\u5237\u65b0",
    "pick_sel":            u"\u62fe\u53d6\u9009\u62e9",
    "new":                 u"\u65b0\u5efa",
    "delete":              u"\u5220\u9664",
    "general":             u"\u5e38\u89c4",
    "active":              u"\u542f\u7528",
    "type":                u"\u7c7b\u578b:",
    "icon_size":           u"\u56fe\u6807\u5927\u5c0f:",
    "vector_angle":        u"\u5411\u91cf\u89d2\u5ea6",
    "direction":           u"\u65b9\u5411:",
    "invert":              u"\u53cd\u8f6c",
    "rotation":            u"\u65cb\u8f6c",
    "use_rotate":          u"\u4f7f\u7528\u65cb\u8f6c",
    "angle":               u"\u89d2\u5ea6:",
    "center_angle":        u"\u4e2d\u5fc3\u89d2\u5ea6:",
    "twist":               u"\u626d\u8f6c",
    "twist_angle":         u"\u626d\u8f6c\u89d2\u5ea6:",
    "translation":         u"\u5e73\u79fb",
    "use_translate":       u"\u4f7f\u7528\u5e73\u79fb",
    "grow":                u"\u589e\u957f",
    "translate_min":       u"\u5e73\u79fb\u6700\u5c0f\u503c:",
    "translate_max":       u"\u5e73\u79fb\u6700\u5927\u503c:",
    "interpolation":       u"\u63d2\u503c:",
    "cone_display":        u"\u5706\u9525\u663e\u793a",
    "draw_cone":           u"\u7ed8\u5236\u5706\u9525",
    "draw_center_cone":    u"\u7ed8\u5236\u4e2d\u5fc3\u5706\u9525",
    "draw_weight":         u"\u7ed8\u5236\u6743\u91cd",
    "rbf":                 u"\u5f84\u5411\u57fa\u51fd\u6570",
    "kernel":              u"\u6838\u51fd\u6570:",
    "radius_type":         u"\u534a\u5f84\u7c7b\u578b:",
    "radius":              u"\u534a\u5f84:",
    "allow_neg":           u"\u5141\u8bb8\u8d1f\u6743\u91cd",
    "scale":               u"\u7f29\u653e:",
    "rbf_mode":            u"RBF \u6a21\u5f0f:",
    "generic_rbf":         u"\u901a\u7528 RBF",
    "distance_type":       u"\u8ddd\u79bb\u7c7b\u578b:",
    "matrix_rbf":          u"\u77e9\u9635 RBF",
    "twist_axis":          u"\u626d\u8f6c\u8f74:",
    "solver_display":      u"\u6c42\u89e3\u5668\u663e\u793a",
    "draw_origin":         u"\u7ed8\u5236\u539f\u70b9",
    "draw_poses":          u"\u7ed8\u5236\u59ff\u6001",
    "pose_length":         u"\u59ff\u6001\u957f\u5ea6:",
    "draw_indices":        u"\u7ed8\u5236\u7d22\u5f15",
    "index_distance":      u"\u7d22\u5f15\u8ddd\u79bb:",
    "draw_twist":          u"\u7ed8\u5236\u626d\u8f6c",
    "opposite":            u"\u53cd\u5411",
    "driver_index":        u"\u9a71\u52a8\u7d22\u5f15:",
    # -- M2.4a: scalar / enum widgets for M1.3 / M1.4 / M2.1a --
    "regularization":      u"\u6b63\u5219\u5316 (\u03bb)\uff1a",
    "solver_method":       u"\u6c42\u89e3\u5668\uff1a",
    "solver_auto":         u"\u81ea\u52a8",
    "solver_force_ge":     u"\u5f3a\u5236GE",
    "input_encoding":      u"\u8f93\u5165\u7f16\u7801\uff1a",
    "enc_raw":             u"\u539f\u59cb",
    "enc_quaternion":      u"\u56db\u5143\u6570",
    "enc_bendroll":        u"\u5f2f\u6eda",
    "enc_expmap":          u"\u6307\u6570\u6620\u5c04",
    "enc_swingtwist":      u"\u6446\u626d",
    # M_QUICKWINS Item 4a: \u6807\u7b7e\u66f4\u65b0\u4e3a"\u52a8\u4f5c\u8303\u56f4\u9650\u5236"\uff0c\u4e0e TD \u671f\u671b\u5bf9\u9f50
    "clamp_enabled":       u"\u52a8\u4f5c\u8303\u56f4\u9650\u5236\uff08\u8d85\u51fa\u5df2\u6ce8\u518c\u59ff\u52bf\u65f6\u505c\u6b62\uff09",
    "clamp_inflation":     u"\u9650\u5236\u81a8\u80c0\u6bd4\u4f8b\uff1a",
    "output_is_scale":     u"\u8f93\u51fa\u4e3a\u7f29\u653e",
    "output_is_scale_hdr": u"\u6807\u8bb0\u7f29\u653e\u901a\u9053\u8f93\u51fa\uff08M1.2 anchor 1.0\uff09",
    # -- M2.4b: ordered-list editors --
    "driver_rotate_order_label":   u"\u9a71\u52a8\u8f93\u5165\u65cb\u8f6c\u987a\u5e8f\uff1a",
    "rotate_order_empty_hint":     u"\u672a\u5b9a\u4e49\u9a71\u52a8\u65cb\u8f6c\u987a\u5e8f\u3002",
    "quat_group_start_label":      u"\u56db\u5143\u6570\u7ec4\u8d77\u59cb\u7d22\u5f15\uff08\u8f93\u51fa\u7d22\u5f15\uff09\uff1a",
    "quat_group_empty_hint":       u"\u672a\u5b9a\u4e49\u56db\u5143\u6570\u7ec4\u3002",
    "quat_group_start_value_tip":
        u"\u8f93\u51fa\u8d77\u59cb\u7d22\u5f15\u2014\u2014\u7ec4\u5360 4 \u4e2a\u8f93\u51fa (S, S+1, S+2, S+3)",
    "list_editor_add":             "+",
    "list_editor_remove":          u"\u2212",
    "list_editor_move_up":         u"\u2191",
    "list_editor_move_down":       u"\u2193",
    "list_editor_add_tip":         u"\u8ffd\u52a0\u65b0\u6761\u76ee",
    "list_editor_remove_tip":      u"\u5220\u9664\u9009\u4e2d\u6761\u76ee",
    "list_editor_move_up_tip":     u"\u4e0a\u79fb\u9009\u4e2d",
    "list_editor_move_down_tip":   u"\u4e0b\u79fb\u9009\u4e2d",
    # -- M3.0 --
    "menu_file":                   u"\u6587\u4ef6",
    "menu_edit":                   u"\u7f16\u8f91",
    "menu_tools":                  u"\u5de5\u5177",
    "menu_help":                   u"\u5e2e\u52a9",
    "menu_reset_confirms":         u"\u91cd\u7f6e\u786e\u8ba4\u5bf9\u8bdd\u6846",
    "reset_confirms_done":         u"\u5df2\u6e05\u7a7a\u786e\u8ba4\u504f\u597d",
    "confirm_dont_ask":            u"\u4e0d\u518d\u8be2\u95ee\u6b64\u64cd\u4f5c",
    "ok":                          u"\u786e\u5b9a",
    "cancel":                      u"\u53d6\u6d88",
    # -- M3.2 --
    "menu_mirror_node":            u"\u955c\u50cf\u8282\u70b9...",
    "row_mirror_this":             u"\u955c\u50cf\u6b64 pose",
    "title_mirror_node":           u"\u955c\u50cf\u8282\u70b9",
    "label_source_node":           u"\u6e90\u8282\u70b9\uff1a",
    "label_mirror_axis":            u"\u955c\u50cf\u8f74\uff1a",
    "label_naming_rule":            u"\u547d\u540d\u89c4\u5219\uff1a",
    "label_direction":              u"\u65b9\u5411\uff1a",
    "dir_auto":                     u"\u81ea\u52a8",
    "dir_forward":                  u"L -> R",
    "dir_reverse":                  u"R -> L",
    "label_custom_pattern":         u"\u6a21\u5f0f\uff1a",
    "label_custom_replacement":     u"\u66ff\u6362\uff1a",
    "label_target_preview":         u"\u76ee\u6807\u8282\u70b9\uff1a",
    "btn_mirror":                   u"\u955c\u50cf",
    "mirror_axis_yz":               u"YZ \u5e73\u9762\uff08\u7ffb X\uff09",
    "mirror_axis_xz":               u"XZ \u5e73\u9762\uff08\u7ffb Y\uff09",
    "mirror_axis_xy":               u"XY \u5e73\u9762\uff08\u7ffb Z\uff09",
    "naming_rule_l_r":              u"L_xxx <-> R_xxx",
    "naming_rule_xl_xr":            u"xxx_L <-> xxx_R",
    "naming_rule_left_right":       u"Left_xxx <-> Right_xxx",
    "naming_rule_xl_lc":            u"xxx_l <-> xxx_r\uff08\u5c0f\u5199\uff09",
    "naming_rule_lf_rt":            u"xxx_lf <-> xxx_rt",
    "naming_rule_lflf":             u"lf_xxx <-> rt_xxx",
    "naming_rule_custom":           u"\u81ea\u5b9a\u4e49...",
    "warn_both_directions_match":   u"\u4e24\u4e2a\u65b9\u5411\u90fd\u5339\u914d\u2014\u2014\u9ed8\u8ba4 forward",
    "warn_name_unchanged":          u"\u955c\u50cf\u540e\u540d\u5b57\u672a\u53d8\u2014\u2014\u68c0\u67e5\u89c4\u5219",
    "warn_name_no_match":           u"\u6e90\u540d\u4e0d\u5339\u914d\u9009\u4e2d\u89c4\u5219",
    "summary_mirror_node":          u"\u955c\u50cf\u8282\u70b9\u914d\u7f6e\uff1a",
    # -- M3.3 --
    "menu_import_rbf":                 u"\u5bfc\u5165 RBF \u914d\u7f6e...",
    "menu_export_selected":            u"\u5bfc\u51fa\u9009\u4e2d RBF...",
    "menu_export_all":                 u"\u5bfc\u51fa\u5168\u90e8 RBF...",
    "title_import_rbf":                u"\u5bfc\u5165 RBF \u914d\u7f6e",
    "title_import_replace":            u"\u8986\u76d6\u73b0\u6709\u8282\u70b9\uff1f",
    "summary_import_replace":
        u"Replace \u6a21\u5f0f\u5c06\u5220\u9664\u5e76\u91cd\u5efa\u4e0b\u5217\u8282\u70b9\u3002",
    "label_import_mode":               u"\u6a21\u5f0f\uff1a",
    "import_mode_add":                 u"Add",
    "import_mode_replace":             u"Replace",
    "label_import_preview":            u"\u9884\u68c0\u9884\u89c8\uff1a",
    "btn_import":                      u"\u5bfc\u5165",
    "status_dry_run_loading":          u"\u6b63\u5728\u9884\u68c0...",
    "status_dry_run_failed":           u"\u9884\u68c0\u5931\u8d25\u3002",
    "status_schema_version_error":     u"Schema \u7248\u672c\u4e0d\u5339\u914d\uff1a",
    "status_export_starting":          u"\u6b63\u5728\u5bfc\u51fa...",
    "status_export_done":              u"\u5bfc\u51fa\u5b8c\u6210\u3002",
    "status_export_failed":            u"\u5bfc\u51fa\u5931\u8d25\u3002",
    "status_import_starting":          u"\u6b63\u5728\u5bfc\u5165...",
    "status_import_done":              u"\u5bfc\u5165\u5b8c\u6210\u3002",
    "status_import_failed":            u"\u5bfc\u5165\u5931\u8d25\u3002",
    # -- M3.4 --
    "live_edit_toggle_label":          u"\u5b9e\u65f6\u7f16\u8f91",
    "live_edit_status_idle":           u"\u5f85\u547d",
    "live_edit_status_listening":      u"\u76d1\u542c {n} \u4e2a\u5c5e\u6027",
    "live_edit_warn_no_node":          u"\u672a\u9009\u4e2d\u8282\u70b9 \u2014 \u8bf7\u5148\u9009\u4e2d\u4e00\u4e2a RBF \u8282\u70b9",
    "live_edit_warn_no_attrs":         u"\u65e0 driver \u5c5e\u6027\u53ef\u76d1\u542c",
    "live_edit_warn_failed":           u"\u5b9e\u65f6\u7f16\u8f91\u5f00\u542f\u5931\u8d25",
    # -- M_B24b1 multi-source driver section --
    "section_driver_sources":          u"\u9a71\u52a8\u6e90",
    "driver_source_list_header":       u"\u9a71\u52a8\u6e90",
    "driver_source_list_empty_hint":
        u"\u672a\u914d\u7f6e\u9a71\u52a8\u6e90\u3002\u70b9\u51fb Add \u6dfb\u52a0\u3002",
    "driver_source_node_tip":          u"\u9a71\u52a8\u8282\u70b9 (\u53ea\u8bfb)\u3002",
    "driver_source_attrs_tip":         u"\u9a71\u52a8\u5c5e\u6027 (\u9017\u53f7\u8fde\u63a5)\u3002",
    "driver_source_weight_tip":
        u"\u6bcf\u6e90\u6743\u91cd\uff1bM_B24b \u4e0b\u6e38\u6d88\u8d39\u4fdd\u7559\u3002",
    "driver_source_encoding_tip":
        u"\u6bcf\u6e90\u8f93\u5165\u7f16\u7801\u679a\u4e3e (0..4)\u3002",
    "output_encoding_label":           u"\u8f93\u51fa\u7f16\u7801\uff1a",
    "output_encoding_combo_tip":
        u"\u8282\u70b9\u7ea7\u8f93\u51fa\u7f16\u7801 (forward-compat)\u3002",
    "output_encoding_euler":           u"Euler",
    "output_encoding_quaternion":      u"Quaternion",
    "output_encoding_expmap":          u"ExpMap",
    "title_remove_driver_source":      u"\u79fb\u9664\u9a71\u52a8\u6e90",
    "summary_remove_driver_source":
        u"\u4ece\u5f53\u524d\u8282\u70b9\u79fb\u9664\u8be5\u9a71\u52a8\u6e90\uff1f",
    # -- M_B24c Mirror \u591a\u6e90\u4fe1\u606f\u63d0\u793a
    #    (Generic mode \u652f\u6301; Matrix mode \u63a8\u8fdf\u5230 M_B24c2) --
    "title_mirror_multi_source":       u"\u955c\u50cf \u2014 \u591a\u6e90\u8282\u70b9",
    "summary_mirror_multi_source":
        u"\u6b64\u8282\u70b9\u914d\u7f6e\u4e86\u591a\u4e2a Generic \u6a21\u5f0f\u9a71\u52a8\u6e90\u3002"
        u"Mirror \u5c06\u9010\u6e90\u8fed\u4ee3\u5e76\u9010\u6e90\u5e94\u7528\u547d\u540d\u89c4\u5219"
        u"\uff08\u4e0d\u5339\u914d\u89c4\u5219\u7684\u6e90\u4fdd\u539f\u540d + \u8b66\u544a\uff09\u3002"
        u"Matrix \u6a21\u5f0f\u591a\u6e90\u955c\u50cf\u4ecd\u63a8\u8fdf\u81f3 M_B24c2 "
        u"\uff08addendum \u00a7M_B24c2-stub\uff09\uff0c\u5728\u5f15\u64ce\u5165\u53e3\u88ab\u62e6\u622a\u3002"
        u"\u7ee7\u7eed\uff1f",
    # -- M3.5 --
    "section_tools":                   u"\u5de5\u5177",
    "menu_profile_to_se":              u"\u8f93\u51fa Profile \u5230\u811a\u672c\u7f16\u8f91\u5668",
    "btn_refresh_profile":             u"\u5237\u65b0 Profile",
    "status_profile_pending":
        u"\u70b9\u51fb \u201c\u5237\u65b0 Profile\u201d \u4ee5\u8bca\u65ad\u5f53\u524d\u8282\u70b9\u3002",
    "status_profile_failed":           u"Profile \u751f\u6210\u5931\u8d25\u3002",
    # -- M3.6 --
    "menu_add_neutral_sample":         u"\u6dfb\u52a0\u4e2d\u6027\u6837\u672c",
    "menu_reset_auto_neutral":         u"\u91cd\u7f6e\u81ea\u52a8\u4e2d\u6027\u9ed8\u8ba4\u503c",
    "reset_auto_neutral_done":         u"\u81ea\u52a8\u4e2d\u6027\u504f\u597d\u5df2\u6e05\u9664",
    "title_add_neutral":               u"\u6dfb\u52a0\u4e2d\u6027\u6837\u672c",
    "summary_add_neutral":
        u"\u4f1a\u5728\u7d22\u5f15 0 \u63d2\u5165\u4e00\u4e2a rest pose\uff1b\u73b0\u6709 pose \u540e\u79fb\u4e00\u4f4d\u3002",
    "status_neutral_starting":         u"\u6b63\u5728\u6dfb\u52a0\u4e2d\u6027\u6837\u672c...",
    "status_neutral_done":             u"\u4e2d\u6027\u6837\u672c\u5df2\u6dfb\u52a0\u3002",
    "status_neutral_failed":           u"\u6dfb\u52a0\u4e2d\u6027\u6837\u672c\u5931\u8d25\u3002",
    # -- M3.1 --
    "menu_prune_poses":                u"\u4fee\u526a Pose...",
    "row_remove_this":                 u"\u5220\u9664\u6b64 pose",
    "title_prune_poses":               u"Pose \u4fee\u526a\u5668",
    "summary_prune_poses":
        u"Pose \u4fee\u526a\u5668\u5c06\u6309\u9009\u4e2d\u7684\u7c7b\u522b\u91cd\u5efa\u8be5 RBF \u8282\u70b9\u3002",
    "prune_cb_duplicates":             u"\u5220\u9664\u91cd\u590d pose",
    "prune_cb_redundant":              u"\u5220\u9664\u5197\u4f59 driver \u7ef4\u5ea6",
    "prune_cb_constant":               u"\u5220\u9664\u5e38\u91cf output",
    "label_prune_preview":             u"\u9884\u68c0\u9884\u89c8\uff1a",
    "btn_prune":                       u"\u4fee\u526a",
    "status_prune_starting":           u"\u6b63\u5728\u4fee\u526a...",
    "status_prune_done":               u"\u4fee\u526a\u5b8c\u6210\u3002",
    "status_prune_failed":             u"\u4fee\u526a\u5931\u8d25\u3002",
    # -- M3.7 --
    "menu_regenerate_aliases":         u"\u91cd\u65b0\u751f\u6210\u522b\u540d",
    "menu_force_regenerate_aliases":   u"\u5f3a\u5236\u91cd\u751f\u522b\u540d...",
    "title_force_alias":               u"\u5f3a\u5236\u91cd\u751f\u522b\u540d",
    "summary_force_alias":
        u"\u5f3a\u5236\u91cd\u751f\u5c06\u6e05\u9664\u8be5 shape \u4e0a\u7528\u6237\u624b\u52a8\u8bbe\u7f6e\u7684\u522b\u540d\u3002",
    "status_alias_starting":           u"\u6b63\u5728\u751f\u6210\u522b\u540d...",
    "status_alias_done":               u"\u522b\u540d\u5df2\u751f\u6210\u3002",
    "status_alias_failed":             u"\u522b\u540d\u751f\u6210\u5931\u8d25\u3002",
    "rbf_pose_editor":     u"RBF \u59ff\u6001\u7f16\u8f91\u5668",
    "auto_fill_bs":        u"\u81ea\u52a8\u586b\u5145\u878d\u5408\u53d8\u5f62",
    "driver":              u"\u9a71\u52a8",
    "driven":              u"\u88ab\u9a71\u52a8",
    "select":              u"\u9009\u62e9",
    "attributes":          u"\u5c5e\u6027",
    "poses":               u"\u59ff\u6001",
    "add_pose":            u"\u6dfb\u52a0\u59ff\u6001",
    "apply":               u"\u5e94\u7528",
    "connect":             u"\u8fde\u63a5",
    "disconnect":          u"\u65ad\u5f00",
    "reload":              u"\u91cd\u65b0\u52a0\u8f7d",
    "recall":              u"\u53ec\u56de",
    "update":              u"\u66f4\u65b0",
    "show_keyable":        u"\u663e\u793a\u53ef\u952e\u63a7",
    "show_non_keyable":    u"\u663e\u793a\u4e0d\u53ef\u952e\u63a7",
    "show_readable":       u"\u663e\u793a\u53ef\u8bfb",
    "show_writable":       u"\u663e\u793a\u53ef\u5199",
    "show_connected":      u"\u4ec5\u663e\u793a\u5df2\u8fde\u63a5",
    "show_hidden":         u"\u663e\u793a\u9690\u85cf",
    "show_user_defined":   u"\u663e\u793a\u7528\u6237\u81ea\u5b9a\u4e49",
    "language":            u"\u8bed\u8a00",
    "english":             u"\u82f1\u6587",
    "chinese":             u"\u4e2d\u6587",
    "open":                u"\u6253\u5f00 RBF Tools",
    "settings":            u"\u8bbe\u7f6e",
    # -- M_UIPOLISH per-widget tooltip ZH parity --
    "attribute_list_select_tip":
        u"\u5c06\u573a\u666f\u4e2d\u5f53\u524d\u9009\u62e9\u7684\u8282\u70b9 + \u901a\u9053\u76d2\u4e2d\u9009\u4e2d\u7684\u5c5e\u6027"
        u"\u52a0\u5165\u8be5\u5217\u8868\u3002\u53ef\u5728\u901a\u9053\u76d2\u591a\u9009\u4e00\u6b21\u6dfb\u52a0\u591a\u4e2a\u5c5e\u6027\u3002",
    "import_dialog_btn_tip":
        u"\u4f7f\u7528\u6240\u9009\u6a21\u5f0f\u5bfc\u5165 JSON \u6587\u4ef6\u3002Replace \u4f1a\u6e05\u7a7a\u5f53\u524d\u8282\u70b9\uff1b"
        u"Append \u4f1a\u5411\u5f53\u524d\u8282\u70b9\u8ffd\u52a0\u65b0\u59ff\u52bf\u3002",
    "live_edit_toggle_tip":
        u"\u5207\u6362 Live Edit\u3002\u5f00\u542f\u65f6\uff0c\u5bf9\u573a\u666f\u4e2d\u9a71\u52a8\u8282\u70b9\u7684\u4fee\u6539"
        u"\u4f1a\u5b9e\u65f6\u5199\u5165\u5f53\u524d\u9009\u4e2d\u7684\u59ff\u52bf\u884c\u3002",
    "mirror_dialog_btn_tip":
        u"\u6309\u5f53\u524d\u914d\u7f6e\u6267\u884c\u955c\u50cf\u3002\u5df2\u652f\u6301\u591a\u6e90 Generic \u6a21\u5f0f\uff1b"
        u"\u591a\u6e90 Matrix \u6a21\u5f0f\u5728\u5f15\u64ce\u5165\u53e3\u88ab\u62e6\u622a\uff08M_B24c2\uff09\u3002",
    "mirror_dialog_pattern_tip":
        u"\u81ea\u5b9a\u4e49\u6b63\u5219\u6a21\u5f0f\uff08Python re \u8bed\u6cd5\uff09\uff0c\u7528\u4e8e\u5339\u914d\u6e90"
        u"\u9a71\u52a8 / \u88ab\u9a71\u52a8\u8282\u70b9\u540d\u3002",
    "mirror_dialog_replacement_tip":
        u"\u6a21\u5f0f\u5339\u914d\u547d\u4e2d\u65f6\u4f7f\u7528\u7684\u66ff\u6362\u5b57\u7b26\u4e32\u3002",
    "node_selector_combo_tip":
        u"\u5f53\u524d\u6d3b\u52a8\u7684 RBFtools \u8282\u70b9\u3002\u4e0b\u62c9\u5217\u8868\u8986\u76d6\u573a\u666f\u4e2d\u6240\u6709 "
        u"RBFtools shape\u3002",
    "node_selector_pick_tip":
        u"\u5c06 Maya \u5f53\u524d\u9009\u62e9\u8bbe\u4e3a\u6d3b\u52a8\u8282\u70b9\u3002",
    "node_selector_new_tip":
        u"\u65b0\u5efa\u4e00\u4e2a RBFtools \u8282\u70b9 + transform\u3002",
    "node_selector_delete_tip":
        u"\u5220\u9664\u5f53\u524d\u6d3b\u52a8\u7684 RBFtools \u8282\u70b9\u53ca\u5176\u8fde\u63a5\u3002",
    "node_selector_refresh_tip":
        u"\u91cd\u65b0\u626b\u63cf\u573a\u666f\u5e76\u91cd\u5efa\u8282\u70b9\u5217\u8868\u3002",
    "pose_editor_apply_tip":
        u"\u5c06\u8868\u683c\u4e2d\u7684\u59ff\u52bf\u6570\u636e\u5199\u5165\u8282\u70b9\uff08Apply\uff09\u3002",
    "pose_editor_connect_tip":
        u"\u5c06\u9a71\u52a8 / \u88ab\u9a71\u52a8\u5c5e\u6027\u8fde\u63a5\u5230\u8282\u70b9\uff08Connect\uff09\u3002",
    "prune_dialog_btn_tip":
        u"\u6309\u6240\u9009\u7c7b\u522b\u6267\u884c Prune \u6d41\u7a0b\u3002",
    "profile_widget_refresh_tip":
        u"\u4e3a\u5f53\u524d\u6d3b\u52a8\u8282\u70b9\u91cd\u65b0\u8ba1\u7b97 Profile \u62a5\u544a\u3002",
    "warning_pose_pruner_no_node":
        u"Pose Pruner: \u8bf7\u5148\u9009\u62e9\u4e00\u4e2a RBF \u8282\u70b9\u3002",
    "warning_driver_source_no_selection":
        u"Driver Sources: \u70b9\u51fb + \u4e4b\u524d\u8bf7\u5728\u573a\u666f\u4e2d\u9009\u62e9\u4e00\u4e2a\u6216\u591a\u4e2a transform\u3002",
    "warning_driver_source_self_excluded":
        u"Driver Sources: \u5f53\u524d RBF \u8282\u70b9\u5df2\u88ab\u6392\u9664\uff08\u8282\u70b9\u4e0d\u80fd\u9a71\u52a8\u81ea\u8eab\uff09\uff0c"
        u"\u65e0\u53ef\u6dfb\u52a0\u7684\u6e90\u3002",
    "banner_multi_source_detected":
        u"\u8be5\u8282\u70b9\u5df2\u914d\u7f6e\u591a\u6e90\u9a71\u52a8\u3002\u8bf7\u4f7f\u7528\u4e0a\u65b9 Driver Sources \u7f16\u8f91\u5668\uff1b"
        u"\u4e0b\u65b9\u5355\u9a71\u52a8\u9009\u62e9\u5668\u4ec5\u663e\u793a\u7b2c\u4e00\u4e2a\u6e90\u3002",
    # M_UIRECONCILE_PLUS Item 4b \u5c5e\u6027\u9009\u62e9
    "driver_source_attrs_btn":
        u"\u5c5e\u6027\u2026",
    "driver_source_attrs_btn_tip":
        u"\u4e3a\u8be5\u9a71\u52a8\u6e90\u9009\u62e9\u53c2\u4e0e RBF \u8ba1\u7b97\u7684\u53ef\u952e\u5c5e\u6027\u3002"
        u"\u4fee\u6539\u5c5e\u6027\u5217\u8868\u4f1a\u91cd\u6392 input[] \u7d22\u5f15\uff08\u5185\u90e8\u6309\u987a\u5e8f"
        u"\u79fb\u9664\u5e76\u91cd\u65b0\u6dfb\u52a0\uff09\u3002",
    "title_pick_driver_attrs":
        u"\u9009\u62e9\u9a71\u52a8\u5c5e\u6027",
    "summary_pick_driver_attrs":
        u"\u9009\u62e9 '{node}' \u4e0a\u8981\u53c2\u4e0e\u8be5\u9a71\u52a8\u6e90 RBF \u8f93\u5165\u5411\u91cf\u7684\u5c5e\u6027\u3002",
    "btn_ok":              u"\u786e\u5b9a",
    "warning_driver_source_no_node_for_attrs":
        u"Driver Sources: \u8be5\u6e90\u5c1a\u672a\u6307\u5b9a\u8282\u70b9\uff1b\u8bf7\u5148\u79fb\u9664\u5b83\uff0c"
        u"\u7136\u540e\u5728\u573a\u666f\u4e2d\u9009\u62e9\u8282\u70b9\u91cd\u65b0\u6dfb\u52a0\u3002",
    # M_DRIVEN_MULTI Item 4c \u591a\u88ab\u9a71\u52a8
    "section_driven_sources":          u"\u88ab\u9a71\u52a8\u76ee\u6807",
    "driven_source_list_header":       u"\u88ab\u9a71\u52a8\u76ee\u6807",
    "driven_source_list_empty_hint":
        u"\u5c1a\u672a\u6ce8\u518c\u88ab\u9a71\u52a8\u76ee\u6807\u3002\u5728\u573a\u666f\u4e2d\u9009\u62e9 transform \u540e\u70b9 + \u6dfb\u52a0\u3002",
    "driven_source_node_tip":          u"\u88ab\u9a71\u52a8\u8282\u70b9\uff08\u53ea\u8bfb\uff09\u3002",
    "driven_source_attrs_tip":
        u"\u8be5\u88ab\u9a71\u52a8\u8282\u70b9\u4ece RBF output[] \u5411\u91cf\u63a5\u6536\u7684\u5c5e\u6027"
        u"\uff08\u9017\u53f7\u8fde\u63a5\u9884\u89c8\uff09\u3002",
    "driven_source_attrs_btn":         u"\u5c5e\u6027\u2026",
    "driven_source_attrs_btn_tip":
        u"\u4e3a\u8be5\u88ab\u9a71\u52a8\u76ee\u6807\u9009\u62e9\u63a5\u6536 RBF \u8f93\u51fa\u7684\u5c5e\u6027\u3002"
        u"\u4fee\u6539\u5c5e\u6027\u5217\u8868\u4f1a\u91cd\u6392\u6240\u6709\u88ab\u9a71\u52a8\u6e90\u7684 output[] \u7d22\u5f15\u3002",
    "title_remove_driven_source":      u"\u79fb\u9664\u88ab\u9a71\u52a8\u76ee\u6807",
    "summary_remove_driven_source":
        u"\u4ece\u5f53\u524d\u8282\u70b9\u79fb\u9664\u8be5\u88ab\u9a71\u52a8\u76ee\u6807\uff1f",
    "title_pick_driven_attrs":         u"\u9009\u62e9\u88ab\u9a71\u52a8\u5c5e\u6027",
    "summary_pick_driven_attrs":
        u"\u9009\u62e9 '{node}' \u4e0a\u8981\u63a5\u6536\u8be5\u88ab\u9a71\u52a8\u76ee\u6807 RBF \u8f93\u51fa\u7684\u5c5e\u6027\u3002",
    "warning_driven_source_no_selection":
        u"\u88ab\u9a71\u52a8\u76ee\u6807: \u70b9\u51fb + \u4e4b\u524d\u8bf7\u5728\u573a\u666f\u4e2d\u9009\u62e9\u4e00\u4e2a\u6216\u591a\u4e2a transform\u3002",
    "warning_driven_source_no_node_for_attrs":
        u"\u88ab\u9a71\u52a8\u76ee\u6807: \u8be5\u76ee\u6807\u5c1a\u672a\u6307\u5b9a\u8282\u70b9\uff1b\u8bf7\u5148\u79fb\u9664\u5b83\uff0c"
        u"\u7136\u540e\u5728\u573a\u666f\u4e2d\u9009\u62e9\u8282\u70b9\u91cd\u65b0\u6dfb\u52a0\u3002",
    # M_TABBED_EDITOR \u5b50\u5206\u9875\u8303\u5f0f
    "source_tab_add_tip":
        u"\u4ece\u5f53\u524d Maya \u9009\u62e9\u65b0\u5efa\u6807\u7b7e\uff08\u4ec5 transform \u8282\u70b9\uff09\u3002",
    "source_tab_connect_tip":
        u"\u5c06\u5f53\u524d\u9009\u4e2d\u7684\u5c5e\u6027\u5e94\u7528\u5230\u8be5\u6e90\u3002"
        u"\u63d2\u4ef6\u4f1a\u8de8\u6240\u6709\u6e90\u91cd\u6392 input[]/output[] \u7d22\u5f15\u4fdd\u6301\u8fde\u7eed\u3002",
    "source_tab_disconnect_tip":
        u"\u6e05\u7a7a\u8be5\u6e90\u7684\u5c5e\u6027\u5217\u8868\u3002"
        u"\u63d2\u4ef6\u4f1a\u4ece input[]/output[] \u4e2d\u79fb\u9664\u8be5\u6e90\u7684\u8fde\u63a5\u5e76\u4e0a\u79fb\u540e\u7eed\u6e90\u3002",
    "driver_source_weight_label":      u"\u6743\u91cd\uff1a",
    "driver_source_encoding_label":    u"\u7f16\u7801\uff1a",
}

_TABLES = {"en": _EN, "zh": _ZH}


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------

def current_language():
    """Return ``'en'`` or ``'zh'``."""
    if cmds.optionVar(exists=LANG_OPT_VAR):
        return cmds.optionVar(query=LANG_OPT_VAR)
    return "en"


def set_language(lang):
    """Persist the language choice."""
    cmds.optionVar(sv=(LANG_OPT_VAR, lang))


def tr(key):
    """Translate *key* into the current language string."""
    table = _TABLES.get(current_language(), _EN)
    return table.get(key, _EN.get(key, key))
