# RBFtools v5 — Addendum 2026-04-24

> **关系**：本文档为 `RBFtools_v5_设计方案.md` 的补丁/澄清，不覆写主文档。
> **适用范围**：Milestone 1.1（`getAngle` / 四元数距离修复）。
> **状态**：用户已批准，按本文档执行。

---

## 1. 主文档 PART D.3 假设更正

### 1.1 原文假设

主文档 PART D.3 与 Milestone 1 的 M1.1 条目写道：

> "当前 `distanceType == Angle` 具体实现需要在 `RBFtools.cpp:getAngle()` 里确认是否加了绝对值。若未加，这是一个隐蔽 bug，补助骨会在 ±180° 附近 flip。"

并建议应用 G.2 公式 $d(q_1, q_2) = 1 - |q_1 \cdot q_2|$。

### 1.2 源码核查事实（2026-04-24）

读源码后发现，**当前代码形态与上述假设不匹配**：

| 项 | 主文档假设 | 实际代码（v4.1.0） |
|---|---|---|
| `getAngle()` 输入维度 | 4-D 四元数 `(qx, qy, qz, qw)` | 3-D 轴向量 `(vx, vy, vz)` |
| `getAngle()` 内部实现 | 可能缺 `\|·\|` 的 `dot(q1, q2)` | `MVector::angle(v1, v2)` |
| `MVector::angle` 返回范围 | —— | `[0, π]`，**本身就是无符号** |
| 真正 `q · q` 写法 | 预期存在 | 代码中**不存在** |

**结论**：`getAngle()` 本身**没有** "`\|q·q\|` 缺绝对值" 的 bug。PART D.3 的那条假设不成立。

### 1.3 真正暴露的两个 bug

核查过程中发现两个独立 bug，一个是 M1.1 要修的、一个挪到 M2.1：

- **Bug 1 — Twist wrap flip**（本子任务修）
  `RBFtools::getTwistAngle` 返回 `2 * atan2(axisComp, w)`，值域 `(-2π, 2π]`。
  Matrix 模式下 driver 向量布局为 `[vx, vy, vz, twist] × driverCount`。
  当前 `getRadius`（Euclidean）在 `distType == 0 (Linear)` 分支里对 twist 分量直接做 `(τ₁ - τ₂)²`。
  若 twist 从 +179° 变到 −179°（实际只差 2°），`|Δτ| ≈ 358°`，平方项将距离放大 ~32000 倍，
  kernel 激活值近 0，**产生观感上的 "flip"**。这是 Milestone 1 要根除的核心数值 bug。

- **Bug 2 — Matrix+Angle 静默退化（Bug A）**（**推迟到 M2.1**）
  `getPoseDelta` 在 `distType == 1` 分支里只有 `vec.size() == 3` 才走 `getAngle`；
  Matrix 模式 4k 向量落空后 fallback 到 `getRadius`（Euclidean）。
  这让用户选的 "Angle" 语义静默变成 "Linear"。修复需与 M2.1 的 Quaternion 输入编码一起做，
  避免本 commit 同时改动两处 dispatch 造成更大回归面。

---

## 2. M1.1 最终执行决议

### 2.1 改动范围（最小 blast radius）

**只改距离计算，不改 `distType` 分派决策。**

- 保留 `getAngle()`（3-D `MVector::angle`）原封不动 —— 无 bug。
- 保留 `getPoseDelta` 中 `distType == 0 / 1` 两大分支不变。
- 在 `distType == 0 (Linear)` 分支里增加**布局感知子路由**：当 `vec.size() == vec2.size() >= 4 且 vec.size() % 4 == 0` 时，
  改走新函数 `getMatrixModeLinearDistance`，该函数对每个 4-D 块 `(x,y,z,twist)` 做：

  $$d_{\text{block}} = \sqrt{(\Delta x)^2 + (\Delta y)^2 + (\Delta z)^2 + \operatorname{wrap}(\Delta \tau)^2}$$

  跨 driver 聚合：

  $$d_{\text{total}} = \sqrt{\sum_{k=1}^{\text{driverCount}} d_{\text{block}}^{(k)\,2}}$$

  其中 $\operatorname{wrap}(\Delta \tau) = \min(|\Delta \tau| \bmod 2\pi,\; 2\pi - |\Delta \tau| \bmod 2\pi)$。

