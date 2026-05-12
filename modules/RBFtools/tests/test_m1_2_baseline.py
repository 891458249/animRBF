"""M1.2 — Output Base Value + outputIsScale spec tests.

Validates the Python reference mirror of the C++ baseline pipeline
(subtract before solve → re-add after inference). Also covers the
capture-priority contract and the runtime dirty-tracker that trips
``evalInput = true`` when the baseline spec mutates at runtime.
"""

from __future__ import annotations

import random
import unittest

import numpy as np

from _reference_impl import (
    BaselineDirtyTracker,
    capture_output_baselines_pure,
    is_scale_attr,
    readd_baseline,
    resolve_anchor,
    subtract_baseline,
)


class T1_IsScaleAttr(unittest.TestCase):

    def test_long_names(self):
        for name in ("scaleX", "scaleY", "scaleZ"):
            self.assertTrue(is_scale_attr(name), name)

    def test_short_names(self):
        for name in ("sx", "sy", "sz"):
            self.assertTrue(is_scale_attr(name), name)

    def test_non_scale(self):
        for name in ("translateX", "tx", "rotateY", "ry",
                     "visibility", "v", "", "scale"):
            self.assertFalse(is_scale_attr(name), name)


class T2_SubtractReaddIdentity(unittest.TestCase):
    """For any invertible K, `K · solve(K, Y - b) + b == Y` to fp noise."""

    def _round_trip(self, K, Y, base_values, is_scale_flags):
        Y_shifted = subtract_baseline(Y, base_values, is_scale_flags)
        W = np.linalg.solve(K, Y_shifted)
        delta = K @ W
        recovered = readd_baseline(delta, base_values, is_scale_flags)
        return recovered

    def test_diagonal_dominant_random(self):
        rng = np.random.default_rng(0xC0FFEE)
        for trial in range(40):
            N = rng.integers(3, 8)
            M = rng.integers(1, 5)
            K = rng.standard_normal((N, N))
            K = K @ K.T + N * np.eye(N)
            Y = rng.standard_normal((N, M)) * 3.0
            base_values = rng.standard_normal(M).tolist()
            is_scale_flags = [bool(rng.integers(0, 2)) for _ in range(M)]
            recovered = self._round_trip(K, Y, base_values, is_scale_flags)
            err = float(np.max(np.abs(recovered - Y)))
            self.assertLess(err, 1e-10,
                            msg="trial {}: max|recovered - Y|={}".format(trial, err))

    def test_identity_kernel(self):
        Y = np.array([[0.5, 2.0], [1.3, -0.7], [-0.2, 0.1]])
        base_values = [0.3, 0.0]
        is_scale_flags = [False, True]
        K = np.eye(3)
        recovered = self._round_trip(K, Y, base_values, is_scale_flags)
        np.testing.assert_allclose(recovered, Y, atol=1e-12)


class T3_ScaleChannelProtection(unittest.TestCase):
    """Scale channel anchor is 1.0 regardless of base_value or scene value."""

    def test_resolve_anchor_scale_ignores_base(self):
        # Even if base_value is 0 (pathological scene) or -999, scale → 1.0.
        self.assertEqual(resolve_anchor(0.0,    True), 1.0)
        self.assertEqual(resolve_anchor(-999.0, True), 1.0)
        self.assertEqual(resolve_anchor(7.5,    True), 1.0)

    def test_resolve_anchor_non_scale_uses_base(self):
        self.assertEqual(resolve_anchor(0.0,  False), 0.0)
        self.assertEqual(resolve_anchor(3.14, False), 3.14)

    def test_capture_scene_scale_is_zero_still_yields_1(self):
        # Worst-case: user clicks Apply while driven scale is transiently 0.
        baselines = capture_output_baselines_pure(
            driven_attrs=["scaleX", "scaleY", "scaleZ"],
            pose0_inputs=None, pose0_values=None,
            scene_values=[0.0, 0.0, 0.0],
        )
        for bv, is_scale in baselines:
            self.assertEqual(bv, 1.0)
            self.assertTrue(is_scale)


