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


# ----------------------------------------------------------------------
# M1.2 — Output baseline (Base Value + outputIsScale)
# ----------------------------------------------------------------------

# Exact attribute names matched by _is_scale_attr. Mirrors
# constants.SCALE_ATTR_NAMES so the pure-math test file stays free of
# Maya imports.
SCALE_ATTR_NAMES = frozenset({
    "scaleX", "scaleY", "scaleZ",
    "sx", "sy", "sz",
})


def is_scale_attr(attr_name: str) -> bool:
    """Mirror of core._is_scale_attr."""
    return attr_name in SCALE_ATTR_NAMES


def resolve_anchor(base_value: float, is_scale: bool) -> float:
    """Per-dimension training/inference anchor.

    Scale channels always anchor at 1.0 regardless of base_value;
    other channels use base_value. Mirrors the C++ compute() branch.
    """
    return 1.0 if is_scale else base_value


def subtract_baseline(y, base_values, is_scale_flags):
    """Return ``Y - anchor`` per output dimension c (column-wise).

    Y shape: (N_poses, N_outputs). Mirrors the C++ subtract loop before
    ``solveMat.solve``.
    """
    import numpy as np
    y = np.asarray(y, dtype=float).copy()
    for c in range(y.shape[1]):
        anchor = resolve_anchor(base_values[c], is_scale_flags[c])
        if anchor != 0.0:
            y[:, c] -= anchor
    return y


def readd_baseline(delta, base_values, is_scale_flags):
    """Return ``delta + anchor`` per output dimension.

    Mirrors the C++ add-back loop *after* allowNegative / interpolateWeight
    / scaleVal have operated on the delta.
    """
    import numpy as np
    out = np.asarray(delta, dtype=float).copy()
    for c in range(out.shape[0] if out.ndim == 1 else out.shape[1]):
        anchor = resolve_anchor(base_values[c], is_scale_flags[c])
        if out.ndim == 1:
            out[c] += anchor
        else:
            out[:, c] += anchor
    return out


class BaselineDirtyTracker:
    """Mirror of the C++ prevBaseValueArr / prevOutputIsScaleArr cache.

    `update()` compares the supplied arrays to the previous snapshot;
    returns True iff anything changed (→ C++ sets evalInput = true to
    force a re-solve against the new anchors).
    """

    def __init__(self):
        self._prev_base = None
        self._prev_scale = None

    def update(self, base_values, is_scale_flags):
        base = list(base_values)
        scale = [bool(s) for s in is_scale_flags]
        changed = (base != self._prev_base) or (scale != self._prev_scale)
        if changed:
            self._prev_base = base
            self._prev_scale = scale
        return changed


# ----------------------------------------------------------------------
# M1.3 — Driver Clamp (per-dim bounding box + inflation)
# ----------------------------------------------------------------------


def compute_bounds(poses, skip_twist=False, block=4):
    """Per-dim min/max over a batch of pose input vectors.

    Parameters
    ----------
    poses : list[list[float]]
        Rows = poses, columns = input dimensions. Must be rectangular.
    skip_twist : bool
        Matrix-mode flag. When True, indices where ``j % block == 3``
        (the twist slot in each [vx, vy, vz, twist] block) get
        ``(lo, hi) = (0.0, 0.0)`` as a sentinel that tells
        :func:`apply_clamp` to pass the value through untouched.
        Bounds on non-twist dims are populated normally.
    block : int
        Block stride for Matrix-mode layout. Ignored when
        ``skip_twist=False``.

    Returns
    -------
    (list[float], list[float])
        ``(mins, maxs)``. Both length == column count.
    """
    if not poses:
        return [], []
    n = len(poses[0])
    mins = [0.0] * n
    maxs = [0.0] * n
    for j in range(n):
        is_twist = skip_twist and (j % block == 3)
        if is_twist:
            continue
        col = [row[j] for row in poses]
        mins[j] = min(col)
        maxs[j] = max(col)
    return mins, maxs


def apply_clamp(driver, mins, maxs, inflation=0.0,
                skip_twist=False, block=4):
    """Clip *driver* per-dim to ``[min - alpha*r, max + alpha*r]``.

    Mirrors the C++ compute() clamp block. When ``skip_twist`` is True,
    indices where ``j % block == 3`` pass through untouched regardless
    of the stored bounds (used by Matrix mode for the circular twist
    scalar; see v5 addendum §M1.1 / §M1.3).

    Defense (mirrors C++): when ``mins`` or ``maxs`` is empty or the
    length does not match ``driver``, return ``driver`` unchanged
    rather than raise.
    """
    if not mins or not maxs:
        return list(driver)
    if len(mins) != len(driver) or len(maxs) != len(driver):
        return list(driver)
    out = list(driver)
    for j, x in enumerate(out):
        if skip_twist and (j % block == 3):
            continue
        r = maxs[j] - mins[j]
        lo = mins[j] - inflation * r
        hi = maxs[j] + inflation * r
        if x < lo:
            out[j] = lo
        elif x > hi:
            out[j] = hi
    return out


# ----------------------------------------------------------------------
# M1.4 — Regularized solver with Cholesky + GE fallback
# ----------------------------------------------------------------------


