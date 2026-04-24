"""M1.4 — Regularized solver with Cholesky + GE fallback.

Mirrors RBFtools::compute() M1.4 path:

    linMat += λI                     (absolute, addendum §M1.4)
    if solverMethod == Auto and lastSolveMethod == Cholesky:
        L, ok = Cholesky(linMat)
        if ok: solve per dim via choleskySolve; lastSolveMethod = 0
    if not solved:
        per dim GE;                    lastSolveMethod = 1

``solverMethod`` change resets ``lastSolveMethod`` (T9).
"""

from __future__ import annotations

import math
import unittest

import numpy as np

from _reference_impl import (
    SolverDispatcher,
    apply_absolute_lambda,
    cholesky_decompose,
    cholesky_solve_single,
)


def _random_spd(n, rng, scale=1.0):
    A = rng.standard_normal((n, n))
    return (A @ A.T) + n * np.eye(n) * scale


def _np_solve(A, b):
    return np.linalg.solve(A, b)


class T1_CholeskyBasic(unittest.TestCase):
    """A = L Lᵀ on SPD matrices; back-sub recovers np.linalg.solve."""

    def test_small_identity(self):
        K = np.eye(3) * 4.0
        L, ok = cholesky_decompose(K)
        self.assertTrue(ok)
        np.testing.assert_allclose(L @ L.T, K, atol=1e-12)

    def test_random_spd_multi_trial(self):
        rng = np.random.default_rng(0xA11CE)
        for _ in range(20):
            n = int(rng.integers(2, 10))
            K = _random_spd(n, rng)
            L, ok = cholesky_decompose(K)
            self.assertTrue(ok)
            np.testing.assert_allclose(L @ L.T, K, atol=1e-9)

            b = rng.standard_normal(n)
            x_ref = np.linalg.solve(K, b)
            x_got = cholesky_solve_single(L, b)
            np.testing.assert_allclose(x_got, x_ref, atol=1e-9)

    def test_upper_triangle_zeroed(self):
        # Mirrors the C++ contract that L is clean lower-triangular.
        K = np.array([[4.0, 2.0], [2.0, 3.0]])
        L, ok = cholesky_decompose(K)
        self.assertTrue(ok)
        self.assertEqual(L[0, 1], 0.0)


class T2_NonSPDDetection(unittest.TestCase):
    """cholesky() returns False on non-SPD inputs (negative pivot)."""

    def test_negative_identity(self):
        L, ok = cholesky_decompose(-np.eye(3))
        self.assertFalse(ok)

    def test_indefinite(self):
        # Eigenvalues: 3, -1 -> indefinite, cholesky must fail.
        K = np.array([[1.0, 2.0], [2.0, 1.0]])
        L, ok = cholesky_decompose(K)
        self.assertFalse(ok)

    def test_zero_diagonal_fails(self):
        # Exactly zero pivot -> <= 0.0 guard trips; return False.
        K = np.zeros((3, 3))
        L, ok = cholesky_decompose(K)
        self.assertFalse(ok)


class T3_AbsoluteLambdaNotAdaptive(unittest.TestCase):
    """λ is added as an absolute value to the diagonal — it is NOT
    scale-adaptive, so it works uniformly on Linear / Thin Plate kernels
    where the diagonal is 0."""

    def test_linear_kernel_diagonal_zero_gets_regularized(self):
        # Linear kernel φ(r) = r -> K[i,i] = 0. Scale-adaptive λ=tr(K)/N
        # would be 0 (bug); absolute λ=1e-8 gives us 1e-8 on the diagonal.
        K_linear = np.array([[0.0, 0.8, 0.6],
                             [0.8, 0.0, 0.7],
                             [0.6, 0.7, 0.0]])
        K_reg = apply_absolute_lambda(K_linear, 1.0e-8)
        for i in range(3):
            self.assertAlmostEqual(K_reg[i, i], 1.0e-8, places=15)

    def test_absolute_value_does_not_depend_on_kernel_magnitude(self):
        # Two kernels of different magnitudes get the same absolute λ
        # on the diagonal — the user's λ number is what they see in the
        # attribute, no hidden rescaling.
        K_big   = np.eye(3) * 1000.0
        K_small = np.eye(3) * 0.001
        K_big_r   = apply_absolute_lambda(K_big,   1.0e-6)
        K_small_r = apply_absolute_lambda(K_small, 1.0e-6)
        self.assertAlmostEqual(K_big_r[0, 0]   - K_big[0, 0],   1.0e-6)
        self.assertAlmostEqual(K_small_r[0, 0] - K_small[0, 0], 1.0e-6)

    def test_lambda_zero_is_noop(self):
        K = np.array([[4.0, 2.0], [2.0, 3.0]])
        K_r = apply_absolute_lambda(K, 0.0)
        np.testing.assert_array_equal(K_r, K)


