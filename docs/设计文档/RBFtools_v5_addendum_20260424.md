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

---

## §M2.1b — BendRoll + SwingTwist Encodings + Swing-Twist 分解

M2.1a 声明了 5 档 `inputEncoding` 但只落了 Raw / Quaternion / ExpMap 三档；BendRoll (2) 与 SwingTwist (4) 为占位 fall-back。M2.1b **解除占位**，把这两档的数学实现接入 M2.1a 框架。**不碰** attr schema、**不碰** dispatch / 签名框架。

### M2.1b.1 — 决议日志

| # | 分叉 | 选项 | 选定理由 |
|---|---|---|---|
| (A) | BendRoll 边界处理 | **② 不 canonicalize + ε = 10⁻⁴** | 连续优于 canonicalize 的 θ=π 翻转；ε=10⁻⁴ 在归一后不触发 kernel 数值失守 |
| (B) | Swing-Twist 分解退化 fallback | **① identity swing + zero twist** | 退化集合是 q_w=0 ∧ q[axis]=0（测度零），fallback 行为可预测；不要求 round-trip |
| (C) | Clamp-skip 接入 | **① 查表 mask** | 清晰、可扩展、O(N) 额外内存可忽略 |
| (D) | SwingTwist 复合距离权重 | **① $w_{\text{twist}} = 1.0$** | 经 `normalizeColumns` 按列 L2 归一后 swing 与 twist 量纲自动平衡；用户覆盖推 M3 |
| (E) | twistAxis 复用 | **① 节点级 `twistAxis`** | M3 + UI 时再考虑 per-group；当前零侵入 |
| (F) | BendRoll 3-tuple 布局 | **① `(roll, bendH, bendV)`** | 首位 roll 对应 wrap-aware，skip `j%3==0` 最自然对齐 M1.3 pattern |

### M2.1b.2 — 数学规约（核心公式）

**Swing-Twist 分解**（v5 PART G.3）：给定单位四元数 $q = (q_x, q_y, q_z, q_w)$ 和扭转主轴 $\hat{\mathbf{a}}$（X/Y/Z），令 $a = (q_x, q_y, q_z) \cdot \hat{\mathbf{a}}$：

$$\|t\|^2 = q_w^2 + a^2, \quad q_{\text{twist}} = \frac{(q_w, a\hat{\mathbf{a}})}{\|t\|}, \quad q_{\text{swing}} = q \cdot q_{\text{twist}}^{-1}$$

$$\tau = 2\operatorname{atan2}(a, q_w)$$

退化 fallback ($\|t\|^2 < 10^{-12}$)：$q_{\text{swing}} = (0,0,0,1)$, $\tau = 0$.

**BendRoll**（v5 PART G.4 + ε 加固）：从 swing 四元数 $(s_x, s_y, s_z, s_w)$，选 twist 轴正交平面内两坐标 $(s_h, s_v)$：

$$\tilde{s}_w = \max(s_w, -1 + \varepsilon), \quad \varepsilon = 10^{-4}$$

$$\text{bend}_H = \frac{2 s_h}{1 + \tilde{s}_w}, \quad \text{bend}_V = \frac{2 s_v}{1 + \tilde{s}_w}, \quad \text{roll} = \tau$$

Per-group 3-tuple: $(\text{roll}, \text{bend}_H, \text{bend}_V)$, stride = 3.

**SwingTwist**：直接 5-tuple $(s_x, s_y, s_z, s_w, \tau)$ per group, stride = 5.

**SwingTwist 复合距离**（本子任务新增，全局用户拍板 $w_{\text{twist}} = 1.0$）：

$$d(v_1, v_2) = \sqrt{\sum_{k} \left[(1 - |q_{\text{swing},1}^{(k)} \cdot q_{\text{swing},2}^{(k)}|)^2 + \operatorname{twistWrap}(\tau_1^{(k)}, \tau_2^{(k)})^2\right]}$$

### M2.1b.3 — ε 数值分析（(A)② 决议）

Denominator $1 + \tilde{s}_w \in [\varepsilon, 2]$。ε=10⁻⁴ 下最坏 amplification = $2/\varepsilon = 2 \times 10^4$。

| swing 角度 | $s_w$ | denom | 最大 bend 幅值（$s_h = 1$）|
|---|---|---|---|
| 0 (静态) | 1.0 | 2.0 | 1.0 |
| π/2 (90°) | 0.707 | 1.707 | 1.17 |
| π (180° 精确) | 0.0 | 1.0 | 2.0 |
| π + 10⁻² (微外推) | -0.005 | 0.995 | 2.01 |
| π + 10⁻³ | -0.0005 | 0.9995 | 2.001 |
| 2π − 10⁻⁴（ε 触发线）| 0.999... | 1.999... | 1.0 |

**典型补助骨 swing < π/2**：denom > 1.7，ε 完全不启动；BendRoll 幅值 ≤ 1.2 量级——对 RBF kernel 完美。ε 的作用仅在极端 > π 的 swing 场景，此时 ε=10⁻⁴ 把幅值上限钳在 $2 \times 10^4$，归一化后仍可用。

**没有热路径 boundary 分支**：`std::max(s_w, -1 + ε)` 一行，无 if 分支；边界由 T14 锚定测试约束。

### M2.1b.4 — Clamp-skip 规则矩阵（最终完整版）

| encoding | 作用域 | per-block 维 | 跳过位 (relative offset) | 理由 |
|---|---|---|---|---|
| Raw | Generic | 1 | 无 | 全钳制 |
| Quaternion | Generic | 4 | 无 | 分量 $\in [-1, 1]$ 有界 |
| BendRoll | Generic | 3 | **0 (roll)** | twist 是 wrap-aware 圆量 |
| ExpMap | Generic | 3 | 无 | ℝ³ 连续 |
| SwingTwist | Generic | 5 | **4 (twist)** | twist 是 wrap-aware |
| （任意） | Matrix | 4 | 3 (twist) | M1.3 不变 |

实现：`compute()` 在 clamp 前构建 `std::vector<bool> clampSkipMask(dim)`，按 (isMatrixMode, effectiveEncoding) 填；clamp loop 按 mask 跳过。详见 (C)①。

### M2.1b.5 — q ≡ -q 符号歧义契约（测试 T16.c 守护）

四元数 $q$ 与 $-q$ 表示同一旋转。`decomposeSwingTwist(q)` 与 `decomposeSwingTwist(-q)` **不必**产生相同的 4-tuple swing / scalar twist，但：

$$q = q_{\text{swing}} \cdot q_{\text{twist}}, \quad -q = (-q_{\text{swing}}) \cdot q_{\text{twist}}\quad \text{or} \quad q_{\text{swing}} \cdot (-q_{\text{twist}})$$

任一代表都满足 round-trip。`getQuatDistance(q_{\text{swing}, 1}, q_{\text{swing}, 2}) = 1 - |q_1 \cdot q_2| \approx 0$，因此下游 RBF 训练在 $q$ 与 $-q$ 的两种表示上产生**同一**权重——不会因符号歧义引入非确定性。

### M2.1b.6 — `twistAxis` 零回归分析

- `twistAxis` attr（`RBFtools.cpp:217`，default 0 = X）在 M2.1a 及以前**仅** Matrix 模式 `getPoseVectors` / `getTwistAngle` 路径消费
- M2.1b 首次让 Generic 模式（通过 BendRoll / SwingTwist）读此 attr
- **零回归路径**：v4 rig 升级后 `inputEncoding` 默认 Raw，**永不触发** BendRoll/SwingTwist encode 分支，`twistAxis` 仍不读；只有用户主动切到 BendRoll/SwingTwist 才开始消费，属"新功能启用"，不是回归
- Raw / Quaternion / ExpMap 路径**不触碰** `twistAxis`

### M2.1b.7 — 零回归回归测试

M1.1–M1.4 + M2.1a 的 102 条测试保持全绿（T12 从 M2.1a 剔除，因其验证的是 M2.1a-to-M2.1b 过渡期占位契约，已被 M2.1b 超越；说明移至 M2.1a 文件注释中）。Raw 行为字节级等价由 M2.1a T2 持续守护。

### M2.1b.8 — M2.2 QWA 前瞻契约（锁定）

**SwingTwist 输出格式契约**（编入 `encodeSwingTwist` 注释 + 此处）：

- per-block layout = `(sx, sy, sz, sw, τ)`，stride = 5
- 前 4 分量 $(s_x, s_y, s_z, s_w)$ 为**标准单位四元数**（unit norm 由 T12p 验证）
- M2.2 QWA 如需从 SwingTwist-encoded 驱动向量提取四元数序列作为加权平均输入，**按 stride=5 前 4 维切片**即可

**BendRoll 不可消费为 QWA 源**：立体投影是有损（roll 是标量而非旋转分量），不可逆回到四元数。用户若需要 QWA 数据流，需把 driver 切到 `Quaternion` 或 `SwingTwist` 编码。

此契约提前锁定，M2.2 开工时不需再回溯核查 M2.1b 的数据布局。

### M2.1b.9 — 推迟项（Non-goals 对齐）

- ❌ v5 PART C.2.7 分字段 pose 存储（`poseSwingQuat` / `poseTwistAngle` 缓存）→ **M2.5**
- ❌ per-group `driverInputTwistAxis[]` → M3（加 UI 时一起做）
- ❌ `swingTwistWeight` 属性（复合距离加权可调）→ M3
- ❌ 新增 MObject → 本次 commit **一个也不加**
- ❌ 修改 `twistAxis` default / enum → 零侵入

### M2.1b.10 — 签名演化记录

```
// getPoseData (M2.1b +1 param)
//   +unsigned twistAxis    — 让 BendRoll/SwingTwist encode 能拿到主轴

// 其他签名 (M2.1a 已定) 保持不变
getPoseDelta(v1, v2, distType, encoding, isMatrixMode)     // M2.1a, 不变
getDistances(poseMat, distType, encoding, isMatrixMode)    // M2.1a, 不变
getPoseWeights(..., distType, encoding, isMatrixMode, ...) // M2.1a, 不变
```

BendRoll (encoding=2) + SwingTwist (encoding=4) 现在在 `getPoseDelta` Generic 分支里有**实际实现路径**，不再 fall-through 到 Raw。

---

## §M2.2 — Quaternion Weighted Average (QWA) Output Encoding

v5 PART D.4 / G.6 的 QWA 落地：输出端支持把连续 4 个 output slot 声明为一组 quaternion，用协方差矩阵最大特征向量代替标量加权和，解决 LERP 退化 + 单位长度破坏问题。本节记录决议、数学、使用点索引。

### M2.2.1 — 决议日志

| # | 分叉 | 选项 | 选定理由 |
|---|---|---|---|
| (A) | path (a) delta-train vs (b) direct | **① path (b) 直接 QWA** | 开题证明交换律 ⇒ 常数 $q_{\text{base}}$ 下 (a) ≡ (b)；选实现简单的 (b) |
| (B) | 输出 quat group 识别 schema | **A 节点级 `outputQuaternionGroupStart[]` int multi** | 显式 start-only schema（隐式 count=4），cleaner than compound；零回归 empty→dormant |
| (C) | 特征值求解器 | **① Power Iteration + dual-seed fallback** | 手写轻量，无 Eigen 依赖；M4.5 swap for `SelfAdjointEigenSolver<Matrix4d>` |
| (D) | scale ∩ quat 冲突 | **① 两者都跳 + warning** | 拒绝 silent override；用户显式修正 |
| (E) | 退化 fallback | **① identity quat + 一次性 warning** | 沿用 M2.1 模式；DG 永不停 |
| (F) | Power Iteration 初始向量 | **① identity (0,0,0,1) 主 + `M·(1,1,1,1)` 副** | 主 seed 贴 rest-pose-typical 场景；副 seed 覆盖 QWA-adversarial 边界 |
| (G) | 符号规范 | **① 强制 $q^*_w \ge 0$** | 与 M2.1b SwingTwist 对齐；消除 $q \equiv -q$ 歧义 |
| (Q8) | 负权重 PSD 保护 | **仅 QWA 路径 `max(0, φ_i)` 截断** + 一次性 warning | 标量 M1.2 路径完全不动 |
| (Q9) | isQuatMember 掩码架构 | **单一来源（compute 内构建一次，4 使用点消费）** | 避免派生漂移 |

### M2.2.2 — 交换律完整证明（path (a) ≡ (b) 的理论基础）

四元数右乘 $q \mapsto q \cdot q_0$ 作用于 $\mathbb{R}^4$ 列向量是一个线性变换：

$$R(q_0) = \begin{pmatrix} d & c & -b & a \\ -c & d & a & b \\ b & -a & d & c \\ -a & -b & -c & d \end{pmatrix}, \quad q_0 = (a, b, c, d)^\top$$

**正交性**：对 $\|q_0\|^2 = a^2 + b^2 + c^2 + d^2 = 1$，$R^\top R = I$。（验证：4 列两两内积 = 0；每列 norm² = $a^2+b^2+c^2+d^2 = 1$）

**反同态**：$R(q \cdot q') = R(q') \cdot R(q)$。由此 $R(q_0^{-1}) = R(q_0)^\top$。

**path (a) 推导**：

$$\tilde{q}_i = R^\top q_i \implies \tilde{M} = \sum_i w_i \tilde{q}_i \tilde{q}_i^\top = R^\top M R$$

$$\tilde{q}^* = \arg\max_{\|q\|=1} q^\top \tilde{M} q = \arg\max_{\|q\|=1} q^\top R^\top M R q$$

代换 $u = R q$（正交保范）：$q^\top R^\top M R q = u^\top M u$，所以 $\tilde{q}^* = R^\top u^*$，其中 $u^* = \arg\max u^\top M u$ 是 pure QWA。

**重组**：

$$q^{*(\text{a})} = \tilde{q}^* \cdot q_0 = R(q_0) \tilde{q}^* = R R^\top u^* = u^* = q^{*(\text{pure})}$$

**结论**：对常数 $q_{\text{base}}$，path (a) 与 path (b) 产出位级相同。实施走 (b)。

### M2.2.3 — Power Iteration 数学 + dual-seed 策略

**核心算法**：对 4×4 对称 PSD 矩阵 $M$，迭代 $q_{k+1} = \operatorname{normalize}(M q_k)$ 收敛到 $\lambda_1$ 的特征向量。

**收敛速率**：$\|q_k - v_1\| \lesssim (\lambda_2/\lambda_1)^k \|q_0 - v_1\|$。QWA 补助骨场景（样本聚集、rank-1 dominant）下 $\lambda_1/\lambda_2 \gg 1$，15-20 iter 收敛。

**停止判据**：$\|q_{k+1} - q_k\|_2 < 10^{-8}$ **或** $|q_{k+1} \cdot q_k| > 1 - 10^{-16}$（dot 判据处理可能的符号振荡，实践中罕见但守护了边界）。

**Dual-seed 策略**（(F)① 扩展）：

1. **主 seed**：$(0, 0, 0, 1)$ identity quat。rest-pose-biased，典型查询快速收敛。
2. **副 seed**：$M \cdot (1, 1, 1, 1)^\top$ 归一化。当主 seed 与 $v_1$ 接近正交（测试用全随机 S³ 样本时可发生，实际 rig 场景极罕见）时，副 seed 保证与 $v_1$ 有非零分量（因为 $M \cdot \mathbf{1}$ 是 $M$ 列和，在 SPD 下必有 $v_1$ 分量）。

若两 seed 都 50-iter 未收敛 → 返回 $(0, 0, 0, 1)$ identity + `qwa_no_converge` 一次性 warning（(E)）。

### M2.2.4 — **Q8**：负权重 PSD 保护

$M = \sum_i w_i q_i q_i^\top$ 要求 $w_i \ge 0$ 才保证 PSD（从而最大特征值有合理几何语义）。

**问题**：
- `allowNegative` attr default `true`
- 某些 kernel（MQ variants）激活值可负
- `interpolateRbf` 输出不保证非负

**若 $w_i < 0$，$M$ 失去 PSD 性**：可能产生负特征值，Power Iteration 可能返回反向四元数（反映同旋转的另一半球），收敛性能也无保证。

**决议**：**仅在 QWA 累加路径**做 `phi_i_qwa = max(0, phi_i)` 截断。首次截断触发 `qwa_clipped_weights` 一次性 warning。

**关键**：**标量路径完全不截断**。allowNegative / interpolateWeight / scale 的语义对 scalar output 不变（M1.2 behavior intact）。负权重仅对 QWA 是 PSD 破坏源。

### M2.2.5 — **Q9** / §MASK-INDEX：`isQuatMember[]` 单一来源架构

`isQuatMember[j]` 是 **output-dim × 1** 的 bool 掩码，由 `resolveQuaternionGroups` 在 `compute()` 早期**构建一次**，被以下 **4 个使用点**只读消费：

| # | 使用点 | 作用 |
|---|---|---|
| 1 | **M1.2 subtract-before-solve**（`yCols` 构建）| `isQuatMember[c]==true` → `yCols[c] = zeros`（跳过 baseline 减法 + 跳过 solve）|
| 2 | **M1.4 Cholesky / GE solve**（wMat 列）| 通过 (1) 的零 yCols 自动产生零 wMat 列（无额外判断） |
| 3 | **M1.2 add-back + post-processing**（final weight loop）| `isQuatMember[i]==true` → `continue`（保留 QWA 写入的值；不走 allowNegative / interpolate / scale / baseline）|
| 4 | **getPoseWeights QWA 累加**（反向使用）| `isQuatMember[j]==true` → 跳过 scalar sum；QWA 累加 $M_g$ 代替 |

**禁止**任何使用点重新派生掩码。派生位置:
- 声明：`std::vector<bool> isQuatMember(solveCount, false);` 在 `compute()` 的 baseline-read 块之后
- 填充：由 `resolveQuaternionGroups(rawStarts, solveCount, outputIsScaleArr, validStarts, isQuatMember, anyInvalid)` 写入
- 传递：按值 const& 传给 `getPoseWeights`（使用点 3 直接读 compute() scope 内变量）

### M2.2.6 — 配置验证规则（`resolveQuaternionGroups`）

Raw starts 被依次检查，**有以下任一问题的整组丢弃**，剩下的继续：

1. **越界**：`s < 0` 或 `s + 4 > solveCount`
2. **重叠**：该组 4 个 slot 中任一已被前组占用
3. **与 scale 冲突**：该组 4 个 slot 中任一 `outputIsScale[s+k] == true`

任一组被丢弃 → `anyInvalid = true` → compute() 发一次性 `qwa_config` warning。用户需要显式修正（拒绝 silent override 符合 (D)①）。

配置 hash 基于 order-sensitive rolling 函数：用户编辑 starts 时 `prevQuatGroupConfigHash` 变化 → 重置 3 个 warning flag + trip `evalInput = true` 强制重训 wMat（同步与新 `isQuatMember` 对齐）。

### M2.2.7 — 零回归契约

**空 `outputQuaternionGroupStart[]`**（v4 rig 升级 + 未显式声明）：

- `rawStarts` 为空 → `resolveQuaternionGroups` 返回空 `validStarts` + 全 false `isQuatMember`
- `getPoseWeights` 内 QWA 累加 `gCount == 0`，完全跳过
- 所有 4 个使用点 mask 全 false → 行为字节级等价 M2.1b

**测试 T9** 守护该契约；M1+M2.1 的 130 条测试在 M2.2 改动后全绿 ⇒ 零回归验证通过。

### M2.2.8 — **§CORNER-PATH-A**：path (a) 显式 delta 模式的未来扩展路径

当前 M2.2 实施 path (b) 直接 QWA。**交换律证明（M2.2.2）作为 path (a) 未来落地的数学保证**：

未来场景（M3 或独立子任务）可能需要：
- **per-sample $q_{\text{base},i}$**：每个 pose sample 关联不同 rest quaternion
- **外部 API 对称性**：下游消费方约定"给我 delta 四元数"的接口
- **局部 Transform 双存储**（M2.3 的一部分）：rest-frame 变换可能需要 delta 分解

此时重新启用 delta 路径（$\tilde{q}_i = q_i \cdot q_0^{-1}$），经过 QWA 后乘回 $q_0$。**数学等价性由本证明保证**，实施时只需改训练存储 + 推理重组两处，QWA 核心代码不动。

### M2.2.9 — **§M4.5-FORWARD**：Eigen 替换指针

M4.5 引入 Eigen 后：

```cpp
Eigen::Map<const Eigen::Matrix4d> Mmat(M);  // row-major
Eigen::SelfAdjointEigenSolver<Eigen::Matrix4d> es(Mmat);
Eigen::Vector4d eig = es.eigenvectors().col(3);  // largest (ascending)
```

替换 `powerIterationMaxEigenvec4x4` + `computeQWAForGroup`。保留 dual-seed 策略 + identity + mass check + canonicalisation 为测试对照 / 调试用，实际路径走 Eigen。M4.5 scope 追加一项（连同 QR/SVD）。

### M2.2.10 — 签名演化（getPoseWeights 本次 +5 参数）

```cpp
// M2.1b 之后
getPoseWeights(out, poses, norms, driver, poseModes, wMat,
               width, distType, encoding, isMatrixMode, kernelType);

