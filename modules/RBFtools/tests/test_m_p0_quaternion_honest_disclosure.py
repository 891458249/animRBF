# -*- coding: utf-8 -*-
"""T_M_P0_QUATERNION_HONEST_DISCLOSURE (2026-05-10) PERMANENT guard

Pins the audit-trail / UI honest-disclosure changes that ship with
``M_P0_QUATERNION_HONEST_DISCLOSURE``. Background:

* Step-1 audit found the ``outputEncoding`` backend inverse
  transform was never implemented -- the C++ code at
  ``RBFtools.cpp:4063-4071`` is a ``thread_local`` placeholder, but
  the addendum speed-table row 4114 had already been marked
  "complete (full)" by the M_B24b2 commit.
* Per-source ``driverSource_encoding`` is metadata-only; ``compute()``
  reads the node-level ``inputEncoding``, so the per-row UI combo
  was a silent no-op.
* This commit ships the honest-disclosure half: addendum audit
  correction + i18n tooltip rewrites + per-source combo disabled.
  The backend land lives in M_P0_QUATERNION_BACKEND_LAND.

The guards below defend each surface so a future refactor cannot
silently re-introduce the misleading state.
"""
from __future__ import absolute_import, division, print_function

import ast
import io
import os
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(os.path.dirname(_HERE)))
_SCRIPTS = os.path.join(os.path.dirname(_HERE), "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

_ADDENDUM = os.path.join(
    _REPO, "docs", u"设计文档",
    "RBFtools_v5_addendum_20260424.md")
_I18N = os.path.join(_SCRIPTS, "RBFtools", "ui", "i18n.py")
_DSLE = os.path.join(
    _SCRIPTS, "RBFtools", "ui", "widgets",
    "driver_source_list_editor.py")
_PARITY_TEST = os.path.join(
    _HERE, "test_v5_parity_b2_b4.py")


def _read(path):
    with io.open(path, "r", encoding="utf-8") as fh:
        return fh.read()


class TestQuaternionHonestDisclosure(unittest.TestCase):

    def test_PERMANENT_a_addendum_b4_row_no_longer_claims_full(self):
        """Row 4114 must not claim the original 'complete (full)' marker
        — that text was the M_B24b2 overstatement that
        M_P0_QUATERNION_HONEST_DISCLOSURE corrected. Backend land
        (M_P0_QUATERNION_BACKEND_LAND) restored the row to
        'complete (Quat + ExpMap; BendRoll / SwingTwist deferred)',
        which is honest about the partial-encoding scope. The earlier
        'partial' assertion that lived here was superseded by
        T_M_P0_QUATERNION_BACKEND_LAND test_PERMANENT_o once the
        Quat / ExpMap halves shipped."""
        src = _read(_ADDENDUM)
        b4_lines = [ln for ln in src.splitlines()
                    if "B4" in ln and u"输入 Quat" in ln]
        self.assertTrue(b4_lines,
            "B4 row not found in addendum speed table")
        for ln in b4_lines:
            self.assertNotIn("complete (full)", ln,
                "Audit drift: B4 row must never re-claim "
                "'complete (full)' -- the BendRoll / SwingTwist "
                "halves are still deferred.")
            # Either of the post-disclosure markers is acceptable:
            #   "partial"   -- disclosure phase, backend not landed
            #   "complete"  -- backend land phase, Quat + ExpMap shipped
            # Both flow through the audit-history paragraph; what we
            # really pin is the absence of the misleading 'full'.
            self.assertTrue(
                ("partial" in ln) or ("complete" in ln),
                "B4 row must declare its honest status "
                "(partial during disclosure phase, complete after "
                "backend land).")

    def test_PERMANENT_b_audit_correction_paragraph_present(self):
        src = _read(_ADDENDUM)
        self.assertIn("M_P0_QUATERNION_HONEST_DISCLOSURE", src,
            "Audit correction paragraph missing from addendum.")
        self.assertIn("M_P0_QUATERNION_BACKEND_LAND", src,
            "Forward pointer to backend land subtask missing.")

    def test_PERMANENT_c_i18n_output_tooltip_says_forward_compat(self):
        """EN + ZH output_encoding_combo_tip must contain the
        forward-compat marker so Maya users see the warning."""
        src = _read(_I18N)
        # Two distinct dict literal blocks (EN + ZH); the marker must
        # appear at least twice.
        en_zh_hits = src.count("forward-compat")
        self.assertGreaterEqual(en_zh_hits, 2,
            "i18n.py must contain 'forward-compat' in both EN+ZH "
            "output_encoding_combo_tip values "
            "(found {} hits).".format(en_zh_hits))

    def test_PERMANENT_d_i18n_has_source_encoding_disabled_tip(self):
        src = _read(_I18N)
        # Key must appear in both EN and ZH dicts, so >= 2 hits.
        self.assertGreaterEqual(
            src.count("source_encoding_disabled_tip"), 2,
            "source_encoding_disabled_tip key missing from EN or ZH "
            "i18n dict.")

    def test_PERMANENT_e_per_source_combo_disabled(self):
        """AST guard: ``_combo_enc.setEnabled(False)`` must appear
        in the row widget so the per-source combo is non-interactive."""
        src = _read(_DSLE)
        tree = ast.parse(src)
        found = False
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "setEnabled"
                    and isinstance(node.func.value, ast.Attribute)
                    and node.func.value.attr == "_combo_enc"
                    and len(node.args) == 1
                    and isinstance(node.args[0], ast.Constant)
                    and node.args[0].value is False):
                found = True
                break
        self.assertTrue(found,
            "_combo_enc.setEnabled(False) call missing from "
            "driver_source_list_editor.py "
            "(M_P0_QUATERNION_HONEST_DISCLOSURE).")

    def test_PERMANENT_f_per_source_combo_uses_disabled_tooltip(self):
        """The per-source combo must show the disabled-tooltip key,
        not the legacy 'driver_source_encoding_tip' (which described
        an interactive widget). Both render-time and retranslate
        paths must agree."""
        src = _read(_DSLE)
        # Disabled tip appears in two places: combo creation +
        # _row_retranslate. Legacy interactive tip should be gone.
        self.assertGreaterEqual(
            src.count("source_encoding_disabled_tip"), 2,
            "source_encoding_disabled_tip must be set in both "
            "combo creation and _row_retranslate.")
        self.assertNotIn(
            'tr("driver_source_encoding_tip")', src,
            "Legacy interactive tooltip key must not be referenced "
            "after the combo is disabled.")

    def test_PERMANENT_g_parity_b4_test_carries_deferred_note(self):
        """The schema-only #30 test must carry an explicit NOTE so
        future readers do not mistake schema land for backend land."""
        src = _read(_PARITY_TEST)
        self.assertIn(
            "M_P0_QUATERNION_HONEST_DISCLOSURE", src,
            "test_v5_parity_b2_b4.py docstring missing the disclosure "
            "anchor.")
        self.assertIn("deferred", src,
            "Disclosure NOTE must mark backend behavior as deferred.")


if __name__ == "__main__":
    unittest.main()
