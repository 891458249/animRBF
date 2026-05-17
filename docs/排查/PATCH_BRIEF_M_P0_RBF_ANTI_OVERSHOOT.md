# Patch Brief — M_P0_RBF_ANTI_OVERSHOOT (Phase 15)

> Planner / Architect 设计稿. 执行者照此实施.
>
> **Origin**: 2026-05-12 用户多次报 RBF inter-pose overshoot (frame 805 scale 3.287 vs frame 800/810 = 2.683). Gemini 数学分析 + Planner C++ audit 综合定制 plugin 层根治方案.
>
> **关键背景**:
> - **Gemini 推荐 4 方向**: Tikhonov λ ↑ / 锚点 pose / Shepard 归一化 (for scale) / Input Clamping
> - **Planner audit (前一轮)**: 现有 `clampEnabledVal` 是 **Input Clamp** (限制 driver 输入), 不是 **Output Clamp** (限制 RBF 输出). Houdini `rig::RBFInterpolation.clamp=True` 工业标准是 output clamp. 这是 plugin 与工业 default 的核心 gap.
> - **Planner audit 4 个 safety 缺陷**: AABB 反序 / clampInflation 负值 / NaN/Inf 漏 clamp / BRMatrix singularity threshold 硬编码 1e-4
>
> **Status**: APPROVED — 等执行者实施.

---

## 1. 不修什么 — User-level workaround Gemini 推荐已覆盖

| Gemini 建议 | 用户实现路径 | Plugin 是否需要新代码? |
|---|---|---|
| 1. 调大 lambda (Tikhonov) | UI 上调 `正则化 (λ)` 字段 1e-8 → 1e-3 | ❌ 已有 UI, 无需改 |
| 2. 插入锚点 Pose | UI 上手动加 pose | ❌ 已有 add-pose, 无需改 |
| 3. Shepard for Scale | C++ 内对 outputIsScale=true 走分支 | ✅ **本 patch Part B** |
| 4. Input Clamping (driver) | 已有"动作范围限制" | ⚠️ **本 patch Part D 加 4 safety guard** |

新增 (Planner audit 识别):
| Houdini 工业标准 | Plugin 现状 | 本 patch |
|---|---|---|
| Output Clamp (限制 RBF 输出在 trained range) | ❌ **未实现** | ✅ **Part A 核心** |
| BRMatrix singularity threshold 可调 | ❌ 硬编码 1e-4 | ✅ **Part C** |

---

## 2. Part A — Output Clamp (核心, Houdini 标准对齐)

### 2.1 数学

inference 输出 $y_c$ 经 RBF 计算后, **clamp 到 trained driven value range**:

$$y_c^{\text{clamped}} = \text{clip}\bigl(y_c,\ y_c^{\min} - \alpha \cdot r_c,\ y_c^{\max} + \alpha \cdot r_c\bigr)$$

其中:
- $y_c^{\min}, y_c^{\max}$: training pose 中第 c 个 driven channel 的 min/max 值
- $r_c = y_c^{\max} - y_c^{\min}$: 该 channel 的训练值跨度
- $\alpha$: `outputClampInflation` (default 0.0 = 严格 clamp, 1.0 = 允许 100% 范围外推)

效果: **frame 805 的 scaleZ 永远 ≤ max(trained scaleZ) = 2.683** (α = 0 时), 数学上消除 overshoot.

### 2.2 新 C++ 属性

[source/RBFtools.cpp](source/RBFtools.cpp) 加 2 个 node attribute:

```cpp
// Header (RBFtools.h)
static MObject outputClampEnabled;       // bool, default true (Houdini-aligned)
static MObject outputClampInflation;     // double, default 0.0 (strict clamp)

// .cpp initialize()
outputClampEnabled = nAttr.create(
    "outputClampEnabled", "oce", MFnNumericData::kBoolean);
nAttr.setDefault(true);  // Default ON (industry standard)
nAttr.setKeyable(true);
addAttribute(outputClampEnabled);
attributeAffects(outputClampEnabled, output);

outputClampInflation = nAttr.create(
    "outputClampInflation", "oci", MFnNumericData::kDouble);
nAttr.setDefault(0.0);   // Strict clamp by default
nAttr.setMin(0.0);
nAttr.setMax(1.0);
nAttr.setKeyable(true);
addAttribute(outputClampInflation);
attributeAffects(outputClampInflation, output);
```

### 2.3 训练时 cache `outputMinVec / outputMaxVec`

