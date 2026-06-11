# -*- coding: utf-8 -*-
"""M_P0_RBF_ANTI_OVERSHOOT (2026-05-17) -- Phase 15 anti-overshoot
permanent guards.

The C++ unit-level behaviour cannot be tested without an actual Maya
runtime (the inference path is inside the DG compute) so this file
uses source-introspection + .mll binary string checks to lock the
patch invariants. Mirrors the test_m_p0_apply_nodestate_fix.py
pattern.

Cases:
  Part A (Output Clamp):
    1. test_PERMANENT_A1_output_clamp_attributes_declared
    2. test_PERMANENT_A2_output_clamp_attributes_registered
    3. test_PERMANENT_A3_output_clamp_attribute_affects_output
    4. test_PERMANENT_A4_output_min_max_vectors_declared
    5. test_PERMANENT_A5_inference_clamp_present
  Part C (audit safety):
    6. test_PERMANENT_C1_aabb_inversion_swap_in_input_clamp
    7. test_PERMANENT_C2_negative_inflation_floor_in_input_clamp
    8. test_PERMANENT_C3_nan_driver_replaced_in_input_clamp
    9. test_PERMANENT_C4_brmatrix_singular_threshold_configurable
  Cross-binary:
   10. test_PERMANENT_BIN_dual_mll_contains_phase15_strings
"""

from __future__ import absolute_import

import io
import os
import re
import sys
import unittest

_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
if _TESTS_DIR not in sys.path:
    sys.path.insert(0, _TESTS_DIR)

import conftest  # noqa: E402


_REPO_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
_RBF_H = os.path.join(_REPO_ROOT, "source", "RBFtools.h")
_RBF_CPP = os.path.join(_REPO_ROOT, "source", "RBFtools.cpp")
_BRMAT_H = os.path.join(_REPO_ROOT, "source", "BRMatrix.h")
_BRMAT_CPP = os.path.join(_REPO_ROOT, "source", "BRMatrix.cpp")
_MLL_2022 = os.path.join(
    _REPO_ROOT, "modules", "RBFtools", "plug-ins",
    "win64", "2022", "RBFtools.mll")
_MLL_2025 = os.path.join(
    _REPO_ROOT, "modules", "RBFtools", "plug-ins",
    "win64", "2025", "RBFtools.mll")


def _read(path):
    with io.open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def _read_bin(path):
    with open(path, "rb") as fh:
        return fh.read()


# ----------------------------------------------------------------------
# PERMANENT GUARDS -- Part A: Output Clamp
# ----------------------------------------------------------------------


