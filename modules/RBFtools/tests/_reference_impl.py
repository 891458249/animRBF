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


# ----------------------------------------------------------------------
# M2.1a — Input encoding (Raw, Quaternion, ExpMap) + dispatch
# ----------------------------------------------------------------------

# Encoding enum values (match C++ inputEncoding eAttr order).
ENC_RAW        = 0
ENC_QUATERNION = 1
ENC_BENDROLL   = 2
ENC_EXPMAP     = 3
ENC_SWINGTWIST = 4

# Twist axis enum (matches C++ twistAxis attr). Moved above encode_driver
# so its default-kwarg `twist_axis=AXIS_X` resolves at import time.
AXIS_X = 0
AXIS_Y = 1
AXIS_Z = 2

# rotateOrder enum values (match Maya native + C++ driverInputRotateOrder).
RO_XYZ = 0
RO_YZX = 1
RO_ZXY = 2
RO_XZY = 3
RO_YXZ = 4
RO_ZYX = 5


def _quat_mul(a, b):
    """Hamilton product of two (w, x, y, z) quats."""
    aw, ax, ay, az = a
    bw, bx, by, bz = b
    return (
        aw*bw - ax*bx - ay*by - az*bz,
        aw*bx + ax*bw + ay*bz - az*by,
        aw*by - ax*bz + ay*bw + az*bx,
        aw*bz + ax*by - ay*bx + az*bw,
    )


def encode_euler_to_quaternion(rx, ry, rz, rotate_order):
    """Euler → Quaternion. Mirrors C++ encodeEulerToQuaternion.

    Returns (qx, qy, qz, qw).
    """
    hx, hy, hz = rx * 0.5, ry * 0.5, rz * 0.5
    qX = (math.cos(hx), math.sin(hx), 0.0, 0.0)
    qY = (math.cos(hy), 0.0, math.sin(hy), 0.0)
    qZ = (math.cos(hz), 0.0, 0.0, math.sin(hz))

    if rotate_order == RO_YZX:
        out = _quat_mul(_quat_mul(qY, qZ), qX)
    elif rotate_order == RO_ZXY:
        out = _quat_mul(_quat_mul(qZ, qX), qY)
    elif rotate_order == RO_XZY:
        out = _quat_mul(_quat_mul(qX, qZ), qY)
    elif rotate_order == RO_YXZ:
        out = _quat_mul(_quat_mul(qY, qX), qZ)
    elif rotate_order == RO_ZYX:
        out = _quat_mul(_quat_mul(qZ, qY), qX)
    else:  # RO_XYZ (Maya default)
        out = _quat_mul(_quat_mul(qX, qY), qZ)
    w, x, y, z = out
    return (x, y, z, w)


def encode_quaternion_to_expmap(qx, qy, qz, qw):
    """Quaternion → log-map ∈ ℝ³. Mirrors C++ encodeQuaternionToExpMap.

    Returns (lx, ly, lz). Canonicalises to q_w ≥ 0 hemisphere; uses
    Taylor fallback for θ → 0 to avoid division by zero.
    """
    if qw < 0.0:
        qx, qy, qz, qw = -qx, -qy, -qz, -qw
    qw = max(-1.0, min(1.0, qw))

    sin_half = math.sqrt(1.0 - qw * qw)
    half_theta = math.acos(qw)
    EPS = 1.0e-8
    scale = 1.0 if sin_half < EPS else (half_theta / sin_half)
    return (scale * qx, scale * qy, scale * qz)


