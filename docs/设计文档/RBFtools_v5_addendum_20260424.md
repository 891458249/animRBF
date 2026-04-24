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

**本文档结束。**
