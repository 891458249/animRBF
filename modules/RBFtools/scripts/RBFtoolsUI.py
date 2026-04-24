# ---------------------------------------------------------------------
# RBFtoolsUI.py
#
# Unified UI for the RBF Tools plugin (RBFtools node).
# Consolidates all functionality from:
#   - AERBFtoolsTemplate.mel (Attribute Editor controls)
#   - RBFtoolsEditRBF.mel (RBF Pose Editor)
#   - RBFtoolsGetRadius.mel
#   - RBFtoolsLockRadiusType.mel
#   - RBFtoolsUpdateEvaluation.mel
#
# Usage:
#   import RBFtoolsUI
#   RBFtoolsUI.show()
#
# ---------------------------------------------------------------------

import maya.cmds as cmds
import maya.mel as mel
import math

WINDOW_NAME = "RBFtoolsMainUI"
WINDOW_TITLE = "RBF Tools"
WINDOW_WIDTH = 520
WINDOW_HEIGHT = 750

# =====================================================================
# Enum labels (must match the C++ node's enum order)
# =====================================================================

TYPE_LABELS = ["Vector Angle", "RBF"]

DIRECTION_LABELS = [
    "X", "Y", "Z",
    "-X", "-Y", "-Z",
]

INTERPOLATION_LABELS = [
    "Linear", "Smooth", "Smooth2",
]

KERNEL_LABELS = [
    "Gaussian", "Thin Plate", "Multi Quadratic Biharmonic",
    "Inv Multi Quadratic Biharmonic",
]

RADIUS_TYPE_LABELS = [
    "Mean Distance", "Variance", "Standard Deviation", "Custom",
]

DISTANCE_TYPE_LABELS = [
    "Euclidean", "Angle",
]

TWIST_AXIS_LABELS = [
    "X", "Y", "Z",
]

# =====================================================================
# i18n
# =====================================================================

LANG_OPT_VAR = "RBFtools_language"

_STRINGS = {
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
    # -- pose editor --
    "rbf_pose_editor":     "RBF Pose Editor",
    "auto_fill_bs":        "Auto Fill BlendShape",
    "driver":              "Driver",
    "driven":              "Driven",
    "select":              "Select",
    "attributes":          "Attributes",
    "poses":               "Poses:",
    "add_pose":            "Add Pose",
    "apply":               "Apply",
    "connect":             "Connect",
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
    # -- settings gear --
    "language":            "Language",
    "english":             "English",
    "chinese":             "Chinese",
}

_STRINGS_ZH = {
    # -- top bar --
    "node":                u"\u8282\u70b9:",
    "refresh":             u"\u5237\u65b0",
    "pick_sel":            u"\u62fe\u53d6\u9009\u62e9",
    "new":                 u"\u65b0\u5efa",
    "delete":              u"\u5220\u9664",
    # -- general --
    "general":             u"\u5e38\u89c4",
    "active":              u"\u542f\u7528",
    "type":                u"\u7c7b\u578b:",
    "icon_size":           u"\u56fe\u6807\u5927\u5c0f:",
    # -- vector angle --
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
    # -- rbf --
    "rbf":                 u"\u5f84\u5411\u57fa\u51fd\u6570",
    "kernel":              u"\u6838\u51fd\u6570:",
    "radius_type":         u"\u534a\u5f84\u7c7b\u578b:",
    "radius":              u"\u534a\u5f84:",
    "allow_neg":           u"\u5141\u8bb8\u8d1f\u6743\u91cd",
    "scale":               u"\u7f29\u653e:",
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
    # -- pose editor --
    "rbf_pose_editor":     u"RBF \u59ff\u6001\u7f16\u8f91\u5668",
    "auto_fill_bs":        u"\u81ea\u52a8\u586b\u5145\u878d\u5408\u53d8\u5f62",
    "driver":              u"\u9a71\u52a8",
    "driven":              u"\u88ab\u9a71\u52a8",
    "select":              u"\u9009\u62e9",
    "attributes":          u"\u5c5e\u6027",
    "poses":               u"\u59ff\u6001:",
    "add_pose":            u"\u6dfb\u52a0\u59ff\u6001",
    "apply":               u"\u5e94\u7528",
    "connect":             u"\u8fde\u63a5",
    "reload":              u"\u91cd\u65b0\u52a0\u8f7d",
    "recall":              u"\u53ec\u56de",
    "update":              u"\u66f4\u65b0",
    # -- filter --
    "show_keyable":        u"\u663e\u793a\u53ef\u952e\u63a7",
    "show_non_keyable":    u"\u663e\u793a\u4e0d\u53ef\u952e\u63a7",
    "show_readable":       u"\u663e\u793a\u53ef\u8bfb",
    "show_writable":       u"\u663e\u793a\u53ef\u5199",
    "show_connected":      u"\u4ec5\u663e\u793a\u5df2\u8fde\u63a5",
    "show_hidden":         u"\u663e\u793a\u9690\u85cf",
    "show_user_defined":   u"\u663e\u793a\u7528\u6237\u81ea\u5b9a\u4e49",
    # -- settings gear --
    "language":            u"\u8bed\u8a00",
    "english":             u"\u82f1\u6587",
    "chinese":             u"\u4e2d\u6587",
}

_LANG_MAP = {"en": _STRINGS, "zh": _STRINGS_ZH}


def _current_lang():
    if cmds.optionVar(exists=LANG_OPT_VAR):
        return cmds.optionVar(query=LANG_OPT_VAR)
    return "en"


def _tr(key):
    table = _LANG_MAP.get(_current_lang(), _STRINGS)
    return table.get(key, _STRINGS.get(key, key))