def encode_driver(raw_vec, encoding, rotate_orders, twist_axis=AXIS_X):
    """Encode a raw driver vector into the (effective) encoded vector.

    `raw_vec` must be a list of scalars. Under Raw (0), returned as-is.
    Non-Raw encodings consume (rx, ry, rz) triples:
      * Quaternion (1) → 4-tuples
      * BendRoll (2)   → 3-tuples (roll, bendH, bendV)
      * ExpMap (3)     → 3-tuples
      * SwingTwist (4) → 5-tuples (sx, sy, sz, sw, twist)
    Any non-Raw encoding on a non-triple inDim falls back to Raw
    (caller is expected to have resolved via resolve_effective_encoding).
    """
    n = len(raw_vec)
    if encoding == ENC_RAW or n == 0 or n % 3 != 0:
        return list(raw_vec)

    groups = n // 3
    out = []

    if encoding == ENC_QUATERNION:
        for g in range(groups):
            ro = rotate_orders[g] if g < len(rotate_orders) else RO_XYZ
            q = encode_euler_to_quaternion(
                raw_vec[g*3+0], raw_vec[g*3+1], raw_vec[g*3+2], ro)
            out.extend(q)
        return out

    if encoding == ENC_EXPMAP:
        for g in range(groups):
            ro = rotate_orders[g] if g < len(rotate_orders) else RO_XYZ
            qx, qy, qz, qw = encode_euler_to_quaternion(
                raw_vec[g*3+0], raw_vec[g*3+1], raw_vec[g*3+2], ro)
            lx, ly, lz = encode_quaternion_to_expmap(qx, qy, qz, qw)
            out.extend((lx, ly, lz))
        return out

    if encoding == ENC_BENDROLL:
        for g in range(groups):
            ro = rotate_orders[g] if g < len(rotate_orders) else RO_XYZ
            out.extend(encode_bendroll(
                raw_vec[g*3+0], raw_vec[g*3+1], raw_vec[g*3+2], ro, twist_axis))
        return out

    if encoding == ENC_SWINGTWIST:
        for g in range(groups):
            ro = rotate_orders[g] if g < len(rotate_orders) else RO_XYZ
            out.extend(encode_swing_twist(
                raw_vec[g*3+0], raw_vec[g*3+1], raw_vec[g*3+2], ro, twist_axis))
        return out

    return list(raw_vec)


def resolve_effective_encoding(encoding, raw_in_dim):
    """Apply the safety net. Returns (effective_encoding, warning).

    M2.1b: BendRoll / SwingTwist are no longer placeholder — they are
    implemented. Only the `non_triple` branch remains.

    `warning` is one of None / 'non_triple'.
    Mirrors the compute() pre-getPoseData safety block.
    """
    if encoding != ENC_RAW and raw_in_dim % 3 != 0:
        return ENC_RAW, 'non_triple'
    return encoding, None


# ----------------------------------------------------------------------
# M2.1b — Swing-Twist decomposition + BendRoll + SwingTwist encodings
# ----------------------------------------------------------------------
# (Constants moved above encode_driver so the default twist_axis kwarg
#  resolves at module-load time — see AXIS_X / AXIS_Y / AXIS_Z defined
#  earlier in the file.)

# BendRoll stereographic projection ε. See addendum §M2.1b.3.
BENDROLL_EPS = 1.0e-4


def _quat_conjugate(q_wxyz):
    w, x, y, z = q_wxyz
    return (w, -x, -y, -z)


def decompose_swing_twist(qx, qy, qz, qw, twist_axis):
    """Swing-Twist decomposition. Mirrors C++ decomposeSwingTwist.

    Axis: AXIS_X / AXIS_Y / AXIS_Z. Returns (sx, sy, sz, sw, twist_angle).
    Degenerate projection (q_w² + axis_component² < 1e-12) falls back
    to (identity swing = (0,0,0,1), zero twist) per option (B)①.
    """
    if twist_axis == AXIS_X:
        a = qx
    elif twist_axis == AXIS_Y:
        a = qy
    else:
        a = qz

    norm_sq = qw * qw + a * a
    if norm_sq < 1.0e-12:
        return (0.0, 0.0, 0.0, 1.0, 0.0)

    norm = math.sqrt(norm_sq)
    tw = qw / norm
    tx = ty = tz = 0.0
    if twist_axis == AXIS_X:
        tx = a / norm
    elif twist_axis == AXIS_Y:
        ty = a / norm
    else:
        tz = a / norm

    # Swing = q · conj(twist). Quat packed (w, x, y, z) for the multiply.
    a_q = (qw, qx, qy, qz)
    b_q = (tw, -tx, -ty, -tz)
    rw, rx, ry, rz = _quat_mul(a_q, b_q)

    twist_angle = 2.0 * math.atan2(a, qw)
    return (rx, ry, rz, rw, twist_angle)


