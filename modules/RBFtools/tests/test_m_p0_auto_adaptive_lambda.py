# -*- coding: utf-8 -*-
"""T_M_P0_AUTO_ADAPTIVE_LAMBDA — defend the auto-adaptive Tikhonov
regularization retry loop in compute().

Bug context (M_P0_AUTO_ADAPTIVE_LAMBDA, 2026-05-10):
  Multiple user-reported repros: highly redundant production rigging
  pose sets (face / muscle / shoulder) hit "RBF decomposition failed"
  even with the new 1e-3 default regularization. The fix history
  M_P0_CREATE_NODE_REGULARIZATION (1e-8 → 1e-4 → 1e-3) was a moving
  target — every value that worked for one rig failed for another.

  Maya's native poseInterpolator never returns "decomposition
  failed" for legal pose sets — it auto-tunes its internal
  regularization to whatever value lets the linear solve succeed,
  and only fails when poses are genuinely identical (in which case
  no math could distinguish them).

Fix: ``compute()`` now wraps the Cholesky / GE solver dispatch in
a retry loop that progressively bumps λ from the user's value up
to LAMBDA_CEIL = 1.0 (×10 per retry), trying both Cholesky AND GE
at each level. On success after retry > 0, a once-per-solve
warning surfaces the auto-bump value so the TD can tune λ
permanently. Failure is reserved for genuinely-singular pose sets
(two or more poses are exact duplicates in encoded driver space).

This brings driver→driven robustness up to Maya poseInterpolator
parity. The user's previously-failing rigs (20 poses × N=3 driver
× ExpMap encoding with redundant driver 1) now solve cleanly at
auto-bumped λ ≈ 1e-2 with a clear disclosure warning.

Source-level guard: ASTscan of source/RBFtools.cpp asserts the
retry loop, the LAMBDA_FLOOR / LAMBDA_CEIL / MAX_RETRIES constants,
the Cholesky-on-retry override, the trial-wMat staging in GE, and
the auto-bump warning emit exist with the right structure.
"""
from __future__ import absolute_import, division, print_function

import io
import os
import re
import unittest


_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(os.path.dirname(_HERE)))
_RBF_CPP = os.path.join(_REPO, "source", "RBFtools.cpp")


def _read(path):
    with io.open(path, "r", encoding="utf-8") as fh:
        return fh.read()