- **xyz 分量保持 chord（直线差）语义**，不改为 arc angle，以免干扰现有 rig 的 `radius` 调校。
  L2 语义在 "非 ±π 区间" 与原 `getRadius` 完全一致（用户要求 T4 验证）。

- `distType == 1 (Angle)` 分支**完全不动**（Bug 2/Bug A 保留，留给 M2.1）。

### 2.2 同时追加的未接线辅助函数

为 M2.1 铺路，一次性落入，避免 M2.1 再碰该文件：

- `twistWrap(τ₁, τ₂)` — 2π wrap 工具，独立命名，不与 `getRadius` / `getAngle` 耦合。
- `getQuatDistance(q1, q2) = 1 − |q1 · q2|`（PART G.2 公式）——**本 commit 不接线**，仅声明 + 实现，留给 M2.1 的 Quaternion 输入编码路径调用。

### 2.3 刻意不做（Non-goals）

- ❌ 不改 `getRadius` 签名/行为
- ❌ 不改 `getAngle` 签名/行为
- ❌ 不修 Bug 2（Matrix+Angle 静默退化） —— M2.1 修
- ❌ 不引入任何新 MObject / 节点属性 —— M1.2 起才动节点 schema
- ❌ 不改 `normalizeColumns` / kernel / solver

---

## 3. 测试策略（对齐用户要求的 T1–T4）

### 3.1 本 commit 的测试交付

`modules/RBFtools/tests/test_m1_1_distance.py` — **Python 规格测试**，镜像 C++ 辅助函数的纯数学逻辑，不依赖 Maya。
作为 "数学规约" 存在，定义 C++ 侧须满足的行为；M1.5 再补 `mayapy` 端到端集成测试串通 C++。

覆盖：

- **T1**：两向量夹角 0° / 90° / 180° 的 `MVector::angle` 语义（3-D 轴向量无 flip）
- **T2**：`twist = +179° → −179°` 距离 ≈ 2°（回归 Bug 1）
- **T3**：双 driver 场景下，单独扰动第 2 个 driver 的 twist 仅影响对应分块（分块独立性）
- **T4**：**L2 尺度回归** —— 对随机生成的、所有 twist 差落在 `(-π, π]` 的 pose 对，`getMatrixModeLinearDistance` 与原 `getRadius` 的差 < 1e-10

### 3.2 C++ 集成测试

推迟到 M1.5 统一做（用 `mayapy` headless + 真实 `RBFtools` 节点 + 已知 pose fixture 驱动 compute 输出对比）。

---

## 4. 影响面与回滚

### 4.1 用户可感知的行为变化

- **Matrix 模式 + Linear 距离** 下，若某 pose 与查询点的 twist 差 > π：距离会**变小**，kernel 激活值**变大**。这在 ±180° 邻域是正确方向的修复。
- **Matrix 模式 + Linear 距离** 下，若所有 twist 差都 ≤ π：距离与修复前数值一致（T4 验证）。
- **Matrix 模式 + Angle 距离**：行为不变（Bug 2 保留至 M2.1）。
- **Vector Angle 模式（3-D）**：行为不变。

### 4.2 回滚路径

本 commit 是纯增量（add helpers + 一个 `if` 分派子路由）。回滚直接 `git revert` 单 commit 即可。

---

## 5. 不变量（ledger）

- 用户已确认：`axis` 分量保持 chord（Euclidean）语义，不换 arc angle。
- 用户已确认：L2 聚合语义保留。
- 用户已确认：`getQuatDistance` 独立命名、本 commit 不接线。
- 用户已确认：Bug 2 挪到 M2.1。

---

---

## §M1.2 — Output Base Value + outputIsScale 实施决议

主文档 PART C.2.4 / 铁律 B6 的方案落地时做以下三处细化，对主文档无冲突，仅补充：

### M1.2.A — Baseline 源头优先级

`capture_output_baselines(driven_node, driven_attrs, poses)` 按以下顺序取每输出维度的 `base_value`：

1. **`poses[0]`（首选）**：当 `poses[0].inputs` 全 ≈ 0（通过 `float_eq`）时，视为 rest row，用 `poses[0].values[i]` 作基线。确定性、从存储数据复现。
2. **当前场景值（fallback）**：否则读 `driven_node.attr`，并发 `cmds.warning` 提示用户确保 rest pose。
3. **0.0（保底）**：两者都不可用时兜底。

