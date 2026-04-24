"""M1.1 — Distance computation spec tests.

Tests are written against the Python reference mirror in `_reference_impl.py`.
They define the mathematical contract the C++ helpers added to
`source/RBFtools.cpp` must satisfy. M1.5 will re-exercise this contract
through a live mayapy plugin load; see tests/README.md.
"""

from __future__ import annotations

import math
import random
import unittest

from _reference_impl import (
    TWO_PI,
    get_angle,
    get_matrix_mode_linear_distance,
    get_quat_distance,
    get_radius,
    twist_wrap,
)


class T1_AxisVectorAngle(unittest.TestCase):
    """3-D axis-vector angle is unsigned [0, pi] — no flip concern."""

    def test_zero(self):
        self.assertAlmostEqual(get_angle([1, 0, 0], [1, 0, 0]), 0.0, places=12)

    def test_ninety(self):
        self.assertAlmostEqual(get_angle([1, 0, 0], [0, 1, 0]), math.pi / 2, places=12)

    def test_one_eighty(self):
        self.assertAlmostEqual(get_angle([1, 0, 0], [-1, 0, 0]), math.pi, places=12)

    def test_range_always_nonneg(self):
        rng = random.Random(0xBEEF)
        for _ in range(200):
            v1 = [rng.uniform(-1, 1) for _ in range(3)]
            v2 = [rng.uniform(-1, 1) for _ in range(3)]
            if all(abs(x) < 1e-9 for x in v1) or all(abs(x) < 1e-9 for x in v2):
                continue
            a = get_angle(v1, v2)
            self.assertGreaterEqual(a, 0.0)
            self.assertLessEqual(a, math.pi + 1e-12)


class T2_TwistWrapFlipBug(unittest.TestCase):
    """Regression: twist going +179 deg -> -179 deg must register as ~2 deg, not ~358 deg."""

    def test_near_pi_seam(self):
        tau_plus = math.radians(179.0)
        tau_minus = math.radians(-179.0)
        d = twist_wrap(tau_plus, tau_minus)
        self.assertAlmostEqual(d, math.radians(2.0), places=9)

    def test_exact_pi(self):
        # Maximum wrap distance is exactly pi.
        self.assertAlmostEqual(twist_wrap(math.pi, 0.0), math.pi, places=12)
        self.assertAlmostEqual(twist_wrap(-math.pi, 0.0), math.pi, places=12)

    def test_matrix_mode_single_driver_seam(self):
        # Single driver block, only twist differs by 2 deg across the +/- pi seam.
        v1 = [1.0, 0.0, 0.0, math.radians(179.0)]
        v2 = [1.0, 0.0, 0.0, math.radians(-179.0)]
        d = get_matrix_mode_linear_distance(v1, v2)
        # Expected: sqrt(0 + wrap^2) = 2 deg in radians.
        self.assertAlmostEqual(d, math.radians(2.0), places=9)

    def test_matrix_mode_vs_naive_radius_at_seam(self):
        # The original getRadius would have reported ~358 deg -> near 2*pi*... -> ~6.24 rad.
        v1 = [1.0, 0.0, 0.0, math.radians(179.0)]
        v2 = [1.0, 0.0, 0.0, math.radians(-179.0)]
        naive = get_radius(v1, v2)
        fixed = get_matrix_mode_linear_distance(v1, v2)
        self.assertGreater(naive, 6.0)  # ~358 deg = ~6.248 rad (the bug)
        self.assertLess(fixed, 0.1)     # ~2 deg = ~0.035 rad (the fix)


