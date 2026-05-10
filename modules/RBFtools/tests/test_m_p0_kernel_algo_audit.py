# -*- coding: utf-8 -*-
"""T_M_P0_KERNEL_ALGO_AUDIT — defend the algorithm audit fixes
to TPS PSD edge case + Raw + Angle multi-driver aggregation.

Bug context (M_P0_KERNEL_ALGO_AUDIT, 2026-05-10):
  Comprehensive audit of the kernel × distance dispatch surface
  surfaced two real algorithm bugs:

  (1) Thin Plate kernel returned `value` (the negative-or-zero
      branch) instead of 0.0 when r ≤ 0. Float-noise from
      normalizeColumns can produce r ≈ -1e-15 — a value that
      passes `value > 0` as false but is NOT exactly 0. The
      `else result = value` then wrote a tiny negative entry to
      the K diagonal, breaking K's positive-semidefinite property
      → Cholesky probe fails spuriously → GE fallback → solver
      churn even on well-conditioned pose sets.

  (2) Raw + Angle distance honoured the Angle selection ONLY
      when n == 3 (single driver, single 3-vector). For multi-
      driver Raw setups (n = 3K, K > 1), distType == 1 was
      silently ignored and the path fell through to Euclidean.
      Same dropdown choice meant different things at N=1 vs N>1
      — a real multi-driver bug.

Fix:
  (1) TPS r ≤ 0 branch returns 0.0 — mathematically correct AND
      numerically robust against float-noise negatives.
  (2) Raw + Angle: when n is a positive multiple of 3, aggregate
      per-3-block angles via L2 (matches Riemannian product-
      manifold semantics used by per-block quat / swing-twist
      distance). N=1 single-block path unchanged.

Bonus: comprehensive σ (width) semantics + PSD property
documentation block above interpolateRbf so future readers
do not need to reverse-engineer kernel formulas.
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


class TestKernelAlgoAudit(unittest.TestCase):

    # ----- TPS PSD edge case fix (Bug A) -----

    def test_PERMANENT_a_tps_else_returns_zero(self):
        """TPS r ≤ 0 branch must return 0.0 (was returning `value`)."""
        cpp = _read(_RBF_CPP)
        m = re.search(
            r"//\s*thin\s+plate[\s\S]{0,800}?else\s*\n?\s*result\s*=\s*([^;]+);",
            cpp)
        self.assertIsNotNone(m,
            "Could not locate the TPS else-branch in interpolateRbf.")
        else_value = m.group(1).strip()
        self.assertEqual(else_value, "0.0",
            "TPS r ≤ 0 branch must assign result = 0.0 (PSD-preserving). "
            "The legacy `result = value;` produced a tiny negative "
            "diagonal entry on float-noise inputs, breaking K's "
            "positive-semidefinite property.")

    def test_PERMANENT_b_tps_branch_still_pos_compute(self):
        """TPS r > 0 branch unchanged — still computes r²·log(r)."""
        cpp = _read(_RBF_CPP)
        self.assertRegex(cpp,
            r"if\s*\(\s*value\s*>\s*0\s*\)\s*\n?\s*result\s*=\s*"
            r"value\s*\*\s*value\s*\*\s*log\s*\(\s*value\s*\)",
            "TPS r > 0 branch must still compute value²·log(value).")

    # ----- Raw + Angle multi-driver fix (Bug B) -----

    def test_PERMANENT_c_raw_angle_multi_driver_branch(self):
        """Raw + Angle for n > 3 must aggregate per-3-block angles."""
        cpp = _read(_RBF_CPP)
        # Find the Raw branch in getPoseDelta.
        m = re.search(
            r"if\s*\(\s*encoding\s*==\s*0\s*\)[\s\S]+?(?=\n\s{0,8}if\s*\(\s*encoding\s*==\s*1)",
            cpp)
        self.assertIsNotNone(m,
            "Could not locate the Raw (encoding == 0) branch in getPoseDelta.")
        body = m.group(0)
        # Multi-block path
        self.assertRegex(body,
            r"n\s*>\s*3\s*&&\s*n\s*%\s*3\s*==\s*0",
            "Raw branch must contain a multi-block guard "
            "'n > 3 && n % 3 == 0' for multi-driver Angle aggregation.")
        # L2 aggregation
        self.assertIn("sumSq", body,
            "Multi-block Angle aggregation must use sumSq accumulator "
            "for L2 aggregation across per-3-block angles.")
        self.assertIn("getAngle", body,
            "Multi-block Angle path must call getAngle on each 3-block.")
        self.assertRegex(body,
            r"return\s+sqrt\s*\(\s*sumSq\s*\)",
            "Multi-block Angle path must return sqrt(sumSq) — L2 norm.")

    def test_PERMANENT_d_raw_single_block_path_preserved(self):
        """N=1 single-block Angle path unchanged for backcompat."""
        cpp = _read(_RBF_CPP)
        m = re.search(
            r"if\s*\(\s*encoding\s*==\s*0\s*\)[\s\S]+?(?=\n\s{0,8}if\s*\(\s*encoding\s*==\s*1)",
            cpp)
        body = m.group(0)
        self.assertRegex(body,
            r"if\s*\(\s*n\s*==\s*3\s*\)\s*\n?\s*return\s+getAngle\s*\(",
            "Single-block n==3 path must preserve `return getAngle(...)`.")

    # ----- Unknown-encoding fallback mirrors Raw -----

    def test_PERMANENT_e_unknown_encoding_fallback_mirrors_raw(self):
        """Defensive fallback for unknown encoding must use the same "
        "multi-block Angle aggregation."""
        cpp = _read(_RBF_CPP)
        # Find the unknown-encoding fallback at the end of getPoseDelta.
        # Window: from "// Unknown encoding" up to the next blank line
        # / next function — the closing `}` of getPoseDelta is hard to
        # anchor reliably (other braces in nested vec1/vec2 init), so
        # use a generous slice and check the block content directly.
        idx = cpp.find("// Unknown encoding")
        self.assertGreater(idx, 0,
            "Could not locate the // Unknown encoding fallback "
            "comment in getPoseDelta.")
        body = cpp[idx:idx + 1200]
        self.assertRegex(body,
            r"n\s*>\s*3\s*&&\s*n\s*%\s*3\s*==\s*0",
            "Unknown-encoding fallback must mirror Raw's multi-block "
            "Angle aggregation guard.")
        self.assertRegex(body,
            r"return\s+sqrt\s*\(\s*sumSq\s*\)",
            "Unknown-encoding fallback must end its multi-block "
            "branch with return sqrt(sumSq).")

    # ----- Documentation block -----

    def test_PERMANENT_f_kernel_catalog_doc_present(self):
        """interpolateRbf docstring documents all 6 kernels."""
        cpp = _read(_RBF_CPP)
        # Find the doc block above interpolateRbf.
        m = re.search(
            r"//\s*M_P0_KERNEL_ALGO_AUDIT[\s\S]{0,4000}?double\s+RBFtools::interpolateRbf",
            cpp)
        self.assertIsNotNone(m,
            "Could not locate the M_P0_KERNEL_ALGO_AUDIT kernel "
            "catalog docstring above interpolateRbf.")
        doc = m.group(0)
        # All 6 kernel types must be documented
        for kernel_name in ("Linear", "Gaussian 1", "Gaussian 2",
                            "Thin Plate", "Multi-Quadric",
                            "Inverse Multi-Quadric"):
            self.assertIn(kernel_name, doc,
                "Kernel catalog doc must mention {!r} so future "
                "readers know its formula and PSD property without "
                "reverse-engineering.".format(kernel_name))
        # Width semantics + PSD property mention
        self.assertIn("PSD:", doc,
            "Kernel catalog doc must describe each kernel's PSD "
            "property (positive-definite vs conditionally PD vs not).")
        self.assertIn("Width:", doc,
            "Kernel catalog doc must describe each kernel's width "
            "(σ) semantics — they are NOT consistent across kernels "
            "and the user needs to know.")

    # ----- Landing tag -----

    def test_PERMANENT_g_landing_tag_referenced(self):
        cpp = _read(_RBF_CPP)
        n = cpp.count("M_P0_KERNEL_ALGO_AUDIT")
        self.assertGreaterEqual(n, 3,
            "M_P0_KERNEL_ALGO_AUDIT must be referenced ≥3x in cpp "
            "(TPS fix + Raw multi-block + kernel catalog doc) for "
            "git-blame traceability across all 3 fix sites.")


if __name__ == "__main__":
    unittest.main()