def encode_bendroll(rx, ry, rz, rotate_order, twist_axis, eps=BENDROLL_EPS):
    """Euler → BendRoll (roll, bendH, bendV).

    Layout (roll, bendH, bendV) per v5 addendum §M2.1b (F)①. Denominator
    clamped to max(1 + s_w, ε) to handle the stereographic-pole
    singularity without a hot-path branch.
    """
    qx, qy, qz, qw = encode_euler_to_quaternion(rx, ry, rz, rotate_order)
    sx, sy, sz, sw, twist_angle = decompose_swing_twist(qx, qy, qz, qw, twist_axis)

    if twist_axis == AXIS_X:
        sh, sv = sy, sz
    elif twist_axis == AXIS_Y:
        sh, sv = sz, sx
    else:
        sh, sv = sx, sy

    sw_clamped = sw if sw >= -1.0 + eps else -1.0 + eps
    denom = 1.0 + sw_clamped
    bend_h = 2.0 * sh / denom
    bend_v = 2.0 * sv / denom
    return (twist_angle, bend_h, bend_v)


def encode_swing_twist(rx, ry, rz, rotate_order, twist_axis):
    """Euler → SwingTwist (sx, sy, sz, sw, twist). Mirrors C++ encodeSwingTwist."""
    qx, qy, qz, qw = encode_euler_to_quaternion(rx, ry, rz, rotate_order)
    return decompose_swing_twist(qx, qy, qz, qw, twist_axis)


# ----------------------------------------------------------------------
# M2.2 — QWA (Quaternion Weighted Average) output-side helpers
# ----------------------------------------------------------------------

# Identity quat fallback.
QWA_IDENTITY = (0.0, 0.0, 0.0, 1.0)


def right_mul_matrix(q0):
    """Right-multiplication matrix R(q0) such that R(q0) @ q = q · q0.

    q0 is (a, b, c, d) = (qx, qy, qz, qw). Used in the commutativity
    proof (v5 addendum §M2.2.CORNER-PATH-A) — R is orthogonal when q0
    is unit, so the path-(a) delta-train / path-(b) direct-QWA pair
    produces identical output for any constant q_base.
    """
    import numpy as np
    a, b, c, d = q0
    return np.array([
        [ d,  c, -b,  a],
        [-c,  d,  a,  b],
        [ b, -a,  d,  c],
        [-a, -b, -c,  d],
    ])


def power_iteration_max_eigenvec_4x4(M, max_iter=50, tol=1.0e-8):
    """Mirror of C++ powerIterationMaxEigenvec4x4.

    Dual-seed strategy per addendum §M2.2 (F)①-extended: primary seed
    is identity quaternion (0, 0, 0, 1) (rest-pose-biased, user design
    intent). If that fails to converge in max_iter steps, a secondary
    seed normalize(sum-of-M-columns) is used — guaranteed to have
    non-zero component along any eigenvector with non-zero eigenvalue.
    Returns (q, converged, iters_total).
    """
    import numpy as np
    M_np = np.asarray(M, dtype=float).reshape(4, 4)

    def _run(seed):
        q = np.array(seed, dtype=float)
        n0 = float(np.linalg.norm(q))
        if n0 == 0.0:
            return (q, False, 0)
        q = q / n0
        converged = False
        iters = 0
        for k in range(max_iter):
            qp = M_np @ q
            norm = float(np.linalg.norm(qp))
            if norm < 1.0e-30:
                return (q, False, k + 1)
            qp = qp / norm
            delta = float(np.linalg.norm(qp - q))
            dot = float(np.dot(qp, q))
            q = qp
            iters = k + 1
            if delta < tol or abs(dot) > 1.0 - tol * tol:
                converged = True
                break
        return (q, converged, iters)

    # Primary: identity. Secondary: normalize(M·1) (robust against
    # identity-seed being near-orthogonal to the dominant eigenvector).
    q1, ok1, it1 = _run([0.0, 0.0, 0.0, 1.0])
    if ok1:
        q_final, iters = q1, it1
        converged = True
    else:
        sec = M_np @ np.array([1.0, 1.0, 1.0, 1.0])
        if float(np.linalg.norm(sec)) < 1.0e-30:
            sec = np.array([0.5, 0.5, 0.5, 0.5])
        q2, ok2, it2 = _run(sec)
        q_final = q2
        iters = it1 + it2
        converged = ok2

    if q_final[3] < 0.0:
        q_final = -q_final
    return ((float(q_final[0]), float(q_final[1]),
             float(q_final[2]), float(q_final[3])),
            converged, iters)