class T3_MultiDriverBlockIndependence(unittest.TestCase):
    """Perturbing driver[k]'s twist must only change block k's contribution."""

    def _make_two_driver(self, tau0_a, tau0_b, tau1_a, tau1_b):
        va = [1.0, 0.0, 0.0, tau0_a, 0.0, 1.0, 0.0, tau1_a]
        vb = [1.0, 0.0, 0.0, tau0_b, 0.0, 1.0, 0.0, tau1_b]
        return va, vb

    def test_only_block1_changes(self):
        # Block 0 identical; block 1 twist differs by +30 deg vs +60 deg.
        va, vb_30 = self._make_two_driver(0.5, 0.5, 0.0, math.radians(30.0))
        _, vb_60 = self._make_two_driver(0.5, 0.5, 0.0, math.radians(60.0))

        d_block1_30 = get_matrix_mode_linear_distance(va, vb_30)
        d_block1_60 = get_matrix_mode_linear_distance(va, vb_60)

        # Expected pure block-1 twist-wrap contribution: 30 vs 60 deg.
        self.assertAlmostEqual(d_block1_30, math.radians(30.0), places=9)
        self.assertAlmostEqual(d_block1_60, math.radians(60.0), places=9)

    def test_l2_aggregation(self):
        # Block 0 twist delta 30 deg, block 1 twist delta 40 deg.
        # L2 aggregation expects sqrt(30^2 + 40^2) deg = 50 deg.
        va, vb = self._make_two_driver(
            0.0, math.radians(30.0),
            0.0, math.radians(40.0),
        )
        d = get_matrix_mode_linear_distance(va, vb)
        self.assertAlmostEqual(d, math.radians(50.0), places=9)


class T4_L2ScaleRegression(unittest.TestCase):
    """For all twist deltas within (-pi, pi], the new distance must equal the
    old plain-Euclidean getRadius to floating-point noise. Protects against
    the wrap formula silently rescaling the normal operating range."""

    def test_random_non_seam_cases(self):
        rng = random.Random(0xC0FFEE)
        max_abs_err = 0.0
        for _ in range(2000):
            driver_count = rng.randint(1, 4)
            n = 4 * driver_count
            va = []
            vb = []
            for k in range(driver_count):
                # xyz arbitrary
                for _i in range(3):
                    va.append(rng.uniform(-3.0, 3.0))
                    vb.append(rng.uniform(-3.0, 3.0))
                # twist: generate two values whose ABSOLUTE delta is strictly
                # less than pi so wrap is a no-op.
                t1 = rng.uniform(-math.pi + 1e-6, math.pi - 1e-6)
                # delta in (-pi, pi) exclusive:
                delta = rng.uniform(-math.pi + 1e-6, math.pi - 1e-6)
                # Clip so t1 + delta also stays away from wrap ambiguity:
                t2 = t1 + delta
                va.append(t1)
                vb.append(t2)

            old = get_radius(va, vb)
            new = get_matrix_mode_linear_distance(va, vb)
            err = abs(old - new)
            max_abs_err = max(max_abs_err, err)
            self.assertLess(err, 1e-10,
                            msg=f"scale regression: |new - old|={err} va={va} vb={vb}")

        # Sanity: in the non-seam regime max err should be tiny.
        self.assertLess(max_abs_err, 1e-10)


class T5_GetQuatDistanceUnwired(unittest.TestCase):
    """getQuatDistance is shipped but unwired; spec-only tests here."""

    def test_identical(self):
        q = [0.0, 0.0, 0.0, 1.0]
        self.assertAlmostEqual(get_quat_distance(q, q), 0.0, places=12)

    def test_antipodal_same_rotation(self):
        raw = [0.1, 0.2, 0.3, 0.9]
        n = math.sqrt(sum(c * c for c in raw))
        q = [c / n for c in raw]
        neg = [-c for c in q]
        # d = 1 - |q.(-q)| = 1 - |-1| = 0
        self.assertAlmostEqual(get_quat_distance(q, neg), 0.0, places=12)

    def test_ninety_deg_rotation(self):
        # q1 = identity, q2 = 90 deg about x. dot = cos(45 deg).
        q1 = [0.0, 0.0, 0.0, 1.0]
        q2 = [math.sin(math.pi / 4), 0.0, 0.0, math.cos(math.pi / 4)]
        expected = 1.0 - abs(math.cos(math.pi / 4))
        self.assertAlmostEqual(get_quat_distance(q1, q2), expected, places=12)


if __name__ == "__main__":
    unittest.main()
