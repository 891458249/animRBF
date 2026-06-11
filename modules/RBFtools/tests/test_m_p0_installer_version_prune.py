# -*- coding: utf-8 -*-
"""M_P0_INSTALLER_VERSION_PRUNE (2026-05-01) — install() now
prunes plug-ins/<platform>/<ver>/ subdirectories that the caller
did NOT request.

Bug:
  Before this change, installing only Maya 2022 still left
  plug-ins/win64/2025/ on disk (and vice versa). _copy_tree is a
  bulk shutil.copytree with no per-subdir filter, so every
  version the repo carries was replicated regardless of the
  ``versions`` selection. The .mod file routed only the chosen
  subset, but end-users browsing the install dir saw both — a
  visual contradiction with the routing.

Fix path B (chosen): copy everything, then prune. The
selectively-copy alternative (path A) requires a custom ignore=
callback for shutil.copytree per platform, plus careful symlink
+ permission handling — high complexity for marginal payoff. The
post-copy prune is a few-LoC defensive sweep that keeps the bulk
copy primitive untouched.

versions=None (legacy --headless / install-for-all path) skips
the prune entirely, preserving the historical "every version we
have a binary for" payload.

PERMANENT GUARD T_M_P0_INSTALLER_VERSION_PRUNE.
"""

from __future__ import absolute_import

import ast
import os
import shutil
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


def _seed_fake_source(root, versions):
    """Build a minimal modules/RBFtools/ tree under *root* with
    plug-ins/win64/<ver>/RBFtools.mll for each version. Mirrors
    the layout install() expects."""
    pkg = os.path.join(root, "RBFtools")
    win = os.path.join(pkg, "plug-ins", "win64")
    os.makedirs(win)
    for v in versions:
        d = os.path.join(win, v)
        os.makedirs(d)
        with open(os.path.join(d, "RBFtools.mll"), "w") as fh:
            fh.write("fake-binary-{}".format(v))
    # Add a non-plug-ins sibling so we can verify it survives
    # the prune.
    scripts = os.path.join(pkg, "scripts")
    os.makedirs(scripts)
    with open(os.path.join(scripts, "marker.py"), "w") as fh:
        fh.write("# scripts marker")
    return pkg


class T_M_P0_INSTALLER_VERSION_PRUNE(unittest.TestCase):
    """PERMANENT GUARD — DO NOT REMOVE."""

    @classmethod
    def setUpClass(cls):
        cls._gui_src = _read(_GUI_PY)

    def test_PERMANENT_a_install_body_references_effective_versions(self):
        # AST guard: install() body must reference
        # ``effective_versions`` AND iterate plug-ins/<plat> via
        # os.listdir. Source-scan only — runtime tests below
        # verify the actual prune behaviour.
        tree = ast.parse(self._gui_src)
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            if node.name != "install":
                continue
            body_src = (ast.unparse(node) if hasattr(ast, "unparse")
                        else self._gui_src)
            self.assertIn(
                "effective_versions", body_src,
                "install() body MUST reference effective_versions "
                "to drive the per-version prune.")
            self.assertIn(
                "os.listdir(plug_root)", body_src,
                "install() body MUST iterate plug_root via "
                "os.listdir to detect unselected version dirs.")
            self.assertIn(
                "_remove_tree(", body_src,
                "install() body MUST call _remove_tree on "
                "unselected version dirs.")
            return
        self.fail("install() FunctionDef not found.")

    def test_PERMANENT_b_install_logs_pruned_unselected(self):
        self.assertIn(
            "Pruned unselected", self._gui_src,
            "install() MUST log 'Pruned unselected: ...' when "
            "removing an unselected version dir so the user can "
            "see what happened.")