class TestAutoAdaptiveLambda(unittest.TestCase):

    def test_PERMANENT_a_lambda_constants_present(self):
        """LAMBDA_FLOOR, LAMBDA_CEIL, MAX_RETRIES literals."""
        cpp = _read(_RBF_CPP)
        self.assertRegex(cpp,
            r"const\s+double\s+LAMBDA_FLOOR\s*=\s*1\.0e-6",
            "LAMBDA_FLOOR must be 1.0e-6 (the lowest non-trivial λ "
            "the auto-adapt loop will escalate to from a zero / sub-"
            "FLOOR user value).")
        self.assertRegex(cpp,
            r"const\s+double\s+LAMBDA_CEIL\s*=\s*1\.0",
            "LAMBDA_CEIL must be 1.0 (the upper guard above which "
            "the solver gives up — a λ that high indicates a truly "
            "degenerate pose set, not a numerical conditioning miss).")
        self.assertRegex(cpp,
            r"const\s+int\s+MAX_RETRIES\s*=\s*7",
            "MAX_RETRIES must be 7 (covers 1e-6 → 1e-1 ×10 ladder, "
            "matches the LAMBDA_CEIL boundary).")

    def test_PERMANENT_b_retry_loop_structure(self):
        """The retry loop iterates up to MAX_RETRIES with break-on-solve."""
        cpp = _read(_RBF_CPP)
        self.assertRegex(cpp,
            r"for\s*\(\s*int\s+retry\s*=\s*0\s*;\s*retry\s*<=\s*MAX_RETRIES",
            "Retry loop must use 'for (int retry = 0; retry <= "
            "MAX_RETRIES; ++retry)' — the <= boundary is intentional "
            "(MAX_RETRIES retries means MAX_RETRIES+1 solve attempts, "
            "matching the FLOOR..CEIL ×10 ladder of 7 jumps).")

    def test_PERMANENT_c_cholesky_retry_override(self):
        """Cholesky must be re-attempted on retry > 0 even if "
        "lastSolveMethod cached GE."""
        cpp = _read(_RBF_CPP)
        # The intent is that a retry triggers Cholesky probe again
        # because the bumped λ may make the kernel SPD.
        self.assertRegex(cpp,
            r"tryCholesky[\s\S]{0,300}?retry\s*>\s*0\s*\|\|\s*"
            r"lastSolveMethod\s*==\s*0",
            "Cholesky-on-retry override missing: the auto-adapt loop "
            "must re-probe Cholesky after a λ bump because the "
            "larger diagonal can flip a previously-non-SPD kernel "
            "to SPD.")

    def test_PERMANENT_d_ge_uses_trial_wmat(self):
        """GE per-dim solve writes to wMatTrial, commits only on full success."""
        cpp = _read(_RBF_CPP)
        self.assertIn("BRMatrix wMatTrial;", cpp,
            "GE retry path must use a trial wMat staging copy so a "
            "partial-solve failure cannot pollute the committed wMat "
            "across retries.")
        self.assertRegex(cpp,
            r"if\s*\(\s*geOk\s*\)\s*\{[\s\S]{0,200}?wMat\s*=\s*wMatTrial",
            "Trial wMat must be committed only after full GE success "
            "(geOk == true), inside the post-loop branch.")

    def test_PERMANENT_e_lambda_delta_injection(self):
        """λ injection is incremental (delta), not full rebuild."""
        cpp = _read(_RBF_CPP)
        self.assertRegex(cpp,
            r"const\s+double\s+delta\s*=\s*nextLambda\s*-\s*appliedLambda",
            "λ injection must be incremental — the loop adds "
            "(nextLambda - appliedLambda) to the diagonal so we "
            "never rebuild linMat from scratch (would defeat the "
            "Cholesky/GE retry cost amortization).")

    def test_PERMANENT_f_giveup_above_ceil(self):
        """Loop breaks when nextLambda > LAMBDA_CEIL."""
        cpp = _read(_RBF_CPP)
        self.assertRegex(cpp,
            r"if\s*\(\s*nextLambda\s*>\s*LAMBDA_CEIL\s*\)\s*\n?\s*break",
            "Loop must break when next-step λ would exceed "
            "LAMBDA_CEIL — at that point further λ growth would "
            "destroy interpolation fidelity even if it could solve.")

    def test_PERMANENT_g_failure_diagnostic(self):
        """Genuinely-degenerate pose set triggers detailed error."""
        cpp = _read(_RBF_CPP)
        self.assertIn(
            "Auto-adaptive \xce\xbb escalated to ".decode("latin-1")
            if hasattr("", "decode") else "Auto-adaptive ",
            cpp,
            "Failure diagnostic must mention 'Auto-adaptive λ "
            "escalated' so the TD knows the auto-loop tried.")
        self.assertIn("genuinely degenerate", cpp,
            "Failure diagnostic must explain that a λ=1.0 failure "
            "means truly duplicate poses, not a numerical glitch.")
        self.assertIn(
            "RBF decomposition failed even at \xce\xbb=1.0".decode("latin-1")
            if hasattr("", "decode") else "RBF decomposition failed even at ",
            cpp,
            "Final displayError must reference the λ=1.0 ceiling so "
            "users have a definitive 'this is a data problem' signal.")

    def test_PERMANENT_h_success_warning_emit(self):
        """retry > 0 success emits a once-per-solve warning."""
        cpp = _read(_RBF_CPP)
        self.assertRegex(cpp,
            r"if\s*\(\s*retryCount\s*>\s*0\s*\)\s*\{[\s\S]{0,500}?"
            r"displayWarning",
            "retry > 0 success branch must emit displayWarning so "
            "the TD sees the auto-bump and can tune λ permanently.")
        self.assertIn("auto-adaptive regularization escalated", cpp,
            "Warning text must contain 'auto-adaptive regularization "
            "escalated' for git-blame searchability and user "
            "recognizability.")

    def test_PERMANENT_i_landing_tag_present(self):
        """Source comments reference the landing tag."""
        cpp = _read(_RBF_CPP)
        n = cpp.count("M_P0_AUTO_ADAPTIVE_LAMBDA")
        self.assertGreaterEqual(n, 2,
            "M_P0_AUTO_ADAPTIVE_LAMBDA must be referenced ≥2x in "
            "RBFtools.cpp (intro comment + warning comment) for "
            "git-blame traceability.")

    def test_PERMANENT_j_retry_tracking_var(self):
        """retryCount tracks how many retries were taken."""
        cpp = _read(_RBF_CPP)
        self.assertRegex(cpp,
            r"int\s+retryCount\s*=\s*0",
            "retryCount must be declared and initialized to 0.")
        self.assertRegex(cpp,
            r"retryCount\s*=\s*retry",
            "retryCount must be set from the loop variable on "
            "successful solve.")


if __name__ == "__main__":
    unittest.main()
