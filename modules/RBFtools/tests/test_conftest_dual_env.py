"""T_CONFTEST_DUAL_ENV — the 17th PERMANENT GUARD.

Guards the dual-environment contract that lets tests run under
both pure Python (development-time fast feedback, ~0.4 s) and
mayapy 2025 (integration verification, ~5 s; the M1.5 spillover
bucket).

Five invariants plus a branch-behaviour assertion, all PERMANENT:

  1. _REAL_MAYA detection symbol exists in conftest.
  2. Two-condition detection (basename + import probe) is
     present — single-condition detection has known false
     positives (addendum §M1.5-conftest F1).
  3. The 12 mock-target sys.modules names are listed in
     conftest source — guards against silent removal that would
     leave the pure-Python branch naked.
  4. Pure-Python collected test count is at or above the
     baseline recorded in addendum §M1.5-conftest — guards
     against a refactor that accidentally skipif-skips tests
     in the pure-Python branch (e.g. by upgrading skipif
     decorators from class-level to module-level).
  5. mayapy branch must NOT call maya.standalone.initialize() —
     that is M1.5 spillover, NOT this sub-task's responsibility.

Reinforcement context (addendum §M1.5-conftest reinforcements):
  Reinforcement 1 — invariant 4 above: the test-count baseline
  catches "silent skip drift" that would otherwise slip past
  refactors.
  Reinforcement 2 — addendum §M1.5-conftest carries an
  observed-baseline log dated 2026-04-26 with the mayapy fail
  list classification.
  Reinforcement 3 — Maya 2022 caveat is documented at the top
  of addendum §M1.5-conftest + tests/README.md.
"""

from __future__ import absolute_import

import conftest  # noqa: F401

import inspect
import os
import re
import unittest


def _strip_docstrings_and_comments(src):
    """Same pattern as M3.4 / M3.5 / M3.6 source-scan tests:
    docstrings + line comments are documentation channels and must
    be allowed to mention forbidden symbols (e.g. "MUST NOT call
    maya.standalone") without tripping the executable-body
    guard."""
    src = re.sub(r'"""[\s\S]*?"""', "", src)
    out = []
    for line in src.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue
        out.append(line)
    return "\n".join(out)


# =====================================================================
# Baselines — see addendum §M1.5-conftest invariants table
# =====================================================================
#
# The 12 mock-target sys.modules names that MUST stay listed in
# conftest source even when the mayapy branch skips installing
# them. Source-text presence is what matters here — the actual
# behaviour-side enforcement happens via the if/else branch.
_REQUIRED_MOCK_TARGET_NAMES = (
    "'maya'",
    "'maya.cmds'",
    "'maya.api'",
    "'maya.api.OpenMaya'",
    "'maya.OpenMayaUI'",
    "'maya.utils'",
    "'PySide6'",
    "'PySide6.QtCore'",
    "'PySide6.QtWidgets'",
    "'PySide6.QtGui'",
    "'shiboken6'",
    "'shiboken2'",
)

# Pure-Python baseline test count — recorded after the M2.5
# commit (`c866604`) at 434 + this file's own subtests. The
# guard checks ">=" rather than equality so future test
# additions naturally pass; the failure mode it catches is a
# refactor that REDUCES the count via accidental over-broad
# skipif. Update this baseline when intentionally raising it
# (and document the change in addendum §M1.5-conftest).
_PURE_PYTHON_BASELINE = 434


# =====================================================================
# T_CONFTEST_DUAL_ENV — PERMANENT GUARD #17
# =====================================================================


