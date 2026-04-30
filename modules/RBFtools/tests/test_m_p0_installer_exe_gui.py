# -*- coding: utf-8 -*-
"""M_P0_INSTALLER_EXE_GUI (2026-05-01) — standalone tkinter GUI
installer + PyInstaller-bundled .exe (post-inline revision).

Original commit (e9f6d52) shipped a separate install.py backend
that installer_gui.py imported at runtime. M_P0_INSTALLER_INLINE
(2026-05-01) folded install.py into installer_gui.py so the .exe
is now built from a single self-contained module — no separate
import path, no second public entry point. dragDropInstaller.py
was deleted in the same refactor.

This test file is the surviving structural-API guard. The two
deleted companion files (install.py + dragDropInstaller.py) had
their own dedicated test modules (test_m_p0_install_dual_version
+ test_m_p0_dragdrop_permerr_retry) — those are gone alongside
their targets.

PERMANENT GUARD T_M_P0_INSTALLER_EXE_GUI (post-inline):
  * Source-scan: installer_gui defines install + uninstall +
    _build_mod_content + _discover_maya_versions + the
    detection helpers.
  * AST: install() declares versions kwarg with default None.
  * Runtime: dynamic version discovery returns the live
    plug-ins/win64 subset; _build_mod_content emits subset
    routing blocks; main(--headless) dispatches without GUI.
  * .spec / .bat: PyInstaller wiring still bundles modules/ +
    resources/, windowed mode, exe name unchanged.
  * .gitignore: dist/ + build/ exclude PyInstaller artifacts.
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
_BAT = os.path.join(_REPO_ROOT, "build_installer.bat")
_GITIGNORE = os.path.join(_REPO_ROOT, ".gitignore")


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
# PERMANENT GUARD T_M_P0_INSTALLER_EXE_GUI (post-inline)
# ----------------------------------------------------------------------


class T_M_P0_INSTALLER_EXE_GUI(unittest.TestCase):
    """PERMANENT GUARD — DO NOT REMOVE.

    Locks the structural surface of installer_gui.py + the
    PyInstaller wiring + the gitignore covering build artifacts.
    install.py + dragDropInstaller.py are gone; their PERMANENT
    suites (test_m_p0_install_dual_version +
    test_m_p0_dragdrop_permerr_retry) were removed alongside."""

    @classmethod
    def setUpClass(cls):
        cls._gui_src = _read(_GUI_PY)
        cls._spec_src = _read(_SPEC)
        cls._bat_src = _read(_BAT)

    # ----- installer_gui surface -----------------------------------

    def test_PERMANENT_a_install_signature_has_versions_kwarg(self):
        # AST guard (lesson #6 reapplied): install() declares
        # ``versions`` kwarg with default None.
        tree = ast.parse(self._gui_src)
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            if node.name != "install":
                continue
            kwargs = [a.arg for a in node.args.args]
            self.assertIn(
                "versions", kwargs,
                "installer_gui.install() MUST declare a "
                "'versions' kwarg.")
            defaults = node.args.defaults
            offset = len(kwargs) - len(defaults)
            ver_idx = kwargs.index("versions")
            default = defaults[ver_idx - offset]
            self.assertTrue(
                isinstance(default, ast.Constant)
                and default.value is None,
                "install() versions kwarg MUST default to None.")
            return
        self.fail("install() FunctionDef not found.")

    def test_PERMANENT_b_build_mod_content_versions_kwarg(self):
        tree = ast.parse(self._gui_src)
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            if node.name != "_build_mod_content":
                continue
            kwargs = [a.arg for a in node.args.args]
            self.assertIn("versions", kwargs)
            return
        self.fail(
            "_build_mod_content FunctionDef not found.")

    def test_PERMANENT_c_uninstall_function_present(self):
        self.assertIn(
            "def uninstall(", self._gui_src,
            "installer_gui MUST keep its uninstall() public "
            "function — the GUI's Uninstall radio dispatches "
            "to it.")

    def test_PERMANENT_d_gui_imports_tkinter(self):
        self.assertIn(
            "import tkinter", self._gui_src,
            "installer_gui MUST import tkinter.")

    def test_PERMANENT_e_gui_required_functions_present(self):
        for sym in (
                "def detect_installed_maya():",
                "def discover_available_versions():",
                "def compute_installable_versions():",
                "class InstallerWindow",
                "def main(",
                "def _headless_install_all(",
                "def install(",
                "def uninstall(",
                "def _discover_maya_versions(",
                "def _build_mod_content(",
                "def _default_modules_dir(",
                "def _copy_tree(",
                "def _remove_tree("):
            self.assertIn(
                sym, self._gui_src,
                "installer_gui missing required symbol "
                "{!r}.".format(sym))

    def test_PERMANENT_f_legacy_install_module_gone(self):
        # The original install.py + dragDropInstaller.py are
        # deleted post-inline. Their absence from the repo root
        # is part of the contract — re-introducing either would
        # split the install entry-point surface again.
        for legacy in ("install.py", "dragDropInstaller.py"):
            path = os.path.join(_REPO_ROOT, legacy)
            self.assertFalse(
                os.path.exists(path),
                "Legacy installer file {!r} MUST stay deleted "
                "— installer_gui.py is now the single entry "
                "point. Re-introducing would re-fork the "
                "install code path that M_P0_INSTALL_DUAL_VERSION "
                "+ M_P0_DRAGDROP_PERMERR_RETRY just unified.".format(
                    legacy))

    def test_PERMANENT_g_gui_uses_inline_install_uninstall(self):
        # Defence-in-depth: _run_action MUST call the local
        # install / uninstall (not import install). The
        # post-inline call shape is bare ``install(...)`` /
        # ``uninstall(...)`` since the helpers live at module
        # scope.
        body = self._gui_src.split(
            "def _run_action(self, mode, versions, install_dir):"
        )[1].split("\n    def ")[0]
        self.assertNotIn(
            "import install", body,
            "_run_action MUST NOT import a separate install "
            "module — the helpers are inlined.")
        self.assertIn(
            "install(", body)
        self.assertIn(
            "uninstall(", body)

    def test_PERMANENT_h_spec_bundles_modules_tree(self):
        self.assertIn(
            "('modules', 'modules')", self._spec_src,
            "build_installer.spec MUST bundle modules/ tree.")
        self.assertIn(
            "('resources', 'resources')", self._spec_src)

    def test_PERMANENT_i_spec_onefile_windowed(self):
        self.assertIn("console=False", self._spec_src)
        self.assertIn("name='RBFtoolsInstaller'", self._spec_src)

    def test_PERMANENT_j_spec_does_not_hidden_import_install(self):
        # install.py is gone — the spec MUST NOT list it as a
        # hidden import (PyInstaller would error on the missing
        # module name).
        self.assertNotIn(
            "'install',", self._spec_src,
            "build_installer.spec MUST NOT list 'install' in "
            "hiddenimports — that module no longer exists.")

    def test_PERMANENT_k_bat_invokes_pyinstaller(self):
        self.assertIn(
            "pyinstaller", self._bat_src.lower())
        self.assertIn(
            "build_installer.spec", self._bat_src)

    def test_PERMANENT_l_gitignore_excludes_pyinstaller_outputs(self):
        gitignore = _read(_GITIGNORE)
        for pat in ("dist/", "build/"):
            self.assertIn(pat, gitignore)


# ----------------------------------------------------------------------
# Mock E2E — runtime (post-inline).
# ----------------------------------------------------------------------


class TestM_P0_INSTALLER_EXE_GUI_RuntimeBehavior(unittest.TestCase):

    def test_install_default_uses_full_maya_versions(self):
        gui = _import_gui()
        text = gui._build_mod_content("/fake")
        self.assertIn("MAYAVERSION:2022", text)
        self.assertIn("MAYAVERSION:2025", text)

    def test_install_subset_routes_only_selected_version(self):
        gui = _import_gui()
        text = gui._build_mod_content(
            "/fake", versions=["2025"])
        self.assertNotIn("MAYAVERSION:2022", text)
        self.assertIn("MAYAVERSION:2025", text)

    def test_install_subset_can_be_empty_list(self):
        gui = _import_gui()
        text = gui._build_mod_content("/fake", versions=[])
        self.assertNotIn("MAYAVERSION:", text)

    def test_install_subset_unknown_version_routes_only_present(self):
        gui = _import_gui()
        text = gui._build_mod_content(
            "/fake", versions=["2025", "2099"])
        self.assertIn("MAYAVERSION:2025", text)
        self.assertNotIn("MAYAVERSION:2099", text)

    def test_detect_returns_dict_of_versions(self):
        gui = _import_gui()
        result = gui.detect_installed_maya()
        self.assertIsInstance(result, dict)
        for ver, path in result.items():
            self.assertEqual(len(ver), 4)
            self.assertTrue(ver.isdigit())
            self.assertIsInstance(path, str)

    def test_detect_handles_missing_program_files(self):
        gui = _import_gui()
        with mock.patch("os.path.isdir", return_value=False):
            with mock.patch("os.listdir",
                            side_effect=FileNotFoundError):
                result = gui.detect_installed_maya()
        self.assertEqual(result, {})

    def test_discover_matches_inline_helper(self):
        gui = _import_gui()
        self.assertEqual(
            gui.discover_available_versions(),
            gui._discover_maya_versions(),
            "discover_available_versions MUST stay a thin "
            "wrapper over _discover_maya_versions — drift would "
            "mean a GUI selection silently no-ops.")

    def test_compute_installable_intersection_on_live_repo(self):
        gui = _import_gui()
        result = gui.compute_installable_versions()
        self.assertIsInstance(result, list)
        for entry in result:
            self.assertEqual(len(entry), 2)
            ver, path = entry
            self.assertEqual(len(ver), 4)
            self.assertTrue(ver.isdigit())

    def test_compute_installable_filters_to_intersection(self):
        gui = _import_gui()
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

    def test_headless_calls_install_with_detected_versions(self):
        gui = _import_gui()
        with mock.patch.object(
                gui, "compute_installable_versions",
                return_value=[
                    ("2022", "C:/Maya2022"),
                    ("2025", "C:/Maya2025")]):
            with mock.patch.object(
                    gui, "install",
                    return_value=True) as install_call:
                ok = gui._headless_install_all()
        self.assertTrue(ok)
        install_call.assert_called_once()
        kwargs = install_call.call_args.kwargs
        self.assertEqual(
            kwargs.get("versions"), ["2022", "2025"])

    def test_headless_warns_when_no_maya_detected(self):
        gui = _import_gui()
        with mock.patch.object(
                gui, "compute_installable_versions",
                return_value=[]):
            with mock.patch.object(
                    gui, "install",
                    return_value=True) as install_call:
                ok = gui._headless_install_all()
        self.assertFalse(ok)
        install_call.assert_not_called()

    def test_main_headless_argv_skips_gui(self):
        gui = _import_gui()
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
