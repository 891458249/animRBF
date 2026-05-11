# -*- coding: utf-8 -*-
"""T_M_P0_RBF_COLUMN_RANK_DEFENSE (2026-05-12) PERMANENT guard.

Defends the column-rank defence patch over M_P0_RBF_POLYNOMIAL_AUGMENTATION:

  * Path B half (polyDim upgrade): MQB / IMQB / Linear bumped from
    polyDim = 1 (strict-CPD-minimum) to polyDim = 1 + driverDim
    (industry-standard, matches SciPy RBFInterpolator + PyGeM).
  * C lite half (column-rank defence): pre-solve variance-floor scan
    drops near-constant driver columns from the polynomial basis P,
    keeping the saddle-point system invertible when raw rig data has
    a near-rest driver dimension. Inference layer is untouched —
    dropped polyMat rows are zero-padded, multiplying to 0 in
    polyBasis(driver) · polyMat without any inference-side branch.

Why this matters (user reproducer):
  - 22 poses × 9-dim Raw rig, kernel = MQB (kernelType = 4)
  - 18/22 poses share bit-identical values in driver-1 cols 0-2
  - User λ = 1e-7 → augmented system singular even after
    polynomial-augmentation patch shipped (M_P0_RBF_POLYNOMIAL_AUGMENTATION)
  - Root cause: MQB polyDim = 1 (constant only) gave the saddle-point
    system no driver-derived columns to absorb the rest-pose pattern
  - Fix: polyDim → 1 + driverDim AND drop the bit-identical cols
    from P at solve time

Source-scan / AST-based assertions only. Phase-5-style behavioural
verification (training-point identity holds for the user rig under
the rank-defence patch, max |Δ| < 1e-3) lives in
tests/scratch/diag_kernel_rollback.py.

Per Planner spec, 8 PERMANENT guards:
  a. header declares `static void detectDegeneratePolyCols(...)`
  b. header declares the `bool degenerateColumnWarningIssued`
     private flag
  c. ctor initialises the flag to `false`
  d. cpp implements `detectDegeneratePolyCols` with column-mean +
     column-variance loop and a `var < varFloor` threshold check
  e. solver block calls `detectDegeneratePolyCols` and uses
     `isActiveLinear` to drive an `activePolyToDriver` index map
     for the reduced P matrix
  f. polyMatTrial is sized to FULL polyDim (not activePolyDim) so
     dropped rows zero-pad automatically
  g. M_P0_RBF_COLUMN_RANK_DEFENSE anchor referenced ≥ 3 times in
     cpp (helper / solver / inference handoff)
  h. once-per-rig warning emit is gated by
     `degenerateColumnWarningIssued` (anti-flood)
"""
from __future__ import absolute_import, division, print_function

import io
import os
import re
import unittest


_HERE = os.path.dirname(os.path.abspath(__file__))
_TESTS_DIR = os.path.dirname(_HERE)
_REPO = os.path.dirname(os.path.dirname(os.path.dirname(_TESTS_DIR)))
_RBF_CPP = os.path.join(_REPO, "source", "RBFtools.cpp")
_RBF_H = os.path.join(_REPO, "source", "RBFtools.h")


def _read(path):
    with io.open(path, "r", encoding="utf-8") as fh:
        return fh.read()