def compute_qwa_for_group(M):
    """Mirror of C++ computeQWAForGroup. Returns (quat, status) where
    status ∈ {'OK', 'ZERO_MASS', 'NO_CONVERGE'}."""
    import numpy as np
    M_np = np.asarray(M, dtype=float).reshape(4, 4)
    EPS_M = 1.0e-12
    trace = float(np.trace(M_np))
    if trace < EPS_M:
        return (QWA_IDENTITY, 'ZERO_MASS')
    q, ok, _ = power_iteration_max_eigenvec_4x4(M_np)
    if not ok:
        return (QWA_IDENTITY, 'NO_CONVERGE')
    return (q, 'OK')


def resolve_quaternion_groups(raw_starts, output_count, is_scale_arr):
    """Mirror of C++ resolveQuaternionGroups.

    Returns (valid_starts, is_quat_member, any_invalid). Drops entries
    that are out-of-range, overlap another accepted group, or collide
    with any outputIsScale==True on their 4 slots. `is_quat_member`
    is the single-source-of-truth mask (addendum §M2.2.Q9).
    """
    valid_starts = []
    is_quat_member = [False] * output_count
    any_invalid = False
    for s in raw_starts:
        if s < 0 or s + 4 > output_count:
            any_invalid = True
            continue
        if any(is_quat_member[s + k] for k in range(4)):
            any_invalid = True
            continue
        if any(s + k < len(is_scale_arr) and is_scale_arr[s + k]
               for k in range(4)):
            any_invalid = True
            continue
        for k in range(4):
            is_quat_member[s + k] = True
        valid_starts.append(s)
    return (valid_starts, is_quat_member, any_invalid)


def accumulate_qwa_matrix(phis, quats, clip_negative=True):
    """Build M = Σ_i max(0, φ_i) · q_i q_iᵀ.

    Returns (M, any_clipped). any_clipped is True iff at least one
    φ_i was negative (addendum §M2.2 (Q8)). With clip_negative=False
    the negative samples are retained for test T11.b/c so the PSD
    breakage can be demonstrated explicitly.
    """
    import numpy as np
    M = np.zeros((4, 4))
    any_clipped = False
    for phi, q in zip(phis, quats):
        phi_use = phi
        if phi_use < 0.0:
            any_clipped = True
            if clip_negative:
                phi_use = 0.0
        if phi_use == 0.0:
            continue
        qv = np.asarray(q, dtype=float).reshape(4, 1)
        M += phi_use * (qv @ qv.T)
    return (M, any_clipped)


# ----------------------------------------------------------------------
# M2.3 — Local-Transform decomposition (pure-Python mirror)
# ----------------------------------------------------------------------

IDENTITY_LOCAL_TRANSFORM = {
    "translate": (0.0, 0.0, 0.0),
    "quat":      (0.0, 0.0, 0.0, 1.0),
    "scale":     (1.0, 1.0, 1.0),
}