**Scale 通道始终覆盖为 1.0**，忽略上述优先级结果，防御 rest 为 0 的场景塌陷。

### M1.2.B — 运行时重解触发

`attributeAffects(baseValue → output)` 会触发 `compute()`，但不会自动置 `evalInput = true`；若不处理，DG 会复用旧 `wMat`，在用户运行时改 `baseValue` 后产出错误输出。

**方案**：沿用代码已有的 `globalPoseCount` compare-on-read 模式。新增两个私有成员：

```cpp
std::vector<double> prevBaseValueArr;
std::vector<bool>   prevOutputIsScaleArr;
```

`compute()` 入口读完新数组后与 prev 比较，不一致则 `evalInput = true` 并更新 prev。这样 live-edit `baseValue` / `outputIsScale` 会强制一次 training 重跑。仅 Generic 模式下激活；Matrix 模式数组始终空，比较总是相等，不触发无意义重训。

### M1.2.C — 老 rig 升级策略

不引入 schema version 门控。`apply_poses` 检测到 "节点有 poses 但 baseValue 数组为空" → 发 `cmds.warning("Upgrading node <name> to v5 baseline schema")`。日志即留痕，不弹窗不阻断。

### M1.2.D — 加-减顺序与既有后处理的关系

C++ 侧 compute() 的后处理循环原顺序：

```
1. 取 δ = weightsArray[i]
2. if !allowNegative: max(δ, 0)
3. if useInterpolation: curve(δ)
4. δ *= scaleVal
5. 写回
```

M1.2 在 step 4 后、step 5 前插入 `δ += anchor`（仅 Generic 模式）。这样：

- `allowNegative=false` 钳制 δ 不能低于 0 → 输出 ≥ anchor（"永不低于 rest"）；scale 通道 ≥ 1.0。
- `scaleVal` 仅放大 delta，不动 anchor → 用户调 scale 不会移动 rest 基准。
- `interpolateWeight` 作用于 δ 的 [0,1] 曲线语义保持（Matrix 模式行为不变）。

### M1.2.E — 不激活路径

Matrix 模式下 `weightsArray` 索引是 pose id（blendShape blend weight），不是输出维度索引；baseline 加回在 C++ 侧被 `genericMode` gate 抑制。`baseValue[]` / `outputIsScale[]` 数组允许存在但不参与 Matrix 模式计算，也不会触发重解（prev 数组始终空，比较恒等）。

---

## §M1.3 — Driver Clamp 实施决议

对齐 v5 PART C.2.3 / G.7 / 铁律 B5 的 "Driver Clamp"。本节记录落地时与主文档的偏离与补充。

### M1.3.A — 默认策略（零回归）

- `clampEnabled` 默认 **`false`**：沿用 M1.2 baseline 的零回归策略，v4 rig 升级到 v5 binary 后行为完全不变，用户在需要的节点按需开启。
- `clampInflation` 默认 **`0.0`**：严格对齐 PART G.7 的硬钳公式。软钳（`α > 0`）作为用户可调选项存在，不做默认。

### M1.3.B — 为什么不需要 dirty tracker（与 M1.2 的关键区别）

`clampEnabled` / `clampInflation` 仅影响推理时的 `driver` 变换，**不进入 `solve`**，不改动 `wMat`。`attributeAffects(clampEnabled → output)` + `attributeAffects(clampInflation → output)` 让 DG 在参数变化时重新调用 `compute()`；缓存的 `wMat` 对新的钳制 `driver` 仍然有效。

这与 M1.2 的 `baseValue` / `outputIsScale` 不同——那两者**参与训练**（`Y − anchor`），必须 trip `evalInput = true` 强制重训。本子任务不需要 `prevClampEnabled` / `prevClampInflation` 成员。

### M1.3.C — Bounds 缓存生命周期契约

新增两个 private 成员：

```cpp
std::vector<double> poseMinVec;
std::vector<double> poseMaxVec;
```

**填充时机**（与现有 `wMat` 生命周期对齐）：