class T_M_P0_RBF_ANTI_OVERSHOOT_PartA(unittest.TestCase):
    """Part A: output clamp attributes + training-time AABB cache +
    inference clamp injection. The C++ ABI cannot be tested without
    a Maya runtime, so we lock the layout via source introspection
    so a future refactor cannot silently remove the patch."""

    @classmethod
    def setUpClass(cls):
        cls._h = _read(_RBF_H)
        cls._cpp = _read(_RBF_CPP)

    def test_PERMANENT_A1_output_clamp_attributes_declared(self):
        """RBFtools.h MUST declare the two new MObject attributes."""
        self.assertIn(
            "static MObject outputClampEnabled;", self._h,
            "Part A: RBFtools.h MUST declare outputClampEnabled")
        self.assertIn(
            "static MObject outputClampInflation;", self._h,
            "Part A: RBFtools.h MUST declare outputClampInflation")

    def test_PERMANENT_A2_output_clamp_attributes_registered(self):
        """RBFtools.cpp MUST register the attributes via addAttribute."""
        self.assertIn(
            "addAttribute(outputClampEnabled);", self._cpp,
            "Part A: addAttribute(outputClampEnabled) missing")
        self.assertIn(
            "addAttribute(outputClampInflation);", self._cpp,
            "Part A: addAttribute(outputClampInflation) missing")
        # The default ON must be set explicitly in the create block
        # so the Houdini-aligned behaviour is the schema default.
        self.assertRegex(
            self._cpp,
            r'outputClampEnabled\s*=\s*nAttr\.create\(\s*'
            r'"outputClampEnabled"',
            "Part A: outputClampEnabled MUST be created with the "
            "documented attr name")

    def test_PERMANENT_A3_output_clamp_attribute_affects_output(self):
        """attributeAffects pairs MUST exist so the DG re-evaluates
        the output when the user toggles the new attrs."""
        self.assertIn(
            "attributeAffects(RBFtools::outputClampEnabled, "
            "RBFtools::output);", self._cpp,
            "Part A: outputClampEnabled MUST affect output")
        self.assertIn(
            "attributeAffects(RBFtools::outputClampInflation, "
            "RBFtools::output);", self._cpp,
            "Part A: outputClampInflation MUST affect output")

    def test_PERMANENT_A4_output_min_max_vectors_declared(self):
        """RBFtools.h MUST declare the per-channel bounds state
        vectors used by the inference clamp."""
        self.assertIn(
            "std::vector<double> outputMinVec;", self._h,
            "Part A: outputMinVec member missing")
        self.assertIn(
            "std::vector<double> outputMaxVec;", self._h,
            "Part A: outputMaxVec member missing")

    def test_PERMANENT_A5_inference_clamp_present(self):
        """The per-channel inference finalize loop MUST contain the
        clamp block guarded by outputClampEnabledVal + the AABB
        bounds vectors. We assert on the canonical fragment so a
        future refactor must touch this guard."""
        self.assertIn(
            "outputClampEnabledVal", self._cpp,
            "Part A: inference path MUST read outputClampEnabledVal")
        # Inference clamp body fragments:
        self.assertIn(
            "i < outputMinVec.size()", self._cpp,
            "Part A: inference clamp MUST guard on outputMinVec size")
        self.assertIn(
            "i < outputMaxVec.size()", self._cpp,
            "Part A: inference clamp MUST guard on outputMaxVec size")
        # The warning text is split across adjacent string literals
        # ("output AABB " + "inverted (max < min) at " + ...); the
        # source-text check splits the assertion accordingly.
        self.assertIn(
            "output AABB ", self._cpp,
            "Part A: inference clamp MUST emit the documented "
            "output-side AABB-inversion warning")
        self.assertIn(
            "(max < min)", self._cpp,
            "Part A: inference clamp warn MUST mention the "
            "max < min check so the user can distinguish "
            "input-side from output-side AABB inversion")


# ----------------------------------------------------------------------
# PERMANENT GUARDS -- Part C: audit safety
# ----------------------------------------------------------------------


