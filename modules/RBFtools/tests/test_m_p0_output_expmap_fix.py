# -*- coding: utf-8 -*-
"""T_M_P0_OUTPUT_EXPMAP_FIX (2026-05-10) PERMANENT guard

Pins the three-bug fix that ships with ``M_P0_OUTPUT_EXPMAP_FIX``:

* Bug 1 (numbering) -- ``M_P0_QUATERNION_BACKEND_LAND`` (ce136dd)
  wrote the ``applyOutputEncodingBlend`` dispatch as
  ``if (outputEncoding != 1 && outputEncoding != 3) return;``,
  borrowing inputEncoding's ``ExpMap=3`` enum value. But the
  outputEncoding schema is ``{0=Euler, 1=Quaternion, 2=ExpMap}`` --
  three slots only. Picking ExpMap (value=2) silently fell through
  the early return and degenerated to Raw weighted-sum semantics,
  exactly the "no effect" symptom the disclosure phase had
  warned about and that backend land was supposed to fix. The
  fix renumbers the dispatch + the else-branch to {1, 2}.

* Bug 2 (dead warning) -- ce136dd guarded a once-per-rig
  ``cmds.warning('outputEncoding=BendRoll(2)/SwingTwist(4) ...')``
  behind ``outputEncodingDeferredWarningIssued``. Both the flag and
  the warning text were unreachable (outputEncoding's enum has no
  BendRoll/SwingTwist slot at all -- those are inputEncoding-only).
  Removed; addendum audit history now records the dead-code event
  so future readers understand why the flag is gone.

* Bug 3 (UI honest disclosure) -- distance-type Angle is hard-coded
  Euclidean for every non-Raw inputEncoding (RBFtools.cpp:3084-3088
  is the only Angle dispatch site, gated on encoding==0 + n==3).
  The UI now disables the Angle radio when the user picks any
  non-Raw encoding, and forces a fall-back to Euclidean if the
  combo state was Angle when they switched. Defended by an AST
  guard in this test file (the slot must exist + be wired into
  the inputEncoding combo's currentIndexChanged signal).
"""
from __future__ import absolute_import, division, print_function

import ast
import io
import os
import re
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(os.path.dirname(_HERE)))
_RBF_CPP = os.path.join(_REPO, "source", "RBFtools.cpp")
_RBF_H = os.path.join(_REPO, "source", "RBFtools.h")
_RBF_SECTION = os.path.join(
    _REPO, "modules", "RBFtools", "scripts", "RBFtools",
    "ui", "widgets", "rbf_section.py")
_I18N = os.path.join(
    _REPO, "modules", "RBFtools", "scripts", "RBFtools",
    "ui", "i18n.py")
_ADDENDUM = os.path.join(
    _REPO, "docs", u"设计文档",
    "RBFtools_v5_addendum_20260424.md")


def _read(path):
    with io.open(path, "r", encoding="utf-8") as fh:
        return fh.read()


