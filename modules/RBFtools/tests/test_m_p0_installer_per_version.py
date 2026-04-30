# -*- coding: utf-8 -*-
"""M_P0_INSTALLER_PER_VERSION (2026-05-01) — installer GUI shows
per-Maya-version install state and supports installing/
uninstalling individual versions.

Before this change:
  * GUI showed only the detected Maya versions, not whether each
    one currently had RBFtools wired up.
  * install(versions=[X]) overwrote the .mod file, kicking out
    any previously-routed versions.
  * uninstall() always removed the .mod AND the content directory
    in one shot — there was no "uninstall just 2022" path.

After this change:
  * installed_versions() parses MAYAVERSION:<ver> tokens out of
    the .mod file -> the source of truth for "is RBFtools wired
    up for this Maya?".
  * install(versions=[X]) MERGES X with whatever is already
    routed, so single-version installs no longer clobber others.
  * uninstall(versions=[X, Y]) rewrites the .mod with only the
    NOT-removed versions; if the remaining set becomes empty,
    falls through to full-uninstall (drop .mod + content).
  * GUI: per-row ``[Installed]`` / ``[Not installed]`` label
    refreshed at startup, after each action, and on language
    switch. uninstall mode now also requires at least one row
    checked.

PERMANENT GUARD T_M_P0_INSTALLER_PER_VERSION.
"""

from __future__ import absolute_import

import ast
import os
import sys
import tempfile
import unittest
from unittest import mock


_REPO_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
_GUI_PY = os.path.join(_REPO_ROOT, "installer_gui.py")


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
# Source / signature guards.
# ----------------------------------------------------------------------


class T_M_P0_INSTALLER_PER_VERSION(unittest.TestCase):
    """PERMANENT GUARD — DO NOT REMOVE."""

    @classmethod
    def setUpClass(cls):
        cls._gui_src = _read(_GUI_PY)

    # ---------- public API surface ---------------------------------

    def test_PERMANENT_a_installed_versions_function_present(self):
        self.assertIn(
            "def installed_versions(", self._gui_src,
            "installer_gui MUST expose installed_versions() so "
            "the GUI can render per-row install state.")

    def test_PERMANENT_b_uninstall_signature_has_versions_kwarg(self):
        # AST guard (lesson #6 reapplied): uninstall() declares a
        # ``versions`` kwarg with default None. Keeps the legacy
        # call shape (uninstall(install_dir=..., verbose=...))
        # working while opening the per-version subset path.
        tree = ast.parse(self._gui_src)
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            if node.name != "uninstall":
                continue
            kwargs = [a.arg for a in node.args.args]
            self.assertIn(
                "versions", kwargs,
                "installer_gui.uninstall() MUST declare a "
                "``versions`` kwarg.")
            # Default is the last positional default, lined up
            # with the last len(defaults) args.
            defaults = node.args.defaults
            self.assertTrue(defaults)
            ver_idx = kwargs.index("versions")
            default_idx = ver_idx - (len(kwargs) - len(defaults))
            self.assertGreaterEqual(default_idx, 0)
            default_node = defaults[default_idx]
            self.assertIsInstance(
                default_node, ast.Constant)
            self.assertIsNone(
                default_node.value,
                "uninstall() versions kwarg MUST default to None.")
            return
        self.fail("uninstall() FunctionDef not found.")

    # ---------- GUI per-row status wiring --------------------------

    def test_PERMANENT_c_gui_has_status_label_dict(self):
        self.assertIn(
            "_version_status_labels", self._gui_src,
            "InstallerWindow MUST track per-version status "
            "labels in _version_status_labels so the GUI can "
            "refresh them after each action.")

    def test_PERMANENT_d_gui_has_refresh_install_status(self):
        self.assertIn(
            "def _refresh_install_status(", self._gui_src,
            "InstallerWindow MUST expose _refresh_install_status "
            "to recompute per-row install state.")

    def test_PERMANENT_e_run_action_refreshes_status_via_after(self):
        # Backend mutates from a worker thread; tkinter is not
        # thread-safe. The refresh MUST be funneled through
        # root.after(0, ...) so it runs on the GUI thread.
        self.assertIn(
            "self._root.after(0, self._refresh_install_status)",
            self._gui_src,
            "_run_action MUST schedule _refresh_install_status "
            "via root.after(0, ...) — direct calls from the "
            "worker thread would race tkinter's event loop.")

    def test_PERMANENT_f_uninstall_passes_versions_subset(self):
        # _run_action's uninstall branch MUST forward ``versions``
        # through; otherwise the new per-version semantics are
        # silently bypassed.
        tree = ast.parse(self._gui_src)
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            if node.name != "_run_action":
                continue
            body_src = ast.unparse(node) if hasattr(
                ast, "unparse") else self._gui_src
            self.assertIn(
                "uninstall(", body_src)
            self.assertIn(
                "versions=versions", body_src,
                "_run_action's uninstall branch MUST pass "
                "versions=versions so the per-version subset "
                "reaches the backend.")
            return
        self.fail("_run_action FunctionDef not found.")

    # ---------- i18n parity ----------------------------------------

    def test_PERMANENT_g_i18n_status_keys_present_en_zh(self):
        gui = _import_gui()
        for lang in ("en", "zh"):
            for key in ("status_installed",
                        "status_not_installed",
                        "err_no_version_uninstall"):
                self.assertIn(
                    key, gui._TR[lang],
                    "i18n locale %r MUST define %r." % (lang, key))


