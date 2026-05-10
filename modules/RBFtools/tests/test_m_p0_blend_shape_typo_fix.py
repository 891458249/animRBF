# -*- coding: utf-8 -*-
"""T_M_P0_BLEND_SHAPE_TYPO_FIX (2026-05-10) PERMANENT guard

``capture_per_pose_local_transforms`` (core.py:3356) called
``is_blend_shape`` with a stray underscore; the real definition
(core.py:4763) is ``is_blendshape`` with no underscore. Apply
on any driven node walked into a NameError -- Python's own
"Did you mean: 'is_blendshape'?" suggestion located the typo.

Pin the corrected spelling so a future refactor cannot silently
re-introduce the typo at either the call site or the docstring.
"""
from __future__ import absolute_import, division, print_function

import ast
import io
import os
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_SCRIPTS = os.path.join(os.path.dirname(_HERE), "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

_CORE = os.path.join(_SCRIPTS, "RBFtools", "core.py")


def _read(path):
    with io.open(path, "r", encoding="utf-8") as fh:
        return fh.read()


class TestBlendShapeTypoFix(unittest.TestCase):

    def test_PERMANENT_a_no_typo_call_in_ast(self):
        """No `ast.Call` whose callee is the bare name `is_blend_shape`."""
        tree = ast.parse(_read(_CORE))
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == "is_blend_shape"):
                self.fail(
                    "core.py contains a call to the non-existent "
                    "is_blend_shape (should be is_blendshape).")

    def test_PERMANENT_b_no_typo_literal_anywhere(self):
        """No occurrence of the typo literal anywhere in core.py
        (defends docstrings + comments + strings too)."""
        self.assertNotIn(
            "is_blend_shape", _read(_CORE),
            "core.py must not carry the typo 'is_blend_shape' "
            "anywhere -- the canonical name is 'is_blendshape'.")

    def test_PERMANENT_c_real_function_still_present(self):
        from RBFtools import core
        self.assertTrue(callable(getattr(core, "is_blendshape", None)),
            "is_blendshape must remain importable + callable.")

    def test_PERMANENT_d_capture_helper_imports_clean(self):
        """``capture_per_pose_local_transforms`` -- the function whose
        body called the typo -- must import without raising."""
        from RBFtools import core
        self.assertTrue(callable(getattr(
            core, "capture_per_pose_local_transforms", None)),
            "capture_per_pose_local_transforms must be importable; "
            "a recurrence of the typo would surface here as soon as "
            "the function body referenced the bad name.")


if __name__ == "__main__":
    unittest.main()
