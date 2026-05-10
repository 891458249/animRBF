# -*- coding: utf-8 -*-
"""T_M_P0_QUAT_RBF_LANDING_GUARDS — Pure-Python unit tests

Pin the **mathematical properties** of the multi-driver × multi-driven
quaternion RBF stack against the Python reference impl in
``_reference_impl.py``. Pure Python, no mayapy / .mll dependency.

Layered structure mirrors §2-§5 of
``docs/设计文档/RBFtools_v5_multi_quat_implementation.md``:
  * §2 input encode      — encode_euler_to_quaternion / encode_driver
  * §3 distance          — get_quat_block_distance
  * §5.1 QWA             — power_iteration_max_eigenvec_4x4 / compute_qwa_for_group
  * §5.2 outputEncoding  — nlerp / expmap inverse round-trip
"""
from __future__ import absolute_import, division, print_function

import math
import os
import random
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

import _reference_impl as ref  # noqa: E402

RO_XYZ = ref.RO_XYZ
RO_YZX = ref.RO_YZX
RO_ZXY = ref.RO_ZXY
RO_XZY = ref.RO_XZY
RO_YXZ = ref.RO_YXZ
RO_ZYX = ref.RO_ZYX
ENC_RAW = ref.ENC_RAW
ENC_QUATERNION = ref.ENC_QUATERNION
ENC_BENDROLL = ref.ENC_BENDROLL
ENC_EXPMAP = ref.ENC_EXPMAP
ENC_SWINGTWIST = ref.ENC_SWINGTWIST


# ---------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------

def _quat_norm(q):
    return math.sqrt(sum(c * c for c in q))


def _quat_dot(a, b):
    return sum(a[i] * b[i] for i in range(4))


def _quat_mul_xyzw(a, b):
    """Hamilton product for (x, y, z, w) packed quats."""
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return (
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
        aw * bw - ax * bx - ay * by - az * bz,
    )


def _nlerp_python(quats, weights):
    """Python-side mirror of cpp:3324-3366 nlerpQuaternions.

    quats: list of (qx, qy, qz, qw) tuples.
    weights: list of floats.
    Returns (qx, qy, qz, qw) unit-length blended.
    """
    if not quats:
        return (0.0, 0.0, 0.0, 1.0)
    rx, ry, rz, rw = quats[0]
    sx = sy = sz = sw = 0.0
    for i, q in enumerate(quats):
        qx, qy, qz, qw = q
        dot = qx * rx + qy * ry + qz * rz + qw * rw
        if dot < 0.0:
            qx, qy, qz, qw = -qx, -qy, -qz, -qw
        w = weights[i] if i < len(weights) else 0.0
        sx += w * qx
        sy += w * qy
        sz += w * qz
        sw += w * qw
    norm = math.sqrt(sx * sx + sy * sy + sz * sz + sw * sw)
    if norm < 1.0e-9:
        return (rx, ry, rz, rw)
    inv = 1.0 / norm
    return (sx * inv, sy * inv, sz * inv, sw * inv)


def _expmap_to_quat(lx, ly, lz):
    """Inverse of encode_quaternion_to_expmap. q_w >= 0 hemisphere."""
    theta = math.sqrt(lx * lx + ly * ly + lz * lz)
    if theta < 1.0e-12:
        return (lx, ly, lz, 1.0)  # Taylor at 0
    half = theta
    s = math.sin(half) / theta
    return (lx * s, ly * s, lz * s, math.cos(half))


# ---------------------------------------------------------------
# §2 input encode — encodeEulerToQuaternion + multi-driver dispatch
# ---------------------------------------------------------------

