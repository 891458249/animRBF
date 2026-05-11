# -*- coding: utf-8 -*-
"""T_M_P0_RBF_POLYNOMIAL_AUGMENTATION (2026-05-11) PERMANENT guard.

Defends the polynomial-augmentation rewrite of the RBF solver.
CPD kernels (Linear, TPS, MQB, IMQB) are mathematically
rank-deficient under pure Tikhonov regularization — no λ value
makes K + λI a faithful interpolation operator, only damps the
null-space contribution. The augmented system

    [ K + λI   P ] [ w ]   [ y ]
    [ P^T      0 ] [ a ] = [ 0 ]

is the canonical CPD treatment (Wendland 2004 §10, Schaback 1995,
Wahba 1990).

Audit chain superseded by this patch:
  fd5607b  M_P0_LAMBDA_RETRY_TIERED_CEIL  .mll v3
  4a3cae4  M_P0_LAMBDA_RETRY_TIERED_CEIL  source
  b16d117  M_P0_BOUNDED_LAMBDA_RETRY_FLOOR_1E5  .mll v1 (audit-trail)
  8e7a6d3  M_P0_BOUNDED_LAMBDA_RETRY_FLOOR_1E5  source (audit-trail)

Source-scan / AST-based guards (PySide / mayapy runtime not in this
test environment). Behavioural verification (training-point identity
holds for all 6 kernels under polynomial augmentation, max|Δ| < 1e-3)
lives in tests/scratch/diag_kernel_rollback.py.

Per Planner spec, 8 PERMANENT guards:
  a. RBFtools.h declares ``static int getPolynomialDim(...)``
  b. RBFtools.h declares ``static void polyBasis(...)``
  c. RBFtools.h declares ``BRMatrix polyMat;`` private member
  d. cpp implements ``getPolynomialDim`` with correct kernel dispatch
  e. cpp implements ``polyBasis`` with constant + linear terms
  f. compute() solver block contains augmented (K + λI, P; P^T, 0)
     matrix construction (literal ``A(poseCount + (unsigned)pk, ai)``
     transpose fill — the saddle-point fingerprint)
  g. getPoseWeights inference adds polynomial term gated on
     ``polyDim > 0``
  h. M_P0_RBF_POLYNOMIAL_AUGMENTATION anchor ≥ 3x in cpp
     (audit trail + solver block + getPoseWeights)
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


class TestPolynomialAugmentation(unittest.TestCase):

    # ----- header declarations -----

    def test_PERMANENT_a_header_declares_getPolynomialDim(self):
        h = _read(_RBF_H)
        self.assertIn(
            "static int getPolynomialDim(", h,
            "RBFtools.h must declare `static int getPolynomialDim("
            "short kernelType, int driverDim)`.")

    def test_PERMANENT_b_header_declares_polyBasis(self):
        h = _read(_RBF_H)
        self.assertIn(
            "static void polyBasis(", h,
            "RBFtools.h must declare `static void polyBasis(...)`.")

    def test_PERMANENT_c_header_declares_polyMat_member(self):
        h = _read(_RBF_H)
        self.assertIsNotNone(
            re.search(r"\bBRMatrix\s+polyMat\s*;", h),
            "RBFtools.h must declare `BRMatrix polyMat;` as a private "
            "runtime member (alongside wMat).")

    # ----- cpp implementations -----

    def test_PERMANENT_d_cpp_getPolynomialDim_dispatch(self):
        """getPolynomialDim must dispatch:
          - Gaussian 1 / 2 (kernelType ∈ {1,2}) → 0
          - TPS (kernelType == 3) → 1 + driverDim
          - default (Linear / MQB / IMQB) → 1
        """
        cpp = _read(_RBF_CPP)
        # Function body present.
        m = re.search(
            r"int\s+RBFtools::getPolynomialDim\s*\([^)]*\)\s*\{"
            r"[\s\S]{0,500}?return\s+1\s*\+\s*driverDim\s*;"
            r"[\s\S]{0,200}?return\s+1\s*;",
            cpp)
        self.assertIsNotNone(m,
            "getPolynomialDim must contain TPS-branch "
            "`return 1 + driverDim` and default `return 1`.")
        # Gaussian branch (return 0).
        self.assertIsNotNone(
            re.search(
                r"if\s*\(\s*kernelType\s*==\s*1\s*\|\|\s*"
                r"kernelType\s*==\s*2\s*\)\s*return\s+0\s*;",
                cpp),
            "getPolynomialDim must return 0 for Gaussian kernels "
            "(kernelType ∈ {1, 2}).")

    def test_PERMANENT_e_cpp_polyBasis_constant_linear(self):
        """polyBasis must:
          - polyDim == 0 → return early empty
          - polyDim >= 1 → out[0] = 1.0 (constant)
          - polyDim > 1  → fill out[1..polyDim-1] from vec
        """
        cpp = _read(_RBF_CPP)
        # Function body
        m = re.search(
            r"void\s+RBFtools::polyBasis\s*\([^)]*\)\s*\{"
            r"[\s\S]{0,800}?out\[0\]\s*=\s*1\.0\s*;"
            r"[\s\S]{0,400}?out\[1\s*\+\s*i\]\s*=\s*vec\[i\]",
            cpp)
        self.assertIsNotNone(m,
            "polyBasis must set out[0] = 1.0 and out[1+i] = vec[i].")

    # ----- solver block: augmented matrix construction -----

    def test_PERMANENT_f_augmented_matrix_construction(self):
        """Solver block must contain the saddle-point matrix transpose
        fill `A(poseCount + (unsigned)pk, ai) = ...` — this is the
        fingerprint of the (K + λI, P; P^T, 0) construction; the same
        fill in the (i, N+k) direction is required but the transpose
        block is the unambiguous augmentation marker."""
        cpp = _read(_RBF_CPP)
        # Two-sided P fill (training side).
        self.assertIsNotNone(
            re.search(
                r"A\s*\(\s*ai\s*,\s*poseCount\s*\+\s*\(unsigned\)pk\s*\)\s*=",
                cpp),
            "Augmented matrix must fill the P block at "
            "A(ai, poseCount + pk).")
        self.assertIsNotNone(
            re.search(
                r"A\s*\(\s*poseCount\s*\+\s*\(unsigned\)pk\s*,\s*ai\s*\)\s*=",
                cpp),
            "Augmented matrix must fill the P^T block at "
            "A(poseCount + pk, ai).")
        # polyDim branch in solver.
        self.assertIn(
            "if (polyDim == 0)", cpp,
            "Solver must branch on `polyDim == 0` for the strictly-PD "
            "(Gaussian) path.")
        # Augmented size.
        self.assertIsNotNone(
            re.search(
                r"augN\s*=\s*poseCount\s*\+\s*\(unsigned\)polyDim",
                cpp),
            "Augmented system size must be N + polyDim.")

    # ----- inference: polynomial term -----

    def test_PERMANENT_g_inference_polynomial_term(self):
        """getPoseWeights must add a polynomial term gated on
        `polyDim > 0` after the RBF accumulation loop and before
        the QWA post-loop."""
        cpp = _read(_RBF_CPP)
        # The inference polynomial accumulator must reference
        # polyMatArg (the parameter name we used in the signature)
        # and gate on polyDim > 0.
        self.assertIsNotNone(
            re.search(
                r"if\s*\(\s*polyDim\s*>\s*0\s*\)[\s\S]{0,800}?"
                r"polyMatArg\s*\(\s*\(unsigned\)k\s*,\s*j\s*\)",
                cpp),
            "getPoseWeights must gate the polynomial term on "
            "`polyDim > 0` and read coefficients from "
            "polyMatArg((unsigned)k, j).")
        # The polynomial term must be added to out[j], not overwritten.
        self.assertIn(
            "out[j] += polySum;", cpp,
            "Polynomial term must be added (+=) to the scalar "
            "accumulator, not overwritten.")

    # ----- audit anchor -----

    def test_PERMANENT_h_anchor_referenced(self):
        """M_P0_RBF_POLYNOMIAL_AUGMENTATION anchor ≥ 3 hits in cpp:
          1. solver block audit-chain comment
          2. getPoseWeights inference polynomial term comment
          3. failure displayError text
        """
        cpp = _read(_RBF_CPP)
        hits = cpp.count("M_P0_RBF_POLYNOMIAL_AUGMENTATION")
        self.assertGreaterEqual(hits, 3,
            "Audit anchor M_P0_RBF_POLYNOMIAL_AUGMENTATION must "
            "appear at least 3 times in cpp (audit chain + "
            "inference + displayError). Found {} hit(s).".format(hits))


if __name__ == "__main__":
    unittest.main()