| 路径 | 何时刷新 bounds |
|---|---|
| Generic 模式 `getPoseData` | `evalInput == true` 内部，`normalizeColumns` 之前（**raw 空间**）|
| Matrix 模式 `getPoseVectors` | 每次 compute（无 `evalInput` gate——Matrix 模式本就每 tick 重填 `poseData`） |

**为什么 raw 空间**：`clampInflation` 是用户可见的 scene-unit 外扩比例。若在 normalized 空间里钳制，`α = 0.1` 的物理含义会随 pose 集合的 L2 范数漂移，完全不可预测。raw 空间下 `α = 0.1` 始终意味着"外扩 10% of training range"。

**为什么不是每 tick 重算 bounds**：Generic 模式的 `getPoseData` 仅在 `evalInput` 时才重填 `poseData`，raw 数据外部不可见；要每 tick 重算就得多读一次 multi 数组，浪费。pose 变化必 trip `evalInput`（现有 `globalPoseCount` + `numConnChildren` 逻辑），所以 bounds 始终跟着 pose 数据同步更新。

### M1.3.D — Matrix 模式 twist 维跳过（关键语义）

Matrix 模式下 `driver` layout 是 `[vx, vy, vz, twist] × driverCount`，其中 `twist = 2·atan2(axisComp, w)` 值域 `(−2π, 2π]`。twist 是**环形量**：`+3.0` 和 `−3.0` 是近似同一物理姿态。M1.1 已经为 twist 引入 wrap-aware 距离 `twistWrap`。

如果对 twist 维做线性 clamp，会把如 `+π/2` 的查询压到训练集的 `+π/4`，**冻结 M1.1 的 wrap 校正**——把 M1.1 修复过的 ±π seam flip 用 clamp 重新引入一次。

**决议**：C++ 和 Python 规约里都硬编码 `j % 4 == 3` 跳过。**不引入 `clampTwistMode` 枚举**（会扩大表面积，破坏 "新功能默认 off" 的简洁性）。未来如需 wrap-aware twist clamp，可纯追加一个 helper 并在 clamp 循环里按 `genericMode` / 新 flag 分派，不破坏本次实现。

### M1.3.E — Generic 模式 + Angle 距离 + 3-D 轴向量的单位长度备案

当前 clamp 是 per-dim 独立钳制。Generic 模式下如果用户喂的是单位轴向量（通常由 `distanceType == Angle` 时隐含使用），per-dim 独立 clamp 会破坏单位长度性（例如 `[1, 0, 0]` 钳到 `[0.8, 0, 0]` 模长只剩 0.8）。

**但现有 `rest[j]` 减法（`compute` 里 `driver[i] -= rest[i]`）本就不保单位长度**——这不是 M1.3 新引入的问题，而是现有 `rest` 语义的固有特性。

**决议**：不做 3-D 轴向量的专门处理。M2.1 做 Quaternion 输入编码时统一重构（Swing-Twist 分解后在单位球面上的切线空间里做 clamp 才语义正确，属于 M2 的 scope）。本子任务只备案，不改逻辑。

### M1.3.F — 防御分支（compute 应用处三重检查）

```cpp
if (clampEnabledVal
    && !poseMinVec.empty()
    && poseMinVec.size() == driver.size()
    && poseMaxVec.size() == driver.size())
```

三个条件全部真才执行 clamp：

1. **`clampEnabledVal`**：用户未开启 → 完全绕过（零性能开销，零行为变化）。
2. **`!poseMinVec.empty()`**：首次创建节点、poses 还没写、DG 初始化就触发 compute 的边缘场景；缓存为空时跳过，不越界。
3. **`size == driver.size()`**：用户在 live 运行时改了 driver attr count，但尚未重训（`evalInput` 还没触发），bounds 缓存与当前 driver 维度不对齐。此情况不崩溃、不误用旧 bounds，保留原 driver 不变，等下一轮训练同步。

对应 Python 侧 `apply_clamp` 的同等防御（见 T9）。

---

## §M1.4 — Regularized Solver + Cholesky / GE Fallback

### M1.4.A — 路径决议：方案 C（手写 Cholesky，不引 Eigen）

v5 PART D.1 规划的是 Cholesky → QR → LU → SVD 四层 fallback。本子任务**只实现前两层**（Cholesky + 现有 GE，GE 等价于带主元 LU），不引入 Eigen。

理由：