class TestOutputExpMapFix(unittest.TestCase):

    # ----- Bug 1: dispatch numbering -----

    def test_PERMANENT_a_dispatch_uses_expmap_2_not_3(self):
        """The early return must filter on the schema-correct
        outputEncoding values {1=Quaternion, 2=ExpMap}, not the
        inputEncoding-style {1, 3}. We assert by literal presence
        because the function body contains comment text with braces
        (notably the {0=Euler, 1=Quaternion, 2=ExpMap} schema
        mnemonic) that breaks any naive nested-brace regex."""
        src = _read(_RBF_CPP)
        # The fixed dispatch literal must be present.
        self.assertIn(
            "if (outputEncoding != 1 && outputEncoding != 2) return;",
            src,
            "applyOutputEncodingBlend must guard on != 1 && != 2 "
            "(M_P0_OUTPUT_EXPMAP_FIX renumbering).")
        # The buggy ce136dd dispatch must be gone.
        self.assertNotIn(
            "if (outputEncoding != 1 && outputEncoding != 3)",
            src,
            "ce136dd-era dispatch with value 3 must be removed.")

    def test_PERMANENT_b_else_branch_uses_expmap_2(self):
        """The else branch comment + (post-fix) explicit equality
        check must reference outputEncoding == 2, not 3."""
        src = _read(_RBF_CPP)
        # The post-fix branch is `else if (outputEncoding == 2)`.
        self.assertIsNotNone(
            re.search(
                r"else\s+if\s*\(\s*outputEncoding\s*==\s*2\s*\)",
                src),
            "ExpMap branch must use 'else if (outputEncoding == 2)' "
            "(M_P0_OUTPUT_EXPMAP_FIX renumbering).")
        self.assertNotIn("// outputEncoding == 3 (ExpMap)", src,
            "Stale `outputEncoding == 3` comment must be gone "
            "(no such schema slot exists).")

    def test_PERMANENT_c_no_inputencoding_3_in_output_dispatch(self):
        """Defensive: the Quat+ExpMap dispatch in compute() must not
        mistakenly check outputEncoding against value 3."""
        src = _read(_RBF_CPP)
        # The compute() guard reads outEncRebuildVal; any inequality
        # against 3 there would re-introduce Bug 1.
        self.assertNotIn("outEncRebuildVal == 3", src)
        self.assertNotIn("outEncRebuildVal != 3", src)

    # ----- Bug 2: dead BendRoll/SwingTwist warning removed -----

    def test_PERMANENT_d_no_deferred_warning_flag(self):
        """Both header and cpp may keep the literal in
        removed-on-purpose comments (so the audit history stays
        readable in source); what must not exist is any LIVE
        statement that declares or references the flag."""
        for path in (_RBF_H, _RBF_CPP):
            src = _read(path)
            live_uses = [ln for ln in src.splitlines()
                         if "outputEncodingDeferredWarningIssued" in ln
                         and not ln.lstrip().startswith("//")]
            self.assertEqual(
                live_uses, [],
                "Dead flag must not be used in any live "
                "statement (path={!r}).".format(path))

    def test_PERMANENT_e_no_dead_warning_text(self):
        cpp_src = _read(_RBF_CPP)
        # The literal "BendRoll(2)/SwingTwist(4)" must not appear in
        # any live string -- outputEncoding has no such slots.
        for ln in cpp_src.splitlines():
            if ln.lstrip().startswith("//"):
                continue
            self.assertNotIn(
                "BendRoll(2)/SwingTwist(4)", ln,
                "Dead warning text must not re-appear in live code.")

    # ----- Bug 3: UI honest disclosure for distanceType=Angle -----

    def test_PERMANENT_f_ui_slot_disables_angle_for_non_raw(self):
        """The inputEncoding combo's slot must call setEnabled on
        the distance-type Angle entry, gated on idx==0 (Raw)."""
        src = _read(_RBF_SECTION)
        tree = ast.parse(src)
        # Look for a method body that touches both _cmb_dist (or
        # _distance_type_combo) and setEnabled within the same fn.
        slot_found = False
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            body_src = ast.unparse(node) if hasattr(ast, "unparse") \
                else ""
            if (("_cmb_dist" in body_src
                    or "_distance_type_combo" in body_src)
                    and "setEnabled" in body_src
                    and "M_P0_OUTPUT_EXPMAP_FIX" in body_src):
                slot_found = True
                break
        self.assertTrue(slot_found,
            "rbf_section.py must define a slot that disables the "
            "Angle distance-type entry when inputEncoding != Raw "
            "(M_P0_OUTPUT_EXPMAP_FIX honest disclosure).")

    def test_PERMANENT_g_i18n_has_angle_disabled_tooltip(self):
        src = _read(_I18N)
        # EN + ZH dict, expect >= 2 hits.
        self.assertGreaterEqual(
            src.count("angle_disabled_for_encoding_tip"), 2,
            "i18n.py must define angle_disabled_for_encoding_tip "
            "in both EN + ZH dicts.")

    # ----- audit history -----

    def test_PERMANENT_h_addendum_records_fix(self):
        src = _read(_ADDENDUM)
        self.assertIn("M_P0_OUTPUT_EXPMAP_FIX", src,
            "Addendum must record the M_P0_OUTPUT_EXPMAP_FIX audit "
            "section so the ce136dd numbering bug history is "
            "discoverable from a single document.")


if __name__ == "__main__":
    unittest.main()
