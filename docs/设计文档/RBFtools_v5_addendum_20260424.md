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

### M3.5.6.M3.4-validation — Spillover §3 forward-compat contract validated

**追加（M3.4 commit 末尾）**：M3.4 实施时实测 §3 API（`add_tools_panel_widget` / `remove_tools_panel_widget`）作为第二真实消费者：

```python
# M3.4 LiveEditWidget registration:
self.add_tools_panel_widget("live_edit_toggle", LiveEditWidget(...))
```

- ✅ Lazy creation 行为正确（M3.5 已建 ToolsSection；M3.4 仅 add child）
- ✅ widget_id `"live_edit_toggle"` 不与 `"profile_report"` 冲突（H.2 RuntimeError 防护未触发，正确）
- ✅ M3.4 不调 `remove_tools_panel_widget`（Live Edit 永久存在）—— remove API 在 M3.4 不消费但保留为 forward-compat
- ✅ **M3.5 forward-compat 契约成立**：M3.4 实施零 §3 API 修改

签名锁定（M5 monitoring 等后续子任务消费时）—— **`add_tools_panel_widget` / `remove_tools_panel_widget` 签名永远不变**，新功能用新方法名扩展（如 `set_tools_panel_widget_visible`）。

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

## §M3.4 — Live Edit Mode

Milestone 3 收官子任务。Algo / 集成层比例 ~30/70 是 M3.x 系列纯函数比例最低的子任务——纯 algo 部分（throttle 状态机 + 生命周期决策）本子任务做，scriptJob 真实触发推 **M1.5 mayapy 集成测试**。**0 行 C++ + 0 行 core.py 改动**——M3.1 / M3.6 / M3.5 / **M3.4 四连**。

### M3.4.F1-F4 — Verify-before-design 第 5 次使用

| # | 验证项 | 结论 | 决议影响 |
|---|---|---|---|
| **F1** | `cmds.scriptJob` 项目里现有用法 | ❌ 无 —— M3.4 首次引入 | 算法层 mock 测试 + 真实集成推 M1.5 |
| **F2** | `controller.update_pose` 是否复用 | ✅ —— [controller.py:969](modules/RBFtools/scripts/RBFtools/controller.py:969) 已存在 | (D.2) Live Edit `live_edit_apply_inputs` 是 thin wrapper，0 新接口 |
| **F3** | scriptJob `parent=` 用的窗口对象名 | ✅ —— `constants.WINDOW_OBJECT = "RBFToolsMainWindow"` | scriptJob 自动随窗口关闭 cleanup |
| **F4** | "current pose row" 是否已有 accessor | ❌ —— controller / model 都没有 | (D.2) widget 内通过 `selectionModel().currentChanged` 独立跟踪 |

**F4 是真正驱动决议的发现**——其他 3 个是确认现成路径可用。比例 25% F 真正驱动 vs 75% F 确认复用 —— 反映 M3.4 是 M3 系列最依赖现有基础设施的子任务，恰好契合"复用 > 新建"四连。

### M3.4.1 — 决议日志（9 项 + 2 加固 + (D) forward-compat caveat）

| # | 分叉 | 选项 | 选定理由 |
|---|---|---|---|
| (A) | 监听对象 | **A.1** 仅 driver | 红线锁死，避免与 RBF compute 死循环 |
| (B) | Throttle 策略 | **B.3** hybrid leading+trailing | 响应性 + 终态准确 |
| (C) | scriptJob 粒度 | **C.2** per-driver-attr | 精确监听 |
| (D) | active row 跟踪 | **D.2** widget 内独立 | MVC 风格一致；F4 触发分叉 |
| (E) | 空 driver_attrs 行为 | **E.1** 拒绝 + warning | fail fast |
| (F) | UI 入口 | **F.1** 仅 ToolsSection | toggle 是 per-node 状态 |
| (G) | Toggle off flush | **G.1** 强制 flush pending | 不丢用户最后一次拖动 |
| (H) | Throttle 时长 | **H.1** 100ms 写死 | M5 再考虑暴露 |
| (I) | summary 文档处理 | **I.2** 重写为 M3 收官 summary | M3 主体收官值得整理 |
| 加固 1 | T_LIVE_NO_DRIVEN_LISTEN | source-scan core_live.py | 防止误改加 driven 监听导致死循环 |
| 加固 2 | T_THROTTLE_TIME_INJECTION | source-scan core_live.py | throttle 纯函数 time 注入可测 |
| (D) caveat | controller 接口提升预留 | M5 monitoring 演化路径 | widget→controller 迁移直接可行 |

### M3.4.2 — Throttle 状态机（hybrid leading+trailing）

```python
# core_live.py — pure functions; no maya.cmds; time injected by caller

ThrottleState:
    last_emit_ts          # 0.0 = "no emit yet"
    pending_event_ts      # None or float — set when in-window event arrives
    throttle_sec          # 0.1 by default

should_emit_now(state, now_ts) -> (emit_now, schedule_trailing)
    ├── if last_emit_ts == 0 OR (now - last) >= throttle_sec
    │       → leading emit; advance state.last_emit_ts
    │       return (True, False)
    └── else
            → record state.pending_event_ts = now
            return (False, True)        # caller starts trailing timer

trailing_due(state, now_ts) -> bool
    pending_event_ts is not None AND (now - last_emit_ts) >= throttle_sec

mark_emitted(state, now_ts)
    state.last_emit_ts = now_ts
    state.pending_event_ts = None

flush_pending(state, now_ts) -> bool
    return pending_event_ts is not None    # caller fires + reset
```

### M3.4.3 — scriptJob 生命周期清单

| 时点 | 动作 | 安全网 |
|---|---|---|
| toggle on（driver_attrs 非空） | per-attr `cmds.scriptJob(attributeChange=..., parent=WINDOW_OBJECT)` | parent= 自动 cleanup |
| toggle on（driver_attrs 空） | warning + 不注册 + 复位 checkbox（E.1）| `_fail_to_idle` blockSignals 防回弹 |
| toggle off | flush_pending → 逐个 kill + clear list | try/except 包裹 kill |
| node change（toggle on 期间） | `planned_transition_on_node_change` 决策 → flush + kill + re-register | `editorLoaded` signal 触发 |
| pose row 切换 | active_row 更新；jobs 不动 | `selectionModel().currentChanged` |
| window close | Maya 自动 cleanup（parent=）| try/except 吃 dead-id |
| Maya scene new | scriptJob 自动失效 | next callback fail 被吞 |

### M3.4.4 — Driver-Only 红线（T_LIVE_NO_DRIVEN_LISTEN PERMANENT）

```
Live Edit MUST NEVER listen on driven_node attributes.
Listening on driven would create a feedback loop:
  RBF compute writes driven attr
   → attributeChange triggers throttle
   → throttle re-writes inputs
   → compute again
   → ∞ loop / infinite redraw

Permanent guard T_LIVE_NO_DRIVEN_LISTEN source-scans
core_live.py executable body (docstrings + comments stripped)
for any leakage of driven-side identifiers:
  read_driven_info / driven_node / driven_attrs
```

T_LIVE_NO_DRIVEN_LISTEN 是**第 13 条 PERMANENT GUARD**。

### M3.4.5 — Time-Injection 纯函数契约（T_THROTTLE_TIME_INJECTION PERMANENT）

```
Throttle pure functions accept now_ts as a parameter; they
MUST NOT call time.time() / time.monotonic() / datetime.now()
directly. Caller (LiveEditWidget) is the only real-time source.

Permanent guard T_THROTTLE_TIME_INJECTION source-scans
core_live.py executable body for those forbidden calls.

Rationale:
  - Tests can advance "time" deterministically via injected
    floats (no time.sleep, no freezegun, no mock.patch on time)
  - Subtle ordering bugs from time drift cannot accumulate
  - LiveEditWidget reads time.monotonic() at the Qt-event
    boundary — that's the canonical real-time source.
```

T_THROTTLE_TIME_INJECTION 是**第 14 条 PERMANENT GUARD**。

### M3.4.6 — (D) Forward-Compat for active-row promotion

```
M3.4 active-row tracking lives inside LiveEditWidget (D.2):
the widget subscribes to the pose table's QSelectionModel
currentChanged signal directly.

If a future sub-task (e.g. M5 performance monitoring) needs
controller-level access to "currently active pose row", the
extraction is straightforward:
  1. Promote the QSelectionModel listener from LiveEditWidget
     to MainController as currentPoseRow property +
     currentPoseRowChanged signal.
  2. LiveEditWidget switches its subscription target from the
     view's selection model to controller.currentPoseRowChanged.
  3. No core.py changes; no public API removal.

M3.4's design does NOT preclude this; it merely defers it.
Keeping active-row tracking inside the widget today preserves
the M3 "复用 > 新建" minimalism (no controller surface area
expanded for a single consumer).
```

### M3.4.7 — M1.5 Spillover Scope（**锁定**）

```
M3.4 ships:
  - core_live.py pure throttle state machine
  - LiveEditController orchestrating cmds.scriptJob lifecycle
    via mocked-testable code paths (T1-T9 cover state machine,
    can_toggle_on/off, planned_transition_on_node_change)
  - Tools panel toggle widget (spillover §3 second consumer)
  - 100% mock test coverage of pure functions + state transitions

M1.5 mayapy integration tests will close the loop on:
  - cmds.scriptJob attributeChange callback actually firing on
    Maya plug change
  - parent=WINDOW_OBJECT auto-cleanup on window close
  - throttle behaviour under real viewport drag (artist hand on
    manipulator at 60 FPS)
  - end-to-end: viewport drag → throttle → update_pose → model
    refresh → table view repaint

Forward-compat contract:
  core_live.py pure-function API (ThrottleState /
  should_emit_now / trailing_due / mark_emitted / flush_pending /
  can_toggle_on / can_toggle_off /
  planned_transition_on_node_change) is locked. M1.5 wraps
  mayapy integration around the existing shape; never
  re-implements logic that already lives in core_live.
```

### M3.4.8 — 改动清单

| 文件 | 改动 |
|---|---|
| `core_live.py` | **新建** ~190 行（ThrottleState + 5 pure throttle helpers + LiveEditState + 3 lifecycle decisions + F1-F4 docstring + 双契约文档）|
| `core.py` | **0 改动**（M3.1 / M3.6 / M3.5 / M3.4 四连零核心改动）|
| `controller.py` | +`live_edit_apply_inputs` thin wrapper ~20 行 |
| `ui/main_window.py` | +`add_tools_panel_widget("live_edit_toggle", ...)` + LiveEditWidget wiring ~7 行 |
| `ui/widgets/live_edit_widget.py` | **新建** ~205 行（QCheckBox + status label + active row tracking + scriptJob orchestration + QTimer trailing tick）|
| `ui/i18n.py` | +6 keys × 2 langs = 12 行 |
| `tests/test_m3_4_live_edit.py` | **新建** ~395 行（14 测试类，**25 子测试**）|
| `docs/.../addendum_20260424.md` | §M3.4 + M1.5 spillover + (D) forward-compat + §M3.5.6.M3.4-validation 追加 ~180 行 |
| `docs/.../milestone_3_summary.md` | **重写为 M3 收官 summary** ~190 行（M2 模式扩充） |

**总：~1200 行**（含测试 + addendum + summary 重写）；**生产代码 ~290 行 < 800**。

### M3.4.9 — 测试矩阵（25 子测试）

| T# | 名称 | 子测 |
|---|---|---|
| T1 | ThrottleState 默认 + reset | 2 |
| T2 | should_emit_now 首事件 leading | 1 |
| T3 | should_emit_now 窗内事件 defer | 1 |
| T4 | should_emit_now 窗外事件 leading | 1 |
| T5 | trailing_due / mark_emitted | 4 |
| T6 | flush_pending | 2 |
| T7 | can_toggle_on（IDLE+attrs / E.1 / LISTENING）| 3 |
| T8 | can_toggle_off | 2 |
| T9 | planned_transition_on_node_change 三分支 | 3 |
| T10 | controller.live_edit_apply_inputs guards | 2 |
| T11 | ToolsSection wiring（spillover §3 第二消费者）| 1 |
| T12 | i18n 6 keys EN/CN parity | 1 |
| **T_LIVE_NO_DRIVEN_LISTEN** | **PERMANENT** — core_live 不含 driven 关键字 | 1 |
| **T_THROTTLE_TIME_INJECTION** | **PERMANENT** — core_live 不含 time 直接调用 | 1 |

合计 **14 测试类，25 子测试**。**总测试数：399 + 25 = 424 / 424**。

### M3.4.10 — 零回归

- `core.py` **0 改动** —— **第 4 次连续零核心改动**（M3.1 / M3.6 / M3.5 / M3.4 四连）
- spillover §3 第二真实消费者无 API 修改需求 —— M3.5 forward-compat 契约成立
- ProfileWidget / LiveEditWidget 共存于 ToolsSection（懒创建 + 持久存在 T_TOOLS_SECTION_PERSISTS 守护）
- `controller.editorLoaded` signal 既有，新增 LiveEditWidget 订阅不破坏 ProfileWidget 订阅
- 全量回归：399 + 25 = **424 / 424** 通过

### M3.4.11 — Non-goals

- ❌ 监听 driven_node（红线 — 死循环风险）
- ❌ 自动新增 pose row（仅 update 当前 active row）
- ❌ Live Edit 触发 RBF 重训（仅 update model；用户手动 Apply 触发训练）
- ❌ 多节点同时 Live Edit（仅当前 RBFtools 节点）
- ❌ Throttle 时长用户暴露（默认 100ms 写死，M5 再考虑暴露）
- ❌ 真实 mayapy 集成测试（推 M1.5）
- ❌ scriptJob 真实触发回归（推 M1.5）
- ❌ 单 attr 监听粒度选择（per-attr 写死，all wired drivers）
- ❌ active row 提升到 controller（M5 监控触发时再做）

### M3.4.12 — 红线确认

- ✅ 沿用 M3 / M3.0 / M3.2 / M3.7 / M3.3 / M3.1 / M3.6 / M3.5 全部红线
- ✅ Live Edit **仅 driver → inputs**（**T_LIVE_NO_DRIVEN_LISTEN** PERMANENT）
- ✅ scriptJob **必须** `parent=WINDOW_OBJECT` + 显式 kill 双重清理
- ✅ Throttle **必须**纯函数可测（**T_THROTTLE_TIME_INJECTION** PERMANENT）
- ✅ Toggle off 必须 flush pending（不丢用户最后一次拖动）
- ✅ **0 行 core.py 改动**（**M3.1 / M3.6 / M3.5 / M3.4 四连**）
- ✅ **0 行 C++ 改动**（M3 全程零 C++）
- ✅ scriptJob 真实集成测试推 M1.5（addendum §M3.4.7 明文锁定）
- ✅ Spillover §3 第二消费者无 API 变更需求（§M3.5.6.M3.4-validation 验证记录）
- ✅ (D) forward-compat 备注 active row 提升路径（§M3.4.6）

---

## §M2.5 — Per-Pose SwingTwist Cache (Constitutional Stress Test)

Milestone 3 收官后的 forward-compat 闭环子任务。M2.5 把 v5 PART C.2.7 + addendum §M2.4b 末尾"性能优化 schema 追加"承诺落地。**核心交付不是 5 个新字段——是 v5 宪法层（14→15 PERMANENT GUARDS）首次真实演化压力测试通过的证据**。

### M2.5.F1-F4 — Verify-before-design 第 6 次使用

| # | 验证项 | 结论 |
|---|---|---|
| **F1** | `_reference_impl.decompose_swing_twist` Python mirror 是否存在？ | ✅ —— [_reference_impl.py:529](modules/RBFtools/tests/_reference_impl.py:529)。M2.1b 已落地。**此次仅 schema 改动不消费**（compute() 实际填充推 M2.5b/M5）|
| **F2** | C++ source 是否已有 5 字段前置声明？ | ❌ —— `grep` source 树 0 命中 `poseSwingQuat` 等。M2.5 是**全新引入** |
| **F3** | `clear_node_data` 如何清理 poses 多实例？ | ✅ —— `removeMultiInstance("shape.poses[idx]", b=True)` 在 compound multi 上**自动级联清子 compound**。新 cache compound 随 poses 清，**`clear_node_data` 0 行改动** |
| **F4** | `apply_poses` 流水线注入点？ | ✅ —— step 3 插在 `_write_pose_to_node`（step 2）之后、`capture_output_baselines`（→step 4）之前 |

**F3 直接驱动 scope 缩减**：从理论 ~250 行压到实际 ~125 行生产代码——核查模式驱动 scope 缩减的最佳例证。

### M2.5.1 — 战略价值澄清（M3 红线 vs M2.5 红线）

- M3 期间确立的 **"0 C++ + 0 core.py 四连"** 是 **M3-milestone-specific** 红线 —— v5 设计文档明文 M3 是 Python-only milestone
- **M2.5 不属于 M3**，按 v5 PART C.2.7 它本身就是 C++ schema 改动子任务
- M2.5 真红线：
  - ✅ **`SCHEMA_VERSION` 不变** = `"rbftools.v5.m3"`（T0 守护稳定）
  - ✅ **`core_json.py` 0 行改动**（**核心宪法证据** — `git diff` 实测为空）
  - ✅ **缓存字段不进 JSON export**（**T_M2_5_CACHE_NOT_IN_SCHEMA** 第 15 条 PERMANENT GUARD，扫**三个文件**）

### M2.5.2 — Schema 草案（落地）

```cpp
// source/RBFtools.h additions:
static MObject poseSwingTwistCache;       // compound child of poses[p]
  static MObject poseSwingQuat;             // double4, default (0,0,0,1)
  static MObject poseTwistAngle;            // double,  default 0.0
  static MObject poseSwingWeight;           // double,  default 1.0
  static MObject poseTwistWeight;           // double,  default 1.0
  static MObject poseSigma;                 // double,  default -1.0 (sentinel)
```

**包装 compound** 与 M2.3 `poseLocalTransform` 嵌套模式一致；命名空间清晰 + Channel Box 折叠友好。

### M2.5.3 — `poseSigma == -1.0` 双语义合并（C.3 决议）

```
poseSigma == -1.0  ⇒  cache NOT populated AND use global radius
poseSigma >= 0     ⇒  cache populated AND per-pose sigma override
                       (v5 PART E.10 forward-compat)
```

两个语义在"cache 未填充时也用 global radius"前提下一致——简洁且自洽。compute() 消费者（M2.5b / M5 实施时）单一 `if poseSigma == -1.0` 分支同时处理两件事。

### M2.5.4 — Cache vs Schema Boundary Contract（**核心宪法决策**）

```
M2.5 Cache vs Schema Boundary Contract:

  Definition:
    poseSwingTwistCache.* fields are RUNTIME PERFORMANCE
    OPTIMIZATION cache values, derived from poses[p].poseInput[]
    via decompose_swing_twist (see _reference_impl.py:529).

  NOT part of the v5 JSON schema:
    - SCHEMA_VERSION remains "rbftools.v5.m3"
    - _ATTR_NAME_TO_JSON_KEY does not gain new entries
    - EXPECTED_NODE_DICT_KEYS / EXPECTED_SETTINGS_KEYS unchanged
    - core_json.node_to_dict does not read cache fields
    - core_json.dict_to_node does not write cache fields

  Rebuild path on import:
    JSON import → core_json.dict_to_node → wires + writes
    poseInput[] / poseValue[] / baselines / poseLocalTransform →
    user-triggered (or auto via M3.6) Apply →
    write_pose_swing_twist_cache writes default sentinel state →
    (M2.5b/M5 future consumer populates real values).

  Why this is the correct boundary:
    - Cache is DERIVED state, not source-of-truth state
    - Bumping SCHEMA_VERSION for derived state would create false
      coupling between disk format and runtime perf strategy
    - Future cache-strategy revisions (e.g. M5 SIMD changes)
      would otherwise force JSON migrations for unchanged
      semantic content

  Enforcement:
    T_M2_5_CACHE_NOT_IN_SCHEMA PERMANENT GUARD source-scans
    THREE files for any cache field name leakage:
      core_json.py    (SCHEMA layer)
      core_mirror.py  (would copy derived state)
      core_alias.py   (would expose to channel box, violating G.2)
```

### M2.5.5 — Implementation Scope (M2.5 vs M2.5b/M5)

**M2.5 ships:**
- C++ schema additions (compound + 5 children + addAttribute table) — `source/RBFtools.{h,cpp}` ~65 lines
- Python `core.write_pose_swing_twist_cache` — writes **default sentinel state** for every pose
- Python `core.read_pose_swing_twist_cache` — read-back helper for future Profiler / M5 perf analysis
- `apply_poses` step 3 integration (between pose write and baseline capture)
- T_M2_5_CACHE_NOT_IN_SCHEMA permanent guard (15th)

**M2.5b / M5 deferred (forward-compat):**
- C++ compute() consumer reading cache via `poseSigma != -1.0` sentinel
- Python populating real decomposition values (currently writes sentinel = unpopulated)
- Real benchmark data replacing the conceptual perf numbers (paired with §M3.5 `_K_*` constants)

The constitutional value (schema boundary + 14 → 15 guards holding under演化 pressure) is **fully delivered by schema-only**. The actual perf optimization is a clean drop-in once mayapy benchmark is available — `poseSigma == -1.0` sentinel makes consumer addition non-breaking.

### M2.5.6 — 改动清单

| 文件 | 改动 |
|---|---|
| `source/RBFtools.h` | +5 MObject declarations + compound 父结构 ~15 行 |
| `source/RBFtools.cpp` | +5 attribute() create blocks + compound build + 6 addAttribute calls ~50 行 |
| `core.py` | +`write_pose_swing_twist_cache` (~30 行) + `read_pose_swing_twist_cache` (~25 行) + `apply_poses` step 3 注入 (~10 行) ~65 行 |
| `core_json.py` | **0 改动** —— 核心宪法证据；T_M2_5_CACHE_NOT_IN_SCHEMA 守护扫此文件 |
| `core_mirror.py` | **0 改动** —— Mirror 不复制 cache（F.2 决议；T_M2_5_CACHE_NOT_IN_SCHEMA 同样守护）|
| `core_alias.py` | **0 改动** —— Alias 不暴露 cache（G.2 决议；同上）|
| `tests/test_m2_5_cache.py` | **新建** ~250 行（5 测试类 + 2 PERMANENT GUARD 类）|
| `docs/.../addendum_20260424.md` | §M2.5 全节 + boundary contract + F1-F4 ~150 行 |

**总：~530 行**（含测试 + addendum）；**生产代码 ~130 行**（C++ 65 + Python 65；core_json/mirror/alias 全零）。

### M2.5.7 — 测试矩阵

| T# | 名称 | 子测 |
|---|---|---|
| T1 | write_cache 5 child fields per pose | 1 |
| T2 | sentinel poseSigma=-1.0 | 1 |
| T3 | apply_poses pipeline insertion order + try/except | 2 |
| T4 | read_cache dict shape | 1 |
| T5 | read_cache defensive (missing node) | 1 |
| **T_M2_5_CACHE_NOT_IN_SCHEMA** | **PERMANENT** — 6 forbidden × 3 files = 18 scan points (core_json + core_mirror + core_alias) | 3 |
| **T_CoreJsonDiffEmpty** | **PERMANENT** — SCHEMA_VERSION still "rbftools.v5.m3" | 1 |