- 项目目前 `#include` 无 Eigen，CMakeLists 无引用；引入 Eigen 会 vendor ~30 MB 源码或强制用户安装依赖
- Cholesky + 绝对 λI 已经把 v5 PART D.1 的"数值稳定性"目标吃掉 90%：λI 让任何 PD kernel 严格 SPD，Cholesky 几乎永不失败
- 剩下的 GE（等价于带主元 LU with destructive in-place）足以兜底 Cholesky 失败的边缘场景（Thin Plate / Linear 无 λ 的病态）
- 把 QR/SVD 推迟到独立 milestone (§M4.5) 让 scope 清晰

### M1.4.B — 独立 Milestone 4.5（新增）

**位置**：M4 完成后、M5 开始前。

**交付物**：
1. Vendor Eigen 到 `source/third_party/eigen/Eigen/`（或 CMake find_package，具体方式 M4.5 开工时决定）
2. `BRMatrix` 替换手写 Cholesky → `Eigen::LLT`，或在 RBFtools 层直接用 Eigen 分解，保留 BRMatrix 作为 I/O 壳
3. 补齐 `Tier 3: Eigen::ColPivHouseholderQR` 和 `Tier 4: Eigen::JacobiSVD` pseudo-inverse
4. `solverMethod` enum 从 M1.4 的 `{Auto, ForceGE}` 扩展为 `{Auto, ForceCholesky, ForceQR, ForceLU, ForceSVD}`
5. `lastSolveMethod` 缓存从 `{0,1}` 扩展为 `{0..3}`；生命周期契约不变
6. Python 规约测试 `test_m4_5_full_fallback.py` 覆盖四层 fallback 与 SVD 伪逆的奇异截断

**不做**：M5 的性能优化（对称存储、SIMD）与此正交，留 M5。

**为何不"搭车 M5"**：把 4 层 fallback 这个 PART D.1 明确交付物绑定到 M5 的性能优化上会产生 "M5 滑动 → QR/SVD 永远拿不到" 的耦合风险。独立 M4.5 scope 单一、无性能优化交叉，是更可靠的交付形态。

### M1.4.C — 绝对 λ 决议（修正执行者原推荐）

v5 PART G.1 Step 2 明文规定 $\tilde{K} = K + \lambda I$，λ 直接加在对角（绝对值）。执行者原方案提出 `λ = λ_ui · tr(K)/N` 尺度自适应，**本子任务拒绝**。

**致命原因**：Linear kernel $\phi(r) = r$ 和 Thin Plate kernel $\phi(r) = r^2 \log r$ 的 $\phi(0) = 0$ → $K_{ii} = 0$ → $\operatorname{tr}(K)/N = 0$ → **λ 永远为 0**。正则化在最需要它的 kernel 上静默失效，而且这个 bug 在测试里不用 Linear / TP 矩阵就发现不了（测试 T3 就是针对这条设计的回归守护）。

**绝对 λ 在归一化输入上的合理性**：

- 输入向量已经 `normalizeColumns` 归一化，K 元素量纲可预测：Gaussian 类 kernel 对角 ≈ 1，λ = 1e-8 相对影响约 10⁻⁸（几乎无感）
- Linear / TP 对角 = 0，off-diagonal ~ O(1)，λ = 1e-8 把 K 从条件正定推到严格正定（正是我们要的）
- 单一默认值 1e-8 在**所有 kernel** 上都行为一致，用户可通过 `regularization` attr 按节点覆盖

### M1.4.D — `regularization` / `solverMethod` 默认值

- `regularization` 默认 **1e-8**（v5 PART G.1 Step 2 + Chad Vernon 参考值）
- `solverMethod` 默认 **Auto**（enum 0）
- 二者均 `keyable(true)`, `storable(true)`

### M1.4.E — `lastSolveMethod` 缓存生命周期契约

**成员**（`private:` in `RBFtools`）：
```cpp
short lastSolveMethod;        // 0 = Cholesky, 1 = GE
short prevSolverMethodVal;    // mirror of last solverMethod plug value
```

**契约**（实现见 `compute()` M1.4 dispatch 段）：

