# -*- coding: utf-8 -*-
"""T_M_P0_LAMBDA_RETRY_TIERED_CEIL (2026-05-11) PERMANENT guard.

Defends the tiered λ-ceil patch:
  * 8e7a6d3 / b16d117 (M_P0_BOUNDED_LAMBDA_RETRY_FLOOR_1E5) restored
    bounded retry with a uniform 1e-5 ceil. User λ-sweep then showed
    that ceil is sufficient for strictly-PD kernels (Linear / Gaussian)
    but TPS / MQB / IMQB still kFailure at 1e-5 because their
    K[i,i] = O(σ) or O(1/σ) is 100× smaller.
  * M_P0_LAMBDA_RETRY_TIERED_CEIL (this commit) replaces the uniform
    1e-5 with a per-kernel-class ceil:
        kIsStrictlyPDKernel = (kernelVal in {0,1,2})
        LAMBDA_CEIL_TIERED = 1e-5 (strictly PD) | 1e-3 (cond PD)
        MAX_RETRIES_TIERED = 4 (strictly PD) | 6 (cond PD)

Source-scan / AST-based assertions only. Phase 5-style behavioural
verification (Maya λ-sweep CSV) lives in
``tests/scratch/diag_kernel_rollback.py``.

Per Planner spec, 6 PERMANENT guards:
  a. `kIsStrictlyPDKernel` ternary detection literal present
  b. `LAMBDA_CEIL_TIERED` literal + tiered values 1e-5 / 1e-3 present
  c. `MAX_RETRIES_TIERED` literal + tiered values 4 / 6 present
  d. strictly-PD detection covers exactly kernelVal ∈ {0, 1, 2}
  e. old `LAMBDA_CEIL_FLOOR_1E5` / `MAX_RETRIES_FLOOR_1E5` const
     names are GONE from active source (sentinel that the patch
     truly replaced 8e7a6d3 instead of stacking)
  f. landing tag `M_P0_LAMBDA_RETRY_TIERED_CEIL` referenced ≥ 2x
     in cpp (audit anchor)
"""
from __future__ import absolute_import, division, print_function

import io
import os
import re
import unittest

import pytest


_HERE = os.path.dirname(os.path.abspath(__file__))
_TESTS_DIR = os.path.dirname(_HERE)
_REPO = os.path.dirname(os.path.dirname(os.path.dirname(_TESTS_DIR)))
_RBF_CPP = os.path.join(_REPO, "source", "RBFtools.cpp")


def _read(path):
    with io.open(path, "r", encoding="utf-8") as fh:
        return fh.read()


# M_P0_RBF_POLYNOMIAL_AUGMENTATION (2026-05-11) supersedes
# M_P0_LAMBDA_RETRY_TIERED_CEIL by removing the entire retry loop
# in favour of mathematically-correct polynomial augmentation for
# CPD kernels. All six guards below were AST/regex assertions on
# LAMBDA_CEIL_TIERED / MAX_RETRIES_TIERED / kIsStrictlyPDKernel
# constructs that no longer exist in cpp. Inverting each assertion
# was rejected — class-level skip mirrors the
# test_m_p0_auto_adaptive_lambda.py treatment from
# M_P0_KERNEL_SWITCH_ROLLBACK_2 (91adfc9) and keeps the historical
# guard intent readable to future audit readers.
#
# Behavioural verification of the polynomial-augmented solver lives
# in test_polynomial_augmentation.py + Maya-side λ-sweep diag.
@pytest.mark.skip(
    reason="M_P0_RBF_POLYNOMIAL_AUGMENTATION: tiered retry loop "
           "removed; polynomial augmentation is the correct math for "
           "CPD kernels (see test_polynomial_augmentation.py).")