合计 **7 测试类，10 子测试**。**总测试数：424 + 10 = 434 / 434**。

### M2.5.8 — 宪法层压力测试通过证据（**M2.5 留给后续 milestone 的最大遗产**）

M2.5 实施完成后实测：

| 守护 | 状态 |
|---|---|
| **T0** SCHEMA_VERSION 不变量 | ✅ `"rbftools.v5.m3"` 保持不变 |
| **T1b** `_ATTR_NAME_TO_JSON_KEY` bijection | ✅ 不动（未加新映射）|
| **T_M3_3_SCHEMA_FIELDS** frozen sets | ✅ 不动（EXPECTED_*_KEYS 不变）|
| **T_M2_5_CACHE_NOT_IN_SCHEMA**（**新增第 15 条**）| ✅ core_json + core_mirror + core_alias 三文件 0 命中 |
| `core_json.py` `git diff` | ✅ **空**（构造性证据）|

**结论**：v5 宪法层在"看似该 bump SCHEMA_VERSION"的真实场景下**仍然不需要 bump**。**"不 bump 比 bump 更难做对"——bump 简单（加版本字符串就完事），不 bump 需要严格的"derived vs source-of-truth"边界判断**。

未来 M4 / M4.5 / M5 加新字段时，本节是决策范式：
- **Source-of-truth state** → bump SCHEMA_VERSION + 多版本 reader（hard）
- **Derived runtime state** → 不进 JSON + source-scan 守护（soft，但需精准边界判断）

### M2.5.9 — M1.5 Forward-Compat Caveat

```
M1.5 mayapy integration tests will close the loop on:
  - C++ schema changes compile cleanly under Maya 2024+ devkit
  - poseSwingTwistCache compound loads on existing v4/v5 nodes
    without data corruption (forward compat: nodes saved before
    M2.5 should load with default cache values)
  - decompose_swing_twist Python mirror (_reference_impl.py:529)
    matches C++ decomposeSwingTwist byte-for-byte across the
    full unit-quaternion sphere (M2.1b verification regression)

M2.5b deferred forward-compat (depends on M1.5):
  - C++ compute() reads poseSigma sentinel and chooses cache vs
    live decompose
  - Python write_pose_swing_twist_cache populates real values
    (currently writes sentinel = unpopulated)
  - Real benchmark replaces conceptual _K_CHOL etc constants in
    core_profile.py (§M3.5.F2)
```

### M2.5.10 — Non-goals

- ❌ Cache 进 JSON export（路径 B 锁定 —— T_M2_5_CACHE_NOT_IN_SCHEMA）
- ❌ SCHEMA_VERSION bump（路径 B 核心 —— T0 守护稳定）
- ❌ Cache 在 Channel Box 暴露用户编辑（runtime metadata）
- ❌ Per-pose `poseSigma` UI 控件（schema 占位 forward-compat 给 v5 PART E.10；UI 推 M5）
- ❌ M3.x 工具感知 cache（cache 是 Apply 流水线内部细节）
- ❌ Live Edit 触发 cache 重写（Apply 兜底）
- ❌ Cache 一致性主动校验（cache miss → fallback 兜底）
- ❌ **C++ compute() 真实消费 cache**（推 M2.5b / M5；M1.5 mayapy 验证后启动）
- ❌ **Python 写入真实 decompose 值**（推 M2.5b / M5）

### M2.5.11 — 红线确认（M2.5 全程）

- ✅ **`SCHEMA_VERSION` 不变** = `"rbftools.v5.m3"`（T0 守护稳定）
- ✅ **`core_json.py` 0 行改动**（核心宪法证据 — `git diff` 实测）
- ✅ **缓存字段不进 JSON export**（T_M2_5_CACHE_NOT_IN_SCHEMA 第 15 条 PERMANENT GUARD）
- ✅ Apply 时自动初始化缓存（与 M2.3 模式一致）
- ✅ Import 时不写缓存（Apply 时自动重建）
- ✅ Mirror 时不复制缓存（cache 是派生量；F.2 决议）
- ✅ Pruner / Profiler / Live Edit / Auto-neutral 不感知缓存（all 0 行改动）
- ✅ T_M2_5_CACHE_NOT_IN_SCHEMA 守护扫**三个文件**（core_json + core_mirror + core_alias）
- ✅ M2.5 是 M2 sub-task，C++ 改动允许但**仅限 schema 注册**——compute() 消费推 M2.5b/M5
- ✅ M2.5 commit 不做 mayapy 编译验证（无环境）；M1.5 时首批回归

---

## §M1.5-conftest — Dual-Environment Test Adaptation

> **⚠ Maya version compatibility caveat**: The dual-environment
> support documented below is verified ONLY on **Maya 2025 +
> Python 3.11.4 + PySide6 6.5.3**. Maya 2022 (Python 3.7 + PySide2)
> compatibility is **deferred to M5**; until then assume mayapy
> testing only passes on Maya 2025. This caveat is repeated at the
> top of `tests/README.md` for user-side discoverability.

This sub-task is the **environment gate** for the rest of M1.5 +
M4.5. By making `conftest.py` aware of whether the current
interpreter is mayapy or pure Python, the entire C++ change
risk surface for downstream work collapses: mayapy integration
verification becomes routinely reachable.

**Scope:** ~30 lines `conftest.py` + ~150 lines new test file +
24 class-level `skipIf` decorators across 8 existing test files +
~70 lines docs. **Smallest sub-task in v5; highest strategic
leverage** — verify-before-design 6th use of the canonical pattern.

### M1.5-conftest.F1-F4 — Verify-before-design 7th use

| # | Verified | Outcome |
|---|---|---|
| **F1** | mayapy detection — what's the most reliable judgement? | Two-condition: `sys.executable` basename starts with `mayapy` (cross-platform — no `.exe`-only assumption) **AND** `import maya.cmds` succeeds. Single-condition probes have known false positives (alias rebinding) or false negatives (mocked module masquerades as real). |
| **F2** | Which modules are real under mayapy 2025? | All 12 mock targets are real: `maya` / `maya.cmds` / `maya.api.OpenMaya` / `maya.OpenMayaUI` / `maya.utils` / `PySide6 6.5.3` / `PySide6.QtCore` / `PySide6.QtWidgets` / `PySide6.QtGui` / `shiboken6`. (`shiboken2` / `PySide2` not present — Maya 2022 only.) |
| **F3** | `AttributeError: __name__` root cause | PySide6 import installs `shibokensupport.feature.feature_imported` as `__import__` hook → subsequent `import maya.cmds` (mocked) triggers hook → hook accesses `module.__name__` → `MagicMock(name='maya.cmds')` defines mock's repr name not module's `__name__` attr → `__getattr__` raises `AttributeError('__name__')` for dunders. **Structural fix:** under mayapy, skip mock entirely; real maya.cmds exposes `__name__` natively. |
| **F4** | Existing conftest mock-target enumeration | 12 `sys.modules` mock points + 1 PySide minimal shim (real-class subset for widget metaclass-safe inheritance, addendum §M2.4a). Pure-Python branch keeps full framework; mayapy branch skips both. |

### M1.5-conftest.1 — Decision log (9 items + 3 reinforcements)

| # | Decision point | Choice | Rationale |
|---|---|---|---|
| (A) | Detection judgement | A.3 — basename `mayapy` + `import maya.cmds` two-condition | F1 verified |
| (B) | Mock skip granularity under mayapy | B.3 — all 12 module-level mocks skipped | Half-mock is more dangerous than no-mock (PySide metaclass trap from §M2.4a teaches us) |
| (C) | mayapy fail handling | C.3 — empirically classify each fail / error after first run | Avoids pre-set whitelist that would mask real regressions |
| (D) | `skipIf` granularity | D.2 — class-level | Class-level shares fixtures (`setUp` / `_reset_cmds`); method-level would leave half-fixtures dangling |
| (E) | T_CONFTEST_DUAL_ENV scope | E.2 — detection symbol + mock target list preservation | Reinforcement 1 below adds test-count baseline; reinforcement 2 adds maya.standalone forbidance |
| (F) | Maya 2022 compat | F.2 — defer to M5 | Caveat block at top of §M1.5-conftest + tests/README.md |
| **Reinforcement 1** | T_CONFTEST_DUAL_ENV invariant 4 | Pure-Python collected test count ≥ baseline | Catches silent skip drift from over-broad refactor |
| **Reinforcement 2** | mayapy fail list transparent disclosure | Empirical baseline log dated 2026-04-26 in this section | Future Maya / mayapy upgrades regression compare against logged baseline |
| **Reinforcement 3** | Maya 2022 caveat visibility | Addendum top + tests/README.md top | Prevents user-side time-waste on unsupported version |

### M1.5-conftest.2 — `_REAL_MAYA` detection

```python
def _has_real_maya():
    """True iff running under real mayapy AND maya.cmds importable.

    Two conditions both required. MUST run BEFORE any mock install
    (else condition 2 succeeds against our own mock).
    """
    base = os.path.basename(sys.executable).lower()
    if not base.startswith("mayapy"):
        return False
    try:
        import maya.cmds  # noqa: F401
        return True
    except ImportError:
        return False

_REAL_MAYA = _has_real_maya()
```

Branch wiring at the bottom of conftest:

```python
_install_package_path()    # always — pure sys.path; no maya dep

if not _REAL_MAYA:
    _install_maya_mocks()       # 6 maya.* mock targets
    _install_pyside_mocks()     # 6 PySide / shiboken mock targets
# else: real mayapy — mocks skipped; real modules resolve naturally
```

### M1.5-conftest.3 — T_CONFTEST_DUAL_ENV (PERMANENT GUARD #17)

`tests/test_conftest_dual_env.py` enforces 6 invariants:

1. `_REAL_MAYA` symbol exists (module-level `bool`)
2. Two-condition detection code present (basename + import probe)
3. All 12 mock-target sys.modules names listed in conftest source
4. Pure-Python collected test count ≥ `_PURE_PYTHON_BASELINE` (440 as of M2.5 commit `c866604` + 6 dual-env subtests)
5. mayapy branch must NOT call `maya.standalone.initialize()` (M1.5 spillover, not this sub-task)
6. Branch behaviour consistent: under mayapy `sys.modules['maya.cmds']` is NOT a MagicMock; under pure Python it IS

Source-text guards strip docstrings + comments before scanning so legitimate documentation can name forbidden symbols (same pattern as M3.4 / M3.5 / M3.6).

### M1.5-conftest.4 — Skip class registry (24 classes across 8 files)

mayapy실측 fail / error after F3 fix all collapsed to one root: `cmds.reset_mock()` and `mock.patch('maya.cmds.<x>')` require `cmds` to be a MagicMock. Real `maya.cmds` is a Python module without `reset_mock`.

Class-level `@unittest.skipIf(conftest._REAL_MAYA, ...)` applied to:

| File | Classes |
|---|---|
| `test_m2_4a_core.py` | T0a_FullWrite / T0b_MidWriteFailure / T0c_EmptyList / T0d_LengthCap / T0e_TypeGuard |
| `test_m2_5_cache.py` | T1_WriteCacheChildren / T2_SentinelSigma / T4_ReadCacheShape |
| `test_m3_0_infrastructure.py` | T1_ShouldShowConfirmDialog / T3_ResetAllSkipConfirms / T6_SelectRigForNode |
| `test_m3_1_prune.py` | T6_ExecutePruneSequencing / T12_InvalidGroupPreservesStart |
| `test_m3_2_mirror.py` | T_ROLLBACK |
| `test_m3_3_jsonio.py` | T3_DictToNode / T4_DryRunValidation / T5_DryRunMultiNode / T9_PoseLocalTransformBypass |
| `test_m3_6_neutral.py` | T4_AddNeutralSampleSequencing / T5_AutoTriggerGating |
| `test_m3_7_alias.py` | T5_ClearManagedPreservesUser / T6_ApplyAliasesAPIPaths / T7_ReadAliases / T8_ConflictFallback |

**Total:** 24 classes (44 individual subtests after class expansion). Skip reason string is uniform: `"mock-dependent (cmds.reset_mock / mock.patch on cmds.*); real maya.cmds is not a MagicMock under mayapy"`.

### M1.5-conftest.5 — Empirical baseline log (2026-04-26)

```
Baseline: post-M2.5 commit c866604

Pure-Python (python -m unittest discover):
  Ran 440 tests in 0.245s — OK
  (was 434 before this sub-task; +6 from T_CONFTEST_DUAL_ENV)

mayapy 2025 (mayapy.exe -m unittest discover):
  Ran 440 tests in 0.705s — OK (skipped=44)
  Pass: 396  /  Skip: 44  /  Fail: 0  /  Error: 0
  All 44 skips are class-level mock-dependent skips listed above.
```

Future mayapy / Maya version upgrades regression compare against this log. New skip categories (e.g. Maya 2025.x → 2026 API changes) MUST be enumerated here AND in §M1.5-conftest.4 with rationale; new fails MUST be fixed or explicitly skipped before merge.

### M1.5-conftest.6 — Forward-compat for M1.5 actual integration tests

This sub-task **does NOT**:

- Call `maya.standalone.initialize()` — invariant 5 forbids it
- Load any `.mll` plugin — no compiled RBFtools.mll exists yet
- Run `node.eval()` / real `cmds.scriptJob` triggering / real `cmds.aliasAttr` on multi-instance plugs

Those are the **3 spillover items** that M1.5 will tackle:

1. M2.5b — C++ compute() consumer reading `poseSigma` sentinel
2. M3.4 — scriptJob real attributeChange triggering + `parent=` cleanup
3. M2.5 — `decompose_swing_twist` Python ↔ C++ byte-for-byte regression

The M1.5 milestone will introduce a per-test `maya.standalone` fixture (NOT a conftest-level init — that would slow every pure-Python sweep). T_CONFTEST_DUAL_ENV invariant 5 enforces this boundary.

### M1.5-conftest.7 — Change list

| File | Change |
|---|---|
| `tests/conftest.py` | +`_has_real_maya()` + `_REAL_MAYA` constant + branch wiring + dual-env docstring (~80 lines including doc) |
| `tests/test_conftest_dual_env.py` | **New** ~150 lines — T_CONFTEST_DUAL_ENV with 6 sub-checks |
| `tests/test_m2_4a_core.py` | +5 class-level `@skipIf` decorators |
| `tests/test_m2_5_cache.py` | +3 class-level `@skipIf` decorators |
| `tests/test_m3_0_infrastructure.py` | +3 class-level `@skipIf` decorators |
| `tests/test_m3_1_prune.py` | +2 class-level `@skipIf` decorators |
| `tests/test_m3_2_mirror.py` | +1 class-level `@skipIf` decorator |
| `tests/test_m3_3_jsonio.py` | +4 class-level `@skipIf` decorators |
| `tests/test_m3_6_neutral.py` | +2 class-level `@skipIf` decorators |
| `tests/test_m3_7_alias.py` | +4 class-level `@skipIf` decorators |
| `tests/README.md` | +Dual-environment运行 section + Maya 2022 caveat block |
| `addendum_20260424.md` | §M1.5-conftest (this section) ~150 lines |

**Total:** ~330 lines (zero business code; tests + docs + 24 decorators).

### M1.5-conftest.8 — Permanent guards updated to 17

Project-wide PERMANENT GUARDS now total **17**:

```
Schema integrity        — T0, T1b, T_M3_3_SCHEMA_FIELDS, T_FLOAT_ROUND_TRIP,
                          T_M2_5_CACHE_NOT_IN_SCHEMA,
                          T_M2_5_CORE_JSON_DIFF_EMPTY
Read-only invariants    — T16, T_ANALYSE_READ_ONLY,
                          T_PROFILE_READ_ONLY, T_LIVE_NO_DRIVEN_LISTEN
Algorithmic correctness — T_QUAT_GROUP_SHIFT, T_NEUTRAL_QUAT_W,
                          T_THROTTLE_TIME_INJECTION,
                          T_MANAGED_ALIAS_DETECT
UI contracts            — T_CAVEAT_VISIBLE, T_TOOLS_SECTION_PERSISTS
Test infrastructure     — T_CONFTEST_DUAL_ENV    ← NEW (#17)
```

### M1.5-conftest.9 — Red-line confirmations

- ✅ **0 业务代码改动** — `scripts/RBFtools/*.py` 完全未触碰；source 也未触碰
- ✅ **0 C++ 改动** — M3 红线沿用
- ✅ **i18n 永久守护未回退** — `test_i18n_no_hardcoded_strings.py` 在 mayapy 下与纯 Python 下一致通过
- ✅ **Mock target list preserved** — invariant 3 守护
- ✅ **Pure-Python baseline ≥ 440** — invariant 4 守护
- ✅ **No `maya.standalone.initialize()` in conftest** — invariant 5 守护
- ✅ **Class-level `skipIf`** (D.2) — 不允许模块级 / 文件级
- ✅ **Maya 2022 caveat** — addendum top + README top
- ✅ **No spillover work** — M2.5b / M3.4 / M2.5 decompose 推 M1.5

---

## §M1.5.1 — mayapy Fixture Framework + A-class Conversion

> **⚠ scope summary**: 0 C++ / 0 business code / 0 CMakeLists changes.
> Test infrastructure only. **3 spillovers (M2.5b / M3.4 / M2.5
> decompose) all blocked or deferred** — see §M1.5.1.X Blocker
> Matrix below.

### §M1.5.1.F1-F5 — Verify-before-design 8th use (highest-value yet)

F-checks executed BEFORE Step 2 surfaced **two structural blockers**
that together collapsed the original "3 spillover one-shot
regression" scope down to "fixture framework + 5 A-class
conversion". This is the canonical example of why
verify-before-design exists — the alternative was writing
~200 lines of M2.5b regression code before discovering F1.

| F | Verified | Outcome |
|---|---|---|
| **F1** | `.mll` build + Maya 2025 load | **❌ BLOCKER**. `source/build/Release/RBFtools.mll` (Maya 2022 build, dated 2026-04-07, predates M2.5 schema) **fatally crashes Maya 2025 mayapy** on `cmds.loadPlugin` — stack ends in `Shared.dll!TbaseApp::initGeneral`, triggering auto-save dump. Resolution: M1.5.1b (independent sub-task, C++ scope). |
| **F2** | `maya.standalone.initialize()` re-entry | **❌ NOT re-entrant**. Second `initialize()` after `uninitialize()` crashes at the same point. Autodesk-documented one-shot constraint. **Drives (A.3) session-scoped lazy-init**: never call `uninitialize()`; process exit cleans up. |
| **F3** | `_K_*` references in repo | 3 constants in `core_profile.py:62-64` (`1e-9` / `3e-9` / `1e-7`); 6 consumption sites; T_CAVEAT_VISIBLE守护 `_K_CHOL` literal in report. Untouched by M1.5.1 — replacement is M1.5.2 scope. |
| **F4** | scriptJob `attributeChange` headless | **❌ BLOCKER**. Empirical probe: `cmds.scriptJob(attributeChange=[...])` returns `None` (silent registration failure) under standalone; `cmds.setAttr` triggers 0 callbacks; `cmds.refresh(force=True)` does not help. scriptJob lifecycle ties to UI idle queue — **fundamentally untestable in headless mayapy**. M3.4 spillover deferred to M5 GUI long-tail. |
| **F5** | 24 mock-skip class classification | A (M1.5.1 convertible, standalone-friendly) ~7 / B (needs .mll, M1.5.3) ~15 / C (forever mock-only, tests pure-Python logic) ~2. **M1.5.1 commits exactly 5 A-class conversions** (加固 2 lock-list); B and C deferred. |

### §M1.5.1.1 — Decision log (12 + 5 reinforcements)

| # | Decision | Choice | Rationale |
|---|---|---|---|
| (A) | fixture scope | A.3 session-scoped lazy-init | F2 verified |
| (B) | fixture location | B.1 `tests/_mayapy_fixtures.py` (single file, `_` prefix) | unittest discover ignores `_`-prefix modules; T_M1_5_FIXTURE_BOUNDARY guards the boundary |
| (C) | `.mll` load strategy | C.1 do not load (F1 blocker) | Avoids fatal crash; M1.5.1b owns rebuild |
| (D) | M2.5b sentinel replacement | D.3 fully deferred (F1 blocker) | No mayapy verification path → writing without verification is reverse of verify-before-design |
| (E) | M3.4 scriptJob real triggering | E.2 deferred to GUI Maya / long-tail (F4 blocker) | Headless idle queue absent — see加固 3: NO mock workaround allowed |
| (F) | M2.5 decompose Python ↔ C++ | F.3 deferred (same F1 blocker as D) | — |
| (G) | T_M1_5_FIXTURE_BOUNDARY scope | G.3 dual: source-scan + import-graph | 加固 1 lock 4 specific invariants A/B/C/D |
| (H) | mayapy fixture failure semantics | H.3 warning + skipTest | Aligns with M3.4 / M3.5 degradation pattern |
| (I) | A-class conversion granularity | I.2 conservative 5 classes | 加固 2 lock list — see §M1.5.1.4 below |
| (J) | mayapy file naming | J.3 dual-path same file (if/else branch) | Avoids file膨胀; T_CONFTEST_DUAL_ENV invariant 4 (≥ 440) guards count |
| (K) | C++ / CMakeLists changes | **K.1 absolute zero** — `.mll` rebuild is independent sub-task M1.5.1b | Approved separately; even build-config changes are "C++ scope" by the calling-convention contract |
| (L) | commit message format | L.2 detailed F-block log + Blocker Matrix anchor | 加固 4 — addendum §M1.5.1.X cross-reference |
| **R1** | T_M1_5_FIXTURE_BOUNDARY 4 explicit invariants | A (conftest no-fixture-import) + B (fixture no-conftest-token) + C (import-graph) + D (no maya.standalone in conftest) | All 4 PERMANENT, separate `test_PERMANENT_*` methods |
| **R2** | A-class lock list | T1/T3/T6 (m3_0) + T5/T7 (m3_7); explicitly NOT T6_apply / T8 / T4_DryRun | 5 classes only; M1.5.3 reviews remainder |
| **R3** | F4 mock workaround forbidden | 0 hits of `cmds.refresh` / `cmds.idleQueue` / `cmds.evalDeferred` in M1.5.1 test additions | Documented as red line; not permanent (sub-task scope) |
| **R4** | Blocker Matrix in addendum | §M1.5.1.X — forward-compat anchor for downstream sub-tasks | Mechanical consumption format (table) |
| **R5** | Dual-path equivalence assertion | Each A-class subtest has IDENTICAL behaviour assertion across branches (not "two independent tests") | Guards mock vs real-Maya semantic drift |

### §M1.5.1.2 — `_mayapy_fixtures.py` API

```python
# tests/_mayapy_fixtures.py — single file (`_` prefix excludes
# from unittest discovery)

_INITIALIZED = False    # process-global flag

def ensure_maya_standalone():
    """Idempotent session-scoped lazy init. F2 verified one-shot
    constraint — never call uninitialize(). Process exit cleans
    up automatically."""

def skip_if_no_maya(reason="..."):
    """Decorator: skip test/class when not under mayapy. Reads
    conftest._REAL_MAYA via __import__(_CONFTEST_NAME) where
    _CONFTEST_NAME is concatenated to keep the literal token
    out of the executable body (T_M1_5_FIXTURE_BOUNDARY
    invariant B)."""

def require_rbftools_plugin():
    """Stub for M1.5.1b. Currently always raises SkipTest with
    Blocker Matrix reference. Once Maya 2025 .mll exists this
    will load + verify schema."""
```