def _rotation_matrix_to_quat(R):
    """3x3 rotation matrix (Maya row-major, post-multiply convention)
    → (qx, qy, qz, qw). Shepperd-style branchless stable method; returns
    q_w >= 0 canonical form.

    NOTE on convention: textbook Shepperd assumes column-major M·v; for
    Maya's row-major v·M (where M_row[i][j] == M_col[j][i]), the
    off-diagonal index pairs in the qx/qy/qz expressions are swapped
    relative to the textbook formula.
    """
    import math
    m00, m01, m02 = R[0][0], R[0][1], R[0][2]
    m10, m11, m12 = R[1][0], R[1][1], R[1][2]
    m20, m21, m22 = R[2][0], R[2][1], R[2][2]
    trace = m00 + m11 + m22
    if trace > 0.0:
        s = math.sqrt(trace + 1.0) * 2.0
        qw = 0.25 * s
        qx = (m12 - m21) / s
        qy = (m20 - m02) / s
        qz = (m01 - m10) / s
    elif m00 > m11 and m00 > m22:
        s = math.sqrt(1.0 + m00 - m11 - m22) * 2.0
        qw = (m12 - m21) / s
        qx = 0.25 * s
        qy = (m10 + m01) / s
        qz = (m20 + m02) / s
    elif m11 > m22:
        s = math.sqrt(1.0 + m11 - m00 - m22) * 2.0
        qw = (m20 - m02) / s
        qx = (m10 + m01) / s
        qy = 0.25 * s
        qz = (m21 + m12) / s
    else:
        s = math.sqrt(1.0 + m22 - m00 - m11) * 2.0
        qw = (m01 - m10) / s
        qx = (m20 + m02) / s
        qy = (m21 + m12) / s
        qz = 0.25 * s
    if qw < 0.0:
        qx, qy, qz, qw = -qx, -qy, -qz, -qw
    return (qx, qy, qz, qw)


def decompose_matrix_quat_pure(matrix):
    """Pure-Python mirror of core.decompose_matrix_quat.

    Maya stores matrices row-major with post-multiply convention: a row
    vector is multiplied on the right by the matrix, so the translation
    lives in the LAST ROW (M[3][0..2]) and the linear part in the
    upper-left 3x3. Scale is the row-wise L2 norm of the 3x3; after
    scale normalization the rows form an (approximately) orthogonal
    rotation matrix which is converted to quaternion.

    Shear is silently absorbed — addendum §M2.3 T7 contract.
    """
    import math
    M = matrix
    # Accept numpy or list-of-lists.
    def g(i, j):
        return float(M[i][j])
    tx, ty, tz = g(3, 0), g(3, 1), g(3, 2)

    row0 = (g(0, 0), g(0, 1), g(0, 2))
    row1 = (g(1, 0), g(1, 1), g(1, 2))
    row2 = (g(2, 0), g(2, 1), g(2, 2))
    sx = math.sqrt(sum(c*c for c in row0))
    sy = math.sqrt(sum(c*c for c in row1))
    sz = math.sqrt(sum(c*c for c in row2))
    if sx > 1e-12 and sy > 1e-12 and sz > 1e-12:
        R = [
            [row0[0]/sx, row0[1]/sx, row0[2]/sx],
            [row1[0]/sy, row1[1]/sy, row1[2]/sy],
            [row2[0]/sz, row2[1]/sz, row2[2]/sz],
        ]
        q = _rotation_matrix_to_quat(R)
    else:
        # Degenerate scale (rare) — emit identity rotation.
        q = (0.0, 0.0, 0.0, 1.0)
    return {
        "translate": (tx, ty, tz),
        "quat":      q,
        "scale":     (sx, sy, sz),
    }


def get_swing_twist_block_distance(v1, v2):
    """Per-5-block composite: sqrt(d_swing² + d_twist²) aggregated L2."""
    assert len(v1) == len(v2)
    n = len(v1)
    blocks = n // 5
    sum_sq = 0.0
    for k in range(blocks):
        base = k * 5
        dot = sum(v1[base+i] * v2[base+i] for i in range(4))
        d_swing = 1.0 - abs(dot)
        d_twist = twist_wrap(v1[base+4], v2[base+4])
        sum_sq += d_swing * d_swing + d_twist * d_twist
    return math.sqrt(sum_sq)


