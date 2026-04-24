"""M2.2 — Quaternion Weighted Average (QWA) output encoding.

Covers:
  T1  Hamilton right-mul matrix orthogonality (R^T R = I)
  T2  Commutativity: QWA(q_i · q0^-1) · q0 == QWA(q_i)    [path (a)=(b) proof]
  T3  Power Iteration matches numpy.linalg.eigh max eigenvector
  T4  Identity seed: convergence + iteration count stays small
  T5  Two-sample equal-weight: slerp midpoint recovered
  T6  Sign canonicalisation: q_w >= 0 always
  T7  Degenerate: M=0 / zero-mass → identity + status
  T8  Config validation: out-of-range / overlap / scale conflict
  T9  Zero regression: empty groups → scalar path untouched
  T10 Scale∩Quat collision drops group (no silent override)
  T11 Negative phi clamped to 0 for PSD preservation (Q8)
"""

from __future__ import annotations

import math
import unittest

import numpy as np

from _reference_impl import (
    QWA_IDENTITY,
    accumulate_qwa_matrix,
    compute_qwa_for_group,
    power_iteration_max_eigenvec_4x4,
    resolve_quaternion_groups,
    right_mul_matrix,
)


def _rand_unit_quat(rng):
    v = rng.standard_normal(4)
    v /= np.linalg.norm(v)
    return tuple(v.tolist())


def _quat_mul(a, b):
    # (x, y, z, w) Hamilton product: p = a · b
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return (
        aw*bx + ax*bw + ay*bz - az*by,
        aw*by - ax*bz + ay*bw + az*bx,
        aw*bz + ax*by - ay*bx + az*bw,
        aw*bw - ax*bx - ay*by - az*bz,
    )


class T1_HamiltonRightMulOrthogonal(unittest.TestCase):
    """R(q0) is orthogonal ⟺ right-multiplication by unit q0 preserves norm."""

    def test_identity_quat(self):
        R = right_mul_matrix((0.0, 0.0, 0.0, 1.0))
        np.testing.assert_allclose(R @ R.T, np.eye(4), atol=1e-12)

    def test_random_unit_quat(self):
        rng = np.random.default_rng(0xBADC0DE)
        for _ in range(10):
            q0 = _rand_unit_quat(rng)
            R = right_mul_matrix(q0)
            np.testing.assert_allclose(R @ R.T, np.eye(4), atol=1e-12)
            np.testing.assert_allclose(R.T @ R, np.eye(4), atol=1e-12)

    def test_right_mul_matches_hamilton(self):
        """R(q0) @ q (as column) == Hamilton(q, q0) (as column)."""
        rng = np.random.default_rng(0xFEEDFACE)
        q0 = _rand_unit_quat(rng)
        q  = _rand_unit_quat(rng)
        R = right_mul_matrix(q0)
        matrix_result = R @ np.array(q)
        hamilton_result = _quat_mul(q, q0)
        np.testing.assert_allclose(matrix_result, hamilton_result, atol=1e-12)


class T2_PathA_EqualsPathB_Commutativity(unittest.TestCase):
    """Numerical verification of the algebraic commutativity proof:
    QWA({q_i · q0^-1}, w_i) · q0 == QWA({q_i}, w_i) for constant q0."""

    def test_constant_q_base(self):
        rng = np.random.default_rng(0xDEADBEEF)
        for trial in range(5):
            # QWA-realistic samples: cluster near a random mean
            # quaternion, plus small noise. Rank-1-dominant covariance
            # → Power Iteration converges quickly. Fully random S^3
            # samples produce covariances with λ_1/λ_2 ≈ 1, which is
            # outside the design envelope of a 50-iter Power Iteration
            # seeded at identity (addendum §M2.2 Q3 discussion).
            q_mean = _rand_unit_quat(rng)
            q_mean_np = np.array(q_mean)
            quats = []
            for _ in range(6):
                delta = rng.standard_normal(4) * 0.08
                q_perturbed = q_mean_np + delta
                q_perturbed /= np.linalg.norm(q_perturbed)
                quats.append(tuple(q_perturbed.tolist()))
            weights = [abs(float(rng.standard_normal())) + 0.1 for _ in range(6)]

            # q0 arbitrary unit quat (non-identity).
            q0 = _rand_unit_quat(rng)

            # Path (b): direct QWA.
            M_b, _ = accumulate_qwa_matrix(weights, quats)
            q_b, _ = compute_qwa_for_group(M_b)

            # Path (a): transform to delta, QWA, reassemble.
            def conj(q): return (-q[0], -q[1], -q[2], q[3])
            q0_inv = conj(q0)
            quats_delta = [_quat_mul(qi, q0_inv) for qi in quats]
            M_a, _ = accumulate_qwa_matrix(weights, quats_delta)
            q_a_delta, _ = compute_qwa_for_group(M_a)
            q_a = _quat_mul(q_a_delta, q0)

            # Canonicalise both to w >= 0 for comparison.
            if q_a[3] < 0.0: q_a = tuple(-c for c in q_a)
            if q_b[3] < 0.0: q_b = tuple(-c for c in q_b)

            # dot ≈ 1 means same rotation (modulo sign, which is
            # canonicalised above).
            dot = sum(a*b for a, b in zip(q_a, q_b))
            self.assertGreater(dot, 1.0 - 1e-6,
                msg="trial {}: path (a)={}  path (b)={}".format(trial, q_a, q_b))


