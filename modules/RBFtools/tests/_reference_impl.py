"""Python mirror of the C++ distance helpers added in M1.1.

These functions MUST stay behaviourally identical to the C++ implementations in
`source/RBFtools.cpp`. They exist so the pure-math contract can be exercised by
pytest without spinning up Maya. When M1.5 wires up `mayapy` integration tests,
the C++ outputs are expected to match these to floating-point noise.
"""

from __future__ import annotations

import math
from typing import Sequence

TWO_PI = 2.0 * math.pi


def twist_wrap(tau1: float, tau2: float) -> float:
    """Fold |tau1 - tau2| onto the 2*pi circle. Mirrors RBFtools::twistWrap."""
    d = math.fabs(tau1 - tau2)
    d = math.fmod(d, TWO_PI)
    if d > math.pi:
        d = TWO_PI - d
    return d


def get_radius(vec1: Sequence[float], vec2: Sequence[float]) -> float:
    """Plain Euclidean. Mirrors RBFtools::getRadius."""
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(vec1, vec2)))


def get_matrix_mode_linear_distance(
    vec1: Sequence[float], vec2: Sequence[float]
) -> float:
    """Wrap-aware L2 for Matrix-mode [vx, vy, vz, twist] * driverCount vectors.

    Mirrors RBFtools::getMatrixModeLinearDistance.
    """
    assert len(vec1) == len(vec2), "vectors must be same length"
    assert len(vec1) % 4 == 0 and len(vec1) >= 4, "length must be positive multiple of 4"
    sum_sq = 0.0
    blocks = len(vec1) // 4
    for k in range(blocks):
        base = k * 4
        for i in range(3):
            d = vec1[base + i] - vec2[base + i]
            sum_sq += d * d
        w = twist_wrap(vec1[base + 3], vec2[base + 3])
        sum_sq += w * w
    return math.sqrt(sum_sq)


def get_angle(vec1: Sequence[float], vec2: Sequence[float]) -> float:
    """Unsigned angle between 3-D vectors. Mirrors RBFtools::getAngle (MVector::angle)."""
    assert len(vec1) == 3 and len(vec2) == 3
    n1 = math.sqrt(sum(c * c for c in vec1))
    n2 = math.sqrt(sum(c * c for c in vec2))
    if n1 == 0.0 or n2 == 0.0:
        return 0.0
    dot = sum(a * b for a, b in zip(vec1, vec2)) / (n1 * n2)
    dot = max(-1.0, min(1.0, dot))
    return math.acos(dot)


def get_quat_distance(q1: Sequence[float], q2: Sequence[float]) -> float:
    """d(q1, q2) = 1 - |q1 . q2|. Mirrors RBFtools::getQuatDistance."""
    n = min(len(q1), len(q2), 4)
    dot = sum(q1[i] * q2[i] for i in range(n))
    return 1.0 - math.fabs(dot)