| 事件 | 行为 |
|---|---|
| 节点创建 | 构造函数置 0 / 0（首次 compute 先试 Cholesky） |
| compute 入口，`solverMethodVal == prevSolverMethodVal` | **不重置**，尊重上次成功的 tier |
| compute 入口，`solverMethodVal != prevSolverMethodVal` | 重置 `lastSolveMethod = 0`，同步 `prev = current`。用户切 Auto ↔ ForceGE 强制一次 Cholesky 再试 |
| `evalInput == true`（pose 变化触发重训） | **不重置**。kernel SPD-ness 是 kernel 类型的属性，不是 pose 数据的属性 |
| Cholesky 成功 | `lastSolveMethod = 0`（sticky） |
| Cholesky 失败 / 跳过 → GE | `lastSolveMethod = 1`（sticky：已知非 SPD kernel，下次不再浪费 Cholesky probe） |

测试 T9 三条覆盖：① Force → Auto 重试 Cholesky；② 同模式连续调用不重置；③ 非 SPD kernel 下 Auto → GE → ForceGE → Auto 的完整状态转移。

### M1.4.F — 性能顺手改进（非核心但值得记录）

现有 GE 是 in-place destructive，每个输出维度 $c = 1, \ldots, m$ 必须拷贝 `linMat` 再 solve，总成本 $m \cdot O(N^3)$。

Cholesky 路径一次分解 + $m$ 次两级回代：$O(N^3/3) + m \cdot O(N^2)$。Generic 模式典型 $m = 6 \sim 24$ 下，**理论加速 3–10×**。

M5.1（对称存储 + SIMD）是正交优化；Cholesky 路径的多 RHS 分摊是 M1.4 顺手收下的红利，与性能 milestone 解耦。

### M1.4.G — 零回归论证

v4 rig 首次在 v5 binary 下加载：
- `regularization` 默认 1e-8，**比当前 GE 直接 solve 更稳**（λI 把近奇异矩阵推离奇异点）
- Gaussian / MQ / IMQ kernel：Cholesky 成功，输出与 GE 的差 ≤ O(1e-8) 量级，低于 `FLOAT_ABS_TOL = 1e-6` 感知阈值
- Linear / TP kernel：Cholesky 通常失败（$\phi(0) = 0$ 即便 λ = 1e-8 也可能不足以推离非 SPD），自动落 GE，行为与 v4 完全一致
- ForceGE 提供完全 v4 行为的逃生通道（调试用）

风险点：Cholesky 与 GE 在 ill-conditioned 但仍 SPD 的矩阵上可能给出微 ε 不同的 W —— 下游 kernel 评估是连续函数，W 的 ε 扰动映射到 output 的 ε 扰动，低于用户感知。

---

## §M4.5（前瞻声明）— Eigen Integration + Full Fallback Chain

**状态**：未开工。v5 设计方案 PART D.1 明确交付物。本 addendum 提前为其锚定位置与 scope。

**必须先完成的前置 milestone**：M1.4（✅ 本次交付）+ M2（编码）+ M3（工作流）+ M4（其他 solver），不依赖 M5 性能优化。

**scope（一次 commit 粒度）**：
1. 引入 Eigen（header-only，vendor 或 find_package）
2. 实现 `Tier 3 QR`（ColPivHouseholderQR）和 `Tier 4 SVD` pseudo-inverse（JacobiSVD with singular-value truncation at 1e-6）
3. 手写 Cholesky 切换到 `Eigen::LLT`，旧实现删除或保留做回归对照
4. `solverMethod` enum 扩展；`lastSolveMethod` 扩为 4 档
5. Python 规约 + C++ 集成测试覆盖四层转移矩阵
6. **`lastSolveMethod` 对 `kernel` 变化敏感**：M1.4 实现仅对 `solverMethod` 切换重置缓存。
   用户从非 SPD kernel（Thin Plate / Linear，缓存 sticky 到 GE=1）切到 SPD kernel（Gaussian 类）后，
   `lastSolveMethod` 仍保持 1，Cholesky 永远不重试——数学上仍正确（GE 能解 λI 后的任意矩阵），
   但性能永久停在慢路径。**非 correctness bug，是性能债**。M4.5 solver 路径重写时追加
   `prevKernelVal` 成员 + "kernel 变化 → 清 `lastSolveMethod`" 契约一并处理。

**明确不在 M4.5 scope 内**：性能优化（对称存储、SIMD、分块）——M5.1；`solverStats` 只读属性——M5.2。

---