// M2.2 之后 — 追加 QWA 参数
getPoseWeights(..., kernelType,
               const BRMatrix& poseVals,              // 样本 quat 来源
               const std::vector<int>& quatGroupStarts,
               const std::vector<bool>& isQuatMember,
               bool& qwaAnyClippedOut,                // PSD 截断 flag
               bool& qwaAnyDegenerateOut);            // 非收敛 flag
```

仅一个 caller（`compute()`），签名变更受控。M4.5 Eigen 引入时可能进一步重构，届时再议。

### M2.2.11 — Non-goals（明确推迟）

- ❌ path (a) 显式 delta 训练模式 → §CORNER-PATH-A 未来扩展（commutativity 保证无功能收益除非 per-sample q_base）
- ❌ per-sample $q_{\text{base}}$ → M3 或独立子任务
- ❌ Jacobi / Eigen → M4.5
- ❌ 输入端 quat group → 已由 M2.1b SwingTwist 覆盖
- ❌ UI Quat Group 面板 → M2.4
- ❌ QWA 调试可视化（特征值谱）→ M5
- ❌ `swingTwistWeight` 可调权重 → M3
- ❌ 分字段 pose 存储 → M2.5

---

## §M2.3 — Local-Transform 双存储 (per-pose)

v5 PART D.5 / 铁律 B10 落地。Apply 时刻在每个 pose 上**额外**快照 driven_node 的 local Transform（分解为 t/q/s），与 `poseValue` 标量并行存储。compute() **零消费**——这是为 M3 JSON Export + 引擎端 bone-pose 重建准备的纯数据通道。

### M2.3.1 — 决议日志

| # | 分叉 | 选项 | 选定理由 |
|---|---|---|---|
| (A) | 分解格式 | **① 10-dim t(3)+q(4)+s(3)** | quat 避免 gimbal + rotateOrder 二义性；与 M2.1b/M2.2 q_w≥0 规范统一 |
| (B) | Apply 时点 | **① 统一抓** | 与 M1.2 baseline 捕获并行；用户期望 "Apply 一键搞定" |
| (C) | blendShape fallback | **① identity，不加 valid flag** | schema 简洁；引擎端约定 "identity ⇒ no meaningful Transform" |
| (D) | Per-pose 策略 | **① Replay 每 pose** via connection sever | faithful 快照；存得起 Apply 一次的代价 |
| (E) | Replay 失败 | **① 跳过 + warning** | 对齐 M2.1/M2.2 fall-back 模式；DG 永不停 |
| (F) | Matrix mode 是否写 | **① 不写** | `driverList[d].pose[p].poseMatrix` 已是等价来源 |
| (G) | Schema 层级 | **① `poses[p].poseLocalTransform.{t,q,s}` compound 嵌套** | 与现存 `driverList[d].pose[p]` precedent 对齐 |

### M2.3.2 — Schema 草案（C++ 实施版）

```
poses[p] (existing compound, multi)
  ├── poseInput[]  (existing — driver scalars)
  ├── poseValue[]  (existing — driven scalars)
  └── poseLocalTransform (NEW, compound)        ← M2.3
        ├── poseLocalTranslate (double3, default 0,0,0)
        ├── poseLocalQuat      (double4, default 0,0,0,1)   ← q_w canonical
        └── poseLocalScale     (double3, default 1,1,1)
```

- 4 个新 MObject，全部 `setStorable(true) + setKeyable(false)`
- **零 `attributeAffects`**：pure data channel，compute() 不读
- v4 rig 升级：multi 稀疏存储 + 不写则不占空间，老 rig 0 字节膨胀

### M2.3.3 — **Non-driven-channel Freeze Contract**（强制契约）

M2.3 replay **只 setAttr 用户选择的 `driven_attrs`**，其余 transform 通道保持 Apply 调用时刻 driven_node 的场景状态。这意味着：

- 若用户在 Apply 时 driven_node 处于 rest pose，所有 pose 的 `poseLocalTransform` 共享该 rest 的 non-driven 通道值（理想情况）
- 若用户在 Apply 时 driven_node 有 stale 非零值（例如 `rx=30°`），那 30° 会被冻结进**所有** `poseLocalTransform.poseLocalQuat` 里
- 引擎端消费时应假定 non-driven 通道 = Apply 时刻快照，而非每 pose 独立

**用户实践建议**：**Apply 前手动重置 driven_node 到 rest pose**（典型工作流：把 driven_node 的所有 transform 通道清零或回到绑定状态，再点 Apply）。

**M3 UI Forward-pointer**：M3 阶段加 "Reset driven to rest before capture" 复选框自动化此步。M2.3 **不做** UI 侧处理，只埋契约。

### M2.3.4 — Single-Sever / Single-Restore 生命周期（强制实施细节）

`capture_per_pose_local_transforms` 实施约束：

```
def capture_per_pose_local_transforms(driven_node, driven_attrs, poses):
    # === 一次断 (循环之前) ===
    saved_conns = [...]    # 收集 incoming connections
    saved_values = [...]   # 收集原始 attr 值
    
    try:
        # === 循环内只 setAttr + 读 transform ===
        for pose in poses:
            for attr, v in zip(driven_attrs, pose.values):
                cmds.setAttr(driven_node + "." + attr, v)
            mat = get_local_matrix(driven_node)
            results.append(decompose_matrix_quat(mat))
    finally:
        # === 一次连回 (即使异常) ===
        for plug, orig in saved_values:
            cmds.setAttr(plug, orig)
        for src, dst in saved_conns:
            cmds.connectAttr(src, dst)
```

**禁止**循环内重复断连/重连（会产生 DG dirty 风暴 + 中间态污染下游）。test T9 守护此契约。

### M2.3.5 — Shear 处理契约（T7）

`MTransformationMatrix::scale()` 只返回 3 维 scale；shear 由独立 `shear()` getter 提取。M2.3 **不读 shear**——shear 部分被静默丢弃。

- **T7.a 纯 shear 输入**：分解 → t/q/s 接近 identity，**无 NaN，无 crash**
- **T7.b 混合 SRT + shear**：t/q/s 正确提取，shear 部分丢失。Quat 模长偏离单位 O(shear) 量级（Shepperd 公式假设输入正交矩阵；shear 破坏正交性）

**用户实践**：driven_node 有 shear 的 rig 应在 Apply 前烘焙 shear。M2.3 不处理 polar decomposition（M5 或专项）。

### M2.3.6 — rotateOrder 无关性（关键技术红利）

quat 分解通过 `MTransformationMatrix::rotation(asQuaternion=True)` 提取，**完全跳过 Euler 中间态**。意味着：

- 用户切 driven_node 的 `rotateOrder` 不影响 `poseLocalQuat` 数值
- M2.3 与 M2.1a 的 `driverInputRotateOrder[]`（输入端）**正交**——一个解 Euler→quat（输入），一个抓 matrix→quat（输出）
- 这是选 (A)① 10-dim 而非 (A)③ 9-dim Euler 的核心收益

### M2.3.7 — Compute() 零消费契约（架构红线）

`poseLocalTransform` 及其 3 个 children **永远**不出现在 `compute()` 路径里：

- 不在 `getPoseData` / `getPoseVectors` 读取
- 不在 `getPoseDelta` / `getPoseWeights` 读取
- 不在 `attributeAffects` 列表（无 DG dependency）
- 不在 M1.2 baseline / M1.3 clamp / M1.4 solver / M2.1 encoding / M2.2 QWA 任何地方读取

**唯一消费者**：M3 JSON Export 路径。本子任务**仅写入**。

### M2.3.8 — JSON Export 前瞻契约（M3 锁定）

`poseLocalTransform` compound 的 child 布局 = `{poseLocalTranslate(double3), poseLocalQuat(double4), poseLocalScale(double3)}`。翻译成 JSON 时保持 10 维定长，key 为 `t/q/s`：

```json
{
  "local_transform": {
    "t": [tx, ty, tz],
    "q": [qx, qy, qz, qw],
    "s": [sx, sy, sz]
  }
}
```

每 pose 一份，array 元素顺序与 `poses[p]` 索引对齐。blendShape driven → 全 pose 写 identity。M3 Export 按此约定读取，**不需二次协商**。

### M2.3.9 — DG 副作用 caveat

Replay 期间 driven_node 的属性被频繁 setAttr，下游连接的节点会短暂看到中间态。Interactive Maya 用户可能感知"画面轻微抖动 1 帧"。这是 Apply 动作固有代价，本子任务**不解决**——解决需要 `cmds.refresh(suspend=True)` + DG pause 包装，属 M3 UI 优化范畴。

### M2.3.10 — 零回归契约

- v4 rig 升级 + 未触发 Apply：`poses[p].poseLocalTransform` multi 稀疏不写入 → 0 字节膨胀
- 已触发 Apply：`apply_poses` 追加调用 `capture_per_pose_local_transforms` + `write_pose_local_transforms`，但 compute() 路径完全不读，行为字节级等价 M2.2
- M1+M2.1+M2.2 的 153 条测试在 M2.3 改动后全绿 ⇒ 零回归验证通过

### M2.3.11 — Non-goals

- ❌ JSON 导出实现 → **M3**
- ❌ "Capture Local Transform" 独立按钮 → M3
- ❌ "Reset driven to rest before capture" UI checkbox → M3
- ❌ Polar decomposition / 精确 shear 处理 → M5 或专项（addendum T7 caveat 已备案）
- ❌ Per-pose 非 driven 通道精确快照 → M4 专项（要求完整 driven_node state capture）
- ❌ `cmds.refresh(suspend=True)` DG pause 包装 → M3 UI 优化
- ❌ compute() 消费 `poseLocalTransform` → **永不**（架构红线）
- ❌ Matrix mode 写入 → 不实施（`driverList[d].pose[p].poseMatrix` 已等价）
- ❌ 引擎端 runtime 组件 → M5

### M2.3.12 — 签名演化 / 新增 API

```python
# core.py 新增（M2.3）
IDENTITY_LOCAL_TRANSFORM      # module-level dict 常量
decompose_matrix_quat(matrix) → dict           # 新（与 decompose_matrix Euler 版并列）
capture_per_pose_local_transforms(driven_node, driven_attrs, poses) → list[dict]
write_pose_local_transforms(node, local_transforms) → None
read_pose_local_transforms(node) → list[dict]  # 给 M3 Export 准备

# apply_poses 流程追加 step 4
#   3 baseline capture / write (M1.2)
#   4 local Transform capture / write (M2.3, NEW)
#   5 trigger evaluate
```

API 签名稳定。M3 JSON Export 直接消费 `read_pose_local_transforms` 输出。

---

## §M2.4a — UI Surface (Scalar / Enum / Bool 控件 + outputIsScale[])

Milestone 2 第一个 view-side-only 子任务。把 M1.3 / M1.4 / M2.1a / M2.1b 引入的 5 个标量/枚举属性 + M1.2 的 `outputIsScale[]` 在 RBF UI 暴露给用户。**0 行 C++ 改动**——schema 已冻结。

### M2.4a.1 — 决议日志

| # | 分叉 | 选项 | 选定理由 |
|---|---|---|---|
| (A) | M2.4 拆分 | **① M2.4a + M2.4b** | a 700 行 / b 500 行，分两次 commit 更可 review |
| (B) | `outputIsScale[]` 编辑位置 | **① 独立 OutputScaleEditor** | 不动 attribute_list（selection model 风险大）|
| (C) | Multi list editor UI | **① 轻量 QListWidget + setItemWidget** | M2.4b 落地；本次只埋占位 |
| (D) | quat group validation | **① Deferred via 节点 warning** | 复用 M2.2 `resolveQuaternionGroups` |
| (E) | Controller signal | **① 零新 signal** | 全走 `set_attribute(attr, value)` 通用通道 |
| (F) | 测试范式 | **① 结构 + 纯函数 mock** | 真实 QApplication 推迟 M1.5 |
| (G) | i18n 提交 | **① 与 widget 同 commit** | 避免半英文中间态 |
| (H) | RBFSection 嵌入 | **① Inline 5 widget** | 沿用现 `_add_float_to` 模板 |
| (I) | `set_node_multi_attr` 位置 | **① `core.py` 新函数** | 保持 controller 薄 |

### M2.4a.2 — `set_node_multi_attr` 事务性契约（强制实施细节）

```python
def set_node_multi_attr(node, attr, list_values, max_length=10000):
    # 1) Type guard: list/tuple only
    # 2) Length cap: > max_length → truncate + warning
    # 3) Wrap in undo_chunk
    # 4) Step A: removeMultiInstance for every existing index
    # 5) Step B: setAttr for index 0..len-1, in order
    # 6) On per-index failure: warning, continue (undo_chunk is rollback)