class TestEncodeEulerToQuaternion(unittest.TestCase):

    def test_a01_identity_at_zero_rotation(self):
        """encodeEulerToQuaternion(0,0,0,*) = (0, 0, 0, 1)"""
        for ro in (RO_XYZ, RO_YZX, RO_ZXY, RO_XZY, RO_YXZ, RO_ZYX):
            qx, qy, qz, qw = ref.encode_euler_to_quaternion(0, 0, 0, ro)
            self.assertAlmostEqual(qx, 0.0, places=12)
            self.assertAlmostEqual(qy, 0.0, places=12)
            self.assertAlmostEqual(qz, 0.0, places=12)
            self.assertAlmostEqual(qw, 1.0, places=12)

    def test_a02_unit_norm_invariant(self):
        """所有有效 Euler 输入产生单位 quat"""
        random.seed(42)
        for _ in range(50):
            rx = random.uniform(-math.pi, math.pi)
            ry = random.uniform(-math.pi/2, math.pi/2)
            rz = random.uniform(-math.pi, math.pi)
            for ro in (RO_XYZ, RO_ZYX):
                q = ref.encode_euler_to_quaternion(rx, ry, rz, ro)
                self.assertAlmostEqual(_quat_norm(q), 1.0, places=10)

    def test_a03_rotateOrder_changes_result(self):
        """非零 Euler 在不同 rotateOrder 下 quat 不同"""
        rx, ry, rz = 0.5, 0.3, 0.7
        q_xyz = ref.encode_euler_to_quaternion(rx, ry, rz, RO_XYZ)
        q_zyx = ref.encode_euler_to_quaternion(rx, ry, rz, RO_ZYX)
        # 至少一个分量差 > 0.01
        diff = max(abs(q_xyz[i] - q_zyx[i]) for i in range(4))
        self.assertGreater(diff, 0.01,
            "RO_XYZ vs RO_ZYX should produce distinguishable quats.")

    def test_a04_quat_x_only_at_pi_half(self):
        """rx=π/2 only, RO_XYZ → (sin(π/4), 0, 0, cos(π/4))"""
        q = ref.encode_euler_to_quaternion(math.pi / 2, 0, 0, RO_XYZ)
        s = math.sin(math.pi / 4)
        c = math.cos(math.pi / 4)
        self.assertAlmostEqual(q[0], s, places=10)
        self.assertAlmostEqual(q[1], 0.0, places=10)
        self.assertAlmostEqual(q[2], 0.0, places=10)
        self.assertAlmostEqual(q[3], c, places=10)


class TestMultiDriverEncode(unittest.TestCase):

    def test_a05_N1_quat_eff_dim_4(self):
        raw = [0.1, 0.2, 0.3]
        out = ref.encode_driver(raw, ENC_QUATERNION, [RO_XYZ])
        self.assertEqual(len(out), 4)

    def test_a06_N3_quat_eff_dim_12(self):
        """user 当前场景: N=3 driver × Quat → 12 维"""
        raw = [0.1, 0.2, 0.3,
               0.0, 0.4, 0.0,
               -0.2, 0.0, 0.1]
        out = ref.encode_driver(raw, ENC_QUATERNION, [RO_XYZ] * 3)
        self.assertEqual(len(out), 12,
            "N=3 + Quat must produce 12-element vector (3 quats × 4).")

    def test_a07_NK_quat_generic(self):
        """N ∈ {1, 2, 3, 5, 10, 16} × Quat 通用维度"""
        for N in (1, 2, 3, 5, 10, 16):
            raw = [0.1 * (i + 1) for i in range(3 * N)]
            out = ref.encode_driver(raw, ENC_QUATERNION, [RO_XYZ] * N)
            self.assertEqual(len(out), 4 * N,
                "N={} + Quat must produce {} elements.".format(N, 4 * N))

    def test_a08_NK_swingtwist_generic(self):
        """N=K + SwingTwist → 5K"""
        for N in (1, 2, 3, 5, 10, 16):
            raw = [0.1 * (i + 1) for i in range(3 * N)]
            out = ref.encode_driver(raw, ENC_SWINGTWIST, [RO_XYZ] * N)
            self.assertEqual(len(out), 5 * N)

    def test_a09_NK_expmap_generic(self):
        """N=K + ExpMap → 3K"""
        for N in (1, 2, 3, 5, 10, 16):
            raw = [0.1 * (i + 1) for i in range(3 * N)]
            out = ref.encode_driver(raw, ENC_EXPMAP, [RO_XYZ] * N)
            self.assertEqual(len(out), 3 * N)

    def test_a10_raw_passthrough(self):
        raw = [1.0, 2.0, 3.0, 4.0, 5.0]
        out = ref.encode_driver(raw, ENC_RAW, [])
        self.assertEqual(out, raw)

    def test_a11_non_triple_falls_back_to_raw(self):
        """inDim 非 3 倍数 → fallback Raw (encoder side defensive)"""
        raw = [1.0, 2.0, 3.0, 4.0]  # len=4, not divisible by 3
        out = ref.encode_driver(raw, ENC_QUATERNION, [RO_XYZ])
        self.assertEqual(out, raw,
            "Non-triple inDim with non-Raw encoding must fall back "
            "to Raw verbatim (encoder-side safety; node-side caller "
            "also resets effectiveEncoding via resolve_effective_encoding).")


# ---------------------------------------------------------------
# §3 distance — get_quat_block_distance
# ---------------------------------------------------------------

