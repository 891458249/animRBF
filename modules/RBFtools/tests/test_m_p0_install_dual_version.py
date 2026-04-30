# -*- coding: utf-8 -*-
"""M_P0_INSTALL_DUAL_VERSION (2026-04-30) — install.py hardcoded
single Maya version.

User report 2026-04-30: install.py-based installs only routed
the .mod file to Maya 2022, leaving Maya 2025 launches without
the RBFtools plug-in path. The dragDropInstaller.py route already
worked because that script dynamically scans
``modules/RBFtools/plug-ins/<platform>/`` for available version
subdirs (lines 56-65) — install.py used a hardcoded
``MAYA_VERSIONS = ["2022"]`` constant that silently dropped the
2025 routing line from ``_build_mod_content``.

Symptoms in the wild:

  * After install.py install, RBFtools.mod contained ONLY the
    ``+ MAYAVERSION:2022 PLATFORM:win64 ...`` block. Maya 2025
    launches did not see the plug-in path; users hit a
    ``PermissionError on win64/2025/RBFtools.mll`` when manually
    poking around the install dir trying to figure out why
    Maya 2025 could not find the plug-in.
  * The two installer scripts disagreed on version discovery
    strategy — install.py was static, dragDropInstaller.py was
    dynamic. Adding 2025 binaries to the repo fixed the dragdrop
    path but not the install.py path.

Path A fix: install.py mirrors dragDropInstaller's design with
a new ``_discover_maya_versions()`` function that scans the same
plug-ins/<platform>/ tree. Filtering keeps only 4-digit numeric
subdir names that actually carry a plugin binary
(.mll / .so / .bundle), so an empty version directory created
but never built is skipped instead of producing a broken .mod
route. Defensive fallback to ``["2022", "2025"]`` when the
directory scan raises so the installer can still produce a
usable .mod for the historically-common 2-version case.

Future Maya 2026 / 2027 additions are picked up automatically
with no install.py edit required.

PERMANENT GUARD T_M_P0_INSTALL_DUAL_VERSION.
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
_INSTALL_PY = os.path.join(_REPO_ROOT, "install.py")
_DRAGDROP_PY = os.path.join(_REPO_ROOT, "dragDropInstaller.py")


def _read(p):
    with open(p, "r", encoding="utf-8") as fh:
        return fh.read()


def _import_install():
    """Import install.py with the repo root on sys.path."""
    if _REPO_ROOT not in sys.path:
        sys.path.insert(0, _REPO_ROOT)
    if "install" in sys.modules:
        # Force reimport so module-level MAYA_VERSIONS resolves
        # against the live filesystem each test run.
        del sys.modules["install"]
    import install   # noqa: F401
    return sys.modules["install"]


# ----------------------------------------------------------------------
# PERMANENT GUARD T_M_P0_INSTALL_DUAL_VERSION
# ----------------------------------------------------------------------


class T_M_P0_INSTALL_DUAL_VERSION(unittest.TestCase):
    """PERMANENT GUARD — DO NOT REMOVE.

    Locks the install.py dynamic-version-discovery contract +
    parity with dragDropInstaller's strategy."""

    @classmethod
    def setUpClass(cls):
        cls._install_src = _read(_INSTALL_PY)
        cls._dragdrop_src = _read(_DRAGDROP_PY)

    def test_PERMANENT_a_no_hardcoded_versions_list(self):
        # Defence-in-depth: the legacy MAYA_VERSIONS = ["2022"]
        # constant MUST NOT reappear. Locked via AST inspection
        # so a future commit that types it back in fails CI.
        tree = ast.parse(self._install_src)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign):
                continue
            for target in node.targets:
                if not isinstance(target, ast.Name):
                    continue
                if target.id != "MAYA_VERSIONS":
                    continue
                # The RHS MUST NOT be a List literal — must be a
                # Call to _discover_maya_versions.
                if isinstance(node.value, ast.List):
                    self.fail(
                        "AST guard: install.py MAYA_VERSIONS "
                        "MUST NOT be assigned a List literal — "
                        "the dynamic-discovery fix is the bug "
                        "shape avoided. Got literal at "
                        "line {}.".format(node.lineno))
                # Any other expression is fine but assert it's
                # the canonical Call to _discover_maya_versions.
                if isinstance(node.value, ast.Call):
                    func = node.value.func
                    if isinstance(func, ast.Name):
                        self.assertEqual(
                            func.id,
                            "_discover_maya_versions",
                            "MAYA_VERSIONS RHS Call MUST be "
                            "_discover_maya_versions — got "
                            "{!r}.".format(func.id))

    def test_PERMANENT_b_discover_function_present(self):
        self.assertIn(
            "def _discover_maya_versions():",
            self._install_src,
            "install.py MUST define _discover_maya_versions() — "
            "the canonical scanner that mirrors "
            "dragDropInstaller.getMayaVersions's design.")

    def test_PERMANENT_c_discover_uses_listdir_scan(self):
        body = self._install_src.split(
            "def _discover_maya_versions():"
        )[1].split("\ndef ")[0]
        self.assertIn(
            "os.listdir(", body,
            "_discover_maya_versions MUST scan the plug-ins "
            "directory dynamically (same primitive as "
            "dragDropInstaller.getMayaVersions).")
        self.assertIn(
            'plug-ins"', body,
            "Scan MUST target the plug-ins/<platform> subtree.")

    def test_PERMANENT_d_discover_filters_4_digit_numeric(self):
        body = self._install_src.split(
            "def _discover_maya_versions():"
        )[1].split("\ndef ")[0]
        self.assertIn(
            "isdigit()", body,
            "_discover_maya_versions MUST filter to 4-digit "
            "numeric subdirs so non-version directories never "
            "leak into the .mod routing.")
        self.assertIn(
            "len(v) == 4", body,
            "Filter MUST require exactly 4-digit names.")

    def test_PERMANENT_e_discover_requires_binary_present(self):
        body = self._install_src.split(
            "def _discover_maya_versions():"
        )[1].split("\ndef ")[0]
        # The filter MUST require at least one .mll / .so /
        # .bundle inside; an empty version dir would otherwise
        # produce a broken .mod route.
        for ext in (".mll", ".so", ".bundle"):
            self.assertIn(
                ext, body,
                "_discover_maya_versions MUST gate on the "
                "presence of a {!r} plugin binary inside each "
                "version subdir.".format(ext))

    def test_PERMANENT_f_defensive_fallback_present(self):
        body = self._install_src.split(
            "def _discover_maya_versions():"
        )[1].split("\ndef ")[0]
        # Defensive fallback ["2022", "2025"] when the scan
        # fails or yields nothing — at least one return path
        # MUST hand back a usable list.
        self.assertIn(
            '["2022", "2025"]', body,
            "_discover_maya_versions MUST fall back to "
            '["2022", "2025"] when the directory scan fails '
            "or yields no valid versions — without it a "
            "permission corner case would leave the .mod "
            "file empty.")

    def test_PERMANENT_g_dragdrop_dynamic_scan_unchanged(self):
        # dragDropInstaller already uses dynamic scanning
        # (lines 56-65 getMayaVersions). The fix only touches
        # install.py; the dragdrop strategy MUST remain dynamic
        # so both installers stay in sync.
        self.assertIn(
            "def getMayaVersions():", self._dragdrop_src,
            "dragDropInstaller MUST keep getMayaVersions — "
            "this is the source-of-truth design that "
            "install.py now mirrors.")
        self.assertIn(
            "sorted(os.listdir(path))", self._dragdrop_src,
            "dragDropInstaller MUST keep its sorted listdir "
            "scan; install.py mirrors this primitive.")

    def test_PERMANENT_h_build_mod_iterates_dynamic_versions(self):
        # _build_mod_content MUST consume the dynamic
        # MAYA_VERSIONS list (no ad-hoc hardcoded ver list inside
        # the loop).
        body = self._install_src.split(
            "def _build_mod_content(content_path):"
        )[1].split("\ndef ")[0]
        self.assertIn(
            "for ver in MAYA_VERSIONS:", body,
            "_build_mod_content MUST iterate MAYA_VERSIONS — "
            "the module-level dynamic constant feeds the .mod "
            "routing loop.")