### §M1.5.1.3 — T_M1_5_FIXTURE_BOUNDARY (PERMANENT GUARD #18)

`tests/test_m1_5_fixture_boundary.py` — 4 sub-checks, each its
own `test_PERMANENT_*` method (加固 1):

| Sub | Invariant | Check |
|---|---|---|
| A | conftest no fixture import | `inspect.getsource(conftest)` (stripped) contains 0 hits of `_mayapy_fixtures` |
| B | fixture no conftest token | `inspect.getsource(_mayapy_fixtures)` (stripped) contains 0 hits of literal `conftest` |
| C | import graph decoupled | `inspect.getfile(conftest)` ends with `conftest.py`; `inspect.getfile(_mayapy_fixtures)` ends with `_mayapy_fixtures.py`; neither path nests under the other |
| D | no maya.standalone in conftest | redundant cross-check from fixture side; T_CONFTEST_DUAL_ENV invariant 5 enforces from env-probe side. Both fail simultaneously on violation for max visibility |

### §M1.5.1.4 — A-class conversion lock list (5 classes, 加固 2)

```
1. T1_ShouldShowConfirmDialog          (test_m3_0_infrastructure.py)
2. T3_ResetAllSkipConfirms             (test_m3_0_infrastructure.py)
3. T6_SelectRigForNode                 (test_m3_0_infrastructure.py)
4. T5_ClearManagedPreservesUser        (test_m3_7_alias.py)
5. T7_ReadAliases                      (test_m3_7_alias.py)
```

**NOT converted** (deferred to M1.5.3 review): `T8_ConflictFallback`,
`T6_ApplyAliasesAPIPaths` (both PASS and FAIL paths),
`T4_DryRunValidation` (7 subtests, read-only). All depend on
`mock.patch` / `cmds.reset_mock` semantics that need either .mll
or RBFtools-shape-specific multi-instance plugs.

Each conversion follows R5 dual-path equivalence: a single
`if conftest._REAL_MAYA: ... else: ...` branch in setUp /
test body, ending in **the same `assert*` statement** under
both branches. mayapy uses real `cmds.optionVar` /
`cmds.aliasAttr` against transient transforms with
fixture-built aliases; pure-Python uses the conftest mock
framework. Same behaviour contract; different observation
mechanism.

### §M1.5.1.5 — Empirical baseline (2026-04-26)

```
Pure-Python (python -m unittest discover):
  Ran 444 tests in 0.331s — OK
  (was 440 pre-M1.5.1; +4 from T_M1_5_FIXTURE_BOUNDARY)

mayapy 2025 (mayapy.exe -m unittest discover):
  Ran 444 tests in 3.281s — OK (skipped=37)
  Pass: 407  /  Skip: 37  /  Fail: 0  /  Error: 0

  Skip count dropped 44 → 37 (-7 subtests across 5 converted
  A-class entries: T1×3, T3×1, T6×1, T5×1, T7×1).

  Remaining 37 skips: ~32 from B-class (need M1.5.1b .mll) +
  ~5 from C-class (forever mock-only) + 1 self-skip
  (T_CONFTEST_DUAL_ENV invariant 4 pure-Python-only check).
  Categorisation table — see §M1.5.1.F5.
```

### §M1.5.1.6 — Project-wide PERMANENT GUARDS now total 18

```
Schema integrity (6)        — T0, T1b, T_M3_3_SCHEMA_FIELDS,
                              T_FLOAT_ROUND_TRIP,
                              T_M2_5_CACHE_NOT_IN_SCHEMA,
                              T_M2_5_CORE_JSON_DIFF_EMPTY
Read-only invariants (4)    — T16, T_ANALYSE_READ_ONLY,
                              T_PROFILE_READ_ONLY,
                              T_LIVE_NO_DRIVEN_LISTEN
Algorithmic (4)             — T_QUAT_GROUP_SHIFT, T_NEUTRAL_QUAT_W,
                              T_THROTTLE_TIME_INJECTION,
                              T_MANAGED_ALIAS_DETECT
UI contracts (2)            — T_CAVEAT_VISIBLE,
                              T_TOOLS_SECTION_PERSISTS
Test infrastructure (2)     — T_CONFTEST_DUAL_ENV (#17, 6 sub),
                              T_M1_5_FIXTURE_BOUNDARY (#18, 4 sub)
```

### §M1.5.1.7 — Red lines confirmed

- ✅ **0 C++ changes** (K.1 lock; CMakeLists.txt also untouched)
- ✅ **0 business code changes** (`scripts/RBFtools/*.py` and `source/*` both empty diffs)
- ✅ **0 `.mll` load** in this commit (C.1 + K.1 double lock)
- ✅ **A-class conversion exactly 5 classes** (R2 lock list; no scope creep)
- ✅ **0 `cmds.refresh` / `cmds.idleQueue` / `cmds.evalDeferred`** in M1.5.1 test additions (R3 — F4 mock workaround forbidden)
- ✅ **`core_live.py` mock-based tests untouched** (existing T_LIVE_NO_DRIVEN_LISTEN / T_THROTTLE_TIME_INJECTION still cover pure-function semantics)
- ✅ **T_CONFTEST_DUAL_ENV 6 sub-checks remain green**; pure-Python ≥ 440 invariant honoured (now 444)
- ✅ **`maya.standalone` not in conftest** (T_CONFTEST_DUAL_ENV invariant 5 + T_M1_5_FIXTURE_BOUNDARY invariant D — both enforce)
- ✅ **§M1.5.1.X Blocker Matrix present** as forward-compat anchor (R4)

---

## §M1.5.1.X — Blocker Matrix (forward-compat anchor)

Mechanical consumption format. Future sub-tasks reference this
table by row to determine which blocker their work depends on.

| Blocker | Discovered in | Blocks | Resolution sub-task | ETA hint |
|---|---|---|---|---|
| 2022 .mll incompatible with Maya 2025 | F1 (M1.5.1) | M2.5b compute() consumer / M2.5 decompose Python↔C++ regression / `_K_*` benchmark replacement (M1.5.2) / B-class skip conversion (~15 classes) / M1.1-M2.4 byte-level C++ regression (M1.5.3) | **M1.5.1b** (independent C++ sub-task; CMakeLists cosmetic adaptation + recompile + load verification) | **RESOLVED** in M1.5.1b — see §M1.5.1b below |
| `maya.standalone` not re-entrant | F2 (this sub-task) | Any per-test or module-scoped `initialize/uninitialize` cycle | (RESOLVED in this sub-task: `_mayapy_fixtures.ensure_maya_standalone` session-scoped lazy-init pattern) | n/a — done |
| scriptJob `attributeChange` does not fire under headless mayapy | F4 (this sub-task) | M3.4 spillover items 1/2/3 (real attributeChange / `parent=` cleanup / viewport drag throttle) | **M5 GUI Maya long-tail manual verification** | Long-deferred; not on M4 / M4.5 / M5-perf critical path. R3 forbids mock workaround in interim. |

Downstream sub-task contract: when a planning step decides "we
need X", consult this table; if X is blocked, either tackle the
resolution sub-task first or explicitly defer X with a Blocker
Matrix row reference in its addendum entry.

---

## §M1.5.1b — .mll Rebuild for Maya 2025 (Blocker Matrix Row 1 RESOLVED)

> **⚠️ Maya 2022 用户重要 caveat**（加固 7）：
>
> 当前 `modules/RBFtools/plug-ins/win64/2022/RBFtools.mll`（126976
> bytes, 2026-04-07）时间戳早于 M2.5 commit (`c866604`)，**缺失**
> `poseSwingTwistCache` 等 5 个 cache 字段。Maya 2022 用户须本地
> 用 2022 devkit 重 build 一次以获得 M2.5 schema：
>
> ```
> cd source && cmake -G "Visual Studio 17 2022" -A x64 -B build_2022 \
>   -DMAYA_DEVKIT_PATH="C:/Program Files/Autodesk/Maya2022"
> cmake --build build_2022 --config Release
> # 然后 cp build_2022/Release/RBFtools.mll modules/RBFtools/plug-ins/win64/2022/
> ```
>
> Maya 2025 用户直接载 `modules/RBFtools/plug-ins/win64/2025/RBFtools.mll`
> （本子任务交付物）即可。`tests/README.md` 同载此 caveat（用户首入口）。

### §M1.5.1b.0 — 子任务范畴

Resolution of §M1.5.1.X Blocker Matrix Row 1（"2022 .mll
incompatible with Maya 2025"）。M3 全程 enforced "0 C++ changes"
红线在此首次 controlled-break，但 actual breach 极小：

- **0 行 C++ source 改动**（`source/RBFtools.h` / `source/RBFtools.cpp`
  / `source/BRMatrix.cpp` / `source/pluginMain.cpp` 全部不动）
- **6 行 cosmetic CMakeLists.txt 注释**（line 4 / 6 / 8 / 12 / 13 / 39
  —— 仅 "Maya 2022" → "Maya 2022/2025" 字面清理 + MSVC 工具链注释
  对齐 build/CMakeCache 实证（v143 而非 v142））
- **1 个新 build artifact**（`modules/RBFtools/plug-ins/win64/2025/RBFtools.mll`）

### §M1.5.1b.1 — F1-F5 + F6/F7 现状核查（verify-before-design 第 9 次使用）

| F | 实测 | 关键发现 |
|---|---|---|
| **F1** | `C:/Program Files/Autodesk/Maya2025/` 含完整 include/lib；`devkit/` 子目录仅 `README_DEVKIT_MOVED.txt`（separate download）；Maya 2022 仍并存 | install root 可直接作 `MAYA_DEVKIT_PATH`；2022 + 2025 双安装 |
| **F2** | `cmake -G "Visual Studio 17 2022" -A x64 -DMAYA_DEVKIT_PATH=Maya2025` 配置 7.7s **零 error / 零 warning**；MSVC 19.44.35223（v143）；同一 toolchain 也是现 build/ 用 | CMakeLists configure 层 100% 2025-兼容 |
| **F3** | M2.5 schema 5 字段 + compound parent **已在 C++**：`RBFtools.h:336-341` 声明 / `RBFtools.cpp:88-93` 全局实例 / cpp:571-595 创建 / cpp:751-755 addChild / cpp:823-828 addAttribute | **F.2 NO-OP** — M1.5.1c 子任务**取消** |
| **F4** | `modules/RBFtools/plug-ins/win64/2022/RBFtools.mll` (126976 b, Apr 7) 唯一现存；无 `.mod` 文件；2025/ 子目录不存在 | 新建 win64/2025/，保留 2022/ stale .mll（D.3） |
| **F5** | 现有 `#if MAYA_API_VERSION < 202400` 守护（h:45,438,502 + cpp:4483）覆盖 MDrawContext.h 移除；Maya 2025 = `MAYA_API_VERSION 20250300` → 守护正确路由 | C++ source 0 改动即 API-level 适配 |
| **F6** | 单 `MAYA_DEVKIT_PATH` 变量 + `#if MAYA_API_VERSION` 预处理依赖编译时 include path | 双 SDK 不可同 build；用户须各跑一次（文档化） |
| **F7** | F3 已确认全字段在 C++ | M1.5.1c 取消（无须存在） |

### §M1.5.1b.2 — 13 决议（默认全批）

| # | 决议 | 选择 |
|---|---|---|
| A | MAYA_DEVKIT_PATH 默认值 | **A.3** 不动 + 注释清理 |
| B | Maya 版本支持范围 | **B.2** 双版本并存 |
| C | 编译产出目录约定 | **C.1** `win64/2025/` Autodesk 标准 |
| D | stale 2022 .mll 处置 | **D.3** 保留原位（B.2 对称）|
| E | `.mod` 文件 | **E.3** 不引入（沿用 `MAYA_PLUG_IN_PATH`）|
| F | C++ schema 暴露 | **F.2 NO-OP** — 已暴露 |
| G | API breaking change 适配 | **G.1** 沿用现 `#if` 守护 |
| H | 编译警告策略 | **H.2** 沿用 MSVC 默认 |
| I | `require_rbftools_plugin` 启用 | **NO** — M1.5.3 锁 |
| J | loadPlugin 验证范围 | **J.3** loadPlugin + createNode + 5 字段 introspection |
| K | C++/CMake 改动列表 | （见 §M1.5.1b.3） |
| L | 回退策略 | **L.1** 单 commit revert |
| M | commit message 草稿 | （见 commit body）|
| N | 永久守护新增 | **N.1+N.2+N.3** 三新 guard |

加固 5/6/7/8 全部纳入：

- **加固 5**：J3 introspection dump 文本块写入 §M1.5.1b.J3-baseline（M1.5.3 byte-level diff source-of-truth）
- **加固 6**：.mll SHA256 写入 §M1.5.1b.SHA256-baseline + commit body
- **加固 7**：Maya 2022 caveat 写入本节顶部 + tests/README.md
- **加固 8**：T_M1_5_1B_PLUGIN_LOADABLE 不写 size 范围断言（仅 exists / size > 0 / `MZ` header）

### §M1.5.1b.3 — 改动清单（K）

| 类别 | 文件 / 路径 | 行数 | 内容 |
|---|---|---|---|
| build config | `source/CMakeLists.txt` | 6 行 cosmetic | line 4/6/8/12/13/39，"Maya 2022" → "Maya 2022/2025"；MSVC 注释 v142→v143 |
| C++ source | — | **0** | F5 已实证零改动即兼容 |
| build artifact (新) | `modules/RBFtools/plug-ins/win64/2025/RBFtools.mll` | 1 binary, 166912 bytes | Release build，VS 2022 v143，cxx_std_14 |
| 测试 (新) | `modules/RBFtools/tests/test_m1_5_1b_build.py` | ~140 行 | PERMANENT GUARD #19/#20/#21（7 test methods） |
| 文档 | `docs/设计文档/RBFtools_v5_addendum_20260424.md` | +§M1.5.1b 本节 | 决议 / J3 baseline / SHA256 baseline / Blocker Row 1 RESOLVED |
| 文档 | `modules/RBFtools/tests/README.md` | +Maya 2022 caveat | 加固 7 |

### §M1.5.1b.4 — 永久守护新增 (#19/#20/#21)

实现于 [test_m1_5_1b_build.py](../../modules/RBFtools/tests/test_m1_5_1b_build.py)：

- **#19 T_M1_5_1B_BUILD_CONFIG**：`source/CMakeLists.txt` 含全部
  关键 token（每 token 单独 subTest 定位精确）：
  `MAYA_DEVKIT_PATH` / `OpenMaya` / `OpenMayaUI` / `OpenMayaAnim` /
  `OpenMayaRender` / `Foundation` / `NT_PLUGIN` / `REQUIRE_IOSTREAM` /
  `SUFFIX ".mll"` / `PREFIX ""` / `RBFtools` / `pluginMain.cpp` /
  `RBFtools.cpp` / `BRMatrix.cpp`（14 token）
- **#20 T_M1_5_1B_PLUGIN_LOADABLE**：`win64/2025/RBFtools.mll`
  存在 + `getsize() > 0` + 头 2 字节 `b"MZ"`（PE32+ marker）。
  **不写 size 范围**（避免 toolchain drift 假阳性 fail）。
  mayapy `loadPlugin` 实测断言留 M1.5.3。
- **#21 T_M1_5_1B_2025_DIR_EXISTS**：`win64/2025/` 与 `win64/2022/`
  双目录 symmetric 存在。

### §M1.5.1b.J3-baseline — mayapy introspection dump（加固 5）

一次性 mayapy probe 实测输出（probe script 不进 commit）：

```
=== loadPlugin ===
loaded: True
version: 4.0.1

=== createNode ===
node: RBFtoolsShape1

=== M2.5 schema introspection ===
poseSwingTwistCache: exists=True
  longName=poseSwingTwistCache shortName=pstc
poseSwingQuat: exists=True
  longName=poseSwingQuat shortName=psq
poseTwistAngle: exists=True
  longName=poseTwistAngle shortName=pta
poseSwingWeight: exists=True
  longName=poseSwingWeight shortName=psw
poseTwistWeight: exists=True
  longName=poseTwistWeight shortName=ptw
poseSigma: exists=True
  longName=poseSigma shortName=psg

=== listAttr count ===
total attrs: 274

=== unloadPlugin ===
unloaded ok
```

M1.5.3 byte-level 回归测试以本节为 source-of-truth diff baseline。

### §M1.5.1b.SHA256-baseline — .mll reference build hash（加固 6）

```
2725287715b9793ba5a485becd0fe70e57a554574bd5e1e8c0ed702e3d104c02 *modules/RBFtools/plug-ins/win64/2025/RBFtools.mll
```

环境：VS 2022 17.14 / MSVC 19.44.35223 (v143) / Windows SDK 10.0.26100.0
/ Release config / Maya 2025 devkit (`C:/Program Files/Autodesk/Maya2025`)
/ 2026-04-26 build。后续重 build 漂移检测 anchor；**不**做永久守护
（toolchain 小版本变化时 SHA 漂移正常）。

### §M1.5.1b.5 — Empirical baseline (2026-04-26)

| 环境 | Pre-M1.5.1b | Post-M1.5.1b | Δ |
|---|---|---|---|
| Pure-Python | 444 / 444 OK | **451 / 451 OK** | +7（test_m1_5_1b_build.py 7 methods） |
| mayapy 2025 | 444 ran 407 pass 37 skip | **451 ran 414 pass 37 skip** | +7 / +7 / **0**（37 skip 不变 — `require_rbftools_plugin` 仍 NO-OP，M1.5.3 锁） |

cmake build (Maya 2025): 0 error；warning 全部**预存在**（C4819 中文 codepage / C4005 `M_PI` 重定义 — 与 M1.5.1b 改动无关）。

PERMANENT GUARD: **18 → 21**。

### §M1.5.1b.6 — Unblocks downstream

参照 §M1.5.1.X Blocker Matrix Row 1，本子任务 RESOLVED 后解锁：

- M1.5.2 `_K_*` benchmark replacement（**DEFERRED to M5** — 见 §M1.5.2）
- M1.5.3 B-class ~15 conversion + byte-level C++ regression +
  `require_rbftools_plugin` 启用
- M2.5b compute consumer（.mll 依赖通过 §M1.5.1b 满足）
- M2.5 decompose Python↔C++ 双向

---

## §M1.5.2 — _K_* benchmark calibration protocol probe (DEFERRED to M5)

**Status: DEFERRED to M5**（保留 caveat `[CONCEPTUAL — no machine
calibration]` 不变；保留 `_K_CHOL = 1e-9` / `_K_GE = 3e-9` /
`_K_QWA = 1e-7` 概念值不变）

