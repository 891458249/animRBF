# -*- coding: utf-8 -*-
"""M_HELPBUBBLE_BATCH (2026-04-29) — red-frame area HelpButton coverage.

User report (2026-04-29): the red-frame screenshot covers Output
Encoding / RBF Pose Editor outer 3-tab / Driver Sources / Driven
Targets / Utility / Tools sections — every interactive widget had
zero HelpButton coverage. Per spec decisions D.1 (full coverage) +
E.1 (3-5 line bubble with function + usage + edge cases) + F.1
(EN+ZH parity), this milestone wires HelpButton instances next to:

  * Output Encoding combo (main_window output_encoding section)
  * Outer 3-tab corner widget (DriverDriven / BaseDrivenPose / Pose)
  * TabbedSourceEditor 4 widgets × 2 panels (driver / driven):
      Connect / Disconnect / Add / Batch checkbox
  * Utility section: Split RBFSolver, Cleanup modes overview,
    Remove Unnecessary Datas
  * Tools section: Refresh Profile (ProfileWidget)

12 new help-text keys land in BOTH _EN and _ZH dicts. The keys are
DISTINCT from existing ``*_tip`` setToolTip strings — those carry
single-line hover text per M_UIPOLISH paradigm; HelpButton bubbles
carry the longer 3-5-line description per E.1.

PERMANENT GUARD T_HELPTEXT_REDFRAME_COVERAGE locks:
  1. Each widget file references HelpButton + the right key.
  2. EN/ZH parity for the 12 new keys.
  3. Help text non-empty in both languages (false-green prevention
     mirroring the d01a964 ComboHelpButton key_map lesson).
"""

from __future__ import absolute_import

import os
import unittest

import conftest


_REPO_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
_HELP_TEXTS_PY = os.path.join(
    _REPO_ROOT, "modules", "RBFtools", "scripts", "RBFtools",
    "ui", "help_texts.py")
_MAIN_WINDOW_PY = os.path.join(
    _REPO_ROOT, "modules", "RBFtools", "scripts", "RBFtools",
    "ui", "main_window.py")
_TABBED_SE_PY = os.path.join(
    _REPO_ROOT, "modules", "RBFtools", "scripts", "RBFtools",
    "ui", "widgets", "tabbed_source_editor.py")
_PROFILE_PY = os.path.join(
    _REPO_ROOT, "modules", "RBFtools", "scripts", "RBFtools",
    "ui", "widgets", "profile_widget.py")


# 12 new help-text keys covering the red-frame area.
_NEW_KEYS = (
    "output_encoding",
    "outer_tabs_overview",
    "source_tab_connect",
    "source_tab_disconnect",
    "source_tab_add_driver",
    "source_tab_add_driven",
    "source_tab_batch_driver",
    "source_tab_batch_driven",
    "btn_split_solver_per_joint",
    "cleanup_modes_overview",
    "btn_remove_unnecessary_datas",
    "btn_refresh_profile",
)


def _read(p):
    with open(p, "r", encoding="utf-8") as fh:
        return fh.read()


# ----------------------------------------------------------------------
# PERMANENT GUARD T_HELPTEXT_REDFRAME_COVERAGE
# ----------------------------------------------------------------------