# ----------------------------------------------------------------------
# Runtime behaviour — installed_versions() + install/uninstall merge.
# ----------------------------------------------------------------------


class TestPerVersionRuntime(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="rbf_pv_")
        self._gui = _import_gui()

    def tearDown(self):
        import shutil
        try:
            shutil.rmtree(self._tmp, ignore_errors=True)
        except Exception:
            pass

    # ---------- installed_versions parsing -------------------------

    def test_installed_versions_empty_when_no_mod_file(self):
        result = self._gui.installed_versions(mod_dir=self._tmp)
        self.assertEqual(result, set())

    def test_installed_versions_parses_mod_blocks(self):
        mod_path = os.path.join(self._tmp, "RBFtools.mod")
        content = self._gui._build_mod_content(
            "/fake/install", versions=["2022", "2025"])
        with open(mod_path, "w") as fh:
            fh.write(content)
        result = self._gui.installed_versions(mod_dir=self._tmp)
        self.assertEqual(result, {"2022", "2025"})

    def test_installed_versions_subset_round_trip(self):
        mod_path = os.path.join(self._tmp, "RBFtools.mod")
        content = self._gui._build_mod_content(
            "/fake/install", versions=["2025"])
        with open(mod_path, "w") as fh:
            fh.write(content)
        self.assertEqual(
            self._gui.installed_versions(mod_dir=self._tmp),
            {"2025"})

    # ---------- install merges with existing routing ---------------

    def test_install_merges_with_existing_routing(self):
        # Pre-seed the .mod with 2022 routed; install with
        # versions=["2025"]; the resulting .mod must contain BOTH.
        # We bypass _copy_tree by patching it (the source folder
        # exists in the live repo, but we don't want to actually
        # write into the user's modules dir).
        install_dir = os.path.join(self._tmp, "RBFtools")
        mod_path = os.path.join(self._tmp, "RBFtools.mod")
        # Seed.
        with open(mod_path, "w") as fh:
            fh.write(self._gui._build_mod_content(
                install_dir, versions=["2022"]))
        # Install 2025 — must merge to 2022+2025.
        with mock.patch.object(self._gui, "_copy_tree"):
            with mock.patch.object(self._gui, "_ensure_dir"):
                ok = self._gui.install(
                    install_dir=install_dir,
                    mod_dir=self._tmp,
                    versions=["2025"],
                    verbose=False)
        self.assertTrue(ok)
        self.assertEqual(
            self._gui.installed_versions(mod_dir=self._tmp),
            {"2022", "2025"})

    # ---------- uninstall subset rewrites .mod ---------------------

    def test_uninstall_subset_keeps_remaining_versions(self):
        install_dir = os.path.join(self._tmp, "RBFtools")
        mod_path = os.path.join(self._tmp, "RBFtools.mod")
        os.makedirs(install_dir)
        with open(os.path.join(install_dir, "marker.txt"), "w") as fh:
            fh.write("keep me")
        with open(mod_path, "w") as fh:
            fh.write(self._gui._build_mod_content(
                install_dir, versions=["2022", "2025"]))
        ok = self._gui.uninstall(
            install_dir=install_dir,
            mod_dir=self._tmp,
            versions=["2022"],
            verbose=False)
        self.assertTrue(ok)
        # .mod still exists, only 2025 left.
        self.assertTrue(os.path.isfile(mod_path))
        self.assertEqual(
            self._gui.installed_versions(mod_dir=self._tmp),
            {"2025"})
        # Content directory preserved.
        self.assertTrue(os.path.isfile(
            os.path.join(install_dir, "marker.txt")))

    def test_uninstall_subset_clears_when_all_removed(self):
        install_dir = os.path.join(self._tmp, "RBFtools")
        mod_path = os.path.join(self._tmp, "RBFtools.mod")
        os.makedirs(install_dir)
        with open(os.path.join(install_dir, "marker.txt"), "w") as fh:
            fh.write("nuke me")
        with open(mod_path, "w") as fh:
            fh.write(self._gui._build_mod_content(
                install_dir, versions=["2022", "2025"]))
        # Removing both routed versions falls through to full
        # uninstall (drops .mod + content).
        ok = self._gui.uninstall(
            install_dir=install_dir,
            mod_dir=self._tmp,
            versions=["2022", "2025"],
            verbose=False)
        self.assertTrue(ok)
        self.assertFalse(os.path.isfile(mod_path))
        self.assertFalse(os.path.isdir(install_dir))

    def test_uninstall_no_versions_kwarg_is_full_uninstall(self):
        # Backwards-compat: callers that didn't pass versions=
        # still trigger the legacy "remove everything" branch.
        install_dir = os.path.join(self._tmp, "RBFtools")
        mod_path = os.path.join(self._tmp, "RBFtools.mod")
        os.makedirs(install_dir)
        with open(mod_path, "w") as fh:
            fh.write(self._gui._build_mod_content(
                install_dir, versions=["2022", "2025"]))
        ok = self._gui.uninstall(
            install_dir=install_dir,
            mod_dir=self._tmp,
            verbose=False)
        self.assertTrue(ok)
        self.assertFalse(os.path.isfile(mod_path))
        self.assertFalse(os.path.isdir(install_dir))


if __name__ == "__main__":
    unittest.main()