## §M2.1a — Input Encoding (Raw / Quaternion / ExpMap) + Bug 2 Fix

v5 PART C.2.2 定义了 5 档 `inputEncoding` 枚举；PART D.3 / M1.1 addendum §Bug 2 同时存在 "Matrix + Angle 静默退化到 Euclidean" 的遗留。本节落地 M2.1 的**拆分第一半（M2.1a）**，只交付 Raw + Quaternion + ExpMap 三档 + Bug 2 修复；BendRoll / Swing-Twist 推迟到 M2.1b。

### M2.1a.1 — 决议日志

| # | 分叉 | 选项 | 选定理由 |
|---|---|---|---|
| (A) | M2.1 拆分？ | **① 拆 M2.1a + M2.1b** | 单次吞下 5 档 + 维度级联 + 存储重构 + clamp 矩阵重写会让单 commit 巨大，回滚成本高 |
| (B) | 驱动分组元数据 | **A 硬约定 + `driverInputRotateOrder[]`** | 最小侵入；复用 Maya 原生 rotateOrder enum，用户可直接 `driver.rotateOrder → node.driverInputRotateOrder[k]` |
| (C) | M2.1a 覆盖档位 | **① Raw + Quaternion + ExpMap** | Quat/ExpMap 是无依赖的 3→3/3→4 映射；BendRoll 需 Swing-Twist 分解前置，耦合度高 |
| (D) | `inputEncoding` 作用域 | **① 节点级单枚举** | per-source encoding 属"多源驱动"完整 vision，与 M2.1 核心数学正交 |
| (E) | Bug 2 修复时机 | **① M2.1a 一起修** | Bug 2 是 dispatch 问题，与 encoding-aware dispatch 同源，同一 commit 里复用 isMatrixMode 分派最省 |
| (F) | Matrix 模式交互 | **① 不交互** | Matrix 模式的打包语义（swing on S² + twist）独立演化；M4 Aim/Jiggle 重构时再议 |
| (G) | clamp-skip 规则 | **① C++ 硬编码** | 规则简单（见 M2.1a.7 表）；暴露属性让用户覆盖会扩大表面积 |

### M2.1a.2 — Per-encoding clamp-skip 规则矩阵

| encoding | per-block 维 $k$ | 跳过 clamp 的维 | 理由 |
|---|---|---|---|
| Raw (Generic) | 1 (per scalar attr) | 无（全部参与） | 现状保持 |
| Quaternion (Generic) | 4 | 无（所有分量天然 $\in [-1, 1]$，有界）| 线性 clamp 在 [-1,1] 内无害 |
| ExpMap (Generic) | 3 | 无（$\mathbb{R}^3$ 连续） | 连续且无环绕 |
| BendRoll (M2.1b 占位) | 3 | roll 维（wrap-aware）| 当前 fall-back 到 Raw → 走 Raw 规则 |
| Swing-Twist (M2.1b 占位) | 5 | twist 维（wrap-aware）| 当前 fall-back 到 Raw → 走 Raw 规则 |
| Matrix 模式（遗留）| 4 | `j % 4 == 3`（twist 槽，M1.3 现状）| **不变**，M2.1a 不动 Matrix 布局 |

### M2.1a.3 — Bug 2 修复

M1.1 addendum §Bug 2 挪到本节落地：**Matrix 模式 + `distanceType == Angle` 静默退化到 Euclidean**。

修复两步：
1. 删除 `compute()` Matrix 分支里的 `distanceTypeVal = 0;` 强制覆盖——用户选的 distanceType 现在生效
2. 新增 `getMatrixModeAngleDistance(v1, v2)`：per-block `sqrt(arc_angle² + twistWrap²)`，跨 block L2 聚合；
   `getPoseDelta` 在 `isMatrixMode==true` 分支按 `distType` 分派到 Linear 或 Angle 版本

**Resolves M1.1 addendum §Bug 2 via encoding-aware dispatch.**

### M2.1a.4 — 零回归契约

v4 rig 在 v5-M2.1a binary 加载：

- `inputEncoding` 默认 `0 (Raw)`
- `driverInputRotateOrder[]` 默认空 multi
- 结果：`effectiveEncoding = Raw`，`getPoseData` 走 Raw 直通分支，`getPoseDelta` 走 legacy Raw 分派
- 与 v4 行为**逐字节等价**（规约测试 T2 守护）