def cholesky_decompose(A):
    """In-place-style Cholesky A = L Lᵀ.

    Mirrors the C++ BRMatrix::cholesky. Returns ``(L, ok)``; ``L`` is
    always a fresh lower-triangular numpy matrix (even on failure, for
    callers that want to inspect partial progress). ``ok == False`` at
    the first non-positive pivot.
    """
    import numpy as np
    A = np.asarray(A, dtype=float)
    n = A.shape[0]
    L = np.zeros_like(A)
    for i in range(n):
        for j in range(i + 1):
            s = A[i, j]
            for k in range(j):
                s -= L[i, k] * L[j, k]
            if i == j:
                if s <= 0.0:
                    return L, False
                L[i, i] = math.sqrt(s)
            else:
                L[i, j] = s / L[j, j]
    return L, True


def cholesky_solve_single(L, b):
    """Solve L Lᵀ x = b given L from :func:`cholesky_decompose`."""
    import numpy as np
    L = np.asarray(L, dtype=float)
    b = np.asarray(b, dtype=float)
    n = len(b)
    x = np.zeros(n)
    # Forward: L z = b, z stored in x.
    for i in range(n):
        s = b[i]
        for k in range(i):
            s -= L[i, k] * x[k]
        x[i] = s / L[i, i]
    # Back: Lᵀ x = z (z currently in x).
    for i in range(n - 1, -1, -1):
        s = x[i]
        for k in range(i + 1, n):
            s -= L[k, i] * x[k]
        x[i] = s / L[i, i]
    return x


def apply_absolute_lambda(K, lam):
    """Add λI to the kernel matrix diagonal. Absolute λ per addendum §M1.4.

    Returns a fresh numpy matrix — never mutates input.
    """
    import numpy as np
    K = np.asarray(K, dtype=float).copy()
    if lam > 0.0:
        n = K.shape[0]
        for i in range(n):
            K[i, i] += lam
    return K


class SolverDispatcher:
    """Pure-Python mirror of the RBFtools::compute() M1.4 solver path.

    Tracks the ``lastSolveMethod`` cache (0 = Cholesky, 1 = GE) and the
    ``prevSolverMethodVal`` used to detect Auto <-> ForceGE flips that
    must reset the cache.
    """

    # Tier codes (match C++ lastSolveMethod semantics).
    TIER_CHOLESKY = 0
    TIER_GE       = 1

    # solverMethod enum values (match C++ addField order).
    MODE_AUTO     = 0
    MODE_FORCE_GE = 1

    def __init__(self):
        self.last_solve_method = self.TIER_CHOLESKY
        self.prev_solver_method_val = self.MODE_AUTO

    def _observe_mode(self, solver_method_val):
        """Mirror: reset cache when user flipped solverMethod."""
        if solver_method_val != self.prev_solver_method_val:
            self.last_solve_method = self.TIER_CHOLESKY
            self.prev_solver_method_val = solver_method_val

    def solve(self, K, Y, lam, solver_method_val, ge_solve):
        """Solve (K + λI) W = Y with tiered dispatch.

        Parameters
        ----------
        K : ndarray (N, N)
            Kernel activation matrix (before λI).
        Y : ndarray (N, m)
            Per-output-dim RHS (baseline already subtracted by caller).
        lam : float
            Absolute Tikhonov regularization strength.
        solver_method_val : int
            0 = Auto (try Cholesky then GE), 1 = ForceGE.
        ge_solve : callable (A, b) -> x
            GE solver injected by the caller (in tests, numpy.linalg.solve
            stands in for BRMatrix::solve — behaviour-equivalent for the
            dispatch contract).

        Returns
        -------
        W : ndarray (N, m)
        """
        import numpy as np
        self._observe_mode(solver_method_val)

        K_reg = apply_absolute_lambda(K, lam)
        N, m = Y.shape
        W = np.zeros((N, m))

        used_cholesky = False
        if solver_method_val == self.MODE_AUTO \
                and self.last_solve_method == self.TIER_CHOLESKY:
            L, ok = cholesky_decompose(K_reg)
            if ok:
                for c in range(m):
                    W[:, c] = cholesky_solve_single(L, Y[:, c])
                used_cholesky = True
                self.last_solve_method = self.TIER_CHOLESKY

        if not used_cholesky:
            for c in range(m):
                W[:, c] = ge_solve(K_reg, Y[:, c])
            self.last_solve_method = self.TIER_GE

        return W


def capture_output_baselines_pure(driven_attrs,
                                  pose0_inputs=None,
                                  pose0_values=None,
                                  scene_values=None):
    """Pure-Python spec for core.capture_output_baselines.

    Priority (v5 addendum 2026-04-24):
      1. pose0_values when pose0_inputs is all ~0 (rest row).
      2. scene_values otherwise.
    Scale channels always force base_value = 1.0 regardless.

    Returns list[(base_value, is_scale)].
    """
    FLOAT_ABS_TOL = 1e-6
    rest_from_pose0 = None
    if pose0_inputs is not None and pose0_values is not None:
        if all(abs(v) <= FLOAT_ABS_TOL for v in pose0_inputs):
            rest_from_pose0 = list(pose0_values)

    result = []
    for i, attr in enumerate(driven_attrs):
        is_scale = is_scale_attr(attr)
        if is_scale:
            base_value = 1.0
        elif rest_from_pose0 is not None and i < len(rest_from_pose0):
            base_value = float(rest_from_pose0[i])
        elif scene_values is not None and i < len(scene_values):
            base_value = float(scene_values[i])
        else:
            base_value = 0.0
        result.append((base_value, is_scale))
    return result
