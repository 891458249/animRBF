# ---------------------------------------------------------------------
# RBFtoolsMenu.py
#
# Creates the "RBF Tools" top-level menu in Maya's main menu bar.
# Only two items: Open UI  +  Settings (language switch).
# ---------------------------------------------------------------------

import maya.cmds as cmds
import maya.mel as mel

MENU_NAME = "RBFtoolsMainMenu"
LANG_OPT_VAR = "RBFtools_language"


def _current_lang():
    if cmds.optionVar(exists=LANG_OPT_VAR):
        return cmds.optionVar(query=LANG_OPT_VAR)
    return "en"


_MENU_STRINGS = {
    "en": {
        "open":      "Open RBF Tools",
        "settings":  "Settings",
        "language":  "Language",
        "english":   "English",
        "chinese":   "Chinese",
    },
    "zh": {
        "open":      u"\u6253\u5f00 RBF Tools",
        "settings":  u"\u8bbe\u7f6e",
        "language":  u"\u8bed\u8a00",
        "english":   u"\u82f1\u6587",
        "chinese":   u"\u4e2d\u6587",
    },
}


def _tr(key):
    lang = _current_lang()
    table = _MENU_STRINGS.get(lang, _MENU_STRINGS["en"])
    return table.get(key, _MENU_STRINGS["en"].get(key, key))


def _ensure_plugin():
    if not cmds.pluginInfo("RBFtools", query=True, loaded=True):
        cmds.loadPlugin("RBFtools")


def _open_ui(*_args):
    _ensure_plugin()
    import RBFtools
    RBFtools.show()


def _switch_language(lang, *_args):
    cmds.optionVar(sv=(LANG_OPT_VAR, lang))
    # Rebuild this menu with new language
    create()
    # If the UI window is open, rebuild it too
    from RBFtools.ui.compat import QtWidgets
    from RBFtools.constants import WINDOW_OBJECT
    existing = QtWidgets.QApplication.instance().findChild(
        QtWidgets.QMainWindow, WINDOW_OBJECT)
    if existing is not None:
        _open_ui()


def create():
    """Create (or recreate) the RBF Tools top-level menu."""
    remove()

    main_window = mel.eval("$tmpVar = $gMainWindow")
    cmds.menu(MENU_NAME, label="RBF Tools", parent=main_window, tearOff=False)

    # 1 -- Open UI
    cmds.menuItem(label=_tr("open"), image="RBFtools.png", command=_open_ui)

    cmds.menuItem(divider=True)

    # 2 -- Settings
    cmds.menuItem(label=_tr("settings"), subMenu=True)

    # Language sub-menu
    cmds.menuItem(label=_tr("language"), subMenu=True)
    cmds.radioMenuItemCollection()
    cmds.menuItem(label=_tr("english"),
                   radioButton=(_current_lang() == "en"),
                   command=lambda *a: _switch_language("en"))
    cmds.menuItem(label=_tr("chinese"),
                   radioButton=(_current_lang() == "zh"),
                   command=lambda *a: _switch_language("zh"))
    cmds.setParent("..", menu=True)  # close Language

    cmds.setParent("..", menu=True)  # close Settings


def remove():
    if cmds.menu(MENU_NAME, exists=True):
        cmds.deleteUI(MENU_NAME)