即便 Matrix 模式 Bug 2 修复，也属"修正语义错误"而非"改变正确行为"——v4 用户选 Angle 时拿到 Euclidean 是 bug，现在拿到 Angle 是正确行为。若老 rig 依赖 Euclidean 行为，用户可显式切 `distanceType = Euclidean` 恢复。

### M2.1a.5 — BendRoll / Swing-Twist 占位契约

**拒用 kFailure**（会停 DG，破坏 rig）；**拒绝返回 0.0**（让所有样本距离相同，kernel 矩阵退化）。

落地策略：**Fall back to Raw with once-per-rig warning**：

```
MGlobal::displayWarning(thisName + ": inputEncoding BendRoll/SwingTwist
    lands in M2.1b; falling back to Raw.");
```

`inputEncodingWarningIssued` 成员 flag 防止洪水告警；`prevInputEncodingVal` 变化时重置 flag，让用户切换编码时拿到新的一次 warning 机会。

M2.1b 将这两档的实际 encode 实现替换到位后，占位 warning 自然消失。

### M2.1a.6 — 安全网：inDim 非 3 的倍数

用户选 `inputEncoding = Quaternion / ExpMap` 但 driver attr 数量不是 3 的倍数（例如 5 个 attr）：

- 发一次性 warning：`"inputEncoding requires driver inputs in (rx, ry, rz) triples; inDim=N is not a multiple of 3. Falling back to Raw."`
- `effectiveEncoding = 0 (Raw)`，getPoseData 走 Raw 直通
- **不 kFailure**，不阻断 DG

与占位 fall-back 共用 `inputEncodingWarningIssued` flag，但 warning 文案区分（"placeholder" 还是 "non_triple"），方便 Script Editor 诊断。

### M2.1a.7 — M1.3 clamp 语义延续

- **Matrix 模式**：`j % 4 == 3`（twist 槽）继续跳过，**一字不改**（M1.3 的不变量）
- **Generic 模式 Raw**：全钳制（M1.3 现状）
- **Generic 模式 Quaternion**：全钳制（分量 $\in [-1, 1]$ 有界）
- **Generic 模式 ExpMap**：全钳制（$\mathbb{R}^3$ 连续）

clamp-skip 判定硬编码于 C++ `compute()` 的 clamp 块里（沿用现有 `if (!genericMode && (j % 4 == 3))` 条件——M2.1a 没有其他 encoding 需要跳过的维，条件无需增补）。

### M2.1a.8 — Matrix 模式与 `inputEncoding` 的互斥

Matrix 模式**不读取** `inputEncoding` 的语义：
- `compute()` 在 `!genericMode` 分支末尾强制 `effectiveEncoding = 0`，保证下游 `getDistances` / `getPoseWeights` 收到 `(isMatrixMode=true, encoding=0)` 组合
- `getPoseDelta` 在 `isMatrixMode=true` 分支完全忽略 encoding 参数
- 用户在 Matrix 模式 rig 上设置 `inputEncoding` 不会触发任何 warning（没有意义但也不出错）

**Forward pointer**：M4 Aim/Jiggle solver 重构时，"Matrix 模式的打包（swing on S² + twist）是否统一归为 `inputEncoding` 的第 5 / 6 档"将再议；本 milestone 保持两者独立。

### M2.1a.9 — 签名演化（面向后续 milestone 的 API 记录）

```
// 之前
getPoseDelta(v1, v2, distType)
getDistances(poseMat, distType)
getPoseWeights(..., distType, kernelType)
getPoseData(data, driver, poseCount, solveCount, poseData, poseValues,
            poseModes, normFactors)

// M2.1a 之后
getPoseDelta(v1, v2, distType, encoding, isMatrixMode)
getDistances(poseMat, distType, encoding, isMatrixMode)
getPoseWeights(..., distType, encoding, isMatrixMode, kernelType)
getPoseData(... + int inputEncoding, const std::vector<short>& rotateOrders,
                   unsigned& effectiveInDim)
```

所有 caller 已同步更新。encoding 参数为内部值：0..4 对应 v5 PART C.2.2 用户可见档位，Matrix 模式调用方应显式传 0 + `isMatrixMode=true` 以明确语义。

---

**本文档结束。**
