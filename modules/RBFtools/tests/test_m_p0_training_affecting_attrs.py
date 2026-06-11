# -*- coding: utf-8 -*-
"""T_M_P0_TRAINING_AFFECTING_ATTRS — defend the auto-retrain-on-
training-attr-change machinery in compute().

Bug context (M_P0_TRAINING_AFFECTING_ATTRS, 2026-05-10):
  User reported driven joint offset / drift on rest pose when
  switching kernel from Gaussian to Multi-Quadratic Biharmonic.
  Root cause: ``attributeAffects(<attr>, output)`` marks output
  dirty on attr change, but ``evalInput = evaluatePlug.asBool()``
  defaults to False, so the cached wMat (trained under the OLD
  attribute value) is reused with the NEW value at inference →
  mathematically inconsistent solver state → output drift.

  Same root cause applies to: distanceType, inputEncoding, radius,
  radiusType, regularization. All six attributes mutate either
  the K matrix structure (kernel / distanceType / radius family)
  or the encoded pose vector dimensions (inputEncoding) or the
  diagonal regularization (regularization). Any of these changing
  must trigger wMat re-solve.

Fix: track each attr's last-applied value in RBFtools.h members
``prevKernelVal`` / ``prevDistanceTypeVal`` / ``prevRadiusTypeVal``
/ ``prevRadiusVal`` / ``prevRegularizationVal``. At compute()
entry, after the plug reads, compare to current and set
``evalInput = true`` if any differ. inputEncoding piggybacks on
the existing ``prevInputEncodingVal`` tracker via a frame-local
``inputEncodingChangedThisFrame`` flag (the existing prev tracker
runs BEFORE the evalInput plug read so could not be promoted in
place without clobbering).

Sentinel values (-1 / -1.0) chosen so the FIRST compute() after
node creation never spuriously triggers a re-train (initial prev
== -1, current is a real plug value, but we explicitly skip the
"first compute" branch via the != -1 guard).
"""
from __future__ import absolute_import, division, print_function

import io
import os
import re
import unittest


_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(os.path.dirname(_HERE)))
_RBF_CPP = os.path.join(_REPO, "source", "RBFtools.cpp")
_RBF_H = os.path.join(_REPO, "source", "RBFtools.h")


def _read(path):
    with io.open(path, "r", encoding="utf-8") as fh:
        return fh.read()