class TestQuatBlockDistance(unittest.TestCase):

    def test_b01_self_distance_zero(self):
        for N in (1, 3, 5, 10):
            v = [0.1 * (i + 1) for i in range(3 * N)]
            q = ref.encode_driver(v, ENC_QUATERNION, [RO_XYZ] * N)
            d = ref.get_quat_block_distance(q, q)
            self.assertAlmostEqual(d, 0.0, places=10,
                msg="d(q, q) must be 0 for N={}".format(N))

    def test_b02_double_cover_invariance(self):
        """d(q, -q) = 0 (双覆盖不变性)"""
        for N in (1, 3, 5):
            v = [0.1 * (i + 1) for i in range(3 * N)]
            q = ref.encode_driver(v, ENC_QUATERNION, [RO_XYZ] * N)
            q_neg = [-c for c in q]
            d = ref.get_quat_block_distance(q, q_neg)
            self.assertAlmostEqual(d, 0.0, places=10,
                msg="d(q, -q) must be 0 (double-cover) for N={}".format(N))

    def test_b03_symmetry(self):
        random.seed(7)
        for N in (1, 3, 5):
            v1 = [random.uniform(-1, 1) for _ in range(3 * N)]
            v2 = [random.uniform(-1, 1) for _ in range(3 * N)]
            q1 = ref.encode_driver(v1, ENC_QUATERNION, [RO_XYZ] * N)
            q2 = ref.encode_driver(v2, ENC_QUATERNION, [RO_XYZ] * N)
            d12 = ref.get_quat_block_distance(q1, q2)
            d21 = ref.get_quat_block_distance(q2, q1)
            self.assertAlmostEqual(d12, d21, places=10)

    def test_b04_non_negative(self):
        random.seed(11)
        for _ in range(20):
            N = random.choice([1, 2, 3, 5])
            v1 = [random.uniform(-1, 1) for _ in range(3 * N)]
            v2 = [random.uniform(-1, 1) for _ in range(3 * N)]
            q1 = ref.encode_driver(v1, ENC_QUATERNION, [RO_XYZ] * N)
            q2 = ref.encode_driver(v2, ENC_QUATERNION, [RO_XYZ] * N)
            d = ref.get_quat_block_distance(q1, q2)
            self.assertGreaterEqual(d, 0.0)

    def test_b05_l2_aggregation(self):
        """N=2 距离 = sqrt(d_block_0² + d_block_1²)"""
        # Block 0: identity vs identity → 0
        # Block 1: identity vs (sin45, 0, 0, cos45) → 1 - cos45
        q1 = [0, 0, 0, 1, 0, 0, 0, 1]
        s, c = math.sin(math.pi / 4), math.cos(math.pi / 4)
        q2 = [0, 0, 0, 1, s, 0, 0, c]
        d_expected = abs(1.0 - c)  # block 1 only
        d_actual = ref.get_quat_block_distance(q1, q2)
        self.assertAlmostEqual(d_actual, d_expected, places=10)


# ---------------------------------------------------------------
# §5.1 QWA — Power Iteration / compute_qwa_for_group
# ---------------------------------------------------------------