```

**禁止**部分恢复（"还原一半")。失败时由 `undo_chunk` 兜底，用户 Ctrl+Z 全量回滚。测试 T0a/b/c/d/e 五子覆盖：全量写入 / 中途失败 / 空 list / 长度截断 / 类型守护。

### M2.4a.3 — i18n 永久守护（test_i18n_no_hardcoded_strings.py）

新增**永久测试**扫描 `widgets/` 所有 `.py`：抓 `setText` / `addItem` / `setToolTip` / `setWindowTitle` / `setPlaceholderText` / `setStatusTip` / `setWhatsThis` 调用，flag 任何字面字符串（非 `tr()` 包装）。

- **白名单 `KNOWN_VIOLATIONS`**：维护 pre-existing 合法例外（如 `pose_table.py` 的 `'{:.3f}'` 格式 spec —— 不是用户翻译串）
- **新违规 0 容忍**：未来任何 widget 加硬编码字符串立即测试挂掉
- **效果**：M2.4 起所有可见字符串 100% 走 `tr()`；i18n 表是唯一真相源

### M2.4a.4 — PySide Mock 陷阱与降级（关键工程发现）

**陷阱**：`MagicMock` 实例作为 widget 基类时（`class Foo(QtWidgets.QWidget):`），Python 元类机制**返回 MagicMock 子类**，不是真实 class——子类的用户定义方法被 MagicMock 自动属性机制吞没，`getattr(Foo, "method")` 返回 MagicMock 不是真实函数引用。

**降级方案**（用户在批示中预授权）：`conftest.py` 使用**最小真实类 shim**而非纯 MagicMock：

- `_Stub` 基类：accepts any constructor, auto-creates MagicMock attrs on access
- `_StubSignal` 类：替换 `QtCore.Signal`，提供 `connect/disconnect/emit` 的 no-op
- 关键 widget 类（`QWidget`, `QFrame`, `QLabel`, ...）通过 `type(name, (_Stub,), {})` 动态创建为真实 class

**优先级**：尝试导入真实 `PySide6` → fallback `PySide2` → fallback shim。本地装了 PySide 的开发者跑真实 binding；CI / 纯 Python 跑 shim。

### M2.4a.5 — Widget 改动清单

| 文件 | 改动 | 行数 |
|---|---|---|
| `constants.py` | +`SOLVER_METHOD_LABELS` / `INPUT_ENCODING_LABELS` / `DRIVER_INPUT_ROTATE_ORDER_LABELS` | +20 |
| `core.py` | +`set_node_multi_attr`（事务性）| +95 |
| `controller.py` | `set_attribute` 扩展 list dispatch | +12 |
| `ui/i18n.py` | +15 EN + 15 CN 条目 | +35 |
| `ui/help_texts.py` | +5 EN + 5 CN 帮助文本段 | +90 |
| `ui/widgets/rbf_section.py` | +5 inline 控件 + 2 handler + load/retranslate 扩展 | +95 |
| `ui/widgets/output_scale_editor.py` | 新建 | +110 |
| `ui/widgets/pose_editor.py` | 嵌入 OutputScaleEditor + 新 signal | +20 |
| `tests/conftest.py` | 新建（Maya + PySide mock + 路径注入）| +180 |
| `tests/test_m2_4a_core.py` | T0a-e | +160 |
| `tests/test_m2_4a_widgets.py` | T1-T6 | +200 |
| `tests/test_i18n_no_hardcoded_strings.py` | 永久守护 | +90 |

### M2.4a.6 — Visibility 联动（M2.4b 占位）

`_on_input_encoding(idx)` 调用 `attributeChanged.emit("inputEncoding", idx)` + 检查 `hasattr(self, "_rotate_order_editor")`：

```python
if hasattr(self, "_rotate_order_editor"):
    self._rotate_order_editor.setVisible(idx != 0)
```

**M2.4a 阶段**：`_rotate_order_editor` **不存在**，`hasattr` 返回 False，分支不进。
**M2.4b 阶段**：实例化 `OrderedEnumListEditor` 赋给 `self._rotate_order_editor`，visibility 联动激活。

这是 forward-compat 钩子，**M2.4a 不破坏 M2.4b 的入口**。

### M2.4a.7 — 零回归契约

- v4 / v5-pre-M2.4a rig 加载：所有 M2.4a 控件显示 C++ schema 默认值（`regularization=1e-8` / `solverMethod=0` / `inputEncoding=0` / `clampEnabled=False` / `clampInflation=0.0` / `outputIsScale[]` 全 False）
- `RBFSection.load(data)` 使用 `data.get("attr", default)` 模式，老 rig 无该 key 时回退到 default
- 168 条 M1+M2.1+M2.2+M2.3 测试在 M2.4a 改动后全绿 ⇒ 零回归验证

### M2.4a.8 — Test 矩阵

T0a-e（core 事务性）+ T1-T6（widget 结构性）+ T_HC（永久 i18n 守护）= 20 子测试（含 1 skipped 当 widgets dir 不存在时的防御）。全量 188/188 通过。

### M2.4a.9 — Non-goals（推迟到 M2.4b）

- ❌ `OrderedIntListEditor` / `OrderedEnumListEditor` 实现 → **M2.4b**
- ❌ `outputQuaternionGroupStart[]` UI → M2.4b
- ❌ `driverInputRotateOrder[]` UI → M2.4b
- ❌ "Reset driven to rest" Apply 时复选框 → M3
- ❌ JSON Import/Export UI → M3
- ❌ Mirror / Pose Pruner / Live Edit Mode 等 M3 工具 → M3
- ❌ E2E QApplication 测试 → M1.5 / mayapy 集成
- ❌ stylesheet 主题大调整 → 永不

### M2.4a.10 — MVC 红线守护

- ✅ Widget 不 import `RBFtools.core`（grep 验证：`output_scale_editor.py` / `rbf_section.py` 中 0 命中 `from RBFtools import core`）
- ✅ Controller 仅 `set_attribute` 扩展，无新 signal
- ✅ C++ schema 0 改动（diff 验证：`source/` 0 修改）
- ✅ Stylesheet 不动（`style.py` 不在改动文件列表）
- ✅ 默认值显示与 C++ enum 同步（T1/T2 守护）

---

## §M2.4b — Multi List Editors (rotateOrder + Quaternion Group Starts)

Milestone 2 主体收官子任务。把 M2.1a 的 `driverInputRotateOrder[]` + M2.2 的 `outputQuaternionGroupStart[]` 这两个 multi 数组通过两个**有序列表编辑器** (`OrderedEnumListEditor` + `OrderedIntListEditor`) 暴露给用户。零 C++ 改动。

### M2.4b.1 — 决议日志

| # | 分叉 | 选项 | 选定理由 |
|---|---|---|---|
| (A) | 公共基类抽取 | **① `_OrderedListEditorBase`** | 两 editor 99% 共享逻辑；基类 ~150 行 + 子类 ~30 行 vs 独立两份 ~500 行 |
| (B) | Signal 转发链路 | **① 统一 `_on_any_row_changed` 全表扫** | 重排后 stale-row-index bug 消除；典型 ≤10 项扫描成本可忽略 |
| (C) | 重排 widget 同步 | **① 销毁重建** | 避免 `takeItem` 期间 widget parent 短暂悬空触发 PySide warning |
| (D) | `hasattr` 守护 | **① 保留** | 防御未来 `_build` 顺序变更，零代码收益删除 |
| (E) | Quat group editor visibility | **① 始终可见 + empty hint** | empty 时不占空间 (maxHeight=0) + gray italic 提示文字 |
| (F) | rotateOrder labels 大小写 | **① 沿用 lowercase** | 对齐 Maya 原生 + C++ enum；改 uppercase 会破坏与 `transform.rotateOrder` 直连语义 |

### M2.4b.2 — `set_values` 的零 emit 契约（强制实施细节）

```python
def set_values(self, values):
    """Programmatic rebuild — emits listChanged ZERO times."""
    self._suspend_emit = True
    try:
        self._list.clear()
        for v in values:
            self._add_row_internal(v)
    finally:
        self._suspend_emit = False
    # Critical: NO listChanged.emit at end. set_values is controller-
    # initiated; emitting back creates a feedback loop:
    #   controller.set_attribute(attr, list)
    #     → core writes node
    #     → controller._load_settings()
    #     → widget.load(data)
    #     → widget.set_values(...)
    #     → emit listChanged
    #     → connect → controller.set_attribute(attr, list)  [loop]

def _on_any_row_changed(self):
    if self._suspend_emit:
        return
    self.listChanged.emit(self.get_values())
```

**契约**：用户交互（add / remove / move / inline edit）才 emit `listChanged`；程序化 `set_values` 不 emit。沿用 M2.4a `OutputScaleEditor` 已建立的范式。**测试 T9 双层守护**：源码扫描断言 `set_values` 包含 `_suspend_emit = True` + `_suspend_emit = False` 但**不**直接 `emit`；`_on_any_row_changed` 必须 gate 在 `_suspend_emit`。

### M2.4b.3 — `setItemWidget` + `setSizeHint` 跨版本陷阱（明文记录）

`QListWidgetItem` 默认 `sizeHint = QSize(0, 0)`。`QListWidget.setItemWidget(item, widget)` **不会自动调整** item 行高，结果是行塌陷为 1 px（用户看到一条几乎隐形的线）。

PySide2 / PySide6 行为一致，是 Qt 的 documented behaviour 而非 bug。

**强制约定**：`_OrderedListEditorBase._add_row_internal` 与 `_rebuild_row` 在每次 `setItemWidget` 之后立即调用：

```python
item.setSizeHint(widget.sizeHint())
```

否则 M2.4b 上线后 `OrderedIntListEditor` (QSpinBox 行) 与 `OrderedEnumListEditor` (QComboBox 行) 都会塌陷。M2.4a `OutputScaleEditor` 用的是 QCheckBox，sizeHint 内置工作，未触发此问题——但 M2.4b 必触发。

### M2.4b.4 — Visibility 状态机

`_update_encoding_visibility(idx)` 抽出为独立 helper（不再嵌在 `_on_input_encoding` 内），让 `load(data)` 也能直接调用：

```python
def _update_encoding_visibility(self, idx):
    if hasattr(self, "_rotate_order_editor"):
        self._rotate_order_editor.setVisible(idx != 0)

def _on_input_encoding(self, idx):
    self.attributeChanged.emit("inputEncoding", idx)
    self._update_encoding_visibility(idx)

def load(self, data):
    ...
    ienc = data.get("inputEncoding", 0)
    self._cmb_ienc.setCurrentIndex(ienc)
    if hasattr(self, "_rotate_order_editor"):
        self._rotate_order_editor.set_values(
            data.get("driverInputRotateOrder", []))
    if hasattr(self, "_quat_group_editor"):
        self._quat_group_editor.set_values(
            data.get("outputQuaternionGroupStart", []))
    # Visibility sync AFTER set_values so v5 rig opening with
    # encoding=2 sees the populated editor visible immediately.
    self._update_encoding_visibility(ienc)
```

**Quat group editor 始终可见**——不联动任何 attr。empty list 时显示 `quat_group_empty_hint` 占位文字（gray italic），列表区域 `setMaximumHeight(0)` 收缩。

`hasattr(self, "_rotate_order_editor")` 守护**保留**：M2.4a 占位时是必要的；M2.4b 实例化后理论上守护永远 True，但删除它带来 0 收益且失去对未来 `_build` 顺序变更的防御。

### M2.4b.5 — Widget 改动清单

| 文件 | 改动 | 行数 |
|---|---|---|
| `ui/widgets/_ordered_list_editor_base.py` | 新建（基类 + 销毁重建 + suspend-emit guard）| **+250** |
| `ui/widgets/ordered_int_list_editor.py` | 新建 | **+45** |
| `ui/widgets/ordered_enum_list_editor.py` | 新建 | **+55** |
| `ui/widgets/rbf_section.py` | +`_update_encoding_visibility` 抽取 + 集成 2 editor + load 扩展 + retranslate | **+55** |
| `ui/i18n.py` | +13 EN + 13 CN | **+30** |
| `ui/help_texts.py` | +2 EN + 2 CN markdown 段 | **+45** |
| `tests/test_m2_4b_widgets.py` | T1-T9 | **+285** |

总 **~+770 行**（略高于 +685 估算 ~85 行，因基类的销毁重建 / suspend-emit / 按钮 row / hint 占位综合体积超出）。

### M2.4b.6 — Test 矩阵

T1（base API × 6）+ T2（int editor × 3）+ T3（enum editor × 3）+ T4（signal × 3）+ T5（visibility helper × 2）+ T6（load 同步 × 1）+ T7（i18n × 1）+ T8（rotateOrder enum × 2）+ T9（set_values 不 emit 双层守护 × 2）= **23 子测试**。

T9 通过**源码扫描**断言契约（不依赖 instantiation 与真实 Qt signal）：
- 检查 `set_values` 体内有 `_suspend_emit = True` / `False`
- 检查 `set_values` 体内**没有** `self.listChanged.emit`
- 检查 `_on_any_row_changed` 体内有 `if self._suspend_emit`

未来重构若意外破坏契约，T9 立即 fail。

### M2.4b.7 — 零回归

- v4 / v5-pre-M2.4b rig 加载：`inputEncoding=0 (Raw)` → `_rotate_order_editor.setVisible(False)` → 用户感知不到新 widget；`outputQuaternionGroupStart[]` empty → `_quat_group_editor` 显示 empty hint
- `load(data)` 用 `data.get("driverInputRotateOrder", [])` / `data.get("outputQuaternionGroupStart", [])` 默认空 list 不抛 KeyError
- 188 条 M1+M2.1+M2.2+M2.3+M2.4a 测试在 M2.4b 改动后全绿 ⇒ 零回归验证
- v4 rig 完全无 visual diff（rotateOrder editor 隐藏 + quat group editor empty hint 几乎不占视觉空间）

### M2.4b.8 — Non-goals（M3 / 未来）

- ❌ 多选 + 批量删除 → M3
- ❌ 拖拽重排（DnD）→ M3 UI polish
- ❌ Group 越界 / 重叠即时反馈（红色高亮）→ M3 validation UX；M2.4b 沿用 deferred validation 走节点 warning
- ❌ rotateOrder editor 与 driver attr count 自动同步 → M3
- ❌ Quat group editor 与 outputIsScale 编辑器交叉 hint → M3
- ❌ 键盘快捷键（Delete / Ctrl+Up/Down）→ **永不**（addendum §M2.4b 红线）

### M2.4b.9 — 红线确认

- ✅ 沿用 M2.4a 全部红线（0 C++、MVC 严守、不暴露 baseValue/poseLocalTransform、i18n 100% tr()）
- ✅ Editor 不直接 emit `attributeChanged`，仅 emit `listChanged(list)`，由 `RBFSection` 转发
- ✅ 键盘 Delete 键不绑定到列表删除（仅"−"按钮）
- ✅ `item.setSizeHint(widget.sizeHint())` 在每次 `setItemWidget` 之后调用（基类实现 + 销毁重建 + 重排路径全覆盖）
- ✅ M2.4a 占位 `hasattr(self, "_rotate_order_editor")` 守护**保留**
- ✅ Visibility 联动**只有 inputEncoding 影响 rotateOrder editor**；quat group editor 始终可见
- ✅ `set_values(...)` 不触发 `listChanged`（T9 源码扫描守护）

---

## **Milestone 2 主体收官 + M2.5 前瞻锁定**

### Milestone 2 deliverables（截至 M2.4b）

| 子任务 | Commit | 测试累计 | Addendum 章节 |
|---|---|---|---|
| M2.1a | `6368bb7` | 105 | §M2.1a |
| M2.1b | `89197b4` | 130 | §M2.1b |
| M2.2 | `39f8225` | 153 | §M2.2 |
| M2.3 | `9f3e11f` | 168 | §M2.3 |
| M2.4a | `f326447` | 188 | §M2.4a |
| **M2.4b** | (本次) | **211** | §M2.4b |

**Milestone 2 主体收官**：M2.1a + M2.1b + M2.2 + M2.3 + M2.4a + M2.4b 共同覆盖 v5 PART C.2.2 / D.4 / D.5 / F.M2.4 的全部用户可见目标——输入编码（5 档）+ 输出编码（QWA）+ local Transform 双存储 + UI 控件 + 多 attr 编辑器。

### M2.5 forward-compat 契约（**锁定**）

**M2.5 是优化补丁性质**：v5 PART C.2.7 的 `poseSwingQuat` / `poseTwistAngle` / `poseSwingWeight` / `poseTwistWeight` / `poseSigma` 分字段 pose 存储，作用是避免 Swing-Twist 编码（M2.1b）下每 compute 重复做 quaternion 分解。

**Forward-compat 契约**：

- **M2.4 系列 UI 完全不消费 pose 内部存储**——`poseInput[]` / `poseValue[]` / `poseLocalTransform` / 未来 M2.5 新字段都是 schema 内部，UI 通过 controller `set_attribute` 写入，不 introspect storage layout
- **M2.5 schema 变更不影响 M2.4 任何 widget 的行为或测试**——M2.4 的 211 条测试在 M2.5 完工后必须依然全绿
- **M2.5 与 M3（工作流工具）可并行**——M3 优先级高于 M2.5（M3 的 Mirror / Pose Pruner / JSON Export 是 TD 阻塞项；M2.5 是性能优化）
- **M2.5 可任意时刻插入**——不阻塞 M3 启动，roadmap 灵活度由此契约保障

### 后续 milestone 索引

- **M3** — 工作流工具（Mirror / Pose Pruner / JSON Import-Export / Live Edit Mode / Pose Profiler / 自动中性样本 / aliasAttr）
- **M4** — 附加 solver（Jiggle / Aim Constraint / solverType 分支）
- **M4.5** — Eigen + 完整四层 fallback chain（独立 milestone，scope 见 §M4.5）
- **M5** — 性能与引擎对接（BRMatrix 对称存储 + SIMD / solverStats / 每目标 sigma / UE5 runtime / 245 补助骨 benchmark）
- **M1.5** — mayapy headless C++ 集成测试（环境就位时一次性覆盖 M1.1-M2.3 的 C++ 路径）
- **M2.5** — pose 分字段缓存（forward-compat 契约见上）

---

## §M3.0 — Shared Infrastructure for Milestone 3 Workflow Tools

Milestone 3 共 7 个子任务（M3.1–M3.7）都是工作流工具，反复需要 confirm 对话框 + 进度反馈 + 节点选中辅助 + JSON I/O 工具。M3.0 是**预备子任务**，把这 4 项基础设施一次性抽出，避免每个 M3.x 重复造轮子。**0 行 C++ 改动**。

### M3.0.1 — 决议日志

| # | 分叉 | 选项 | 选定理由 |
|---|---|---|---|
| (A) | 预览区域 widget | **① QPlainTextEdit read-only monospace** | 3/3 caller 实际需求都是 multi-line 文本摘要；callers 序列化到 ASCII，避免 widget 复杂化 |
| (B) | Modal vs Non-modal | **① Modal (`exec_()`)** | confirm 语义本就是同步阻塞；Qt 惯例；API 简单 |
| (C) | `enumerate_rbf_nodes` 是否新增 | **① 不新增**，复用 [`core.list_all_nodes()`](modules/RBFtools/scripts/RBFtools/core.py:127) | 现有 v4 helper 完全等价，新增是冗余 |
| (D) | `core_json.py` 文件位置 | **① 新文件** | core.py 已 1860 行；I/O 序列化与 DG ops 正交；M3.3 还要扩展 ~200 行 |
| (E) | Confirm 容器 | **① QDialog 子类** | 需要 preview pane + Don't-ask-again checkbox，QMessageBox 不支持 |
| (F) | menuBar 实例化时机 | **① `_build_ui` 末尾** | 与 `StatusProgressController` 实例化对齐；统一在 build 结束后做 wiring |
| (G) | `reset_all_skip_confirms` 二次确认 | **① 不需要** | 选择菜单项即用户意图；二次确认是冗余 |

### M3.0.2 — Schema Version Immutability Contract（**永久不变量**）

`core_json.SCHEMA_VERSION` = `"rbftools.v5.m3"` 是**永久不变量**。

任何 schema 演化必须：

1. 引入**新**版本字符串（如 `"rbftools.v5.m3.1"` 或 `"rbftools.v6"`）—— 永远不能修改既有字符串而让字段语义在底下漂移
2. `read_json_with_schema_check` 扩展为**多版本 reader**，同时支持读旧版 + 写新版
3. 在本 addendum 新建 `§M3.x-extension-YYYYMMDD` 子节记录变更

**三层守护**：

- **Layer 1 — 源码注释**：`core_json.py` 模块 docstring + `SCHEMA_VERSION` 行尾注释
- **Layer 2 — addendum 契约**：本节
- **Layer 3 — 永久测试**：`tests/test_m3_0_infrastructure.py::T0_SchemaVersionImmutability::test_schema_version_unchanged_M3_0` —— 标注 `# PERMANENT GUARD — DO NOT REMOVE` 并 fail 时给出"读 §M3.0 contract"指引