# ----------------------------------------------------------------------
# Mock E2E — runtime: dynamic discovery against live filesystem.
# ----------------------------------------------------------------------


class TestM_P0_INSTALL_DUAL_VERSION_RuntimeBehavior(unittest.TestCase):

    def test_repo_resolves_to_2022_and_2025(self):
        # The current repo has both win64/2022 and win64/2025
        # populated with .mll binaries (per fee0e80 deploy).
        # _discover_maya_versions MUST find both.
        install = _import_install()
        self.assertEqual(
            install.MAYA_VERSIONS, ["2022", "2025"],
            "MAYA_VERSIONS resolved against the live repo MUST "
            "be ['2022', '2025']; got {!r}.".format(
                install.MAYA_VERSIONS))

    def test_build_mod_content_emits_both_routing_blocks(self):
        install = _import_install()
        text = install._build_mod_content("/fake/install/path")
        # Both MAYAVERSION blocks MUST be present.
        self.assertIn("MAYAVERSION:2022", text,
            "Generated .mod MUST contain the 2022 routing "
            "block.")
        self.assertIn("MAYAVERSION:2025", text,
            "Generated .mod MUST contain the 2025 routing "
            "block — the user-reported bug was its absence.")
        # Both plug-ins paths MUST be present.
        self.assertIn("plug-ins/win64/2022", text)
        self.assertIn("plug-ins/win64/2025", text)

    def test_discover_handles_missing_directory(self):
        # Simulate plug-ins/<platform> missing entirely (the
        # defensive-fallback path). The function MUST NOT raise
        # and MUST return ["2022", "2025"].
        install = _import_install()
        with mock.patch(
                "os.listdir",
                side_effect=FileNotFoundError(
                    "fake missing plug-ins dir")):
            result = install._discover_maya_versions()
        self.assertEqual(result, ["2022", "2025"])

    def test_discover_handles_empty_directory(self):
        # If the directory exists but is empty, the fallback
        # also fires.
        install = _import_install()
        with mock.patch("os.listdir", return_value=[]):
            result = install._discover_maya_versions()
        self.assertEqual(result, ["2022", "2025"])

    def test_discover_picks_up_future_2026_directory(self):
        # Simulate a future Maya 2026 subdir alongside 2022 +
        # 2025. The dynamic scan MUST return all three without
        # any install.py edit.
        install = _import_install()
        original_listdir = os.listdir

        def _fake_listdir(path):
            # Top-level scan returns the three version dirs.
            if path.endswith("win64") or path.endswith("win64\\"):
                return ["2022", "2025", "2026"]
            # Per-version scan returns a fake .mll for each.
            return ["RBFtools.mll"]

        with mock.patch("os.listdir", side_effect=_fake_listdir):
            with mock.patch("os.path.isdir", return_value=True):
                result = install._discover_maya_versions()
        self.assertEqual(
            sorted(result), ["2022", "2025", "2026"],
            "Future 2026 subdir MUST be picked up automatically. "
            "Got {!r}.".format(result))

    def test_discover_skips_empty_version_directory(self):
        # An empty win64/2024/ (created but no .mll yet) MUST
        # NOT appear in the result — would produce a broken .mod
        # route.
        install = _import_install()

        def _fake_listdir(path):
            if path.endswith("win64") or path.endswith("win64\\"):
                return ["2022", "2024", "2025"]
            # 2024 has no .mll; others do.
            if "2024" in path:
                return ["readme.txt"]
            return ["RBFtools.mll"]

        with mock.patch("os.listdir", side_effect=_fake_listdir):
            with mock.patch("os.path.isdir", return_value=True):
                result = install._discover_maya_versions()
        self.assertNotIn(
            "2024", result,
            "Empty 2024 dir (no .mll) MUST be filtered out. "
            "Got {!r}.".format(result))
        self.assertEqual(sorted(result), ["2022", "2025"])

    def test_discover_skips_non_version_subdirs(self):
        # A "test" or "tools" sibling directory MUST NOT match
        # the 4-digit-numeric filter.
        install = _import_install()

        def _fake_listdir(path):
            if path.endswith("win64") or path.endswith("win64\\"):
                return ["2022", "2025", "tools", "old", "ABCD"]
            return ["RBFtools.mll"]

        with mock.patch("os.listdir", side_effect=_fake_listdir):
            with mock.patch("os.path.isdir", return_value=True):
                result = install._discover_maya_versions()
        self.assertEqual(sorted(result), ["2022", "2025"])

    def test_install_and_dragdrop_agree_on_versions(self):
        # Cross-installer parity: install._discover_maya_versions
        # MUST return the same set as
        # dragDropInstaller.getMayaVersions's listdir output.
        install = _import_install()
        plat = install._current_platform()
        plug_dir = os.path.join(
            install.MODULES_SRC, install.MODULE_NAME,
            "plug-ins", plat)
        # Direct listdir reproduces dragdrop's primitive
        # (modulo the 4-digit-numeric filter applied by
        # install._discover_maya_versions). The dragdrop
        # implementation does NOT filter — but the populated
        # repo state contains only valid version dirs, so the
        # results converge in practice.
        try:
            raw = sorted(os.listdir(plug_dir))
        except OSError:
            self.skipTest("plug-ins dir not present")
        # In a clean repo the raw list is exactly what
        # _discover returns (since every entry is a 4-digit
        # version with a binary).
        self.assertEqual(
            install.MAYA_VERSIONS, raw,
            "install.py and dragDropInstaller MUST agree on "
            "the set of Maya versions. install: {!r}, raw "
            "listdir: {!r}.".format(install.MAYA_VERSIONS, raw))


if __name__ == "__main__":
    unittest.main()