class TestColumnRankDefense(unittest.TestCase):

    # ----- header declarations -----

    def test_PERMANENT_a_header_declares_detector(self):
        h = _read(_RBF_H)
        self.assertIn(
            "static void detectDegeneratePolyCols(", h,
            "RBFtools.h must declare `static void "
            "detectDegeneratePolyCols(const BRMatrix &poseData, "
            "double varFloor, std::vector<bool> &isActiveLinear, "
            "bool &anyDegenerate)`.")

    def test_PERMANENT_b_header_declares_warning_flag(self):
        h = _read(_RBF_H)
        self.assertIsNotNone(
            re.search(r"\bbool\s+degenerateColumnWarningIssued\s*;",
                      h),
            "RBFtools.h must declare `bool "
            "degenerateColumnWarningIssued;` as a private member.")

    # ----- ctor init -----

    def test_PERMANENT_c_ctor_initialises_flag(self):
        cpp = _read(_RBF_CPP)
        self.assertIn(
            "degenerateColumnWarningIssued(false)", cpp,
            "RBFtools::RBFtools ctor must initialise "
            "`degenerateColumnWarningIssued` to false (fresh per "
            "rig instance).")

    # ----- detector implementation -----

    def test_PERMANENT_d_detector_variance_loop(self):
        """detectDegeneratePolyCols must compute per-column mean then
        per-column variance, and threshold via `var < varFloor`."""
        cpp = _read(_RBF_CPP)
        m = re.search(
            r"void\s+RBFtools::detectDegeneratePolyCols\s*\([^)]*\)\s*\{"
            r"[\s\S]{0,3000}?const\s+double\s+mean\s*="
            r"[\s\S]{0,1500}?const\s+double\s+var\s*="
            r"[\s\S]{0,500}?if\s*\(\s*var\s*<\s*varFloor\s*\)",
            cpp)
        self.assertIsNotNone(m,
            "detectDegeneratePolyCols must compute per-column mean "
            "+ variance and threshold with `var < varFloor`.")

    # ----- solver wiring -----

    def test_PERMANENT_e_solver_uses_active_poly_map(self):
        """Solver block must call detectDegeneratePolyCols, derive
        activePolyDim + activePolyToDriver, and use the map both
        when filling P and when expanding the reduced solution back
        into the full polyMat layout."""
        cpp = _read(_RBF_CPP)
        # Detector invocation.
        self.assertIn(
            "detectDegeneratePolyCols(", cpp,
            "Solver must call detectDegeneratePolyCols.")
        # activePolyToDriver index map.
        self.assertIn(
            "activePolyToDriver", cpp,
            "Solver must use an `activePolyToDriver` map to track "
            "which P column corresponds to which driver dimension.")
        # activePolyDim used as the reduced matrix size.
        self.assertIn(
            "activePolyDim", cpp,
            "Solver must use `activePolyDim` as the reduced "
            "saddle-point matrix dimension.")
        # The augmented matrix size must use activePolyDim, not
        # polyDim.
        self.assertIsNotNone(
            re.search(
                r"augN\s*=\s*poseCount\s*\+\s*"
                r"\(unsigned\)activePolyDim",
                cpp),
            "Augmented matrix size must read "
            "`poseCount + (unsigned)activePolyDim`, NOT polyDim.")

    def test_PERMANENT_f_polymattrial_sized_to_full_polydim(self):
        """polyMatTrial must be sized to FULL polyDim (not
        activePolyDim) so dropped rows zero-pad automatically and
        inference reads at full polyDim without any branch."""
        cpp = _read(_RBF_CPP)
        # Find the polyMatTrial.setSize call in the solver block and
        # verify it uses polyDim.
        self.assertIsNotNone(
            re.search(
                r"polyMatTrial\.setSize\s*\(\s*"
                r"\(unsigned\)polyDim\s*,",
                cpp),
            "polyMatTrial.setSize must use full polyDim (not "
            "activePolyDim) so dropped rows zero-pad automatically.")

    # ----- audit anchor -----

    def test_PERMANENT_g_audit_anchor_referenced(self):
        cpp = _read(_RBF_CPP)
        hits = cpp.count("M_P0_RBF_COLUMN_RANK_DEFENSE")
        self.assertGreaterEqual(hits, 3,
            "Audit anchor M_P0_RBF_COLUMN_RANK_DEFENSE must appear "
            "at least 3 times in cpp (header decl, helper body, "
            "solver block + ctor init flag comment). Found {} hit(s)."
            .format(hits))

    # ----- anti-flood warning -----

    def test_PERMANENT_h_warning_gated_by_flag(self):
        """The degenerate-column warning emit must be guarded by
        `!degenerateColumnWarningIssued` so a single rig with a
        degenerate driver only logs the warning once across
        interactive timeline scrubs."""
        cpp = _read(_RBF_CPP)
        m = re.search(
            r"if\s*\(\s*anyDegenerate\s*"
            r"&&\s*!degenerateColumnWarningIssued\s*\)"
            r"[\s\S]{0,3500}?"
            r"degenerateColumnWarningIssued\s*=\s*true\s*;",
            cpp)
        self.assertIsNotNone(m,
            "Solver must gate the disclosure warning behind "
            "`if (anyDegenerate && !degenerateColumnWarningIssued)` "
            "and set the flag to true after emitting.")


if __name__ == "__main__":
    unittest.main()