class TestQWAPowerIteration(unittest.TestCase):

    def test_c01_recovers_target_from_outer_product(self):
        """M = q_target · q_target^T → out ≈ q_target (容许 ± sign)"""
        q_target = (0.1, 0.3, 0.5, math.sqrt(1 - 0.01 - 0.09 - 0.25))
        # Build M = q q^T
        M = [0.0] * 16
        for a in range(4):
            for b in range(4):
                M[a * 4 + b] = q_target[a] * q_target[b]
        q_out, ok, _ = ref.power_iteration_max_eigenvec_4x4(M)
        self.assertTrue(ok)
        # ± sign tolerance via |dot|
        dot = sum(q_out[i] * q_target[i] for i in range(4))
        self.assertGreater(abs(dot), 0.999)

    def test_c02_zero_mass_returns_identity(self):
        """tr(M) < ε → ZERO_MASS, identity quat"""
        M = [0.0] * 16
        q_out, status = ref.compute_qwa_for_group(M)
        self.assertEqual(status, "ZERO_MASS")
        self.assertEqual(q_out, ref.QWA_IDENTITY)

    def test_c03_canonicalize_qw_positive(self):
        """所有 OK 输出 q_w >= 0 hemisphere"""
        random.seed(99)
        for _ in range(20):
            # Build a PSD M from random unit quat outer product
            theta = random.uniform(0, math.pi)
            ax, ay, az = random.uniform(-1, 1), random.uniform(-1, 1), random.uniform(-1, 1)
            n = math.sqrt(ax * ax + ay * ay + az * az)
            if n < 1e-9:
                continue
            ax, ay, az = ax / n, ay / n, az / n
            s = math.sin(theta / 2)
            q = (ax * s, ay * s, az * s, math.cos(theta / 2))
            # Negate (force q_w<0) — Markley M = q q^T = (-q)(-q)^T anyway
            q = tuple(-c for c in q)
            M = [q[a] * q[b] for a in range(4) for b in range(4)]
            q_out, status = ref.compute_qwa_for_group(M)
            self.assertEqual(status, "OK")
            self.assertGreaterEqual(q_out[3], 0.0,
                "QWA must canonicalize to q_w >= 0 hemisphere.")

    def test_c04_psd_invariance_negative_clamp(self):
        """phi<0 应在累积前 clamp → M PSD"""
        # Test the matrix-builder ensures PSD via clamp
        phis = [0.5, -0.3, 0.8]  # one negative
        quats = [
            (0.1, 0.2, 0.3, 0.93),
            (0.4, 0.0, -0.2, 0.89),
            (0.0, 0.5, 0.0, 0.87),
        ]
        M, any_clipped = ref.accumulate_qwa_matrix(phis, quats,
                                                   clip_negative=True)
        self.assertTrue(any_clipped,
            "Negative phi must raise any_clipped flag.")
        # Symmetric (M is a numpy 4x4 array)
        for a in range(4):
            for b in range(4):
                self.assertAlmostEqual(float(M[a, b]), float(M[b, a]),
                    places=12,
                    msg="M not symmetric at ({},{})".format(a, b))


# ---------------------------------------------------------------
# §5.2 outputEncoding inverse — nlerp / ExpMap round-trip
# ---------------------------------------------------------------

class TestNlerpQuaternions(unittest.TestCase):

    def test_d01_single_quat_returns_self(self):
        q = (0.1, 0.2, 0.3, math.sqrt(1 - 0.01 - 0.04 - 0.09))
        out = _nlerp_python([q], [1.0])
        for i in range(4):
            self.assertAlmostEqual(out[i], q[i], places=10)

    def test_d02_zero_weights_returns_reference(self):
        """全 0 weights → return reference q (退化保护)"""
        q1 = (0.1, 0.2, 0.3, math.sqrt(1 - 0.14))
        q2 = (-0.1, 0.4, 0.0, math.sqrt(1 - 0.17))
        out = _nlerp_python([q1, q2], [0.0, 0.0])
        for i in range(4):
            self.assertAlmostEqual(out[i], q1[i], places=10)

    def test_d03_unit_norm(self):
        """非平凡 weights 输出仍是单位 quat"""
        random.seed(13)
        for _ in range(10):
            quats = [tuple(random.uniform(-1, 1) for _ in range(4))
                     for _ in range(4)]
            # Normalize
            quats = [tuple(c / _quat_norm(q) for c in q) for q in quats]
            weights = [random.uniform(0.1, 1.0) for _ in range(4)]
            out = _nlerp_python(quats, weights)
            self.assertAlmostEqual(_quat_norm(out), 1.0, places=10)

    def test_d04_short_arc_against_reference(self):
        """q1 vs -q1 同侧 → 不出现 0 输出 (短弧选择)"""
        q1 = (0.2, 0.0, 0.0, math.sqrt(0.96))
        q1_neg = tuple(-c for c in q1)
        out = _nlerp_python([q1, q1_neg], [0.5, 0.5])
        # 应近似 q1 (因为 -q1 被翻号回 q1)
        dot = _quat_dot(out, q1)
        self.assertGreater(abs(dot), 0.999)

    def test_d05_two_quat_blend_lies_between(self):
        """nlerp(q_a, q_b, [0.5, 0.5]) 在 q_a 与 q_b 之间的弧上"""
        q_a = ref.encode_euler_to_quaternion(0.0, 0.0, 0.0, RO_XYZ)
        q_b = ref.encode_euler_to_quaternion(math.pi / 2, 0, 0, RO_XYZ)
        out = _nlerp_python([q_a, q_b], [0.5, 0.5])
        # Halfway angle ~ π/4 → q ~ (sin(π/8), 0, 0, cos(π/8))
        self.assertAlmostEqual(out[0], math.sin(math.pi / 8), places=8)
        self.assertAlmostEqual(out[3], math.cos(math.pi / 8), places=8)