class T_HELPTEXT_REDFRAME_COVERAGE(unittest.TestCase):
    """PERMANENT GUARD — DO NOT REMOVE.

    Locks the wiring chain from each red-frame widget through the
    HelpButton constructor to the help_texts dict, in both
    languages."""

    @classmethod
    def setUpClass(cls):
        cls._help = _read(_HELP_TEXTS_PY)
        cls._mw = _read(_MAIN_WINDOW_PY)
        cls._tse = _read(_TABBED_SE_PY)
        cls._pw = _read(_PROFILE_PY)

    def test_PERMANENT_a_en_zh_parity_for_new_keys(self):
        # Each new key must appear at least twice (EN dict + ZH dict).
        for key in _NEW_KEYS:
            count = self._help.count('"{}":'.format(key))
            self.assertGreaterEqual(
                count, 2,
                "help_texts.py missing EN/ZH parity for {!r} "
                "(found {} occurrences, need >= 2)".format(
                    key, count))

    def test_PERMANENT_b_help_text_lookup_returns_nonempty(self):
        # Mirror of M_HELPTEXT_ENC_PER_KEY false-green guard:
        # source-scan key existence is necessary but not sufficient;
        # the dict entries must actually map to non-empty strings.
        from RBFtools.ui import help_texts
        for key in _NEW_KEYS:
            self.assertTrue(
                help_texts._EN.get(key),
                "_EN[{!r}] empty/missing — HelpButton would "
                "display blank bubble.".format(key))
            self.assertTrue(
                help_texts._ZH.get(key),
                "_ZH[{!r}] empty/missing — ZH locale would "
                "display blank bubble.".format(key))

    def test_PERMANENT_c_main_window_helpbuttons(self):
        # Output Encoding combo's HelpButton, the outer-tabs corner
        # widget, and the Utility section's three HelpButtons must
        # reference the canonical keys.
        for key in ("output_encoding",
                    "outer_tabs_overview",
                    "btn_split_solver_per_joint",
                    "cleanup_modes_overview",
                    "btn_remove_unnecessary_datas"):
            self.assertIn(
                'HelpButton("{}")'.format(key), self._mw,
                "main_window.py missing HelpButton({!r}) — "
                "red-frame coverage incomplete.".format(key))

    def test_PERMANENT_d_main_window_outer_tabs_corner(self):
        # The corner widget MUST attach to QtCore.Qt.TopRightCorner
        # so the HelpButton appears next to the tab bar (not inside
        # tab content where it would scroll away).
        self.assertIn("setCornerWidget(", self._mw,
            "_outer_tabs.setCornerWidget call missing — corner "
            "HelpButton would have no host.")
        self.assertIn("TopRightCorner", self._mw,
            "Corner placement MUST be TopRightCorner so the help "
            "bubble surfaces next to the tab labels.")

    def test_PERMANENT_e_tabbed_source_editor_keys(self):
        # The base class declares the 4 help_key class attrs that
        # subclasses override for driver/driven variants.
        for sym in ("_connect_help_key",
                    "_disconnect_help_key",
                    "_add_help_key",
                    "_batch_help_key"):
            self.assertIn(sym, self._tse,
                "tabbed_source_editor missing class-attr "
                "{} — per-button help wiring broken.".format(sym))
        # Base class default (driver) values.
        for key in ("source_tab_connect",
                    "source_tab_disconnect",
                    "source_tab_add_driver",
                    "source_tab_batch_driver"):
            self.assertIn('"{}"'.format(key), self._tse,
                "tabbed_source_editor missing key {!r} — "
                "driver-side HelpButton broken.".format(key))
        # Driven-side overrides MUST appear too.
        for key in ("source_tab_add_driven",
                    "source_tab_batch_driven"):
            self.assertIn('"{}"'.format(key), self._tse,
                "tabbed_source_editor missing key {!r} — "
                "driven-side HelpButton broken.".format(key))
        # 4 HelpButton constructions in the panel _build.
        self.assertGreaterEqual(
            self._tse.count("HelpButton("), 4,
            "tabbed_source_editor expected >=4 HelpButton "
            "constructions (Connect / Disconnect / Add / Batch).")

    def test_PERMANENT_f_profile_widget_help(self):
        self.assertIn(
            'HelpButton("btn_refresh_profile")', self._pw,
            "profile_widget missing HelpButton(btn_refresh_profile)"
            " — Tools section coverage incomplete.")

    def test_PERMANENT_g_all_keys_distinct_from_tip_keys(self):
        # Spec hardening 5: do NOT collide with existing setToolTip
        # `_tip` keys (M_UIPOLISH paradigm). The bubble keys above
        # must NOT be the same identifiers used for setToolTip.
        for key in _NEW_KEYS:
            self.assertFalse(
                key.endswith("_tip"),
                "HelpButton key {!r} ends with _tip; would alias "
                "an existing setToolTip i18n key.".format(key))


# ----------------------------------------------------------------------
# Mock E2E — runtime HelpButton -> bubble text resolution
# ----------------------------------------------------------------------


@unittest.skipIf(conftest._REAL_MAYA,
    "mock-dependent (PySide minimal shim)")
class TestM_HELPBUBBLE_BATCH_LookupResolution(unittest.TestCase):
    """Catch the d01a964 false-green class of bug: source-scan saw
    the key, runtime lookup returned empty.

    HelpButton's text-resolve path goes through ``get_help_text`` —
    asserting the function returns non-empty text for each new key
    proves the click->bubble chain delivers user-visible content.
    """

    def test_get_help_text_resolves_each_new_key(self):
        from RBFtools.ui.help_texts import get_help_text
        for key in _NEW_KEYS:
            text = get_help_text(key)
            self.assertTrue(
                text and len(text) > 30,
                "get_help_text({!r}) returned empty / too short "
                "({!r}) — HelpButton click would render a blank "
                "or near-blank bubble.".format(key, text))

    def test_each_key_describes_3_to_5_concept_lines(self):
        # Decision E.1 spec: each bubble carries function + usage +
        # edge cases (~3-5 lines). Looser proxy: each key's EN
        # text contains at least one explicit "\n\n" paragraph
        # break so bubble formatting is multi-paragraph.
        from RBFtools.ui.help_texts import _EN
        for key in _NEW_KEYS:
            self.assertIn(
                "\n\n", _EN[key],
                "_EN[{!r}] has no paragraph break — spec E.1 "
                "calls for multi-section content.".format(key))


if __name__ == "__main__":
    unittest.main()
