# -*- coding: utf-8 -*-
"""T_M_P0_QUATERNION_BACKEND_LAND (2026-05-10) PERMANENT guard

Pins the C++ outputEncoding inverse transform that ships with
``M_P0_QUATERNION_BACKEND_LAND``. Behavioural verification (true
round-trip Quat → Euler with mayapy) lives in
``T_M_B24_OUTPUT_QUAT_ROUNDTRIP`` once the dual-runtime mayapy
fixture is fixed; this file pins the source-level invariants so
a future refactor cannot silently un-land the implementation:

* ``decodeQuaternionToEuler`` / ``decodeExpMapToEuler`` /
  ``nlerpQuaternions`` / ``computePerPosePhi`` /
  ``applyOutputEncodingBlend`` are declared and defined.
* ``compute()`` calls ``applyOutputEncodingBlend`` between
  ``getPoseWeights`` and the final-weight scale loop.
* The setOutputValues placeholder thread_local sink remains
  (legacy DG-edge protection) but its comment now references the
  real implementation site.
* The audit-trail row 4114 is restored to ✅ for Quat + ExpMap
  with BendRoll / SwingTwist explicitly listed as v5.x deferral.
* The i18n ``output_encoding_combo_tip`` text no longer carries
  the honest-disclosure forward-compat warning for Quat / ExpMap.
"""
from __future__ import absolute_import, division, print_function

import io
import os
import re
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(os.path.dirname(_HERE)))
_RBF_H = os.path.join(_REPO, "source", "RBFtools.h")
_RBF_CPP = os.path.join(_REPO, "source", "RBFtools.cpp")
_ADDENDUM = os.path.join(
    _REPO, "docs", u"设计文档",
    "RBFtools_v5_addendum_20260424.md")
_I18N = os.path.join(
    _REPO, "modules", "RBFtools", "scripts", "RBFtools",
    "ui", "i18n.py")


def _read(path):
    with io.open(path, "r", encoding="utf-8") as fh:
        return fh.read()