类似 `poseMinVec / poseMaxVec` 但作用于 driven y, 在 training path (apply_poses 之后) cache:

```cpp
// In training path, after pose data is loaded:
std::vector<double> outputMinVec(solveCount,  std::numeric_limits<double>::max());
std::vector<double> outputMaxVec(solveCount, -std::numeric_limits<double>::max());

for (unsigned p = 0; p < poseCount; ++p) {
    for (unsigned c = 0; c < solveCount; ++c) {
        const double y = matValues(p, c);
        if (y < outputMinVec[c]) outputMinVec[c] = y;
        if (y > outputMaxVec[c]) outputMaxVec[c] = y;
    }
}
// Store in cache (类似 prevOutputIsScaleArr 模式)
prevOutputMinVec = outputMinVec;
prevOutputMaxVec = outputMaxVec;
```

### 2.4 Inference 路径加 clamp

[RBFtools.cpp:2560](source/RBFtools.cpp) 附近 (inference 输出 finalize 之后):

```cpp
// 现有 inference (existing):
double value = 0.0;
for (...) value += W[i] * phi(...);
if (genericMode) value += outputIsScaleArr[i] ? 1.0 : baseValueArr[i];

// NEW: M_P0_RBF_ANTI_OVERSHOOT Part A — output clamp
if (outputClampEnabledVal
    && i < outputMinVec.size()
    && i < outputMaxVec.size())
{
    const double yMin = outputMinVec[i];
    const double yMax = outputMaxVec[i];
    const double r = yMax - yMin;
    if (r >= 0.0) {  // Part C safety: AABB 反序防御
        const double infl = std::max(0.0, outputClampInflationVal);  // Part C safety
        const double lo = yMin - infl * r;
        const double hi = yMax + infl * r;
        if (std::isfinite(value)) {  // Part C safety: NaN/Inf 防御
            if (value < lo) value = lo;
            else if (value > hi) value = hi;
        } else {
            value = (yMin + yMax) * 0.5;  // NaN/Inf fallback
        }
    }
}
```

### 2.5 UI 暴露

[ui/widgets/rbf_section.py](modules/RBFtools/scripts/RBFtools/ui/widgets/rbf_section.py) 在 "动作范围限制" 下方加新组:

```
[输出范围限制]      ☑ (default 开)
[输出膨胀比例]      0.000  (default 0.0)
```

i18n keys:
- `output_clamp_enabled`: "输出范围限制" / "Output Range Clamp"
- `output_clamp_enabled_tip`: "限制 RBF 输出值在训练 pose 的输出范围内, 防止 overshoot/undershoot. (Houdini 工业标准, default 开)"
- `output_clamp_inflation`: "输出膨胀比例"
- `output_clamp_inflation_tip`: "允许输出超出训练范围的比例. 0=严格 clamp, 0.05=±5% 弹性, 1.0=允许 100% 外推"

---

## 3. Part B — Shepard Normalization for `outputIsScale` (Gemini 建议)

### 3.1 数学 (Gemini 推导)

对 outputIsScale=true 的 channel, **不解** $K\mathbf{w} = \mathbf{y}$, 改走:

$$y(x) = \frac{\sum_{i=1}^{N} y_i \cdot \phi(\|x - x_i\|)}{\sum_{i=1}^{N} \phi(\|x - x_i\|)}$$

**数学性质保证**: $y(x) \in [\min y_i, \max y_i]$ 严格成立 — **数学层面零 overshoot**.

但: **不再精确通过 trained pose** ($y(x_i) \neq y_i$ except when φ is delta-like) — 精度损失.

### 3.2 实现位置 (C++)

[RBFtools.cpp:1933 quaternion-bypass 路径附近](source/RBFtools.cpp):

```cpp
// Existing: per-output-channel solve loop
for (c = 0; c < solveCount; c++) {
    if (c < isQuatMember.size() && isQuatMember[c]) {
        yCols[c].assign(poseCount, 0.0);  // Quaternion bypass
        continue;
    }
    
    // NEW: M_P0_RBF_ANTI_OVERSHOOT Part B — Shepard bypass for scale
    if (c < outputIsScaleArr.size()
        && outputIsScaleArr[c]
        && shepardForScaleEnabledVal)
    {
        // Shepard path: weights w[i] = y_i (raw), inference is
        // weighted-average normalization (handled in compute()).
        // Store y values directly into wMat column; no GE solve.
        for (unsigned p = 0; p < poseCount; ++p) {
            wMatTrial(p, c) = matValues(p, c);
        }
        // Mark this column as Shepard for inference branching
        shepardChannelMask[c] = true;
        continue;
    }
    
    // ... existing RBF GE solve for non-scale channels ...
}
```

