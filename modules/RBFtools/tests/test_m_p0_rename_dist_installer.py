# -*- coding: utf-8 -*-
"""M_P0_RENAME_DIST_INSTALLER (2026-05-01) — rename PyInstaller
output directory from ``dist/`` (PyInstaller's generic default)
to ``installer/`` so the artefact directory reads as its purpose.

Achieved by passing ``--distpath installer`` to PyInstaller in
tools/build_installer.bat. The .spec file itself is unchanged in
behaviour (only docstring references updated). .gitignore now
covers both the new ``installer/`` location and the legacy
``dist/`` (defensive: a direct ``python -m PyInstaller`` call
without ``--distpath`` still falls back to ``dist/``).

PERMANENT GUARD T_M_P0_RENAME_DIST_INSTALLER:
  * tools/build_installer.bat passes --distpath installer.
  * tools/build_installer.bat does not reference ``dist`` outside
    the ``--distpath installer`` argument or comments that
    explicitly call out the rename.
  * .gitignore excludes installer/ and still excludes build/ +
    dist/ (defensive fallback).
  * tools/build_installer.spec docstring references installer/,
    not dist/, for output-path documentation.
"""

from __future__ import absolute_import

import os
import re
import unittest


_REPO_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
_BAT = os.path.join(_REPO_ROOT, "tools", "build_installer.bat")
_SPEC = os.path.join(_REPO_ROOT, "tools", "build_installer.spec")
_GITIGNORE = os.path.join(_REPO_ROOT, ".gitignore")


def _read(p):
    with open(p, "r", encoding="utf-8") as fh:
        return fh.read()


class T_M_P0_RENAME_DIST_INSTALLER(unittest.TestCase):
    """PERMANENT GUARD — DO NOT REMOVE."""

    # ---------- bat: --distpath installer is wired -----------------

    def test_PERMANENT_a_bat_passes_distpath_installer(self):
        bat = _read(_BAT)
        self.assertIn(
            "--distpath installer", bat,
            "tools/build_installer.bat MUST pass "
            "--distpath installer to PyInstaller so the artefact "
            "lands in installer/ instead of the default dist/.")

    # ---------- bat: no stray dist references ----------------------

    def test_PERMANENT_b_bat_has_no_stray_dist_references(self):
        # Strip out the one legitimate ``dist`` token: the
        # ``--distpath installer`` flag itself contains the
        # substring ``dist`` (in ``distpath``). Also tolerate
        # comment lines that explicitly call out the rename
        # ("default dist/", "default ``dist/``", "fall back to
        # dist/") for documentation. Any other dist\ or dist/
        # reference (e.g. an echoed output path) is a bug.
        bat = _read(_BAT)
        cleaned_lines = []
        for raw in bat.splitlines():
            # Drop the --distpath token from the scan window so
            # ``distpath`` doesn't trip the regex below.
            scrubbed = raw.replace("--distpath installer", "")
            # Drop any comment line that calls out the rename
            # rationale. Match REM lines that mention ``dist`` in
            # the same line as ``installer`` or ``default`` —
            # those are the rename-rationale comments.
            stripped = scrubbed.strip()
            if stripped.upper().startswith("REM ") and (
                ("default" in scrubbed.lower()
                 and "dist" in scrubbed.lower())
                or ("installer" in scrubbed.lower()
                    and "dist" in scrubbed.lower())
            ):
                continue
            cleaned_lines.append(scrubbed)
        cleaned = "\n".join(cleaned_lines)
        # Now scan for any remaining ``dist\`` or ``dist/`` token.
        leaks = re.findall(r"\bdist[\\/]", cleaned)
        self.assertEqual(
            leaks, [],
            "tools/build_installer.bat MUST NOT reference dist\\ "
            "or dist/ outside the --distpath installer argument "
            "and the rename-rationale comments. Found stray "
            "references: %r in cleaned content:\n%s"
            % (leaks, cleaned))

    # ---------- .gitignore: installer/ + dist/ + build/ ------------

    def test_PERMANENT_c_gitignore_excludes_installer_dir(self):
        gi = _read(_GITIGNORE)
        self.assertIn(
            "installer/", gi,
            ".gitignore MUST exclude installer/ so the "
            "PyInstaller-generated artefact directory does not "
            "enter history.")

    def test_PERMANENT_d_gitignore_keeps_legacy_dist_and_build(self):
        # Defensive fallback: a developer running PyInstaller
        # directly (without --distpath) still gets dist/ as the
        # output dir — must remain ignored.
        gi = _read(_GITIGNORE)
        for legacy in ("dist/", "build/"):
            self.assertIn(
                legacy, gi,
                ".gitignore MUST keep %r as a defensive fallback "
                "for direct PyInstaller invocations that skip "
                "--distpath." % (legacy,))

    # ---------- .spec docstring is consistent ---------------------

    def test_PERMANENT_e_spec_docstring_references_installer(self):
        spec = _read(_SPEC)
        self.assertIn(
            "installer/RBFtoolsInstaller.exe", spec,
            "tools/build_installer.spec docstring MUST document "
            "installer/RBFtoolsInstaller.exe as the output path "
            "(matching the --distpath override).")
        # The .spec MAY mention dist/ in the rename-rationale
        # comment block but must not present it as the canonical
        # output path. Detect by ensuring the "Produces ``...``"
        # line points at installer/.
        produces = re.search(
            r"Produces\s+``([^`]+)``", spec)
        self.assertIsNotNone(
            produces, "spec docstring MUST include a Produces "
            "``...`` line documenting the canonical output path.")
        self.assertEqual(
            produces.group(1), "installer/RBFtoolsInstaller.exe",
            "spec docstring 'Produces' line MUST point at "
            "installer/RBFtoolsInstaller.exe; got %r"
            % (produces.group(1),))


if __name__ == "__main__":
    unittest.main()