class T3_PowerIterationMatchesEigh(unittest.TestCase):
    """Against numpy.linalg.eigh as golden reference."""

    def _qwa_rank_dominant_matrix(self, rng, n_samples=6):
        """Build M = Σ w_i q_i q_iᵀ from clustered unit quats — the
        realistic QWA scenario where rank-1 dominance gives a clean
        λ_1/λ_2 >> 1. Power Iteration (any reasonable seed) converges
        in well under 50 iterations."""
        q_mean = rng.standard_normal(4)
        q_mean /= np.linalg.norm(q_mean)
        M = np.zeros((4, 4))
        for _ in range(n_samples):
            delta = rng.standard_normal(4) * 0.05
            q = q_mean + delta
            q /= np.linalg.norm(q)
            w = abs(float(rng.standard_normal())) + 0.1
            M += w * np.outer(q, q)
        return M

    def test_rank_dominant_qwa(self):
        rng = np.random.default_rng(0xA11CE)
        for _ in range(10):
            M = self._qwa_rank_dominant_matrix(rng)
            vals, vecs = np.linalg.eigh(M)
            gold = vecs[:, -1]  # eigh sorts ascending → last is max
            if gold[3] < 0: gold = -gold
            q_got, ok, _ = power_iteration_max_eigenvec_4x4(M)
            q_got = np.array(q_got)
            dot = abs(float(np.dot(q_got, gold)))
            self.assertTrue(ok)
            self.assertGreater(dot, 1.0 - 1e-6)

    def test_rank_one_matrix(self):
        """For M = q·q^T, max eigenvector is q exactly."""
        q = np.array([0.3, 0.5, 0.1, 0.8])
        q /= np.linalg.norm(q)
        M = np.outer(q, q)
        q_got, ok, _ = power_iteration_max_eigenvec_4x4(M)
        self.assertTrue(ok)
        if q[3] < 0: q = -q
        dot = abs(float(np.dot(np.array(q_got), q)))
        self.assertGreater(dot, 1.0 - 1e-8)


class T4_IdentitySeedConvergence(unittest.TestCase):
    """Identity seed converges within 20 iters for typical RBF QWA
    matrices (dominant eigenvalue from clustered samples)."""

    def test_dominant_rank(self):
        # A cluster of 4 quats all near identity + one positive weight
        # biggest → lambda_1 >> lambda_2. Should converge < 20 iters.
        np.random.seed(0xFACE)
        quats = [(0.01, 0.0, 0.0, 0.99995),
                 (0.0, 0.02, 0.0, 0.9998),
                 (0.0, 0.0, 0.01, 0.99995),
                 (0.0, 0.0, 0.0, 1.0)]
        weights = [0.5, 0.4, 0.3, 0.9]
        M, _ = accumulate_qwa_matrix(weights, quats)
        q, ok, iters = power_iteration_max_eigenvec_4x4(M, max_iter=50)
        self.assertTrue(ok)
        self.assertLessEqual(iters, 25)