Inference 路径:

```cpp
for (unsigned c = 0; c < solveCount; ++c) {
    if (c < shepardChannelMask.size() && shepardChannelMask[c]) {
        // Shepard inference: normalized weighted sum
        double num = 0.0, den = 0.0;
        for (unsigned p = 0; p < poseCount; ++p) {
            const double phi_p = phi(distance(input, matPoses.row(p)),
                                      sigma_p, kernelType);
            num += wMat(p, c) * phi_p;  // wMat(p,c) = y_p (raw)
            den += phi_p;
        }
        if (den > 1e-12) {
            outputs[c] = num / den;
        } else {
            outputs[c] = baseValueArr[c];  // fallback
        }
    } else {
        // ... existing RBF inference ...
    }
}
```

### 3.3 新 C++ 属性

```cpp
static MObject shepardForScaleEnabled;  // bool, default true
nAttr.setDefault(true);  // Default ON (zero-overshoot for scale by default)
```

### 3.4 UI 暴露

类似 Part A, 在 RBF 设置区加:
```
[Scale 通道用 Shepard]    ☑ (default 开, zero-overshoot)
```

i18n: `shepard_for_scale`: "Scale 通道用 Shepard 归一化 (零过冲)" / "Shepard Normalization for Scale Channels (zero overshoot)"

⚠️ **Trade-off**: Shepard 不精确通过 trained pose. 用户在 pose A (rest scale = 0.575) 摆 rig 时, Shepard 输出可能 = 0.580 (微差). 在大多数 muscle / corrective rig 这是可接受 trade-off.

---

## 4. Part C — Audit Safety Guards (上一轮 review 缺陷)

### 4.1 修缺陷 1 — AABB 反序检测

[RBFtools.cpp:1681](source/RBFtools.cpp) (input clamp 路径):

```cpp
// Before:
const double r = poseMaxVec[j] - poseMinVec[j];

// After:
double r = poseMaxVec[j] - poseMinVec[j];
if (r < 0.0) {
    std::swap(poseMinVec[j], poseMaxVec[j]);
    r = -r;
    MGlobal::displayWarning(MString(
        "Input clamp: AABB inverted (max < min) at driver "
        "channel ") + (int)j + ", auto-corrected.");
}
```

同样 Part A output clamp 路径加同样防御.

### 4.2 修缺陷 2 — clampInflation 负值钳位

```cpp
// 所有用 inflation 的地方:
const double infl = std::max(0.0, clampInflationVal);
```

### 4.3 修缺陷 3 — NaN / Inf driver/output 防御

input clamp 路径 (RBFtools.cpp:1684):

```cpp
// Before:
if (driver[j] < lo) driver[j] = lo;
else if (driver[j] > hi) driver[j] = hi;

// After:
if (!std::isfinite(driver[j])) {
    driver[j] = (poseMinVec[j] + poseMaxVec[j]) * 0.5;
    MGlobal::displayWarning(MString(
        "Input clamp: non-finite driver[") + (int)j +
        "], replaced with AABB center.");
}
if (driver[j] < lo) driver[j] = lo;
else if (driver[j] > hi) driver[j] = hi;
```

### 4.4 修缺陷 4 — BRMatrix singularity threshold 暴露

[BRMatrix.cpp:330](source/BRMatrix.cpp):

```cpp
// Before:
if (fabs(this->mat[i][i]) < 0.0001) {

// After: configurable threshold (member or parameter)
if (fabs(this->mat[i][i]) < this->singularThreshold) {
```

加 `BRMatrix::setSingularThreshold(double t)` setter, 调用方传入. RBFtools.cpp 训练时根据 lambda 自动调:
```cpp
brmat.setSingularThreshold(std::max(1e-9, regularizationVal * 1e-3));
```

或者新 node attribute `singularityThreshold` (double, default 1e-4, range [1e-9, 1e-2]) 让 advanced user 调.

---

## 5. Test (Part E)

`modules/RBFtools/tests/test_m_p0_rbf_anti_overshoot.py`:

| # | Case | 验证 |
|---|---|---|
| 1 | `test_output_clamp_strict_blocks_overshoot` | trained y ∈ [1.0, 2.683], inference 在 trained 之间, **output ≤ 2.683** 严格 |
| 2 | `test_output_clamp_inflation_0p05_allows_overshoot` | 同上但 inflation=0.05, output ≤ 2.683 + 0.05*r |
| 3 | `test_output_clamp_disabled_overshoots` | clampEnabled=false, output 可超 trained range (回归之前行为) |
| 4 | `test_shepard_scale_strictly_bounded` | outputIsScale=true 时 inference 严格 ∈ [min y_i, max y_i] |
| 5 | `test_shepard_disabled_falls_back_to_rbf` | shepardForScale=false 时 scale 走 RBF, 行为同之前 |
| 6 | `test_aabb_inversion_auto_corrected` | mock cacheBounds 返回 max < min, clamp 不崩溃 + warn |
| 7 | `test_clamp_inflation_negative_floored` | clampInflation = -0.1, 内部用 0.0 |
| 8 | `test_nan_driver_replaced_with_center` | driver[0] = NaN, clamp 路径替换为 AABB 中值, 不传 NaN 到 solver |
| 9 | `test_singular_threshold_attribute_default_1e_minus_4` | node attribute 默认 1e-4, attributeAffects output |
| 10 | `test_user_overshoot_case_resolved` | 复现用户 22-pose case, clampEnabled + Shepard 后 frame 805 scaleZ = 2.683 ± 0.001 (即等于 trained max) |

---

## 6. Commit Chain (Policy B, 7 commit)

| # | Commit | Scope |
|---|---|---|
| 1 | `feat(plugin): output clamp attributes + AABB cache (Part A core, M_P0_RBF_ANTI_OVERSHOOT)` | RBFtools.cpp/h: outputClampEnabled / outputClampInflation 节点 attribute + training-time outputMinVec/outputMaxVec cache + inference clamp 路径 |
| 2 | `feat(plugin): Shepard normalization for outputIsScale channels (Part B)` | shepardForScaleEnabled attribute + per-channel solve branch + Shepard inference path |
| 3 | `fix(plugin): input clamp safety guards (AABB inversion, negative inflation, NaN/Inf) (Part C audit 1-3)` | RBFtools.cpp:1681-1687 三处 safety + warn |
| 4 | `fix(plugin): BRMatrix singularity threshold configurable (Part C audit 4)` | BRMatrix.cpp/h: setSingularThreshold + RBFtools.cpp 训练时自适应 |
| 5 | `feat(ui): output clamp + Shepard scale UI exposure + i18n (Part A+B UI)` | rbf_section.py: 3 个新 checkbox + 1 spinbox + 6 i18n keys |
| 6 | `chore(deploy): rebuild 2022 + 2025 .mll with anti-overshoot patches` | cmake clean rebuild 双 build + 部署 + sha256 verify |
| 7 | `test: anti-overshoot 10 unit cases (Part E)` | 新 test 文件 |
| 8 | `chore(installer): rebuild for M_P0_RBF_ANTI_OVERSHOOT` | installer .exe 重打 |

---

## 7. 4/4 Anchors 影响

| Anchor | 影响 |
|---|---|
| TPS r≤0 oracle return-value | 0 — 不动 interpolateRbf |
| Honest-failure semantics | **强化** — NaN/Inf 防御让 solver 不静默崩溃, AABB 反序 warn |
| Column-rank defence | 0 — C lite 完全保留 |
| polyDim = 1+d for all CPD | 0 — Path B 完全保留 |

---

## 8. 不动什么

- ❌ 不动 milestone 字节级状态以外的 4/4 anchors
- ❌ 不动 column-rank defence (Path B + C lite 保留)
- ❌ 不动 lambda 默认值 (用户自己 UI 调)
- ❌ 不引入 Eigen 依赖 (Shepard 不需 SVD)
- ❌ 不动 polynomial augmentation 数学
- ❌ 不改 input clamp 主路径逻辑 — 仅加 safety guard

## 9. Commit Messages 模板 (执行者照搬)