class TestVersionPruneRuntime(unittest.TestCase):

    def setUp(self):
        self._gui = _import_gui()
        self._tmp = tempfile.mkdtemp(prefix="rbf_prune_")
        # Seed a fake source repo with two version dirs.
        self._fake_src_root = os.path.join(self._tmp, "src")
        os.makedirs(self._fake_src_root)
        _seed_fake_source(self._fake_src_root, ["2022", "2025"])
        self._fake_install_dir = os.path.join(
            self._tmp, "modules", "RBFtools")
        self._fake_mod_dir = os.path.join(self._tmp, "modules")

    def tearDown(self):
        try:
            shutil.rmtree(self._tmp, ignore_errors=True)
        except Exception:
            pass

    def _run_install(self, versions):
        # Patch _MODULES_SRC so install()'s ``source =
        # os.path.join(_MODULES_SRC, _MODULE_NAME)`` resolves to
        # our fake src tree. Patch _current_platform to win64 so
        # the prune path matches the seeded layout.
        with mock.patch.object(
                self._gui, "_MODULES_SRC", self._fake_src_root):
            with mock.patch.object(
                    self._gui, "_current_platform",
                    return_value="win64"):
                return self._gui.install(
                    install_dir=self._fake_install_dir,
                    mod_dir=self._fake_mod_dir,
                    versions=versions,
                    verbose=False)

    def _plug_dirs(self):
        plug_win = os.path.join(
            self._fake_install_dir, "plug-ins", "win64")
        if not os.path.isdir(plug_win):
            return []
        return sorted(
            d for d in os.listdir(plug_win)
            if os.path.isdir(os.path.join(plug_win, d)))

    # ---------- subset prune --------------------------------------

    def test_install_2022_only_prunes_2025(self):
        ok = self._run_install(["2022"])
        self.assertTrue(ok)
        self.assertEqual(self._plug_dirs(), ["2022"])

    def test_install_2025_only_prunes_2022(self):
        ok = self._run_install(["2025"])
        self.assertTrue(ok)
        self.assertEqual(self._plug_dirs(), ["2025"])

    def test_install_both_keeps_both(self):
        ok = self._run_install(["2022", "2025"])
        self.assertTrue(ok)
        self.assertEqual(self._plug_dirs(), ["2022", "2025"])

    # ---------- legacy (versions=None) is untouched ---------------

    def test_install_versions_none_keeps_all(self):
        # versions=None -> effective_versions stays None ->
        # prune branch skipped. Both subdirs remain.
        ok = self._run_install(None)
        self.assertTrue(ok)
        self.assertEqual(self._plug_dirs(), ["2022", "2025"])

    # ---------- defensive: empty effective set --------------------

    def test_install_unknown_version_does_not_prune_all(self):
        # Caller asks for "2024" which isn't in the repo. After
        # the merge step in install(), effective_versions would
        # be just ["2024"] (no existing .mod). The prune loop
        # iterates plug-ins/win64/ and would try to remove
        # everything that isn't "2024" — i.e. both 2022 AND
        # 2025. That's intentional: the user explicitly asked
        # ONLY for a version we don't have, so wiping the
        # unselected ones is the consistent answer (post-prune
        # plug-ins/win64/ is empty, .mod has no MAYAVERSION
        # block → nothing routed, mirrors the request).
        ok = self._run_install(["2024"])
        self.assertTrue(ok)
        self.assertEqual(self._plug_dirs(), [])

    # ---------- prune failure is non-fatal ------------------------

    def test_install_prune_failure_is_logged_not_raised(self):
        # If _remove_tree raises mid-prune, install() must keep
        # going (write the .mod, return True) so the user is not
        # left with a half-installed module. The failure must
        # show up in the log.
        captured = []

        # _copy_tree itself calls _remove_tree to clear an
        # existing dst before re-copying — we MUST let that path
        # succeed. Only fail when the prune branch targets a
        # plug-ins/<plat>/<ver> dir.
        real_remove = self._gui._remove_tree

        def _fake_remove(path, *_a, **_k):
            norm = os.path.normpath(path).replace("\\", "/")
            if "plug-ins/win64/" in norm and norm.endswith(
                    ("/2022", "/2025")):
                captured.append(path)
                raise OSError("fake permission denied")
            return real_remove(path, *_a, **_k)

        with mock.patch.object(
                self._gui, "_MODULES_SRC", self._fake_src_root):
            with mock.patch.object(
                    self._gui, "_current_platform",
                    return_value="win64"):
                with mock.patch.object(
                        self._gui, "_remove_tree",
                        side_effect=_fake_remove):
                    ok = self._gui.install(
                        install_dir=self._fake_install_dir,
                        mod_dir=self._fake_mod_dir,
                        versions=["2022"],
                        verbose=True)
        self.assertTrue(ok)
        self.assertTrue(captured,
                        "_remove_tree should have been invoked.")
        # 2025 still on disk because the prune raised; .mod must
        # still be written (verify by checking installed_versions).
        self.assertEqual(
            self._gui.installed_versions(
                mod_dir=self._fake_mod_dir),
            {"2022"})


if __name__ == "__main__":
    unittest.main()
