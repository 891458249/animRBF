# -*- coding: utf-8 -*-
"""T_M_P0_DUPLICATE_POSE_DETECT (2026-05-01) PERMANENT guard

Validates the Python-layer pose-input dedup pre-check that
``controller.apply_poses`` performs before delegating to the C++
RBF kernel. Background:

* User report — switching kernel to Multi-Quadratic Biharmonic on a
  21-pose node triggered ``MS::kFailure`` ("RBF decomposition failed").
* Root cause — Pose 6 and Pose 8 had bit-identical input vectors,
  making the kernel matrix ``K`` singular. Gaussian / IMQ kernels
  mask via lambda regularization; MQB / IMQB cannot.
* Fix — ``core._detect_duplicate_pose_inputs`` flags the offending
  pairs, ``controller.apply_poses`` surfaces them through the existing
  ``ask_confirm`` dialog so the user can fix the data instead of
  bisecting 21 poses against an opaque C++ error.
"""
from __future__ import absolute_import, division, print_function

import ast
import os
import sys
import unittest

# Make the package importable when running this test stand-alone (the
# project conftest already does this for the full sweep, but stand-alone
# invocation through ``python -m unittest`` should still work).
_HERE = os.path.dirname(os.path.abspath(__file__))
_SCRIPTS = os.path.join(os.path.dirname(_HERE), "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from RBFtools import core  # noqa: E402


class _PoseStub(object):
    """Minimal duck-type stand-in for ``ui.pose_model.Pose``.

    Only ``inputs`` is exercised by the detector; ``values`` is kept
    for symmetry with the real class.
    """

    __slots__ = ("inputs", "values")

    def __init__(self, inputs, values=None):
        self.inputs = list(inputs)
        self.values = list(values or [])


class TestDuplicatePoseDetect(unittest.TestCase):
    """Direct tests against ``core._detect_duplicate_pose_inputs``."""

    def test_PERMANENT_a_unique_inputs_no_duplicates(self):
        poses = [_PoseStub([1.0, 2.0, 3.0]),
                 _PoseStub([4.0, 5.0, 6.0]),
                 _PoseStub([7.0, 8.0, 9.0])]
        self.assertEqual(core._detect_duplicate_pose_inputs(poses), [])

    def test_PERMANENT_b_exact_duplicate_at_indices_1_3(self):
        same = [1.0, 2.0, 3.0]
        poses = [_PoseStub([0.0, 0.0, 0.0]),
                 _PoseStub(same),
                 _PoseStub([4.0, 4.0, 4.0]),
                 _PoseStub(list(same))]
        self.assertEqual(
            core._detect_duplicate_pose_inputs(poses), [(1, 3)])

    def test_PERMANENT_c_within_tolerance_5e8_treated_as_duplicate(self):
        poses = [_PoseStub([1.0, 2.0]),
                 _PoseStub([1.0 + 5e-8, 2.0 - 5e-8])]
        self.assertEqual(
            core._detect_duplicate_pose_inputs(poses), [(0, 1)])

    def test_PERMANENT_d_outside_tolerance_1e6_not_duplicate(self):
        poses = [_PoseStub([1.0, 2.0]),
                 _PoseStub([1.0 + 1e-6, 2.0])]
        self.assertEqual(core._detect_duplicate_pose_inputs(poses), [])

    def test_PERMANENT_e_input_length_mismatch_skip(self):
        poses = [_PoseStub([1.0, 2.0, 3.0]),
                 _PoseStub([1.0, 2.0])]
        self.assertEqual(core._detect_duplicate_pose_inputs(poses), [])

    def test_PERMANENT_f_multiple_duplicate_pairs(self):
        poses = [_PoseStub([1.0]), _PoseStub([1.0]),
                 _PoseStub([2.0]), _PoseStub([2.0])]
        self.assertEqual(
            core._detect_duplicate_pose_inputs(poses), [(0, 1), (2, 3)])

    def test_PERMANENT_g_user_reported_index_6_8_scenario(self):
        """Mirrors the field report — 21 poses, two with identical
        sub-microradian rotation deltas."""
        poses = [_PoseStub([float(i), 0.0, 0.0]) for i in range(21)]
        same = [2.03389e-06, -1.60774e-06, -9.13287e-07]
        poses[6] = _PoseStub(list(same))
        poses[8] = _PoseStub(list(same))
        result = core._detect_duplicate_pose_inputs(poses)
        self.assertIn((6, 8), result)

    def test_PERMANENT_h_empty_list(self):
        self.assertEqual(core._detect_duplicate_pose_inputs([]), [])

    def test_PERMANENT_i_single_pose(self):
        self.assertEqual(
            core._detect_duplicate_pose_inputs([_PoseStub([1.0])]), [])

    def test_PERMANENT_j_helper_exists_in_core(self):
        self.assertTrue(callable(
            getattr(core, "_detect_duplicate_pose_inputs", None)))

    def test_PERMANENT_k_ast_apply_poses_calls_detector(self):
        """AST guard — controller.apply_poses must call the detector
        before delegating to ``core.apply_poses``. Defends against a
        future refactor silently dropping the pre-check."""
        path = os.path.join(_SCRIPTS, "RBFtools", "controller.py")
        # Explicit utf-8 — Windows Python 3 defaults to cp936 / gbk
        # which chokes on the file's non-ASCII comments.
        import io
        with io.open(path, "r", encoding="utf-8") as fh:
            src = fh.read()
        tree = ast.parse(src)
        found = False
        for node in ast.walk(tree):
            if (isinstance(node, ast.FunctionDef)
                    and node.name == "apply_poses"):
                for sub in ast.walk(node):
                    if (isinstance(sub, ast.Call)
                            and isinstance(sub.func, ast.Attribute)
                            and sub.func.attr
                            == "_detect_duplicate_pose_inputs"):
                        found = True
                        break
        self.assertTrue(
            found,
            "apply_poses must call _detect_duplicate_pose_inputs "
            "before core.apply_poses (M_P0_DUPLICATE_POSE_DETECT)")


if __name__ == "__main__":
    unittest.main()
