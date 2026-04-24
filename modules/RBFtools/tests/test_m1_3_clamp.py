"""M1.3 — Driver Clamp spec tests.

Mirrors the C++ compute() clamp branch:

    bounds = compute_bounds(poseData, skip_twist=(matrix_mode))
    driver = apply_clamp(driver, bounds[0], bounds[1],
                         inflation=clampInflationVal,
                         skip_twist=(matrix_mode))

Defaults: clamp off, inflation 0.0 (hard). T1–T8 per v5 addendum
2026-04-24 §M1.3.
"""

from __future__ import annotations

import math
import unittest

from _reference_impl import apply_clamp, compute_bounds


class T1_ComputeBounds(unittest.TestCase):

    def test_generic_all_dims(self):
        poses = [
            [0.0, -1.0, 2.0],
            [5.0,  3.0, 2.0],
            [1.0,  0.0, 2.5],
        ]
        mins, maxs = compute_bounds(poses, skip_twist=False)
        self.assertEqual(mins, [0.0, -1.0, 2.0])
        self.assertEqual(maxs, [5.0,  3.0, 2.5])

    def test_matrix_skip_twist(self):
        # Single driver: [vx, vy, vz, twist]
        poses = [
            [1.0, 0.0, 0.0,  3.0],
            [0.9, 0.1, 0.0, -3.0],
        ]
        mins, maxs = compute_bounds(poses, skip_twist=True)
        self.assertEqual(mins[:3], [0.9, 0.0, 0.0])
        self.assertEqual(maxs[:3], [1.0, 0.1, 0.0])
        # Twist slot (j=3) is sentinel-zero and thus pass-through at apply.
        self.assertEqual((mins[3], maxs[3]), (0.0, 0.0))

    def test_matrix_multiple_drivers_skip_only_twist_slots(self):
        # Two drivers: indices 3 and 7 are twist; 0-2 and 4-6 are xyz.
        poses = [
            [1.0, 0.0, 0.0,  3.0, 0.5, 0.5, 0.0,  0.1],
            [0.0, 1.0, 0.0, -3.0, 0.6, 0.4, 0.0, -0.1],
        ]
        mins, maxs = compute_bounds(poses, skip_twist=True)
        self.assertEqual(mins[0:3], [0.0, 0.0, 0.0])
        self.assertEqual(maxs[0:3], [1.0, 1.0, 0.0])
        self.assertEqual((mins[3], maxs[3]), (0.0, 0.0))
        self.assertEqual(mins[4:7], [0.5, 0.4, 0.0])
        self.assertEqual(maxs[4:7], [0.6, 0.5, 0.0])
        self.assertEqual((mins[7], maxs[7]), (0.0, 0.0))

    def test_empty(self):
        self.assertEqual(compute_bounds([]), ([], []))


class T2_ApplyClampScalar(unittest.TestCase):

    def test_inside_unchanged(self):
        out = apply_clamp([0.5], [0.0], [1.0])
        self.assertEqual(out, [0.5])

    def test_below_snaps_to_min(self):
        out = apply_clamp([-3.0], [0.0], [1.0])
        self.assertEqual(out, [0.0])

    def test_above_snaps_to_max(self):
        out = apply_clamp([17.0], [0.0], [1.0])
        self.assertEqual(out, [1.0])

    def test_exact_boundary_passes(self):
        self.assertEqual(apply_clamp([0.0], [0.0], [1.0]), [0.0])
        self.assertEqual(apply_clamp([1.0], [0.0], [1.0]), [1.0])


class T3_InflationSemantics(unittest.TestCase):
    """alpha=0 hard, alpha>0 widens by alpha * range symmetrically."""

    def test_hard_clamp_default(self):
        out = apply_clamp([2.0, -5.0], [0.0, 0.0], [1.0, 1.0], inflation=0.0)
        self.assertEqual(out, [1.0, 0.0])

    def test_inflation_widens_range(self):
        # range = 10, alpha = 0.2 -> extra 2 on each side, hull [-2, 12].
        out = apply_clamp([11.0], [0.0], [10.0], inflation=0.2)
        self.assertEqual(out, [11.0])   # 11 < 12, passes
        out = apply_clamp([13.0], [0.0], [10.0], inflation=0.2)
        self.assertAlmostEqual(out[0], 12.0, places=12)
        out = apply_clamp([-2.5], [0.0], [10.0], inflation=0.2)
        self.assertAlmostEqual(out[0], -2.0, places=12)

    def test_inflation_zero_equals_hard(self):
        self.assertEqual(
            apply_clamp([11.0], [0.0], [10.0], inflation=0.0),
            apply_clamp([11.0], [0.0], [10.0]),
        )


class T4_MatrixTwistPassthrough(unittest.TestCase):
    """Twist slot (j % 4 == 3) pass-through; xyz still clamped."""

    def test_twist_value_far_outside_is_kept(self):
        # Single driver: xyz bounds [0, 1]^3, twist sentinel (0, 0).
        # Driver: vx=2 (should clamp to 1), twist=999 rad (should pass).
        driver = [2.0, 0.0, 0.0, 999.0]
        mins   = [0.0, 0.0, 0.0, 0.0]
        maxs   = [1.0, 0.0, 0.0, 0.0]
        out = apply_clamp(driver, mins, maxs, skip_twist=True)
        self.assertEqual(out, [1.0, 0.0, 0.0, 999.0])

    def test_generic_mode_does_clamp_index_3(self):
        # Same data but skip_twist=False — j=3 must be clamped.
        driver = [2.0, 0.0, 0.0, 999.0]
        mins   = [0.0, 0.0, 0.0, 0.0]
        maxs   = [1.0, 0.0, 0.0, 0.0]
        out = apply_clamp(driver, mins, maxs, skip_twist=False)
        self.assertEqual(out, [1.0, 0.0, 0.0, 0.0])


