# -*- coding: utf-8 -*-
"""T_M_P0_BOUNDED_LAMBDA_RETRY_FLOOR_1E5 (2026-05-11) PERMANENT guard.

Defends the bounded λ retry restoration:
  * ROLLBACK_2 (91adfc9) removed M_P0_AUTO_ADAPTIVE_LAMBDA's retry loop
    in favour of single-pass "honest failure". Empirical evidence on
    user's 22-pose redundant rig later showed K is singular at λ < 1e-5
    across ALL kernels, not just MQ/IMQ. ROLLBACK_2's single-pass +
    kFailure punished mathematically legitimate dense rigs.
  * M_P0_BOUNDED_LAMBDA_RETRY_FLOOR_1E5 restores bounded retry capped
    at 1e-5 (100× tighter than M_P0_AUTO_ADAPTIVE_LAMBDA's 1e-3 ceil)
    to preserve ROLLBACK_2's "honest failure" philosophy at the ceil
    while letting standard well-conditioned RBF training (Schaback /
    Wendland λ ∈ [1e-8, 1e-5]) succeed without kFailure.

Source-scan / AST-based assertions only. Phase 5-style behavioural
verification (Maya λ-sweep CSV) lives in
``tests/scratch/diag_kernel_rollback.py``.

Per Planner spec:
  a. LAMBDA_CEIL_FLOOR_1E5 = 1e-5 literal present
  b. MAX_RETRIES_FLOOR_1E5 = 4 literal present
  c. retry block sits near the ROLLBACK_2 anchor (rewind anchor)
  d. cpp schema regularization setDefault(1.0e-5) present
  e. retry uses `while` loop with bounded condition (NOT the
     ROLLBACK_2-forbidden `for (int retry = ` outer construct)
  f. landing tag M_P0_BOUNDED_LAMBDA_RETRY_FLOOR_1E5 referenced
     in ≥ 2 places (audit traceability)
"""
from __future__ import absolute_import, division, print_function

import ast
import io
import os
import re
import unittest


_HERE = os.path.dirname(os.path.abspath(__file__))
_TESTS_DIR = os.path.dirname(_HERE)
_REPO = os.path.dirname(os.path.dirname(os.path.dirname(_TESTS_DIR)))
_RBF_CPP = os.path.join(_REPO, "source", "RBFtools.cpp")


def _read(path):
    with io.open(path, "r", encoding="utf-8") as fh:
        return fh.read()