class TestLambdaRetryTieredCeil(unittest.TestCase):

    def test_PERMANENT_a_strictly_pd_detection_literal(self):
        """`const bool kIsStrictlyPDKernel = (kernelVal == 0 ...)`
        must be declared so the ternary tier dispatch can read it."""
        cpp = _read(_RBF_CPP)
        m = re.search(
            r"const\s+bool\s+kIsStrictlyPDKernel\s*=",
            cpp)
        self.assertIsNotNone(m,
            "M_P0_LAMBDA_RETRY_TIERED_CEIL: kIsStrictlyPDKernel "
            "boolean must be declared as the gate for the tiered ceil.")

    def test_PERMANENT_b_lambda_ceil_tiered_present(self):
        """`LAMBDA_CEIL_TIERED` ternary + both 1.0e-5 / 1.0e-3 ceil
        literals."""
        cpp = _read(_RBF_CPP)
        m = re.search(
            r"const\s+double\s+LAMBDA_CEIL_TIERED\s*=\s*"
            r"kIsStrictlyPDKernel\s*\?\s*1\.0e-?5\s*:\s*1\.0e-?3\s*;",
            cpp)
        self.assertIsNotNone(m,
            "LAMBDA_CEIL_TIERED must be declared as `ternary on "
            "kIsStrictlyPDKernel : 1.0e-5 : 1.0e-3`. The ternary form "
            "is the patch's whole correctness argument — drift would "
            "silently regress to the uniform-ceil bug.")

    def test_PERMANENT_c_max_retries_tiered_present(self):
        """`MAX_RETRIES_TIERED` ternary + both 4 / 6 retry-count
        literals. Conditionally-PD needs more retries because they
        start with a smaller user λ relative to a larger ceil."""
        cpp = _read(_RBF_CPP)
        m = re.search(
            r"const\s+int\s+MAX_RETRIES_TIERED\s*=\s*"
            r"kIsStrictlyPDKernel\s*\?\s*4\s*:\s*6\s*;",
            cpp)
        self.assertIsNotNone(m,
            "MAX_RETRIES_TIERED must be declared as `ternary on "
            "kIsStrictlyPDKernel : 4 : 6`. 4 retries cover 1e-8 → "
            "1e-5 (strictly PD); 6 retries cover 1e-8 → 1e-3 "
            "(conditionally PD).")

    def test_PERMANENT_d_strictly_pd_kernel_set_is_012(self):
        """Strictly-PD detection must enumerate exactly kernelVal ∈
        {0, 1, 2} (Linear, Gaussian 1, Gaussian 2). Adding 3 (TPS)
        or 4/5 (MQ/IMQ) would silently regress to the uniform-ceil
        bug for those kernels."""
        cpp = _read(_RBF_CPP)
        m = re.search(
            r"const\s+bool\s+kIsStrictlyPDKernel\s*=\s*"
            r"\(\s*kernelVal\s*==\s*0\s*"
            r"\|\|\s*kernelVal\s*==\s*1\s*"
            r"\|\|\s*kernelVal\s*==\s*2\s*\)\s*;",
            cpp, re.DOTALL)
        self.assertIsNotNone(m,
            "kIsStrictlyPDKernel must read EXACTLY "
            "(kernelVal == 0 || kernelVal == 1 || kernelVal == 2). "
            "Drift here means TPS / MQB / IMQB get the wrong ceil.")

    def test_PERMANENT_e_old_floor_1e5_consts_removed(self):
        """8e7a6d3's `LAMBDA_CEIL_FLOOR_1E5` and
        `MAX_RETRIES_FLOOR_1E5` must be GONE from active source.
        Their absence is the sentinel that the tiered patch truly
        replaced the uniform-ceil patch in place rather than stacking
        a duplicate const block."""
        cpp = _read(_RBF_CPP)
        for sym in ("LAMBDA_CEIL_FLOOR_1E5", "MAX_RETRIES_FLOOR_1E5"):
            live_lines = [ln for ln in cpp.splitlines()
                          if sym in ln
                          and not ln.lstrip().startswith("//")
                          and not ln.lstrip().startswith("*")]
            self.assertEqual(
                live_lines, [],
                "Old uniform-ceil const {!r} must be removed from "
                "active cpp source (replaced by LAMBDA_CEIL_TIERED / "
                "MAX_RETRIES_TIERED). Found in lines: {!r}".format(
                    sym, live_lines))

    def test_PERMANENT_f_landing_tag_referenced(self):
        """Audit anchor M_P0_LAMBDA_RETRY_TIERED_CEIL must appear ≥ 2
        times in cpp (solver block comment + displayError)."""
        cpp = _read(_RBF_CPP)
        hits = cpp.count("M_P0_LAMBDA_RETRY_TIERED_CEIL")
        self.assertGreaterEqual(hits, 2,
            "Audit anchor M_P0_LAMBDA_RETRY_TIERED_CEIL must appear "
            "at least 2 times in cpp (solver block + displayError). "
            "Found {} hit(s).".format(hits))


if __name__ == "__main__":
    unittest.main()