class T5_InHullIdentity(unittest.TestCase):
    """Any stored pose input, fed back as the live driver, must be
    unchanged by clamp."""

    def test_each_pose_unchanged(self):
        poses = [
            [0.5, -0.3,  1.2],
            [1.7,  2.1, -0.4],
            [0.0,  0.0,  0.0],
        ]
        mins, maxs = compute_bounds(poses)
        for p in poses:
            self.assertEqual(apply_clamp(p, mins, maxs), list(p))


class T6_DegenerateSinglePose(unittest.TestCase):
    """min == max -> range 0 -> clamp pins input to the single value."""

    def test_single_pose(self):
        poses = [[3.0, -1.0]]
        mins, maxs = compute_bounds(poses)
        self.assertEqual(mins, [3.0, -1.0])
        self.assertEqual(maxs, [3.0, -1.0])
        out = apply_clamp([99.0, 99.0], mins, maxs)
        self.assertEqual(out, [3.0, -1.0])

    def test_all_poses_same_value_on_one_dim(self):
        poses = [[1.0, 5.0], [2.0, 5.0], [3.0, 5.0]]
        mins, maxs = compute_bounds(poses)
        self.assertEqual(mins[1], 5.0)
        self.assertEqual(maxs[1], 5.0)
        # dim 1 is pinned to 5.0 regardless of input.
        self.assertEqual(apply_clamp([10.0, 99.0], mins, maxs), [3.0, 5.0])


class T7_MatrixClampXYZAndPassthroughCombined(unittest.TestCase):
    """Mixed: xyz outside gets clamped, twist in same block passes through."""

    def test_single_block_mixed(self):
        # Two poses, single driver block.
        poses = [
            [0.2, 0.3, 0.4,  1.0],
            [0.8, 0.7, 0.6, -1.0],
        ]
        mins, maxs = compute_bounds(poses, skip_twist=True)
        # driver: vx below hull, vy in hull, vz above hull, twist wild.
        driver = [0.0, 0.5, 99.0, 42.0]
        out = apply_clamp(driver, mins, maxs, skip_twist=True)
        self.assertAlmostEqual(out[0], 0.2)     # clamped to min
        self.assertAlmostEqual(out[1], 0.5)     # in hull
        self.assertAlmostEqual(out[2], 0.6)     # clamped to max
        self.assertEqual(out[3], 42.0)          # twist passes through


class T8_CacheLifecycle(unittest.TestCase):
    """Bounds cache must refresh cleanly when the pose set grows / changes.

    Mirrors the C++ contract: evalInput==true re-runs getPoseData/
    getPoseVectors which unconditionally rewrite poseMinVec /
    poseMaxVec. Old bounds must never leak through.
    """

    def test_growing_pose_set_expands_bounds(self):
        poses_v1 = [[0.0, 0.0], [1.0, 1.0]]
        mins_v1, maxs_v1 = compute_bounds(poses_v1)
        self.assertEqual((mins_v1, maxs_v1), ([0.0, 0.0], [1.0, 1.0]))

        driver = [5.0, 5.0]
        # With v1 bounds, driver clips to [1.0, 1.0]:
        self.assertEqual(apply_clamp(driver, mins_v1, maxs_v1), [1.0, 1.0])

        # A third pose with a larger value on dim 0 is added; cache refresh.
        poses_v2 = poses_v1 + [[7.0, 0.5]]
        mins_v2, maxs_v2 = compute_bounds(poses_v2)
        self.assertEqual(mins_v2, [0.0, 0.0])
        self.assertEqual(maxs_v2, [7.0, 1.0])

        # Same driver under v2 bounds is now INSIDE dim 0's hull.
        self.assertEqual(apply_clamp(driver, mins_v2, maxs_v2), [5.0, 1.0])

    def test_shrinking_pose_set_refreshes(self):
        poses_big = [[-10.0, -10.0], [10.0, 10.0]]
        mins_big, maxs_big = compute_bounds(poses_big)

        poses_small = [[-1.0, -1.0], [1.0, 1.0]]
        mins_small, maxs_small = compute_bounds(poses_small)

        driver = [5.0, 5.0]
        # Would be unclamped under big bounds, must clip under small.
        self.assertEqual(apply_clamp(driver, mins_big, maxs_big), [5.0, 5.0])
        self.assertEqual(apply_clamp(driver, mins_small, maxs_small),
                         [1.0, 1.0])


class T9_Defense(unittest.TestCase):
    """Mirror of the C++ defense branch: empty cache / size mismatch = pass-through."""

    def test_empty_cache_passthrough(self):
        out = apply_clamp([1.0, 2.0, 3.0], [], [])
        self.assertEqual(out, [1.0, 2.0, 3.0])

    def test_size_mismatch_passthrough(self):
        out = apply_clamp([1.0, 2.0, 3.0], [0.0, 0.0], [1.0, 1.0])
        self.assertEqual(out, [1.0, 2.0, 3.0])


if __name__ == "__main__":
    unittest.main()
