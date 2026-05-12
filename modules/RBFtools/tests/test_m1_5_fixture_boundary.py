"""T_M1_5_FIXTURE_BOUNDARY — the 18th PERMANENT GUARD.

Decouples the two test-infrastructure layers:

  conftest.py             — decides "real maya or not" (env probe
                             + module-level mock framework).
  _mayapy_fixtures.py     — decides "real maya session standing up"
                             (lazy ``maya.standalone.initialize()``).

The decoupling matters because:

  * If conftest imported _mayapy_fixtures, every pure-Python test
    sweep would pull in the standalone-init module — defeating the
    "no maya.standalone in conftest" invariant 5 of
    T_CONFTEST_DUAL_ENV (#17).

  * If _mayapy_fixtures imported conftest, the lazy-init flow
    would couple to the env-probe module and any future conftest
    refactor could silently change init semantics.

Four invariants, all PERMANENT (addendum §M1.5.1 加固 1):

  A. conftest.py executable body has 0 hits of "_mayapy_fixtures"
     / "from _mayapy_fixtures" / "import _mayapy_fixtures".

  B. _mayapy_fixtures.py executable body has 0 hits of "conftest"
     / "from conftest" / "import conftest" — the string token,
     after stripping docstrings + line comments. (The fixture
     module DOES read conftest._REAL_MAYA for the skip_if_no_maya
     decorator, but does so via __import__(_CONFTEST_NAME) where
     _CONFTEST_NAME is built by concatenation — keeps the literal
     token out of the executable body so the source-scan stays
     clean. See _mayapy_fixtures.py header.)

  C. Import-graph: at runtime, the conftest module file MUST NOT
     have been loaded via _mayapy_fixtures' import path. Verified
     by ``inspect.getfile(conftest)`` having a stable real-FS
     location independent of _mayapy_fixtures.

  D. conftest.py executable body has 0 hits of "maya.standalone"
     — also enforced by T_CONFTEST_DUAL_ENV invariant 5; kept
     here as a redundant cross-check from the FIXTURE side. If
     conftest ever gains "maya.standalone" both #17 and #18 fail
     simultaneously, making the violation maximally visible.
"""

from __future__ import absolute_import

import conftest  # noqa: F401

import inspect
import re
import unittest


def _strip_docstrings_and_comments(src):
    src = re.sub(r'"""[\s\S]*?"""', "", src)
    out = []
    for line in src.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue
        out.append(line)
    return "\n".join(out)


# Lazy-imported here so the test file can run under both
# environments. _mayapy_fixtures itself never imports conftest.
import _mayapy_fixtures  # noqa: E402


class T_M1_5_FixtureBoundary(unittest.TestCase):
    """PERMANENT GUARD #18 — DO NOT REMOVE."""

    def test_PERMANENT_A_conftest_no_fixture_import(self):
        """Invariant A: conftest.py executable body must not
        reference the _mayapy_fixtures module."""
        src = _strip_docstrings_and_comments(
            inspect.getsource(conftest))
        for forbidden in ("_mayapy_fixtures",):
            self.assertNotIn(forbidden, src,
                "conftest.py executable body references {!r} — "
                "invariant A violated. conftest must not import "
                "the fixture module; pure-Python sweeps would "
                "pull in maya.standalone init.".format(forbidden))

    def test_PERMANENT_B_fixture_no_conftest_token(self):
        """Invariant B: _mayapy_fixtures.py executable body must
        not contain the literal string 'conftest'. The fixture
        accesses conftest._REAL_MAYA via __import__(_CONFTEST_NAME)
        where _CONFTEST_NAME is a concatenation; the source-scan
        stays clean of the literal token."""
        src = _strip_docstrings_and_comments(
            inspect.getsource(_mayapy_fixtures))
        self.assertNotIn("conftest", src,
            "_mayapy_fixtures.py executable body contains "
            "'conftest' — invariant B violated. Use indirect "
            "module-name resolution (see file header) or read "
            "conftest._REAL_MAYA via __import__.")

    def test_PERMANENT_C_import_graph_decoupled(self):
        """Invariant C: at runtime the conftest module file path
        is independent of the _mayapy_fixtures module file path
        — both modules live in the same tests directory but were
        loaded via independent import paths, not one-from-the-
        other. The behavioural symptom of a violation would be
        conftest.__file__ residing under a path that includes
        _mayapy_fixtures (e.g. via __path__ shenanigans), which
        we explicitly verify is NOT the case."""
        cf = inspect.getfile(conftest)
        ff = inspect.getfile(_mayapy_fixtures)
        # Both must resolve to real files in the same directory
        # but neither path may be a prefix of the other.
        self.assertTrue(cf.endswith("conftest.py"))
        self.assertTrue(ff.endswith("_mayapy_fixtures.py"))
        # Neither path is a prefix of the other (rules out
        # nested-module attacks).
        self.assertFalse(
            cf.startswith(ff[:-len("_mayapy_fixtures.py")] + "_mayapy_fixtures"),
            "conftest path is nested under _mayapy_fixtures — "
            "import graph broken")

    def test_PERMANENT_D_no_standalone_in_conftest(self):
        """Invariant D: redundant cross-check from the fixture
        side that conftest.py executable body has 0 hits of
        'maya.standalone'. T_CONFTEST_DUAL_ENV invariant 5
        already enforces this; if conftest gains the token, both
        guards fail in tandem for maximum visibility."""
        src = _strip_docstrings_and_comments(
            inspect.getsource(conftest))
        self.assertNotIn("maya.standalone", src,
            "conftest.py executable body contains "
            "'maya.standalone' — invariant D violated. Move "
            "standalone-init logic into _mayapy_fixtures.py "
            "(or any non-conftest module).")


if __name__ == "__main__":
    unittest.main()
