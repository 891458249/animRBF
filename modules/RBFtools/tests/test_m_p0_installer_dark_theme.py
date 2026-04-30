# -*- coding: utf-8 -*-
"""M_P0_INSTALLER_DARK_THEME (2026-05-01) — installer GUI dark
theme + RBF-node window icon.

User mandate 2026-05-01: the standalone RBFtoolsInstaller.exe
must (a) render in a dark colour scheme matching modern Maya
UX expectations, and (b) display the RBF-node icon
(modules/RBFtools/icons/RBFtools.png) in its title bar +
taskbar + file-explorer thumbnail.

Design (recap of installer_gui.py changes)
==========================================

  * ``_DARK`` palette dict at module scope — 12 named colour
    slots (bg / fg / fg_muted / fg_warn / field_bg / field_fg /
    border / btn_bg / btn_bg_hover / btn_bg_pressed / log_bg /
    log_fg / select_bg / indicator). Self-contained — no
    external theme library.
  * ``InstallerWindow._apply_dark_theme()`` runs at
    construction time. Switches to ttk's ``clam`` base theme
    (the most customizable of the stdlib trio) and applies
    style.configure / style.map calls for every widget class
    the GUI uses (TFrame / TLabel / TCheckbutton / TRadiobutton
    / TButton / TEntry / TSeparator) plus three custom Label
    subclasses (Header / Hint / Warn).
  * ``InstallerWindow._apply_window_icon()`` loads
    modules/RBFtools/icons/RBFtools.png as a tk.PhotoImage and
    calls ``root.iconphoto(True, ...)``. The image reference is
    held on ``self._icon_image`` to defeat the Tk garbage
    collector — a dropped reference would silently revert to
    the default feather icon. Path resolution searches the
    repo layout AND the PyInstaller _MEIPASS unpack directory
    (via ``_repo_root``) so the same code path works in dev
    runs and the bundled .exe.
  * ``build_installer.spec`` ``EXE(..., icon=...png)`` — the
    same RBFtools.png path is passed to PyInstaller so the
    Windows file-explorer thumbnail + taskbar match the
    title-bar icon.
  * The ScrolledText log panel uses raw Tk colour kwargs
    (bg / fg / insertbackground / selectbackground) since
    ScrolledText is not a ttk widget and is not driven by the
    Style system.

PERMANENT GUARD T_M_P0_INSTALLER_DARK_THEME.
"""

from __future__ import absolute_import

import ast
import os
import sys
import unittest
from unittest import mock


_REPO_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
_GUI_PY = os.path.join(_REPO_ROOT, "installer_gui.py")
_SPEC = os.path.join(_REPO_ROOT, "build_installer.spec")
_ICON_PATH = os.path.join(
    _REPO_ROOT, "modules", "RBFtools", "icons", "RBFtools.png")


def _read(p):
    with open(p, "r", encoding="utf-8") as fh:
        return fh.read()


def _import_gui():
    if _REPO_ROOT not in sys.path:
        sys.path.insert(0, _REPO_ROOT)
    if "installer_gui" in sys.modules:
        del sys.modules["installer_gui"]
    import installer_gui   # noqa: F401
    return sys.modules["installer_gui"]


# ----------------------------------------------------------------------
# PERMANENT GUARD T_M_P0_INSTALLER_DARK_THEME
# ----------------------------------------------------------------------