class RBFtoolsUI(object):
    """Unified UI for the RBF Tools plugin."""

    def __init__(self):
        self.current_node = ""
        self.driver_attr_count = 0
        self.driven_attr_count = 0

    # -----------------------------------------------------------------
    # utility
    # -----------------------------------------------------------------

    def _ensure_plugin(self):
        if not cmds.pluginInfo("RBFtools", query=True, loaded=True):
            cmds.loadPlugin("RBFtools")

    def _get_shape(self, node):
        if not node or not cmds.objExists(node):
            return node
        if cmds.nodeType(node) == "transform":
            shapes = cmds.listRelatives(node, shapes=True) or []
            if shapes:
                return shapes[0]
        return node

    def _get_transform(self, node):
        if not node or not cmds.objExists(node):
            return node
        if cmds.nodeType(node) == "RBFtools":
            parents = cmds.listRelatives(node, parent=True) or []
            if parents:
                return parents[0]
        return node

    def _update_evaluation(self, node=None):
        node = node or self.current_node
        if not node:
            return
        shape = self._get_shape(node)
        if not shape or not cmds.objExists(shape):
            return
        cmds.setAttr(shape + ".evaluate", 1)
        cmds.refresh()
        cmds.setAttr(shape + ".evaluate", 0)
        cmds.refresh()

    def _get_radius(self, node=None):
        node = node or self.current_node
        if not node:
            return
        shape = self._get_shape(node)
        if not shape or not cmds.objExists(shape):
            return
        cmds.setAttr(shape + ".radius", lock=False)
        rtype = cmds.getAttr(shape + ".radiusType")
        if rtype == 0:
            cmds.setAttr(shape + ".radius", cmds.getAttr(shape + ".meanDistance"), lock=True)
        elif rtype == 1:
            cmds.setAttr(shape + ".radius", cmds.getAttr(shape + ".variance"), lock=True)
        elif rtype == 2:
            val = cmds.getAttr(shape + ".variance")
            cmds.setAttr(shape + ".radius", math.sqrt(val), lock=True)
        self._update_evaluation(node)

    def _lock_radius_type(self, node=None):
        node = node or self.current_node
        if not node:
            return
        shape = self._get_shape(node)
        if not shape or not cmds.objExists(shape):
            return
        lock = cmds.getAttr(shape + ".kernel") == 0
        cmds.setAttr(shape + ".radiusType", lock=lock)
        self._update_evaluation(node)

    # -----------------------------------------------------------------
    # node list helpers
    # -----------------------------------------------------------------

    def _list_all_nodes(self):
        """Return all RBFtools transform nodes in the scene."""
        self._ensure_plugin()
        shapes = cmds.ls(type="RBFtools") or []
        transforms = []
        for s in shapes:
            t = self._get_transform(s)
            if t not in transforms:
                transforms.append(t)
        return transforms

    def _refresh_node_menu(self, *_args):
        items = cmds.optionMenu(self.ui_node_menu, query=True, itemListLong=True) or []
        for it in items:
            cmds.deleteUI(it)
        cmds.menuItem(label="< None >", parent=self.ui_node_menu)
        for n in self._list_all_nodes():
            cmds.menuItem(label=n, parent=self.ui_node_menu)

    def _on_node_changed(self, value):
        if value == "< None >":
            self.current_node = ""
        else:
            self.current_node = value
        self._load_node_settings()
        self._load_rbf_editor_data()

    def _select_node_from_scene(self, *_args):
        """Pick the first selected RBFtools node."""
        sel = cmds.ls(selection=True) or []
        for s in sel:
            shape = self._get_shape(s)
            if shape and cmds.objExists(shape) and cmds.nodeType(shape) == "RBFtools":
                self._refresh_node_menu()
                transform = self._get_transform(shape)
                cmds.optionMenu(self.ui_node_menu, edit=True, value=transform)
                self._on_node_changed(transform)
                return
        cmds.warning("No RBFtools node selected.")

    def _create_new_node(self, *_args):
        self._ensure_plugin()
        sel = cmds.ls(selection=True) or []
        node = cmds.createNode("RBFtools")
        transform = self._get_transform(node)
        if sel:
            cmds.select(sel, replace=True)
        self._refresh_node_menu()
        cmds.optionMenu(self.ui_node_menu, edit=True, value=transform)
        self._on_node_changed(transform)

    def _delete_current_node(self, *_args):
        if not self.current_node or not cmds.objExists(self.current_node):
            return
        cmds.delete(self.current_node)
        self.current_node = ""
        self._refresh_node_menu()
        self._load_node_settings()
        self._load_rbf_editor_data()

    # -----------------------------------------------------------------
    # load / sync controls from node
    # -----------------------------------------------------------------

    def _safe_get(self, attr, default=0):
        try:
            return cmds.getAttr(attr)
        except Exception:
            return default

    def _load_node_settings(self):
        """Populate all controls from current node attributes."""
        node = self.current_node
        has_node = bool(node) and cmds.objExists(node)
        shape = self._get_shape(node) if has_node else ""

        # -- General --
        if has_node:
            cmds.checkBox(self.ui_active, edit=True, value=self._safe_get(shape + ".active", True))
            cmds.optionMenuGrp(self.ui_type, edit=True, select=self._safe_get(shape + ".type", 0) + 1)
            cmds.floatSliderGrp(self.ui_icon_size, edit=True, value=self._safe_get(shape + ".iconSize", 1.0))
        else:
            cmds.checkBox(self.ui_active, edit=True, value=True)
            cmds.optionMenuGrp(self.ui_type, edit=True, select=1)
            cmds.floatSliderGrp(self.ui_icon_size, edit=True, value=1.0)

        # -- Vector Angle --
        if has_node:
            cmds.optionMenuGrp(self.ui_direction, edit=True, select=self._safe_get(shape + ".direction", 0) + 1)
            cmds.checkBox(self.ui_invert, edit=True, value=self._safe_get(shape + ".invert", False))
            cmds.checkBox(self.ui_use_rotate, edit=True, value=self._safe_get(shape + ".useRotate", True))
            cmds.floatSliderGrp(self.ui_angle, edit=True, value=self._safe_get(shape + ".angle", 45.0))
            cmds.floatSliderGrp(self.ui_center_angle, edit=True, value=self._safe_get(shape + ".centerAngle", 0.0))
            cmds.checkBox(self.ui_twist, edit=True, value=self._safe_get(shape + ".twist", False))
            cmds.floatSliderGrp(self.ui_twist_angle, edit=True, value=self._safe_get(shape + ".twistAngle", 90.0))
            cmds.checkBox(self.ui_use_translate, edit=True, value=self._safe_get(shape + ".useTranslate", False))
            cmds.checkBox(self.ui_grow, edit=True, value=self._safe_get(shape + ".grow", False))
            cmds.floatFieldGrp(self.ui_translate_min, edit=True, value1=self._safe_get(shape + ".translateMin", 0.0))
            cmds.floatFieldGrp(self.ui_translate_max, edit=True, value1=self._safe_get(shape + ".translateMax", 0.0))
            cmds.optionMenuGrp(self.ui_interpolation, edit=True, select=self._safe_get(shape + ".interpolation", 0) + 1)
            cmds.checkBox(self.ui_draw_cone, edit=True, value=self._safe_get(shape + ".drawCone", True))
            cmds.checkBox(self.ui_draw_center_cone, edit=True, value=self._safe_get(shape + ".drawCenterCone", False))
            cmds.checkBox(self.ui_draw_weight, edit=True, value=self._safe_get(shape + ".drawWeight", False))

        # -- RBF --
        if has_node:
            cmds.optionMenuGrp(self.ui_kernel, edit=True, select=self._safe_get(shape + ".kernel", 0) + 1)
            cmds.optionMenuGrp(self.ui_radius_type, edit=True, select=self._safe_get(shape + ".radiusType", 0) + 1)
            cmds.floatSliderGrp(self.ui_radius, edit=True, value=self._safe_get(shape + ".radius", 0.0))
            cmds.checkBox(self.ui_allow_neg, edit=True, value=self._safe_get(shape + ".allowNegativeWeights", True))
            cmds.floatSliderGrp(self.ui_scale, edit=True, value=self._safe_get(shape + ".scale", 1.0))
            cmds.optionMenuGrp(self.ui_distance_type, edit=True, select=self._safe_get(shape + ".distanceType", 0) + 1)
            cmds.optionMenuGrp(self.ui_twist_axis, edit=True, select=self._safe_get(shape + ".twistAxis", 0) + 1)
            cmds.checkBox(self.ui_draw_origin, edit=True, value=self._safe_get(shape + ".drawOrigin", False))
            cmds.checkBox(self.ui_draw_poses, edit=True, value=self._safe_get(shape + ".drawPoses", False))
            cmds.floatSliderGrp(self.ui_pose_length, edit=True, value=self._safe_get(shape + ".poseLength", 1.0))
            cmds.checkBox(self.ui_draw_indices, edit=True, value=self._safe_get(shape + ".drawIndices", False))
            cmds.floatSliderGrp(self.ui_index_distance, edit=True, value=self._safe_get(shape + ".indexDistance", 0.0))
            cmds.checkBox(self.ui_draw_twist_rbf, edit=True, value=self._safe_get(shape + ".drawTwist", False))
            cmds.checkBox(self.ui_opposite, edit=True, value=self._safe_get(shape + ".opposite", False))
            cmds.intSliderGrp(self.ui_driver_index, edit=True, value=self._safe_get(shape + ".driverIndex", 0))

        self._on_type_changed()

    # -----------------------------------------------------------------
    # attribute setters (called by UI callbacks)
    # -----------------------------------------------------------------

    def _set_attr(self, attr, value):
        node = self.current_node
        if not node:
            return
        shape = self._get_shape(node)
        if not shape or not cmds.objExists(shape):
            return
        try:
            cmds.setAttr(shape + "." + attr, value)
        except Exception as e:
            cmds.warning("Cannot set {}.{}: {}".format(shape, attr, e))

    def _set_float(self, attr):
        def cb(val):
            self._set_attr(attr, val)
        return cb

    def _set_int(self, attr):
        def cb(val):
            self._set_attr(attr, val)
        return cb

    # -----------------------------------------------------------------
    # type change: show/hide sections
    # -----------------------------------------------------------------

    def _on_type_changed(self, *_args):
        node = self.current_node
        if node:
            idx = cmds.optionMenuGrp(self.ui_type, query=True, select=True) - 1
            self._set_attr("type", idx)
        else:
            idx = cmds.optionMenuGrp(self.ui_type, query=True, select=True) - 1

        is_va = (idx == 0)
        is_rbf = (idx == 1)
        cmds.frameLayout(self.ui_va_frame, edit=True, visible=is_va, collapse=not is_va)
        cmds.frameLayout(self.ui_rbf_frame, edit=True, visible=is_rbf, collapse=not is_rbf)
        cmds.frameLayout(self.ui_rbf_editor_frame, edit=True, visible=is_rbf, collapse=not is_rbf)

    # -----------------------------------------------------------------
    # RBF kernel / radius callbacks
    # -----------------------------------------------------------------

    def _on_kernel_changed(self, *_args):
        if not self.current_node:
            return
        idx = cmds.optionMenuGrp(self.ui_kernel, query=True, select=True) - 1
        self._set_attr("kernel", idx)
        self._lock_radius_type(self.current_node)
        self._refresh_radius_ui()

    def _on_radius_type_changed(self, *_args):
        if not self.current_node:
            return
        idx = cmds.optionMenuGrp(self.ui_radius_type, query=True, select=True) - 1
        self._set_attr("radiusType", idx)
        self._get_radius(self.current_node)
        self._refresh_radius_ui()

    def _on_radius_changed(self, val):
        if not self.current_node:
            return
        shape = self._get_shape(self.current_node)
        if not shape:
            return
        rtype = cmds.getAttr(shape + ".radiusType")
        if rtype == 3:  # Custom
            self._set_attr("radius", val)
            self._update_evaluation(self.current_node)

    def _refresh_radius_ui(self):
        if not self.current_node:
            return
        shape = self._get_shape(self.current_node)
        if not shape or not cmds.objExists(shape):
            return
        rtype = cmds.getAttr(shape + ".radiusType")
        is_custom = (rtype == 3)
        cmds.floatSliderGrp(self.ui_radius, edit=True,
                            enable=is_custom,
                            value=cmds.getAttr(shape + ".radius"))
        kernel = cmds.getAttr(shape + ".kernel")
        cmds.optionMenuGrp(self.ui_radius_type, edit=True, enable=(kernel != 0))

    # -----------------------------------------------------------------
    # RBF Pose Editor helpers
    # -----------------------------------------------------------------

    def _clear_pose_items(self):
        children = cmds.scrollLayout(self.ui_pose_scroll, query=True, childArray=True) or []
        for c in children:
            cmds.deleteUI(c)

    def _clear_rbf_editor(self):
        self.driver_attr_count = 0
        self.driven_attr_count = 0
        cmds.textField(self.ui_rbf_driver_field, edit=True, text="")
        cmds.textField(self.ui_rbf_driven_field, edit=True, text="")
        cmds.iconTextScrollList(self.ui_rbf_driver_attr_list, edit=True, removeAll=True)
        cmds.iconTextScrollList(self.ui_rbf_driven_attr_list, edit=True, removeAll=True)
        self._clear_pose_items()

    def _load_rbf_editor_data(self, *_args):
        self._clear_rbf_editor()
        node = self.current_node
        if not node:
            return
        shape = self._get_shape(node)
        if not shape or not cmds.objExists(shape):
            return
        # Only relevant for RBF mode
        if cmds.getAttr(shape + ".type") != 1:
            return

        # Driver
        inputs = cmds.listConnections(
            shape + ".input", source=True, destination=False,
            plugs=True, connections=True, skipConversionNodes=True) or []
        driver = ""
        driver_attrs = []
        for i in range(0, len(inputs), 2):
            parts = inputs[i + 1].split(".")
            if not driver:
                driver = parts[0]
            if len(parts) > 1:
                driver_attrs.append(parts[1])
        self.driver_attr_count = len(driver_attrs)
        cmds.textField(self.ui_rbf_driver_field, edit=True, text=driver)
        if driver:
            self._rbf_list_attributes("driver")
            for a in driver_attrs:
                try:
                    cmds.iconTextScrollList(self.ui_rbf_driver_attr_list, edit=True, selectItem=a)
                except Exception:
                    pass

        # Driven
        outputs = cmds.listConnections(
            shape + ".output", source=False, destination=True,
            plugs=True, connections=True, skipConversionNodes=True) or []
        driven = ""
        driven_attrs = []
        for i in range(0, len(outputs), 2):
            parts = outputs[i + 1].split(".")
            if not driven:
                driven = parts[0]
            if len(parts) > 1:
                driven_attrs.append(parts[1])
        self.driven_attr_count = len(driven_attrs)
        cmds.textField(self.ui_rbf_driven_field, edit=True, text=driven)
        if driven:
            self._rbf_list_attributes("driven")
            for a in driven_attrs:
                try:
                    cmds.iconTextScrollList(self.ui_rbf_driven_attr_list, edit=True, selectItem=a)
                except Exception:
                    pass

        # Poses
        try:
            pose_ids = cmds.getAttr(shape + ".poses", multiIndices=True) or []
        except Exception:
            pose_ids = []

        if pose_ids and pose_ids[0] != 0:
            cmds.setAttr(shape + ".poses[0].poseInput[0]", 0)
            cmds.setAttr(shape + ".poses[0].poseValue[0]", 0)
            pose_ids = cmds.getAttr(shape + ".poses", multiIndices=True) or []

        for pid in pose_ids:
            self._read_pose_row(shape, pid)

    def _read_pose_row(self, shape, pid):
        """Create a row for an existing pose from the node data."""
        try:
            attr_size = cmds.getAttr(shape + ".input", size=True)
        except Exception:
            attr_size = 0
        try:
            val_size = cmds.getAttr(shape + ".output", size=True)
        except Exception:
            val_size = 0
        if attr_size == 0 or val_size == 0:
            return

        row_name = "wdUI_poseData_{}_row".format(pid)
        # columns: label + attr_size + separator + val_size + sep + Recall + sep + Update + sep + Delete = +8
        cmds.setParent(self.ui_pose_scroll)
        cmds.rowLayout(row_name, numberOfColumns=attr_size + val_size + 8)
        cmds.text(label="Pose {}".format(pid), width=55, align="left")
        for i in range(attr_size):
            v = self._safe_get("{}.poses[{}].poseInput[{}]".format(shape, pid, i), 0.0)
            cmds.floatField("wdUI_poseData_{}_a{}".format(pid, i), precision=3, value=v, width=60)
        cmds.separator(style="in", horizontal=False, width=20, height=20)
        for i in range(val_size):
            v = self._safe_get("{}.poses[{}].poseValue[{}]".format(shape, pid, i), 0.0)
            cmds.floatField("wdUI_poseData_{}_v{}".format(pid, i), precision=3, value=v, width=60)
        cmds.separator(style="none", width=8)
        cmds.button(label=_tr("recall"), width=50, command=lambda *a, _id=pid: self._recall_pose(_id))
        cmds.separator(style="none", width=4)
        cmds.button(label=_tr("update"), width=50, command=lambda *a, _id=pid: self._update_pose(_id))
        cmds.separator(style="none", width=4)
        cmds.button(label=_tr("delete"), width=50, command=lambda *a, _id=pid, _r=row_name: cmds.deleteUI(_r))
        cmds.setParent("..")

    def _rbf_get_node(self, role, *_args):
        """Load selected scene node as driver or driven."""
        sel = cmds.ls(selection=True) or []
        if not sel:
            return
        field = self.ui_rbf_driver_field if role == "driver" else self.ui_rbf_driven_field
        cmds.textField(field, edit=True, text=sel[0])
        self._rbf_list_attributes(role)

    # -- filter option var helpers --

    _FILTER_DEFAULTS = {
        "Keyable":       1,
        "Readable":      1,
        "Writable":      1,
        "NonKeyable":    0,
        "Connected":     0,
        "Hidden":        0,
        "UserDefined":   0,
    }

    def _filter_var(self, role, key):
        """Return the optionVar name for a filter toggle."""
        return "RBFtools_filter_{}_{}".format(role, key)

    def _get_filter(self, role, key):
        var = self._filter_var(role, key)
        if cmds.optionVar(exists=var):
            return cmds.optionVar(query=var)
        return self._FILTER_DEFAULTS.get(key, 0)

    def _set_filter(self, role, key, value):
        cmds.optionVar(iv=(self._filter_var(role, key), int(value)))

    def _toggle_filter(self, role, key, value, *_args):
        self._set_filter(role, key, value)
        self._rbf_list_attributes(role)

    def _build_filter_popup(self, parent_list, role):
        """Build a right-click popup menu with attribute filter toggles."""
        cmds.popupMenu(parent=parent_list)
        filters = [
            ("show_keyable",      "Keyable"),
            ("show_non_keyable",  "NonKeyable"),
            None,
            ("show_readable",     "Readable"),
            ("show_writable",     "Writable"),
            None,
            ("show_connected",    "Connected"),
            ("show_hidden",       "Hidden"),
            ("show_user_defined", "UserDefined"),
        ]
        for item in filters:
            if item is None:
                cmds.menuItem(divider=True)
            else:
                tr_key, filter_key = item
                val = self._get_filter(role, filter_key)
                cmds.menuItem(
                    label=_tr(tr_key),
                    checkBox=val,
                    command=lambda v, _r=role, _k=filter_key: self._toggle_filter(_r, _k, v))

    def _rbf_list_attributes(self, role):
        if role == "driver":
            lst = self.ui_rbf_driver_attr_list
            node = cmds.textField(self.ui_rbf_driver_field, query=True, text=True)
        else:
            lst = self.ui_rbf_driven_attr_list
            node = cmds.textField(self.ui_rbf_driven_field, query=True, text=True)

        cmds.iconTextScrollList(lst, edit=True, removeAll=True)
        if not node or not cmds.objExists(node):
            return []

        f_keyable      = self._get_filter(role, "Keyable")
        f_readable     = self._get_filter(role, "Readable")
        f_writable     = self._get_filter(role, "Writable")
        f_nonkeyable   = self._get_filter(role, "NonKeyable")
        f_connected    = self._get_filter(role, "Connected")
        f_hidden       = self._get_filter(role, "Hidden")
        f_userdef      = self._get_filter(role, "UserDefined")

        # Build listAttr flags -- never use multi=True (causes thousands
        # of indexed entries like weight[0]..weight[5000] and freezes Maya).
        kw = {}
        if f_keyable and not f_nonkeyable:
            kw["keyable"] = True
        if f_readable:
            kw["read"] = True
        if f_writable:
            kw["write"] = True
        if f_hidden:
            kw["hidden"] = True
        if f_userdef:
            kw["userDefined"] = True

        attrs = cmds.listAttr(node, **kw) or []

        # Filter out compound children (e.g. translateX when translate exists)
        # and multi-instance indices (e.g. weight[0]) to keep the list clean.
        attr_set = set(attrs)
        clean = []
        for a in attrs:
            # Skip indexed multi entries like "attr[0]"
            if "[" in a:
                continue
            # Skip compound children if their parent is also listed
            # (e.g. skip "translateX" if "translate" is present)
            if "." in a:
                continue
            clean.append(a)
        attrs = clean

        # Post-filter: connected only
        if f_connected:
            connected = set()
            conns = cmds.listConnections(node, plugs=True, connections=True,
                                          skipConversionNodes=True) or []
            for i in range(0, len(conns), 2):
                plug = conns[i].split(".")[-1]
                connected.add(plug)
            attrs = [a for a in attrs if a in connected]

        # Post-filter: non-keyable only (exclude keyable)
        if f_nonkeyable and not f_keyable:
            keyable_set = set(cmds.listAttr(node, keyable=True) or [])
            attrs = [a for a in attrs if a not in keyable_set]

        # Batch-append to UI list (single call, no per-item UI refresh)
        if attrs:
            cmds.iconTextScrollList(lst, edit=True, append=attrs)
        return attrs

    def _get_selected_attrs(self, role):
        lst = self.ui_rbf_driver_attr_list if role == "driver" else self.ui_rbf_driven_attr_list
        return cmds.iconTextScrollList(lst, query=True, selectItem=True) or []

    def _get_pose_indices(self):
        children = cmds.scrollLayout(self.ui_pose_scroll, query=True, childArray=True) or []
        ids = []
        for c in children:
            parts = c.split("_")
            try:
                idx = int(parts[-2])
                ids.append(idx)
            except (ValueError, IndexError):
                pass
        return ids

    def _get_new_pose_index(self):
        ids = self._get_pose_indices()
        if ids:
            return ids[-1] + 1
        return 0

    def _has_rest_pose(self):
        row = "wdUI_poseData_0_row"
        if not cmds.rowLayout(row, query=True, exists=True):
            return False
        children = cmds.rowLayout(row, query=True, childArray=True) or []
        total = 0.0
        for c in children:
            if "_v" in c:
                try:
                    total += cmds.floatField(c, query=True, value=True)
                except Exception:
                    pass
        return total == 0.0

    # -----------------------------------------------------------------
    # pose actions
    # -----------------------------------------------------------------

    def _add_pose(self, *_args):
        driver_attrs = self._get_selected_attrs("driver")
        driven_attrs = self._get_selected_attrs("driven")
        driver_node = cmds.textField(self.ui_rbf_driver_field, query=True, text=True)
        driven_node = cmds.textField(self.ui_rbf_driven_field, query=True, text=True)

        if not driver_node or not driven_node:
            cmds.warning("Please set both driver and driven nodes.")
            return
        if not driver_attrs:
            cmds.warning("No driver attributes selected.")
            return
        if not driven_attrs:
            cmds.warning("No driven attributes selected.")
            return

        # Check attribute count consistency
        if self.driver_attr_count > 0 and self.driver_attr_count != len(driver_attrs):
            cmds.warning("Driver attribute count differs from existing poses.")
            return
        if self.driven_attr_count > 0 and self.driven_attr_count != len(driven_attrs):
            cmds.warning("Driven attribute count differs from existing poses.")
            return

        self.driver_attr_count = len(driver_attrs)
        self.driven_attr_count = len(driven_attrs)

        pid = self._get_new_pose_index()

        # Blend shape auto-fill
        is_bs = cmds.objExists(driven_node) and cmds.nodeType(driven_node) == "blendShape"
        auto_fill = False
        try:
            auto_fill = cmds.optionVar(query="RBFtoolsAutoFillValues")
        except Exception:
            pass
        as_rest = False
        has_rest = self._has_rest_pose()

        if is_bs and auto_fill and pid == 0:
            result = cmds.confirmDialog(
                title="RBF Tools",
                message="Add the first pose as the rest pose?",
                button=["OK", "Cancel"],
                defaultButton="OK", cancelButton="Cancel")
            if result == "OK":
                as_rest = True

        row_name = "wdUI_poseData_{}_row".format(pid)
        cmds.setParent(self.ui_pose_scroll)
        # columns: label + drivers + separator + drivens + sep + Recall + sep + Update + sep + Delete = +8
        cmds.rowLayout(row_name, numberOfColumns=len(driver_attrs) + len(driven_attrs) + 8)
        cmds.text(label="Pose {}".format(pid), width=55, align="left")
        for i, a in enumerate(driver_attrs):
            v = cmds.getAttr(driver_node + "." + a) if cmds.objExists(driver_node) else 0.0
            cmds.floatField("wdUI_poseData_{}_a{}".format(pid, i), precision=3, value=v, width=60)
        cmds.separator(style="in", horizontal=False, width=20, height=20)
        for i, a in enumerate(driven_attrs):
            v = 0.0
            if not as_rest:
                if not (is_bs and auto_fill):
                    v = cmds.getAttr(driven_node + "." + a) if cmds.objExists(driven_node) else 0.0
                else:
                    position = pid - (1 if has_rest else 0)
                    if i == position:
                        v = 1.0
            cmds.floatField("wdUI_poseData_{}_v{}".format(pid, i), precision=3, value=v, width=60)
        cmds.separator(style="none", width=8)
        cmds.button(label=_tr("recall"), width=50, command=lambda *a, _id=pid: self._recall_pose(_id))
        cmds.separator(style="none", width=4)
        cmds.button(label=_tr("update"), width=50, command=lambda *a, _id=pid: self._update_pose(_id))
        cmds.separator(style="none", width=4)
        cmds.button(label=_tr("delete"), width=50, command=lambda *a, _id=pid, _r=row_name: cmds.deleteUI(_r))
        cmds.setParent("..")

    def _update_pose(self, pid):
        driver_attrs = self._get_selected_attrs("driver")
        driven_attrs = self._get_selected_attrs("driven")
        driver_node = cmds.textField(self.ui_rbf_driver_field, query=True, text=True)
        driven_node = cmds.textField(self.ui_rbf_driven_field, query=True, text=True)
        if not driver_node or not driven_node:
            return
        for i, a in enumerate(driver_attrs):
            v = cmds.getAttr(driver_node + "." + a)
            cmds.floatField("wdUI_poseData_{}_a{}".format(pid, i), edit=True, value=v)
        for i, a in enumerate(driven_attrs):
            v = cmds.getAttr(driven_node + "." + a)
            cmds.floatField("wdUI_poseData_{}_v{}".format(pid, i), edit=True, value=v)

    def _recall_pose(self, pid):
        driver_attrs = self._get_selected_attrs("driver")
        driven_attrs = self._get_selected_attrs("driven")
        driver_node = cmds.textField(self.ui_rbf_driver_field, query=True, text=True)
        driven_node = cmds.textField(self.ui_rbf_driven_field, query=True, text=True)
        if not driver_node or not driven_node:
            return

        for i, a in enumerate(driver_attrs):
            plug = driver_node + "." + a
            conns = cmds.listConnections(plug, source=True, destination=False,
                                         plugs=True, connections=True,
                                         skipConversionNodes=True) or []
            if conns:
                cmds.disconnectAttr(conns[1], conns[0])
            v = cmds.floatField("wdUI_poseData_{}_a{}".format(pid, i), query=True, value=True)
            cmds.setAttr(plug, v)
            if conns:
                cmds.connectAttr(conns[1], conns[0])

        for i, a in enumerate(driven_attrs):
            plug = driven_node + "." + a
            conns = cmds.listConnections(plug, source=True, destination=False,
                                         plugs=True, connections=True,
                                         skipConversionNodes=True) or []
            if conns:
                cmds.disconnectAttr(conns[1], conns[0])
            v = cmds.floatField("wdUI_poseData_{}_v{}".format(pid, i), query=True, value=True)
            cmds.setAttr(plug, v)
            if conns:
                cmds.connectAttr(conns[1], conns[0])

    # -----------------------------------------------------------------
    # apply / connect
    # -----------------------------------------------------------------

    def _create_driver_node(self):
        driver_node = cmds.textField(self.ui_rbf_driver_field, query=True, text=True)
        driven_node = cmds.textField(self.ui_rbf_driven_field, query=True, text=True)
        if not driver_node or not driven_node:
            return ""
        self._ensure_plugin()
        sel = cmds.ls(selection=True) or []
        node = cmds.createNode("RBFtools")
        cmds.setAttr(node + ".type", 1)
        if sel:
            cmds.select(sel, replace=True)
        return self._get_transform(node)

    def _delete_node_data(self, node):
        shape = self._get_shape(node)
        for attr in ["input", "poses", "output"]:
            try:
                ids = cmds.getAttr(shape + "." + attr, multiIndices=True) or []
            except Exception:
                ids = []
            for idx in ids:
                try:
                    cmds.removeMultiInstance(shape + ".{}[{}]".format(attr, idx), b=True)
                except Exception:
                    pass
        return self._get_transform(shape)

    def _create_poses_on_node(self, node, connect=False):
        driver_attrs = self._get_selected_attrs("driver")
        driven_attrs = self._get_selected_attrs("driven")
        driver_node = cmds.textField(self.ui_rbf_driver_field, query=True, text=True)
        driven_node = cmds.textField(self.ui_rbf_driven_field, query=True, text=True)
        if not driver_node or not driven_node or not driver_attrs or not driven_attrs:
            return

        shape = self._get_shape(node)
        sel = []
        if connect:
            sel = cmds.ls(selection=True) or []
            if not sel:
                return

        for i, a in enumerate(driver_attrs):
            cmds.connectAttr(driver_node + "." + a, shape + ".input[{}]".format(i), force=True)

        ids = self._get_pose_indices()
        pose_count = len(sel) if connect else len(ids)

        for p in range(pose_count):
            if connect:
                for i, a in enumerate(driver_attrs):
                    cmds.connectAttr(
                        sel[p] + "." + a,
                        shape + ".poses[{}].poseInput[{}]".format(p, i), force=True)
                for i, a in enumerate(driven_attrs):
                    cmds.connectAttr(
                        sel[p] + "." + a,
                        shape + ".poses[{}].poseValue[{}]".format(p, i), force=True)
            else:
                pid = ids[p]
                for i in range(len(driver_attrs)):
                    v = cmds.floatField("wdUI_poseData_{}_a{}".format(pid, i), query=True, value=True)
                    cmds.setAttr(shape + ".poses[{}].poseInput[{}]".format(p, i), v)
                for i in range(len(driven_attrs)):
                    v = cmds.floatField("wdUI_poseData_{}_v{}".format(pid, i), query=True, value=True)
                    cmds.setAttr(shape + ".poses[{}].poseValue[{}]".format(p, i), v)

        for i, a in enumerate(driven_attrs):
            cmds.connectAttr(shape + ".output[{}]".format(i), driven_node + "." + a, force=True)

        cmds.setAttr(shape + ".evaluate", 0)
        cmds.setAttr(shape + ".evaluate", 1)

    def _apply_rbf(self, connect=False, *_args):
        sel = cmds.ls(selection=True) or []

        node = self.current_node
        if not node or not cmds.objExists(node):
            node = self._create_driver_node()
        else:
            node = self._delete_node_data(node)

        if node:
            self._create_poses_on_node(node, connect)

        self._refresh_node_menu()
        try:
            cmds.optionMenu(self.ui_node_menu, edit=True, value=node)
        except Exception:
            pass
        self.current_node = node
        self._load_node_settings()
        # Do NOT call _load_rbf_editor_data() here -- it would clear
        # all pose rows and try to re-read from the node, which may
        # compact indices and lose pose data.  The UI already shows
        # the correct poses.  User can click "Reload" to refresh.

        if sel:
            try:
                cmds.select(sel, replace=True)
            except Exception:
                pass

        cmds.inViewMessage(
            amg="<hl>RBF data applied.</hl>",
            pos="topCenter", fade=True)

    # -----------------------------------------------------------------
    # language switch
    # -----------------------------------------------------------------

    def _switch_language(self, lang, *_args):
        cmds.optionVar(sv=(LANG_OPT_VAR, lang))
        saved_node = self.current_node
        self.show()
        if saved_node and cmds.objExists(saved_node):
            transform = self._get_transform(self._get_shape(saved_node))
            try:
                cmds.optionMenu(self.ui_node_menu, edit=True, value=transform)
                self._on_node_changed(transform)
            except Exception:
                pass
        # also rebuild the top menu bar
        try:
            import RBFtoolsMenu
            RBFtoolsMenu.create()
        except Exception:
            pass

    # -----------------------------------------------------------------
    # build UI
    # -----------------------------------------------------------------

    def show(self):
        self._ensure_plugin()

        if cmds.window(WINDOW_NAME, exists=True):
            cmds.deleteUI(WINDOW_NAME)

        T = _tr  # shorthand

        cmds.window(WINDOW_NAME, title=WINDOW_TITLE,
                     widthHeight=(WINDOW_WIDTH, WINDOW_HEIGHT),
                     sizeable=True)

        main_form = cmds.formLayout()

        # ===================== Node selector bar =====================
        node_row = cmds.formLayout(height=28)
        nd_label = cmds.text(label=T("node"), width=40)
        self.ui_node_menu = cmds.optionMenu(changeCommand=self._on_node_changed)
        cmds.menuItem(label="< None >")
        nd_refresh = cmds.button(label=T("refresh"), width=60, command=self._refresh_node_menu)
        nd_pick    = cmds.button(label=T("pick_sel"), width=60, command=self._select_node_from_scene)
        nd_new     = cmds.button(label=T("new"), width=50, command=self._create_new_node)
        nd_del     = cmds.button(label=T("delete"), width=55, command=self._delete_current_node)

        # -- gear settings button --
        gear_btn = cmds.iconTextButton(
            style="iconOnly", image="gear.png",
            width=24, height=24,
            annotation=T("language"))
        gear_popup = cmds.popupMenu(parent=gear_btn, button=1)
        cmds.menuItem(label=T("language"), subMenu=True, parent=gear_popup)
        cmds.radioMenuItemCollection()
        cmds.menuItem(label=T("english"),
                       radioButton=(_current_lang() == "en"),
                       command=lambda *a: self._switch_language("en"))
        cmds.menuItem(label=T("chinese"),
                       radioButton=(_current_lang() == "zh"),
                       command=lambda *a: self._switch_language("zh"))
        cmds.setParent("..", menu=True)

        cmds.formLayout(node_row, edit=True,
            attachForm=[
                (nd_label, "left", 0), (nd_label, "top", 7),
                (self.ui_node_menu, "top", 3),
                (nd_refresh, "top", 2),
                (nd_pick, "top", 2),
                (nd_new, "top", 2),
                (nd_del, "top", 2),
                (gear_btn, "top", 2), (gear_btn, "right", 0),
            ],
            attachControl=[
                (self.ui_node_menu, "left", 3, nd_label),
                (self.ui_node_menu, "right", 5, nd_refresh),
                (nd_refresh, "right", 3, nd_pick),
                (nd_pick, "right", 3, nd_new),
                (nd_new, "right", 3, nd_del),
                (nd_del, "right", 5, gear_btn),
            ],
            attachNone=[
                (nd_label, "right"),
                (nd_refresh, "left"),
                (nd_pick, "left"),
                (nd_new, "left"),
                (nd_del, "left"),
                (gear_btn, "left"),
            ])
        cmds.setParent("..")

        sep_top = cmds.separator(style="in", height=8)

        # ===================== Scroll area =====================
        scroll = cmds.scrollLayout(childResizable=True)

        # ============== General ==============
        cmds.frameLayout(label=T("general"), collapsable=True, collapse=False,
                         marginWidth=5, marginHeight=5)
        cmds.columnLayout(adjustableColumn=True, rowSpacing=4)
        self.ui_active = cmds.checkBox(label=T("active"), value=True,
                                        changeCommand=lambda v: self._set_attr("active", v))
        self.ui_type = cmds.optionMenuGrp(label=T("type"), columnWidth2=(80, 150),
                                           changeCommand=self._on_type_changed)
        for t in TYPE_LABELS:
            cmds.menuItem(label=t)
        self.ui_icon_size = cmds.floatSliderGrp(label=T("icon_size"), field=True,
                                                 columnWidth3=(80, 60, 100),
                                                 minValue=0.01, maxValue=10.0, value=1.0,
                                                 dragCommand=self._set_float("iconSize"),
                                                 changeCommand=self._set_float("iconSize"))
        cmds.setParent("..")
        cmds.setParent("..")

        # ============== Vector Angle ==============
        self.ui_va_frame = cmds.frameLayout(label=T("vector_angle"), collapsable=True,
                                             collapse=False, marginWidth=5, marginHeight=5)
        cmds.columnLayout(adjustableColumn=True, rowSpacing=4)

        self.ui_direction = cmds.optionMenuGrp(label=T("direction"), columnWidth2=(80, 100),
                                                changeCommand=lambda *a: self._set_attr("direction", cmds.optionMenuGrp(self.ui_direction, q=True, select=True) - 1))
        for d in DIRECTION_LABELS:
            cmds.menuItem(label=d)
        self.ui_invert = cmds.checkBox(label=T("invert"),
                                        changeCommand=lambda v: self._set_attr("invert", v))
        cmds.separator(style="in", height=8)

        # Rotation
        cmds.text(label=T("rotation"), font="boldLabelFont", align="left")
        self.ui_use_rotate = cmds.checkBox(label=T("use_rotate"),
                                            changeCommand=lambda v: self._set_attr("useRotate", v))
        self.ui_angle = cmds.floatSliderGrp(label=T("angle"), field=True,
                                             columnWidth3=(80, 60, 100),
                                             minValue=0.01, maxValue=180.0, value=45.0,
                                             dragCommand=self._set_float("angle"),
                                             changeCommand=self._set_float("angle"))
        self.ui_center_angle = cmds.floatSliderGrp(label=T("center_angle"), field=True,
                                                    columnWidth3=(80, 60, 100),
                                                    minValue=0.0, maxValue=180.0, value=0.0,
                                                    dragCommand=self._set_float("centerAngle"),
                                                    changeCommand=self._set_float("centerAngle"))
        self.ui_twist = cmds.checkBox(label=T("twist"),
                                       changeCommand=lambda v: self._set_attr("twist", v))
        self.ui_twist_angle = cmds.floatSliderGrp(label=T("twist_angle"), field=True,
                                                   columnWidth3=(80, 60, 100),
                                                   minValue=0.01, maxValue=180.0, value=90.0,
                                                   dragCommand=self._set_float("twistAngle"),
                                                   changeCommand=self._set_float("twistAngle"))
        cmds.separator(style="in", height=8)

        # Translation
        cmds.text(label=T("translation"), font="boldLabelFont", align="left")
        self.ui_use_translate = cmds.checkBox(label=T("use_translate"),
                                               changeCommand=lambda v: self._set_attr("useTranslate", v))
        self.ui_grow = cmds.checkBox(label=T("grow"),
                                      changeCommand=lambda v: self._set_attr("grow", v))
        self.ui_translate_min = cmds.floatFieldGrp(label=T("translate_min"), numberOfFields=1,
                                                    columnWidth2=(80, 80), value1=0.0,
                                                    changeCommand=lambda *a: self._set_attr("translateMin", cmds.floatFieldGrp(self.ui_translate_min, q=True, value1=True)))
        self.ui_translate_max = cmds.floatFieldGrp(label=T("translate_max"), numberOfFields=1,
                                                    columnWidth2=(80, 80), value1=0.0,
                                                    changeCommand=lambda *a: self._set_attr("translateMax", cmds.floatFieldGrp(self.ui_translate_max, q=True, value1=True)))
        cmds.separator(style="in", height=8)

        # Interpolation
        self.ui_interpolation = cmds.optionMenuGrp(label=T("interpolation"), columnWidth2=(80, 150),
                                                    changeCommand=lambda *a: self._set_attr("interpolation", cmds.optionMenuGrp(self.ui_interpolation, q=True, select=True) - 1))
        for lbl in INTERPOLATION_LABELS:
            cmds.menuItem(label=lbl)

        cmds.separator(style="in", height=8)

        # Cone Display
        cmds.frameLayout(label=T("cone_display"), collapsable=True, collapse=True,
                         marginWidth=5, marginHeight=3)
        cmds.columnLayout(adjustableColumn=True, rowSpacing=2)
        self.ui_draw_cone = cmds.checkBox(label=T("draw_cone"),
                                           changeCommand=lambda v: self._set_attr("drawCone", v))
        self.ui_draw_center_cone = cmds.checkBox(label=T("draw_center_cone"),
                                                  changeCommand=lambda v: self._set_attr("drawCenterCone", v))
        self.ui_draw_weight = cmds.checkBox(label=T("draw_weight"),
                                             changeCommand=lambda v: self._set_attr("drawWeight", v))
        cmds.setParent("..")
        cmds.setParent("..")

        cmds.setParent("..")  # columnLayout
        cmds.setParent("..")  # VA frameLayout

        # ============== RBF Settings ==============
        self.ui_rbf_frame = cmds.frameLayout(label=T("rbf"), collapsable=True,
                                              collapse=False, marginWidth=5, marginHeight=5)
        cmds.columnLayout(adjustableColumn=True, rowSpacing=4)

        self.ui_kernel = cmds.optionMenuGrp(label=T("kernel"), columnWidth2=(80, 200),
                                             changeCommand=self._on_kernel_changed)
        for k in KERNEL_LABELS:
            cmds.menuItem(label=k)
        self.ui_radius_type = cmds.optionMenuGrp(label=T("radius_type"), columnWidth2=(80, 150),
                                                  changeCommand=self._on_radius_type_changed)
        for r in RADIUS_TYPE_LABELS:
            cmds.menuItem(label=r)
        self.ui_radius = cmds.floatSliderGrp(label=T("radius"), field=True,
                                              columnWidth3=(80, 60, 100),
                                              minValue=0.0, maxValue=10.0, value=0.0,
                                              dragCommand=self._on_radius_changed,
                                              changeCommand=self._on_radius_changed)
        self.ui_allow_neg = cmds.checkBox(label=T("allow_neg"), value=True,
                                           changeCommand=lambda v: self._set_attr("allowNegativeWeights", v))
        self.ui_scale = cmds.floatSliderGrp(label=T("scale"), field=True,
                                             columnWidth3=(80, 60, 100),
                                             minValue=0.0, maxValue=10.0, value=1.0,
                                             dragCommand=self._set_float("scale"),
                                             changeCommand=self._set_float("scale"))
        cmds.separator(style="in", height=8)

        # Generic RBF
        cmds.frameLayout(label=T("generic_rbf"), collapsable=True, collapse=True,
                         marginWidth=5, marginHeight=3)
        cmds.columnLayout(adjustableColumn=True, rowSpacing=2)
        self.ui_distance_type = cmds.optionMenuGrp(label=T("distance_type"), columnWidth2=(80, 120),
                                                    changeCommand=lambda *a: (self._set_attr("distanceType", cmds.optionMenuGrp(self.ui_distance_type, q=True, select=True) - 1), self._update_evaluation()))
        for d in DISTANCE_TYPE_LABELS:
            cmds.menuItem(label=d)
        cmds.setParent("..")
        cmds.setParent("..")

        # Matrix RBF
        cmds.frameLayout(label=T("matrix_rbf"), collapsable=True, collapse=True,
                         marginWidth=5, marginHeight=3)
        cmds.columnLayout(adjustableColumn=True, rowSpacing=2)
        self.ui_twist_axis = cmds.optionMenuGrp(label=T("twist_axis"), columnWidth2=(80, 80),
                                                 changeCommand=lambda *a: self._set_attr("twistAxis", cmds.optionMenuGrp(self.ui_twist_axis, q=True, select=True) - 1))
        for t in TWIST_AXIS_LABELS:
            cmds.menuItem(label=t)

        # Solver Display
        cmds.frameLayout(label=T("solver_display"), collapsable=True, collapse=True,
                         marginWidth=5, marginHeight=3)
        cmds.columnLayout(adjustableColumn=True, rowSpacing=2)
        self.ui_draw_origin = cmds.checkBox(label=T("draw_origin"),
                                             changeCommand=lambda v: self._set_attr("drawOrigin", v))
        self.ui_draw_poses = cmds.checkBox(label=T("draw_poses"),
                                            changeCommand=lambda v: self._set_attr("drawPoses", v))
        self.ui_pose_length = cmds.floatSliderGrp(label=T("pose_length"), field=True,
                                                   columnWidth3=(80, 60, 80),
                                                   minValue=0.01, maxValue=10.0, value=1.0,
                                                   dragCommand=self._set_float("poseLength"),
                                                   changeCommand=self._set_float("poseLength"))
        self.ui_draw_indices = cmds.checkBox(label=T("draw_indices"),
                                              changeCommand=lambda v: self._set_attr("drawIndices", v))
        self.ui_index_distance = cmds.floatSliderGrp(label=T("index_distance"), field=True,
                                                      columnWidth3=(80, 60, 80),
                                                      minValue=0.0, maxValue=100.0, value=0.0,
                                                      dragCommand=self._set_float("indexDistance"),
                                                      changeCommand=self._set_float("indexDistance"))
        self.ui_draw_twist_rbf = cmds.checkBox(label=T("draw_twist"),
                                                changeCommand=lambda v: self._set_attr("drawTwist", v))
        self.ui_opposite = cmds.checkBox(label=T("opposite"),
                                          changeCommand=lambda v: self._set_attr("opposite", v))
        cmds.separator(style="in", height=4)
        self.ui_driver_index = cmds.intSliderGrp(label=T("driver_index"), field=True,
                                                  columnWidth3=(80, 50, 80),
                                                  minValue=0, maxValue=20, value=0,
                                                  dragCommand=self._set_int("driverIndex"),
                                                  changeCommand=self._set_int("driverIndex"))
        cmds.setParent("..")  # columnLayout
        cmds.setParent("..")  # Solver Display frameLayout

        cmds.setParent("..")  # columnLayout
        cmds.setParent("..")  # Matrix RBF frameLayout

        cmds.setParent("..")  # columnLayout
        cmds.setParent("..")  # RBF frameLayout

        # ============== RBF Pose Editor ==============
        self.ui_rbf_editor_frame = cmds.frameLayout(label=T("rbf_pose_editor"),
                                                     collapsable=True, collapse=False,
                                                     marginWidth=5, marginHeight=5)
        cmds.columnLayout(adjustableColumn=True, rowSpacing=4)

        # Settings menu
        cmds.rowLayout(numberOfColumns=2, adjustableColumn=2,
                       columnWidth2=(140, 100))
        try:
            auto_fill_state = cmds.optionVar(query="RBFtoolsAutoFillValues")
        except Exception:
            auto_fill_state = 0
        cmds.checkBox(label=T("auto_fill_bs"),
                       value=auto_fill_state,
                       changeCommand=lambda v: cmds.optionVar(iv=("RBFtoolsAutoFillValues", int(v))))
        cmds.text(label="")
        cmds.setParent("..")

        cmds.separator(style="in", height=6)

        # Driver / Driven row
        driver_driven_form = cmds.formLayout(height=175)

        drv_label = cmds.text(label=T("driver"), width=50, align="left")
        self.ui_rbf_driver_field = cmds.textField(width=100)
        drv_btn = cmds.button(label=T("select"), width=55,
                               command=lambda *a: self._rbf_get_node("driver"))
        drv_attr_label = cmds.text(label=T("attributes"), width=50, align="left")
        self.ui_rbf_driver_attr_list = cmds.iconTextScrollList(
            allowMultiSelection=True, height=120)
        self._build_filter_popup(self.ui_rbf_driver_attr_list, "driver")

        div = cmds.separator(style="in", horizontal=False)

        dvn_label = cmds.text(label=T("driven"), width=50, align="left")
        self.ui_rbf_driven_field = cmds.textField(width=100)
        dvn_btn = cmds.button(label=T("select"), width=55,
                               command=lambda *a: self._rbf_get_node("driven"))
        dvn_attr_label = cmds.text(label=T("attributes"), width=50, align="left")
        self.ui_rbf_driven_attr_list = cmds.iconTextScrollList(
            allowMultiSelection=True, height=120)
        self._build_filter_popup(self.ui_rbf_driven_attr_list, "driven")

        cmds.formLayout(driver_driven_form, edit=True,
                         attachForm=[
                             (drv_label, "top", 5), (drv_label, "left", 5),
                             (self.ui_rbf_driver_field, "top", 2),
                             (drv_btn, "top", 0),
                             (drv_attr_label, "left", 5),
                             (div, "top", 5), (div, "bottom", 5),
                             (dvn_label, "top", 5),
                             (self.ui_rbf_driven_field, "top", 2),
                             (dvn_btn, "top", 0), (dvn_btn, "right", 5),
                             (self.ui_rbf_driven_attr_list, "right", 5),
                         ],
                         attachControl=[
                             (self.ui_rbf_driver_field, "left", 5, drv_label),
                             (self.ui_rbf_driver_field, "right", 5, drv_btn),
                             (drv_attr_label, "top", 12, drv_label),
                             (self.ui_rbf_driver_attr_list, "top", 8, self.ui_rbf_driver_field),
                             (self.ui_rbf_driver_attr_list, "left", 5, drv_attr_label),
                             (self.ui_rbf_driven_field, "left", 5, dvn_label),
                             (self.ui_rbf_driven_field, "right", 5, dvn_btn),
                             (dvn_attr_label, "top", 12, dvn_label),
                             (self.ui_rbf_driven_attr_list, "top", 8, self.ui_rbf_driven_field),
                             (self.ui_rbf_driven_attr_list, "left", 5, dvn_attr_label),
                         ],
                         attachPosition=[
                             (drv_btn, "right", 10, 50),
                             (self.ui_rbf_driver_attr_list, "right", 10, 50),
                             (dvn_label, "left", 10, 50),
                             (dvn_attr_label, "left", 10, 50),
                             (div, "left", 0, 50),
                         ])
        cmds.setParent("..")

        cmds.separator(style="in", height=6)

        # Pose data scroll
        cmds.text(label=T("poses"), align="left", font="boldLabelFont")
        self.ui_pose_scroll = cmds.scrollLayout(childResizable=True, height=150)
        cmds.setParent("..")

        cmds.separator(style="in", height=6)

        # Buttons
        cmds.rowLayout(numberOfColumns=4, adjustableColumn=1,
                       columnWidth4=(100, 100, 100, 100),
                       columnAttach4=("both", "both", "both", "both"))
        cmds.button(label=T("add_pose"), command=self._add_pose)
        cmds.button(label=T("apply"), command=lambda *a: self._apply_rbf(False))
        cmds.button(label=T("connect"), command=lambda *a: self._apply_rbf(True))
        cmds.button(label=T("reload"), command=self._load_rbf_editor_data)
        cmds.setParent("..")

        cmds.setParent("..")  # columnLayout
        cmds.setParent("..")  # RBF Editor frameLayout

        cmds.setParent("..")  # scroll

        # ===================== Form attachments =====================
        cmds.formLayout(main_form, edit=True,
                         attachForm=[
                             (node_row, "top", 5), (node_row, "left", 5), (node_row, "right", 5),
                             (sep_top, "left", 5), (sep_top, "right", 5),
                             (scroll, "left", 0), (scroll, "right", 0), (scroll, "bottom", 0),
                         ],
                         attachControl=[
                             (sep_top, "top", 2, node_row),
                             (scroll, "top", 2, sep_top),
                         ])

        # initialize
        self._refresh_node_menu()
        self._on_type_changed()

        cmds.showWindow(WINDOW_NAME)


# -----------------------------------------------------------------
# module-level entry point
# -----------------------------------------------------------------

_instance = None


def show():
    """Show the unified RBF Tools UI."""
    global _instance
    _instance = RBFtoolsUI()
    _instance.show()
    return _instance
