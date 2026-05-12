"""M2.1a — Input encoding (Raw, Quaternion, ExpMap) + Bug 2 fix.

Tests the Python mirror of the C++ compute() M2.1a path: effective
encoding resolution via safety net, encode_driver / encode_euler_to_*
math, per-encoding getPoseDelta dispatch, and the Bug 2 regression
that Matrix-mode + distanceType==Angle now routes through
getMatrixModeAngleDistance instead of silently falling to Euclidean.
"""

from __future__ import annotations

import math
import unittest

from _reference_impl import (
    ENC_BENDROLL,
    ENC_EXPMAP,
    ENC_QUATERNION,
    ENC_RAW,
    ENC_SWINGTWIST,
    RO_XYZ,
    RO_YXZ,
    RO_YZX,
    RO_ZXY,
    clamp_skip_dims,
    encode_driver,
    encode_euler_to_quaternion,
    encode_quaternion_to_expmap,
    get_angle,
    get_matrix_mode_angle_distance,
    get_matrix_mode_linear_distance,
    get_pose_delta,
    get_quat_block_distance,
    get_radius,
    is_scale_attr,
    resolve_effective_encoding,
)


class T1_IsScaleAttrUnchanged(unittest.TestCase):
    """M1.2's scale-attr detection must not regress across M2.1a work."""

    def test_cross_milestone(self):
        self.assertTrue(is_scale_attr("scaleX"))
        self.assertTrue(is_scale_attr("sz"))
        self.assertFalse(is_scale_attr("translateX"))


class T2_RawBytewiseIdentity(unittest.TestCase):
    """Zero-regression contract: inputEncoding=Raw + missing rotate-order
    array is equivalent to v4 behaviour — encode_driver must return the
    raw vector unchanged, and get_pose_delta must hit the legacy dispatch."""

    def test_encode_raw_passthrough(self):
        raw = [0.1, -0.2, 3.5, 0.0, 7.2]
        self.assertEqual(encode_driver(raw, ENC_RAW, []), raw)
        self.assertEqual(encode_driver(raw, ENC_RAW, [RO_XYZ]), raw)

    def test_raw_dispatch_generic_euclidean(self):
        v1 = [1.0, 2.0, 3.0, 4.0]
        v2 = [0.5, 1.5, 2.5, 3.5]
        got = get_pose_delta(v1, v2, dist_type=0, encoding=ENC_RAW,
                             is_matrix_mode=False)
        self.assertAlmostEqual(got, get_radius(v1, v2), places=12)

    def test_raw_dispatch_generic_angle_on_3d(self):
        v1 = [1.0, 0.0, 0.0]
        v2 = [0.0, 1.0, 0.0]
        got = get_pose_delta(v1, v2, dist_type=1, encoding=ENC_RAW,
                             is_matrix_mode=False)
        self.assertAlmostEqual(got, math.pi / 2, places=12)


class T3_EulerToQuaternionAcrossRotateOrders(unittest.TestCase):
    """Different rotateOrder values produce different quaternions for
    the same (rx, ry, rz), and each matches a reference right-to-left
    composition."""

    def test_identity(self):
        for ro in (RO_XYZ, RO_YZX, RO_ZXY, RO_YXZ):
            q = encode_euler_to_quaternion(0.0, 0.0, 0.0, ro)
            self.assertAlmostEqual(q[0], 0.0, places=12)
            self.assertAlmostEqual(q[1], 0.0, places=12)
            self.assertAlmostEqual(q[2], 0.0, places=12)
            self.assertAlmostEqual(q[3], 1.0, places=12)

    def test_xyz_order_distinct_from_zxy(self):
        rx, ry, rz = math.radians(30.0), math.radians(45.0), math.radians(60.0)
        q_xyz = encode_euler_to_quaternion(rx, ry, rz, RO_XYZ)
        q_zxy = encode_euler_to_quaternion(rx, ry, rz, RO_ZXY)
        diff = sum((a - b) ** 2 for a, b in zip(q_xyz, q_zxy))
        self.assertGreater(diff, 1e-6)

    def test_single_axis_reduces_correctly(self):
        # Rotate pi/2 around X only, rotateOrder irrelevant for single axis.
        q = encode_euler_to_quaternion(math.pi / 2, 0.0, 0.0, RO_XYZ)
        # Expected: (sin(π/4), 0, 0, cos(π/4))
        expected = (math.sin(math.pi / 4), 0.0, 0.0, math.cos(math.pi / 4))
        for a, b in zip(q, expected):
            self.assertAlmostEqual(a, b, places=12)