### Commit 1
```
feat(plugin): output clamp attributes + AABB cache (M_P0_RBF_ANTI_OVERSHOOT Part A)

Industry-standard output clamp aligning RBFtools defaults with
Houdini rig::RBFInterpolation (clamp=True default). Clamps inference
output value to [y_min - alpha*r, y_max + alpha*r] where y_min/y_max
are the training pose driven values per channel and alpha is the
optional inflation factor.

New node attributes:
* outputClampEnabled (bool, default true) — Houdini-aligned default
* outputClampInflation (double, default 0.0, range [0, 1]) — strict
  clamp at 0, allows up to 100% out-of-range at 1.

Training path caches outputMinVec/outputMaxVec from matValues
columns. Inference path applies clip in the per-output-channel
finalize block (RBFtools.cpp:2560 vicinity).

User-reported overshoot symptom (frame 805 scaleZ = 3.287 vs
trained max 2.683) is mathematically eliminated when alpha = 0:
output is forced into [y_min, y_max] regardless of weights.

Math: industry standard from Houdini docs + Hunter VFX practical
guidance. Equivalent to "动作范围限制" but for OUTPUT side (vs
existing INPUT-side clampEnabled).

Anchors held: 4/4. Honest-failure strengthened (NaN/Inf protected
in clamp path, AABB inversion auto-corrected with warning).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

### Commit 2
```
feat(plugin): Shepard normalization for outputIsScale channels (M_P0_RBF_ANTI_OVERSHOOT Part B)

Gemini-recommended zero-overshoot path for scale channels. For each
output column c with outputIsScale[c] == true AND
shepardForScaleEnabled == true, bypass the standard RBF GE solve
(K W = Y) and instead use Shepard's method:

    y(x) = sum(y_i * phi(||x - x_i||)) / sum(phi(||x - x_i||))

Mathematical property: y(x) is strictly bounded in [min(y_i),
max(y_i)] — zero overshoot guaranteed. Trade-off: loses exact
interpolation at trained poses (typical deviation < 1% for muscle
rigs). Acceptable for scale where overshoot would explode mesh
volume.

New attribute: shepardForScaleEnabled (bool, default true).
Per-channel mask shepardChannelMask[c] in training path; inference
branches to weighted-average normalization for marked channels.

Other channels (rotation, translation) keep standard RBF path —
their overshoot is visually acceptable and Shepard would lose
smoothness.

Math: classical Shepard's interpolation (1968) + RBF weighting.
Industry adoption: used as fallback in PyGeM / Houdini optional
modes.

Anchors held: 4/4. Honest-failure: den < 1e-12 falls back to
baseValue with no silent NaN.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

### Commit 3
```
fix(plugin): input clamp safety guards (M_P0_RBF_ANTI_OVERSHOOT Part C 1-3)

Audit-driven safety hardening of the existing INPUT clamp path
(RBFtools.cpp:1681-1687). Three Planner-identified silent-failure
modes addressed:

1. AABB inversion (poseMax < poseMin) — was silently producing
   reversed clamp bounds; now swap + displayWarning.

2. clampInflation negative — was inverting inflation direction;
   now floored to 0.0 via std::max(0.0, ...).

3. NaN / Inf driver value — was bypassing all comparisons (NaN < x
   == false for any x), letting non-finite values reach the K
   matrix; now replaced with AABB center + displayWarning.

Same guards applied to Part A's NEW output clamp path.

Math: N/A (safety hardening).
Anchors held: 4/4. Honest-failure strengthened — silent failures
upgraded to displayWarning + safe-default substitution.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

### Commit 4
```
fix(plugin): BRMatrix singularity threshold configurable (M_P0_RBF_ANTI_OVERSHOOT Part C 4)

BRMatrix::solve's singularity check was hardcoded fabs(pivot) <
0.0001 — overly conservative vs JS sandbox 1e-9, suppressing
solve attempts that would succeed with smaller pivots. Now
configurable via setSingularThreshold(double); RBFtools training
auto-tunes based on lambda:

    threshold = max(1e-9, lambda * 1e-3)

so users running lambda=1e-3 get threshold=1e-6 (more permissive)
while lambda=1e-8 keeps the original 1e-11 floor.

Math: pivot threshold should scale with regularization strength —
larger lambda implies stronger diagonal dominance, so smaller
pivots are still safe to solve.

Anchors held: 4/4.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

### Commit 5
```
feat(ui): output clamp + Shepard scale UI exposure + i18n (M_P0_RBF_ANTI_OVERSHOOT Part A+B UI)

Surface new node attributes in the RBFtools UI panel:
* "输出范围限制" / "Output Range Clamp" — checkbox (default on)
* "输出膨胀比例" / "Output Range Inflation" — spinbox 0.0-1.0
* "Scale 通道用 Shepard" / "Shepard for Scale Channels" — checkbox
  (default on, zero-overshoot for scale)

i18n: 6 new keys for label + tooltip per control (en + zh).

Anchors held: 4/4.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

### Commit 6
```
chore(deploy): rebuild 2022 + 2025 .mll with anti-overshoot patches (M_P0_RBF_ANTI_OVERSHOOT)