class T4_LambdaIdentityAndPerturbation(unittest.TestCase):
    """λ = 0 -> exact np.linalg.solve; small λ -> small perturbation."""

    def test_lambda_zero_matches_np_solve(self):
        rng = np.random.default_rng(0xBEEF)
        K = _random_spd(5, rng)
        Y = rng.standard_normal((5, 3))
        W_ref = np.linalg.solve(K, Y)
        L, ok = cholesky_decompose(apply_absolute_lambda(K, 0.0))
        self.assertTrue(ok)
        W_got = np.column_stack([cholesky_solve_single(L, Y[:, c])
                                 for c in range(Y.shape[1])])
        np.testing.assert_allclose(W_got, W_ref, atol=1e-9)

    def test_small_lambda_bounded_perturbation(self):
        rng = np.random.default_rng(0xCAFE)
        K = _random_spd(6, rng)
        Y = rng.standard_normal((6, 2))
        W_unreg = np.linalg.solve(K, Y)

        lam = 1e-8
        K_r = apply_absolute_lambda(K, lam)
        W_reg = np.linalg.solve(K_r, Y)

        # ||W_reg - W_unreg|| is O(λ) for moderately conditioned K.
        self.assertLess(float(np.max(np.abs(W_reg - W_unreg))), 1e-5)


class T5_DispatcherAutoAndForceGE(unittest.TestCase):
    """Auto on SPD -> Cholesky; Auto on non-SPD -> GE; ForceGE skips Cholesky."""

    def setUp(self):
        self.rng = np.random.default_rng(0xDEAD)

    def test_spd_matrix_uses_cholesky(self):
        K = _random_spd(5, self.rng)
        Y = self.rng.standard_normal((5, 2))
        d = SolverDispatcher()
        W = d.solve(K, Y, 1e-10,
                    solver_method_val=SolverDispatcher.MODE_AUTO,
                    ge_solve=_np_solve)
        self.assertEqual(d.last_solve_method, SolverDispatcher.TIER_CHOLESKY)
        np.testing.assert_allclose(W, np.linalg.solve(K + 1e-10 * np.eye(5), Y),
                                   atol=1e-9)

    def test_non_spd_matrix_falls_back_to_ge(self):
        # Linear kernel layout: zero diagonal, symmetric off-diagonal,
        # indefinite -> Cholesky must fail, GE must kick in.
        K = np.array([[0.0, 0.5, 0.3],
                      [0.5, 0.0, 0.4],
                      [0.3, 0.4, 0.0]])
        Y = self.rng.standard_normal((3, 2))
        d = SolverDispatcher()
        W = d.solve(K, Y, 0.0,
                    solver_method_val=SolverDispatcher.MODE_AUTO,
                    ge_solve=_np_solve)
        self.assertEqual(d.last_solve_method, SolverDispatcher.TIER_GE)
        np.testing.assert_allclose(W, np.linalg.solve(K, Y), atol=1e-9)

    def test_force_ge_skips_cholesky_even_on_spd(self):
        K = _random_spd(4, self.rng)
        Y = self.rng.standard_normal((4, 1))
        d = SolverDispatcher()
        W = d.solve(K, Y, 1e-10,
                    solver_method_val=SolverDispatcher.MODE_FORCE_GE,
                    ge_solve=_np_solve)
        self.assertEqual(d.last_solve_method, SolverDispatcher.TIER_GE)
        np.testing.assert_allclose(W, np.linalg.solve(K + 1e-10 * np.eye(4), Y),
                                   atol=1e-9)

    def test_sticky_ge_on_known_nonspd(self):
        """After GE fallback, subsequent Auto calls still prefer GE — the
        cache is sticky on non-SPD kernels."""
        K_nspd = np.array([[0.0, 0.5], [0.5, 0.0]])
        Y = np.array([[1.0], [2.0]])
        d = SolverDispatcher()
        d.solve(K_nspd, Y, 0.0,
                solver_method_val=SolverDispatcher.MODE_AUTO,
                ge_solve=_np_solve)
        self.assertEqual(d.last_solve_method, SolverDispatcher.TIER_GE)
        # A subsequent call stays on GE without re-probing Cholesky.
        d.solve(K_nspd, Y, 0.0,
                solver_method_val=SolverDispatcher.MODE_AUTO,
                ge_solve=_np_solve)
        self.assertEqual(d.last_solve_method, SolverDispatcher.TIER_GE)


