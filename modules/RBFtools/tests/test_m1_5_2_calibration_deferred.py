"""M1.5.2 — T_M1_5_2_CALIBRATION_DEFERRED (#22 PERMANENT GUARD).

Locks the P4 disposition: _K_* benchmark calibration was probed
under verify-before-design 10th use, hit red lines 7 (R² < 0.95
on both Cholesky and GE fits) + 8 (K_GE / K_CHOL = 0.753 ∉
[1.5, 5.0]), and was DEFERRED to M5 per addendum §M1.5.2.6 —
matching original §M3.5.F2 design intent ("M5 will replace these
with real benchmarks").

Three sub-checks:

  (a) addendum file contains the section header "§M1.5.2"
  (b) addendum §M1.5.2 contains the literal "DEFERRED" marker
  (c) core_profile.py STILL contains the original conceptual
      caveat string "[CONCEPTUAL — no machine calibration]"

Sub-check (c) is the load-bearing one: it mechanically prevents
a future executor from reading the M1.5.2 commit and concluding
"calibration done — let me update the caveat string". The string
must stay until M5 (or a successor sub-task with explicit
verify-before-design re-opens calibration) actually replaces the
constants.
"""

from __future__ import absolute_import

import os
import unittest


_REPO_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
_ADDENDUM = os.path.join(
    _REPO_ROOT, "docs", "设计文档", "RBFtools_v5_addendum_20260424.md"
)
_CORE_PROFILE = os.path.join(
    _REPO_ROOT, "modules", "RBFtools", "scripts",
    "RBFtools", "core_profile.py"
)


class TestM1_5_2_CalibrationDeferred(unittest.TestCase):
    """#22 T_M1_5_2_CALIBRATION_DEFERRED."""

    def test_addendum_section_header_present(self):
        self.assertTrue(os.path.isfile(_ADDENDUM),
                        "addendum file missing: %s" % _ADDENDUM)
        with open(_ADDENDUM, "r", encoding="utf-8") as f:
            text = f.read()
        self.assertIn("§M1.5.2", text,
            "addendum missing §M1.5.2 section header — P4 "
            "disposition record absent")

    def test_addendum_marks_deferred(self):
        with open(_ADDENDUM, "r", encoding="utf-8") as f:
            text = f.read()
        self.assertIn("DEFERRED", text,
            "addendum §M1.5.2 missing DEFERRED marker — without "
            "it the recorded calibration probe could be misread "
            "as a completed calibration")

    def test_core_profile_caveat_string_preserved(self):
        """The CONCEPTUAL caveat MUST stay in core_profile.py.

        If a future executor calibrates _K_* and updates the
        caveat string, that work must come with its own
        verify-before-design pass + new permanent guard — NOT a
        silent edit that contradicts §M1.5.2.
        """
        with open(_CORE_PROFILE, "r", encoding="utf-8") as f:
            src = f.read()
        self.assertIn(
            "[CONCEPTUAL — no machine calibration]", src,
            "core_profile.py CONCEPTUAL caveat removed without "
            "going through M5 calibration sub-task — see addendum "
            "§M1.5.2.6 for the M5 restart conditions")


if __name__ == "__main__":
    unittest.main()