class T_M_P0_RBF_ANTI_OVERSHOOT_PartC(unittest.TestCase):
    """Part C: 4 audit safety guards across the existing input clamp
    + the new BRMatrix singularity threshold."""

    @classmethod
    def setUpClass(cls):
        cls._cpp = _read(_RBF_CPP)
        cls._brmat_h = _read(_BRMAT_H)
        cls._brmat_cpp = _read(_BRMAT_CPP)

    def test_PERMANENT_C1_aabb_inversion_swap_in_input_clamp(self):
        """Part C.1: input clamp MUST swap inverted AABB + warn.

        The warning text is split across adjacent C++ string literals
        (compiler-time concatenation); the source-text check uses
        substring fragments + a `Part C.1` patch-tag reference.
        """
        self.assertIn(
            "AABB inverted ", self._cpp,
            "Part C.1: input clamp MUST display an AABB-inversion "
            "warning when the cached bounds are reversed")
        # The literal `(poseMax < poseMin)` lives in the input clamp
        # warning specifically. Output clamp uses `(max < min)` so
        # we can distinguish them.
        self.assertIn(
            "(poseMax < poseMin)", self._cpp,
            "Part C.1: input clamp warning MUST mention the "
            "specific poseMax < poseMin comparison so the user can "
            "tell input-side vs output-side at a glance")
        self.assertIn(
            "Part C.1", self._cpp,
            "Part C.1: input clamp warn MUST reference the patch "
            "tag for triage")
        # std::swap on the local copies of the bounds.
        self.assertIn(
            "std::swap(pmin, pmax)", self._cpp,
            "Part C.1: input clamp MUST swap inverted bounds")

    def test_PERMANENT_C2_negative_inflation_floor_in_input_clamp(self):
        """Part C.2: clampInflation MUST be floored to 0.0 before
        the lo / hi computation."""
        self.assertIn(
            "(clampInflationVal > 0.0) ? clampInflationVal : 0.0",
            self._cpp,
            "Part C.2: input clamp MUST floor clampInflationVal at "
            "0.0 so a negative value cannot invert the inflation "
            "direction")

    def test_PERMANENT_C3_nan_driver_replaced_in_input_clamp(self):
        """Part C.3: non-finite driver MUST be replaced with the
        AABB midpoint + warn before the < / > comparisons."""
        self.assertIn(
            "non-finite driver[", self._cpp,
            "Part C.3: input clamp MUST display the documented "
            "non-finite-driver warning")
        # The patch tag appears split across adjacent C++ string
        # literals -- the compiler concatenates them but the source
        # has a quote-quote-newline boundary. Assert both halves
        # are present plus a `Part C.3` reference somewhere in the
        # file.
        self.assertIn(
            "M_P0_RBF_ANTI_OVERSHOOT", self._cpp,
            "Part C.3: NaN/Inf guard MUST cite the patch tag")
        self.assertIn(
            "Part C.3", self._cpp,
            "Part C.3: NaN/Inf guard MUST cite the part number "
            "in the warning message")
        # The replacement value is the AABB midpoint.
        self.assertIn(
            "(pmin + pmax) * 0.5", self._cpp,
            "Part C.3: NaN/Inf driver MUST be replaced with the "
            "AABB midpoint")

    def test_PERMANENT_C4_brmatrix_singular_threshold_configurable(self):
        """Part C.4: BRMatrix MUST expose a configurable singular
        threshold; the hardcoded 0.0001 in solve() MUST consume the
        member instead."""
        # Setter + getter declared.
        self.assertIn(
            "void setSingularThreshold(double threshold);",
            self._brmat_h,
            "Part C.4: BRMatrix.h MUST declare setSingularThreshold")
        self.assertIn(
            "double getSingularThreshold() const;", self._brmat_h,
            "Part C.4: BRMatrix.h MUST declare getSingularThreshold")
        self.assertIn(
            "double singularThreshold;", self._brmat_h,
            "Part C.4: BRMatrix.h MUST declare the member")
        # solve() consumes the member instead of the legacy literal.
        self.assertIn(
            "fabs(this->mat[i][i]) < this->singularThreshold",
            self._brmat_cpp,
            "Part C.4: BRMatrix::solve MUST compare the pivot "
            "against this->singularThreshold (was a hardcoded 1e-4)")
        # RBFtools::compute MUST auto-tune the threshold from lambda.
        self.assertIn(
            "setSingularThreshold(", self._cpp,
            "Part C.4: RBFtools::compute MUST call "
            "setSingularThreshold to auto-tune the threshold from "
            "the user's lambda")


# ----------------------------------------------------------------------
# PERMANENT BINARY GUARD -- dual .mll byte fingerprints
# ----------------------------------------------------------------------


class T_M_P0_RBF_ANTI_OVERSHOOT_Binary(unittest.TestCase):
    """Lock the .mll artifacts to the Phase 15 build by checking the
    embedded ASCII strings. Any future C++ change that removes the
    Phase 15 strings (e.g. accidentally reverts the inference clamp)
    fails here -- the byte fingerprint check would be too strict
    (any innocuous comment touch breaks it) but the string check is
    surgical."""

    _PHASE15_STRINGS = [
        b"outputClampEnabled",
        b"outputClampInflation",
        b"M_P0_RBF_ANTI_OVERSHOOT Part C.1",
        b"M_P0_RBF_ANTI_OVERSHOOT Part C.3",
        b"output AABB inverted (max < min)",
    ]

    def _assert_strings_in(self, path, label):
        if not os.path.isfile(path):
            self.skipTest("{} not present".format(path))
        data = _read_bin(path)
        for needle in self._PHASE15_STRINGS:
            self.assertIn(
                needle, data,
                "{}: missing Phase 15 marker {!r}".format(
                    label, needle))

    def test_PERMANENT_BIN_dual_mll_contains_phase15_strings(self):
        self._assert_strings_in(_MLL_2022, "modules/.../2022/RBFtools.mll")
        self._assert_strings_in(_MLL_2025, "modules/.../2025/RBFtools.mll")


if __name__ == "__main__":
    unittest.main()
