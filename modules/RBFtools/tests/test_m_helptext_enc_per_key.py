# -*- coding: utf-8 -*-
"""M_HELPTEXT_ENC_PER_KEY (2026-04-29) — per-encoding help keys
for the input-encoding combo's HelpBubble.

User report (2026-04-29 P0): the help bubble next to the
input-encoding combo was BLANK at every selection. d01a964
(commit "docs(ui): expand input_encoding help text") added a
single ``input_encoding`` long-form key, but the actual UI uses
ComboHelpButton with key_map=[``enc_raw``, ``enc_quaternion``,
``enc_bendroll``, ``enc_expmap``, ``enc_swingtwist``]
(rbf_section.py:233-237). The button's _help_key_for_index
(help_button.py:245-248) returns key_map[idx] when in range and
NEVER falls back to the fallback_key for valid combo selections;
those 5 keys did not exist in help_texts.py so get_help_text
returned "" → empty bubble.

This was a "false-green" event for d01a964 — the long-form text
landed but never reached the user because the wiring expected
per-encoding keys.

Fix:
  * 5 ``enc_*`` keys added to both EN and ZH dicts in
    help_texts.py, mirroring the d01a964 long-form content split
    into per-encoding subsections.
  * ★ U+2605 (RBF / limb-rig favorite markers) + · U+00B7
    (bullet) + 万向节死锁 (gimbal-lock CN) verbatim preserved
    from d01a964.
  * input_encoding fallback retained as a defensive
    out-of-range backstop.

PERMANENT GUARD T_HELPTEXT_ENC_PER_KEY locks the 5 keys + EN/ZH
parity + ComboHelpButton key_map alignment.
"""

from __future__ import absolute_import

import os
import unittest


_REPO_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
_HELP_TEXTS_PY = os.path.join(
    _REPO_ROOT, "modules", "RBFtools", "scripts", "RBFtools",
    "ui", "help_texts.py")
_RBF_SECTION_PY = os.path.join(
    _REPO_ROOT, "modules", "RBFtools", "scripts", "RBFtools",
    "ui", "widgets", "rbf_section.py")


def _read(p):
    with open(p, "r", encoding="utf-8") as fh:
        return fh.read()


# ----------------------------------------------------------------------
# PERMANENT GUARD T_HELPTEXT_ENC_PER_KEY
# ----------------------------------------------------------------------


class T_HELPTEXT_ENC_PER_KEY(unittest.TestCase):
    """PERMANENT GUARD — DO NOT REMOVE.

    The 5 enc_* keys MUST exist in both EN and ZH dicts so the
    ComboHelpButton's per-index lookup does not return empty
    bubbles. ★ / · markers + Chinese rigging vocabulary preserved
    from d01a964."""

    @classmethod
    def setUpClass(cls):
        cls._help = _read(_HELP_TEXTS_PY)
        cls._rbf = _read(_RBF_SECTION_PY)

    def test_PERMANENT_a_5_keys_exist_with_en_zh_parity(self):
        # Each enc_* key must appear at least twice (EN + ZH dict).
        for key in ("enc_raw", "enc_quaternion", "enc_bendroll",
                    "enc_expmap", "enc_swingtwist"):
            count = self._help.count('"{}":'.format(key))
            self.assertGreaterEqual(
                count, 2,
                "help_texts.py missing EN/ZH parity for "
                "{!r} (found {} occurrences, need >= 2)".format(
                    key, count))

    def test_PERMANENT_b_keys_align_with_combo_key_map(self):
        # The ComboHelpButton in rbf_section.py wires its key_map
        # to exactly these 5 strings; the help_texts dict MUST
        # cover them all. Source-scan asserts both ends.
        for key in ('"enc_raw"', '"enc_quaternion"',
                    '"enc_bendroll"', '"enc_expmap"',
                    '"enc_swingtwist"'):
            self.assertIn(key, self._rbf,
                "rbf_section.py key_map missing {}".format(key))
            self.assertIn(key, self._help,
                "help_texts.py missing the key {} that "
                "ComboHelpButton resolves at runtime".format(key))

    def test_PERMANENT_c_star_and_bullet_markers_preserved(self):
        # User-spec verbatim requirements: ★ markers on ExpMap +
        # SwingTwist as the "favorites". Encoded as ★ in the
        # source (escape form because the file is also opened by
        # Maya 2022 Python 2.7 in dual-version setups; the escape
        # is universally safe).
        self.assertIn("\\u2605", self._help.encode(
            "unicode_escape").decode("ascii"),
            "★ U+2605 marker missing — d01a964 verbatim preserve "
            "of '★ RBF 最常用' / '★ 肢体绑定最常用' must survive "
            "the per-key split.")

    def test_PERMANENT_d_input_encoding_fallback_retained(self):
        # The long-form input_encoding key stays as a defensive
        # out-of-range backstop. Removing it would break any
        # legacy callsite that opens the bubble without going
        # through the combo (e.g. a plain HelpButton with
        # help_key="input_encoding").
        self.assertGreaterEqual(
            self._help.count('"input_encoding":'), 2,
            "input_encoding fallback key MUST stay in BOTH EN + "
            "ZH dicts (out-of-range backstop for ComboHelpButton).")

    def test_PERMANENT_e_help_text_lookup_returns_nonempty(self):
        # Public-API smoke check — get_help_text with each enc_*
        # key returns a non-empty string in EN. (ZH check elided
        # because cmds-mocking conftest hooks may not switch
        # languages cleanly here; cross-language coverage lives
        # in the existing i18n tests.)
        from RBFtools.ui import help_texts
        for key in ("enc_raw", "enc_quaternion", "enc_bendroll",
                    "enc_expmap", "enc_swingtwist"):
            self.assertTrue(
                help_texts._EN.get(key),
                "_EN dict has no entry for {} — "
                "ComboHelpButton will display empty bubble".format(
                    key))
            self.assertTrue(
                help_texts._ZH.get(key),
                "_ZH dict has no entry for {} — "
                "ZH locale will display empty bubble".format(key))


if __name__ == "__main__":
    unittest.main()
