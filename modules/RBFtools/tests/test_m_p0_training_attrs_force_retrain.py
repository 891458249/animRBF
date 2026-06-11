# -*- coding: utf-8 -*-
"""T_M_P0_TRAINING_ATTRS_FORCE_RETRAIN — defend the Python-layer
belt-and-suspenders retrain trigger in controller.set_attribute.

Bug context (M_P0_TRAINING_ATTRS_FORCE_RETRAIN, 2026-05-11):
  User reports kernel switch (Gaussian 1 → MQB) still causes
  visible driven joint drift even with the M_P0_TRAINING_AFFECTING_ATTRS
  C++ auto-retrain fix in place. Possible causes:

    (a) The C++ prev-tracker logic IS correct but the user's
        installed .mll predates the fix.
    (b) DG dirty propagation race / plug coalescing prevents the
        prev-tracker from seeing the change.
    (c) Parallel eval (Maya 2025 EM) makes the per-node prev
        tracker non-thread-safe.

Defense: every controller.set_attribute call that touches a
training-affecting attr ALSO toggles ``shape.evaluate`` 0 → 1
after the value write. This unconditionally triggers the C++
training block on the next compute(), regardless of whether the
prev-tracker fires. Belt-and-suspenders pattern.

Training-affecting attrs (must trigger retrain):
  - kernel           : K[i,j] = φ(d, σ) shape
  - distanceType     : d(p_i, p_j) metric
  - inputEncoding    : encoded pose vector dimension/content
  - radius           : σ in φ(d, σ) for Custom radiusType
  - radiusType       : which σ source (mean / median / custom)
  - regularization   : λI diagonal injection
  - allowNegativeWeights : affects matValues sign treatment
  - rbfMode          : Generic vs Matrix path divergence
"""
from __future__ import absolute_import, division, print_function

import io
import os
import re
import unittest


_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(os.path.dirname(_HERE)))
_CONTROLLER = os.path.join(_REPO, "modules", "RBFtools", "scripts",
                            "RBFtools", "controller.py")


def _read(path):
    with io.open(path, "r", encoding="utf-8") as fh:
        return fh.read()


class TestTrainingAttrsForceRetrain(unittest.TestCase):

    def test_PERMANENT_a_training_attrs_set_present(self):
        """Controller defines _TRAINING_AFFECTING_ATTRS frozenset."""
        src = _read(_CONTROLLER)
        self.assertRegex(src,
            r"_TRAINING_AFFECTING_ATTRS\s*=\s*frozenset\s*\(\s*\{",
            "controller must define _TRAINING_AFFECTING_ATTRS as a "
            "frozenset for fast membership testing in set_attribute.")

    def test_PERMANENT_b_training_attrs_includes_all_required(self):
        """Frozenset must include every training-affecting attr."""
        src = _read(_CONTROLLER)
        m = re.search(
            r"_TRAINING_AFFECTING_ATTRS\s*=\s*frozenset\s*\(\s*\{"
            r"([\s\S]+?)\}\s*\)", src)
        self.assertIsNotNone(m,
            "Could not locate _TRAINING_AFFECTING_ATTRS body.")
        body = m.group(1)
        required = ("kernel", "distanceType", "inputEncoding",
                    "radius", "radiusType", "regularization",
                    "allowNegativeWeights", "rbfMode")
        for attr in required:
            self.assertIn('"{}"'.format(attr), body,
                "_TRAINING_AFFECTING_ATTRS must include {!r} — its "
                "change requires wMat retrain.".format(attr))

    def test_PERMANENT_c_set_attribute_triggers_evaluate_toggle(self):
        """set_attribute must toggle evaluate=0/1 after writing a "
        "training-affecting attr."""
        src = _read(_CONTROLLER)
        m = re.search(
            r"def\s+set_attribute\b[\s\S]+?(?=\n\s{0,4}def\s)", src)
        self.assertIsNotNone(m, "set_attribute body not found.")
        body = m.group(0)
        self.assertIn("_TRAINING_AFFECTING_ATTRS", body,
            "set_attribute must check membership in "
            "_TRAINING_AFFECTING_ATTRS to decide whether to force "
            "retrain.")
        self.assertRegex(body,
            r'cmds\.setAttr\([^)]*\.evaluate[^)]*,\s*0\s*\)',
            "set_attribute must call cmds.setAttr(<shape>.evaluate, 0) "
            "as part of the retrain toggle.")
        self.assertRegex(body,
            r'cmds\.setAttr\([^)]*\.evaluate[^)]*,\s*1\s*\)',
            "set_attribute must call cmds.setAttr(<shape>.evaluate, 1) "
            "to complete the retrain toggle.")

    def test_PERMANENT_d_force_retrain_is_post_write(self):
        """evaluate toggle must come AFTER the attr write, not before."""
        src = _read(_CONTROLLER)
        m = re.search(
            r"def\s+set_attribute\b[\s\S]+?(?=\n\s{0,4}def\s)", src)
        body = m.group(0)
        # Find the attr write anchor.
        idx_write = body.find("core.set_node_attr(self._current_node, attr, value)")
        idx_eval0 = body.find('"\\.evaluate"')
        # The .evaluate setAttr should appear AFTER the attr write.
        # Use the simpler anchor (just locate ".evaluate" substring).
        idx_dot_evaluate = body.find(".evaluate")
        self.assertGreater(idx_write, 0,
            "core.set_node_attr write anchor missing.")
        self.assertGreater(idx_dot_evaluate, idx_write,
            "The .evaluate toggle MUST come after the attr write — "
            "otherwise the toggle fires before the value is applied "
            "and the retrain reads stale data.")

    def test_PERMANENT_e_force_retrain_guarded_by_membership(self):
        """The evaluate toggle must be inside `if attr in <set>:`."""
        src = _read(_CONTROLLER)
        m = re.search(
            r"def\s+set_attribute\b[\s\S]+?(?=\n\s{0,4}def\s)", src)
        body = m.group(0)
        self.assertRegex(body,
            r"if\s+attr\s+in\s+self\._TRAINING_AFFECTING_ATTRS\s*:",
            "The evaluate toggle must be guarded by "
            "`if attr in self._TRAINING_AFFECTING_ATTRS:` so it "
            "fires ONLY for training-affecting attrs — other attrs "
            "(color, drawing flags) should not pay the retrain cost.")

    def test_PERMANENT_f_landing_tag_present(self):
        src = _read(_CONTROLLER)
        n = src.count("M_P0_TRAINING_ATTRS_FORCE_RETRAIN")
        self.assertGreaterEqual(n, 2,
            "controller.py must reference "
            "M_P0_TRAINING_ATTRS_FORCE_RETRAIN at least 2x for "
            "traceability (frozenset definition + set_attribute "
            "comment).")


if __name__ == "__main__":
    unittest.main()
