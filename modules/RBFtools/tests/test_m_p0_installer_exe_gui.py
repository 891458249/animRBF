# -*- coding: utf-8 -*-
"""M_P0_INSTALLER_EXE_GUI (2026-05-01) — standalone tkinter GUI
installer + PyInstaller-bundled .exe.

User mandate 2026-05-01: ship a single standalone .exe that any
user can double-click on a fresh Windows machine to install
RBFtools onto user-selected Maya versions, with no Python
installation required on the target.

Design (recap of installer_gui.py docstring):

  * Tkinter GUI on top of install.py's existing public API
    (install / uninstall). install.py is reused — no duplicate
    file copy / remove logic.
  * Auto-detect Maya versions on the host (filesystem +
    registry fallback covering Maya 2018..2030).
  * Auto-discover Maya versions the repo carries pre-built
    .mll binaries for (mirrors install._discover_maya_versions
    so cross-installer parity holds).
  * Intersection -> checkbox list -> user picks any subset.
  * Run dispatches to install.install(versions=...) or
    install.uninstall(...) with stdout redirected into the
    GUI's ScrolledText panel for live progress.
  * --headless argv switch skips the GUI and installs onto
    every detected version (CI / silent deploy).

install.py extension (M_P0_INSTALLER_EXE_GUI):
  * install() signature gains optional ``versions`` kwarg. Default
    None preserves the legacy behaviour (use the full
    MAYA_VERSIONS list resolved at module import). Subset support
    routes the .mod file to a TD-selected slice.
  * _build_mod_content gains the same ``versions`` kwarg and
    passes through.

PyInstaller wiring:
  * build_installer.spec specifies onefile + windowed +
    bundles modules/ + resources/ trees so the .exe ships the
    full content including .mll binaries for every supported
    Maya version.
  * build_installer.bat one-shot wrapper (pip install
    pyinstaller, run the .spec).

PERMANENT GUARD T_M_P0_INSTALLER_EXE_GUI.
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
_INSTALL_PY = os.path.join(_REPO_ROOT, "install.py")
_GUI_PY = os.path.join(_REPO_ROOT, "installer_gui.py")
_SPEC = os.path.join(_REPO_ROOT, "build_installer.spec")
_BAT = os.path.join(_REPO_ROOT, "build_installer.bat")


def _read(p):
    with open(p, "r", encoding="utf-8") as fh:
        return fh.read()


def _import_module(name, path):
    """Import a module from a specific path (works for repo-root
    files that are not on the default sys.path)."""
    if _REPO_ROOT not in sys.path:
        sys.path.insert(0, _REPO_ROOT)
    if name in sys.modules:
        del sys.modules[name]
    return __import__(name)


# ----------------------------------------------------------------------
# PERMANENT GUARD T_M_P0_INSTALLER_EXE_GUI
# ----------------------------------------------------------------------


class T_M_P0_INSTALLER_EXE_GUI(unittest.TestCase):
    """PERMANENT GUARD — DO NOT REMOVE.

    Locks the 5-file deliverable: installer_gui.py + install.py
    versions kwarg + build_installer.spec/.bat + .gitignore for
    PyInstaller artifacts."""

    @classmethod
    def setUpClass(cls):
        cls._install_src = _read(_INSTALL_PY)
        cls._gui_src = _read(_GUI_PY)
        cls._spec_src = _read(_SPEC)
        cls._bat_src = _read(_BAT)

    # ----- install.py extension -------------------------------------

    def test_PERMANENT_a_install_signature_has_versions_kwarg(self):
        # AST guard (lesson #6): install() FunctionDef MUST
        # declare a ``versions`` parameter with default None.
        tree = ast.parse(self._install_src)
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            if node.name != "install":
                continue
            kwargs = [a.arg for a in node.args.args]
            self.assertIn(
                "versions", kwargs,
                "install() MUST declare a 'versions' kwarg so the "
                "GUI can pass a user-selected Maya-version subset.")
            # Find the default for 'versions' — must be Constant
            # value None.
            defaults = node.args.defaults
            offset = len(kwargs) - len(defaults)
            ver_idx = kwargs.index("versions")
            default = defaults[ver_idx - offset]
            self.assertTrue(
                isinstance(default, ast.Constant)
                and default.value is None,
                "install() versions kwarg MUST default to None "
                "for legacy back-compat (None means use the full "
                "MAYA_VERSIONS).")
            return
        self.fail("install() FunctionDef not found in install.py.")

    def test_PERMANENT_b_build_mod_content_versions_kwarg(self):
        tree = ast.parse(self._install_src)
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            if node.name != "_build_mod_content":
                continue
            kwargs = [a.arg for a in node.args.args]
            self.assertIn(
                "versions", kwargs,
                "_build_mod_content MUST accept a 'versions' "
                "kwarg so install() can pass through a subset.")
            return
        self.fail(
            "_build_mod_content FunctionDef not found.")

    def test_PERMANENT_c_uninstall_function_present(self):
        # Pre-existing uninstall() at install.py:330 — locked
        # so a future refactor cannot drop the GUI's dispatch
        # target.
        self.assertIn(
            "def uninstall(", self._install_src,
            "install.py MUST keep its uninstall() public "
            "function — the GUI's Uninstall radio dispatches "
            "to it.")

    # ----- installer_gui.py surface ---------------------------------

    def test_PERMANENT_d_gui_imports_tkinter(self):
        # The GUI MUST import tkinter (stdlib only — zero
        # external runtime dependency beyond the PyInstaller
        # bundle).
        self.assertIn(
            "import tkinter", self._gui_src,
            "installer_gui MUST import tkinter — the stdlib-only "
            "GUI is the design constraint that keeps the .exe "
            "self-contained.")

    def test_PERMANENT_e_gui_required_functions_present(self):
        for sym in (
                "def detect_installed_maya():",
                "def discover_available_versions():",
                "def compute_installable_versions():",
                "class InstallerWindow",
                "def main(",
                "def _headless_install_all():"):
            self.assertIn(
                sym, self._gui_src,
                "installer_gui missing required symbol "
                "{!r}.".format(sym))

    def test_PERMANENT_f_gui_dispatches_to_install_py(self):
        # The GUI's _run_action MUST call install.install() and
        # install.uninstall() — never reimplement the file-copy
        # logic. AST walk to confirm.
        tree = ast.parse(self._gui_src)
        seen_install_call = False
        seen_uninstall_call = False
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not isinstance(func, ast.Attribute):
                continue
            if func.attr == "install" and \
                    isinstance(func.value, ast.Name) and \
                    func.value.id == "install":
                seen_install_call = True
            if func.attr == "uninstall" and \
                    isinstance(func.value, ast.Name) and \
                    func.value.id == "install":
                seen_uninstall_call = True
        self.assertTrue(
            seen_install_call,
            "installer_gui MUST call install.install() — not "
            "reimplement copy logic. Drift between the two "
            "installers is the lesson #4 + #8 recurrence shape.")
        self.assertTrue(
            seen_uninstall_call,
            "installer_gui MUST call install.uninstall() for "
            "the Uninstall radio path.")

    def test_PERMANENT_g_gui_passes_versions_to_install(self):
        # Source-scan: the install() call inside _run_action MUST
        # pass versions=... kwarg.
        body = self._gui_src.split("def _run_action(")[1].split(
            "\n    def ")[0]
        self.assertIn(
            "versions=versions", body,
            "_run_action MUST forward the GUI-selected versions "
            "list into install.install() — the whole point of "
            "the subset-selection UX.")

    # ----- PyInstaller build wiring ---------------------------------

    def test_PERMANENT_h_spec_bundles_modules_tree(self):
        self.assertIn(
            "('modules', 'modules')", self._spec_src,
            "build_installer.spec MUST bundle the modules/ tree "
            "so the .exe ships RBFtools.mll for every supported "
            "Maya version. Without this datas entry the runtime "
            "_MEIPASS unpacks an empty modules/ and install fails.")
        self.assertIn(
            "('resources', 'resources')", self._spec_src,
            "build_installer.spec MUST bundle resources/ for "
            "module_template.mod + future asset additions.")

    def test_PERMANENT_i_spec_onefile_windowed(self):
        self.assertIn(
            "console=False", self._spec_src,
            "build_installer.spec MUST use windowed mode "
            "(console=False) so the user does not see a black "
            "cmd window behind the GUI.")
        self.assertIn(
            "name='RBFtoolsInstaller'", self._spec_src,
            "Output exe MUST be named RBFtoolsInstaller.")

    def test_PERMANENT_j_bat_invokes_pyinstaller(self):
        self.assertIn(
            "pyinstaller", self._bat_src.lower(),
            "build_installer.bat MUST invoke pyinstaller.")
        self.assertIn(
            "build_installer.spec", self._bat_src,
            "build_installer.bat MUST point pyinstaller at the "
            ".spec file (so onefile + windowed + datas all fire).")

    # ----- .gitignore ----------------------------------------------

    def test_PERMANENT_k_gitignore_excludes_pyinstaller_outputs(self):
        gitignore = _read(os.path.join(_REPO_ROOT, ".gitignore"))
        for pat in ("dist/", "build/"):
            self.assertIn(
                pat, gitignore,
                ".gitignore MUST exclude {!r} so PyInstaller "
                "build artifacts never enter git.".format(pat))


# ----------------------------------------------------------------------
# Mock E2E — install/uninstall API + GUI dispatch + headless mode.
# ----------------------------------------------------------------------


class TestM_P0_INSTALLER_EXE_GUI_RuntimeBehavior(unittest.TestCase):

    # ----- install() versions kwarg --------------------------------

    def test_install_default_uses_full_maya_versions(self):
        install = _import_module("install", _INSTALL_PY)
        # Default versions=None branch in _build_mod_content.
        text = install._build_mod_content("/fake")
        self.assertIn("MAYAVERSION:2022", text)
        self.assertIn("MAYAVERSION:2025", text)

    def test_install_subset_routes_only_selected_version(self):
        install = _import_module("install", _INSTALL_PY)
        text = install._build_mod_content(
            "/fake", versions=["2025"])
        self.assertNotIn("MAYAVERSION:2022", text)
        self.assertIn("MAYAVERSION:2025", text)

    def test_install_subset_can_be_empty_list(self):
        # Edge: empty selection is legal; the .mod ends up with
        # no routing blocks. The GUI guards against this in
        # _on_run_clicked, but the API itself MUST not raise.
        install = _import_module("install", _INSTALL_PY)
        text = install._build_mod_content("/fake", versions=[])
        # Empty list -> no MAYAVERSION lines.
        self.assertNotIn("MAYAVERSION:", text)

    def test_install_subset_unknown_version_routes_only_present(self):
        # Pass a version NOT in the repo. _build_mod_content's
        # ``if not os.path.isdir(plug_dir): continue`` filter
        # drops it silently — the .mod still has the valid
        # entries.
        install = _import_module("install", _INSTALL_PY)
        text = install._build_mod_content(
            "/fake", versions=["2025", "2099"])
        self.assertIn("MAYAVERSION:2025", text)
        self.assertNotIn("MAYAVERSION:2099", text)

    # ----- detect / discover ---------------------------------------

    def test_detect_returns_dict_of_versions(self):
        gui = _import_module("installer_gui", _GUI_PY)
        result = gui.detect_installed_maya()
        self.assertIsInstance(result, dict)
        # Every value MUST be a path string; every key a 4-digit
        # version string.
        for ver, path in result.items():
            self.assertEqual(len(ver), 4)
            self.assertTrue(ver.isdigit())
            self.assertIsInstance(path, str)

    def test_detect_handles_missing_program_files(self):
        # Simulate a machine with no Autodesk/ folder. Detection
        # MUST return an empty dict, NOT raise.
        gui = _import_module("installer_gui", _GUI_PY)
        with mock.patch("os.path.isdir", return_value=False):
            with mock.patch("os.listdir",
                            side_effect=FileNotFoundError):
                result = gui.detect_installed_maya()
        self.assertEqual(result, {})

    def test_discover_matches_install_module_versions(self):
        gui = _import_module("installer_gui", _GUI_PY)
        install = _import_module("install", _INSTALL_PY)
        self.assertEqual(
            gui.discover_available_versions(),
            install._discover_maya_versions(),
            "Cross-installer parity: GUI's discover MUST match "
            "install._discover_maya_versions exactly. Drift "
            "would mean the GUI exposes a version checkbox that "
            "the .mod routing then drops.")

    def test_compute_installable_intersection_on_live_repo(self):
        gui = _import_module("installer_gui", _GUI_PY)
        result = gui.compute_installable_versions()
        # Result is a list of (version, path) tuples.
        self.assertIsInstance(result, list)
        for entry in result:
            self.assertEqual(len(entry), 2)
            ver, path = entry
            self.assertEqual(len(ver), 4)
            self.assertTrue(ver.isdigit())

    def test_compute_installable_filters_to_intersection(self):
        # Mock detected = {2022, 2024, 2025} but repo = {2022,
        # 2025}. compute MUST return only 2022 + 2025.
        gui = _import_module("installer_gui", _GUI_PY)
        with mock.patch.object(
                gui, "detect_installed_maya",
                return_value={
                    "2022": "C:/Maya2022",
                    "2024": "C:/Maya2024",
                    "2025": "C:/Maya2025"}):
            with mock.patch.object(
                    gui, "discover_available_versions",
                    return_value=["2022", "2025"]):
                result = gui.compute_installable_versions()
        versions = [v for v, _ in result]
        self.assertEqual(sorted(versions), ["2022", "2025"])

    # ----- headless dispatch ---------------------------------------

    def test_headless_calls_install_with_detected_versions(self):
        gui = _import_module("installer_gui", _GUI_PY)
        with mock.patch.object(
                gui, "compute_installable_versions",
                return_value=[
                    ("2022", "C:/Maya2022"),
                    ("2025", "C:/Maya2025")]):
            import install as install_mod
            with mock.patch.object(
                    install_mod, "install",
                    return_value=True) as install_call:
                ok = gui._headless_install_all()
        self.assertTrue(ok)
        install_call.assert_called_once()
        # Versions kwarg MUST equal the detected list.
        kwargs = install_call.call_args.kwargs
        self.assertEqual(
            kwargs.get("versions"), ["2022", "2025"])

    def test_headless_warns_when_no_maya_detected(self):
        gui = _import_module("installer_gui", _GUI_PY)
        with mock.patch.object(
                gui, "compute_installable_versions",
                return_value=[]):
            import install as install_mod
            with mock.patch.object(
                    install_mod, "install",
                    return_value=True) as install_call:
                ok = gui._headless_install_all()
        self.assertFalse(ok)
        install_call.assert_not_called()

    # ----- main entry ----------------------------------------------

    def test_main_headless_argv_skips_gui(self):
        gui = _import_module("installer_gui", _GUI_PY)
        with mock.patch.object(
                gui, "_headless_install_all",
                return_value=True) as headless:
            with mock.patch.object(
                    gui, "InstallerWindow") as window_cls:
                with self.assertRaises(SystemExit):
                    gui.main(["--headless"])
        headless.assert_called_once()
        window_cls.assert_not_called()


if __name__ == "__main__":
    unittest.main()