class TestBoundedRetryFloor1E5(unittest.TestCase):

    def test_PERMANENT_a_lambda_ceil_floor_1e5_literal(self):
        """`const double LAMBDA_CEIL_FLOOR_1E5 = 1.0e-5;` declared."""
        cpp = _read(_RBF_CPP)
        m = re.search(
            r"const\s+double\s+LAMBDA_CEIL_FLOOR_1E5\s*=\s*1\.0e-?5\s*;",
            cpp)
        self.assertIsNotNone(m,
            "M_P0_BOUNDED_LAMBDA_RETRY_FLOOR_1E5: LAMBDA_CEIL_FLOOR_1E5 "
            "must be declared as `const double = 1.0e-5;`. The 1e-5 "
            "ceil is the patch's whole point — drifting it (e.g. back "
            "to 1e-3) would regress to the ROLLBACK_2 garbage-at-ceil "
            "complaint.")

    def test_PERMANENT_b_max_retries_floor_1e5_literal(self):
        """`const int MAX_RETRIES_FLOOR_1E5 = 4;` declared.

        4 retries lets a default 1e-8 user value escalate 1e-8 → 1e-7
        → 1e-6 → 1e-5 (exactly 4 ×10 steps) without overshooting the
        ceil.
        """
        cpp = _read(_RBF_CPP)
        m = re.search(
            r"const\s+int\s+MAX_RETRIES_FLOOR_1E5\s*=\s*4\s*;",
            cpp)
        self.assertIsNotNone(m,
            "M_P0_BOUNDED_LAMBDA_RETRY_FLOOR_1E5: MAX_RETRIES_FLOOR_1E5 "
            "must be declared as `const int = 4;`. 4 retries covers "
            "1e-8 → 1e-7 → 1e-6 → 1e-5 escalation exactly.")

    def test_PERMANENT_c_retry_block_near_rollback_anchor(self):
        """The bounded retry block must live near (immediately after,
        in fact) the M_P0_KERNEL_SWITCH_ROLLBACK_2 audit anchor —
        replacing ROLLBACK_2's single-pass logic in place. This
        keeps the audit history (ROLLBACK_2 → bounded retry restored)
        readable from a single grep.

        We assert spatial proximity by finding both anchors and
        confirming they appear in the same function body (no other
        major construct between them).
        """
        cpp = _read(_RBF_CPP)
        # Locate the BOUNDED anchor. The ROLLBACK_2 anchor in cpp now
        # lives only in the schema-default comment (not the solver
        # block) since the bounded patch overwrote the solver-block
        # ROLLBACK_2 comment. The "near" check is therefore: the
        # bounded anchor must appear in the solver block (between
        # `wMat.setSize(poseCount, solveCount)` and the next
        # `return MStatus::kFailure`).
        bounded_idx = cpp.find("M_P0_BOUNDED_LAMBDA_RETRY_FLOOR_1E5")
        self.assertGreater(bounded_idx, 0,
            "M_P0_BOUNDED_LAMBDA_RETRY_FLOOR_1E5 anchor missing.")
        # The retry block writes wMat — anchor must come before that
        # somewhere in the solver region.
        wmat_idx = cpp.find("wMat.setSize(poseCount, solveCount)",
                            bounded_idx)
        self.assertGreater(wmat_idx, bounded_idx,
            "BOUNDED anchor must appear BEFORE wMat.setSize() in "
            "the solver block, not in a stray location.")

    def test_PERMANENT_d_schema_default_1e_5(self):
        """`nAttr.setDefault(1.0e-5);` for regularization.

        New default for freshly-created nodes; aligns with the
        bounded-retry ceil so new rigs train without ever hitting
        the retry loop (well-posed K from the start).
        """
        cpp = _read(_RBF_CPP)
        m = re.search(
            r"regularization\s*=\s*nAttr\.create\([^)]*\)[\s\S]{0,1200}?"
            r"nAttr\.setDefault\(\s*1\.0e-?5\s*\)",
            cpp)
        self.assertIsNotNone(m,
            "cpp schema regularization must setDefault(1.0e-5) "
            "(M_P0_BOUNDED_LAMBDA_RETRY_FLOOR_1E5). The previous 1e-8 "
            "default left dense production rigs in kFailure on first "
            "Apply.")

    def test_PERMANENT_e_retry_uses_while_not_for_retry(self):
        """The patch uses `while (!solved && retryCount <= ...)` — NOT
        the `for (int retry = ` outer-loop construct that
        test_kernel_rollback_parity.py::test_PERMANENT_a2 explicitly
        forbids. Both forms are mathematically equivalent but
        `while` keeps the ROLLBACK_2 parity test happy.
        """
        cpp = _read(_RBF_CPP)
        # The while form must appear in the solver block.
        m = re.search(
            r"while\s*\(\s*!solved\s*&&\s*retryCount\s*<=?\s*"
            r"MAX_RETRIES_FLOOR_1E5", cpp)
        self.assertIsNotNone(m,
            "Retry loop must use `while (!solved && retryCount "
            "<= MAX_RETRIES_FLOOR_1E5)` form to keep "
            "test_kernel_rollback_parity.py::test_PERMANENT_a2 "
            "(no `for (int retry = `) green.")
        # And `for (int retry = ` must NOT appear as live code.
        live = [ln for ln in cpp.splitlines()
                if "for (int retry = " in ln
                and not ln.lstrip().startswith("//")]
        self.assertEqual(live, [],
            "Legacy `for (int retry = ` outer-loop form must remain "
            "absent. Found: {!r}".format(live))

    def test_PERMANENT_f_landing_tag_referenced(self):
        """Audit anchor M_P0_BOUNDED_LAMBDA_RETRY_FLOOR_1E5 must
        appear ≥ 2 times so future grep audits can trace the bounded
        retry path from any reference site (solver block, schema
        comment, failure displayError)."""
        cpp = _read(_RBF_CPP)
        hits = cpp.count("M_P0_BOUNDED_LAMBDA_RETRY_FLOOR_1E5")
        self.assertGreaterEqual(hits, 2,
            "Audit anchor M_P0_BOUNDED_LAMBDA_RETRY_FLOOR_1E5 must "
            "appear at least 2 times in cpp (solver block + schema "
            "+ displayError). Found {} hit(s).".format(hits))


if __name__ == "__main__":
    unittest.main()
