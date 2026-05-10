# -*- coding: utf-8 -*-
"""T_M_P0_REST_POSE_TOL_LOOSEN — defend the looser tolerance for
rest-pose detection in capture_output_baselines.

Bug context (M_P0_REST_POSE_TOL_LOOSEN, 2026-05-11):
  User reported "基础pose就带了数值" — driven joints show non-zero
  positions even when pose 0 (rest pose) values were explicitly
  set to 0, 0, 0 (translate), 0, 0, 0 (rotate), 1, 1, 1 (scale).

  Root cause: capture_output_baselines uses
  ``float_eq(v, 0.0)`` with the global FLOAT_ABS_TOL = 1e-6 to
  detect whether pose 0 is the rest pose. But Maya's channel-box
  getAttr/setAttr roundtrip introduces float noise in the 1e-5
  to 1e-6 range; joint-orient bake adds 1e-4 noise; unitConversion
  on rotation channels (radian ↔ degree) adds more noise. The
  user's pose 0 driver inputs landed at 2.95e-06 / -5.37e-05 /
  -1.37e-06 / 0.24037 — clearly meant to be rest but failing the
  1e-6 tolerance.

  When the rest-pose check fails, baseline falls back to current
  scene state at Apply time. If the rig's joints aren't EXACTLY
  at world origin (which they rarely are — joints have bind-pose
  offsets), the baseline carries those offsets, and the RBF
  output at rest = baseline = non-zero joint position, instead
  of the user's intended 0,0,0.

Fix: use ``abs(v) < 1e-3`` instead of float_eq with the global
1e-6. 1e-3 radians = 0.057° — visually identical to rest pose,
and far above any plausible noise level. Intentional small
rotations (e.g. 1° = 0.0175 rad) are still flagged as non-rest
(0.0175 ≫ 1e-3).

This test pins the tolerance value + the absolute-value check.
"""
from __future__ import absolute_import, division, print_function

import io
import os
import re
import unittest


_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(os.path.dirname(_HERE)))
_CORE = os.path.join(_REPO, "modules", "RBFtools", "scripts",
                     "RBFtools", "core.py")


def _read(path):
    with io.open(path, "r", encoding="utf-8") as fh:
        return fh.read()


class TestRestPoseTolLoosen(unittest.TestCase):

    def test_PERMANENT_a_tol_constant_defined(self):
        """REST_POSE_INPUT_TOL constant must equal 1e-3."""
        src = _read(_CORE)
        self.assertRegex(src,
            r"REST_POSE_INPUT_TOL\s*=\s*1\.0e-3",
            "capture_output_baselines must declare "
            "REST_POSE_INPUT_TOL = 1.0e-3 (0.057° in radians) for "
            "rest-pose detection — looser than the global "
            "FLOAT_ABS_TOL=1e-6 to accommodate Maya channel-box "
            "and joint-orient float noise.")

    def test_PERMANENT_b_uses_abs_v_lt_tol(self):
        """Rest detection must use abs(v) < tol, not float_eq."""
        src = _read(_CORE)
        m = re.search(
            r"def\s+capture_output_baselines[\s\S]+?(?=\ndef\s|\nclass\s)",
            src)
        self.assertIsNotNone(m, "capture_output_baselines not found.")
        body = m.group(0)
        # Must use the new abs(v) < REST_POSE_INPUT_TOL pattern
        self.assertRegex(body,
            r"abs\s*\(\s*v\s*\)\s*<\s*REST_POSE_INPUT_TOL",
            "Rest-pose detection must use abs(v) < "
            "REST_POSE_INPUT_TOL instead of the legacy "
            "float_eq(v, 0.0) check. The legacy check used "
            "FLOAT_ABS_TOL=1e-6 which is too tight for Maya "
            "channel-box noise.")
        # Must NOT use the legacy float_eq(v, 0.0) here anymore.
        # (Other call sites in core.py may legitimately still use
        # float_eq with a different intent — only check this
        # function body.)
        self.assertNotRegex(body,
            r"float_eq\s*\(\s*v\s*,\s*0\.0\s*\)",
            "capture_output_baselines must no longer use "
            "float_eq(v, 0.0) for rest-pose detection (was the "
            "root cause of the user-reported repro).")

    def test_PERMANENT_c_landing_tag_in_comment(self):
        """Landing tag for git-blame traceability."""
        src = _read(_CORE)
        self.assertIn("M_P0_REST_POSE_TOL_LOOSEN", src,
            "core.py must reference M_P0_REST_POSE_TOL_LOOSEN at "
            "the fix site (capture_output_baselines body).")

    def test_PERMANENT_d_tolerance_documented(self):
        """The chosen tolerance value's rationale must be commented."""
        src = _read(_CORE)
        m = re.search(
            r"def\s+capture_output_baselines[\s\S]+?(?=\ndef\s|\nclass\s)",
            src)
        body = m.group(0)
        # Look for radian / degree mention in the docstring or
        # comment block — readers must know WHY 1e-3 is the right
        # value.
        self.assertRegex(body,
            r"(0\.057|0\.057°|0\.0175|1°|rad)",
            "The tolerance comment must explain the "
            "radian-to-degree conversion (1e-3 rad ≈ 0.057°) so "
            "future readers understand why this specific value.")


if __name__ == "__main__":
    unittest.main()
