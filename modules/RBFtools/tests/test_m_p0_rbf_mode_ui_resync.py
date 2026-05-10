# -*- coding: utf-8 -*-
"""T_M_P0_RBF_MODE_UI_RESYNC — defend the authoritative rbfMode UI
resync from main_window._on_settings_loaded.

Bug context (M_P0_RBF_MODE_UI_RESYNC, 2026-05-10):
  After clicking Apply the rbf_section visually showed "矩阵 RBF"
  while ``shape.rbfMode`` was actually 0 (Generic). Empirical trace
  via Maya scriptJob attributeChange confirmed the node attr never
  flipped to 1; the desync lived purely in the view layer because
  ``blockSignals`` on _rbf_section during ``_on_settings_loaded``
  suppressed the combo's currentIndexChanged signal cascade — and
  load()'s explicit ``_update_mode_visibility(currentIndex())`` at
  line 450 of rbf_section.py runs on a combo that may not yet
  reflect the just-loaded data when block-signal interactions with
  Qt's per-emitter blocking semantics interact with implicit
  default-state combo construction.

  User-facing impact: false-positive "rbfMode flipped to Matrix"
  bug report; multiple debugging rounds (planner Round 1-4) chased
  a phantom Matrix-mode mis-flip that was actually a UI desync.

Fix: rbf_section now exposes ``force_mode_visibility(idx)`` — a
public, signal-suppressed combo+visibility resync from an authoritative
node-attr value. main_window._on_settings_loaded calls it AFTER all
section.load() runs so rbfMode visibility tracks shape.rbfMode as
single source of truth, regardless of blockSignals interactions.

This test pins the source-level invariant: AST scan of both files
asserts the resync path exists and is called from settingsLoaded.
"""
from __future__ import absolute_import, division, print_function

import io
import os
import re
import unittest


_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(os.path.dirname(_HERE)))
_MAIN_WINDOW = os.path.join(_REPO, "modules", "RBFtools", "scripts",
                             "RBFtools", "ui", "main_window.py")
_RBF_SECTION = os.path.join(_REPO, "modules", "RBFtools", "scripts",
                             "RBFtools", "ui", "widgets",
                             "rbf_section.py")


def _read(path):
    with io.open(path, "r", encoding="utf-8") as fh:
        return fh.read()


class TestRBFModeUIResync(unittest.TestCase):

    def test_PERMANENT_a_force_mode_visibility_method_defined(self):
        """rbf_section must expose force_mode_visibility(idx) public."""
        src = _read(_RBF_SECTION)
        self.assertRegex(src,
            r"def\s+force_mode_visibility\s*\(\s*self\s*,\s*idx\s*\)\s*:",
            "rbf_section must define force_mode_visibility(self, idx) "
            "as the authoritative resync entry point.")

    def test_PERMANENT_b_force_mode_visibility_signal_suppressed(self):
        """Combo write inside force_mode_visibility must be signal-blocked."""
        src = _read(_RBF_SECTION)
        m = re.search(
            r"def\s+force_mode_visibility[\s\S]+?(?=\n\s{0,4}def\s)", src)
        self.assertIsNotNone(m,
            "force_mode_visibility function body not found.")
        body = m.group(0)
        self.assertIn("blockSignals(True)", body,
            "force_mode_visibility must blockSignals around the combo "
            "setCurrentIndex to avoid a round-trip "
            "attributeChanged.emit -> controller.set_attribute write "
            "(the value is already on the node).")
        self.assertIn("setCurrentIndex(idx)", body,
            "force_mode_visibility must setCurrentIndex(idx) on _cmb_mode.")
        self.assertIn("_update_mode_visibility(idx)", body,
            "force_mode_visibility must call _update_mode_visibility(idx) "
            "after the combo write to refresh frame setVisible state.")

    def test_PERMANENT_c_settings_loaded_calls_force_mode_visibility(self):
        """main_window._on_settings_loaded must call force_mode_visibility."""
        src = _read(_MAIN_WINDOW)
        m = re.search(
            r"def\s+_on_settings_loaded\b[\s\S]+?(?=\n\s{0,4}def\s)", src)
        self.assertIsNotNone(m,
            "main_window._on_settings_loaded function body not found.")
        body = m.group(0)
        self.assertIn("force_mode_visibility", body,
            "_on_settings_loaded must call self._rbf_section."
            "force_mode_visibility(...) after load() to authoritatively "
            "resync rbfMode UI state from the node attr value.")
        # Source argument must be data["rbfMode"], NOT combo state — the
        # whole point of the fix is that combo state can drift.
        self.assertRegex(body,
            r'force_mode_visibility\s*\(\s*\n?\s*int\s*\(\s*data\s*\.\s*get\s*\(\s*"rbfMode"',
            "force_mode_visibility argument must be int(data.get('rbfMode', 0)) "
            "— the node-attr value carried in the settings dict, not the "
            "combo state (which is what the bug was caused by).")

    def test_PERMANENT_d_settings_loaded_resync_after_load(self):
        """Resync must run AFTER all section.load() calls, not before."""
        src = _read(_MAIN_WINDOW)
        m = re.search(
            r"def\s+_on_settings_loaded\b[\s\S]+?(?=\n\s{0,4}def\s)", src)
        body = m.group(0)
        load_pos = body.rfind("self._rbf_section.load(data)")
        resync_pos = body.find("force_mode_visibility")
        self.assertGreater(load_pos, 0,
            "Could not locate self._rbf_section.load(data) anchor.")
        self.assertGreater(resync_pos, load_pos,
            "force_mode_visibility must be called AFTER "
            "self._rbf_section.load(data) — calling it before would "
            "be overwritten by load()'s own _update_mode_visibility "
            "at the end of load().")

    def test_PERMANENT_e_landing_tag_in_comment(self):
        """Source-level landing tag for traceability."""
        src = _read(_MAIN_WINDOW)
        self.assertIn("M_P0_RBF_MODE_UI_RESYNC", src,
            "main_window must mark the fix with M_P0_RBF_MODE_UI_RESYNC "
            "for traceability via git blame / git log -G.")
        src2 = _read(_RBF_SECTION)
        self.assertIn("M_P0_RBF_MODE_UI_RESYNC", src2,
            "rbf_section must mark force_mode_visibility with "
            "M_P0_RBF_MODE_UI_RESYNC.")


if __name__ == "__main__":
    unittest.main()
