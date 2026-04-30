# -*- coding: utf-8 -*-
"""M_P0_REPO_ROOT_TIDY (2026-05-01) — repo-root layout cleanup.

The repo root used to be a mixed bag: ``installer_gui.py`` (the
single user-facing entry point) sat alongside two build artefacts
(``build_installer.bat`` / ``build_installer.spec``) and a stray
``versions.md`` doc. M_P0_REPO_ROOT_TIDY moved the build scripts
into ``tools/`` and the doc into ``docs/`` so the root advertises
just the four "official" surfaces — ``.gitignore``, ``LICENSE``,
``README.md``, ``installer_gui.py``.

PERMANENT GUARD T_M_P0_REPO_ROOT_TIDY:
  * Repo root tracked-file set is the locked 4-file allow-list.
  * ``tools/build_installer.{bat,spec}`` exist; the legacy paths
    at the repo root do not.
  * ``docs/versions.md`` exists; the legacy path does not.
  * .spec uses SPEC-derived ``HERE`` (not ``os.getcwd()``) so the
    build is cwd-independent.
  * .spec datas list joins on ``HERE`` for both ``modules`` and
    ``resources`` (path-explicit, no relative-cwd reliance).
  * .bat steps up one level (``%~dp0..\\``) before invoking
    PyInstaller, and the spec it references is ``tools\\...``.
"""

from __future__ import absolute_import

import os
import subprocess
import unittest


_REPO_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
_TOOLS_BAT = os.path.join(_REPO_ROOT, "tools", "build_installer.bat")
_TOOLS_SPEC = os.path.join(_REPO_ROOT, "tools", "build_installer.spec")
_DOCS_VERSIONS = os.path.join(_REPO_ROOT, "docs", "versions.md")
_LEGACY_BAT = os.path.join(_REPO_ROOT, "build_installer.bat")
_LEGACY_SPEC = os.path.join(_REPO_ROOT, "build_installer.spec")
_LEGACY_VERSIONS = os.path.join(_REPO_ROOT, "versions.md")


def _read(p):
    with open(p, "r", encoding="utf-8") as fh:
        return fh.read()


class T_M_P0_REPO_ROOT_TIDY(unittest.TestCase):
    """PERMANENT GUARD — DO NOT REMOVE."""

    # ---------- root allow-list ------------------------------------

    def test_PERMANENT_a_repo_root_tracked_set_is_locked(self):
        # ``git ls-files -- :^*/*`` would be cleaner but isn't
        # portable across git versions. Use plain ls-files and
        # filter to entries with no path separator.
        try:
            out = subprocess.check_output(
                ["git", "ls-files"],
                cwd=_REPO_ROOT,
                stderr=subprocess.STDOUT,
            ).decode("utf-8", errors="replace")
        except (OSError, subprocess.CalledProcessError) as exc:
            self.skipTest("git ls-files unavailable: %s" % (exc,))
            return
        root_files = sorted(
            line.strip()
            for line in out.splitlines()
            if line.strip() and "/" not in line
        )
        expected = [".gitignore", "LICENSE", "README.md",
                    "installer_gui.py"]
        self.assertEqual(
            root_files, expected,
            "Repo root tracked file set drift. Expected exactly "
            "%r, got %r. Build scripts belong in tools/, docs in "
            "docs/." % (expected, root_files))

    # ---------- new locations exist --------------------------------

    def test_PERMANENT_b_tools_bat_exists(self):
        self.assertTrue(
            os.path.isfile(_TOOLS_BAT),
            "tools/build_installer.bat MUST exist post-tidy.")

    def test_PERMANENT_c_tools_spec_exists(self):
        self.assertTrue(
            os.path.isfile(_TOOLS_SPEC),
            "tools/build_installer.spec MUST exist post-tidy.")

    def test_PERMANENT_d_docs_versions_exists(self):
        self.assertTrue(
            os.path.isfile(_DOCS_VERSIONS),
            "docs/versions.md MUST exist post-tidy.")

    # ---------- legacy locations are gone --------------------------

    def test_PERMANENT_e_legacy_root_paths_removed(self):
        for legacy in (_LEGACY_BAT, _LEGACY_SPEC, _LEGACY_VERSIONS):
            self.assertFalse(
                os.path.isfile(legacy),
                "Legacy repo-root path %r MUST NOT exist; "
                "M_P0_REPO_ROOT_TIDY moved it." % (legacy,))

    # ---------- .spec is cwd-independent ---------------------------

    def test_PERMANENT_f_spec_uses_SPEC_derived_HERE(self):
        src = _read(_TOOLS_SPEC)
        self.assertNotIn(
            "os.getcwd()", src,
            "tools/build_installer.spec MUST NOT use os.getcwd() "
            "for HERE; resolve from PyInstaller-injected SPEC "
            "instead so the build is cwd-independent.")
        self.assertIn(
            "os.path.abspath(SPEC)", src,
            "tools/build_installer.spec MUST derive HERE from "
            "os.path.abspath(SPEC) so the build is cwd-"
            "independent.")

    def test_PERMANENT_g_spec_datas_use_HERE_join(self):
        src = _read(_TOOLS_SPEC)
        self.assertIn(
            "os.path.join(HERE, 'modules')", src,
            "tools/build_installer.spec datas list MUST use "
            "os.path.join(HERE, 'modules') so the bundle source "
            "is path-explicit.")
        self.assertIn(
            "os.path.join(HERE, 'resources')", src,
            "tools/build_installer.spec datas list MUST use "
            "os.path.join(HERE, 'resources') so the bundle "
            "source is path-explicit.")

    def test_PERMANENT_h_spec_analysis_uses_HERE_join_for_entry(self):
        src = _read(_TOOLS_SPEC)
        self.assertIn(
            "os.path.join(HERE, 'installer_gui.py')", src,
            "tools/build_installer.spec Analysis() MUST use "
            "os.path.join(HERE, 'installer_gui.py') as the entry "
            "script so PyInstaller resolves it independent of "
            "cwd.")

    # ---------- .bat steps up before invoking ---------------------

    def test_PERMANENT_i_bat_cd_steps_up_to_repo_root(self):
        src = _read(_TOOLS_BAT)
        # Single backslash literal in source — match exactly.
        self.assertIn(
            'cd /d "%~dp0..\\"', src,
            "tools/build_installer.bat MUST step up to the repo "
            "root via %~dp0..\\ so PyInstaller treats the repo "
            "root as cwd.")

    def test_PERMANENT_j_bat_invokes_tools_spec(self):
        src = _read(_TOOLS_BAT)
        self.assertIn(
            "tools\\build_installer.spec", src,
            "tools/build_installer.bat MUST invoke PyInstaller "
            "with tools\\build_installer.spec (not the legacy "
            "root-relative path).")


if __name__ == "__main__":
    unittest.main()
