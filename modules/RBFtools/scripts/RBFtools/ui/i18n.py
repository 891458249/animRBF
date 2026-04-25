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
    "clamp_enabled":       "Clamp Driver to Pose Hull",
    "clamp_inflation":     "Clamp Inflation:",
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
    "clamp_enabled":       u"\u9a71\u52a8\u949b\u5236\u5230\u59ff\u6001\u5305\u56f4\u76d2",
    "clamp_inflation":     u"\u949b\u5236\u81a8\u80c0\u6bd4\u4f8b\uff1a",
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