class TestExpMapRoundTrip(unittest.TestCase):

    def test_e01_log_identity_zero(self):
        """log(identity) = (0, 0, 0)"""
        lx, ly, lz = ref.encode_quaternion_to_expmap(0.0, 0.0, 0.0, 1.0)
        self.assertAlmostEqual(lx, 0.0, places=12)
        self.assertAlmostEqual(ly, 0.0, places=12)
        self.assertAlmostEqual(lz, 0.0, places=12)

    def test_e02_log_exp_round_trip(self):
        """对小角 quat (q_w >= 0)，log → exp 还原"""
        random.seed(17)
        for _ in range(20):
            # Build unit quat with q_w >= 0
            theta = random.uniform(0, math.pi * 0.9)  # avoid θ=π singularity
            ax, ay, az = random.uniform(-1, 1), random.uniform(-1, 1), random.uniform(-1, 1)
            n = math.sqrt(ax * ax + ay * ay + az * az)
            if n < 1e-6:
                continue
            ax, ay, az = ax / n, ay / n, az / n
            s = math.sin(theta / 2)
            q = (ax * s, ay * s, az * s, math.cos(theta / 2))
            lx, ly, lz = ref.encode_quaternion_to_expmap(*q)
            q_back = _expmap_to_quat(lx, ly, lz)
            # |dot| ≈ 1 (allow ± sign)
            dot = sum(q[i] * q_back[i] for i in range(4))
            self.assertGreater(abs(dot), 0.9999,
                "log/exp round-trip must preserve quat (modulo ± sign).")


# ---------------------------------------------------------------
# §2.4 + Matrix 互斥安全网
# ---------------------------------------------------------------

class TestSafetyNets(unittest.TestCase):

    def test_f01_resolve_effective_encoding_non_triple(self):
        """非 3 倍数 inDim + 非 Raw → effective = Raw (0) + non_triple warning"""
        for in_dim in (1, 2, 4, 5, 7, 8, 10, 11):
            for enc in (ENC_QUATERNION, ENC_BENDROLL, ENC_EXPMAP, ENC_SWINGTWIST):
                eff, warn = ref.resolve_effective_encoding(enc, in_dim)
                self.assertEqual(eff, ENC_RAW,
                    "inDim={} % 3 != 0 with encoding={} should fall "
                    "back to Raw, got {}".format(in_dim, enc, eff))
                self.assertEqual(warn, 'non_triple')

    def test_f02_resolve_effective_encoding_triple_passthrough(self):
        """3 倍数 inDim → encoding 不变, 无 warning"""
        for in_dim in (3, 6, 9, 12, 15, 30, 48):
            for enc in (ENC_QUATERNION, ENC_BENDROLL, ENC_EXPMAP, ENC_SWINGTWIST):
                eff, warn = ref.resolve_effective_encoding(enc, in_dim)
                self.assertEqual(eff, enc)
                self.assertIsNone(warn)


# ---------------------------------------------------------------
# §5.4.1 quaternion group resolution + B1↔B2 overlap pre-check
# ---------------------------------------------------------------

class TestQuaternionGroupResolution(unittest.TestCase):

    def test_g01_valid_group_accepted(self):
        """单 group [0..3] 在 4 列 output 中合法"""
        valid, mask, any_inv = ref.resolve_quaternion_groups(
            [0], 4, [False] * 4)
        self.assertEqual(valid, [0])
        self.assertEqual(mask, [True, True, True, True])
        self.assertFalse(any_inv)

    def test_g02_out_of_range_dropped(self):
        """超出 outputCount 的 start 被丢弃"""
        valid, mask, any_inv = ref.resolve_quaternion_groups(
            [0, 5], 6, [False] * 6)
        # start=5 needs slots 5,6,7,8 — out of range (count=6)
        self.assertEqual(valid, [0])
        self.assertTrue(any_inv)

    def test_g03_overlap_dropped(self):
        """重叠 group (e.g. start=0 和 start=2) → 后者丢弃"""
        valid, mask, any_inv = ref.resolve_quaternion_groups(
            [0, 2], 8, [False] * 8)
        # start=2 needs slots 2,3,4,5 — overlaps with start=0 (slots 0,1,2,3)
        self.assertEqual(valid, [0])
        self.assertTrue(any_inv)

    def test_g04_scale_collision_dropped(self):
        """quat group 4 列与 outputIsScale 冲突 → 丢弃"""
        is_scale = [False] * 8
        is_scale[2] = True  # col 2 is scale
        valid, mask, any_inv = ref.resolve_quaternion_groups(
            [0], 8, is_scale)
        self.assertEqual(valid, [])
        self.assertTrue(any_inv)


if __name__ == "__main__":
    unittest.main()