class T_M_P0_INSTALLER_DARK_THEME(unittest.TestCase):
    """PERMANENT GUARD — DO NOT REMOVE."""

    @classmethod
    def setUpClass(cls):
        cls._gui_src = _read(_GUI_PY)
        cls._spec_src = _read(_SPEC)

    # ----- Dark palette --------------------------------------------

    def test_PERMANENT_a_dark_palette_present(self):
        # The _DARK dict MUST be at module scope so test code +
        # the runtime can both reach it.
        gui = _import_gui()
        self.assertTrue(
            hasattr(gui, "_DARK"),
            "installer_gui MUST expose _DARK palette at module "
            "scope — single source of truth for theme colors.")

    def test_PERMANENT_b_palette_has_required_slots(self):
        gui = _import_gui()
        required = (
            "bg", "fg", "fg_muted", "fg_warn",
            "field_bg", "field_fg", "border",
            "btn_bg", "btn_bg_hover", "btn_bg_pressed",
            "log_bg", "log_fg", "select_bg", "indicator",
        )
        for key in required:
            self.assertIn(
                key, gui._DARK,
                "_DARK palette missing required slot {!r} — "
                "GUI widget styling depends on every name in "
                "this set.".format(key))
            value = gui._DARK[key]
            self.assertTrue(
                isinstance(value, str)
                and value.startswith("#")
                and len(value) in (4, 7),
                "_DARK[{!r}] = {!r} is not a hex colour "
                "string.".format(key, value))

    def test_PERMANENT_c_palette_is_actually_dark(self):
        # Defence-in-depth: the bg slot's red component MUST be
        # below 0x80 so a future "fix" that accidentally swaps
        # in a light palette fails CI.
        gui = _import_gui()
        bg_hex = gui._DARK["bg"].lstrip("#")
        if len(bg_hex) == 3:
            bg_hex = "".join(c * 2 for c in bg_hex)
        r = int(bg_hex[0:2], 16)
        g = int(bg_hex[2:4], 16)
        b = int(bg_hex[4:6], 16)
        # All channels under mid-grey -> definitively dark.
        self.assertLess(
            (r + g + b) / 3, 128,
            "_DARK['bg'] = {} averages above mid-grey — that's "
            "not a dark theme.".format(gui._DARK["bg"]))

    # ----- _apply_dark_theme + _apply_window_icon presence --------

    def test_PERMANENT_d_apply_dark_theme_method_present(self):
        self.assertIn(
            "def _apply_dark_theme(self):", self._gui_src,
            "InstallerWindow MUST expose _apply_dark_theme — "
            "the entry-point invoked from __init__.")

    def test_PERMANENT_e_apply_window_icon_method_present(self):
        self.assertIn(
            "def _apply_window_icon(self):", self._gui_src)
        self.assertIn(
            "_icon_path()", self._gui_src,
            "_apply_window_icon MUST source the path via "
            "_icon_path() — the helper that searches both the "
            "repo layout and the PyInstaller _MEIPASS unpack "
            "directory.")
        self.assertIn(
            "root.iconphoto(True", self._gui_src,
            "_apply_window_icon MUST call root.iconphoto(True, "
            "...) with default=True so child Toplevels inherit "
            "the icon too.")

    def test_PERMANENT_f_init_invokes_theme_and_icon(self):
        # AST guard: InstallerWindow.__init__ MUST contain Calls
        # to both _apply_dark_theme and _apply_window_icon
        # before _build, so the theme is in place before any
        # widget is constructed.
        tree = ast.parse(self._gui_src)
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            if node.name != "InstallerWindow":
                continue
            for func in node.body:
                if not (isinstance(func, ast.FunctionDef)
                        and func.name == "__init__"):
                    continue
                seen = []
                for sub in ast.walk(func):
                    if not isinstance(sub, ast.Call):
                        continue
                    f = sub.func
                    if isinstance(f, ast.Attribute) \
                            and isinstance(f.value, ast.Name) \
                            and f.value.id == "self":
                        seen.append(f.attr)
                # Theme + icon called BEFORE _build.
                if "_build" in seen:
                    build_idx = seen.index("_build")
                    self.assertIn(
                        "_apply_dark_theme",
                        seen[:build_idx],
                        "_apply_dark_theme MUST run before "
                        "_build so widgets pick up theme "
                        "defaults at construction.")
                    self.assertIn(
                        "_apply_window_icon",
                        seen[:build_idx],
                        "_apply_window_icon MUST run before "
                        "_build for symmetry.")
                return
        self.fail("InstallerWindow.__init__ not found.")

    # ----- ttk Style configuration ---------------------------------

    def test_PERMANENT_g_uses_clam_base_theme(self):
        body = self._gui_src.split(
            "def _apply_dark_theme(self):"
        )[1].split("\n    def ")[0]
        self.assertIn(
            'theme_use("clam")', body,
            "_apply_dark_theme MUST switch ttk to the clam base "
            "theme — it is the most customizable of the three "
            "stdlib options and accepts every override the "
            "palette demands.")

    def test_PERMANENT_h_styles_required_widget_classes(self):
        # Every ttk widget class the GUI uses MUST be themed.
        # Missing one would leave a single light-coloured widget
        # in an otherwise dark window.
        body = self._gui_src.split(
            "def _apply_dark_theme(self):"
        )[1].split("\n    def ")[0]
        for cls in (
                "TFrame", "TLabel",
                "TCheckbutton", "TRadiobutton",
                "TButton", "TEntry", "TSeparator"):
            self.assertIn(
                '"{}"'.format(cls), body,
                "_apply_dark_theme MUST style {!r} — missing "
                "would leave that widget class light-themed.".format(
                    cls))

    def test_PERMANENT_i_log_widget_uses_dark_colors(self):
        # ScrolledText is raw Tk; the colours flow through
        # bg= / fg= kwargs at construction time, NOT through
        # ttk.Style. Test scans the construction site for the
        # _DARK reference.
        body = self._gui_src.split(
            "def _build(self):")[1].split("\n    def ")[0]
        self.assertIn(
            '_DARK["log_bg"]', body,
            "ScrolledText log panel MUST consume _DARK['log_bg'] "
            "for its bg colour. Without this the log area would "
            "render in default white inside an otherwise dark "
            "window.")
        self.assertIn(
            '_DARK["log_fg"]', body)

    # ----- PyInstaller .spec ---------------------------------------

    def test_PERMANENT_j_spec_sets_exe_icon(self):
        self.assertIn(
            "icon=", self._spec_src,
            "build_installer.spec MUST set icon= on the EXE "
            "construction so the Windows file-explorer "
            "thumbnail + taskbar entry match the title-bar.")
        self.assertIn(
            "RBFtools.png", self._spec_src,
            "Spec icon path MUST point at RBFtools.png — the "
            "same asset loaded at runtime by "
            "_apply_window_icon.")

    # ----- Asset existence -----------------------------------------

    def test_PERMANENT_k_icon_asset_exists(self):
        self.assertTrue(
            os.path.isfile(_ICON_PATH),
            "RBFtools.png icon asset MUST exist at "
            "modules/RBFtools/icons/. Both the runtime tk."
            "PhotoImage load AND the PyInstaller spec icon "
            "kwarg point at this single file.")