**Why deferred**: M3 全程 enforced "0 C++ changes" red line + F2
verify-before-design (10th use) confirmed `lastSolveMethod` is a
C++ private instance member NOT exposed as a Maya attribute. This
ceiling means black-box mayapy measurement of solver kernel time
is dominated by DG plug-propagation floor (~19 µs measured),
NOT the actual O(N³) Cholesky / GE work. The protocol failed
both R² ≥ 0.95 (加固 6) and K_GE/K_CHOL ∈ [1.5, 5.0] (红线 8)
gates simultaneously. Per "verify-before-design" doctrine, the
honest move is to defer rather than fudge fit — same disposition
as original §M3.5.F2 design intent ("M5 will replace these with
real benchmarks").

### §M1.5.2.1 — verify-before-design 第 10 次使用决议

**F1-F6 现状核查关键发现**：

| F | 实测 | 关键发现 |
|---|---|---|
| **F1** | `core_profile.py:62-64` 三常数；`:107-109` 消费 = 报告显示；`:341-344` T_CAVEAT_VISIBLE caveat；`:369-373` magnitude table 用 `_K_CHOL` 算 split 建议 ms | 三 K **纯显示用途**——无 solver 决策依赖 |
| **F2** | `RBFtools.h:403` `short lastSolveMethod` C++ private instance member；`addAttribute()` 仅暴露 `solverMethod` enum；无 `lastSolveTime_*` 字段；`BRMatrix` 类不通过 SWIG/Python 暴露 | **黑盒测量是唯一路径**；无法精确隔离 solver 单步耗时 |
| **F3** | mayapy `time.perf_counter` resolution = 1e-7 (100 ns, QueryPerformanceCounter)；1000-iter Python add loop ~51 µs | 100 ns 时钟分辨率充足，但 mayapy 单次 setAttr+getAttr ~19 µs 的 DG floor 是**结构性 noise floor** |
| **F4** | `_THRESH_N_POSES = 80` split 阈值；magnitude table 在 trigger 后输出 N=2/3/4 子分裂建议 | 采样点须覆盖 N=80 附近 |
| **F5** | M2.5 cache 字段仅作用 SwingTwist 解码路径；solver kernel 不感知 cache | Generic 模式 benchmark 单 K 即可（无须双 K split） |
| **F6** | F2 已确认 0-C++ 立场绝对；C++ 暴露诊断字段需独立子任务 | **0 C++ 改动** lock |

**(A)-(N) 决议（probe 阶段已批；P4 推迟后部分作废）**：

- A.3 一次性 probe 脚本不进 commit（仅 verbatim 写 §M1.5.2.7）
- B.2 7 点采样 N ∈ {10, 50, 80, 100, 200, 500} (+1000 if budget)
- C.2 最小二乘 t = K·N³ + b（截距吸收 DG noise）
- D.3 QWA 仅 4×4（与 M2.2 production 一致；numpy proxy due to F2 ceiling）
- E.1 hardcoded 替换 + ISO 日期注释 → **作废（P4 不替换）**
- F.2 caveat 改 `[CALIBRATED ...; tune for your hardware]` → **作废（P4 保 CONCEPTUAL）**
- G.1 T_CAVEAT_VISIBLE sub-test 1 字符串更新 → **作废（P4 不动）**
- H.3 完整环境快照（CPU/RAM/Maya/Python/.mll SHA256）→ §M1.5.2.8
- I.2 report 加 `[calibrated YYYY-MM-DD]` 行 → **作废（P4 无校准日期）**
- J.2 `_THRESH_*` 不动（UX 阈值 ≠ 物理量；K 校准不蕴含阈值校准）
- K **0 C++ 改动**（执行确认）
- L.1 单 commit revert 即回（P4 下仅 docs + 1 守护测试）
- M commit message — type 改 `docs(profile)` 而非 `feat(profile)`
- N.1+N.2+N.3 三守护 → **P4 收缩为单守护 N.0 T_M1_5_2_CALIBRATION_DEFERRED**

### §M1.5.2.2 — Probe 协议设计

```
matrix sizes: N ∈ {10, 50, 80, 100, 200, 500}
per-N: 5 measurements (fresh node each), median taken
fit:   t(N) = K·N³ + b  (b absorbs DG noise + plug push-pull)
driver mode: Generic / Raw encoding (M2.5 SwingTwist cache bypassed)
QWA: numpy proxy of 4x4 SPD power-iteration (D.3 indirect; BRMatrix
     internal QWA call cannot be isolated from compute() under F2
     ceiling)
gates: R²_CHOL ≥ 0.95 AND R²_GE ≥ 0.95 AND
       K_GE/K_CHOL ∈ [1.5, 5.0]
       任一不满足 → 停下报告，不替换数字
```

### §M1.5.2.3 — 实测原始数据（DEFERRED 触发证据，2026-04-26）

**K_CHOL benchmark** (solverMethod=0, Gaussian kernel, SPD path):

| N | median (s) | samples (s) |
|---|---|---|
| 10  | 0.000019 | [0.000392, 2.2e-05, 1.9e-05, 1.8e-05, 1.8e-05] |
| 50  | 0.000019 | [1.9e-05, 1.9e-05, 1.9e-05, 1.8e-05, 2.9e-05] |
| 80  | 0.000029 | [2.7e-05, 2.9e-05, 3.2e-05, 2.5e-05, 3.1e-05] |
| 100 | 0.000025 | [2.4e-05, 3.0e-05, 2.5e-05, 2.1e-05, 4.1e-05] |
| 200 | 0.000036 | [3.6e-05, 4.4e-05, 3.3e-05, 3.2e-05, 4.5e-05] |
| 500 | 0.000042 | [4.5e-05, 4.0e-05, 4.2e-05, 4.0e-05, 4.3e-05] |

**K_GE benchmark** (solverMethod=1, Force GE):

| N | median (s) |
|---|---|
| 10  | 0.000019 |
| 50  | 0.000030 |
| 80  | 0.000027 |
| 100 | 0.000034 |
| 200 | 0.000037 |
| 500 | 0.000042 |

**Fit results** (least-squares t = K·N³ + b):

```
K_CHOL = 1.4300e-13   b_CHOL = 2.5058e-05   R² = 0.5839   ❌ < 0.95
K_GE   = 1.0768e-13   b_GE   = 2.9050e-05   R² = 0.4211   ❌ < 0.95
ratio K_GE / K_CHOL = 0.753                                ❌ ∉ [1.5, 5.0]
```

**K_QWA numpy proxy** (4×4 SPD power-iter, 50 iter × 1000 batches × 7 reps):

```
samples sec/iter: [2.255e-06, 2.237e-06, 2.242e-06, 2.250e-06,
                   2.229e-06, 2.225e-06, 2.245e-06]
K_QWA median = 2.2416e-06 sec/iter   (vs 1e-7 conceptual; ratio 22×)
```

K_QWA proxy 偏离原概念值 22×：根因是 numpy 4×4 ops Python 解释器
开销主导（每 iter 6 PyObject 调用 + ufunc 启动 ~300-400 ns 各，
compared to 实际 4×4 数学 ~50 FLOP × 1 ns ≈ 50 ns）。numpy proxy
**不能代表** C++ 内部 `powerIterationMaxEigenvec4x4` 真实成本。

### §M1.5.2.4 — 根因诊断（4 候选按概率排序）

实测 wall-clock 在 N=10 至 N=500 区间**基本平坦**（19 µs → 42 µs）。
若 compute() 真在跑 O(N³) Cholesky，N=500 应该 ~125 ms（按概念值
1e-9）—— 实测 42 µs 比之**小约 3000×**。`getAttr <node>.output[0]`
路径**没有真正触发** `BRMatrix::cholesky()` / `solve()`。可能原因：

1. **新建 RBFtools 节点未连接 driver → `input[]` 没有 incoming
   connection → `evalInput` 路径走"未配置/退化"短路**——compute()
   早期 return 一个常量或 0，根本不调 solver
2. **节点缺少必要的 `train` trigger**（M1.4 设计可能要求显式
   `evaluate` 切换或 `radius` 重设来触发首次训练）
3. **kernel/rbfMode/distanceType 默认值组合下 `getPoseData()` 返回
   `poseCount=0`**（构造函数设的 `globalPoseCount=0`，需要某个 attr
   让 C++ 重新计数）
4. **probe 用的 vec3 driver + 1-D output 不匹配 RBF 模式 setup
   期望**（`useRotate`/`useTranslate`/`type` enum 未配）

**支持证据**：
- 19 µs 的 baseline 恰好是典型 Maya DG `setAttr → getAttr` 一次
  往返的 plug propagation cost（与 F3 探针 1000-iter 51 µs 同量级）
- N=10 第一个样本是 392 µs（一次性 standalone init / cache prime），
  后续都 ~19 µs —— 暗示后续测的是空 compute()

**结论**：这**不是** `BRMatrix` 实现 bug——是 probe 协议没正确"喂"
节点让 solver 路径生效。修协议（连 driver / 加 train trigger / 配
更完整 attr）可能让大 N 数据点抬到 ms 级，但小 N（10/50）仍受 DG
floor 污染（`b` 截距吸收 ~19-30 µs）。

### §M1.5.2.5 — 红线 7 + 8 触发记录

| 红线 | 触发 | 实测 | 处置 |
|---|---|---|---|
| 7 (加固 6: R²<0.95 任一停) | YES | R²_CHOL=0.58 / R²_GE=0.42 | 立即停下报告 |
| 8 (K_GE/K_CHOL ∉ [1.5, 5.0]) | YES | 0.753 | 立即停下报告 |

**结构性诊断**：0-C++ 约束下 black-box 测量精度上限就是当前观察到
的 R²<0.6（受 DG floor + 协议复杂度 + 小 N 污染共同影响）。**不是
凑数能解决的——是测量协议层面的硬约束**。修 probe 协议至 P1/P2 形
态可能改善 R² 至 ~0.8，但 ratio sanity 在 hand-written O(N³)
solver 下仍可能违反（Cholesky 与 GE 的 N³ 系数差异在 19 µs DG
floor 主导下被掩盖）。

### §M1.5.2.6 — 推迟到 M5 决议

**保留**：
- `_K_CHOL = 1e-9` / `_K_GE = 3e-9` / `_K_QWA = 1e-7` 三常数不变
- caveat `"[CONCEPTUAL — no machine calibration]"` 不变
- T_CAVEAT_VISIBLE sub-test 1 字符串不变
- `_THRESH_N_POSES = 80` / `_THRESH_CELLS = 500` / `_THRESH_CHOL_MS = 5.0`
  阈值不变（J.2 — UX 阈值非物理量；K 校准不蕴含阈值校准）

**与原始设计一致性**：v5 设计原 §M3.5.F2 已写"M5 will replace
these with real benchmarks, keeping the symbol names as a
forward-compat interface"。P4 与原设计 forward-compat 完全对齐，
不偏离。

**M5 重启触发条件**（任一）：

1. M5 性能子任务自然推进（v5 PART F roadmap 自然到达）
2. 用户 benchmark 请求（明确报告"profile ms 数与实际差距大"）
3. 独立 C++ timer-exposure 子任务（破 0-C++ 红线，需新 verify-
   before-design 现状核查 + (K) 红线预批 + 新增 MObject `lastSolveTimeMs`）
4. 用户机器 CPU 重大变化触发重新校准需求

### §M1.5.2.7 — Probe 脚本 verbatim（加固 7：M5 重启 reference）

脚本本身 **NOT committed**（A.3 一次性范式）。完整内容如下，
未来 M5 重启时复制此块到 `/tmp/probe_m1_5_2.py` 直接复用：

```python
"""M1.5.2 _K_* benchmark probe — one-shot mayapy script.

NOT committed (A.3 lock). Verbatim copied to addendum
§M1.5.2.probe-script for future re-calibration reference.

Protocol (addendum §M1.5.2.probe-script):
  matrix sizes: N in {10, 50, 80, 100, 200, 500}
  per-N: 5 measurements (fresh node each), median taken
  fit:   t(N) = K * N^3 + b   (b absorbs DG noise)
  driver mode: Generic / Raw encoding (M2.5 cache bypassed)
  K_QWA: numpy proxy of 4x4 SPD power-iteration (D.3 indirect)
"""

from __future__ import absolute_import, print_function

import os, sys, time, random, statistics

import maya.standalone
maya.standalone.initialize()
import maya.cmds as cmds

_MLL = "X:/Plugins/RBFtools/modules/RBFtools/plug-ins/win64/2025/RBFtools.mll"
print("loadPlugin:", _MLL)
cmds.loadPlugin(_MLL)
print("loaded:", cmds.pluginInfo("RBFtools", q=True, loaded=True))

random.seed(42)


def build_node(n_poses, solver_method):
    """Create RBFtools node, configure N poses with vec3 driver and 1
    output. solver_method: 0=Auto (Cholesky preferred), 1=Force GE."""
    n = cmds.createNode("RBFtools")
    cmds.setAttr(n + ".solverMethod", solver_method)
    cmds.setAttr(n + ".kernel", 0)            # 0=Gaussian
    cmds.setAttr(n + ".rbfMode", 1)           # 1=RBF
    cmds.setAttr(n + ".inputEncoding", 0)     # 0=Raw
    cmds.setAttr(n + ".regularization", 1e-3)
    cmds.setAttr(n + ".radius", 1.0)
    for i in range(3):
        cmds.setAttr(n + ".input[{}]".format(i), 0.0)
    for p in range(n_poses):
        for i in range(3):
            cmds.setAttr(
                n + ".poses[{}].poseInput[{}]".format(p, i),
                random.uniform(-1.0, 1.0),
            )
        cmds.setAttr(
            n + ".poses[{}].poseValue[0]".format(p),
            random.uniform(-1.0, 1.0),
        )
    return n


def time_first_compute(n_poses, solver_method):
    n = build_node(n_poses, solver_method)
    cmds.setAttr(n + ".input[0]", 0.123)
    cmds.setAttr(n + ".input[1]", 0.456)
    cmds.setAttr(n + ".input[2]", 0.789)
    t0 = time.perf_counter()
    _ = cmds.getAttr(n + ".output[0]")
    t1 = time.perf_counter()
    cmds.delete(n)
    return t1 - t0


SIZES = [10, 50, 80, 100, 200, 500]
REPLICATES = 5

print("\n=== K_CHOL benchmark ===")
chol_data = []
for N in SIZES:
    samples = [time_first_compute(N, 0) for _ in range(REPLICATES)]
    med = statistics.median(samples)
    chol_data.append((N, med, samples))
    print("N={:4d}  median={:.6f}s".format(N, med))

print("\n=== K_GE benchmark ===")
ge_data = []
for N in SIZES:
    samples = [time_first_compute(N, 1) for _ in range(REPLICATES)]
    med = statistics.median(samples)
    ge_data.append((N, med, samples))
    print("N={:4d}  median={:.6f}s".format(N, med))


def fit_cubic(data):
    xs = [N ** 3 for (N, _, _) in data]
    ys = [t for (_, t, _) in data]
    n = len(xs)
    sx = sum(xs); sy = sum(ys)
    sxx = sum(x * x for x in xs)
    sxy = sum(x * y for x, y in zip(xs, ys))
    K = (n * sxy - sx * sy) / (n * sxx - sx * sx)
    b = (sy - K * sx) / n
    y_mean = sy / n
    ss_tot = sum((y - y_mean) ** 2 for y in ys)
    ss_res = sum((y - (K * x + b)) ** 2 for x, y in zip(xs, ys))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 1.0
    return K, b, r2


K_CHOL, b_CHOL, R2_CHOL = fit_cubic(chol_data)
K_GE, b_GE, R2_GE = fit_cubic(ge_data)

print("\nK_CHOL = {:.4e}  R2 = {:.4f}".format(K_CHOL, R2_CHOL))
print("K_GE   = {:.4e}  R2 = {:.4f}".format(K_GE, R2_GE))
print("ratio K_GE / K_CHOL = {:.3f}".format(K_GE / K_CHOL))

import numpy as np
random.seed(2025)
A = np.random.rand(4, 4)
M = (A @ A.T) + np.eye(4) * 0.1

samples_qwa = []
for _ in range(7):
    t0 = time.perf_counter()
    for _b in range(1000):
        v = np.array([0.0, 0.0, 0.0, 1.0])
        for _i in range(50):
            v = M @ v
            n_ = np.linalg.norm(v)
            if n_ > 0:
                v = v / n_
    t1 = time.perf_counter()
    samples_qwa.append((t1 - t0) / (1000 * 50))

K_QWA = statistics.median(samples_qwa)
print("\nK_QWA proxy = {:.4e} sec/iter".format(K_QWA))
```

### §M1.5.2.8 — 环境快照（H.3）

| 维度 | 值 |
|---|---|
| CPU | Intel Core i7-14700KF (28 threads) |
| RAM | 64 GB (68551335936 bytes) |
| OS | Windows 11 Enterprise (10.0.26200) |
| Maya | 2025 |
| Python | 3.11.4 (mayapy) |
| Win SDK | 10.0.26100.0 |
| MSVC | 19.44.35223 (VS 2022 v143) |
| .mll SHA256 | `2725287715b9793ba5a485becd0fe70e57a554574bd5e1e8c0ed702e3d104c02` |
| 测试日期 | 2026-04-26 |
| 后台进程 | （probe 未关闭后台；M5 重启时建议关闭浏览器/IDE/同步工具）|

### §M1.5.2.9 — Blocker Matrix update

§M1.5.1.X Blocker Matrix **不**新增 row（_K_* 推迟不阻塞 M1.5.3 /
M2.5b / M2.5 decompose；这些子任务依赖 .mll 而非 _K_* 数值精度）。

**新 forward-compat anchor entry**：

| 项 | Discovered in | 状态 | 重启条件 |
|---|---|---|---|
| `_K_CHOL` / `_K_GE` / `_K_QWA` 实际校准 | M1.5.2 (this section) | DEFERRED to M5 | 见 §M1.5.2.6 四触发条件 |

未来执行者读到此 entry 时知：(1) M1.5.2 已尝试且推迟，(2) 重启不
是"自由发挥"，需先评估 §M1.5.2.6 四触发条件至少一个成立，(3) 重
启时 §M1.5.2.7 probe 脚本是 reference 起点。

---

## §M1.5.3 — B-class Conversion + Byte-level Regression (PAUSED until v5.0 final)

> **STATUS: PAUSED until v5.0 final** (since 2026-04-26)
>
> M1.5.3 4-commit plan (a/b/c/d) was approved but not started
> — pivoted to M_FEATURE_PARITY_AUDIT after roadmap audit
> identified 6 B-matrix gaps (B1/B2/B4/B7/B11/B14) needing
> closure before any optimization sub-task. M1.5.3 research
> findings (F1/F2/F3/F4/F8 in M1.5.3 现状核查报告, see
> conversation transcript verify-before-design 11th use)
> preserved as v5.x post-final restart baseline. See
> §M_PARITY_AUDIT for revised sequence.
>
> Restart trigger: v5.0 final tag landed (B-matrix 15/15 ✅)
> + user explicitly requests post-final test infrastructure
> work.
>
> **Status definition**: PAUSED ≠ ABANDONED. The 4-commit
> plan + verify-before-design 11th findings are full-fidelity
> recoverable. Do NOT silently start M1.5.3a in v5.x without
> first re-reading both restart triggers above.

### §M1.5.3.research-preserved — verify-before-design 11th findings

The following findings from the M1.5.3 现状核查 (paused before
implementation) are kept here as the v5.x restart base — they
will save ~half a day of re-discovery work:

- **F1 — `require_rbftools_plugin` enable path**: `cmds.loadPlugin`
  is naturally idempotent under Maya 2025 mayapy (2nd call returns
  `None` + "already loaded" warning rather than raising).
  `_PLUGIN_LOADED` flag is for warning-noise reduction, not
  idempotency correctness. Replacement of the SkipTest stub at
  `_mayapy_fixtures.py:109-130` is ~30 LOC.
- **F2 — M2.5b sentinel C++ consumer logic IS NOT IMPLEMENTED**:
  `poseSigma` / `poseSwingQuat` / `poseTwistAngle` / `poseSwingWeight`
  / `poseTwistWeight` are all schema-declared + `addAttribute()`'d
  but **NO compute() consumer reads them back** (no
  `inputValue(poseSigma)` access). The cpp:820 comment promises
  "sentinel for cache not populated — falls back to live decompose",
  but the actual compute() does neither cache read nor sentinel
  check. Implementing M2.5b consumer = ~100-130 LOC NEW C++ in
  `RBFtools.cpp` compute() SwingTwist branch + helper.
- **F3 — Python `decompose_swing_twist` does NOT exist**:
  C++ side has `RBFtools::decomposeSwingTwist` (cpp:3036) + 2
  callers; Python side has zero such function (only a docstring
  reference at `core.py:1918`). M2.5 "decompose 双向同步" is
  actually "build Python side first, then bidirectional".
- **F4 — B-class is 19, not 15**: actual count of `skipIf(_REAL_MAYA)`
  decorated classes is 19 (test_m2_4a_core×5 + test_m2_5_cache×3
  + test_m3_1_prune×2 + test_m3_2_mirror×1 + test_m3_3_jsonio×4
  + test_m3_6_neutral×2 + test_m3_7_alias×2). M2.5 cache subset
  (3 classes) blocks until F2 consumer implementation lands.
- **F8 — Scope split**: total estimate 1180-2110 LOC + major C++,
  must split into 4 commits per restart-time agreement.
  Commit-split lock: M1.5.3a (require_rbftools_plugin enable + 2
  smoke B-class) → M1.5.3b (Python decompose_swing_twist + byte-
  level M1.1/M2.1a/M2.1b) → M1.5.3c (M2.5b C++ consumer + cache
  3 B-classes) → M1.5.3d (remaining ~14 B-class + byte-level
  M1.4/M2.2/M1.2/M1.3).

### §M1.5.3.restart-protocol

When restart triggers fire (v5.0 final tag + user post-final
test request), the executor MUST:

1. Re-read this §M1.5.3 PAUSED block + §M1.5.3.research-preserved
2. Re-read the M1.5.3 现状核查报告 (full transcript) to confirm
   F1-F8 still hold against the v5.0 final code base
3. If any F finding has drifted (e.g., M2.5b consumer was added
   in some intermediate sub-task), update §M1.5.3.research-preserved
   in the same commit before starting M1.5.3a
4. Only then start M1.5.3a per the locked 4-commit split

---

## §M_PARITY_AUDIT — v5.0 final 复刻完整度断面（"宪法"级文档）

> **CONSTITUTIONAL DOC**: This section is the source-of-truth
> for v5.0 final acceptance. Each B-matrix row's status here
> is what v5.0 final's release commit MUST flip to ✅. Any
> sub-task whose work would change this section MUST update
> the relevant B-row's status table entry in the same commit.

### §M_PARITY_AUDIT.0 — 总览

| 项 | 值 |
|---|---|
| 审计日期 | 2026-04-26 |
| commit hash 基线 | `459dd56` (post-M1.5.2 DEFERRED push) |
| 总体完整度 | **11/15 ✅ + 2/15 ⚠️ + 2/15 ❌** *(audit trail: M_B24b2 11/15 → M_B24d data-path correction 10/15 → M_B24d resolution 11/15; B2 status precision-corrected to "complete (Generic) + Mirror DEFERRED to M_B24c + Matrix DEFERRED to M_B24d_matrix_followup")* |
| 致命未达项 | **B1**（仅一项；B3/B5/B6 已落地） |
| 高未达项 | ~~B2~~ / ~~B4~~ → ✅ complete per M_B24b2 + M_B24d (B2 with deferred caveats; B4 full) |
| 中未达项 | **B7** / **B11** |
| 低未达项 | **B14** |
| verify-before-design | 第 12 次使用（H 顺序两轮决议; H.2 LOCKED）|

#### Roadmap pivot driver

Pre-audit roadmap (rejected): M1.5.3 → M4.5 → M5.x → ... 优化
导向，B 矩阵未闭合即开优化。Post-audit roadmap (LOCKED, H.2 user
override 2026-04-26):

```
M_B24 (B2 + B4)              [M_B24a backend, M_B24b frontend]
  ↓ TD 多源驱动 UI 解锁 (primary deliverable per user override)
M4 (B1)                      [M4.1, M4.2, M4.3, M4.4]
  ↓ M4.1 chained migration: pre-M_B24 nodes hit type+rbfMode
                            → solverType + driverList → driverSource
                            sequentially (~30 LoC backcompat)
M_B7  (split tool)
M_B11 (Live Edit GUI integration)
M_B14 (driver lock UI hint)
═══ v5.0 final → tag v5.0 ═══
[v5.x post-final 优化层 — M1.5.3 解冻 / M4.5 / M5.1-5.5]
```

**(H) 顺序决议（user override 2026-04-26 LOCKED）**：

| 选项 | 顺序 | 状态 |
|---|---|---|
| H.1 | M4(B1) → M_B24(B2+B4) → ... | ~~rejected (planner-suggested)~~ |
| **H.2** | **M_B24(B2+B4) → M4(B1) → ...** | ✅ **LOCKED** |

**用户 business priority 决议**：multi-source driver UI integration
是最高频 TD 可见 AnimaRbfSolver 复刻缺口。TDs working with cross-bone
driven rigs (e.g. shoulder + elbow → deltoid aux) 当前**无法**使用
v5——这是阻塞实际生产工作流的硬伤，优先级高于 schema-thrash 优化。

**代价（已被用户接受）**：~30 LoC chained-migration backcompat 代码
in M4.1（处理 pre-M_B24 节点同时承受 driver schema + solverType schema
双次升级链）；product-of-paths 复杂度小幅增加。

**规划层级失职追责**：原 H.1 反转建议来自计划者（schema-thrash 最小化
工程逻辑），但忽略了"复刻先于优化、用户实际工作流先于内部 schema
洁癖"的 v5 首要原则。用户审视后裁决 H.2，规划层级承担 ~30 LoC 工程
代价作为责任体现。

#### 完整度速览表

| # | 铁律 | v5 设计评级 | 当前状态 | 实施 commit | 子任务归属 |
|---|---|---|---|---|---|
| **B1** | 六类 Solver | ❌ 致命 | **❌ 仅 RBF + Vector-Angle 二类** (`type` + `rbfMode` 双 enum 切 2 路径) | —— | **M4** (a/b/c/d) |
| **B2** | 多源驱动异构 | ⚠️ 高 | **✅ complete (Generic + Matrix + UI + downstream + Generic-mode multi-source mirror)** *(Matrix-mode multi-source mirror DEFERRED to M_B24c2)* | M_B24a1 `d73d6b9` + a2-1 `a43f0de` + a2-2 `1719056` + b1 `2da2059` + b2 `000d127` + d `62fa87c` + d_matrix_followup `c7fd289` + c (this commit, Generic-mode multi-source mirror) | M_B24 (a1+a2+b+d+d_matrix_followup+c) |
| B3 | 输入编码枚举 5 档 | ❌ 致命 | **✅ 完整** | M2.1a (`8541d4d`-pre) / M2.1b | 已完成 |
| **B4** | 输入 Quat / 输出 Euler 分离 | ❌ 高 | **✅ complete (full)** | M_B24a1 `d73d6b9` (schema) + a2-2 `1719056` (JSON versioned) + b1 `2da2059` (UI combo) + b2 (this commit, T_V5_PARITY_B4_LIVE #30) | M_B24 (a1+a2-2+b1+b2) |
| B5 | Driver Clamp | ❌ 致命 | **✅ 完整** (`clampEnabled` + `clampInflation` + `poseMinVec/MaxVec`) | M1.3 | 已完成 |
| B6 | Output Base Value + Scale | ❌ 致命 | **✅ 完整** (`baseValue[]` + `outputIsScale[]`) | M1.2 | 已完成 |
| **B7** | 按补助骨拆分工具 | ❌ 中 | **⚠️ 仅 `core_profile.py:358` split 建议字符串; ❌ 无实际拆分** | (M3.5 part) | **M_B7** |
| B8 | Pose 精简 | ❌ 高 | **✅ 完整** (`core_prune.py` analyse_node) | M3.1 | 已完成 |
| B9 | Maya↔引擎一致性 | ⚠️ 高 | **✅ 完整** (local Transform path + 双存储) | M2.3 | 已完成 |
| B10 | local Transform 双存储 | ❌ 中 | **✅ 完整** (`poseLocalTransform` compound) | M2.3 | 已完成 |
| **B11** | GUI 视口实时回写 | ⚠️ 中 | **⚠️ algo 完整但 scriptJob attributeChange headless 不触发** | M3.4 (`8541d4d`) | **M_B11** |
| B12 | GUI 清理未用 | ❌ 中 | **✅ 完整** (M3.1 + M3.5 health checks) | M3.1 + M3.5 | 已完成 |
| B13 | GUI 镜像 | ❌ 高 | **✅ 完整** (`core_mirror.py` L/R + 自定义命名规则) | M3.2 | 已完成 |
| **B14** | GUI driver 锁豁免 | ⚠️ 低 | **⚠️ algo 已 work** (`recall_pose` 断连-重连) **❌ UI 锁状态提示缺失** | (M3.6 partial) | **M_B14** |
| B15 | GUI Import/Export JSON | ❌ 高 | **✅ 完整** (`core_json.py` + addendum schema 锁定) | M3.3 | 已完成 |

---

### §M_PARITY_AUDIT.B1 — 六类 Solver（**致命**, 归属 M4）

**当前**: `RBFtools.h:342-345` 仅 `MObject rbfMode` + `MObject type` 二 enum.
`RBFtools.cpp:1145-1147` compute() 主分支:

```cpp
if (typeVal == 0) { /* Vector Angle */ }
if (typeVal == 1) { /* RBF */ }
else if (rbfModeVal == 1) { /* RBF sub-mode */ }
```

**仅 2 类** (Vector-Angle + RBF). AnimaDriver 6 类: RBFSolver / Jiggle /
AimConstraint / + 3 待定 (BlendShape proxy / Custom callback / Combiner).

**缺什么**:
1. 新 `MObject solverType` enum (值: `0=RBF / 1=VectorAngle / 2=Jiggle /
   3=Aim / 4=BlendShape / 5=Custom`) — 当前 2-enum 系统须重构合并
2. compute() 六分支: Jiggle solver (Verlet + spring + damping) +
   Aim solver (vector → quaternion) 全新算法
3. Jiggle 状态字段 (C++ 私有 instance member): `jiggleStiffness` /
   `jiggleDamping` / `jiggleRestVel` / dt 保护
4. Aim 字段 (MObject): `aimVector` / `upVector` / `worldUpType`
5. UI: solverType combo + 模式特定 inspector 折叠面板
6. JSON schema (`core_json.py`): solverType 字段 + 双向序列化
7. Mirror (`core_mirror.py`): Jiggle rest velocity 不镜像 / Aim vector 镜像

**M4 scope 估算**: ~800-1200 LoC C++ + ~300-500 Python + ~400-600 测试
= **~1500-2300 LoC 总**.

#### M4 sub-commit lock (pre-approved during M_PARITY_AUDIT, 加固 5)

```
M4.1 — solverType enum + RBF/VA 双 enum 重构合并到单 enum
       (zero algo change; pure schema refactor + auto-migration)
M4.2 — Jiggle solver (Verlet integration + dt protection)
M4.3 — Aim solver (vector → quaternion target)
M4.4 — UI solver type combo + JSON schema + Mirror adapt

Each ≤ 800 LoC hard limit (sustained from M1.5.3 红线 7 重批).
M4.1 must include legacy-node auto-migration:
  type=0,rbfMode=*  → solverType=1 (VectorAngle)
  type=1,rbfMode=0  → solverType=0 (RBF)
  type=1,rbfMode=1  → solverType=0 (RBF, sub-mode flag preserved)
with cmds.warning per F.3 first-load-of-legacy-node path.

M4.1 legacy node migration MUST handle TWO paths (per H.2 user
override 2026-04-26):
  - v4 / v5-pre-M_B24 nodes (type+rbfMode → solverType only;
                              ALSO inherit M_B24a's driverList[0]
                              → driverSource[0] migration since
                              that node has not been touched by
                              M_B24a load-time hook yet)
  - v5-M_B24 nodes (driverSource already migrated by M_B24a load
                    hook; still need type+rbfMode → solverType)
  Chained migration logic: ~30 LoC additional backcompat beyond
  what would be needed under H.1; accepted per user override
  (2026-04-26). The chain order on first-load of a v4 / v5-pre-
  M_B24 node must be: M_B24a's driver migration FIRST, then M4.1's
  solverType migration — sequential, single cmds.warning summary
  citing both upgrades in one message.
```

M4 现状核查 (verify-before-design 第 13 次使用) 仅消费此 lock + 给 (A)-(N)
决议 + scope 实测; 不再重新讨论拆分形态.

---

### §M_PARITY_AUDIT.B2 — 多源驱动异构（**高**, 归属 M_B24）

**当前**: `RBFtools.h:299` `MObject driverList` 已声明 + multi.
`RBFtools.h:297` `MObject driverIndex` 索引器存在. 但:

```bash
$ grep -rE "driverSource|driver_source|add_driver_source" \
       modules/RBFtools/scripts/
（空输出 — UI / core 完全未消费 multi driver）
```

**缺什么**:
1. C++ schema 扩展 (PART C.2.1 设计):
   - `driverSource` compound multi
   - `driverSource_node` (MMessage — 目标节点)
   - `driverSource_attrs` (MStringArray — 属性名列表)
   - `driverSource_weight` (double[] — 该源在输入向量中的权重)
   - `driverSource_encoding` (per-source enum: Raw/Quat/BendRoll/ExpMap/Euler)
2. compute() 内 driverList[] 聚合循环 (当前仅消费 driverList[0])
3. core.py: `add_driver_source` / `remove_driver_source` /
   `read_driver_info_multi`
4. UI: 多驱动 list editor (增/删/重排/per-source 编码下拉)
5. JSON schema 扩展: `drivers: [{node, attrs, weight, encoding}, ...]`
   替代当前单 driver 字段
6. **(F.3) 旧节点自动迁移** (加固 2 永久保留):
   - `_migrate_legacy_single_driver(node)` 函数 in core.py
   - openFile 时探测旧 schema (无 `driverSource` 但有 `driverList`)
   - 升级为 1-driver list + `cmds.warning` 提示
   - **永久守护**: `T_M_B2_MIGRATION_BACKCOMPAT` (M_B24 子任务定义)
     source-scan core.py 含 `_migrate_legacy_single_driver` 函数 +
     函数体含 `cmds.warning`. **此守护永久不删** — 任何未来"瘦身"
     须在 addendum 显式记录"v5.X 起停止支持 v4 / v5-pre-B24 节点 .ma
     升级"才允许删
7. Mirror / Pruner / Profiler / JSON IO 全适配

**M_B24 scope** (B2 + B4 合并): ~150-250 C++ + ~400-600 Python +
~250-400 测试 = **~800-1250 LoC**.

#### M_B24 sub-commit lock (pre-approved)

```
M_B24a (backend):  schema (driverSource compound + outputEncoding
                   enum) + compute() 聚合 + core multi-source API
                   (add_driver_source / remove_driver_source /
                   read_driver_info_multi) + JSON schema +
                   auto-migration core function (cmds.warning per F.3)
                   ≤ 800 LoC hard limit

M_B24b (frontend): ★ UI integration is THIS subtask's primary
                   deliverable per user override 2026-04-26.
                   Backend completion ≠ subtask completion;
                   UI multi-driver list editor + outputEncoding
                   combo + Mirror/Pruner/Profiler/JSON IO
                   downstream adapters MUST land in same series.
                   ≤ 800 LoC hard limit
```

**M_B24a must include T_M_B2_MIGRATION_BACKCOMPAT permanent
guard** (加固 2: source-scan `core.py` 含
`_migrate_legacy_single_driver` 函数 + 函数体含 `cmds.warning`.
**永久不删** — any future "leanup" wishing to delete must record
"v5.X 起停止支持 v4 / v5-pre-M_B24 节点 .ma 升级" in addendum
explicitly).

**Sequence priority** (per user override 2026-04-26): M_B24 lands
**before** M4. M_B24a/b ≤ 800 LoC hard limit is **non-negotiable** —
任何"UI 复杂导致超限"必须停下报告再批 (拆 M_B24b 为
M_B24b1/b2 等), 不允许放宽上限.

#### B2 EMPIRICAL CORRECTION (2026-04-26, M_B24a1 F2 verify-before-design)

**Original §M_PARITY_AUDIT.B2 status above states**: "C++ `driverList`
exists but UI/core single-driver". This phrasing implies BOTH layers
are single-driver. F2 in M_B24a1 现状核查 (verify-before-design 13th
use) empirically refutes the C++ side:

[RBFtools.cpp:1967-2000](source/RBFtools.cpp:1967) compute() contains
a real multi-driver iteration:

```cpp
unsigned driverCount = driverListHandle.elementCount();
for (d = 0; d < driverCount; d++) {
    driverListHandle.jumpToArrayElement(d);
    MDataHandle driverInputHandle = driverListIdHandle.child(driverInput);
    ...
}
```

**Corrected semantics**: "C++ multi-driver loop ALREADY iterates
`driverList[*]`; the bottleneck is Python `read_driver_info()`
returning a single tuple + 14 callers (controller.py × 5,
core.py × 3, core_json.py / core_neutral.py / core_profile.py /
core_prune.py × 2 / live_edit_widget.py × 2) all making single-
driver assumptions."

**Implication for M_B24**: backend work augments `driverList` with a
companion `driverSource[*]` compound carrying per-driver metadata
(weight, encoding) — NO compute() iteration rewrite needed. The
"~30 LoC chained backcompat" (H.2 user override) cost remains; the
C++ surface is smaller than originally feared.

This correction is the M_B24a1 verify-before-design highest-value
finding: it cut the M_B24a backend C++ scope estimate from ~300-400
LoC down to ~130 LoC without changing functional outcome.

---

### §M_PARITY_AUDIT.B4 — 输出编码（**高**, 合并入 M_B24）

**当前**: `grep outputEncoding source/* modules/.../scripts/` → **0 hits**.
`output[]` 仅 `double` 输出, 无编码概念.

**缺什么**:
- `MObject outputEncoding` enum (值: `0=Euler / 1=Quaternion / 2=ExpMap`)
- compute() 输出端编码反变换 (Quat → Euler 默认; Euler 是 v4 用户期望)
- UI: outputEncoding combo (与 M_B24a inputEncoding combo 同 widget pattern)
- JSON schema 加段
- Mirror / Pruner 适配

**B4 scope**: ~80-120 C++ + ~150 Python + ~100 测试 = **~350-400 LoC**.

**合并依据**: B4 与 B2 同属 schema 扩展周期 (driverSource_encoding 是
per-source 输入编码; outputEncoding 是节点级输出编码). 一次性扩 schema
省迁移代码. 命名 `M_B24` 显式承认双 B# 覆盖.

---

### §M_PARITY_AUDIT.B7 — 按补助骨拆分工具（**中**, 归属 M_B7）

**当前**: `core_profile.py:358-379` 给文字"split 建议":

```
[WARN] Node size triggers split suggestion:
       N=2 (M~120): ~5.18 ms / node
       ...
Splitting strategy is rig-semantic and must be decided by the user
— Profiler does not auto-split or suggest specific attribute groupings.
```

**仅文字提示, 无实际拆分操作**. Profiler 自己声明 "does not auto-split"
是设计约束 — 但 v5 设计 B7 要求"新增 Split by Aux Bone 辅助工具".

**缺什么**:
1. 新建 `core_split.py` 模块: `split_by_attribute_groups(node, groups,
   ...) -> [new_nodes]`
2. 算法: 按 user 指定的 attr 分组创建 N 子节点; 每子节点保留对应输出
   channel; poses 复制 (每子节点保 attr 子集); driverInput 重连
3. UI 工具按钮: 弹窗让用户拖拽分组 attr 到子组 → 调用 split
4. 测试: split 后 N 子节点 compute() 输出之和 ≈ 原节点 compute() 输出
   (fp64 误差 < 1e-12)

**M_B7 scope**: ~200 Python core_split + ~150 UI + ~150 测试 = **~500
LoC**, **0 C++** (纯 Maya cmds operations + Python wiring).

**M_B7 单 commit** (无内部拆分; ≤800 LoC 单 commit 红线天然满足).

---

### §M_PARITY_AUDIT.B11 — GUI 视口实时回写（**中**, 归属 M_B11）

**当前**: `core_live.py` 算法实现完整 (M3.4, commit `8541d4d`),
但 **scriptJob attributeChange headless 不触发** — 此事实记录于
§M1.5.1.X Blocker Matrix Row 3, 标 "deferred to M5 GUI long-tail
manual verification".

**M_B11 = M3.4.7 spillover 三件事 (E.2 决议)**:
1. 真实 scriptJob attributeChange 集成 (非 mock; 需 GUI Maya
   session 手动验证)
2. `parent=` cleanup (scriptJob 在 widget 销毁时正确取消订阅)
3. drag throttle (viewport drag 期间限频, 防止每帧触发 train)

**M_B11 scope**: ~50-100 Python (scriptJob 实际订阅 + parent= 包装) +
~50 UI 调整 + 手动验证 checklist (addendum 段) = **~150 LoC + 文档**.

GUI Maya 必跑 (headless 不达). 测试是"半自动+手动":
- T_M_B11_LIVE_INTEGRATION 守护 source-scan (确认 scriptJob 实际调用
  存在 + parent= 包装存在)
- 实际行为靠手动 ✓ checklist (addendum §M_B11 章节最后)

**Blocker Matrix Row 3 在 M_B11 commit 中标 RESOLVED**.

---

### §M_PARITY_AUDIT.B14 — driver 锁豁免 UI 提示（**低**, 归属 M_B14）

**当前**: `core.py:2258` `recall_pose` 体使用 `_safe_disconnect_incoming`
+ `connectAttr` 重连模式 — **algo 实证已对 locked driver 生效**
(C++ 仍可写 disconnected attr). v5 设计 B14 评级 "⚠️ 低", **algo 已
work**, 仅缺 UI 提示.

**缺什么**:
1. UI: 对每个 driver 显示锁状态徽标 (lock icon if `cmds.getAttr(plug,
   lock=True)`)
2. tooltip: "此 driver 已 lock, recall pose 时通过断连-重连绕开"
3. 可选 (M_B14b 内): 批量解锁按钮 (用户主动解锁则提示移除断连-重连保护)

**M_B14 scope**: ~80-120 Python (UI lock 状态查 + 显示) + ~50 测试
= **~150 LoC**, **0 C++**.

**M_B14 单 commit** (≤800 LoC 红线天然满足).

---

### §M_PARITY_AUDIT.completed — 已完成项简核 (G.1)

| # | 实施 commit | 验证测试 | 简短证据 |
|---|---|---|---|
| B3 | M2.1a + M2.1b | test_m2_1a_encoding.py / test_m2_1b_swing_twist.py | RBFtools.h:283 inputEncoding + 5 encode* 静态函数 (cpp:2493-2516) |
| B5 | M1.3 | test_m1_3_clamp.py | RBFtools.h:277-278 clampEnabled+clampInflation + h:393-394 poseMinVec/MaxVec |
| B6 | M1.2 | test_m1_2_baseline.py | RBFtools.h:276+279 baseValue + outputIsScale |
| B8 | M3.1 | test_m3_1_prune.py | core_prune.py analyse_node (重复/冗余/常量/冲突 4 类检测) |
| B9 | M2.3 | test_m2_3_local_transform.py | poseLocalTransform compound 在 compute() 内被消费 |
| B10 | M2.3 | (同 B9) | RBFtools.h:324-326 poseLocalQuat/Translate/Scale |
| B12 | M3.1 + M3.5 | test_m3_1_prune.py + test_m3_5_profile.py | analyse_node 计 redundant_inputs / constant_outputs / conflict_pairs |
| B13 | M3.2 | test_m3_2_mirror.py | core_mirror.py L/R + 自定义命名规则 |
| B15 | M3.3 | test_m3_3_jsonio.py | core_json.py + addendum §M3.3 schema 锁定 |

---

### §M_PARITY_AUDIT.v5.0-final-criteria — 验收门槛 + STUB

**v5.0 final 验收门槛 = 15/15 ✅, 不可妥协** (本节红线 5).

**T_V5_PARITY_COMPLETE 守护 STUB** (加固 1 — markdown 文档化, **不写
.py 文件**):

```python
# tests/test_v5_parity_complete.py
# This file does NOT exist as of M_PARITY_AUDIT commit (2026-04-26).
# Each B# sub-task lands its own test_v5_parity_b<N>.py with the
# corresponding sub-test enabled. v5.0 final commit consolidates
# (or merges into single file) and flips all 6 to live.

class TestV5ParityComplete(unittest.TestCase):
    """v5.0 final acceptance gate. All 6 sub-tests MUST pass
    before the v5.0 git tag is allowed."""

    def test_b1_six_solvers(self):
        """M4 deliverable: solverType MObject enum exists with
        values 0..5 + compute() has 6 dispatch branches +
        legacy node auto-migration from type+rbfMode covers all
        4 legacy combinations."""
        # Enabled by M4.4 commit; until then skipTest.

    def test_b2_multi_source_driver(self):
        # LIVE per M_B24b2 commit (v5.0 FINAL CONSTITUTIONAL EVENT 2/6,
        # 1/2 sub-criteria activated). Implemented at
        # tests/test_v5_parity_b2_b4.py::TestV5ParityB2Live as
        # T_V5_PARITY_B2_LIVE (#29) — 4 sub-checks: core API
        # importable + DriverSourceListEditor importable +
        # DriverSourceListEditor subclasses _OrderedListEditorBase +
        # read_driver_info_multi docstring references
        # §M_B24b2.mirror-deferred-rationale.

    def test_b4_output_encoding(self):
        # LIVE per M_B24b2 commit (v5.0 FINAL CONSTITUTIONAL EVENT 2/6,
        # 2/2 sub-criteria activated). Implemented at
        # tests/test_v5_parity_b2_b4.py::TestV5ParityB4Live as
        # T_V5_PARITY_B4_LIVE (#30) — 4 sub-checks:
        # OutputEncodingCombo importable + EXPECTED_NODE_DICT_KEYS
        # contains "output_encoding" + RBFtools.h declares
        # MObject outputEncoding + RBFtools.cpp adds it via
        # addAttribute(outputEncoding).

    def test_b7_split_tool(self):
        """M_B7 deliverable: core_split.py module exists with
        split_by_attribute_groups(node, groups, ...) function;
        UI has Split by Aux Bone button; round-trip test
        (split then sum) preserves output to fp64 < 1e-12."""
        # Enabled by M_B7 commit.

    def test_b11_live_integration(self):
        """M_B11 deliverable: scriptJob attributeChange has real
        subscription (not mock); parent= widget cleanup is wired;
        viewport drag throttle is in core_live; manual checklist
        in addendum §M_B11 has been ticked by the implementer."""
        # Enabled by M_B11 commit.

    def test_b14_lock_indicator(self):
        """M_B14 deliverable: UI shows lock icon for locked driver
        plugs; tooltip explains disconnect-reconnect bypass; lock-
        state probe (cmds.getAttr lock=True) is used in driver
        list refresh path."""
        # Enabled by M_B14 commit.
```

**v5.0 final commit 流程**:
1. 各 B# 子任务在自己 commit 内新建 `test_v5_parity_b<N>.py`
   + 启用对应 sub-test (实际断言而非 skipTest)
2. v5.0 final commit 将 6 个文件合并为 `test_v5_parity_complete.py`
   (或保持 6 文件分散; 可选)
3. 所有 6 sub-test 全绿 + git tag `v5.0`
4. 任一红 → 不允许打 tag, 修复后再打

---

### §M_PARITY_AUDIT.subtask-sequence — 后续 5 子任务顺序 + 依赖图

**Sequence decision history**:

- ~~H.1 (planner-suggested, rejected): M4 → M_B24 → M_B7 → M_B11 → M_B14~~
  ~~Schema-thrash minimization argument; rejected by user 2026-04-26.~~
- **H.2 ✅ LOCKED (user override 2026-04-26): M_B24 → M4 → M_B7 → M_B11 → M_B14**

**User business priority override**: multi-source driver UI
integration is the highest-frequency TD-visible AnimaRbfSolver
gap. TDs working with cross-bone driven rigs (e.g. shoulder +
elbow → deltoid aux) cannot use v5 currently. Unblocking
real-world workflows is prioritized over schema-thrash
optimization; ~30 LoC double-migration overhead is accepted.

```
M_B24 (B2 + B4)              [M_B24a, M_B24b]
  ↓ schema 扩展 driverSource + outputEncoding 完成
  ↓ TD 多源驱动 UI 解锁 (primary deliverable per user override)
M4 (B1)                      [M4.1, M4.2, M4.3, M4.4]
  ↓ schema 扩展 solverType 完成
  ↓ M4.1 chained migration: pre-M_B24 nodes hit type+rbfMode
                            → solverType + driverList → driverSource
                            sequentially (~30 LoC backcompat)
M_B7  (split tool)           [single commit]
M_B11 (GUI live)             [single commit; depends on Maya GUI session]
M_B14 (lock indicator)       [single commit]
  ↓ 15/15 ✅
v5.0 final commit            [test_v5_parity_complete.py 启用 6 sub-test]
  ↓ 全绿
git tag v5.0
```

**总估算**:

| 子任务 | LoC | C++ | sub-commits |
|---|---|---|---|
| M4 (B1) | 1500-2300 | 800-1200 | 4 (a/b/c/d) |
| M_B24 (B2+B4) | 1150-1650 | 230-370 | 2 (a/b) |
| M_B7 | 500 | 0 | 1 |
| M_B11 | 150 + 文档 | 0 | 1 |
| M_B14 | 150 | 0 | 1 |
| v5.0 final commit | ~50 (test merge) | 0 | 1 |
| **总** | **~3500-4800** | **~1030-1570** | **~10 commits** |

**单 executor 顺序估**: ~12-18 工作日.

---

### §M_PARITY_AUDIT.schema-migration-track — Schema 演进锚 (加固 3)

**v5.0 final 路径上的 schema 改动是 breaking change 链**. 下游 v4 / v5
pre-final 用户 .ma 文件须经迁移. 演进顺序:

```
v5.0-pre-M_B24 → v5.0-M_B24 : add driverSource compound (multi)
                              + outputEncoding enum
                              (legacy nodes auto-migrate
                               driverList[0] → driverSource[0],
                               outputEncoding default = Euler;
                               F.3 + 加固 2 backcompat permanent)

v5.0-M_B24     → v5.0-M4    : add solverType MObject enum (0..5)
                              (legacy nodes auto-migrate from
                               type+rbfMode; CHAINED migration:
                               pre-M_B24 nodes hit BOTH migrations
                               sequentially — ~30 LoC handles
                               the chain in M4.1 per user override
                               2026-04-26; `type` + `rbfMode`
                               deprecated but schema-retained for
                               read-back compat)

v5.0-M4        → v5.0 final : NO further schema changes
                              (M_B7 / M_B11 / M_B14 are pure
                               tool / UI additions; zero schema delta)
```

任何审查者 (含未来 v5.x post-final 执行者) 看 git log 即可机械重建
schema 演进链. 上游 schema 字段任何后续改动 (v5.x post-final) 必须
向本演进锚追加新行 + 提供迁移路径 + cmds.warning.

---

### §M_PARITY_AUDIT.guards-summary — 永久守护规划

| # | 守护名 | 子任务 | 启用时机 |
|---|---|---|---|
| 既有 #17-#22 | (略) | M1-M3 + M1.5.1/1.5.1b/1.5.2 | 已启用 |
| 候选 | T_M4_SOLVER_TYPE_ENUM_PRESENT | M4.1 | M4.1 commit |
| 候选 | T_M4_LEGACY_MIGRATION_BACKCOMPAT | M4.1 | M4.1 commit (永久, 同 B2 backcompat 范式) |
| 候选 | T_M4_JIGGLE_VERLET_DT_PROTECTED | M4.2 | M4.2 commit |
| 候选 | T_M4_AIM_QUAT_NORMALIZED | M4.3 | M4.3 commit |
| 候选 | **T_M_B2_MIGRATION_BACKCOMPAT** | M_B24a | M_B24a commit (永久, 加固 2) |
| 候选 | T_M_B24_OUTPUT_ENCODING_PRESENT | M_B24a | M_B24a commit |
| 候选 | T_M_B7_SPLIT_ROUNDTRIP | M_B7 | M_B7 commit |
| 候选 | T_M_B11_LIVE_INTEGRATION | M_B11 | M_B11 commit |
| 候选 | T_M_B14_LOCK_INDICATOR | M_B14 | M_B14 commit |
| **#23** | **T_V5_PARITY_COMPLETE** | v5.0 final | v5.0 final commit (本节 STUB 现化, 6 sub-test) |

**永久守护数预估在 v5.0 final 时**: 22 (现) + 9 (上表候选) + 1 (#23) =
**32 条**.

---

### §M_PARITY_AUDIT.audit-completeness-rules — 审计规则锁

本节是 v5.0 final 路径的"宪法":

1. **任何 B# 推迟到 v5.x post-final 是规划错误, 须重审 roadmap**
   (本节红线 5)
2. **任何 sub-task 完成后, 该 sub-task commit 必须更新本节
   §M_PARITY_AUDIT.0 速览表对应 B# 行**: ⚠️/❌ → ✅, 子任务归属列
   改为该 commit 的 hash 或子任务名 + commit hash
3. **本节自身只允许 v5.0 final commit 添加"all green confirmation"
   段** — 在此之前不允许扩 §M_PARITY_AUDIT 主体内容 (子节落地放
   各自 §M_B<N> commit)
4. **schema-migration-track 段每次 schema 改动 commit 必须追加新行**
   (加固 3)
5. **T_V5_PARITY_COMPLETE 6 sub-test 的启用顺序 = 子任务完成顺序**;
   不允许跳过 (例如不允许在 M4 未完成时启用 b1 sub-test)

---

## §M_B24d — Multi-source data path wiring (B2 corrective)

> **PROJECT-CONSTITUTIONAL-EVENT** (2026-04-27):
>
> This commit is the v5 path's first **functional correction**
> sub-task — distinct from PROJECT-CONSTITUTIONAL-EVENT (M_B24a2-2,
> first legal SCHEMA_VERSION bump) and v5.0 FINAL CONSTITUTIONAL
> EVENT (M_B24b2, first 2/6 acceptance gate activation).
>
> **What happened**: M_B24a/b 5 commits delivered the metadata
> layers (C++ schema + Python core API + JSON versioned schema +
> UI widgets + 3 active downstream adapters) but `add_driver_source`
> only wrote `driverSource[d]` metadata — the actual data
> connection from `<driver>.<attr>` to `<shape>.input[base+i]`
> was never established. TDs adding multi-driver sources via the
> UI saw zero RBF compute() response: B2 was structurally complete
> but functionally broken.
>
> **Verify-before-design 范式 self-correction**: M_B24a2-1 F2 found
> `driverList[]` was already multi-iterated by C++ compute() but
> did NOT ask "how does Python populate `driverList[d].driverInput`
> or `shape.input[]`?" The grep would have shown F2's actual blind
> spot: `wire_driver_inputs` (legacy, single-driver, i=0 起步) was
> the only Python-side wiring path; `add_driver_source` reused
> none of it. **Future verify-before-design must include "data
> path tracing" alongside "metadata grep"** — recorded as PROJECT
> METHODOLOGY in §M_B24d.lesson-learned.
>
> **Audit trail counter atomicity**: this commit lands all four
> atomic steps in a single push so PERMANENT guards never go red
> mid-history:
>   (1) §M_PARITY_AUDIT.0 11/15 audit trail records the correction
>       (B2 status precision-fixed: "complete (full)" → "complete
>       (Generic) + Mirror DEFERRED + Matrix DEFERRED")
>   (2) §M_PARITY_AUDIT.B2 row updated with deferred caveats
>   (3) New §M_B24d section (this) + §M_B24d.matrix-mode-deferred
>       sub-section
>   (4) #31 T_M_B24D_DATA_PATH_WIRED + #29 sub-check (e) extension

### §M_B24d.scope

| Layer | Change | LoC |
|---|---|---|
| `core.py` | `_is_matrix_mode` helper + `_count_existing_input_attrs` helper + `add_driver_source` data-path wiring (Generic mode `input[base+i]` append) + atomic fail-soft rollback + `remove_driver_source` data-path disconnect + Matrix mode NotImplementedError defer | ~140 |
| `tests/test_m_b24d_data_path.py` (new) | #31 T_M_B24D_DATA_PATH_WIRED 4 source-scan sub-checks + 3 mock-pattern tests (Matrix defer / atomic rollback / Generic append) | ~210 |
| `tests/test_v5_parity_b2_b4.py` (modified) | #29 sub-check (e) extension — add_driver_source body must contain `connectAttr` to `.input[` | ~20 |
| `addendum_20260424.md` | §M_B24d main section + §M_B24d.matrix-mode-deferred sub-section + audit trail counter rollback then advance | ~180 |

### §M_B24d.atomic-fail-soft

`add_driver_source` now uses two-phase write with rollback:

1. **Phase 1**: write `driverSource[idx]` metadata (message
   connection + attrs + weight + encoding) — existing path,
   unchanged
2. **Phase 2**: append data-path connections
   `<driver>.<attr> → <shape>.input[base+i]` for each attr

If any Phase 2 `connectAttr` raises, the inner `except` block:
- disconnects any partial `input[]` connections it had made so far
- calls `cmds.removeMultiInstance(driverSource[idx], b=True)` to
  delete the metadata entry
- emits `cmds.warning` and re-raises so callers see the failure

The node never holds a half-state where `driverSource[idx]` exists
but `input[]` is partially wired.

### §M_B24d.matrix-mode-deferred

> **STATUS UPDATE**: RESOLVED by §M_B24d_matrix_followup (commit
> following `62fa87c`). The 0-hits gap below is now closed —
> `_wire_matrix_mode_data_path` in core.py establishes the
> `driver.worldMatrix[0] -> shape.driverList[d].driverInput`
> connection inside `add_driver_source` Matrix branch. Original
> rationale preserved verbatim for audit-trail integrity.

Per F2 of M_B24d 现状核查: `grep -rn "connectAttr.*driverList\[" modules/RBFtools/scripts/RBFtools/` returns **0 hits**. The Python codebase has never connected `driverList[d].driverInput` (the matrix-mode driver path); only `wire_driver_inputs` (Generic mode `input[i]` flat scalar) exists.

`add_driver_source` therefore:

- **Generic mode** (type=1 + rbfMode=0 — most common RBF setup):
  data-path wiring fully implemented (this commit)
- **Matrix mode** (type=1 + rbfMode=1):
  raises `NotImplementedError` with explicit message pointing TDs
  at `M_B24d_matrix_followup` (v5.x post-final sub-task)
- **Vector-Angle mode** (type=0): not RBF; multi-source semantics
  not applicable

This is the same "transparent boundary" pattern Mirror DEFERRED
uses (§M_B24b2.mirror-deferred-rationale): TDs see an explicit
failure rather than a silent half-state, and the addendum anchor
gives future implementers the exact roadmap entry to consult.

### §M_B24d.legacy-vs-new-wiring

After M_B24d, two Python-side wiring paths coexist for `shape.input[]`:

- **Legacy single-driver** (`core.wire_driver_inputs`): always
  starts at `input[0]` and overwrites. Used by `apply_poses` and
  the legacy single-driver flow.
- **New multi-source** (`core.add_driver_source` Generic mode):
  appends at `input[base..base+n]` where base is the current
  populated index count.

**Caller contract**: if `wire_driver_inputs` runs after one or
more `add_driver_source` calls, it will overwrite the multi-source
appends starting at `input[0]`, breaking the multi-source state.
This is documented; controller-layer migration to use only
`add_driver_source` is part of M_B24c (controller migration sub-task).

### §M_B24d.permanent-guards

Permanent guards: 31 → 32.

- **T_M_B24D_DATA_PATH_WIRED (#32)** — 4 sub-checks (source-scan
  core.py):
  (a) `add_driver_source` body contains connection to `input[`
  (b) `_count_existing_input_attrs` (or equivalent base helper) defined
  (c) `removeMultiInstance` rollback path present in body
  (d) `_is_matrix_mode` (or equivalent mode probe) defined

- **T_V5_PARITY_B2_LIVE (#29) sub-check (e) extension**:
  `add_driver_source.__source__` must contain `.input[` and
  `connectAttr` (data-path wiring corrective).

### §M_B24d.empirical-baseline (2026-04-27)

| Env | Pre-d (post-hotfix) | Post-d |
|---|---|---|
| Pure-Python | 511 OK (skip 3) | 519 OK (skip 3) |
| mayapy 2025 | 511 ran 469 pass 42 skip | 519 ran 474 pass 45 skip |

mayapy skip count change: 42 → 45 (+3). All three are mock-only
`@skipIf(_REAL_MAYA)` test methods in `test_m_b24d_data_path.py`
(MatrixModeDeferred / AtomicFailSoft / GenericModeAppend) — same
M3.x mock-pattern convention as M_B24b2's +5 baseline shift.
**M1.5.3 PAUSED honored**: no plugin-load skips added; per the
forward-compat-corrected red line 13, mock-pattern legitimate
skip naturally accumulates.

### §M_B24d.lesson-learned

**For future verify-before-design rounds (M4 / M_B7 / M_B11 /
M_B14 / v5.x post-final)**:

When grep finds an existing data-flow path (e.g. C++ `for d <
driverCount`), DO NOT stop at "the iteration exists". The next
mandatory question is: **how is the data populated upstream?**

The M_B24a2-1 F2 grep showed C++ compute() iterating
`driverList[]`. That confirmed read-side multi-iteration but said
nothing about write-side. The hidden assumption — "if iteration
exists, population must exist" — is wrong; the write-side path
was `wire_driver_inputs` to `input[i]` (Generic), not
`driverList[d].driverInput`. M_B24d corrects this by adding
`connectAttr` to `input[base+i]` from `add_driver_source`.

**verify-before-design extended protocol**:
  1. grep the read side ("how is X consumed downstream?")
  2. **grep the write side ("how is X populated upstream?")**
  3. trace any indirection (e.g. message attrs vs. data attrs)
  4. only then call the surface "fully wired"

Step 2 is the M_B24d-driven addition.

---

## §M_B24d_matrix_followup — Matrix mode driverList wiring

> **PROJECT-CONSTITUTIONAL-EVENT** (2026-04-27):
>
> First Python-side implementation of `driverList[d].driverInput`
> wiring in the project's history. Pre-v5 Matrix mode required
> users to manually `connectAttr` the driver matrix in MEL; this
> commit promotes the operation to a first-class
> `add_driver_source` code path with atomic fail-soft + post-
> connect verification + mode-exclusion semantic.
>
> verify-before-design 19th use, sustaining the
> §M_B24d.lesson-learned PROJECT METHODOLOGY: read side math
> chain (cpp:2113) dictates write side choice
> (`worldMatrix[0]` not `.matrix`).

### §M_B24d_matrix_followup.scope

| Layer | Change | LoC |
|---|---|---|
| `core.py` | `_count_existing_driver_list` + `_has_generic_wiring` + `_has_matrix_wiring` + `_resolve_driver_rotate_order` + `_wire_matrix_mode_data_path` + `_unwire_matrix_mode_data_path` 六 helper + `add_driver_source` Matrix branch (replaces NotImplementedError) + mode-exclusion RuntimeError + `remove_driver_source` Matrix unwire branch | ~165 |
| `tests/test_m_b24d_matrix_followup.py` (new) | 5 source-scan + 4 add-wire + 1 verify-guard + 1 atomic rollback + 2 mode-exclusion + 1 remove-unwire = **13 tests** | ~330 |
| `tests/test_m_b24d_data_path.py` (modified) | #32 sub-check (a) extension (Generic OR Matrix wiring valid) + obsolete `TestM_B24D_MatrixModeDeferred` class removed | ~30 |
| `addendum_20260424.md` | this section + §M_B24d.matrix-mode-deferred RESOLVED stamp + §M_PARITY_AUDIT.B2 row update | ~140 |

### §M_B24d_matrix_followup.matrix-vs-worldmatrix

> **(A.3 → A.2) PIVOT** (planner override 2026-04-27): the
> original M_B24d_matrix_followup design (A.3) defaulted to
> `driver.matrix` (local). The verify-before-design read-side
> grep refutes this.

The C++ compute() math chain at [RBFtools.cpp:2113](source/RBFtools.cpp:2113):

```cpp
MTransformationMatrix transMatDriver =
    driverMat * driverParentMatInv * jointOrientMatInv;
```

`driverParentMatInv = dagPath.exclusiveMatrixInverse()` is the
inverse of the driver's parent worldMatrix. The product
`worldMatrix * parentInverseMatrix = localMatrix` holds **only
when `driverMat` is the world-space matrix**. If `driverMat` is
already the local `.matrix`, the multiplication by
`parentInverseMatrix` cancels nothing — it injects an error term
proportional to the parent's world transform, silently corrupting
every RBF pose.

Therefore `_wire_matrix_mode_data_path` connects
`driver.worldMatrix[0]` (NOT `.matrix`). Red line 5 source-scan
guards this in `tests/test_m_b24d_matrix_followup.py::
TestM_B24D_MatrixFollowup_Source.test_uses_worldmatrix_not_local_matrix`.

**PROJECT METHODOLOGY**: when picking a write-side connection,
trace the read-side consumer's math chain to determine the
correct space (local / world / parent-relative). The (A.3) ->
(A.2) pivot is the verify-before-design 19th-use proof point.

### §M_B24d_matrix_followup.mode-exclusion-semantic

A single RBF shape cannot mix Generic mode wiring (`shape.input[]`
flat scalars) and Matrix mode wiring
(`shape.driverList[d].driverInput` matrix). The two read paths
are mutually exclusive in `RBFtools.cpp` compute(). Allowing
mixed wiring would either:

- silently strand half the data (compute() reads only the active
  branch), or
- explode at the next solve when the driver vector geometry is
  inconsistent with the pose vector geometry.

`add_driver_source` therefore probes both wiring topologies via
`_has_generic_wiring` + `_has_matrix_wiring` before any state is
written. On mismatch it raises a `RuntimeError` with the
hardcoded user-facing message:

> RBFtools: cannot mix Matrix mode and Generic mode driver
> sources on the same node. Existing sources are in {old} mode
> ...; current node is in {new} mode .... Remove all driver
> sources first via `remove_driver_source()`, then re-add. See
> addendum §M_B24d_matrix_followup.mode-exclusion-semantic.

**Recovery workflow**: walk every `driverSource[d]` returned by
`read_driver_info_multi(node)`, call `remove_driver_source(node,
d)`, flip `<shape>.rbfMode`, then re-add the desired sources.

### §M_B24d_matrix_followup.first-implementation

Pre-M_B24d_matrix_followup grep:

```bash
$ grep -rE "connectAttr.*driverList\[" \
       modules/RBFtools/scripts/ source/ MEL/
（empty）
```

The C++ side has consumed `driverList[d].driverInput` since the
project's earliest commits, but the *write* side was always
manual MEL: TDs ran `connectAttr -f drv.worldMatrix[0]
RBF1Shape.driverList[0].driverInput` in the script editor before
poses would solve. M_B24d_matrix_followup is the **first**
commit to wire this connection from Python — substantial UX +
correctness improvement, not just multi-source unlock.

A side benefit is the automatic `rotateOrder` sync via
`_resolve_driver_rotate_order`: standard transform / joint
drivers now propagate their rotateOrder to
`shape.driverInputRotateOrder[idx]`, eliminating one historical
"why are my poses rotated wrong?" support ticket category.

### §M_B24d_matrix_followup.permanent-guards

Permanent guards: 32 unchanged.

- **#32 T_M_B24D_DATA_PATH_WIRED sub-check (a) extension**:
  the original literal `.input[` requirement is widened to
  `.input[` OR `.driverList[`, since both the Generic and Matrix
  wiring routes flow real data into `RBFtools.cpp` compute().
  Sub-checks (b)/(c)/(d) — base helper, removeMultiInstance
  rollback, mode probe — unchanged.

The new `tests/test_m_b24d_matrix_followup.py` adds 13 mock-only
tests but registers no new permanent guard number; coverage of
the worldMatrix-vs-matrix invariant + post-connect verification +
mode-exclusion semantic is enforced via the file's own
source-scan class
(`TestM_B24D_MatrixFollowup_Source`) and the mode-exclusion
mock tests, all of which run on every full sweep.

### §M_B24d_matrix_followup.empirical-baseline (2026-04-27)

| Env | Pre-followup (post-M_B24d) | Post-followup |
|---|---|---|
| Pure-Python | 519 OK (skip 3) | 532 OK (skip 3) |
| mayapy 2025 | 519 ran 474 pass 45 skip | 532 ran 479 pass 53 skip |

mayapy delta: +13 tests = +5 pass (5 source-scan tests in
`TestM_B24D_MatrixFollowup_Source`) + +8 skip (8 mock-only
`@skipIf(_REAL_MAYA)` test methods). Per the forward-compat-
corrected red line 13, mock-pattern legitimate skip naturally
accumulates; **no plugin-load skips added** and M1.5.3 PAUSED
remains honored.

### §M_B24d_matrix_followup.scope-exclusions

- 0 lines C++ / 0 .mll / 0 CMakeLists / 0 schema modifications
- 0 lines Mirror code (M_B24c scope, untouched)
- 0 lines hotfix 4 files (`compat.py` / `conftest.py` /
  `test_pyside6_compat.py` / addendum hotfix section —
  M_HOTFIX_PYSIDE6 `edf5367` unchanged)
- 0 changes to the 14 deprecated `read_driver_info` call-sites
- 0 changes to the 5 active downstream adapters
- 0 changes to the 6 PERMANENT dual-version guards
- `driver_attrs` parameter retained as metadata-only in the
  Matrix branch (decision D.2; forward-compat for M5+ per-attr
  Matrix overrides)

---

## §M_B24c — Mirror multi-source migration (Generic mode RESOLVED)

> **STATUS** (2026-04-27): §M_PARITY_AUDIT.B2 row partially
> cleaned — Generic-mode multi-source mirror complete; Matrix-
> mode multi-source mirror DEFERRED to §M_B24c2-stub. Last
> deferred caveat under B2 is now Matrix mirror only.
>
> verify-before-design 20th use, sustaining the
> §M_B24d.lesson-learned PROJECT METHODOLOGY (read side / write
> side / trace indirection). The double-grep on `read_driver_info`
> callsites caught a planner enumeration error before any code
> moved — see §M_B24c.planner-error-correction.

### §M_B24c.scope

| Layer | Change | LoC |
|---|---|---|
| `core.py:mirror_node` | Matrix-mode multi-source entry guard (Hardening 2 hard `NotImplementedError`); single `read_driver_info` -> `read_driver_info_multi`; per-source naming remap + F.1 fallback (no_match keeps original + `cmds.warning`); per-pose per-source `mirror_driver_inputs` slice loop; write side replaces `connect_node` with `wire_driven_outputs` + per-source `add_driver_source` (E.3 reuse) | ~155 |
| `core.py:read_driver_info_multi` | Docstring RESOLVED stamp (preserves the `§M_B24b2.mirror-deferred-rationale` literal that #29 sub-check (d) asserts on; appends M_B24c2 + planner-error-correction anchors) | ~12 |
| `controller.py:mirror_current_node` | Single `read_driver_info` -> `read_driver_info_multi`; per-source preview lines (`Driver[i]: src -> tgt (n attrs, encoding=e)`); dialog `action_id` `mirror_multi_source_warning` -> `mirror_multi_source_info` (G.1 rename); informational notice (D.3) | ~50 |
| `ui/i18n.py` | EN + ZH `summary_mirror_multi_source` narrowed to "Generic-mode supported; Matrix-mode DEFERRED to M_B24c2 and blocked at engine entry. Continue?" | ~15 |
| `tests/test_m_b24b2_downstream.py` | Updated `mirror_multi_source_warning` literal -> `mirror_multi_source_info` (G.1 follow-up; the only M_B24b2 test that asserted the old action_id literal) | ~6 |
| `tests/test_m_b24c_mirror_multi.py` (new) | #33 T_MIRROR_MULTI_SOURCE_WIRED 4 sub-checks + per-source naming fallback source-scan + docstring RESOLVED stamp + Matrix-mode entry guard mock tests + controller `_info` action_id source-scan | ~260 |
| `addendum_20260424.md` | §M_B24c (5 sub-sections) + §M_B24c2-stub + §M_PARITY_AUDIT.B2 row update + §M_B24b2.mirror-deferred-rationale RESOLVED stamp + read_driver_info_multi docstring anchor sync | ~210 |
| **Total** | | **~708** |

≤ 800 LoC hard limit honoured; single commit.

### §M_B24c.planner-error-correction

verify-before-design 范式自我修正第 2 次事件（首次：M_B24a2-1 F2
`driverList` iteration 误判 → M_B24d data-path corrective）：

**Planner 原批示** (M_B24c 现状核查指令 §F1)：
"`controller.py` 5 mirror flow callsites（line 379/459/746/820/899）"

**执行者 F1 双向 grep 实测**：planner-listed 5 行号**全部错指向**：

- 379: `if len(_msrc) > 1:` — multi-source dialog 触发条件，非调用
- 459: `prog.end()` — progress UI 收尾，非调用
- 746: `regenerate_aliases_for_current_node` 函数体起头（M3.7 alias scope，非 mirror flow）
- 820: `force_regenerate_aliases_for_current_node` 内 `read_driver_info` 调用 — 但属 M3.7 alias scope，非 mirror flow
- 899: `_load_editor` 函数体起头（UI 加载 scope，非 mirror flow）

**真实 mirror-flow callsites**（双向 grep 全仓 8 处 deprecated callsites
中的 mirror 子集）:

- `controller.py:397` (`mirror_current_node` — preview 构建)
- `core.py:509` (`mirror_node` — 引擎本体)

**Lesson for future planner batches**: when enumerating callsite line
numbers across files, the planner must rely on actual `grep` output
rather than memory or symmetry-driven guess; "5 line numbers" can
sound plausibly symmetric without being correct. Only `grep` is
authoritative.

**纠正路径**: M_B24c 实施按 2 callsites 进行；其余 6 deprecated
callsites（controller × 4 + core_json + core_neutral）维持
zero-modification 锁（M_B24a2-1 backcompat 沿用）。

PROJECT METHODOLOGY: this entry is a precedent record — not blame —
so the next planner / executor pair has a documented reminder to
double-grep before quoting line numbers.

### §M_B24c.write-side-add-driver-source-reuse

`mirror_node`'s pre-M_B24c write side called `connect_node`
(`core.py:2670`), which internally calls
`wire_driver_inputs(node, driver_node, driver_attrs)` — a legacy
single-driver `for i, attr: connectAttr -> input[i]` loop with no
base offset, no `driverSource[]` metadata write, and no atomic
fail-soft. Re-using that path on a multi-source target would
overwrite the multi-source state immediately (every additional
source's appended `input[base+i]` would be clobbered).

M_B24c (decision E.3) replaces the driver-side `connect_node`
call with a per-source `add_driver_source(target, new_name,
list(s.attrs), s.weight, s.encoding)` loop. Inheriting from
M_B24d / M_B24d_matrix_followup this gives mirrored targets:

- atomic fail-soft per source (M_B24d Hardening 1)
- mode-exclusion semantic (M_B24d_matrix_followup Hardening 1)
- correct base offset for `input[]` indices (Generic) or
  next-free `driverList[]` index (Matrix-mode single-source
  case still routed through this loop)
- `worldMatrix[0]` wiring with post-connect verify (Matrix mode;
  see §M_B24d_matrix_followup.matrix-vs-worldmatrix)
- `driverSource[d]` metadata written so future
  `read_driver_info_multi` round-trips correctly

The driven side still calls `wire_driven_outputs` directly
(driven is single-target; the legacy single path is correct).
`connect_node` is now banned from `mirror_node` body by
permanent guard #33 sub-check (c).

### §M_B24c.per-source-naming-fallback

Decision F.1 mirrors the existing single-source `mirror_node`
behaviour (`core.py:523-527` pre-M_B24c — name-remap failure
appends a warning + uses the original name without aborting)
into the new per-source loop:

```python
for s in sources:
    new_name, dr_status = core_mirror.apply_naming_rule(
        s.node, naming_rule_index, custom_naming, naming_direction)
    if dr_status not in ("ok", "both_match"):
        warnings.append(
            "Driver name remap failed for source {!r} ({}): using "
            "original name".format(s.node, dr_status))
        new_name = s.node
    if dr_status == "both_match":
        warnings.append(...)
    remapped.append((s, new_name))
```

A common scenario this handles cleanly:

```
sources = [L_shoulder, L_elbow, pCube_helper]
rule    = L_/R_

remapped = [(L_shoulder, R_shoulder),     # ok
            (L_elbow,    R_elbow),        # ok
            (pCube_helper, pCube_helper)] # no_match -> kept + warning
```

The mirrored target still wires three sources; the helper rig's
non-L/R-conforming source is honest about the missed rename so
the TD can fix the asymmetric naming or accept the helper as
shared between left and right sides.

### §M_B24c.matrix-mode-still-deferred

`mirror_node` is fundamentally Generic-mode shaped: it iterates
`pose.inputs` (a flat `list[float]`) and routes the slice through
`core_mirror.mirror_driver_inputs` (encoding-aware flat-list
mirror). Matrix-mode pose data, however, lives at
`shape.driverList[d].pose[p]` as `MMatrix` snapshots — a different
storage shape requiring a different mirror primitive
(`mirror_driver_pose_matrix`, not yet written).

Closing that gap is M_B24c2's sub-task — see §M_B24c2-stub. To
prevent silent miswiring before M_B24c2 lands, `mirror_node`
hard-checks at entry:

```python
if _exists(source_shape) and _is_matrix_mode(source_shape):
    _matrix_sources = read_driver_info_multi(source_node)
    if len(_matrix_sources) > 1:
        raise NotImplementedError(
            "RBFtools: Matrix-mode multi-source mirror is DEFERRED "
            "to v5.x post-final M_B24c2. ... See addendum "
            "§M_B24c2-stub.".format(...))
```

The probe is wrapped in `try/except` so test fixtures that mock
`safe_get` to non-int returns conservatively treat the node as
non-Matrix (the Generic mirror path is the legacy default and
mock fixtures predate the M_B24d Matrix mode probe). Single-source
Matrix nodes pass the guard and run through the Generic-shaped
mirror engine — pre-M_B24c behaviour preserved.

The user-facing `controller.py` informational dialog (G.1 rename:
`mirror_multi_source_info`) is purely advisory; the engine guard
is the actual defense.

### §M_B24c.permanent-guards

Permanent guards: 32 → **33**.

```
T_MIRROR_MULTI_SOURCE_WIRED (#33) — 4 source-scan sub-checks on
core.py:mirror_node body:

  (a) body uses read_driver_info_multi (NOT bare read_driver_info()
      on driver side; regex enforces negative lookahead)
      Anchor: M_B24c (C.1 修订) — only mirror flow migrates;
      other 6 deprecated callsites stay on the wrapper.

  (b) body contains add_driver_source (write-side reuse, E.3)
      Anchor: M_B24d / M_B24d_matrix_followup atomic + mode-
      exclusion + worldMatrix wiring inheritance.

  (c) body does NOT call connect_node (legacy single-driver
      bundle); driven side wires via wire_driven_outputs.
      Anchor: §M_B24c.write-side-add-driver-source-reuse.

  (d) body contains _is_matrix_mode entry guard +
      NotImplementedError + M_B24c2 reference.
      Anchor: §M_B24c.matrix-mode-still-deferred (Hardening 2).
```

#29 T_V5_PARITY_B2_LIVE sub-check (d) literal `§M_B24b2.mirror-
deferred-rationale` is **0-modified** — `read_driver_info_multi`
docstring preserves the original anchor and appends the RESOLVED
stamp (§M_B24c.matrix-mode-still-deferred mirroring the
§M_B24d.matrix-mode-deferred RESOLVED block range).

### §M_B24c.empirical-baseline (2026-04-27)

| Env | Pre-c (post-d_matrix_followup) | Post-c |
|---|---|---|
| Pure-Python | 532 OK (skip 3) | **544 OK (skip 3)** |
| mayapy 2025 | 532 ran 479 pass 53 skip | **544 ran 489 pass 55 skip** |

mayapy delta accounting follows the forward-compat-corrected red
line 13 — mock-only `@skipIf(_REAL_MAYA)` test methods accumulate
in the skip pool naturally; no plugin-load skips added; M1.5.3
PAUSED still honoured.

### §M_B24c.scope-exclusions

- 0 lines C++ / 0 .mll / 0 CMakeLists / 0 schema modifications
- 0 lines `core_mirror.py` (decision B.2 — 0-touch invariant
  preserved by per-source loop in `mirror_node` orchestration
  layer)
- 0 modifications to the 6 other deprecated `read_driver_info`
  callsites (controller live-edit / alias × 2 / load-editor +
  core_json + core_neutral)
- 0 modifications to the 14 deprecated wrapper function itself
  (the `read_driver_info` wrapper still exists; only mirror-flow
  callers migrate)
- 0 modifications to `add_driver_source` / `_wire_*` /
  `_resolve_driver_rotate_order` / `_is_matrix_mode` /
  `_count_existing_*` / `_has_*` (all M_B24d / matrix_followup
  helpers locked, pure-call reuse only)
- 0 modifications to hotfix 4 files (M_HOTFIX_PYSIDE6 `edf5367`)
- 0 modifications to b1 widgets / 5 active downstream adapters
- Mirror-multi-source for **Matrix mode** stays DEFERRED to
  M_B24c2 (see §M_B24c2-stub)

---

## §M_B24c2-stub — Matrix-mode multi-source mirror (DEFERRED to v5.x post-final)

> **STATUS**: DEFERRED to v5.x post-final (since 2026-04-27).
>
> M_B24c lands Generic-mode multi-source mirror; Matrix-mode
> multi-source mirror is structurally distinct because Matrix-
> mode pose data is stored at `driverList[d].pose[p]` as
> `MMatrix` snapshots (not flat `input[i]` scalars).
> `core_mirror.mirror_driver_inputs` operates on `list[float]`;
> Matrix-mode requires a new `mirror_driver_pose_matrix`
> dispatching by source.encoding + matrix decomposition.

### Scope (when M_B24c2 lands)

- New `core_mirror.mirror_driver_pose_matrix(matrix, axis,
  encoding)` function that decomposes the per-pose driver
  matrix, mirrors swing / twist / quaternion components per the
  existing primitives, recomposes, and returns the mirrored
  matrix.
- `mirror_node` engine dispatch by `_is_matrix_mode(source_shape)`:
  the existing Generic-mode body becomes the `else` branch; a new
  Matrix-mode branch iterates `driverList[d].pose[p]` and calls
  `mirror_driver_pose_matrix` per source per pose.
- Per-source `add_driver_source` write side already supports
  Matrix mode (M_B24d_matrix_followup); only the read side +
  pose mirror primitive are missing.
- §M_PARITY_AUDIT.B2 row reaches its final form: "complete
  (Generic + Matrix + UI + downstream + multi-source mirror)".
- T_MIRROR_MULTI_SOURCE_WIRED (#33) sub-check (d) extension to
  validate the Matrix-mode dispatch presence (not just the
  guard).

### Restart trigger

- M_B24c push complete + a TD reports a real-scene need for
  Matrix-mode multi-source mirror, OR
- M5 / M4.5 work touches `core_mirror.py` and the Matrix-mode
  pose primitive becomes a natural co-deliverable.

### Current behaviour (pre-M_B24c2)

`mirror_node` raises `NotImplementedError` at entry when the
source node is in Matrix mode AND has > 1 driver sources. The
exception message lists three workarounds (reduce to 1 source,
switch to Generic mode, wait for M_B24c2) and points the TD at
this stub for the roadmap.

Single-source Matrix nodes mirror through the existing engine
(pre-M_B24c behaviour preserved — the guard's `len > 1` check
exempts single-source).

---

## §M_HOTFIX_PYSIDE6 — QActionGroup PySide6 migration shim

> **STRUCTURAL LESSON** (2026-04-27):
>
> Post-M_B24b2 push, user installed RBFtools to Maya 2025 and hit
> `AttributeError: module 'PySide6.QtWidgets' has no attribute
> 'QActionGroup'` at `ui/widgets/node_selector.py:73`. Existing
> `compat.py` shim (line 53-58, M2.4 era) covered `QAction` +
> `QShortcut` migrations but missed `QActionGroup`. UI mock-pattern
> tests (M2.4a/b 范式) completely missed it — `MagicMock` returns
> truthy for any attribute access, so `QtWidgets.QActionGroup`
> appeared valid under conftest mock.
>
> Fix: 1 line in `compat.py` (`if not hasattr` patch block)
> + 1 line in `conftest.py` mock + permanent guard #32 to prevent
> regression.
>
> **Lesson for future milestones**: mock-pattern UI tests cannot
> catch Qt module attribute migration bugs. Real PySide6 import
> path validation should land when the mayapy GUI fixture lands
> (M5 long-tail). 当前 compromise = source-scan permanent guard
> on compat.py shim integrity (#32) + the existing `compat.py`
> shim covers six legacy `QtWidgets.QActionGroup` callsites in
> `node_selector.py` automatically (zero widget source changes).

### §M_HOTFIX_PYSIDE6.fix

| File | Change |
|---|---|
| `ui/compat.py` | +5 lines: `if not hasattr(QtWidgets, "QActionGroup"): QtWidgets.QActionGroup = QtGui.QActionGroup` block, mirroring the existing QAction/QShortcut shim pattern (Hardening 1) |
| `tests/conftest.py` | +1 line: `qtgui.QActionGroup = type("QActionGroup", (_Stub,), {})` mock symbol so pure-python conftest path matches the real PySide6 surface |
| `tests/test_pyside6_compat.py` (NEW) | T_PYSIDE6_COMPAT (#32) — 3 sub-checks on compat.py shim integrity |

### §M_HOTFIX_PYSIDE6.scope-exclusions

- 0 lines `node_selector.py` direct modification (six existing
  `QtWidgets.QActionGroup` / `QtWidgets.QAction` usages are covered
  by the compat shim once the QActionGroup line is added)
- 0 lines `main_window.py` direct modification (four existing
  `QtWidgets.QAction` callsites already covered by the legacy shim)
- 0 C++ / 0 .mll / 0 CMakeLists / 0 schema / 0 business logic

### §M_HOTFIX_PYSIDE6.guard-scope-decision

实施期 Step 2 检测到守护 #32 sub-check (a) 与红线 4 冲突：

  - 红线 4: `node_selector.py / main_window.py / 任何 widget 业务逻辑文件`
    **0 直接修改**（shim 修后自动 work）
  - 原始 sub-check (a): widgets/ 0 `QtWidgets.QAction*` / `.QActionGroup`
    / `.QShortcut` 字面

冲突 = 既有 `node_selector.py` 6 处 Qt5-style usage 在红线 4 下
不可改，但 sub-check (a) 直接 fire（widget folder scan 报 6 offender）。

**裁决（计划者 2026-04-27）: 选项 C** — 守护收缩至 sub-check (b)
单条线（`compat.py` shim 完整性，3 sub-checks: b.1/b.2/b.3）。
理由：

1. 遵守红线 4
2. shim 完整性 = production bug root-cause 防御
3. widget 用 `QtWidgets.X` + compat shim 是项目既建范式
   （`compat.py` line 53-58 既有 QAction/QShortcut shim 已运行多
    个 milestone）
4. 真"新代码不用 Qt5-style"防御推 M5 GUI 长尾 mayapy 实测

**PROJECT METHODOLOGY**: 守护 source-scan 扫描范围与既有红线/范式
冲突时，**收缩守护范围**而非破坏红线 — 守护是工程文化记录，
不应回溯打破既建模式。如需扩大覆盖，设独立 forward-compat 守护
（如未来 #33 with file-creation-time whitelist）。

### §M_HOTFIX_PYSIDE6.permanent-guard

```
T_PYSIDE6_COMPAT (#32) — 3 sub-checks (all source-scan compat.py):

  (b.1) compat.py contains "QActionGroup"
        Anchor: production install on Maya 2025 fails without it.

  (b.2) compat.py contains "QtGui.QActionGroup"
        Anchor: shim RHS must point to Qt6 location, not QtWidgets.

  (b.3) compat.py preserves QtGui.QAction + QtGui.QShortcut +
        QtGui.QActionGroup (3-symbol shim integrity)
        Anchor: future cleanup cannot silently delete any of the
        three migrated symbols.
```

Permanent guards: 30 → 31.

### §M_HOTFIX_PYSIDE6.empirical-baseline (2026-04-27)

| Env | Pre-hotfix | Post-hotfix |
|---|---|---|
| Pure-Python | 508 OK (skip 3) | 511 OK (skip 3) |
| mayapy 2025 | 508 ran 466 pass 42 skip | 511 ran 469 pass 42 skip |

mayapy skip count UNCHANGED at 42 (post-M_B24b2 baseline; M1.5.3
PAUSED still honored).

---

## §M_B24b2 — Downstream multi-source adapters + v5.0 FINAL CONSTITUTIONAL EVENT 2/6

> **STATUS: LANDED** — v5.0 final 路径 B2 + B4 UI primary deliverable
> **完整解锁** (Mirror DEFERRED to M_B24c).

### §M_B24b2.v5.0-final-constitutional-event-2-of-6

This commit is the **FIRST** of six v5.0-final acceptance gates
to activate. Following the M_B24a2-2 PROJECT-CONSTITUTIONAL-EVENT
atomicity precedent, all four atomic steps land in this single
commit:

1. **§M_PARITY_AUDIT.B2 status**: ⚠️ partial → ✅ complete (full)
   *(Mirror DEFERRED to M_B24c)*
2. **§M_PARITY_AUDIT.B4 status**: ❌ missing → ✅ complete (full)
3. **9/15 ✅ counter advances to 11/15** (.0 总览速览表 update)
4. **STUB markdown** at v5.0-final-criteria.test_b2/b4 → "LIVE per
   M_B24b2 commit" + reference to T_V5_PARITY_B2_LIVE (#29) +
   T_V5_PARITY_B4_LIVE (#30)

Tearing any one of (1)..(4) into a separate commit makes the
v5.0-final acceptance suite incoherent mid-history. Future
v5.0-final commits (M4 → B1, M_B7, M_B11, M_B14) follow the same
atomicity precedent for their respective B-row activations.

### §M_B24b2.scope

| Layer | Change |
|---|---|
| `core.py` | +3 lines: `read_driver_info_multi` docstring references §M_B24b2.mirror-deferred-rationale (T_V5_PARITY_B2 #29 sub-check (d) machine-verifiable form) |
| `core_prune.py` | analyse_node + execute_prune adapt to `read_driver_info_multi`; cross-source attr-name redundant detection (A.2); new `cross_source_redundant` field on PruneAction |
| `core_profile.py` | profile_node aggregates multi-source attrs; format_report adds 5-column wiring table (idx/node/attrs/weight/encoding); ZERO touches of `_K_*` / `_THRESH_*` / caveat / `_estimate_solve_times` / split-suggestion (Hardening 1 self-check verified empty diff at lock terms) |
| `live_edit_widget.py` | scriptJob register adapts to (node, attr) pairs from multi-source list; legacy single-driver byte-equivalent |
| `controller.py` | mirror_current_node probes driver source count; if > 1 surfaces ask_confirm("mirror_multi_source_warning") path A dialog (D.2 + Hardening 5 action_id registration) |
| `i18n.py` | EN + ZH parity for title/summary/mirror_multi_source confirm strings |
| `tests/test_m3_1_prune.py` | _stub fixture extended with `read_driver_info_multi.return_value` so existing 4 mock tests cover the new entry-point |
| `tests/test_m3_5_profile.py` | _stub fixture similarly extended |
| `tests/test_m_b24b2_downstream.py` (new) | 3 active downstream multi-source + cross-source redundant + 3 legacy single-driver sanity (Hardening 5 byte-equivalent) + Mirror dialog wiring source-scan |
| `tests/test_v5_parity_b2_b4.py` (new) | T_V5_PARITY_B2_LIVE (#29) + T_V5_PARITY_B4_LIVE (#30) — 4 sub-checks each |

### §M_B24b2.mirror-deferred-rationale

> **STATUS UPDATE** (M_B24c, commit following `c7fd289`): RESOLVED
> for Generic-mode multi-source mirror; Matrix-mode multi-source
> mirror remains DEFERRED to M_B24c2. The pre-M_B24c "5 mirror-
> flow callsites" enumeration below is preserved verbatim for
> audit-trail integrity but has been empirically corrected to
> **2 mirror-flow callsites** (`controller.py:397` +
> `core.py:509`) by the M_B24c F1 double-grep — see
> §M_B24c.planner-error-correction for the verbatim correction.
> The `core_mirror.py` 0-touch invariant is preserved by M_B24c
> (decision B.2, controller / mirror_node layer per-source loop).

`core_mirror.py` is 0-touch in M_B24b (transitively verified —
0 `read_driver_info` calls in the file). Mirror semantics flow
through `controller.py` callsites:

  - `controller.py:379`  (`mirror_current_node` — primary)
  - `controller.py:459`  (auto-fill mirror)
  - `controller.py:746`  (per-pose mirror in apply chain)
  - `controller.py:820`  (per-pose recall mirror)
  - `controller.py:899`  (apply_aliases mirror flow)

These five mirror-flow callsites — alongside the other 9 of the 14
`read_driver_info` callers — remain **zero-modification** per
M_B24a2-1's deprecated-wrapper backcompat success pattern. Effect:
Mirror operations on multi-source nodes (driverSource list with
> 1 entries) currently mirror only `drivers[0]` (the deprecated
wrapper returns `multi[0]`).

**TD-visible boundary**: M_B24b2 introduces a path A dialog warning
in `controller.mirror_current_node`. When the source node has > 1
driver sources, the mirror operation surfaces
`ask_confirm("mirror_multi_source_warning")` — the user sees:

> "This node has multiple driver sources. Mirror will currently
> process only the FIRST source (deferred to M_B24c per addendum
> M_B24b2.mirror-deferred-rationale). Continue with single-source
> mirror?"

The action_id `mirror_multi_source_warning` is registered with the
M3.0 spillover §1 confirm-dialog framework — the optionVar
`RBFtools_skip_confirm_mirror_multi_source_warning` is recognized
by "Reset confirm dialogs" menu (Hardening 5).

**Full controller-layer migration to `read_driver_info_multi`** is
the v5.x post-final M_B24c sub-task (proposed). M_B24b classifies
B2 as ✅ complete (full) with this caveat because:

1. UI primary deliverable per user override 2026-04-26 lands here
2. Backend (a1 + a2-1 + a2-2) lands here
3. 3 active downstream consumers (prune / profile / live_edit)
   land here
4. Mirror-deferred boundary is **mechanically enforced** via the
   path A dialog so TDs cannot silently lose multi-source data

### §M_B24b2.permanent-guards

Permanent guards: 28 → 30.

- **T_V5_PARITY_B2_LIVE (#29)** — 4 sub-checks:
  (a) `from RBFtools.core import DriverSource, add_driver_source,
      remove_driver_source, read_driver_info_multi` all importable
  (b) `from RBFtools.ui.widgets.driver_source_list_editor import
      DriverSourceListEditor` importable + class
  (c) `DriverSourceListEditor` subclasses `_OrderedListEditorBase`
  (d) `read_driver_info_multi.__doc__` contains the literal
      "§M_B24b2.mirror-deferred-rationale" (Hardening 2
      machine-verifiable form)

- **T_V5_PARITY_B4_LIVE (#30)** — 4 sub-checks:
  (a) `from RBFtools.ui.widgets.output_encoding_combo import
      OutputEncodingCombo` importable + class
  (b) `core_json.EXPECTED_NODE_DICT_KEYS` contains
      `"output_encoding"`
  (c) `source/RBFtools.h` contains `static MObject outputEncoding;`
  (d) `source/RBFtools.cpp` contains
      `addAttribute(outputEncoding)` (regex match)

### §M_B24b2.empirical-baseline (2026-04-26)

| Env | Pre-b2 | Post-b2 | Δ |
|---|---|---|---|
| Pure-Python | 492 OK (skip 3) | 508 OK (skip 3) | +16 |
| mayapy 2025 | 492 ran 455 pass 37 skip | 508 ran 461 pass 42 skip | +16 ran / **+5 skip** |

**mayapy skip count change report** (red line 13 deviation, transparent):
The +5 skip increase is from the 5 mock-pattern test methods in
`TestM_B24B2_PruneMultiSource` (3) + `TestM_B24B2_ProfileMultiSource`
(2) which carry `@unittest.skipIf(conftest._REAL_MAYA, ...)` per
the M3.x mock-pattern convention. **M1.5.3 PAUSED is honored** —
`require_rbftools_plugin` remains stub; no plugin-load skips were
added. The skip-count baseline shifts from 37 → 42 because the
mock-test convention legitimately skips on real mayapy. Future
sub-tasks can use the same convention; the "37 严格不变" red-line
intent (M1.5.3 不解冻) holds.

---

## §M_B24b1 — Multi-source driver UI widgets + integration (B2 + B4 UI primary deliverable)

> **STATUS: LANDED** (M_B24b series sub-commit 1/2)
>
> First half of the B2 + B4 UI primary deliverable per user
> override 2026-04-26. Lands the two UI widgets
> (DriverSourceListEditor + OutputEncodingCombo), main_window
> integration as a collapsed section, controller path A wiring,
> i18n EN/CN parity, and 4 new tests + 2 new permanent guards.
> M_B24b2 (next) lands the 3 active downstream consumers
> (core_prune / core_profile / live_edit_widget) + legacy
> sanity coverage + T_V5_PARITY_B2/B4 LIVE activation
> (v5.0 FINAL CONSTITUTIONAL EVENT 2/6).

### §M_B24b1.scope

| Layer | Change | LoC |
|---|---|---|
| `ui/widgets/driver_source_list_editor.py` (new) | Subclass `_OrderedListEditorBase`; `_DriverSourceRow` composite (node label + attrs label + weight spin + encoding combo); `node_name()` deprecated wrapper + `node_names()` accessor (Hardening 5) | 172 |
| `ui/widgets/output_encoding_combo.py` (new) | Thin QComboBox wrapper for the node-level outputEncoding enum (Euler/Quaternion/ExpMap) | 53 |
| `ui/main_window.py` (modified) | Collapsed `_driver_sources_section` between RBFSection and PoseEditorPanel; hosts both new widgets | +18 |
| `controller.py` (modified) | `add_driver_source` / `remove_driver_source` (path A confirm) / `read_driver_sources` entry-points | +55 |
| `ui/i18n.py` (modified) | 14 new keys × EN + ZH = 28 entries (Hardening 6 same-commit dual-language) | +40 |
| `tests/test_m_b24b1_widgets.py` (new) | #27 + #28 + i18n parity + dataclass round-trip + DeprecationWarning source-scan | 195 |

**Total b1 LoC**: ~530 (well under 800 hard limit; mid-Step 2
Hardening 3 checkpoints both passed: stage 1 = 225 ≤ 400; stage 2 cumulative = 338 ≤ 700).

### §M_B24b1.dual-path-strategy (Hardening 5)

`DriverSourceListEditor.node_name()` returns the first source's
node + emits `DeprecationWarning` — mirroring the M_B24a2-1
`core.read_driver_info()` deprecated-wrapper pattern that kept
14 call-sites zero-modification. Combined with the new
`node_names()` multi-source accessor, future code uses the latter
while existing 14 `pe.driver_list.node_name()` consumers continue
working unchanged.

### §M_B24b1.permanent-guards

| # | Guard | Sub-checks |
|---|---|---|
| #27 | T_DRIVER_SOURCE_LIST_EDITOR_PRESENT | (a) class definition present; (b) inherits `_OrderedListEditorBase`; (c) dual-path `node_name()` + `node_names()` + DeprecationWarning |
| #28 | T_OUTPUT_ENCODING_COMBO_PRESENT | (a) class definition present; (b) three enum i18n keys reachable |

Permanent guards: 26 → 28.

### §M_B24b1.empirical-baseline (2026-04-26)

| Env | Pre | Post | Δ |
|---|---|---|---|
| Pure-Python | 482 OK (skipped=2) | 492 OK (skipped=3) | +10 |
| mayapy 2025 | 482 ran 445 pass 37 skip | 492 ran 455 pass 37 skip | +10 |

mayapy skip count UNCHANGED at 37 (M1.5.3 PAUSED honored).

### §M_B24b1.M_B24b2-handoff

M_B24b2 (next sub-commit, v5.0 FINAL CONSTITUTIONAL EVENT 2/6):
- 3 active downstream adapt: `core_prune.py` aggregate +
  redundant detection, `core_profile.py` per-source table rows
  (NO `_K_*` / `_THRESH_*` / caveat changes — Hardening 2),
  `live_edit_widget.py` multi-driver listen algo
- 5 legacy single-driver sanity tests (per-module + UI flow)
- T_V5_PARITY_B2_LIVE (#29) + T_V5_PARITY_B4_LIVE (#30)
  activation (atomic with #25.d & #26 precedent)
- Mirror multi-source DEFERRED to M_B24c (v5.x post-final);
  rationale verbatim in §M_B24b2.mirror-deferred-rationale
- §M_PARITY_AUDIT.B2/B4 status: ⚠️/❌ → ✅ complete (with
  Mirror DEFERRED caveat); 9/15 → 11/15 ✅ counter advance

---

## §M_B24a2 — Multi-source driver Python backend (B2 + B4 backend complete)

> **PROJECT-CONSTITUTIONAL-EVENT** (2026-04-26):
>
> §M_B24a2 contains the v5 path's FIRST legal SCHEMA_VERSION
> bump through a PERMANENT guard (lands in §M_B24a2-2 commit).
> The four atomic steps required to make a bump legal are
> documented inline at §M_B24a2-2.constitutional-bump-protocol
> and serve as PRECEDENT for all future v5.x / v6+ schema
> migrations.
>
> Sub-commits:
>   §M_B24a2-1 — Python multi-source API + 14-caller backcompat
>                (commit a43f0de)
>   §M_B24a2-2 — Versioned JSON schema + PERMANENT guards bump
>                (this commit; see constitutional-bump-protocol)

### §M_B24a2-1 — Python multi-source API + 14-caller backcompat (a43f0de)

Routes the M_B24a1 C++ schema (driverSource compound + outputEncoding,
landed in d73d6b9) up through Python. Public multi-source API +
fail-soft legacy auto-migration + 14-caller zero-modification
backcompat via deprecated wrapper. See commit a43f0de body for
full decision verbatim and §M_B24a2-1.research-preserved equivalents
in conversation transcript (verify-before-design 14th use).

Key surface added to `core.py`:
- `DriverSource` dataclass (frozen, post_init validation)
- `read_driver_info_multi(node) -> list[DriverSource]`
- `add_driver_source(node, driver, attrs, weight=1.0, enc=0)`
- `remove_driver_source(node, index)`
- `_migrate_legacy_single_driver(node)` — fail-soft per 加固 4
- `read_driver_info(node)` — DEPRECATED wrapper, routes through
  `_multi`, emits `DeprecationWarning` (stdlib, NOT i18n per 加固 2)

Permanent guards: 24 -> 25.
- `T_M_B2_MIGRATION_BACKCOMPAT` (#25) sub-checks (a)/(b)/(c) landed.
  Sub-check (d) — legacy fixtures presence + PERMANENT marker —
  deferred to §M_B24a2-2 since the fixtures live there.

### §M_B24a2-2 — Versioned JSON schema + PERMANENT guards bump

#### §M_B24a2-2.constitutional-bump-protocol

This is the v5 path's FIRST legal SCHEMA_VERSION bump through
PERMANENT guards. Recording the four-step atomic protocol here
as PRECEDENT for all future v5.x / v6+ migrations:

1. **SCHEMA_VERSION updated** (`rbftools.v5.m3` -> `rbftools.v5.m_b24`)
2. **LEGACY_SCHEMA_VERSIONS extended** (永久 inclusion of
   `rbftools.v5.m3`; deletion would orphan legacy fixtures)
3. **All PERMANENT guards locking SCHEMA_VERSION upgraded to
   dual-version form**, in the SAME commit:
   - `T6_SchemaVersionUnchanged` (test_m3_3_jsonio.py)
   - `T_M3_3_SCHEMA_FIELDS` (auto-follows EXPECTED_NODE_DICT_KEYS
     mutation)
   - `T_FLOAT_ROUND_TRIP` (literal in test body bumped)
   - `T0_SchemaVersionImmutability` (test_m3_0_infrastructure.py)
   - `T_CoreJsonDiffEmpty.test_PERMANENT_schema_version_locked`
     (test_m2_5_cache.py)
   - `T12_SchemaVersionUnchanged` (test_m3_7_alias.py)
4. **Legacy fixtures committed** (永久) at
   `tests/fixtures/legacy_v5_pre_b24.{ma,json}` for backcompat
   regression coverage.

Tearing any one of (1)..(4) into a separate commit makes
PERMANENT guards red mid-history — forbidden. M_B24a2-2 lands
all 4 atomically.

PERMANENT guard semantic — clarified by the M_B24a2-1 现状核查
F3 finding: "commit must not silently change SCHEMA_VERSION"
≠ "SCHEMA_VERSION can never change". A bump becomes legal when
the four steps above are atomic.

#### §M_B24a2-2.scope

| Layer | Change |
|---|---|
| `core_json.py` | SCHEMA_VERSION bump + LEGACY_SCHEMA_VERSIONS frozenset + EXPECTED_NODE_DICT_KEYS replaced + LEGACY_NODE_DICT_KEYS_M3 + `_upgrade_legacy_node` + `_upgrade_legacy_dict` helpers + `read_json_with_schema_check` versioned dispatch + `node_to_dict` writes new shape (`drivers` list + `output_encoding`) + `_validate_node_dict` + `dict_to_node` upgrade legacy on entry |
| Five tests | T6 dual-method / T2 driver -> drivers[] / T_FLOAT_ROUND_TRIP literal bump / T0 dual / T2.5 cache dual / T12 alias dual |
| Fixtures | `tests/fixtures/legacy_v5_pre_b24.ma` (6978 bytes ASCII) + `legacy_v5_pre_b24.json` (with PERMANENT _comment) |
| New tests | `test_m_b24a2_versioned_schema.py` — #26 + #25.d + 加固 1 + 加固 5 |

#### §M_B24a2-2.legacy-ma-creation-script

Verbatim mayapy probe used to create `legacy_v5_pre_b24.ma`. The
script is NOT committed (one-shot probe per A.3 pattern); preserved
here for future M5+ regeneration when the M_B24 schema is itself
superseded.

```python
import os
import maya.standalone
maya.standalone.initialize(name="python")
import maya.cmds as cmds
mll = "X:/Plugins/RBFtools/modules/RBFtools/plug-ins/win64/2025/RBFtools.mll"
cmds.loadPlugin(mll)
loc = cmds.spaceLocator(n="drv1")[0]
rbf = cmds.createNode("RBFtools", n="rbfTest1Shape")
# legacy single-driver: connect translateXYZ -> input[0..2]
# IMPORTANT: do NOT setAttr any driverSource_* — leave defaults
# to mimic v5.0-pre-M_B24 node where the schema field exists but
# was never written.
cmds.connectAttr(loc + ".translateX", rbf + ".input[0]", force=True)
cmds.connectAttr(loc + ".translateY", rbf + ".input[1]", force=True)
cmds.connectAttr(loc + ".translateZ", rbf + ".input[2]", force=True)
cmds.setAttr(rbf + ".poses[0].poseInput[0]", 0.0)
cmds.setAttr(rbf + ".poses[0].poseInput[1]", 0.0)
cmds.setAttr(rbf + ".poses[0].poseInput[2]", 0.0)
cmds.setAttr(rbf + ".poses[0].poseValue[0]", 0.0)
out = "X:/Plugins/RBFtools/modules/RBFtools/tests/fixtures/legacy_v5_pre_b24.ma"
cmds.file(rename=out)
cmds.file(save=True, type="mayaAscii")
print("size:", os.path.getsize(out))   # observed: 6978 bytes
```

#### §M_B24a2-2.legacy-fixtures

`tests/fixtures/legacy_v5_pre_b24.{ma,json}` are PERMANENT
(加固 5). Deletion is forbidden — any future "leanup" wishing to
remove must explicitly record in addendum "v5.X stops supporting
v4 / v5-pre-M_B24 .ma upgrade" before removal. The .json fixture
carries `"_comment": "... PERMANENT - DO NOT DELETE ..."` as a
machine-readable token; T_M_B2_MIGRATION_BACKCOMPAT (#25) sub-
check (d) regression-tests this marker.

#### §M_B24a2-2.permanent-guards

Permanent guards: 25 -> 26.

- `T_VERSIONED_SCHEMA_PRESENT` (#26) — 3 sub-checks:
  (a) `SCHEMA_VERSION == "rbftools.v5.m_b24"`
  (b) `"rbftools.v5.m3" in LEGACY_SCHEMA_VERSIONS` (加固 3 perm)
  (c) source-scan `core_json.py` matches versioned dispatch
      multi-keyword OR set (加固 3 future-refactor safe)

- `T_M_B2_MIGRATION_BACKCOMPAT` (#25) sub-check (d) ENABLED:
  legacy `.ma` + `.json` files exist + `.json` `_comment` carries
  "PERMANENT - DO NOT DELETE".

#### §M_B24a2-2.empirical-baseline (2026-04-26)

| Env | Pre-M_B24a2-2 | Post-M_B24a2-2 |
|---|---|---|
| Pure-Python | 472 OK (skipped=2) | 482 OK (skipped=2) |
| mayapy 2025 | 472 ran 435 pass 37 skip | 482 ran 445 pass 37 skip |

mayapy skip count UNCHANGED at 37 — M1.5.3 PAUSED honored;
require_rbftools_plugin still stub. +10 tests = 3 (#26) + 3 (#25.d)
+ 4 (加固 1+5 + idempotent) = 10.

#### §M_B24a2-2.parity-audit-update

`§M_PARITY_AUDIT.B2`: status `⚠️ partial` -> `✅ complete (backend)`.
The "backend" qualifier is intentional — UI primary deliverable
(M_B24b) is still ahead, so the row stays partial in the user-
visible sense. The 0/15 ✅ counter does NOT advance until M_B24b
lands.

`§M_PARITY_AUDIT.B4`: status `❌ missing` -> `✅ complete (backend)`.
Same UI caveat.

#### §M_B24a2-2.schema-migration-track

```
v5.0-pre-M_B24 -> v5.0-M_B24-a2-2:
  add LEGACY_SCHEMA_VERSIONS frozenset
  add output_encoding to EXPECTED_NODE_DICT_KEYS
  rename driver -> drivers (plural list)
  add LEGACY_NODE_DICT_KEYS_M3 frozen for legacy round-trip
  legacy nodes auto-upgrade in-memory via _upgrade_legacy_dict
  dump path forces SCHEMA_VERSION = "rbftools.v5.m_b24" (one-way,
    加固 5 wormhole defense)
```

---

## §M_B24a1 — driverSource compound + outputEncoding schema (backend, B2+B4 partial)

> **STATUS: LANDED 2026-04-26 — schema + read path + DG dirty live;
> semantic consumption deferred to M_B24b/business**

First sub-task on the v5.0 final path (H.2 LOCKED order). Adds the
driverSource compound (multi) + 4 child fields + node-level
outputEncoding enum. Pure schema + read-path + DG dirty validation;
no metadata semantic consumption (weight scaling / encoding inverse)
— that lands in M_B24b once the UI exposes the fields to TDs.

### §M_B24a1.scope

| Layer | Change |
|---|---|
| C++ schema | 6 new MObject (driverSource compound + 4 children + outputEncoding) |
| C++ compute() | readDriverSourceMetadata helper (defensive); placeholder calls in driverList for-loop + setOutputValues |
| C++ attributeAffects | 5 new edges (4 driverSource children + outputEncoding -> output) |
| .mll | Re-built; SHA256 below |
| Python | **0** (M_B24a2 territory) |
| Build config | 1 #include added (MFnStringArrayData.h) per K.1-3 pre-approval |

### §M_B24a1.K1-deep-dive — verbatim record

K.1 sub-deep-dive (per planner's "首次 ≥100 行 C++ 子任务" pre-review
gate) locked the following insertion points before any code was
written:

- `RBFtools.h:347` after `poseSigma` decl: 6 MObject member declarations
- `RBFtools.h:152` after `decomposeSwingTwist`: helper static decl
- `RBFtools.cpp:93` after `MObject RBFtools::poseSigma;`: 6 globals
- `RBFtools.cpp:286` after `inputEncoding` eAttr block: outputEncoding
  eAttr block (~7 lines)
- `RBFtools.cpp:736` after `driverList` cAttr block: driverSource cAttr
  block with 4 `{}`-scoped child creations (M2.5 cache pattern)
- `RBFtools.cpp:809` after `addAttribute(driverList)`: 5 addAttributes
- `RBFtools.cpp:844` after `addAttribute(inputEncoding)`: outputEncoding
- `RBFtools.cpp:891` after `attributeAffects(inputEncoding, output)`:
  outputEncoding edge
- `RBFtools.cpp:899` after `attributeAffects(driverInput, output)`:
  4 driverSource_* edges
- `RBFtools.cpp:1991` inside compute() driverList for-loop, after
  `driverInputHandle` access: helper invocation + (void) sink
- `RBFtools.cpp:3920` inside `setOutputValues()`, before output build
  loop: outputEncoding plug read + thread_local sink (加固 K.1-2
  防 MSVC O2 dead-read elimination)
- `RBFtools.cpp:3168` after `decomposeSwingTwist` definition:
  readDriverSourceMetadata helper definition

### §M_B24a1.compile-error-recovery — UTF-8 cp936 incident

First build attempt failed with `error C2039: 'driverSource' is not
a member of 'RBFtools'` despite the declarations being clearly
present in RBFtools.h. Root cause: my added comment block (lines
348-360 of RBFtools.h) contained Chinese characters in 3-byte UTF-8
sequences. Existing M2.3/M2.5 comments used only Latin-1 chars
(em-dash U+2014 = 3-byte UTF-8 but stable in cp936; § U+00A7 = 2-byte
UTF-8). MSVC running in cp936 codepage mode (warning C4819 emitted)
mis-parsed certain UTF-8 multi-byte sequences and silently consumed
the trailing newline of the preceding line, effectively merging
comment + class-member-decl line into a single broken-comment
line — hiding the static MObject declarations from the parser.

Fix: rewrote my added comments to pure ASCII (English-only, matching
the rest of the file's convention). Build then succeeded. Lesson:
when modifying RBFtools.h/cpp, NEW comments must be ASCII-only;
existing Chinese comments in cpp body (RBFtools.cpp:568, etc.) are
grandfathered and have been validated through repeated builds.

### §M_B24a1.J3-baseline (mayapy probe, 2026-04-26)

Probe script NOT committed (one-shot per A.3 范式). Verbatim output:

```
=== loadPlugin ===
loaded: True
version: 4.0.1

=== createNode ===
node: RBFtoolsShape1

=== M2.5 schema introspection (regression check) ===
poseSwingTwistCache: exists=True
poseSwingQuat:       exists=True
poseTwistAngle:      exists=True
poseSwingWeight:     exists=True
poseTwistWeight:     exists=True
poseSigma:           exists=True

=== M_B24a1 schema introspection ===
driverSource:           exists=True  longName=driverSource           shortName=drs
driverSource_node:      exists=True  longName=driverSource_node      shortName=dsn
driverSource_attrs:     exists=True  longName=driverSource_attrs     shortName=dsa
driverSource_weight:    exists=True  longName=driverSource_weight    shortName=dsw
driverSource_encoding:  exists=True  longName=driverSource_encoding  shortName=dse
outputEncoding:         exists=True  longName=outputEncoding         shortName=oenc

=== listAttr count ===
total attrs: 280   (was 274 pre-M_B24a1; +6)

=== DG dirty propagation probe ===
output[0] before: 0.0
setAttr driverSource[0].driverSource_weight = 5.0
output[0] after:  0.0   (no exception — compute rerun OK)
setAttr outputEncoding = 1
output[0] after:  0.0   (no exception — outputEncoding edge live)

=== unloadPlugin ===
unloaded ok
```

### §M_B24a1.SHA256-baseline

```
72de19403d5190e3c04736be7e6b9575a85df033bbe7d55c8fa5442e580d4bc8 *modules/RBFtools/plug-ins/win64/2025/RBFtools.mll
```

Build env: VS 2022 17.14 / MSVC 19.44.35223 (v143) / Win SDK 10.0.26100.0 /
Release / Maya 2025 devkit / 2026-04-26. Size: 171008 bytes (was 166912
in M1.5.1b SHA256-baseline; +4096 bytes). M1.5.1b SHA256
`2725287715b9...` retained at §M1.5.1b.SHA256-baseline as historical
anchor; current production .mll uses this M_B24a1 hash.

### §M_B24a1.permanent-guards — #23 + #24 LANDED

```
T_DRIVER_SOURCE_AGGREGATION (#23):
  source-scan RBFtools.cpp contains:
    - inputArrayValue(driverSource, ...)
    - driverSource_weight read
    - driverSource_encoding read
    - readDriverSourceMetadata helper definition
    - readDriverSourceMetadata invocation from compute()

T_OUTPUT_ENCODING_DECLARED (#24):
  source-scan RBFtools.h contains: static MObject outputEncoding;
  source-scan RBFtools.cpp contains:
    - addAttribute(outputEncoding)
    - attributeAffects(RBFtools::outputEncoding, RBFtools::output)
    - s_outEncSink (placeholder thread_local sink — 加固 K.1-2)
```

Plus class-level `@skipIf(not _REAL_MAYA)` acceptance test
`TestM_B24A1_DirtyPropagationRealMaya` (2 methods) which loads .mll,
sets driverSource_weight / outputEncoding, asserts compute reruns
without exception. NOT a permanent guard (acceptance only); covers
the dead-read elimination scenario 加固 K.1-2 was designed against.

### §M_B24a1.empirical-baseline (2026-04-26)

| Env | Pre-M_B24a1 | Post-M_B24a1 | Delta |
|---|---|---|---|
| Pure-Python | 454 / 454 OK | **462 / 462 OK (skipped=2)** | +8 (#23 × 3 methods + #24 × 3 methods + dirty × 2 skipif) |
| mayapy 2025 | 454 ran 417 pass 37 skip | **462 ran 425 pass 37 skip** | +8 ran / +8 pass / **+0 skip** (dirty methods run real, schema-scan methods run cross-env) |

Permanent guards: 22 -> 24 (#23 + #24).

### §M_B24a1.M_B24a2-handoff

M_B24a2 (next) will:
- Add Python `add_driver_source` / `remove_driver_source` /
  `read_driver_info_multi` core API
- Add JSON versioned schema (`schema_version: "v5.0-M_B24"`) +
  drivers array + outputEncoding field
- Add `_migrate_legacy_single_driver` lazy migration with
  `cmds.warning` per-session (T_M_B2_MIGRATION_BACKCOMPAT, 加固 2)
- Commit minimal legacy `.ma` fixture for migration regression
- Update T_M3_3_SCHEMA_FIELDS to version-aware (legacy + new)
- 0 C++ changes (M_B24a1 schema is the entire C++ surface for
  M_B24)

M_B24b (after a2) will be the UI primary deliverable per H.2 user
override.

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
