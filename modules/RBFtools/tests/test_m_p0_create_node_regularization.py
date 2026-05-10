# -*- coding: utf-8 -*-
"""T_M_P0_CREATE_NODE_REGULARIZATION — defend the rigging-friendly
regularization default (1e-3) on freshly-created nodes.

Bug context (M_P0_CREATE_NODE_REGULARIZATION, 2026-05-10):
  C++ schema default at cpp:532 is 1e-8, following Chad Vernon's
  reference solver. That target audience is sparse, well-
  distributed pose sets. Production rigging workflows (face /
  muscle / corrective) routinely have HIGHLY redundant pose sets
  — multiple poses sharing identical (or near-identical) driver
  blocks for several drivers. Under 1e-8 the K matrix becomes
  numerically singular → both Cholesky probe and GE fallback
  fail → "RBF decomposition failed" → driver does not drive
  driven, with no obvious fix path for the TD beyond "go set
  regularization to 1e-3 manually".

  Empirically: a 20-pose × 3-driver Quat-encoded shoulder rig
  failed solve with regularization=1e-8 (the schema default);
  bumping to 1e-2 produced output[0] = 2.168604, +30deg driver
  motion → output[0] = 1.578010 (driver successfully driving).
  1e-3 sits at the conservative end of the production rigging
  working range. (Earlier attempt: 1e-4 — proved insufficient
  when inputEncoding switched from Quat to ExpMap; the 9-dim
  Euclidean distance offers less numerical separation than 12-
  dim per-block quat chord distance for redundant pose sets.)

Fix: ``core.create_node`` now writes regularization=1e-3 right
after the ``.type=1`` write. Also bump the Python UI fallback
(both ``get_all_settings`` and ``rbf_section.load``) to mirror,
so corrupt-scene / missing-attr paths don't read 1e-8 either.
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
_RBF_SECTION = os.path.join(_REPO, "modules", "RBFtools", "scripts",
                             "RBFtools", "ui", "widgets",
                             "rbf_section.py")


def _read(path):
    with io.open(path, "r", encoding="utf-8") as fh:
        return fh.read()


class TestCreateNodeRegularization(unittest.TestCase):

    def test_PERMANENT_a_create_node_writes_regularization(self):
        """create_node body must write regularization=1e-3."""
        src = _read(_CORE)
        m = re.search(
            r"def\s+create_node\s*\(\s*\)[\s\S]+?(?=\n(?:def |class )\b)",
            src)
        self.assertIsNotNone(m, "create_node function body not found.")
        body = m.group(0)
        # Body contains nested calls (get_shape(transform)) so an
        # exclusive [^)]* regex breaks at the first inner paren.
        # Use literal substring + value check instead.
        self.assertIn('".regularization"', body,
            "create_node must reference '.regularization' literal.")
        self.assertIn("1.0e-3", body,
            "create_node must write the 1.0e-3 default literal.")
        # Cross-check: the regularization line must be inside a setAttr.
        self.assertRegex(body,
            r'cmds\.setAttr[\s\S]{0,200}?\.regularization[\s\S]{0,40}?1\.0e-3',
            "regularization=1e-3 must be written via cmds.setAttr "
            "(not just appear as a comment / docstring literal).")

    def test_PERMANENT_b_get_all_settings_fallback_default(self):
        """get_all_settings fallback default for regularization is 1e-4."""
        src = _read(_CORE)
        m = re.search(
            r'"regularization":\s*g\([^,]+,\s*([0-9.eE+-]+)\)', src)
        self.assertIsNotNone(m,
            "get_all_settings regularization line not found.")
        default_val = float(m.group(1))
        self.assertEqual(default_val, 1.0e-3,
            "get_all_settings fallback default for regularization "
            "must be 1e-4 (rigging-friendly), not 1e-8 (Chad Vernon "
            "reference target).")

    def test_PERMANENT_c_rbf_section_load_fallback_default(self):
        """rbf_section.load fallback default for regularization is 1e-4."""
        src = _read(_RBF_SECTION)
        m = re.search(
            r'self\._spn_reg\.setValue\(\s*data\.get\(\s*"regularization"\s*,\s*([0-9.eE+-]+)\s*\)',
            src)
        self.assertIsNotNone(m,
            "rbf_section.load regularization fallback line not found.")
        default_val = float(m.group(1))
        self.assertEqual(default_val, 1.0e-3,
            "rbf_section.load fallback default for regularization "
            "must be 1e-4 to mirror the create-time write.")

    def test_PERMANENT_d_landing_tag_in_comment(self):
        """Landing tag for traceability."""
        src = _read(_CORE)
        n = src.count("M_P0_CREATE_NODE_REGULARIZATION")
        self.assertGreaterEqual(n, 2,
            "core.py must reference M_P0_CREATE_NODE_REGULARIZATION "
            "at both write sites (create_node + get_all_settings).")
        src2 = _read(_RBF_SECTION)
        self.assertIn("M_P0_CREATE_NODE_REGULARIZATION", src2,
            "rbf_section.py must mark the fallback default change "
            "with M_P0_CREATE_NODE_REGULARIZATION.")


if __name__ == "__main__":
    unittest.main()