# ----------------------------------------------------------------------
# Mock E2E — runtime: helpers are reachable, palette is sound.
# ----------------------------------------------------------------------


class TestM_P0_INSTALLER_DARK_THEME_RuntimeBehavior(
        unittest.TestCase):

    def test_icon_path_helper_returns_existing_file(self):
        gui = _import_gui()
        path = gui._icon_path()
        self.assertIsNotNone(
            path,
            "_icon_path() MUST return a valid path on the "
            "current repo layout.")
        self.assertTrue(os.path.isfile(path))
        self.assertTrue(path.lower().endswith(".png"))

    def test_icon_path_helper_returns_none_when_missing(self):
        # Defensive: simulate the file missing — the helper
        # should return None, NOT raise. Without this fail-soft
        # branch a corrupt _MEIPASS extraction would crash the
        # GUI on startup.
        gui = _import_gui()
        with mock.patch("os.path.exists", return_value=False):
            self.assertIsNone(gui._icon_path())

    def test_dark_palette_field_bg_distinct_from_log_bg(self):
        # Defence-in-depth: log panel bg should be DARKER than
        # field bg (gives the log a code-area feel).
        gui = _import_gui()

        def _avg(hex_col):
            h = hex_col.lstrip("#")
            if len(h) == 3:
                h = "".join(c * 2 for c in h)
            return (int(h[0:2], 16)
                    + int(h[2:4], 16)
                    + int(h[4:6], 16)) / 3

        self.assertLess(
            _avg(gui._DARK["log_bg"]),
            _avg(gui._DARK["field_bg"]),
            "_DARK['log_bg'] should be darker than ['field_bg'] "
            "so the log panel reads as a 'code area' inside "
            "the inputs. Reverse the slots if the design "
            "intent changed.")

    def test_dark_palette_indicator_is_accent_color(self):
        # Indicator (selected check / radio) should NOT be a
        # neutral grey — it's the visible accent.
        gui = _import_gui()
        ind = gui._DARK["indicator"].lstrip("#")
        if len(ind) == 3:
            ind = "".join(c * 2 for c in ind)
        r = int(ind[0:2], 16)
        g = int(ind[2:4], 16)
        b = int(ind[4:6], 16)
        # At least one channel meaningfully different from the
        # other two.
        spread = max(abs(r - g), abs(g - b), abs(r - b))
        self.assertGreater(
            spread, 30,
            "_DARK['indicator'] = #{} reads as near-grey "
            "(channel spread {}). Accent colours should be "
            "visibly chromatic.".format(ind, spread))


if __name__ == "__main__":
    unittest.main()