def get_quat_block_distance(v1, v2):
    """Per-4-block (1 - |q1·q2|) aggregated L2."""
    assert len(v1) == len(v2)
    n = len(v1)
    blocks = n // 4
    sum_sq = 0.0
    for k in range(blocks):
        base = k * 4
        dot = sum(v1[base+i] * v2[base+i] for i in range(4))
        d = 1.0 - abs(dot)
        sum_sq += d * d
    return math.sqrt(sum_sq)


def get_matrix_mode_angle_distance(v1, v2):
    """Bug 2 fix: Matrix-mode [vx, vy, vz, twist] arc angle + wrap twist, L2."""
    assert len(v1) == len(v2)
    n = len(v1)
    blocks = n // 4
    sum_sq = 0.0
    for k in range(blocks):
        base = k * 4
        a = [v1[base+i] for i in range(3)]
        b = [v2[base+i] for i in range(3)]
        na = math.sqrt(sum(c*c for c in a))
        nb = math.sqrt(sum(c*c for c in b))
        if na > 0.0 and nb > 0.0:
            dot = sum(a[i]*b[i] for i in range(3)) / (na * nb)
            axis_angle = math.acos(max(-1.0, min(1.0, dot)))
        else:
            axis_angle = 0.0
        w = twist_wrap(v1[base+3], v2[base+3])
        sum_sq += axis_angle * axis_angle + w * w
    return math.sqrt(sum_sq)


def get_pose_delta(v1, v2, dist_type, encoding, is_matrix_mode):
    """Mirror of RBFtools::getPoseDelta with (encoding, isMatrixMode)."""
    n = len(v1)
    if n != len(v2):
        return get_radius(v1, v2)

    if is_matrix_mode:
        if n >= 4 and n % 4 == 0:
            if dist_type == 0:
                return get_matrix_mode_linear_distance(v1, v2)
            return get_matrix_mode_angle_distance(v1, v2)
        return get_radius(v1, v2)

    # Generic mode
    if encoding == ENC_RAW:
        if dist_type == 0:
            return get_radius(v1, v2)
        if n == 3:
            return get_angle(v1, v2)
        return get_radius(v1, v2)
    if encoding == ENC_QUATERNION:
        if n >= 4 and n % 4 == 0:
            return get_quat_block_distance(v1, v2)
        return get_radius(v1, v2)
    if encoding == ENC_EXPMAP:
        return get_radius(v1, v2)
    if encoding == ENC_BENDROLL:
        return get_radius(v1, v2)
    if encoding == ENC_SWINGTWIST:
        if n >= 5 and n % 5 == 0:
            return get_swing_twist_block_distance(v1, v2)
        return get_radius(v1, v2)
    # Unknown encoding: defensive fall-through.
    if dist_type == 0:
        return get_radius(v1, v2)
    if n == 3:
        return get_angle(v1, v2)
    return get_radius(v1, v2)


# Clamp-skip rule matrix per v5 addendum §M2.1a item 7.
# Returns the set of dimensions within an encoded vector that should NOT
# participate in M1.3 Driver Clamp.
def clamp_skip_dims(encoding, is_matrix_mode, effective_dim):
    if is_matrix_mode:
        # Matrix mode: skip every 4k+3 (twist slot), unchanged from M1.3.
        return {j for j in range(effective_dim) if j % 4 == 3}
    # Generic mode:
    #   Raw / Quaternion / ExpMap → clamp every dim.
    #   BendRoll (M2.1b) → skip every 3k (roll slot, wrap-aware).
    #   SwingTwist (M2.1b) → skip every 5k+4 (twist slot, wrap-aware).
    if encoding == ENC_BENDROLL:
        return {j for j in range(effective_dim) if j % 3 == 0}
    if encoding == ENC_SWINGTWIST:
        return {j for j in range(effective_dim) if j % 5 == 4}
    return set()


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