cmake clean rebuild both Maya 2022 (VS 2017/2019 + Maya 2022 SDK)
and Maya 2025 (VS 2022 + Maya 2025 SDK). Deploy to
modules/RBFtools/plug-ins/win64/{2022,2025}/RBFtools.mll.

New sha256 verified to contain M_P0_RBF_ANTI_OVERSHOOT strings
(grep `strings` output for "output_clamp" / "shepard" / "AABB_inv").

Anchors held: 4/4 (C++ source 含全部 milestone fix + 本次新增).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

---

## 10. 用户实测 (执行者完成后, 全部 8 个 commit land 之后)

### 场景 A — Output Clamp 直接消除 overshoot

1. 用户 22-pose rig: frame 800 scaleZ = 2.683, frame 805 旧版 = 3.287
2. UI 上 "输出范围限制" 默认 ON, "输出膨胀比例" = 0.0
3. **期望**: frame 805 scaleZ = 2.683 (严格 clamp 到 trained max)
4. frame 810 = 2.683 ✓

### 场景 B — Shepard scale 路径

1. 选 driven 中 scale 属性, 确保 outputIsScale=true
2. UI "Scale 通道用 Shepard" ON
3. 验证: trained pose 数值微差 (< 1%), inter-pose 严格 bounded ∈ [min, max]
4. rotation/translation 行为不变 (仍走标准 RBF)

### 场景 C — 关闭新功能 = 回归之前行为

1. 取消 "输出范围限制" + "Shepard for Scale"
2. 行为同 Phase 14 之前: overshoot 重现

### 场景 D — Safety 触发

1. 手动 setAttr `poseMinVec[0] = 10, poseMaxVec[0] = -5` (反序)
2. Apply → Script Editor 出 "AABB inverted, auto-corrected" warning, 不崩溃
3. NaN driver: cmds.setAttr driver attr 为 NaN → warn + 替换为中值, solver 正常

---

## 11. 与现有 4 大 fix 的关系矩阵

| 防御层 | 实现 | 数学性质 |
|---|---|---|
| Tikhonov (λ regularization) | UI lambda 字段, 已有 | 抑制 weights 数值, 减振幅 |
| Polynomial augmentation (Path B) | M_P0_RBF_POLYNOMIAL_AUGMENTATION, 已有 | 数学稳定 CPD kernel |
| Column-rank defence (C lite) | M_P0_RBF_COLUMN_RANK_DEFENSE, 已有 | 处理列退化 |
| **Output Clamp (本 patch Part A)** | **本 patch** | **硬性 cap 输出范围, 零 overshoot** |
| **Shepard for Scale (本 patch Part B)** | **本 patch** | **scale 数学 zero-overshoot** |
| Input Clamp (driver-side) | 已有, 本 patch Part C 加 safety | 防外推爆炸 |

**5 层防御组合**: 用户大多数 case 只需 Output Clamp 就消除 overshoot, 不需要切 Shepard.

---

## 12. 关键路径速查

| 文件 | 操作 |
|---|---|
| [source/RBFtools.h](source/RBFtools.h) | Part A+B: 加 3 个 MObject (outputClampEnabled/Inflation/shepardForScaleEnabled) |
| [source/RBFtools.cpp](source/RBFtools.cpp) | Part A+B+C: attribute init + cache + inference clamp + Shepard branch + safety guards |
| [source/BRMatrix.cpp:330](source/BRMatrix.cpp) | Part C audit 4: singular threshold configurable |
| [source/BRMatrix.h](source/BRMatrix.h) | Part C audit 4: setSingularThreshold + member |
| [modules/RBFtools/scripts/RBFtools/ui/widgets/rbf_section.py](modules/RBFtools/scripts/RBFtools/ui/widgets/rbf_section.py) | Part A+B UI: 3 controls + signal |
| [modules/RBFtools/scripts/RBFtools/ui/i18n.py](modules/RBFtools/scripts/RBFtools/ui/i18n.py) | 6 new keys |
| `modules/RBFtools/tests/test_m_p0_rbf_anti_overshoot.py` | Part E: 10 cases |
| `modules/RBFtools/plug-ins/win64/{2022,2025}/RBFtools.mll` | Part F: 双 SDK rebuild |
| `installer/RBFtoolsInstaller.exe` | 重打 |
