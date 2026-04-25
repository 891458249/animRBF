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