class T4_QuaternionDistanceAntipodal(unittest.TestCase):
    """(1 - |q·q|) collapses the q ≡ -q double cover to zero."""

    def test_random_quats(self):
        import random
        rng = random.Random(0xFACADE)
        for _ in range(10):
            # Random unit quat.
            raw = [rng.uniform(-1, 1) for _ in range(4)]
            n = math.sqrt(sum(c*c for c in raw))
            q = [c/n for c in raw]
            neg = [-c for c in q]
            d = get_quat_block_distance(q, neg)
            self.assertLess(d, 1e-10)


class T5_ExpMapBasics(unittest.TestCase):
    """Identity → (0,0,0); ±90°-around-X → (±π/4, 0, 0)."""

    def test_identity(self):
        l = encode_quaternion_to_expmap(0.0, 0.0, 0.0, 1.0)
        self.assertAlmostEqual(l[0], 0.0, places=12)
        self.assertAlmostEqual(l[1], 0.0, places=12)
        self.assertAlmostEqual(l[2], 0.0, places=12)

    def test_positive_90_around_x(self):
        # q for +90° around X: (sin(π/4), 0, 0, cos(π/4)).
        sx, cx = math.sin(math.pi / 4), math.cos(math.pi / 4)
        l = encode_quaternion_to_expmap(sx, 0.0, 0.0, cx)
        self.assertAlmostEqual(l[0], math.pi / 4, places=12)
        self.assertAlmostEqual(l[1], 0.0, places=12)
        self.assertAlmostEqual(l[2], 0.0, places=12)

    def test_negative_90_around_x(self):
        # q for -90° around X: (-sin(π/4), 0, 0, cos(π/4)).
        sx, cx = math.sin(math.pi / 4), math.cos(math.pi / 4)
        l = encode_quaternion_to_expmap(-sx, 0.0, 0.0, cx)
        self.assertAlmostEqual(l[0], -math.pi / 4, places=12)
        self.assertAlmostEqual(l[1], 0.0, places=12)
        self.assertAlmostEqual(l[2], 0.0, places=12)


class T6_ExpMapNearIdentityTaylor(unittest.TestCase):
    """θ → 0 path: log(q) ≈ (qx, qy, qz), no NaN."""

    def test_tiny_theta(self):
        # Very small rotation: half_theta ≈ qx, sin_half ≈ qx, ratio ≈ 1.
        eps = 1.0e-10
        l = encode_quaternion_to_expmap(eps, 0.0, 0.0, math.sqrt(1 - eps*eps))
        self.assertTrue(math.isfinite(l[0]))
        self.assertAlmostEqual(l[0], eps, delta=1e-8)

    def test_zero_rotation_stable(self):
        l = encode_quaternion_to_expmap(0.0, 0.0, 0.0, 1.0)
        for c in l:
            self.assertTrue(math.isfinite(c))


class T7_ExpMapNearAntipodal(unittest.TestCase):
    """θ ≈ π boundary: output finite. The log map is discontinuous at
    the antipode (ambiguous axis) but callers/tests only require no NaN."""

    def test_near_pi(self):
        eps = 1e-6
        # q_w ≈ 0: θ ≈ π. Axis along x.
        qw = eps
        qx = math.sqrt(1.0 - qw * qw)
        l = encode_quaternion_to_expmap(qx, 0.0, 0.0, qw)
        for c in l:
            self.assertTrue(math.isfinite(c))
        # Magnitude ≈ π/2 (since half_theta ≈ π/2).
        norm = math.sqrt(sum(c*c for c in l))
        self.assertAlmostEqual(norm, math.pi / 2, delta=1e-3)


class T8_Bug2MatrixAngleDispatch(unittest.TestCase):
    """M1.1 addendum §Bug 2 regression: Matrix-mode + distType=1 + size=4
    must reach getMatrixModeAngleDistance, not silently fall to Euclidean."""

    def test_matrix_angle_routes_to_angle_helper(self):
        # Single-block swing xyz unit vectors + wildly different twist.
        v1 = [1.0, 0.0, 0.0, math.radians(179.0)]
        v2 = [0.0, 1.0, 0.0, math.radians(-179.0)]

        # Old (broken) path was Euclidean: sqrt(1 + 1 + 0 + (358°)²) ≈ big.
        euclidean = get_radius(v1, v2)

        # New (fixed) path: sqrt((π/2)² + (2°)²)
        angle = get_pose_delta(v1, v2, dist_type=1, encoding=ENC_RAW,
                               is_matrix_mode=True)

        direct = get_matrix_mode_angle_distance(v1, v2)
        self.assertAlmostEqual(angle, direct, places=12)

        # Sanity: angle path must be drastically SMALLER than legacy
        # Euclidean for this seam case (the whole point of Bug 2).
        self.assertLess(angle, 3.0)
        self.assertGreater(euclidean, 6.0)

    def test_matrix_linear_still_uses_linear_helper(self):
        v1 = [1.0, 0.0, 0.0, 0.5]
        v2 = [0.9, 0.1, 0.0, 0.7]
        got = get_pose_delta(v1, v2, dist_type=0, encoding=ENC_RAW,
                             is_matrix_mode=True)
        direct = get_matrix_mode_linear_distance(v1, v2)
        self.assertAlmostEqual(got, direct, places=12)