任何一层丢失都会被 review 注意到。三层同时丢失即破坏契约——**这种情况禁止**。

### M3.0.3 — Don't-Ask-Again optionVar 命名规则（锁定）

```
RBFtools_skip_confirm_<action_id>
```

- `<action_id>`：snake_case 字符串，由 M3.x 子任务自定义（`prune_poses` / `mirror_node` / `import_solver` / ...）
- 作用域：**全局** optionVar（不 per-rig）—— 用户在某个项目勾掉 "Don't ask again" 跨项目都生效
- 复位入口：`Tools → Reset confirm dialogs` 菜单项一键清所有 `RBFtools_skip_confirm_*` —— 给后悔药
- 持久化函数：`core.should_show_confirm_dialog(action_id)` / `core.set_skip_confirm(action_id, skip)` / `core.reset_all_skip_confirms()` —— 与 `core.get_filter_state` / `core.set_filter_state` 共栖一个文件，所有 optionVar 持久化集中在 core.py

`action_id` 注册表（M3.x 完工时各自补充）：

| action_id | 子任务 | 触发场景 |
|---|---|---|
| (待 M3.1 注册) `prune_poses` | M3.1 | Pose Pruner 删除批量 poses 前 |
| (待 M3.2 注册) `mirror_node` | M3.2 | Mirror 创建镜像节点前 |
| (待 M3.3 注册) `import_solver_overwrite` | M3.3 | Import 覆盖现有节点前 |
| ... | ... | ... |

### M3.0.4 — M3.x 访问路径契约（加固 1）

`StatusProgressController` 与 `ConfirmDialog` 实例化在 `RBFToolsWindow`，但 M3.x 子任务工具通过两条路径访问：

**路径 A（推荐 + 默认）**：经 `MainController`

```python
# In M3.x sub-task widget code (or controller method):
ctrl = self.controller   # the MainController instance

# Confirm prompt:
proceed = ctrl.ask_confirm(
    title=tr("title_prune_poses"),
    summary=tr("summary_prune_poses"),
    preview_text=preview_str,
    action_id="prune_poses",
)
if not proceed:
    return

# Progress feedback:
prog = ctrl.progress()
if prog:
    prog.begin(tr("status_prune_starting"))
    # ... work loop ...
    prog.step(i, total, tr("status_prune_step"))
    prog.end(tr("status_prune_done"))
```

`MainController.ask_confirm` 内部 lazy-imports `ConfirmDialog`，把 parent widget 设为 `controller.parent()`（即主窗口）。M3.x 子任务**不直接 import `ConfirmDialog`**——MVC 边界由 controller 守护。

**路径 B（不推荐但允许）**：直接调用

```python
from RBFtools.ui.widgets.confirm_dialog import ConfirmDialog
proceed = ConfirmDialog.confirm(...)
```

**仅当**工具是"独立 utility 而非 sub-task widget"时才走路径 B（罕见），且必须在子任务 addendum 里**论证**走 B 的理由。

`StatusProgressController` 同理——M3.x 通过 `controller.progress()` 访问，不直接读 `main_window._progress_ctrl` 私有成员。

### M3.0.5 — 改动清单

| 文件 | 改动 |
|---|---|
| `core_json.py` | **新建**（115 行）—— SCHEMA_VERSION + atomic_write_json + read_json_with_schema_check + 三层守护源码注释 |
| `core.py` | +97 行 —— `select_rig_for_node` + `should_show_confirm_dialog` / `set_skip_confirm` / `reset_all_skip_confirms` + `CONFIRM_OPT_VAR_TEMPLATE` |
| `controller.py` | +40 行 —— `set_progress_controller` / `progress` / `ask_confirm` |
| `ui/main_window.py` | +85 行 —— `StatusProgressController` 类 + `_build_menu_bar` + `_on_reset_confirms` + wiring |
| `ui/widgets/confirm_dialog.py` | **新建**（120 行）—— ConfirmDialog QDialog 子类 + `@classmethod confirm` |
| `ui/i18n.py` | +20 行 —— 9 EN + 9 CN 条目 |
| `tests/conftest.py` | +2 行 —— mock `maya.utils` (M3.0 测试需) |
| `tests/test_m3_0_infrastructure.py` | **新建**（330 行）—— T0-T8（18 子测试） |

**总：~+810 行**（含测试 + 新文件）；纯代码（不计测试）~520 行。

### M3.0.6 — 测试矩阵

| T# | 名称 | 子测 |
|---|---|---|
| **T0** | `SCHEMA_VERSION` 永久守护 | 1（PERMANENT GUARD）|
| T1 | `should_show_confirm_dialog` 三状态 | 3 |
| T2 | optionVar 命名规则 + 模板格式 | 2 |
| T3 | `reset_all_skip_confirms` 仅清匹配前缀 | 1 |
| T4 | `atomic_write_json` 写入 + 替换 + 无残留 | 3 |
| T5 | `read_json_with_schema_check` 通过/失败/缺字段 | 3 |
| T6 | `select_rig_for_node` invalid role defensive | 1 |
| T7 | `StatusProgressController` begin/step/end | 3 |
| T8 | M3.0 i18n keys 双语完整 | 1 |

合计 **9 测试类，18 子测试**。

### M3.0.7 — 零回归

- 主窗口加 menuBar 不影响现有布局（menuBar 在标题栏下方独立）
- `MainController` 加 3 个 method 不破坏现有 signal 连接
- `core.py` 加 4 个函数不影响现有 callers
- 新文件 `core_json.py` 完全独立
- 全量回归：211 + 18 = **229 / 229** 通过

### M3.0.8 — Non-goals（M3.x 子任务自己做）

- ❌ 实际工具按钮 / 菜单项 entries（M3.1–M3.7 各自 add）
- ❌ 工具特定的 confirm 提示文本 / preview 序列化（caller 实现）
- ❌ JSON 实际 schema 字段定义（M3.3 实现 export/import）
- ❌ 工具栏图标 / 第三层 UI 入口（顶层报告已决议不做）

### M3.0.9 — 红线确认

- ✅ 沿用 M3 顶层全部红线（0 C++ / MVC / i18n / v4 兼容 / 无新依赖）
- ✅ `SCHEMA_VERSION` 三层守护（源码 + addendum + 测试 T0）
- ✅ optionVar 命名规则 `RBFtools_skip_confirm_<action_id>` 锁定
- ✅ M3.x 默认走 `controller.ask_confirm` / `controller.progress()`，路径 B 直接调用须在子任务 addendum 论证
- ✅ `ConfirmDialog` API 向后兼容契约：caller 升级新参数不能 break 既有调用点（classmethod 用 default kwargs 扩展）
- ✅ 单子任务 ≤ 800 行硬上限：M3.0 估 ~520 代码 + ~290 测试 = ~810 总，**生产代码 520 < 800 上限**

### M3.0.10 — M3.x 子任务复用模板（"如何使用 M3.0"）

```python
# Step 1: confirm prompt (when about to do something destructive)
preview = "\n".join(
    "Pose [{}]: {}".format(p.idx, reason)
    for p, reason in items_to_remove
)
if not self._ctrl.ask_confirm(
    title=tr("title_prune_poses"),
    summary=tr("summary_prune_poses").format(count=len(items_to_remove)),
    preview_text=preview,
    action_id="prune_poses",
):
    return

# Step 2: progress feedback during the work
prog = self._ctrl.progress()
if prog:
    prog.begin(tr("status_prune_starting"))
for i, (p, _r) in enumerate(items_to_remove):
    if prog:
        prog.step(i + 1, len(items_to_remove),
                  tr("status_prune_step").format(idx=p.idx))
    self._ctrl.delete_pose_at(p.idx)
if prog:
    prog.end(tr("status_prune_done"))

# Step 3: JSON I/O (M3.3 export example)
from RBFtools import core_json
core_json.atomic_write_json(path, {
    "schema_version": core_json.SCHEMA_VERSION,
    "node": node_name,
    ...
})
data = core_json.read_json_with_schema_check(path)   # raises on mismatch

# Step 4: rig role selection (utility; one click "show me the driver")
core.select_rig_for_node(self._ctrl.current_node(), "driver")
```

每 M3.x 子任务在自己的 addendum 中：
1. 注册 `action_id` 到 §M3.0.3 的"action_id 注册表"
2. 在子任务 addendum 列出"使用了哪些 M3.0 helper"以便 review 追溯

---

## §M3.0 — Appendix: Reverse-then-Reapply Pattern (M3.7 commit retrospective)

When two sub-tasks land mixed in the working tree (the M3.2 + M3.7 handoff incident, executor commit `c7e07f2`), `git add -p` is **not** available in non-interactive automation. The deterministic alternative:

1. Save the M3.x-only **new** files (the ones that don't exist in HEAD) into a holdout directory (`.m3_x_holdout/`) so unittest discovery cannot find them.
2. Use `Edit` (or a small Python script for large blocks) to **reverse-apply** every M3.x change inside shared files —— restore them to the M3.{x-1}-only state.
3. Verify the M3.{x-1} test count passes on the reversed worktree.
4. Stage the M3.{x-1} files + commit + push.
5. Restore the holdout files to their original locations.
6. Use `Edit` to **re-apply** the M3.x changes to shared files (often this is just running each Edit operation again — your operations log doubles as a forward patch).
7. Verify the M3.x test count passes.
8. Stage + commit + push M3.x.

This is **deterministic** (no interactive hunk picking), idempotent (rerunning step 2 always lands at the same M3.{x-1} state), and leaves clean per-sub-task commit boundaries on the published history. It is the canonical M3.x reuse-pattern fall-back when working-tree commingling happens at handoff.

---

## §M3.0-spillover — `add_tools_action` / `add_pose_row_action` (added in M3.2 commit)

**追溯**：M3.0 落地后，**M3.2 实施时**发现 `_build_menu_bar` 与 `_show_row_menu` 缺少**子任务扩展接口**——M3.x 各自直接修改 `main_window.py` 会破坏 MVC（sub-task 不应改 window 内部）。

**决议**：M3.2 commit 内顺手加两个 helper 作为 **M3.0-spillover**。本节归 §M3.0 章节群（不归 §M3.2），便于未来检索"M3.0 共享基础设施"时一次性看到完整 API。

### API

```python
# RBFToolsWindow
def add_tools_action(self, label_key, callback) -> QAction:
    """Register an action on the Tools menu. Returns the QAction
    so callers can hold a reference for enable/disable state."""

# _PoseEditorPanel
def add_pose_row_action(self, label_key, callback, danger=False):
    """Register a per-pose right-click action. callback receives
    (row_idx). danger=True applies the red 'danger' stylesheet."""
```

### 契约（M3 全程红线）

1. 后续 M3.x 子任务的菜单/右键扩展**必须**走这两个 helper——禁止再直接修改 `main_window.py` menu 结构
2. 测试守护：spillover 助手测试归 `tests/test_m3_0_spillover.py`（独立文件名标识，便于 review）
3. `_show_row_menu` 内 `_extra_row_actions` 迭代**不可绕过**——`test_m3_0_spillover.py:T_RowMenuExtensionContract` 永久守护

### M3.2 是首个真实消费者

`RBFToolsWindow._build_ui` 末尾：
```python
self.add_tools_action("menu_mirror_node", self._on_mirror_node)
self._pose_editor.add_pose_row_action(
    "row_mirror_this", self._on_mirror_pose, danger=False)
```

未来 M3.1 / M3.3 / M3.5 / M3.6 等需要菜单/右键 entry 时，本节是它们的"使用手册"。

---

## §M3.2 — Mirror Tool

Milestone 3 第一个真正的工作流工具——也是 M3.0 path A reuse pattern 的首次真实压力测试。**0 行 C++**。

### M3.2.1 — 决议日志

| # | 分叉 | 选项 | 选定理由 |
|---|---|---|---|
| (A) | Mirror 对象层级 | **① 整节点 + 单 pose 同 commit** | 共用核心镜像数学；最常见用例 |
| (B) | 命名规则集 | **① 6 预设 + Custom** | 覆盖业界 6 套约定；Custom 兜底 |
| (C) | Mirror Axis 持久化 | **① 不持久化** | 防上次错配置污染本次 |
| (D) | Driver/Driven 缺失 | **① 命名查找 + dialog 兜底** | 用户责任 + 工具温和 |
| (E) | inputEncoding 支持 | **① Raw + Quat + ExpMap + SwingTwist + BendRoll fall-back** | 95% 覆盖 |
| (F) | `poseLocalTransform` 镜像 | **① 镜像** | 保持 M2.3 双存储一致性 |
| (G) | M3.0-spillover 在 M3.2 commit 内 | **① 是** | 避免污染 M3.0 commit |
| (H) | 单 pose 右键不走 confirm | **① 不走** | 单 pose 低风险；M3.2 暂为 stub |

### M3.2.2 — 数学

镜像轴：
- AXIS_X (0) — YZ 平面，flip x
- AXIS_Y (1) — XZ 平面，flip y
- AXIS_Z (2) — XY 平面，flip z

**Translate**: $t' = (\sigma_x t_x, \sigma_y t_y, \sigma_z t_z)$，$\sigma_i = -1$ 仅当 $i =$ 镜像轴。

**Quaternion**: $q' = (\sigma_x x, \sigma_y y, \sigma_z z, w)$，$\sigma_i = -1$ 仅当 $i \ne$ 镜像轴。

**ExpMap**：与 quat xyz 同号规则。

**SwingTwist**：swing 部分按 quat；twist 标量取负。

**Raw attr 行为镜像**（Maya 约定）：

| 镜像轴 | flip set |
|---|---|
| X | {tx, ry, rz} |
| Y | {ty, rx, rz} |
| Z | {tz, rx, ry} |

scale 永不 flip。未识别 attr 名 → keep + warning。

### M3.2.3 — 命名规则边界（Naming-rule edge contract）

3 case 显式反馈：

| 情形 | UI 反馈 |
|---|---|
| 同时匹配 forward 和 reverse | 默认 forward + warning |
| 都不匹配 | 禁用 Mirror 按钮 + 红色提示 |
| 匹配但替换后名字未变 | warning + 禁用 Mirror 按钮 |

T_NAMING_EDGE 3 子测试守护。

### M3.2.4 — 失败回滚契约（T_ROLLBACK）

`mirror_node` 整体 `undo_chunk("RBFtools: mirror node")` 包裹。任何子步骤失败 → 异常向上传播 + `undo_chunk` finally 触发 `closeChunk` → Maya undo stack 收到完整 chunk。

T_ROLLBACK 行为验证：mock `apply_poses` 注入异常 → 验证异常未被吞 + `cmds.undoInfo(openChunk=True)` / `closeChunk=True` 各 ≥ 1 次。

### M3.2.5 — Path A 首次真实消费验证

`controller.mirror_current_node(config)`：
- `ask_confirm(title, summary, preview_text, action_id)` —— preview 为 13 行 ASCII 摘要，QPlainTextEdit 显示完整
- `progress()` begin/step/end —— 4 阶段足够灵活
- **零 M3.0 API 修改需求**——path A 设计经受住第一次真实压力

### M3.2.6 — `action_id` 注册（addendum §M3.0.3 注册表更新）

| action_id | Sub-task | Confirm 触发场景 |
|---|---|---|
| `mirror_create` | M3.2 | Mirror 创建新目标节点前 |
| `mirror_overwrite` | M3.2 | Mirror 目标已存在时覆盖前 |

### M3.2.7 — 改动清单

| 文件 | 改动 |
|---|---|
| `core_mirror.py` | **新建** ~280 行 |
| `core.py` | +160 行 (`mirror_node` + `_copy_node_settings`) |
| `controller.py` | +90 行 (`mirror_current_node` path A 首次消费) |
| `ui/main_window.py` | +60 行（M3.0-spillover + Mirror callbacks）|
| `ui/widgets/mirror_dialog.py` | **新建** ~200 行 |
| `ui/i18n.py` | +60 行（28 EN + 28 CN）|
| `tests/conftest.py` | +4 类（QMainWindow / QFormLayout / QPlainTextEdit / QRadioButton）|
| `tests/test_m3_2_mirror.py` | **新建** ~480 行（28 子测试）|
| `tests/test_m3_0_spillover.py` | **新建** ~60 行（3 子测试）|

**总：~+1620 行**；生产代码 ~790 行 < 800 上限。

### M3.2.8 — 零回归

260/260 测试通过（229 累计 + 31 新）；新增菜单项不主动调用就不影响任何 rig；新 `_extra_row_actions` 默认空，右键行为字节级一致。

### M3.2.9 — Non-goals

- ❌ R→L 批量反向 / 选中 R 拉 L → M3 后续
- ❌ Mirror 后自动 Apply → 用户手动
- ❌ BendRoll 编码 driver inputs 真镜像 → M3 后续或永不
- ❌ 跨场景 mirror → M3.3
- ❌ 单 pose 右键真正实现 → 暂 stub warning，待 M3.2 后续 patch

### M3.2.10 — 红线确认

- ✅ 沿用 M3 + M3.0 全部红线
- ✅ Mirror 必须 `undo_chunk` 包裹（T_ROLLBACK 守护）
- ✅ 不修改源节点
- ✅ BendRoll fall-back 一次性 warning
- ✅ 菜单/右键扩展走 spillover helpers
- ✅ 命名规则 3 边界 case 显式反馈

---

## §M3.7 — aliasAttr Auto-Naming

Milestone 3 第三个工作流工具——M3.3 JSON Import/Export 的关键路径前置。**0 行 C++**。把 `<shape>.input[i]` / `<shape>.output[k]` 多实例 plug 自动起人可读 alias，让 channel-box / scriptEditor / 引擎侧 JSON export 都能用 `out_shoulderBlend` 替代 `output[5]`。

### M3.7.1 — 决议日志

| # | 分叉 | 选项 | 选定理由 |
|---|---|---|---|
| (A) | Maya `cmds.aliasAttr` API 信任 | **A.3** 文档 + mock 测试覆盖 | 与 M3.0/M3.2 风格一致；T6 双路径覆盖 PASS + FAIL 行为 |
| (B) | 触发时机 | **B.4** `apply_poses` 末尾自动 + Tools 菜单兜底 | 与 M1.2 baseline / M2.3 localXform 自动捕获一致；用户零认知负担 + 修复入口 |
| (C.1) | Alias 适用范围 | **C.1.b** output + input | 完整对称；pose 内部数组**不**起 alias（C.1.c 过度） |
| (C.2) | 命名模板 | **C.2.β** `out_<x>` / `in_<x>` 前缀 + quat group `<base>QX/QY/QZ/QW` | 防止与 shape 自身 attr 冲突；quat group 沿用社区惯例 |
| (C.3) | 冲突处理 | **a + b + c 全采纳** | 互不冲突；E.1 保留 + `_<idx>` 后缀兜底 + 同 shape 名字碰撞同退化 |
| (D) | Schema 关系 | **D.1 + D.3** SCHEMA_VERSION 不变 | alias 是 Maya 元数据，不属于 RBFtools shape schema；M3.3 JSON 字段扩展不需要 bump version |
| (E) | 既有 alias | **E.1 + E.3** 保留 + 显式覆盖入口 | E.1 默认保护；E.3 force 入口走 confirm（破坏性） |

### M3.7.2 — Driven/Driver Node Write-Boundary Contract（**M3.x 第一次写非 RBFtools-shape 节点的边界**）

```
M3.7 Driven Node Write Boundary Contract:
  - M3.7 alias generation invokes cmds.aliasAttr on the RBFtools SHAPE,
    not on the driver/driven scene nodes themselves
    (input[i] / output[k] are plugs on the shape; the shape is owned
    end-to-end by RBFtools, so alias writes there are fully internal)
  - Distinct from M3.2 mirror's "never modify source node" contract:
    M3.2 was 100% read-only on the source; M3.7 writes aliases that
    *describe* the rig wiring even though wiring itself is unchanged
  - Scope strictly limited to:
    * <shape>.input[i] for i in range(len(driver_attrs))
    * <shape>.output[k] for k in range(len(driven_attrs))
    * Alias names follow C.2.β template (out_<x> / in_<x> /
      <base>QX/QY/QZ/QW)
  - Out of scope (NEVER touched):
    * Non-listed attributes on driver/driven (M2.3 freeze contract analog)
    * Any attribute on third-party scene nodes
    * Any non-RBFtools-managed alias on the shape (E.1 protection,
      enforced by core_alias.is_rbftools_managed_alias)
```

未来 M3.5 / M3.6 / 其他 milestone 如有"修改非 RBFtools-shape 节点"需求都参照本契约模板写入边界范围。

### M3.7.3 — Multi-Instance Plug Alias 行为（**caveat**）

`cmds.aliasAttr` 对 multi-instance plug（`<shape>.output[5]`）的支持**未在真实 Maya 端验证**——执行者无 mayapy 环境。

**采用 PASS 假设实施**，T6 测试覆盖 PASS / FAIL 双路径：

- **PASS 路径**（默认行为）：`apply_aliases` 成功写入 alias，`read_aliases` 反查可还原 `{idx → alias}` 映射
- **FAIL 路径**（fallback）：`cmds.aliasAttr` 抛 `RuntimeError` → `_set_one_alias` 捕获 + `cmds.warning` + 跳过；apply_poses 调用方收到空 dict 但 Apply 主流程**不**中断

**回归触发**：M1.5 mayapy headless 集成测试就位时，对 multi-instance plug alias 行为做一次实测：

- 若**实测 PASS** → 当前实现就是终态
- 若**实测 FAIL** → core_alias 退化方案：
  - `apply_aliases` 改为**仅返回名字映射**，不调 `cmds.aliasAttr`
  - 名字映射作为 in-memory metadata，由 M3.3 export 直接消费写入 JSON
  - **D.1 仍成立**：依然不动 SCHEMA_VERSION，不新增节点 attr

**警告**：T6 FAIL 路径走完后 `result == {"input": {}, "output": {}}`——M3.3 import 时**不能**假设 alias dict 非空，必须有 index-only fallback。

### M3.7.4 — `is_rbftools_managed_alias` 精确性契约（**永久守护**）

清理范围必须严格区分 "RBFtools 自动生成" vs "用户手动设置"。检测规则（来自 `core_alias.py`）：

| 规则 | 判定 | 例 |
|---|---|---|
| 1 | `name` 以 `"in_"` 开头且后有非空 base | `in_rotateX` ✅ managed |
| 2 | `name` 以 `"out_"` 开头且后有非空 base | `out_blendValue` ✅ managed |
| 3 | `name` 末尾匹配 `QX/QY/QZ/QW` 且 base 非空 | `aimQuatQX` ✅ managed |
| 否则 | 非 managed | `myCustomName` ❌ user-set |

**已知边界**：用户手动起的 alias **凑巧**末尾是 `QX/QY/QZ/QW`（如手工命名 `someThingQX`）会被误判 managed。这是文档化 trade-off：

- RBFtools 拥有 `<base>QX/QY/QZ/QW` 四元命名约定的所有权
- 用户冲撞此约定的命名属于知情后果
- Tools → Force Regenerate Aliases（confirm 守门）是兜底逃生口

**T_MANAGED_ALIAS_DETECT 永久守护**（`test_m3_7_alias.py::T4_ManagedAliasDetect`）—— 6 子测试覆盖 in_ / out_ / quat sibling / user / 边界（裸 `in_` 不算）/ empty。

### M3.7.5 — Path A 第二次真实压力测试

`controller.regenerate_aliases_for_current_node()` —— **不走** confirm（非破坏性，只是 progress 反馈）：

```python
prog = self.progress()
if prog is not None:
    prog.begin(tr("status_alias_starting"))
core.auto_alias_outputs(...)
prog.end(tr("status_alias_done"))
```

`controller.force_regenerate_aliases_for_current_node()` —— **必走** confirm（破坏性）：

```python
proceed = self.ask_confirm(
    title=tr("title_force_alias"),
    summary=tr("summary_force_alias"),
    preview_text=preview,                       # user-set + managed 列表
    action_id="force_regenerate_aliases",
)
if not proceed:
    return None
```

零 M3.0 API 修改需求 —— path A 经受住第二次真实压力。

### M3.7.6 — `action_id` 注册表更新（addendum §M3.0.3）

| action_id | Sub-task | Confirm 触发场景 |
|---|---|---|
| `force_regenerate_aliases` | M3.7 | Force Regenerate Aliases（覆盖既有 user alias） |
| ~~`regenerate_aliases`~~ | M3.7 | **不**走 confirm（非破坏性，仅 progress 反馈，无注册）|

### M3.7.7 — 改动清单

| 文件 | 改动 |
|---|---|
| `core_alias.py` | **新建** ~270 行（sanitize + 命名生成 + managed 检测 + apply/read/clear helpers + write-boundary 契约 docstring + M3.3 forward-compat docstring）|
| `core.py` | +60 行（`auto_alias_outputs` orchestrator + `apply_poses` 末尾 try/warning 调用）|
| `controller.py` | +110 行（`regenerate_aliases_for_current_node` + `force_regenerate_aliases_for_current_node`）|
| `ui/main_window.py` | +18 行（2 个 `add_tools_action` 调用 + 2 个 callback stub）|
| `ui/i18n.py` | +14 行（7 EN + 7 CN）|
| `tests/test_m3_7_alias.py` | **新建** ~340 行（13 测试类，31 子测试）|
| `docs/.../addendum_20260424.md` | §M3.7 ~140 行 |
| `docs/.../milestone_3_summary.md` | §1 进度矩阵 + §3.1 注册表更新 |

**总：~960 行**；生产代码 ~470 行 < 800 上限（预测 ~270，实际超过是因为 controller force_regenerate 的 preview 文本生成 + 详细 docstring；不影响子任务性质）。

### M3.7.8 — 测试矩阵

| T# | 名称 | 子测 |
|---|---|---|
| T1 | `_sanitize` 五条 | 5 |
| T2 | `generate_alias_name` 五形态 | 5 |
| T3 | `quat_group_alias_names` 四 sibling + sanitised base | 2 |
| T4 / T_MANAGED_ALIAS_DETECT | `is_rbftools_managed_alias` 永久守护 | 6 |
| T5 | `clear_managed_aliases` 保留 user alias（E.1） | 1 |
| T6 | `apply_aliases` PASS + FAIL multi-plug 双路径 | 2 |
| T7 | `read_aliases` 反查（含 foreign alias 忽略） | 1 |
| T8 | 冲突 `_<idx>` 后缀兜底 | 1 |
| T9 | `apply_poses` 调用 `auto_alias_outputs`（source-text）| 2 |
| T10 | controller path A 方法存在 + action_id 字面量 | 3 |
| T11 | i18n 7 keys EN/CN parity | 1 |
| T12 | SCHEMA_VERSION 仍为 `"rbftools.v5.m3"` | 1 |
| T13 | Tools 菜单走 `add_tools_action` spillover | 1 |

合计 **13 测试类，31 子测试**。

### M3.7.9 — 零回归

- `apply_poses` 第 5 步是 try/except 包裹的纯增量 —— alias 失败仅 warning，evaluate 步骤照常触发
- 新菜单项空闲时不触发任何 cmds.aliasAttr 调用
- 现有 `cmds.aliasAttr` 在源码中**之前从未被引用** —— 引入是首次（grep 验证）
- 全量回归：260 + 31 = **291 / 291** 通过

### M3.7.10 — Non-goals（M3.x 后续）

- ❌ Per-pose 内部数组（`poses[p].poseInput[i]`）alias —— 过度污染 channel box（C.1.c 决议拒绝）
- ❌ Bidirectional sync："用户改了 alias → 反向更新 driver/driven attr 名" —— alias 永远是 RBFtools-side 别名，不传播
- ❌ Per-rig optionVar 关闭自动 alias —— 当前 force-only 入口已足够；如有需求 M3.x 后续 patch
- ❌ 自动 alias 名国际化 —— alias 是引擎侧消费的 ASCII identifier，不应翻译（i18n 仅菜单文本）

### M3.7.11 — 红线确认

- ✅ 沿用 M3.0/M3.2 全部红线（0 C++ / MVC / i18n / undo_chunk / float_eq / no kFailure / spillover helpers / path A）
- ✅ **SCHEMA_VERSION 不变** = `"rbftools.v5.m3"`（D.1 决议；T12 守护）
- ✅ **保留用户手动 alias**（E.1 默认；E.3 force 入口走 confirm）
- ✅ **`is_rbftools_managed_alias` 精确**（T_MANAGED_ALIAS_DETECT 永久守护）
- ✅ 写权限边界严格限制到 `<shape>.input[i]` / `<shape>.output[k]`（M3.7.2 契约）
- ✅ Multi-instance plug alias caveat 文档化（M3.7.3，M1.5 mayapy 回归触发）
- ✅ Tools 菜单经 `add_tools_action` spillover helper（T13 守护）

### M3.7.12 — M3.3 Forward-Compat Contract

M3.3 JSON Import/Export 将直接消费 M3.7 的以下 API。签名稳定承诺 —— M3.3 实施时**调用即可**，M3.7 不再变更：

```python
# 1. Pure name generation (no Maya cmds touched).
core_alias.generate_alias_name(attr_name, idx, role,
                               is_quat_group_leader=False) -> str
core_alias.quat_group_alias_names(leader_attr_name) -> tuple[str x 4]

# 2. Reverse lookup (Maya cmds — read-only).
core_alias.read_aliases(shape) -> {"input": {idx: alias},
                                    "output": {idx: alias}}

# 3. Managed-alias classifier (pure).
core_alias.is_rbftools_managed_alias(name) -> bool

# 4. Public constants.
core_alias.MANAGED_PREFIX_INPUT  = "in_"
core_alias.MANAGED_PREFIX_OUTPUT = "out_"
core_alias.QUAT_SUFFIXES = ("QX", "QY", "QZ", "QW")
```

M3.3 export schema 推荐字段（**不**改 SCHEMA_VERSION）：

```json
{
  "schema_version": "rbftools.v5.m3",
  "outputs": [
    {"index": 5, "alias": "out_shoulderBlend",
     "drivenAttr": "shoulderBlend"}
  ],
  "inputs": [
    {"index": 0, "alias": "in_rotateX", "driverAttr": "rotateX"}
  ]
}
```

M3.3 import 优先 alias → fallback index。alias 在 PASS 路径下持久（Maya 保存到 `.ma`/`.mb`），FAIL 路径下也由 export-time `read_aliases` 反查兜底（FAIL 路径需 M3.3 前补完整退化）。

---

## §M3.0-spillover §2 — `add_file_action` (added in M3.3 commit)

**追溯**：M3.3 实施时发现 `_build_menu_bar` 创建的 `_menu_file` 自 M3.0 起一直为空 —— M3.0-spillover §1 仅给 Tools 菜单提供 `add_tools_action`，File 菜单缺对应扩展接口。M3.3 是首个 File 菜单消费者，**顺手**补 §2，归 §M3.0-spillover 章节群继续追加。

### API

```python
# RBFToolsWindow
def add_file_action(self, label_key, callback) -> QAction:
    """Mirror of add_tools_action for the File menu. Returns the
    QAction so callers can hold a reference for enable/disable
    state."""
```

### 契约（M3 全程红线）

1. 后续 M3.x 子任务的 File 菜单扩展**必须**走此 helper —— 禁止再直接修改 `_build_menu_bar` 的 File 段
2. 测试守护：`tests/test_m3_3_jsonio.py::T_AddFileActionExists` + `T_FileMenuExtensionContract`（source-text scan `_menu_file` 的存在 + addAction 调用）
3. M3.3 是首个真实消费者（3 个 File entries：Import / Export Selected / Export All）

### M3.3 是首个真实消费者

`RBFToolsWindow._build_ui` 末尾：
```python
self.add_file_action("menu_import_rbf", self._on_import_rbf)
self.add_file_action("menu_export_selected", self._on_export_selected)
self.add_file_action("menu_export_all", self._on_export_all)
```

未来如有其他 File 菜单需求（如 "Recent Files" 列表），本节是它们的"使用手册"。

---

## §M3.3 — JSON Import / Export

Milestone 3 体量最大子任务 —— 全双向 JSON IO。**关键路径下游**：消费 M3.7 的 alias 系统 + M2.3 的 poseLocalTransform 双存储 + M3.0 的 core_json 基础设施。**0 行 C++**。

### M3.3.1 — 决议日志 + bijection 映射表

12 项决议（设计文档 PART E.2 + 现状核查会话）：

| # | 分叉 | 选项 | 选定理由 |
|---|---|---|---|
| (A) | 顶层结构 | **A.1** `nodes:[]` 数组顶层 | Single = length 1，统一处理 |
| (B) | settings 粒度 | **B.1** 全量 export | schema 自描述 |
| (C) | 节点不存在 | **C.1** abort + 详细错误 | rig 拓扑由用户预备 |
| (D) | Import 模式 | **D.2** Add + Replace（confirm-gated）| Update 推后续 |
| (E) | 单/两阶段 | **E.2** 两阶段 dry-run + execute | path A 天然消费 |
| (F) | validation 严格度 | **F.3** 严格 + 全量错误 | TD 一次改完 |
| (G) | poseLocalTransform | **G.2** 直写绕过 capture | M2.3 freeze contract 唯一合法绕道 |
| (H) | alias 字段 import | **H.2** 不直写让 M3.7 兜底 | 一处事实来源 |
| (I) | `alias_base` 字段 | **I.2** 反推不存 | 一处事实来源 |
| (J) | meta 块 | **J.2** 可选只读 metadata | 不参与 import 决策 |
| (K) | controller 拆分 | **K.3** core_json 主体 + controller wire | 重逻辑下沉 |
| (L) | 800 行超限 | **L.1 默认尝试单 commit** | 实测 ~620 production lines，远低于阈值 |

**`_ATTR_NAME_TO_JSON_KEY` bijection 契约**（**永久**）：

```python
_ATTR_NAME_TO_JSON_KEY: dict[str, str]   # Maya camelCase -> JSON snake_case
_JSON_KEY_TO_ATTR_NAME = {v: k for k, v in _ATTR_NAME_TO_JSON_KEY.items()}
EXPECTED_SETTINGS_KEYS = frozenset(_ATTR_NAME_TO_JSON_KEY.values())
```

T1a 完整性 + T1b **PERMANENT** 双射性：任何 Maya attr 改名导致 JSON key 重复 → 测试 fail。改 schema 必须 bump SCHEMA_VERSION。

### M3.3.2 — JSON Schema 草案（**永久公共契约**）

详见 `docs/设计文档/RBFtools_v5_设计方案.md` PART E.2 与本 addendum §M3.3.2 联合定义。锁定字段集（T_M3_3_SCHEMA_FIELDS 永久守护）：

```
EXPECTED_NODE_DICT_KEYS = frozenset({
    "name", "type_mode", "settings",
    "driver", "driven", "output_quaternion_groups", "poses",
})

EXPECTED_SETTINGS_KEYS = frozenset(<37 scalar keys>)
```

#### 字段类型 + Maya enum 整数化

所有 enum 字段在 wire-level **用整数**（kernel / radius_type / rbf_mode / distance_type / twist_axis / interpolation / direction / solver_method / input_encoding 等）。可选 `<key>_label` 后缀字段是只读 metadata —— `dict_to_node` 跳过 `_label`-后缀键不写入节点（红线 #4）。

#### sparse multi 索引契约

driver/driven attrs 数组每项**必须**包含显式 `index`（int）字段。`_validate_attr_array` 检查 `index` 唯一性 + 与 array 顺序无关——sparse 多实例（如 `output[0,2,5]`）通过此机制保留 sparseness。

#### Float round-trip 字节稳定性

`atomic_write_json` 使用 `json.dump(..., ensure_ascii=False, indent=2, sort_keys=False)` —— 不改变 Python 默认 float repr。任何"舍入到 6 位小数"等美化操作**禁止**（T_FLOAT_ROUND_TRIP 守护：`dump(load(dump(d))) == dump(d)` 字节级）。

### M3.3.3 — Two-phase Import 流程（path A 第三次真实消费）

```
[Phase 1 — read_json_with_schema_check]
     ↓ raises SchemaVersionError on mismatch
[Phase 2 — dry_run] (read-only)
     ↓ collects all errors per node
     ↓ returns list[PerNodeReport]
[ConfirmDialog (path A) — 仅当 mode='replace' 且至少一个节点 will_overwrite=True]
     action_id="import_replace"
     preview_text = MainController._format_dry_run_report(reports)
     ↓
[Phase 3 — import_path] (write)
     ↓ per ok report:
     ↓   dict_to_node(rpt.data, mode, will_overwrite)
     ↓     - mode='replace' + collide → core.delete_node(name) → create_node()
     ↓     - mode='add' + collide → create + rename to name+'_imported'
     ↓     - 全量 setAttr / wire / write_output_baselines /
     ↓       write_pose_local_transforms (G.2 直写)
     ↓     - core.auto_alias_outputs(...)  # H.2 M3.7 兜底
     ↓ 失败节点不阻塞其他节点 → 收集到 result["failed"]
[refresh_nodes()]
```

非破坏性 Add 模式：**不**走 confirm（仅 progress 反馈）。

### M3.3.4 — `meta` 块只读契约（T16 永久守护）

```
META FIELD CONTRACT (addendum §M3.3.J):
  The 'meta' block is metadata only. dict_to_node and dry_run MUST
  NOT read meta.* for any behavioural decision. Removing or
  modifying meta has no effect on the imported node. If you find
  yourself reading meta.exporter_version etc to branch logic, STOP
  — that's a SCHEMA_VERSION bump, not a meta hack.
```

T16 测试通过 `inspect.getsource` 读取 `dict_to_node` + `dry_run` + `_validate_node_dict`，**剥离 docstring 后**断言执行体内不出现 `'meta'` / `"meta"` / `data.get("meta"`。Docstring 中提到 "meta" 是合法的（契约说明），但执行代码引用即违约。

### M3.3.5 — M2.3 freeze contract 绕道契约（G.2 直写）

```
M2.3 BYPASS (addendum §M3.3.G):
  Import writes poseLocalTransform directly via
  core.write_pose_local_transforms and does NOT call
  capture_per_pose_local_transforms. This is the ONLY legal
  bypass of the M2.3 auto-capture path.

Rationale:
  - capture_per_pose_local_transforms reads driven_node's current
    scene state, which is unknown at Import time
  - JSON's local_transform values are export-time snapshots —
    authoritative for the exporter's scene at export-time
  - User-triggered Apply post-import will auto-capture and
    overwrite (existing M2.3 contract)
```

T_LOCAL_XFORM_BYPASS（T9 in test file）+ source-text 守护：`dict_to_node` 执行体内**不出现** `capture_per_pose_local_transforms`（docstring 中提到合法）。

### M3.3.6 — `action_id` 注册表更新（addendum §M3.0.3）

| action_id | Sub-task | Confirm 触发场景 |
|---|---|---|
| `import_replace` | M3.3 | Replace 模式 + 至少一节点 will_overwrite=True 时 |
| ~~`import_add`~~ | M3.3 | **不**走 confirm（非破坏性，无注册）|

### M3.3.7 — 改动清单

| 文件 | 改动 |
|---|---|
| `core_json.py` | +~480 行（hoisted core/core_alias imports + SchemaValidationError + _ATTR_NAME_TO_JSON_KEY bijection + node_to_dict + dict_to_node + dry_run + _validate_node_dict + _validate_attr_array + import_path + export_nodes_to_path + PerNodeReport + EXPECTED_*_KEYS frozensets）|
| `core.py` | +60 行（read/write_driver_rotate_orders + read/write_quat_group_starts 4 helpers）|
| `controller.py` | +~120 行（import_rbf_setup + export_current_to_path + export_all_to_path + _format_dry_run_report）|
| `ui/main_window.py` | +~95 行（add_file_action spillover + 3 File entries + 3 callbacks）|
| `ui/widgets/import_dialog.py` | **新建** ~110 行 |
| `ui/i18n.py` | +20 keys × 2 langs = 40 行 |
| `tests/test_m3_3_jsonio.py` | **新建** ~700 行（21 测试类，39 子测试）|
| `docs/.../addendum_20260424.md` | §M3.3 + §M3.0-spillover §2 + §M3.0 reverse-then-reapply 附录 ~210 行 |
| `docs/.../milestone_3_summary.md` | §1 进度矩阵 + §3.1 注册表 + Roadmap |

**总：~1810 行**（含测试 + addendum）；生产代码 ~620 行 < 800 上限。

### M3.3.8 — 测试矩阵

| T# | 名称 | 子测 |
|---|---|---|
| **T1** | `_ATTR_NAME_TO_JSON_KEY` 完整性 + bijection（**T1a + T1b PERMANENT**）| 2 |
| **T_M3_3_SCHEMA_FIELDS** | node_to_dict 字段集冻结（**PERMANENT**）| 2 |
| T2 | node_to_dict round-trip | 4 |
| T3 | dict_to_node call 序列 | 4 |
| T4 | dry_run 单节点 validation（含 `_label` 后缀容忍） | 7 |
| T5 | dry_run 多节点混合 + top-level 错误聚合 | 2 |
| **T6** | SCHEMA_VERSION 不变（**PERMANENT**）| 1 |
| T9 | poseLocalTransform 直写（**T_LOCAL_XFORM_BYPASS**）| 2 |
| T10 | alias_base 反推（不存）| 2 |
| T11 | dict_to_node 不直写 alias | 1 |
| T12 | atomic_write_json reuse | 1 |
| T13 | controller path A wiring + action_id | 2 |
| T14 | File menu spillover 3 entries | 2 |
| T15 | i18n 20 keys EN/CN parity | 1 |
| **T16** | meta 块只读（**PERMANENT**）| 2 |
| **T_FLOAT_ROUND_TRIP** | dump(load(dump(d))) byte-stable | 2 |
| spillover §2 helpers | T_AddFileActionExists + T_FileMenuExtensionContract | 2 |

合计 **21 测试类，39 子测试**。**总测试数：291 + 39 = 330 / 330**。

### M3.3.9 — 零回归

- `core_json.py` M3.0 surface 完全保留 —— SCHEMA_VERSION / atomic_write_json / read_json_with_schema_check / SchemaVersionError 字节级未变（顶部 hoisted import 仅添加，不修改原有定义）
- 新增 4 个 core.py multi helpers 是纯增量
- File 菜单 entries 空闲时不触发任何 IO
- 全量回归：291 + 39 = **330 / 330** 通过

### M3.3.10 — Cross-Scene Limitation（forward-compat 备注）

```
M3.3 Cross-Scene Limitation:
  - JSON references driver/driven by exact scene node name
  - Import fails when target scene uses different naming
    (e.g. "L_arm_jnt" -> "myProj_L_arm_jnt")
  - Future: M5 namespace-remap UI / regex-based import wizard
```

### M3.3.11 — Non-goals

- ❌ Update 模式（仅 poses 刷新，节点保留）—— 推 M3 后续 patch
- ❌ 跨场景命名映射（namespace remap / regex 替换）—— 推 M5
- ❌ 引擎侧 runtime（UE5 / Unity 解析 JSON 重建求解器）—— 推 M5
- ❌ Schema migration（v5.m3 → v5.m4 多版本 reader）—— 永远触发新 SCHEMA_VERSION
- ❌ Connection 拓扑外推（"用户没接上 driver/driven 时按 alias 名字猜"）
- ❌ Pose 之外的多节点关联
- ❌ Binary 压缩（.json.gz / msgpack）
- ❌ Versioned `meta.exporter_version` 用于 reader 决策
- ❌ JSON Schema validator 第三方库依赖（手写 `_validate_node_dict` 维持零依赖）

### M3.3.12 — 红线确认

- ✅ 沿用 M3 / M3.0 / M3.2 / M3.7 全部红线
- ✅ **SCHEMA_VERSION 永久不变** = `"rbftools.v5.m3"`（T6 PERMANENT）
- ✅ Import 不创建非 RBFtools 节点
- ✅ Import 不静默跳过失败 —— 两阶段 dry-run + 详细 SchemaError 列表
- ✅ `core_json.SCHEMA_VERSION` 不动；schema 字典写 `"schema_version": SCHEMA_VERSION`
- ✅ `atomic_write_json` reuse —— T12 守护
- ✅ Path A confirm（仅 Replace 模式 / `action_id="import_replace"`）
- ✅ M2.3 freeze contract 不破坏 —— Import 显式绕道（§M3.3.5 文档 + T_LOCAL_XFORM_BYPASS 守护）
- ✅ M3.7 alias 一处事实来源 —— Import 不直写
- ✅ 不引入第三方 JSON validator 依赖
- ✅ **`_ATTR_NAME_TO_JSON_KEY` 双射**（T1b PERMANENT）
- ✅ **`meta` 块只读不参与决策**（T16 source-scan PERMANENT）
- ✅ **node_to_dict 字段集冻结**（T_M3_3_SCHEMA_FIELDS PERMANENT）
- ✅ **enum 字段用整数 + 可选 `_label` 后缀**（_label-suffix 跳过逻辑 + T4 容忍测试）
- ✅ **sparse multi 索引显式 `index`**（_validate_attr_array 唯一性检查）
- ✅ **JSON float 不 rounding**（T_FLOAT_ROUND_TRIP byte-stable）

---

## §M3.1 — Pose Pruner

Milestone 3 数据卫生工具 —— TD 周用工具，删除 RBFtools 节点上的冗余 pose / driver 维度 / 常数 output。**0 行 C++**。

M3.1 的工程价值不在算法（三个独立 pure-function 扫描），而在与 **M3.7 alias 系统** + **M2.2 quat group 系统** + **M2.3 freeze 契约** 的边界交互处理。

### M3.1.1 — 决议日志

11 项决议（现状核查会话）：

| # | 分叉 | 选项 | 选定理由 |
|---|---|---|---|
| (A) | duplicate 判定 | **A.2** (input AND value) 都同才删 | 防止数据丢失；input 同 value 不同 = 用户错误 |
| (B) | redundant driver 语义 | **B.2** 删 RBFtools 的 input[] 引用 | 不动 driver 节点；保护 rig 拓扑 |
| (C) | 阈值 | **C.1** `1e-6`（同 `core.float_eq`）| 一处事实来源 |
| (D) | quat group 副作用 | **D.3** warning + 继续 + (γ3.b) shift 索引 | 用户语义保留 + 信息全告知 |
| (E) | invalid group 处理 | **E.2** start 保留原值 | 用户语义不擦除；C++ silently skip |
| (F) | 单 pose 右键 | **F.2** 直接删 + warning | 单 pose 低风险；轻量 |
| (G) | UI 控件 | **G.2** 三 QCheckBox 独立勾选 | 用户精细控制 |
| (H) | conflict pairs | **H.3** informational only | 不自动决定用户错误 |
| (I) | execute 路径 | **I.2** 复用 `apply_poses` 主路径 | 最小 blast radius；零新代码 |
| (J) | alias 操作 | **J.2** 完全委托 `auto_alias_outputs` 兜底 | F1 验证可行；M3.7 单一来源 |
| (K) | 作用范围 | **K.1** 当前节点 | 批量推后续 |

加固 1：T4 `shift_quat_starts` 边界守护扩展为 **7 子测试**（T4.a-g）。
加固 2：`analyse_node` 0 mutation 升级为 **T13 PERMANENT** source-scan。

### M3.1.2 — F1-F4 现状核查（在选项之前先验证）

执行者在产出 (A)-(K) 选项**之前**先验证现成 helper 的实际行为，把 4 个关键依赖从假设提升到已验证：

| # | 验证项 | 结论 | 影响 |
|---|---|---|---|
| F1 | `auto_alias_outputs` 是否清理 stale alias? | ✅ `apply_aliases` non-force 路径首步调 `clear_managed_aliases` | (J.2) 兜底方案可行 |
| F2 | `read_output_baselines` / `write_output_baselines` 索引模型 | ✅ clear-then-write 模式 | (Q6) sparse shift bug 风险消解 |
| F3 | ConfirmDialog 预览渲染 | ✅ 已用 monospace QPlainTextEdit | 多列 ASCII 报告无需扩展 API |
| F4 | `read_all_poses` / `apply_poses` 重建路径 | ✅ packed `enumerate(poses)` | (I.2) execute 复用整条路径 |

**F1-F4 是 M3.x 跨子任务交互场景的标准 review 入口**——任何依赖既有 helper 行为的子任务都应先做这一步。

### M3.1.3 — `shift_quat_starts` 算法（**T_QUAT_GROUP_SHIFT 永久守护，7 子测试**）

```python
def shift_quat_starts(starts, removed_output_indices):
    """Pure function — no scene access.

    For each *start* in *starts*:
      - if any removed index in [start, start+3] → output None (invalid)
      - else → output (start - count(removed indices < start))
    """
    rm = sorted(set(int(r) for r in removed_output_indices))
    new = []
    for s in starts:
        if any(s <= r <= s + 3 for r in rm):
            new.append(None)
        else:
            new.append(s - sum(1 for r in rm if r < s))
    return new
```

7 边界场景（T4.a-g）锁定全行为空间：

| Sub | 场景 | 期望 |
|---|---|---|
| T4.a | 不重叠不需 shift | start 不变 |
| T4.b | 范围内失效 | None |
| T4.c | 不重叠需 shift | `start - count_before` |
| T4.d | 多 removed 多 group 独立 | 各独立计算 |
| T4.e | removed 为空 | identity |
| T4.f | starts 为空 | `[]` |
| T4.g | 同 group 多 removed in range | None（同 b）|

### M3.1.4 — Cross-sub-task 副作用处理范例（M3.x / M4.x 参考）

M3.1 是 v5 设计中**首次**跨子任务副作用处理：触及 M2.2 quat group 用户语义的同时不能越权修改。决策模式：

1. **F1-F4 现状验证**：先确认现成 helper 行为再选方案
2. **(D.3.b) shift 索引但不改语义**：未受影响 group 的 start 值随 packed 索引调整以**保持原指向**；改 start 是为了**不改语义**
3. **(E.2) invalid group start 保留原值**：被破坏的 group **不擦除**用户的声明；C++ 端 silently skip 是 defensive logic 兜底
4. **dialog warning 全告知**：用户得到完整副作用清单，自主决定是否继续
5. **零自动修复**：pruner 不"帮"用户修破坏，仅信息透明

这套模式在未来 M4.x（附加 solver）/ M5（性能优化）触及用户已有声明时**值得参考**。原则归纳：

```
用户语义保留 > 自动修复
信息透明 > 静默处理
最小侵入 > 全面接管
defensive C++ + warning UI > 阻塞 dialog
```

### M3.1.5 — 改动清单

| 文件 | 改动 |
|---|---|
| `core_prune.py` | **新建** ~270 行（PruneOptions + PruneAction + QuatGroupEffect + 4 pure scan helpers + shift_quat_starts + analyse_node + execute_prune）|
| `controller.py` | +`prune_current_node` + `_format_prune_report` ~120 行 |
| `ui/main_window.py` | +`_on_prune_poses` + `_on_remove_pose_row` + 2 spillover 注册 ~30 行 |
| `ui/widgets/prune_dialog.py` | **新建** ~95 行（3 QCheckBox + preview + Prune button enabled-state）|
| `ui/i18n.py` | +12 keys × 2 langs = 24 行 |
| `tests/test_m3_1_prune.py` | **新建** ~430 行（13 测试类，26 子测试）|
| `docs/.../addendum_20260424.md` | §M3.1 ~140 行 |
| `docs/.../milestone_3_summary.md` | 进度 + action_id 注册 |

**总：~1110 行**（含测试 + addendum）；生产代码 ~440 行 < 800 上限。

`core.py` **0 改动** —— pruner 完全复用 `apply_poses` + `write_quat_group_starts` 既有 API。

### M3.1.6 — 测试矩阵

| T# | 名称 | 子测 |
|---|---|---|
| T1 | `_scan_duplicates` (input AND value) + conflict 分离 | 3 |
| T2 | `_scan_redundant_inputs` | 2 |
| T3 | `_scan_constant_outputs` | 2 |
| **T4** | **`shift_quat_starts` 7 边界场景**（**T_QUAT_GROUP_SHIFT PERMANENT**）| 7 |
| T5 | `analyse_node` end-to-end + has_changes 语义 | 3 |
| T6 | `execute_prune` apply_poses + write_quat_group_starts 调用序列 | 1 |
| T7 | controller path A wire（action_id="prune_poses"）| 2 |
| T8 | Tools 菜单走 add_tools_action | 1 |
| T9 | pose-row 走 add_pose_row_action(danger=True) | 1 |
| T10 | i18n 12 keys EN/CN parity | 1 |
| T11 | Pruner 不直接调 cmds.aliasAttr（source-scan）| 1 |
| **T12** | **invalid quat group 保留原 start 值**（E.2 契约）| 1 |
| **T13** | **`analyse_node` read-only**（**T_ANALYSE_READ_ONLY PERMANENT**，source-scan 7 mutations）| 1 |

合计 **13 测试类，26 子测试**。**总测试数：330 + 26 = 356 / 356**。

### M3.1.7 — Action ID 注册表更新（addendum §M3.0.3）

| action_id | Sub-task | Confirm 触发场景 |
|---|---|---|
| `prune_poses` | M3.1 | Pose Pruner 在 dry-run 后 execute 前 |

**第 4 个 path A 真实消费者**——前 3 个 mirror_create / mirror_overwrite / import_replace / force_regenerate_aliases 都已经稳定运行；本次零 ConfirmDialog API 修改。

### M3.1.8 — Mirror sibling 边界（addendum 明记）

```
M3.1 Mirror Sibling Boundary:
  - Pruning RBF_L_arm does NOT cascade to RBF_R_arm (mirror sibling)
  - M3.2 mirror is a one-shot copy operation; subsequent edits on
    either side are independent
  - To sync prune across siblings, re-run mirror manually after prune
  - M3 后续 patch 可考虑 "sync siblings" UX, but not in M3.1 scope
```

### M3.1.9 — Driven node rest-pose responsibility (M2.3 freeze 契约的延伸)

```
M3.1 Driven Node State Requirement:
  - execute_prune calls apply_poses internally, which triggers
    capture_per_pose_local_transforms (M2.3 step 4)
  - capture path requires driven_node to be in rest pose (non-driven
    channels frozen at Apply-time scene state, per §M2.3 freeze contract)
  - User must reset driven_node to rest before pruning, OR accept
    that non-driven channels capture whatever the current scene says
  - This mirrors the M2.3 user education in §M2.3
```

### M3.1.10 — 零回归

- `core.py` 0 改动 —— 没有新 read/write helper 引入回归面
- M3.0 spillover §1 复用（add_tools_action / add_pose_row_action（danger=True 渲染））—— 既有测试守护
- M3.7 alias 单一来源未破坏 —— T11 source-scan 守护
- M2.2 quat group 用户语义未越权修改 —— T_QUAT_GROUP_SHIFT 7 子测试 + T12 invalid 保留 守护
- 全量回归：330 + 26 = **356 / 356** 通过

### M3.1.11 — Non-goals

- ❌ 批量节点 prune（多 RBF 同时跑）
- ❌ Pruner 自动修改 `outputQuaternionGroupStart` 用户语义
- ❌ Pruner 内部 alias 操作 —— 完全委托 M3.7
- ❌ Mirror sibling 自动同步
- ❌ "Auto-resolve conflicting poses" —— 仅 informational
- ❌ 删 driver_node / driven_node 上的 attr
- ❌ 删 RBFtools 节点本身

### M3.1.12 — 红线确认

- ✅ 沿用 M3 / M3.0 / M3.2 / M3.7 / M3.3 全部红线
- ✅ Pruner 0 行 `cmds.aliasAttr` 直接调用（T11）
- ✅ Pruner 不修改用户 quat group 语义（T_QUAT_GROUP_SHIFT + T12）
- ✅ Pruner 不动 driver_node / driven_node attrs
- ✅ Pruner 不删除 RBFtools 节点本身
- ✅ Mirror sibling 不同步（设计如此，addendum 明记）
- ✅ Path A confirm（`action_id="prune_poses"`）—— 第 4 真实消费者
- ✅ `shift_quat_starts` 通过 7 个边界场景测试（T4.a-g PERMANENT）
- ✅ `analyse_node` 永远 read-only（T13 source-scan PERMANENT）
- ✅ 单 pose 右键删除发 warning（addendum §M3.1.9 用户 expectation）

---

## §M3.6 — Auto-Neutral Sample on Fresh Node

Milestone 3 数据卫生子任务的"播种端"——新建 RBFtools 节点时自动注入一个 rest pose，避免用户漏加 baseline anchor 导致首次 RBF 训练数值退化。**0 行 C++ + 0 行 `core.py` 改动**（与 M3.1 对称——纯复用既有 helper）。

### M3.6.F0 — CMT "3-pose" Pattern Does NOT Map to RBFtools v5

设计文档 PART E.9 提到 "CMT-style 3 neutral samples"。**直读 CMT 源码**（`docs/源文档/chadvernon/cmt-master/scripts/cmt/rig/rbf.py:11-48`）发现这是个常见误读：

```python
# CMT cmt/rig/rbf.py:11-48  (Chad Vernon's reference RBF implementation)
class RBF(object):
    swing = 0
    twist = 1
    swing_twist = 2

    @classmethod
    def create(cls, ..., add_neutral_sample=True):
        ...
        if add_neutral_sample:
            for i in range(3):
                node.add_sample(
                    output_values=output_values,
                    output_rotations=output_rotations,
                    rotation_type=i,    # ← per-sample metadata flag
                )
```

CMT's `add_sample` 不传 `input_values` / `input_rotations` 时**默认读当前场景状态**（rbf.py:233-241）。三个 sample 的输入完全相同（identity at create-time），仅每个 sample 自带 `rotationType` flag (0/1/2 = swing/twist/swing+twist) 选择距离度量。

**三个论点说明 CMT 模式不映射**：

1. CMT `rotationType` 是 **per-sample** distance-metric flag —— 不是 input 角度变体
2. RBFtools v5 把 metric 提到**节点级** `inputEncoding`（M2.1a/b: Raw / Quat / BendRoll / ExpMap / SwingTwist）—— 所有 sample 共享一个 encoding
3. 因此正确等价是**单 rest pose**。复刻 CMT 字面 3-pose 在 RBFtools 上会注入 3 个 identical inputs，让 kernel 距离矩阵奇异 + 触发 M2.2 PSD guard fallback —— 数学冗余甚至病态

### M3.6.F0+ — Verify-Before-Design Pattern (项目 cross-cut 范式)

M3.6 F0 是项目第三次"先核查后设计"的实例：

| Milestone | 先核查项 | 落地章节 |
|---|---|---|
| M3.7 commit retrospective | reverse-then-reapply 用 Edit + Python 替代 git add -p | addendum §M3.0 appendix |
| M3.1 | F1-F4 helper 行为预核查（`auto_alias_outputs` clear stale alias / multi attr index 模型 / ConfirmDialog monospace / read+apply packed-rebuild）| addendum §M3.1.2 |
| M3.6 | F0 直读 CMT 源码（rbf.py:11-48）发现 per-sample rotationType ≠ 角度变体 | 本节 |

**通用规则**：任何 milestone 涉及"参考某个第三方实现"的子任务，先**直读源码**而非依赖二手描述/分析报告。CMT / AnimaDriver / Chad Vernon / Tekken 资料都适用。详见 §M3.0 reverse-then-reapply / §M3.1.2 F1-F4 / §M3.6 F0 三处 verify-before-design 标准入口。

### M3.6.1 — 决议日志（9 项）

| # | 分叉 | 选项 | 选定理由 |
|---|---|---|---|
| (A) | Neutral pose 数量 | **A.1** 单 rest pose | F0 验证 CMT 模式不适用 |
| (B) | 触发时机 | **B.3** 双轨（auto on create + manual button）+ 默认 true | 与 M1.2 baseline 自动捕获一致；optionVar 关闭 |
| (C) | optionVar 名 | **C.1** `RBFtools_auto_neutral_sample`（单数）| 反映 Q1 修订真实语义 |
| (D) | Driven values 来源 | **D.2** 0/1 + isScale + quat W=1 | 当 driven_node 未连接时安全 placeholder |
| (E) | UI 入口 | **E.1** Tools menu entry（不引入 spillover §3）| ToolsSection collapsible 推到 M3.5 真正需要 panel 时 |
| (F) | Edit 菜单 reset | **F.2** 加 "Reset auto-neutral default" | 沿用 M3.0 reset_confirms 模式 |
| (G) | 手动按钮 + existing | **G.3** confirm + insert at 0 | 与 M1.2 "pose[0] is rest" 约定一致 |
| (H) | quat leader W=1 | **H.2** 强制 | 避免 PSD guard fallback；与 M2.2 SwingTwist `q_w >= 0` 规范一致 |
| (I) | 命名 | **I.2** `add_neutral_sample` 单数 | 反映单 rest pose 语义 |

### M3.6.2 — `add_neutral_sample` 加固契约（统一代码路径）

```
M3.6 unified-path contract:
  add_neutral_sample(node) reads quat_group_starts and isScale
  flags from the node ON EVERY CALL — does NOT assume empty
  even on the auto-create-node path. Rationale: rare workflows
  (template import, external scripting) may pre-set
  outputQuaternionGroupStart on a fresh node before the
  auto-trigger fires; honouring those values is essential.
  Single code path covers auto + manual; no branching.
```

T_NEUTRAL_QUAT_W 三 sub-test 守护此规则（无 group / 单 group / 多 group）。

### M3.6.3 — `generate_neutral_values` 算法（pure function）

```python
def generate_neutral_values(n_outputs, output_is_scale=None,
                            quat_group_starts=None):
    """Build the rest-pose driven-values vector.

    Rules:
      - Default 0.0 in every slot.
      - is_scale=True slots forced to 1.0 (M1.2 contract).
      - For each quat-group leader index s, slot s+3 (W comp of
        identity quaternion) forced to 1.0.
    """
    flags = list(output_is_scale) if output_is_scale else []
    while len(flags) < n_outputs:
        flags.append(False)
    out = [1.0 if flags[i] else 0.0 for i in range(n_outputs)]
    for s in (quat_group_starts or []):
        if 0 <= s + 3 < n_outputs:
            out[s + 3] = 1.0
    return out
```

### M3.6.4 — 创建顺序 & 流水线边界（write-only on poses[0]）

```
controller.create_node():
  1. core.create_node()                         # 新 RBFtools shape
  2. self.refresh_nodes() / _load_settings() / _load_editor()
  3. ★ if _auto_neutral_enabled() AND .type == 1:
        core_neutral.add_neutral_sample(transform)
        self._load_editor()
```

**关键**：M3.6 **只**写 pose[0] 数据；**不**触发：

- ❌ M3.7 `auto_alias_outputs`（首次 Apply 兜底）
- ❌ M1.2 `capture_output_baselines`（首次 Apply 兜底）
- ❌ M2.3 `capture_per_pose_local_transforms`（首次 Apply 兜底）

T4b source-text scan 守护：`add_neutral_sample` 执行体内**不出现** `apply_poses` / `capture_output_baselines` / `capture_per_pose_local_transforms` / `auto_alias_outputs` 任何字符串（comment 也不出现 —— 我已统一改为"the Apply step"避免歧义）。

### M3.6.5 — M3.6 与 M1.2 Baseline 一致性

`controller.create_node` auto-seed 写 `pose[0]`（values 全 0 + isScale slot 1.0 + quat W=1），用户首次 Apply 时 M1.2 `capture_output_baselines` 优先用 `pose[0]` 的 driven values 作 baseline。**两者首次自动一致**：M3.6 的 rest pose values 即 M1.2 baseline 来源。

后续 Apply 重 capture 时若 pose[0] 还是 rest → baseline 仍一致；若用户改了 pose[0] → baseline 跟随。**无 bug**，addendum 一行明记。

### M3.6.6 — UI 入口

| 入口 | 通道 |
|---|---|
| 自动触发 | `controller.create_node` 末尾（gated on optionVar + type==1）|
| 手动按钮 | `Tools → Add Neutral Sample`（`add_tools_action`）|
| optionVar 复位 | `Edit → Reset auto-neutral default`（不走 confirm，沿用 M3.0 reset_confirms 模式）|

**未引入 ToolsSection collapsible** —— 推到 M3.5 Pose Profiler 真正需要 per-node 工具面板时再创建（spillover §3 候选）。

### M3.6.7 — Action ID 注册表更新（addendum §M3.0.3）

| action_id | Sub-task | Confirm 触发场景 |
|---|---|---|
| `add_neutral_with_existing` | M3.6 | 手动按钮 + pose[0] 已有用户 pose（非 rest）时 |
| ~~`add_neutral_auto`~~ | M3.6 | **不**走 confirm（自动 create-time 触发，空节点无破坏）|
| ~~`add_neutral_first`~~ | M3.6 | **不**走 confirm（手动按钮 + 空节点无破坏）|

**第 5 个 path A 真实消费者**——前 4 个 mirror_create / mirror_overwrite / import_replace / force_regenerate_aliases / prune_poses 模式稳定运行；本次零 ConfirmDialog API 修改。

### M3.6.8 — 改动清单

| 文件 | 改动 |
|---|---|
| `core_neutral.py` | **新建** ~135 行（`generate_neutral_values` pure + `add_neutral_sample` Maya-touching + F0 docstring）|
| `core.py` | **0 改动**（pruner-style 复用：`read_quat_group_starts` / `read_output_baselines` / `read_all_poses` / `_write_pose_to_node` / `clear_node_data` 全部既有 helper）|
| `controller.py` | +`_auto_neutral_enabled` + `reset_auto_neutral_default` + `add_neutral_sample_to_current_node` + `create_node` auto-trigger ~80 行 |
| `ui/main_window.py` | +Tools entry + Edit reset entry + 2 callbacks ~30 行 |
| `ui/i18n.py` | +8 keys × 2 langs = 16 行 |
| `tests/test_m3_6_neutral.py` | **新建** ~330 行（8 测试类，18 子测试）|
| `docs/.../addendum_20260424.md` | §M3.6 ~135 行（含 F0 + verify-before-design 范式）|
| `docs/.../milestone_3_summary.md` | 进度 + action_id 注册 |

**总：~625 行**（含测试 + addendum）；**生产代码 ~260 行 < 800 上限** ——M3 系列最简子任务之一，与 M3.1 并列在"零 core.py 改动"克制层。

### M3.6.9 — 测试矩阵

| T# | 名称 | 子测 |
|---|---|---|
| T1 | `generate_neutral_values` 默认全 0 | 1 |
| T2 | `generate_neutral_values` isScale=True 强制 1.0 + 短 flags 列表 padding | 2 |
| **T3** | **T_NEUTRAL_QUAT_W** quat leader W=1（**3 sub: 无 group / 单 group / 多 group**）| 3 |
| T4 | `add_neutral_sample` call sequencing：写 pose[0] / 不触发流水线 source-scan / 幂等 / 已有 pose shift +1 | 4 |
| T5 | `controller.create_node` auto-trigger gating（optionVar 默认 / 关闭 / 源码守护）| 3 |
| T6 | 手动按钮 + existing poses 触发 confirm（action_id 字符串守护 + 方法存在）| 2 |
| T7 | Tools 菜单 + Edit reset 菜单 source-scan | 2 |
| T8 | i18n 8 keys EN/CN parity | 1 |

合计 **8 测试类，18 子测试**。**总测试数：356 + 18 = 374 / 374**。

### M3.6.10 — 零回归

- `core.py` **0 改动** —— 没有新 helper 引入回归面（M3 系列第二次零核心改动，与 M3.1 对称）
- 自动触发 gated on type==1 —— `core.create_node` 当前默认 type=0（VectorAngle），所以 "New" 按钮流程下 M3.6 自动是 no-op；手动按钮是实际入口。未来若改 `create_node` 默认 type=1，自动路径自然激活
- M3.7 alias / M1.2 baseline / M2.3 localXform 都没被 M3.6 触发 —— 首次 Apply 时全部由 `apply_poses` 兜底
- 全量回归：356 + 18 = **374 / 374** 通过

### M3.6.11 — Non-goals

- ❌ CMT 字面 3-pose 复刻（F0 验证不适用）
- ❌ inputEncoding 5 档 swing/twist 数学表（Q1 修订后不需要）
- ❌ 用户自定义 neutral pose 角度 / 数量 —— 推 M3 后续 patch
- ❌ Pruner 触发后自动重建 neutral —— 用户主动操作（沿用 M3.1 设计）
- ❌ 引入 ToolsSection collapsible —— 推到 M3.5 Profiler
- ❌ M3.6 不触发 alias / baseline / poseLocalTransform —— `apply_poses` 兜底
- ❌ 自动 neutral 在 driver/driven 已配置后再次触发 —— 仅 create_node 一次

### M3.6.12 — 红线确认

- ✅ 沿用 M3 / M3.0 / M3.2 / M3.7 / M3.3 / M3.1 全部红线
- ✅ M3.6 不主动 setAttr alias（M3.7 兜底）
- ✅ M3.6 不主动 capture baseline / poseLocalTransform（apply 兜底）
- ✅ M3.6 不修改既有 pose（仅 append；覆盖只发生在用户显式 confirm）
- ✅ optionVar 复位入口不需 confirm
- ✅ addendum §M3.6 F0 明文记录 CMT 模式不适用 RBFtools v5 的三个论点
- ✅ optionVar 单数命名 `RBFtools_auto_neutral_sample`
- ✅ `add_neutral_sample` 永远从节点查询 `quat_group_starts`（统一代码路径）
- ✅ T_NEUTRAL_QUAT_W 永久守护（3 sub-cases）
- ✅ T4b source-scan 守护流水线边界（write-only on poses[0]）

---

## §M3.5 — Pose Profiler

Milestone 3 倒数第二个子任务 —— 纯只读诊断工具。算法 85% 纯函数比例（M3.x 系列最高），**0 行 C++ + 0 行 core.py 改动**——M3.1 / M3.6 / M3.5 三连续克制范式。

### M3.5.F1-F4 — Verify-before-design 第 4 次使用

| # | 验证项 | 结论 | 决议影响 |
|---|---|---|---|
| **F1** | `lastSolveMethod` 能否从 Python 读？ | ❌ —— C++ 实例成员（[source/RBFtools.cpp:137](source/RBFtools.cpp:137)），**不是** MObject Maya attr | (A.3) Profile 删 `last_solve_method` 字段，仅显示 `solver_method` 配置值 + caveat。**0 C++ 红线绝对优先**于诊断字段价值——开口子整个 M3 系列零 C++ 契约就崩 |
| **F2** | M1.4 是否有 benchmark ms 数据？ | ❌ —— addendum 全文无 ms / millisecond / 时间常数 | (B.3) 用概念常数 `_K_CHOL` / `_K_GE` / `_K_QWA` + **显著 caveat**；M5 真实 benchmark 替换；符号名作为 forward-compat 接口保留 |
| **F3** | `CollapsibleFrame` API 够用？ | ✅ —— `add_widget` / `set_visible_content` / `set_title` 全齐 | (F.3 + spillover §3) ToolsSection 是薄 lazy subclass + widget_id 索引字典 |
| **F4** | `core_prune.analyse_node` 复用可行？ | ✅ —— read-only（T_ANALYSE_READ_ONLY）+ 返回所有 health-check 字段 | (E.2) Profiler 0 行重新实现扫描 |

四个事实直接驱动四项决议修订（A.3 / B.3 / F.3 / E.2）—— 这是 verify-before-design 模式的最高价值形态。

### M3.5.1 — 决议日志（10 项 + 2 加固）

| # | 分叉 | 选项 | 选定理由 |
|---|---|---|---|
| (A) | `last_solve_method` 字段 | **A.3** 显示 `solver_method` 配置值 + caveat | F1 验证不可读；0 C++ 红线 |
| (B) | Solve 时间单位 | **B.3** 绝对 ms + 显著 caveat | 用户感知量级；caveat 防误信 |
| (C) | 拆分建议形式 | **C.2** 仅量级表无语义 | profile 不暗示自动化 |
| (D) | 拆分阈值 | **D.3** n_poses>80 + cells>500 + cholesky>5ms | 三条件任一即建议 |
| (E) | Health checks | **E.2** 复用 M3.1 analyse_node | 一处事实来源（F4） |
| (F) | 展示形式 | **F.3** 双入口（ToolsSection + Tools 菜单） | 常驻 + 复制保存 |
| (G) | 自动刷新 | **G.3** 切换清空 + 手动 Refresh | 避免大节点切换卡顿 |
| (H) | spillover §3 dup widget_id | **H.2** RuntimeError 拒绝 | 防 M3.4 状态泄漏 |
| (I) | spillover §3 是否含 remove | **I.2** add + remove | 前瞻 M3.4 |
| (J) | 校准常数位置 | **J.1** 模块级常数 | M5 之前不需 UI 暴露 |
| 加固 1 | caveat 可见性 | T_CAVEAT_VISIBLE 守护 | 双行 + 调参入口提示 |
| 加固 2 | ToolsSection 持久 | T_TOOLS_SECTION_PERSISTS 守护 | once created, persists |

### M3.5.2 — Read-only 契约（T_PROFILE_READ_ONLY 永久守护）

```
profile_node body MUST NOT contain any cmds.* mutation call or
undo_chunk wrapper. T_PROFILE_READ_ONLY (PERMANENT GUARD)
source-scans for 8 forbidden symbols:
  cmds.setAttr / connectAttr / disconnectAttr / delete /
  removeMultiInstance / aliasAttr / createNode / undo_chunk

Mirrors M3.1 T_ANALYSE_READ_ONLY. Profiler is the second M3.x
sub-task to ship a read-only PERMANENT guard.
```

### M3.5.3 — Caveat 可见性契约（T_CAVEAT_VISIBLE 永久守护）

格式约束：

1. Caveat 文字用 `[ ... ]` 方括号包围（视觉显著）
2. Performance 段 **section 头** 即带 caveat：`Performance estimates  [CONCEPTUAL — no machine calibration]`
3. Performance 段**末尾**重复带调参符号名 `[tune _K_CHOL / _K_GE / _K_QWA in core_profile.py for your hardware; see addendum §M3.5.F2]`
4. solver_method 字段同段 + 引用 §M3.5.F1

T_CAVEAT_VISIBLE 三 sub-test 守护：

- `[CONCEPTUAL — no machine calibration]` 字符串必须在 report 出现
- `_K_CHOL` 标识符必须在 report 出现（用户 grep 调参入口）
- `[configured value;` 字符串必须在 report 出现（F1 caveat）

任何重写 `format_report` 删掉 caveat 都会被立即捕获。

### M3.5.4 — Split-suggestion 算法（**informational only**）

```
触发条件（任一即给建议）:
  n_poses > 80
  n_inputs * n_outputs > 500
  cholesky_time_ms > 5.0  (estimated)

输出形式:
  仅给量级表 (N=2/3/4 拆分后每节点估算时间)
  不给"按 swing/twist/finger" 等语义猜测
  明文 "Splitting strategy is rig-semantic and must be decided
        by the user — Profiler does not auto-split or suggest
        specific attribute groupings."

Profile 永远不自动执行拆分。
```

### M3.5.5 — Spillover §3 — `add_tools_panel_widget` / `remove_tools_panel_widget`

ToolsSection collapsible 首次落地。**M3.0-spillover §3**（追溯式归章节群）。

```python
# RBFToolsWindow

def _ensure_tools_section(self):
    """Lazily create ToolsSection on first call. Once created,
    persists for the session — see T_TOOLS_SECTION_PERSISTS."""
    if getattr(self, "_tools_section", None) is None:
        self._tools_section = CollapsibleFrame(tr("section_tools"))
        self._tools_panel_widgets = {}
        self._sections.insertWidget(
            self._sections.count() - 1, self._tools_section)
    return self._tools_section

def add_tools_panel_widget(self, widget_id, widget):
    """Register *widget* under *widget_id*. Lazily creates
    ToolsSection on first call. Raises RuntimeError on duplicate
    widget_id (no silent overwrite — H.2)."""

def remove_tools_panel_widget(self, widget_id):
    """Unregister and detach. ToolsSection itself is NOT
    destroyed even when the last child is removed
    (T_TOOLS_SECTION_PERSISTS contract — avoids visual flicker
    on subsequent add)."""
```

**契约（M3 全程红线）**：

1. 后续 M3.x 子任务的 ToolsSection 扩展**必须**走此 helper —— 禁止再直接 `_main_layout.insertWidget` 操作
2. **T_TOOLS_SECTION_PERSISTS PERMANENT GUARD**：source-scan `remove_tools_panel_widget` 体内**不出现** `self._tools_section = None` 或 `self._tools_section.deleteLater`
3. **重复 widget_id → RuntimeError 拒绝**（H.2 防 M3.4 状态泄漏）
4. M3.5 是首个真实消费者：`add_tools_panel_widget("profile_report", ProfileWidget(...))`

### M3.5.6 — M3.4 Forward-Compat Contract

`add_tools_panel_widget` / `remove_tools_panel_widget` 签名锁定。M3.4 Live Edit 落地不再变更：

```python
add_tools_panel_widget(widget_id: str, widget: QWidget) -> QWidget
remove_tools_panel_widget(widget_id: str) -> bool
```

M3.4 实施时如需扩展（例如 widget 显示/隐藏切换），**必须保持现有 add/remove 接口不变**（向后兼容）。新功能用新方法名（如 `set_tools_panel_widget_visible`）扩展。

预期 M3.4 调用形式：

```python
self._live_edit_cb = QtWidgets.QCheckBox(tr("live_edit_toggle"))
self._live_edit_cb.toggled.connect(self._on_live_edit_toggled)
self.add_tools_panel_widget("live_edit_toggle", self._live_edit_cb)
```

### M3.5.7 — 改动清单

| 文件 | 改动 | 行数 |
|---|---|---|
| `core_profile.py` | **新建** ~340 行（profile_node + format_report + 估算函数 + 阈值常数 + `_K_*` calibration 常数 + F1/F2/F3/F4 docstring） |
| `core.py` | **0 改动**（M3.1 / M3.6 / M3.5 三连续零核心改动）|
| `controller.py` | +`profile_current_node` + `profile_to_script_editor`（read-only，无 ask_confirm）~30 行 |
| `ui/main_window.py` | +`_ensure_tools_section` + `add_tools_panel_widget` + `remove_tools_panel_widget` + Tools entry + 1 callback + ProfileWidget wiring ~95 行 |
| `ui/widgets/profile_widget.py` | **新建** ~60 行（QPlainTextEdit + Refresh + on_node_changed slot）|
| `ui/i18n.py` | +5 keys × 2 langs = 10 行 |
| `tests/test_m3_5_profile.py` | **新建** ~440 行（13 测试类，**25 子测试**，含 T_PROFILE_READ_ONLY + T_REUSE_PRUNE + T_CAVEAT_VISIBLE 3 sub + T_TOOLS_SECTION_PERSISTS 1 sub + T7 spillover 3 sub）|
| `docs/.../addendum_20260424.md` | §M3.5 + spillover §3 + F1/F2 caveat + M3.4 forward-compat ~165 行 |
| `docs/.../milestone_3_summary.md` | 进度（6/7 → 6/7 但 next 改 M3.4）+ 把 M3.5 加入 6/7 已完成 |

**总：~1140 行**（含测试 + addendum）；**生产代码 ~525 行 < 800**。

### M3.5.8 — 测试矩阵

| T# | 名称 | 子测 |
|---|---|---|
| T1 | `_estimate_solve_times` 大 O 单调 + GE 3× Cholesky + qwa 仅 quat groups | 3 |
| T2 | `_estimate_memory` 三组件正确 + n=0 边界 | 2 |
| **T3** | `profile_node` 端到端（**T_REUSE_PRUNE** 复用 M3.1 analyse_node + health 字段传递）| 3 |
| T4 | `format_report` 全 7 sections 出现 + OK 推荐 | 2 |
| T5 | split-suggestion 触发（WARN / 量级表 / 无触发不显 WARN / 阈值常数）| 4 |
| **T6** | **T_PROFILE_READ_ONLY** PERMANENT — 8 mutation 黑名单 source-scan | 1 |
| T7 | spillover §3 add_tools_panel_widget 三场景（懒创建 / dup_id 拒绝 / 方法存在）| 3 |
| **T_TOOLS_SECTION_PERSISTS** | PERMANENT — `remove_tools_panel_widget` 不销毁 panel（source-scan）| 1 |
| **T_CAVEAT_VISIBLE** | PERMANENT — perf caveat / `_K_CHOL` / configured value 三段必须在 report 出现 | 3 |
| T8 | controller `profile_current_node` 不调 `ask_confirm`（read-only 无需 confirm）| 1 |
| T9 | Tools 菜单走 `add_tools_action` spillover | 1 |
| T10 | i18n 5 keys EN/CN parity | 1 |

合计 **13 测试类，25 子测试**。**总测试数：374 + 25 = 399 / 399**。

### M3.5.9 — 零回归

- `core.py` **0 改动** —— 第 3 次连续零核心改动（M3.1 / M3.6 / M3.5）
- `core_prune.analyse_node` 签名沿用（T_REUSE_PRUNE forward-compat 约束）
- ToolsSection 是新增 collapsible，不影响既有 sections（General / VectorAngle / RBF / PoseEditor）
- ProfileWidget 节点切换时显示 placeholder（不自动跑 profile，避免大节点卡顿）
- 全量回归：374 + 25 = **399 / 399** 通过

### M3.5.10 — Non-goals

- ❌ 自动拆分 RBFtools 节点
- ❌ 跨节点 / 全场景 profile
- ❌ 历史 profile 对比 / Diff
- ❌ Profile export 到 CSV / JSON（推 M5）
- ❌ Live profile（compute 实时计时；推 M3.4 / M5 monitoring）
- ❌ Cross-node comparison
- ❌ "Apply suggested optimization" 按钮（profile 只读）
- ❌ 暴露 `lastSolveMethod` 真实值（需 C++ 改动；红线"0 C++"拒绝）
- ❌ Machine-calibrated 性能常数（M5 真实 benchmark 替换 `_K_*`）

### M3.5.11 — 红线确认

- ✅ 沿用 M3 / M3.0 / M3.2 / M3.7 / M3.3 / M3.1 / M3.6 全部红线
- ✅ Profile **永远只读**（**T_PROFILE_READ_ONLY** PERMANENT）
- ✅ 拆分建议**仅 informational**，永远不自动执行
- ✅ ToolsSection collapsible **懒创建 + 一旦创建持久存在**（**T_TOOLS_SECTION_PERSISTS** PERMANENT）
- ✅ Spillover §3 重复 widget_id → **RuntimeError 拒绝**
- ✅ Solve 时间估算**显著标注** `[CONCEPTUAL — no machine calibration]`（**T_CAVEAT_VISIBLE** PERMANENT 3 sub）
- ✅ Profile 复用 M3.1 `analyse_node`（T_REUSE_PRUNE）
- ✅ **0 行 core.py 改动**（M3.1 / M3.6 / M3.5 三连续克制）
- ✅ **0 行 C++ 改动**（F1 不暴露 lastSolveMethod）
- ✅ M3.4 forward-compat：`add_tools_panel_widget` / `remove_tools_panel_widget` 签名锁定

---

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