class T_ConftestDualEnv(unittest.TestCase):
    """PERMANENT GUARD #17 — DO NOT REMOVE.

    Dual-environment contract:

      pure-Python: full mock framework, 434+ tests pass.
      mayapy 2025: zero module-level mocks, real Maya / PySide
                   resolves naturally; class-level skipif on
                   tests that depend on mock-specific behaviour.

    See addendum §M1.5-conftest for the full F1-F4 verify-before-
    design log + invariants table + Maya 2022 deferral caveat."""

    @staticmethod
    def _conftest_source():
        return inspect.getsource(conftest)

    # ---- Invariant 1: _REAL_MAYA symbol present ----
    def test_PERMANENT_real_maya_symbol_present(self):
        src = self._conftest_source()
        self.assertIn("_REAL_MAYA", src,
            "_REAL_MAYA detection symbol missing from conftest.py")
        # Module-level access works.
        self.assertTrue(hasattr(conftest, "_REAL_MAYA"),
            "conftest._REAL_MAYA module attribute missing")
        self.assertIsInstance(conftest._REAL_MAYA, bool,
            "_REAL_MAYA must be a bool")

    # ---- Invariant 2: two-condition detection ----
    def test_PERMANENT_two_condition_detection(self):
        src = self._conftest_source()
        # basename probe (cross-platform — no ".exe" assumption)
        self.assertIn("os.path.basename(sys.executable)", src,
            "conftest must probe sys.executable basename")
        self.assertIn('startswith("mayapy")', src,
            "conftest must check 'mayapy' basename prefix")
        # import probe (sanity check guarding against false negatives)
        self.assertIn("import maya.cmds", src,
            "conftest must probe `import maya.cmds` for sanity")
        self.assertIn("ImportError", src,
            "conftest must guard the import probe with ImportError")

    # ---- Invariant 3: 12 mock-target names listed in source ----
    def test_PERMANENT_mock_targets_listed(self):
        """Source-text presence of the 12 mock-target names. If
        any name is silently removed from conftest, the
        pure-Python branch would lose coverage of that module
        without anyone noticing. Both _install_maya_mocks and
        _install_pyside_mocks must keep the full list visible."""
        src = self._conftest_source()
        for tgt in _REQUIRED_MOCK_TARGET_NAMES:
            self.assertIn(tgt, src,
                "conftest mock target {} removed — would silently "
                "break pure-Python tests for that module".format(tgt))

    # ---- Invariant 4: pure-Python collected test count >= baseline
    #      (Reinforcement 1 — silent-skip drift detector)
    def test_PERMANENT_pure_python_test_count_baseline(self):
        """Run only when in the pure-Python branch — under mayapy
        the count may legitimately differ (some classes skipif'd).

        Catches the refactor failure mode where over-broad
        skipif accidentally hides tests in pure-Python too."""
        if conftest._REAL_MAYA:
            self.skipTest("pure-Python baseline check; mayapy "
                          "count may differ legitimately")
        # Discover from the tests directory.
        here = os.path.dirname(os.path.abspath(__file__))
        loader = unittest.TestLoader()
        suite = loader.discover(start_dir=here, top_level_dir=here)
        n = suite.countTestCases()
        self.assertGreaterEqual(n, _PURE_PYTHON_BASELINE,
            "Pure-Python collected test count {} fell below "
            "baseline {} — likely an over-broad skipif "
            "decorator. Update _PURE_PYTHON_BASELINE in this file "
            "ONLY when intentionally raising it (and document in "
            "addendum §M1.5-conftest).".format(
                n, _PURE_PYTHON_BASELINE))

    # ---- Invariant 5: mayapy branch must NOT call maya.standalone
    def test_PERMANENT_no_maya_standalone(self):
        """conftest must NOT call ``maya.standalone.initialize()``
        in executable code — that is M1.5 spillover, not this
        sub-task's responsibility. Source-scan after stripping
        docstrings + comments so legitimate documentation can
        name the forbidden symbol."""
        src = _strip_docstrings_and_comments(self._conftest_source())
        self.assertNotIn("maya.standalone", src,
            "conftest executable body contains 'maya.standalone' "
            "— this is M1.5 scope, NOT the conftest dual-env "
            "sub-task. Move standalone init into a per-test "
            "fixture instead.")

    # ---- Branch behaviour: env-specific assertions ----
    def test_PERMANENT_branch_wiring_consistent(self):
        """Behavioural assertion: when _REAL_MAYA is True, the
        sys.modules entry for maya.cmds must NOT be a MagicMock
        (i.e. mocks were correctly skipped). When False, it MUST
        be a MagicMock (or shim derivative)."""
        import sys
        from unittest import mock as _mock
        cmds_mod = sys.modules.get("maya.cmds")
        if conftest._REAL_MAYA:
            self.assertIsNotNone(cmds_mod,
                "_REAL_MAYA is True but maya.cmds is not in sys.modules")
            self.assertNotIsInstance(cmds_mod, _mock.MagicMock,
                "_REAL_MAYA is True but maya.cmds is a MagicMock — "
                "mock leaked through the branch")
        else:
            self.assertIsInstance(cmds_mod, _mock.MagicMock,
                "_REAL_MAYA is False but maya.cmds is not a "
                "MagicMock — mock framework not installed")


if __name__ == "__main__":
    unittest.main()