class T9_ClampSkipRuleMatrix(unittest.TestCase):
    """Per v5 addendum §M2.1a item 7 table."""

    def test_matrix_mode_skips_twist_slot(self):
        # Two-driver-block: indices 3 and 7 are twist.
        self.assertEqual(
            clamp_skip_dims(encoding=ENC_RAW, is_matrix_mode=True,
                            effective_dim=8),
            {3, 7},
        )

    def test_generic_raw_clamps_all(self):
        self.assertEqual(
            clamp_skip_dims(encoding=ENC_RAW, is_matrix_mode=False,
                            effective_dim=5),
            set(),
        )

    def test_generic_quaternion_clamps_all(self):
        # 4-per-block quats; all 4 dims ∈ [-1, 1] are bounded and safe
        # to clamp linearly — no skip.
        self.assertEqual(
            clamp_skip_dims(encoding=ENC_QUATERNION, is_matrix_mode=False,
                            effective_dim=8),
            set(),
        )

    def test_generic_expmap_clamps_all(self):
        self.assertEqual(
            clamp_skip_dims(encoding=ENC_EXPMAP, is_matrix_mode=False,
                            effective_dim=6),
            set(),
        )


class T10_CrossEncodingDispatch(unittest.TestCase):
    """Given the same vectors, the dispatch picks the intended helper
    based on encoding."""

    def test_quat_routes_to_block_distance(self):
        # Two 4-blocks (2 driver groups).
        v1 = [0.0, 0.0, 0.0, 1.0,     math.sin(math.pi/4), 0.0, 0.0, math.cos(math.pi/4)]
        v2 = [0.0, 0.0, 0.0, 1.0,     0.0, math.sin(math.pi/4), 0.0, math.cos(math.pi/4)]
        got = get_pose_delta(v1, v2, dist_type=0, encoding=ENC_QUATERNION,
                             is_matrix_mode=False)
        direct = get_quat_block_distance(v1, v2)
        self.assertAlmostEqual(got, direct, places=12)

    def test_expmap_routes_to_euclidean(self):
        v1 = [0.1, 0.2, 0.3]
        v2 = [0.4, 0.5, 0.6]
        got = get_pose_delta(v1, v2, dist_type=0, encoding=ENC_EXPMAP,
                             is_matrix_mode=False)
        self.assertAlmostEqual(got, get_radius(v1, v2), places=12)


class T11_InDimSafetyNet(unittest.TestCase):
    """Non-Raw encoding with inDim not divisible by 3 falls back to Raw
    (with a 'non_triple' warning tag). encode_driver must also pass the
    value through unchanged in this state."""

    def test_non_triple_falls_back_and_warns(self):
        enc, warn = resolve_effective_encoding(
            encoding=ENC_QUATERNION, raw_in_dim=5)
        self.assertEqual(enc, ENC_RAW)
        self.assertEqual(warn, 'non_triple')

    def test_raw_never_warns(self):
        enc, warn = resolve_effective_encoding(
            encoding=ENC_RAW, raw_in_dim=5)
        self.assertEqual(enc, ENC_RAW)
        self.assertIsNone(warn)

    def test_triple_pass_through(self):
        enc, warn = resolve_effective_encoding(
            encoding=ENC_QUATERNION, raw_in_dim=6)
        self.assertEqual(enc, ENC_QUATERNION)
        self.assertIsNone(warn)

    def test_encode_driver_ignores_non_triple_request(self):
        # Caller would have already remapped via the safety net; the
        # encode helper itself is also defensive.
        raw = [1.0, 2.0, 3.0, 4.0, 5.0]  # len 5, not divisible by 3
        out = encode_driver(raw, ENC_QUATERNION, [])
        self.assertEqual(out, raw)


# T12 (M2.1a placeholder fallback) was a snapshot of the transient
# "BendRoll/SwingTwist declared but not implemented" contract that
# existed between M2.1a and M2.1b. Superseded by T12' in
# test_m2_1b_encoding.py, which verifies the encodings actually land
# (BendRoll → 3 per group, SwingTwist → 5 per group).


if __name__ == "__main__":
    unittest.main()