class TestTrainingAffectingAttrs(unittest.TestCase):

    # ----- Header member declarations -----

    def test_PERMANENT_a_header_declares_prev_kernel(self):
        h = _read(_RBF_H)
        self.assertRegex(h,
            r"short\s+prevKernelVal\s*;",
            "RBFtools.h must declare prevKernelVal (short).")

    def test_PERMANENT_b_header_declares_prev_distance_type(self):
        h = _read(_RBF_H)
        self.assertRegex(h,
            r"short\s+prevDistanceTypeVal\s*;",
            "RBFtools.h must declare prevDistanceTypeVal (short).")

    def test_PERMANENT_c_header_declares_prev_radius_type(self):
        h = _read(_RBF_H)
        self.assertRegex(h,
            r"short\s+prevRadiusTypeVal\s*;",
            "RBFtools.h must declare prevRadiusTypeVal (short).")

    def test_PERMANENT_d_header_declares_prev_radius(self):
        h = _read(_RBF_H)
        self.assertRegex(h,
            r"double\s+prevRadiusVal\s*;",
            "RBFtools.h must declare prevRadiusVal (double).")

    def test_PERMANENT_e_header_declares_prev_regularization(self):
        h = _read(_RBF_H)
        self.assertRegex(h,
            r"double\s+prevRegularizationVal\s*;",
            "RBFtools.h must declare prevRegularizationVal (double).")

    # ----- Constructor sentinel initialization -----

    def test_PERMANENT_f_constructor_inits_kernel_sentinel(self):
        cpp = _read(_RBF_CPP)
        self.assertRegex(cpp,
            r"prevKernelVal\s*\(\s*-1\s*\)",
            "Constructor must init prevKernelVal to -1 sentinel "
            "so first compute() does not spuriously retrain.")

    def test_PERMANENT_g_constructor_inits_distance_type_sentinel(self):
        cpp = _read(_RBF_CPP)
        self.assertRegex(cpp,
            r"prevDistanceTypeVal\s*\(\s*-1\s*\)")

    def test_PERMANENT_h_constructor_inits_radius_type_sentinel(self):
        cpp = _read(_RBF_CPP)
        self.assertRegex(cpp,
            r"prevRadiusTypeVal\s*\(\s*-1\s*\)")

    def test_PERMANENT_i_constructor_inits_radius_sentinel(self):
        cpp = _read(_RBF_CPP)
        self.assertRegex(cpp,
            r"prevRadiusVal\s*\(\s*-1\.0\s*\)")

    def test_PERMANENT_j_constructor_inits_regularization_sentinel(self):
        cpp = _read(_RBF_CPP)
        self.assertRegex(cpp,
            r"prevRegularizationVal\s*\(\s*-1\.0\s*\)")

    # ----- Detection logic at compute() -----

    def test_PERMANENT_k_compute_has_training_attr_changed_flag(self):
        cpp = _read(_RBF_CPP)
        self.assertRegex(cpp,
            r"bool\s+trainingAttrChanged\s*=\s*false",
            "compute() must declare 'bool trainingAttrChanged = false' "
            "as the aggregator for any of the 6 tracked attr changes.")

    def test_PERMANENT_l_compute_promotes_to_evalinput(self):
        cpp = _read(_RBF_CPP)
        self.assertRegex(cpp,
            r"if\s*\(\s*trainingAttrChanged\s*\)\s*\n?\s*evalInput\s*=\s*true",
            "compute() must promote trainingAttrChanged to "
            "'evalInput = true' so wMat re-solves under the new "
            "attribute value.")

    def test_PERMANENT_m_compute_checks_kernel_change(self):
        cpp = _read(_RBF_CPP)
        self.assertRegex(cpp,
            r"if\s*\(\s*kernelVal\s*!=\s*prevKernelVal\s*\)",
            "compute() must check kernelVal != prevKernelVal.")

    def test_PERMANENT_n_compute_checks_distance_type_change(self):
        cpp = _read(_RBF_CPP)
        self.assertRegex(cpp,
            r"if\s*\(\s*distanceTypeVal\s*!=\s*prevDistanceTypeVal\s*\)")

    def test_PERMANENT_o_compute_checks_radius_change(self):
        cpp = _read(_RBF_CPP)
        self.assertRegex(cpp,
            r"if\s*\(\s*radiusVal\s*!=\s*prevRadiusVal\s*\)")

    def test_PERMANENT_p_compute_checks_regularization_change(self):
        cpp = _read(_RBF_CPP)
        self.assertRegex(cpp,
            r"if\s*\(\s*regularizationVal\s*!=\s*prevRegularizationVal\s*\)")

    def test_PERMANENT_q_input_encoding_propagates_via_flag(self):
        """inputEncoding change → frame-local flag → trainingAttrChanged."""
        cpp = _read(_RBF_CPP)
        self.assertRegex(cpp,
            r"bool\s+inputEncodingChangedThisFrame\s*=\s*false",
            "Must declare inputEncodingChangedThisFrame flag to bridge "
            "the warning-reset block (which runs before evalInput is "
            "read from the plug) and the trainingAttrChanged "
            "aggregator (which runs after the evalInput read).")
        self.assertRegex(cpp,
            r"if\s*\(\s*inputEncodingChangedThisFrame\s*\)\s*\n?\s*"
            r"trainingAttrChanged\s*=\s*true",
            "trainingAttrChanged must be set from "
            "inputEncodingChangedThisFrame.")

    # ----- Landing tag -----

    def test_PERMANENT_r_landing_tag_referenced(self):
        cpp = _read(_RBF_CPP)
        h = _read(_RBF_H)
        self.assertGreaterEqual(
            cpp.count("M_P0_TRAINING_AFFECTING_ATTRS"), 2,
            "RBFtools.cpp must reference M_P0_TRAINING_AFFECTING_ATTRS "
            "at least 2x for git-blame traceability.")
        self.assertIn("M_P0_TRAINING_AFFECTING_ATTRS", h,
            "RBFtools.h must reference M_P0_TRAINING_AFFECTING_ATTRS "
            "at the prev-tracker member declaration site.")


if __name__ == "__main__":
    unittest.main()