class TestQuaternionBackendLand(unittest.TestCase):

    # ----- C++ header declarations -----

    def test_PERMANENT_a_header_declares_decodeQuaternionToEuler(self):
        src = _read(_RBF_H)
        self.assertIn("decodeQuaternionToEuler", src,
            "RBFtools.h must declare decodeQuaternionToEuler.")

    def test_PERMANENT_b_header_declares_decodeExpMapToEuler(self):
        src = _read(_RBF_H)
        self.assertIn("decodeExpMapToEuler", src,
            "RBFtools.h must declare decodeExpMapToEuler.")

    def test_PERMANENT_c_header_declares_nlerpQuaternions(self):
        src = _read(_RBF_H)
        self.assertIn("nlerpQuaternions", src,
            "RBFtools.h must declare nlerpQuaternions.")

    def test_PERMANENT_d_header_declares_apply_output_encoding_blend(self):
        src = _read(_RBF_H)
        self.assertIn("applyOutputEncodingBlend", src,
            "RBFtools.h must declare applyOutputEncodingBlend.")

    def test_PERMANENT_e_header_declares_compute_per_pose_phi(self):
        src = _read(_RBF_H)
        self.assertIn("computePerPosePhi", src,
            "RBFtools.h must declare computePerPosePhi.")

    def test_PERMANENT_f_header_includes_meuler_rotation(self):
        src = _read(_RBF_H)
        self.assertIn("MEulerRotation.h", src,
            "RBFtools.h must include <maya/MEulerRotation.h> "
            "for the decode functions.")

    # ----- C++ implementation -----

    def test_PERMANENT_g_cpp_implements_decodeQuaternionToEuler(self):
        src = _read(_RBF_CPP)
        self.assertIsNotNone(
            re.search(r"void\s+RBFtools::decodeQuaternionToEuler\s*\(",
                      src),
            "RBFtools.cpp must define RBFtools::decodeQuaternionToEuler.")

    def test_PERMANENT_h_cpp_implements_decodeExpMapToEuler(self):
        src = _read(_RBF_CPP)
        self.assertIsNotNone(
            re.search(r"void\s+RBFtools::decodeExpMapToEuler\s*\(",
                      src),
            "RBFtools.cpp must define RBFtools::decodeExpMapToEuler.")

    def test_PERMANENT_i_cpp_implements_nlerpQuaternions(self):
        src = _read(_RBF_CPP)
        self.assertIsNotNone(
            re.search(r"void\s+RBFtools::nlerpQuaternions\s*\(", src),
            "RBFtools.cpp must define RBFtools::nlerpQuaternions.")

    def test_PERMANENT_j_cpp_implements_apply_output_encoding_blend(self):
        src = _read(_RBF_CPP)
        self.assertIsNotNone(
            re.search(
                r"void\s+RBFtools::applyOutputEncodingBlend\s*\(",
                src),
            "RBFtools.cpp must define applyOutputEncodingBlend.")

    def test_PERMANENT_k_cpp_implements_compute_per_pose_phi(self):
        src = _read(_RBF_CPP)
        self.assertIsNotNone(
            re.search(r"void\s+RBFtools::computePerPosePhi\s*\(", src),
            "RBFtools.cpp must define RBFtools::computePerPosePhi.")

    # ----- compute() dispatch -----

    def test_PERMANENT_l_compute_calls_apply_output_encoding_blend(self):
        """The dispatch must live in compute() so weightsArray is
        rebuilt before the final-weight scale loop runs."""
        src = _read(_RBF_CPP)
        # Find the compute method body and assert the call appears
        # there (not just somewhere in the file, which would be
        # vacuously true once the function is defined).
        compute_idx = src.find("MStatus RBFtools::compute(")
        self.assertGreater(compute_idx, 0,
            "RBFtools::compute(...) entry point not found.")
        # Bound the search at the next top-level void/MStatus to
        # avoid bleeding into other methods.
        next_method = re.search(
            r"\n(?:MStatus|void|double|bool)\s+RBFtools::",
            src[compute_idx + 50:])
        end = (compute_idx + 50 + next_method.start()
               if next_method else len(src))
        compute_body = src[compute_idx:end]
        self.assertIn("applyOutputEncodingBlend(", compute_body,
            "compute() must call applyOutputEncodingBlend before "
            "the final-weight scale loop.")
        self.assertIn("computePerPosePhi(", compute_body,
            "compute() must call computePerPosePhi to source "
            "per-pose phi values for the quat blend.")

    def test_PERMANENT_m_compute_warns_on_bendroll_swingtwist(self):
        src = _read(_RBF_CPP)
        self.assertIn(
            "outputEncodingDeferredWarningIssued", src,
            "compute() must guard the BendRoll/SwingTwist deferral "
            "warning behind a once-per-rig flag.")
        self.assertIn("BendRoll(2)/SwingTwist(4)", src,
            "Deferral warning must name BendRoll(2) / SwingTwist(4) "
            "explicitly so users know which encodings are not "
            "implemented yet.")

    def test_PERMANENT_n_setoutput_placeholder_sink_retained(self):
        """The legacy thread_local sink is retained for DG-edge
        protection but its comment now references the real impl."""
        src = _read(_RBF_CPP)
        # Sink literal still present.
        self.assertIn("static thread_local short s_outEncSink", src,
            "thread_local sink must be retained for DG-edge "
            "protection (test_m_b24a1_schema.py guard).")

    # ----- audit + i18n revert -----

    def test_PERMANENT_o_addendum_b4_restored_to_complete(self):
        src = _read(_ADDENDUM)
        b4_lines = [ln for ln in src.splitlines()
                    if "B4" in ln and u"输入 Quat" in ln]
        self.assertTrue(b4_lines)
        for ln in b4_lines:
            self.assertNotIn("⚠️ partial", ln,
                "B4 row must no longer say partial -- backend "
                "now landed for Quat + ExpMap.")
            self.assertIn("complete", ln,
                "B4 row must declare 'complete' status (Quat + "
                "ExpMap; BendRoll / SwingTwist deferred).")

    def test_PERMANENT_p_addendum_audit_history_present(self):
        src = _read(_ADDENDUM)
        # Both the downgrade and the restore must be cited so the
        # audit trail reads as a single linear history.
        self.assertIn("M_P0_QUATERNION_HONEST_DISCLOSURE", src)
        self.assertIn("M_P0_QUATERNION_BACKEND_LAND", src)

    def test_PERMANENT_q_i18n_combo_tip_no_longer_warns_quat(self):
        """The honest-disclosure warning text targeted Quat / ExpMap;
        now that those backends ship, the EN tooltip must no longer
        claim 'no effect' for them. BendRoll / SwingTwist remain
        forward-compat and may keep their own warning text."""
        src = _read(_I18N)
        # The exact disclosure phrase
        # ('Selecting non-Euler currently has no effect') was the
        # honest-disclosure marker; it must be gone in EN.
        self.assertNotIn(
            "Selecting non-Euler currently has no effect", src,
            "Honest-disclosure 'no effect' phrase must be removed "
            "from i18n.py once the Quat + ExpMap backends ship.")


if __name__ == "__main__":
    unittest.main()