class T6_ThinPlateRegularizationGate(unittest.TestCase):
    """Thin Plate kernel: conditionally positive definite. Without λ,
    Cholesky must fail (cache goes to GE). With λ large enough to push
    the matrix into SPD, Cholesky succeeds."""

    def _thin_plate_like(self):
        # Hand-crafted TP-like: zero diagonal, symmetric off-diagonal
        # with values that put at least one eigenvalue negative.
        K = np.array([[0.0, 0.4, 0.6, 0.3],
                      [0.4, 0.0, 0.5, 0.2],
                      [0.6, 0.5, 0.0, 0.7],
                      [0.3, 0.2, 0.7, 0.0]])
        eigs = np.linalg.eigvalsh(K)
        # Sanity: at least one eigenvalue must be negative for this to
        # be a non-SPD test; if numpy produces a fluke all-positive, bail.
        if eigs.min() >= 0.0:
            self.skipTest("hand-crafted TP matrix happened to be SPD")
        return K

    def test_unregularized_fails_cholesky(self):
        K = self._thin_plate_like()
        _, ok = cholesky_decompose(K)
        self.assertFalse(ok)

    def test_regularized_enough_succeeds(self):
        # Shift by |λ_min| + ε -> pushes all eigenvalues strictly > 0.
        K = self._thin_plate_like()
        eigs = np.linalg.eigvalsh(K)
        lam = -eigs.min() + 1e-6
        K_r = apply_absolute_lambda(K, lam)
        _, ok = cholesky_decompose(K_r)
        self.assertTrue(ok)

    def test_dispatcher_gates_cholesky_on_lambda(self):
        K = self._thin_plate_like()
        Y = np.ones((4, 1))
        eigs = np.linalg.eigvalsh(K)
        lam = -eigs.min() + 1e-6

        # Without λ: Cholesky fails, dispatcher falls back to GE.
        d = SolverDispatcher()
        d.solve(K, Y, 0.0,
                solver_method_val=SolverDispatcher.MODE_AUTO,
                ge_solve=_np_solve)
        self.assertEqual(d.last_solve_method, SolverDispatcher.TIER_GE)

        # With λ big enough: FRESH dispatcher should land on Cholesky.
        # (The sticky cache of the previous dispatcher would keep GE.)
        d2 = SolverDispatcher()
        d2.solve(K, Y, lam,
                 solver_method_val=SolverDispatcher.MODE_AUTO,
                 ge_solve=_np_solve)
        self.assertEqual(d2.last_solve_method, SolverDispatcher.TIER_CHOLESKY)


class T7_MultiRHSPerformanceEquivalence(unittest.TestCase):
    """Single Cholesky + m back-subs must equal m independent np.linalg.solve."""

    def test_four_rhs(self):
        rng = np.random.default_rng(0xF00D)
        K = _random_spd(7, rng)
        Y = rng.standard_normal((7, 4))
        L, ok = cholesky_decompose(K)
        self.assertTrue(ok)
        W_chol = np.column_stack([cholesky_solve_single(L, Y[:, c])
                                  for c in range(Y.shape[1])])
        W_ref = np.column_stack([np.linalg.solve(K, Y[:, c])
                                 for c in range(Y.shape[1])])
        np.testing.assert_allclose(W_chol, W_ref, atol=1e-9)