class T5_TwoSampleEqualWeight(unittest.TestCase):
    """Equal-weight average of two quats = their slerp midpoint."""

    def test_identity_and_90x(self):
        q1 = (0.0, 0.0, 0.0, 1.0)
        s45, c45 = math.sin(math.pi / 4), math.cos(math.pi / 4)
        q2 = (s45, 0.0, 0.0, c45)
        M, _ = accumulate_qwa_matrix([1.0, 1.0], [q1, q2])
        q_avg, status = compute_qwa_for_group(M)
        self.assertEqual(status, 'OK')
        # Slerp midpoint between identity and 90°-X is 45°-X:
        # (sin(π/8), 0, 0, cos(π/8))
        expected = (math.sin(math.pi / 8), 0.0, 0.0, math.cos(math.pi / 8))
        dot = sum(a*b for a, b in zip(q_avg, expected))
        self.assertGreater(abs(dot), 1.0 - 1e-6)

    def test_result_is_unit(self):
        rng = np.random.default_rng(0x5EED)
        q1 = _rand_unit_quat(rng)
        q2 = _rand_unit_quat(rng)
        M, _ = accumulate_qwa_matrix([0.7, 0.3], [q1, q2])
        q_avg, _ = compute_qwa_for_group(M)
        n = math.sqrt(sum(c*c for c in q_avg))
        self.assertAlmostEqual(n, 1.0, places=10)


class T6_SignCanonicalisation(unittest.TestCase):
    """q_w >= 0 enforced on output."""

    def test_negative_hemisphere_input_flipped(self):
        # Build M from a single -q_w sample; eigenvector direction is
        # arbitrary but final output must have w >= 0.
        q = (0.1, 0.2, 0.3, -0.9273618495)  # q_w < 0
        n = math.sqrt(sum(c*c for c in q))
        q = tuple(c / n for c in q)
        M, _ = accumulate_qwa_matrix([1.0], [q])
        q_out, _ = compute_qwa_for_group(M)
        self.assertGreaterEqual(q_out[3], 0.0)


class T7_Degenerate(unittest.TestCase):
    """Zero-mass M and manual zero trace both return identity."""

    def test_zero_mass_all_zero_phi(self):
        quats = [(0.1, 0.2, 0.3, 0.9), (0.4, 0.5, 0.6, 0.7)]
        quats = [tuple(c / math.sqrt(sum(ci*ci for ci in q)) for c in q)
                 for q in quats]
        M, _ = accumulate_qwa_matrix([0.0, 0.0], quats)
        q_out, status = compute_qwa_for_group(M)
        self.assertEqual(q_out, QWA_IDENTITY)
        self.assertEqual(status, 'ZERO_MASS')

    def test_explicitly_zero_matrix(self):
        q_out, status = compute_qwa_for_group(np.zeros((4, 4)))
        self.assertEqual(q_out, QWA_IDENTITY)
        self.assertEqual(status, 'ZERO_MASS')

    def test_tiny_trace_still_degenerate(self):
        M = np.eye(4) * 1e-15
        q_out, status = compute_qwa_for_group(M)
        self.assertEqual(q_out, QWA_IDENTITY)
        self.assertEqual(status, 'ZERO_MASS')


class T8_ConfigValidation(unittest.TestCase):
    """Out-of-range / overlap / scale-conflict groups dropped silently."""

    def test_out_of_range_dropped(self):
        valid, mask, invalid = resolve_quaternion_groups(
            raw_starts=[10], output_count=8, is_scale_arr=[False]*8)
        self.assertEqual(valid, [])
        self.assertFalse(any(mask))
        self.assertTrue(invalid)

    def test_negative_start_dropped(self):
        valid, mask, invalid = resolve_quaternion_groups(
            raw_starts=[-1, 0], output_count=4, is_scale_arr=[False]*4)
        self.assertEqual(valid, [0])
        self.assertEqual(mask, [True] * 4)
        self.assertTrue(invalid)

    def test_overlap_dropped(self):
        # Two groups starting at 0 and 2 — overlap on slots 2, 3.
        valid, mask, invalid = resolve_quaternion_groups(
            raw_starts=[0, 2], output_count=6, is_scale_arr=[False]*6)
        self.assertEqual(valid, [0])
        self.assertEqual(mask, [True, True, True, True, False, False])
        self.assertTrue(invalid)

    def test_scale_conflict_drops_whole_group(self):
        # Scale flag on output[2] → group [0..4) collides.
        is_scale = [False, False, True, False, False, False]
        valid, mask, invalid = resolve_quaternion_groups(
            raw_starts=[0], output_count=6, is_scale_arr=is_scale)
        self.assertEqual(valid, [])
        self.assertFalse(any(mask))
        self.assertTrue(invalid)


