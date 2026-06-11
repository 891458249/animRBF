# -*- coding: utf-8 -*-
"""T_M_P0_KERNEL_SWITCH_ROLLBACK_PARITY (2026-05-11) PERMANENT guard

Defends the M_P0_KERNEL_SWITCH_ROLLBACK chain (方案 E, 4 commits):

  c924b1c  ROLLBACK_1  TPS r<=0 -> value (revert M_P0_KERNEL_ALGO_AUDIT TPS)
  91adfc9  ROLLBACK_2  remove lambda retry loop (revert M_P0_AUTO_ADAPTIVE_LAMBDA
                                                      + M_P0_LAMBDA_CEIL_TIGHTEN)
  7e6c25f  ROLLBACK_5  dual .mll deploy (183,296 B parity)
  (this)   ROLLBACK_6  docs + this guard + diag rename

Per Planner-mandated 6 assertion list (see docs/排查/
M_P0_KERNEL_SWITCH_ROLLBACK_index.md §6). Three negatives + three
positives:

  Negative (must be GONE post-rollback):
    A. retry constants `LAMBDA_FLOOR` / `LAMBDA_CEIL` / `MAX_RETRIES`
       absent from RBFtools.cpp
    B. (covered by ROLLBACK_2's class-level skip; defended here from
       the rollback-parity angle as well)

  Positive (must be PRESENT post-rollback):
    C. TPS branch `else result = value;` in interpolateRbf
    D. 5 prev-trackers (M_P0_TRAINING_AFFECTING_ATTRS) preserved as UX
    E. controller `_TRAINING_AFFECTING_ATTRS` frozenset preserved
    F. cpp schema `regularization` setDefault `1.0e-8` preserved
    G. Multi-quat / B1 QWA / B2 nlerp / poses I/O identifiers preserved

If any of A-G regresses, this test fires and the rollback chain
is incomplete or has been silently re-introduced.

Source-level guards only (no Maya runtime). Phase 5 user-driven
behavioural validation lives in
`modules/RBFtools/tests/scratch/diag_kernel_rollback.py`.
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
_CONTROLLER_PY = os.path.join(
    _REPO, "modules", "RBFtools", "scripts", "RBFtools",
    "controller.py")


def _read(path):
    with io.open(path, "r", encoding="utf-8") as fh:
        return fh.read()


class TestKernelRollbackParity(unittest.TestCase):
    """Six Planner-mandated assertions for ROLLBACK chain integrity."""

    # ----- A. retry constants must be GONE -----

    def test_PERMANENT_a_retry_constants_removed(self):
        """ROLLBACK_2 (91adfc9) removed the M_P0_AUTO_ADAPTIVE_LAMBDA
        constants LAMBDA_FLOOR / LAMBDA_CEIL / MAX_RETRIES.

        M_P0_BOUNDED_LAMBDA_RETRY_FLOOR_1E5 (2026-05-11) re-introduced
        bounded retry under NEW names LAMBDA_CEIL_FLOOR_1E5 and
        MAX_RETRIES_FLOOR_1E5. The new names are distinct identifiers
        — substring matching `LAMBDA_CEIL` in `LAMBDA_CEIL_FLOOR_1E5`
        would create a false positive here. Use exact identifier
        matching via regex word boundaries to preserve the ROLLBACK_2
        intent (old constants gone) while accommodating the new
        bounded-retry constants.
        """
        cpp = _read(_RBF_CPP)
        for sym in ("LAMBDA_FLOOR", "LAMBDA_CEIL", "MAX_RETRIES"):
            # Exact-identifier match: `\bSYM\b` does NOT match the
            # longer SYM_FLOOR_1E5 form.
            pattern = re.compile(r"\b" + re.escape(sym) + r"\b")
            # Strip out comment lines so audit-history mentions stay
            # readable in source.
            live_lines = [ln for ln in cpp.splitlines()
                          if pattern.search(ln)
                          and not ln.lstrip().startswith("//")
                          and not ln.lstrip().startswith("*")]
            self.assertEqual(
                live_lines, [],
                "Retry constant {!r} (exact-identifier) must be "
                "removed from active RBFtools.cpp source "
                "(M_P0_KERNEL_SWITCH_ROLLBACK_2; the new bounded-"
                "retry uses LAMBDA_CEIL_FLOOR_1E5 / "
                "MAX_RETRIES_FLOOR_1E5 instead). Found in "
                "lines: {!r}".format(sym, live_lines))

    def test_PERMANENT_a2_retry_loop_keyword_removed(self):
        """The `for (int retry = ` outer-loop construct is the most
        unambiguous ROLLBACK_2 fingerprint. It must not exist in any
        live cpp statement."""
        cpp = _read(_RBF_CPP)
        live_lines = [ln for ln in cpp.splitlines()
                      if "for (int retry = " in ln
                      and not ln.lstrip().startswith("//")]
        self.assertEqual(live_lines, [],
            "Retry outer loop must be removed "
            "(M_P0_KERNEL_SWITCH_ROLLBACK_2). Found: {!r}".format(
                live_lines))

    # ----- C. TPS oracle branch must be PRESENT -----

    def test_PERMANENT_c_tps_oracle_branch_present(self):
        """TPS r <= 0 must return `value` (oracle behaviour) post
        ROLLBACK_1, not `0.0` (M_P0_KERNEL_ALGO_AUDIT historical)."""
        cpp = _read(_RBF_CPP)
        m = re.search(
            r"//\s*thin\s+plate[\s\S]{0,2000}?else\s*\n?\s*result\s*=\s*([^;]+);",
            cpp)
        self.assertIsNotNone(m,
            "TPS else-branch not located in interpolateRbf.")
        else_value = m.group(1).strip()
        self.assertEqual(
            else_value, "value",
            "TPS r <= 0 branch must assign `value` (oracle behaviour, "
            "M_P0_KERNEL_SWITCH_ROLLBACK_1, anchored to e249ec0). "
            "Found: {!r}".format(else_value))

    # ----- D. 5 prev-trackers must REMAIN (UX preservation) -----

    def test_PERMANENT_d_five_prev_trackers_preserved(self):
        """ROLLBACK chain explicitly keeps M_P0_TRAINING_AFFECTING_ATTRS
        prev-trackers as UX enhancement (auto-retrain on attr edit).
        Removing them = ROLLBACK_3 which the user decided NOT to do."""
        h = _read(_RBF_H)
        cpp = _read(_RBF_CPP)
        for tracker in ("prevKernelVal",
                        "prevDistanceTypeVal",
                        "prevRadiusTypeVal",
                        "prevRadiusVal",
                        "prevRegularizationVal"):
            self.assertIn(
                tracker, h,
                "Prev-tracker {!r} must remain declared in "
                "RBFtools.h (M_P0_TRAINING_AFFECTING_ATTRS preserved "
                "per方案 E).".format(tracker))
            self.assertIn(
                tracker, cpp,
                "Prev-tracker {!r} must remain initialised + read in "
                "RBFtools.cpp.".format(tracker))

    # ----- E. controller _TRAINING_AFFECTING_ATTRS frozenset must REMAIN -----

    def test_PERMANENT_e_controller_frozenset_preserved(self):
        """ROLLBACK chain explicitly keeps M_P0_TRAINING_ATTRS_FORCE_RETRAIN
        Python frozenset + evaluate=0/1 toggle (ROLLBACK_4 NOT done)."""
        ctrl = _read(_CONTROLLER_PY)
        self.assertIn(
            "_TRAINING_AFFECTING_ATTRS", ctrl,
            "_TRAINING_AFFECTING_ATTRS frozenset must remain in "
            "controller.py (M_P0_TRAINING_ATTRS_FORCE_RETRAIN "
            "preserved per方案 E).")
        # The frozenset must contain "kernel" (the headline trigger).
        m = re.search(
            r"_TRAINING_AFFECTING_ATTRS\s*=\s*frozenset\(\{([^}]+)\}\)",
            ctrl, re.DOTALL)
        self.assertIsNotNone(m,
            "_TRAINING_AFFECTING_ATTRS must be defined as a frozenset "
            "literal.")
        members = m.group(1)
        self.assertIn(
            '"kernel"', members,
            "_TRAINING_AFFECTING_ATTRS must include 'kernel' (headline "
            "training-affecting attr).")

    # ----- F. cpp schema lambda default 1.0e-8 must REMAIN -----

    def test_PERMANENT_f_lambda_default_1e_5(self):
        """cpp schema `regularization` setDefault.

        Originally guarded the oracle anchor 1e-8. The
        M_P0_BOUNDED_LAMBDA_RETRY_FLOOR_1E5 patch (2026-05-11)
        bumped the schema default to 1e-5 based on user λ-sweep
        showing redundant production rigs (22 poses × 9-dim Raw)
        need λ ≥ 1e-5 for well-posed K across all 6 kernels. The
        new default aligns with the bounded-retry ceil so new
        nodes start at a well-posed state and the retry loop never
        has to escalate on freshly-created rigs.

        Guard now accepts either:
          * 1.0e-5 (post M_P0_BOUNDED_LAMBDA_RETRY_FLOOR_1E5)
          * 1.0e-8 (oracle / pre-bounded-retry historical)
        so the test stays meaningful as a "schema-default exists"
        shape check while accommodating the planner-decided default
        bump. Other defaults (e.g. 1.0e-3, 0.0) would fail and
        signal an unintended schema drift.
        """
        cpp = _read(_RBF_CPP)
        m = re.search(
            r"regularization\s*=\s*nAttr\.create\([^)]*\)[\s\S]{0,1200}?"
            r"nAttr\.setDefault\(\s*(1\.0e-?5|1\.0e-?8)\s*\)",
            cpp)
        self.assertIsNotNone(m,
            "cpp schema must keep nAttr.setDefault(1.0e-5) for "
            "regularization (M_P0_BOUNDED_LAMBDA_RETRY_FLOOR_1E5) "
            "or the historical 1.0e-8 oracle anchor. Drift to any "
            "other value would regress the kernel-switch / bounded-"
            "retry guarantees.")

    # ----- G. preserved-feature identifiers sanity -----

    def test_PERMANENT_g_preserved_features_present(self):
        """Quick sanity scan: identifiers from the M_P0_KERNEL_SWITCH_ROLLBACK
        explicit "保留功能" list must still exist somewhere in the tree.
        Catches accidental wholesale revert that would wipe multi-quat
        / poses I/O / etc. along with the rollback."""
        cpp = _read(_RBF_CPP)
        ctrl = _read(_CONTROLLER_PY)
        # Multi-driver quat (ROLLBACK 不动)
        self.assertIn(
            "encodeEulerToQuaternion", cpp,
            "encodeEulerToQuaternion (multi-driver quat input) must "
            "remain in cpp — ROLLBACK chain does not touch this.")
        # B1 QWA Power Iteration
        self.assertIn(
            "powerIterationMaxEigenvec4x4", cpp,
            "powerIterationMaxEigenvec4x4 (B1 QWA) must remain.")
        # B2 nlerp
        self.assertIn(
            "nlerpQuaternions", cpp,
            "nlerpQuaternions (B2 output blend) must remain.")
        # decodeQuaternionToEuler / decodeExpMapToEuler
        self.assertIn(
            "decodeQuaternionToEuler", cpp,
            "decodeQuaternionToEuler (B2 inverse transform) must "
            "remain.")
        self.assertIn(
            "decodeExpMapToEuler", cpp,
            "decodeExpMapToEuler (B2 ExpMap inverse) must remain.")
        # poses I/O entry point in controller
        self.assertTrue(
            "import_poses_from_path" in ctrl
            or "export_poses_to_path" in ctrl,
            "poses I/O entry points (M_P0_POSES_IO) must remain in "
            "controller.")

    # ----- Landing-tag presence: at least one anchor per commit -----

    def test_PERMANENT_h_rollback_anchors_present(self):
        """Each ROLLBACK_<n> tag must appear at least once in source
        so a future grep-anchored audit traces the chain."""
        cpp = _read(_RBF_CPP)
        self.assertIn(
            "M_P0_KERNEL_SWITCH_ROLLBACK_1", cpp,
            "M_P0_KERNEL_SWITCH_ROLLBACK_1 anchor missing from cpp "
            "(should appear in TPS branch comment).")
        self.assertIn(
            "M_P0_KERNEL_SWITCH_ROLLBACK_2", cpp,
            "M_P0_KERNEL_SWITCH_ROLLBACK_2 anchor missing from cpp "
            "(should appear in solver block comment + displayError).")


if __name__ == "__main__":
    unittest.main()