class T8_DegenerateNearDuplicatePoses(unittest.TestCase):
    """Two nearly identical poses produce an ill-conditioned kernel:
    Cholesky may fail, but GE fallback + λ must still return a finite W
    (no NaN / Inf). Caller sees a bounded answer instead of a crash."""

    def test_duplicate_rows_kernel_with_lambda(self):
        # Construct: a Gaussian-ish activation matrix where rows 0 and
        # 1 are nearly identical (simulates two duplicate poses).
        K = np.array([
            [1.0, 0.999, 0.2, 0.1],
            [0.999, 1.0, 0.2, 0.1],
            [0.2,   0.2, 1.0, 0.5],
            [0.1,   0.1, 0.5, 1.0],
        ])
        Y = np.array([[1.0], [1.0], [0.5], [0.2]])
        d = SolverDispatcher()
        W = d.solve(K, Y, 1e-6,
                    solver_method_val=SolverDispatcher.MODE_AUTO,
                    ge_solve=_np_solve)
        self.assertTrue(np.all(np.isfinite(W)))


class T9_SolverMethodChangeResetsCache(unittest.TestCase):
    """User flipping solverMethod (Auto <-> ForceGE) must clear
    lastSolveMethod, otherwise ForceGE contamination poisons subsequent
    Auto runs."""

    def setUp(self):
        self.rng = np.random.default_rng(0x1337)
        self.K = _random_spd(4, self.rng)
        self.Y = self.rng.standard_normal((4, 1))

    def test_force_ge_then_auto_retries_cholesky(self):
        d = SolverDispatcher()
        # Under ForceGE, cache becomes TIER_GE.
        d.solve(self.K, self.Y, 1e-10,
                solver_method_val=SolverDispatcher.MODE_FORCE_GE,
                ge_solve=_np_solve)
        self.assertEqual(d.last_solve_method, SolverDispatcher.TIER_GE)

        # User flips back to Auto -> cache must reset to TIER_CHOLESKY
        # BEFORE the solve, so Cholesky gets another chance on an SPD K.
        d.solve(self.K, self.Y, 1e-10,
                solver_method_val=SolverDispatcher.MODE_AUTO,
                ge_solve=_np_solve)
        self.assertEqual(d.last_solve_method, SolverDispatcher.TIER_CHOLESKY)

    def test_no_reset_on_repeated_same_mode(self):
        d = SolverDispatcher()
        d.solve(self.K, self.Y, 1e-10,
                solver_method_val=SolverDispatcher.MODE_AUTO,
                ge_solve=_np_solve)
        d.solve(self.K, self.Y, 1e-10,
                solver_method_val=SolverDispatcher.MODE_AUTO,
                ge_solve=_np_solve)
        # prev_solver_method_val unchanged, last cache respected.
        self.assertEqual(d.last_solve_method, SolverDispatcher.TIER_CHOLESKY)

    def test_auto_non_spd_stick_then_force_ge_then_auto(self):
        """Non-SPD K under Auto -> GE sticks. ForceGE keeps it at GE.
        Flipping back to Auto resets the cache so Cholesky gets re-probed
        on the new train (which would succeed if K changed to SPD)."""
        K_nspd = np.array([[0.0, 0.5], [0.5, 0.0]])
        Y = np.array([[1.0], [2.0]])
        d = SolverDispatcher()
        d.solve(K_nspd, Y, 0.0,
                solver_method_val=SolverDispatcher.MODE_AUTO,
                ge_solve=_np_solve)
        self.assertEqual(d.last_solve_method, SolverDispatcher.TIER_GE)

        d.solve(K_nspd, Y, 0.0,
                solver_method_val=SolverDispatcher.MODE_FORCE_GE,
                ge_solve=_np_solve)
        self.assertEqual(d.last_solve_method, SolverDispatcher.TIER_GE)

        # Flip back to Auto: cache reset to Cholesky probe; kernel now is
        # still non-SPD so it drops back to GE — but the key is it DID
        # try Cholesky first (cache was reset).
        d.solve(K_nspd, Y, 0.0,
                solver_method_val=SolverDispatcher.MODE_AUTO,
                ge_solve=_np_solve)
        self.assertEqual(d.last_solve_method, SolverDispatcher.TIER_GE)
        # And prev_solver_method_val tracks the current mode:
        self.assertEqual(d.prev_solver_method_val, SolverDispatcher.MODE_AUTO)


if __name__ == "__main__":
    unittest.main()