class T9_ZeroRegression(unittest.TestCase):
    """Empty quat-group spec → scalar path entirely unaffected.
    is_quat_member must be all-False."""

    def test_empty_spec(self):
        valid, mask, invalid = resolve_quaternion_groups(
            raw_starts=[], output_count=10, is_scale_arr=[False]*10)
        self.assertEqual(valid, [])
        self.assertEqual(mask, [False] * 10)
        self.assertFalse(invalid)


class T10_ScaleQuatMutualExclusion(unittest.TestCase):
    """Q5 contract: scale∩quat ⇒ both semantics skipped on those slots.
    No silent override either way."""

    def test_scale_flags_preserved_after_group_rejection(self):
        # User configured: output[0..3] = quat group + outputIsScale[2] = True.
        # Our spec: reject the group. The scale flag on output[2] stays
        # true for the M1.2 path to honour — we do NOT silently clear it.
        is_scale = [False, False, True, False]
        valid, mask, invalid = resolve_quaternion_groups(
            raw_starts=[0], output_count=4, is_scale_arr=is_scale)
        self.assertEqual(valid, [])
        # is_scale_arr is NOT mutated (resolve_quaternion_groups reads-only).
        self.assertEqual(is_scale, [False, False, True, False])
        # is_quat_member is all-False → M1.2 scalar path runs on all 4.
        self.assertEqual(mask, [False] * 4)

    def test_group_disables_when_any_slot_is_scale(self):
        # Edge coverage: scale flag on the LAST slot of the group.
        is_scale = [False, False, False, True]
        valid, _, invalid = resolve_quaternion_groups(
            raw_starts=[0], output_count=4, is_scale_arr=is_scale)
        self.assertEqual(valid, [])
        self.assertTrue(invalid)


class T11_NegativePhiClamp(unittest.TestCase):
    """Negative kernel activations clipped to 0 for PSD preservation.
    Q8: scalar path is unaffected (not tested here — that's M1.2 T* turf)."""

    def test_clamp_flag_triggers(self):
        rng = np.random.default_rng(0xBAAD)
        quats = [_rand_unit_quat(rng) for _ in range(3)]
        phis_with_neg = [-0.1, 0.8, 0.5]
        phis_clipped  = [ 0.0, 0.8, 0.5]
        M1, any_clipped = accumulate_qwa_matrix(phis_with_neg, quats)
        M2, any_clipped_b = accumulate_qwa_matrix(phis_clipped, quats)
        self.assertTrue(any_clipped)
        self.assertFalse(any_clipped_b)
        np.testing.assert_allclose(M1, M2, atol=1e-12)

    def test_without_clamp_matrix_differs(self):
        """Sanity: unclamped path produces DIFFERENT matrix → demonstrates
        the clamp is semantically meaningful, not just hygienic."""
        rng = np.random.default_rng(0xBEEF)
        quats = [_rand_unit_quat(rng) for _ in range(3)]
        phis_with_neg = [-0.1, 0.8, 0.5]
        M_clipped, _    = accumulate_qwa_matrix(phis_with_neg, quats,
                                                clip_negative=True)
        M_unclipped, _  = accumulate_qwa_matrix(phis_with_neg, quats,
                                                clip_negative=False)
        # Matrices should differ when any phi is negative.
        self.assertGreater(float(np.max(np.abs(M_clipped - M_unclipped))), 1e-6)

    def test_unclipped_matrix_not_psd(self):
        """Proof-of-concept that unclamped M can lose PSD: eigenvalues
        from the unclamped path can include a negative one for adversarial
        samples / weights."""
        # Single negative-weight sample → M = -w · q q^T with w > 0 is
        # rank-1 negative-semidefinite (eigenvalues ≤ 0).
        q = (0.1, 0.2, 0.3, 0.9273618)
        n = math.sqrt(sum(c*c for c in q))
        q = tuple(c / n for c in q)
        M, _ = accumulate_qwa_matrix([-0.5], [q], clip_negative=False)
        eigs = np.linalg.eigvalsh(M)
        self.assertLess(float(eigs.min()), 0.0)


if __name__ == "__main__":
    unittest.main()