class T4_CapturePriority(unittest.TestCase):
    """Rest-pose row beats scene value; both beat nothing; scale overrides."""

    def test_pose0_rest_wins(self):
        baselines = capture_output_baselines_pure(
            driven_attrs=["translateX", "translateY"],
            pose0_inputs=[0.0, 0.0, 0.0],            # rest row
            pose0_values=[5.5, -2.0],
            scene_values=[99.0, 99.0],
        )
        self.assertEqual(baselines[0], (5.5, False))
        self.assertEqual(baselines[1], (-2.0, False))

    def test_pose0_non_rest_falls_back_to_scene(self):
        baselines = capture_output_baselines_pure(
            driven_attrs=["translateX"],
            pose0_inputs=[1.0, 0.0, 0.0],            # NOT a rest row
            pose0_values=[5.5],
            scene_values=[99.0],
        )
        self.assertEqual(baselines[0], (99.0, False))

    def test_no_sources_default_zero(self):
        baselines = capture_output_baselines_pure(
            driven_attrs=["translateX"],
        )
        self.assertEqual(baselines[0], (0.0, False))

    def test_scale_overrides_pose0(self):
        # pose0 says scaleX rest = 0.0 (broken); must still write 1.0.
        baselines = capture_output_baselines_pure(
            driven_attrs=["scaleX", "translateX"],
            pose0_inputs=[0.0, 0.0, 0.0],
            pose0_values=[0.0, 7.0],
        )
        self.assertEqual(baselines[0], (1.0, True))
        self.assertEqual(baselines[1], (7.0, False))


class T5_BaselineDirtyTrackerTripsResolve(unittest.TestCase):
    """Runtime mutation of baseValue / outputIsScale must set evalInput = true."""

    def test_first_call_is_dirty(self):
        t = BaselineDirtyTracker()
        self.assertTrue(t.update([0.0, 0.0], [False, False]))

    def test_unchanged_is_clean(self):
        t = BaselineDirtyTracker()
        t.update([1.0, 2.0], [False, True])
        self.assertFalse(t.update([1.0, 2.0], [False, True]))

    def test_base_value_change_is_dirty(self):
        t = BaselineDirtyTracker()
        t.update([1.0, 2.0], [False, True])
        self.assertTrue(t.update([1.0, 2.5], [False, True]))   # bumped [1]

    def test_is_scale_flip_is_dirty(self):
        t = BaselineDirtyTracker()
        t.update([1.0, 2.0], [False, False])
        self.assertTrue(t.update([1.0, 2.0], [False, True]))   # flipped [1]

    def test_length_change_is_dirty(self):
        t = BaselineDirtyTracker()
        t.update([1.0, 2.0], [False, True])
        self.assertTrue(t.update([1.0, 2.0, 3.0], [False, True, False]))

    def test_post_change_matches_new_output(self):
        """After a dirty update, the NEW anchors govern the recovered Y."""
        Y = np.array([[1.0, 2.0], [3.0, 4.0]])
        K = np.eye(2)

        # Initial solve with base=[0, 0], no scale:
        b_old, s_old = [0.0, 0.0], [False, False]
        W_old = np.linalg.solve(K, subtract_baseline(Y, b_old, s_old))

        # User bumps baseValue[0] → 10.0 at runtime.
        t = BaselineDirtyTracker()
        t.update(b_old, s_old)
        dirty = t.update([10.0, 0.0], s_old)
        self.assertTrue(dirty, "tracker must report dirty so wMat gets rebuilt")

        # Naive: if we reuse W_old under new anchors → wrong Y.
        delta_wrong = K @ W_old
        Y_wrong = readd_baseline(delta_wrong, [10.0, 0.0], s_old)
        self.assertFalse(np.allclose(Y_wrong, Y),
                         "reusing W_old under new anchors must corrupt Y")

        # Correct: re-solve under new anchors (C++ does this after evalInput=true).
        W_new = np.linalg.solve(K, subtract_baseline(Y, [10.0, 0.0], s_old))
        Y_ok = readd_baseline(K @ W_new, [10.0, 0.0], s_old)
        np.testing.assert_allclose(Y_ok, Y, atol=1e-12)


if __name__ == "__main__":
    unittest.main()
