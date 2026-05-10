# RBFtools v5 — Multi-driver × Multi-driven Quaternion RBF 实施权威文档

> **关系**：本文档为 `RBFtools_v5_设计方案.md` 与 `RBFtools_v5_addendum_20260424.md` 的实施侧权威说明。承诺：当 cpp 实现与本文档发生分歧时，以**当前 cpp 行号引用 + AST 守护**为准；本文档负责保留**设计意图**与**数学契约**，防止未来重构无意打破 N-generic / B1+B2 共存设计。
>
> **landing 标签**：`M_P0_QUAT_RBF_LANDING_GUARDS`（2026-05-10）

---

## §0. 适用范围

本文档涵盖 RBFtools 节点在 **Generic 模式**下的 multi-driver（输入侧）× multi-driven（输出侧）quaternion 工作流。Matrix 模式（rbfMode=1）走独立路径（[cpp:1506-1542](../../source/RBFtools.cpp)），与本文档无关。

---

## §1. 总体架构图

```
┌───────────────────── Multi-driver 输入侧 ─────────────────────┐
│                                                              │
│ Maya input[] 数组 (N driver × 3 attr Euler = 3N 维 raw)       │
│        │                                                     │
│        ▼  cpp:2620-2640  rest-subtract                       │
│ rawDriver ∈ ℝ^{3N}                                           │
│        │                                                     │
│        ▼  cpp:2670  groups = inDim / 3                       │
│        ▼  cpp:2671-2676  encoding dispatch                   │
│        ▼  cpp:2684-2742  per-group encode (4 encoding 之一)   │
│ encodedDriver ∈ ℝ^{D_eff}, D_eff ∈ {3N, 4N, 5N}               │
│                                                              │
│ pose 矩阵同一编码: matPoses ∈ ℝ^{P × D_eff}                   │
└──────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌────────────── Distance / Kernel / Solve 训练 ──────────────┐
│                                                            │
│ K_{ij} = φ(d(p_i, p_j), σ_j)         cpp:1758, 3006-3027   │
│   d(·,·) per-block quat dist          cpp:3091-3095, 3164  │
│ K += λI                               cpp:1800-1804        │
│ K W = Y → W ∈ ℝ^{P × C}              cpp:1872-1925         │
│   (Y = matValues, C = solveCount = 输出维度总数)            │
└────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────── Multi-driven 输出侧 (双路径) ────────────────┐
│                                                              │
│ inference: φ_i = φ(d(driver, p_i), σ_i)   cpp:4285-4295      │
│                                                              │
│ ┌─────────────── 路径 A: 标量加权和 ────────────────┐         │
│ │ out[c] = Σ_i W(i,c) · φ_i                         │         │
│ │ cpp:4300-4304                                     │         │
│ └───────────────────────────────────────────────────┘         │
│                                                              │
│ ┌─── 路径 B1: QWA Power Iteration (per-quat-group) ───┐       │
│ │ 用户声明 quatGroupStarts[] (M2.2)                   │       │
│ │ M_g = Σ_i φ_i · q_i^{(g)} (q_i^{(g)})^T  (4×4 PSD)   │       │
│ │ q_out^{(g)} = argmax_{|q|=1} q^T M_g q              │       │
│ │   (Power Iteration on 4×4)                          │       │
│ │ cpp:4310-4337, 3695-3777                            │       │
│ └─────────────────────────────────────────────────────┘       │
│                                                              │
│ ┌── 路径 B2: outputEncoding inverse transform (3-block) ──┐   │
│ │ 节点级 outputEncoding ∈ {0=Euler/None, 1=Quat, 2=ExpMap}│   │
│ │ Quat:   per-pose Euler→quat → nlerp(φ_i) → decode Euler │   │
│ │ ExpMap: per-pose Euler→quat→log → Σ φ_i·log → exp → Eul │   │
│ │ cpp:3445-3527                                            │   │
│ └─────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────┘
```

**关键设计契约**：

- A、B1、B2 三条输出路径**列下标互斥**：B1 写 `quatGroupStarts[g] .. quatGroupStarts[g]+3`（4 列），B2 写连续 3-block，A 写其他列
- 列下标若发生重叠，由 `M_P0_QUAT_RBF_OVERLAP_DISCLOSE` 安全网（[cpp 在 applyOutputEncodingBlend 内](../../source/RBFtools.cpp)）跳过 B2 块并发出 once-per-rig 警告，B1 优先

---

## §2. 输入侧：Multi-driver Quaternion 编码

### §2.1 数学

设 N 个 driver，每 driver 提供 Euler triple $(r_x^{(k)}, r_y^{(k)}, r_z^{(k)})$，$k = 0, \ldots, N-1$。Raw 输入向量：

$$
\mathbf{r} = (r_x^{(0)}, r_y^{(0)}, r_z^{(0)}, \ldots, r_x^{(N-1)}, r_y^{(N-1)}, r_z^{(N-1)}) \in \mathbb{R}^{3N}
$$

Quaternion 编码（`inputEncoding=1`）逐 driver 独立：

$$
\mathbf{q}^{(k)} = \mathcal{E}_{\text{quat}}\!\left(r_x^{(k)}, r_y^{(k)}, r_z^{(k)};\ \text{rotateOrder}_k\right) \in S^3
$$

其中 $\mathcal{E}_{\text{quat}}$ 通过 per-axis half-angle 单位 quat 按 rotateOrder 复合（见 §2.2）。

最终编码后驱动向量：

$$
\mathbf{d} = \big(\mathbf{q}^{(0)}, \mathbf{q}^{(1)}, \ldots, \mathbf{q}^{(N-1)}\big) \in (S^3)^N \subset \mathbb{R}^{4N}
$$

**effective dimension**：$D_{\text{eff}} = 4N$。

### §2.2 半角公式与 rotateOrder 复合

[cpp:3189-3225](../../source/RBFtools.cpp)：

$$
q_X = \left(\cos\tfrac{r_x}{2}, \sin\tfrac{r_x}{2}, 0, 0\right),\quad
q_Y = \left(\cos\tfrac{r_y}{2}, 0, \sin\tfrac{r_y}{2}, 0\right),\quad
q_Z = \left(\cos\tfrac{r_z}{2}, 0, 0, \sin\tfrac{r_z}{2}\right)
$$

按 rotateOrder（0=XYZ, 1=YZX, 2=ZXY, 3=XZY, 4=YXZ, 5=ZYX）复合：

$$
q^{(k)} = q_{A_2} \cdot q_{A_1} \cdot q_{A_0}, \quad A_i = \text{rotateOrder 第 } i \text{ 轴}
$$

约定与 Maya `MTransformationMatrix::rotation` 一致。

### §2.3 4 encoding 的 effectiveInDim 公式

| inputEncoding | $D_{\text{eff}}$ | 块尺寸 | cpp 行号 |
|---|---|---|---|
| 0 = Raw | $3N$ | 1 | [cpp:2676](../../source/RBFtools.cpp), [cpp:2740-2741](../../source/RBFtools.cpp) |
| 1 = Quaternion | $4N$ | 4 | [cpp:2672](../../source/RBFtools.cpp), [cpp:2686-2695](../../source/RBFtools.cpp) |
| 2 = BendRoll | $3N$ | 3 | [cpp:2676](../../source/RBFtools.cpp), [cpp:2711-2721](../../source/RBFtools.cpp) |
| 3 = ExpMap | $3N$ | 3 | [cpp:2676](../../source/RBFtools.cpp), [cpp:2697-2710](../../source/RBFtools.cpp) |
| 4 = SwingTwist | $5N$ | 5 | [cpp:2674](../../source/RBFtools.cpp), [cpp:2723-2735](../../source/RBFtools.cpp) |

**N-generic 不变量**：[cpp:2670](../../source/RBFtools.cpp) `groups = inDim / 3` 自动推 N，每条 encode 分支循环 `g=0..groups-1`，所以 N 任意值通用。

### §2.4 安全网

- **inDim 非 3 倍数** → 退化到 Raw + 一次性警告（[cpp:1473-1486](../../source/RBFtools.cpp)）。例：N=2 但 user 漏接一个 attr 导致 inDim=5，整条 quat 路径关闭，避免半成品 encode。
- **Matrix 模式 (rbfMode=1)** → 强制 `effectiveEncoding=0`（[cpp:1539](../../source/RBFtools.cpp)），与 Generic+Quat 互斥。

### §2.5 代码映射全表

| 步骤 | 行号 |
|---|---|
| 收集 raw 3N 维 | [cpp:2560](../../source/RBFtools.cpp), [cpp:2620-2640](../../source/RBFtools.cpp) |
| 计算 inDim（Maya 数组长度）| [cpp:2560](../../source/RBFtools.cpp) `inputIds.length()` |
| `groups = inDim / 3` | [cpp:2670](../../source/RBFtools.cpp) |
| `effectiveInDim = groups * 4`（Quat） | [cpp:2672](../../source/RBFtools.cpp) |
| `effectiveInDim = groups * 5`（SwingTwist）| [cpp:2674](../../source/RBFtools.cpp) |
| `effectiveInDim = inDim`（其他）| [cpp:2676](../../source/RBFtools.cpp) |
| `driver.assign(effectiveInDim, 0.0)` | [cpp:2683](../../source/RBFtools.cpp) |
| 逐 group 循环 encode | [cpp:2686/2699/2713/2725](../../source/RBFtools.cpp) |
| Pose 矩阵同一编码 | [cpp:2842/2855/2869/2882](../../source/RBFtools.cpp) |
| `matPoses.setSize(P, D_eff)` | [cpp:2757](../../source/RBFtools.cpp) |
| `poseMinVec/MaxVec.assign(D_eff)` | [cpp:2919-2920](../../source/RBFtools.cpp) |

---

## §3. 距离层：Per-block Quaternion Distance

### §3.1 数学

两 pose $\mathbf{p}_i, \mathbf{p}_j \in (S^3)^N$，距离按 per-block 几何距离 + L2 聚合：

$$
d_{\text{quat}}(q_a, q_b) = 1 - \lvert q_a \cdot q_b \rvert
$$

（chord-style，与 $\sin(\theta/2)$ 近似线性，避免 $\arccos$ 的 $\sqrt{1-x^2}$ 退化导数）

$$
d(\mathbf{p}_i, \mathbf{p}_j) = \sqrt{\sum_{k=0}^{N-1} \big[ d_{\text{quat}}(q_k^{(i)}, q_k^{(j)}) \big]^2}
$$

**几何意义**：把 N 个 driver 视为乘积流形 $(S^3)^N$ 上的点，每 driver 量自己的旋转角差，最后用 L2 把 N 维独立误差合成一个 scalar。这是 Riemannian product manifold 上的标准做法。

**双覆盖 robustness**：因为 $|q_a \cdot q_b| = |(-q_a) \cdot q_b|$，距离对四元数双覆盖（$q$ 与 $-q$ 表示同一旋转）天然不变，无须显式 antipodal 处理。

### §3.2 代码映射

| 实现 | 行号 |
|---|---|
| `getPoseDelta` 总调度 | [cpp:3049-3123](../../source/RBFtools.cpp) |
| `encoding == 1` 调度 | [cpp:3091-3095](../../source/RBFtools.cpp) |
| `getQuatBlockDistance` | [cpp:3164-3178](../../source/RBFtools.cpp) |

```cpp
// cpp:3164-3178 —— 直接对应 §3.1 公式
for (size_t k = 0; k < blocks; ++k) {
    double dot = v1[base+0]*v2[base+0] + ... + v1[base+3]*v2[base+3];
    const double d = 1.0 - fabs(dot);   // 1 - |q_a·q_b|
    sumSq += d * d;
}
return sqrt(sumSq);                      // L2 聚合
```

### §3.3 与其他 encoding 的对比

| encoding | per-block 距离 | 块尺寸 | cpp 行号 |
|---|---|---|---|
| Raw (0) | Euclidean / Angle | 1 (整体) | [cpp:3081-3088](../../source/RBFtools.cpp) |
| **Quat (1)** | $1-\lvert q_a\cdot q_b\rvert$ + L2 | 4 | [cpp:3091-3095](../../source/RBFtools.cpp), [cpp:3164](../../source/RBFtools.cpp) |
| BendRoll (2) | Euclidean (in $\mathbb{R}^3$) | 3 | [cpp:3106-3107](../../source/RBFtools.cpp) |
| ExpMap (3) | Euclidean (in $\mathbb{R}^3$) | 3 | [cpp:3100-3101](../../source/RBFtools.cpp) |
| SwingTwist (4) | swing-quat L2 + twist wrap | 5 | [cpp:3110-3114](../../source/RBFtools.cpp), [cpp:3882](../../source/RBFtools.cpp) |

---

## §4. 训练：核矩阵 + 求解

### §4.1 数学

距离矩阵 $D \in \mathbb{R}^{P \times P}$，$D_{ij} = d(\mathbf{p}_i, \mathbf{p}_j)$。

激活矩阵（per-pose σ，commit 0b `M_PER_POSE_SIGMA`）：
$$
K_{ij} = \varphi(D_{ij}, \sigma_j)
$$

其中 $\sigma_j$ 是 pose $j$ 的核宽度（[cpp:1727-1744](../../source/RBFtools.cpp)），$\varphi$ 是用户选择的核函数（Gaussian / Multiquadric / Inverse-MQ / Linear / TPS）。

Tikhonov 正则化（防奇异）：
$$
K \leftarrow K + \lambda I, \quad \lambda = \text{regularization 属性}
$$

求解每输出维 $c$：
$$
K \mathbf{w}_c = \mathbf{y}_c, \quad \mathbf{y}_c = \text{matValues}[\cdot, c] - \text{anchor}_c
$$

其中 $\text{anchor}_c = 1$（scale 维）或 $\text{baseValue}_c$（其他维）—— Generic 模式特有的 baseline subtraction（[cpp:1846-1855](../../source/RBFtools.cpp)）。

### §4.2 求解器分级

| Tier | 触发条件 | 复杂度 | 行号 |
|---|---|---|---|
| **Cholesky** | Auto + 上次成功 | $O(P^3/3) + m \cdot O(P^2)$ | [cpp:1872-1890](../../source/RBFtools.cpp) |
| **GE 回退** | Cholesky 失败 / ForceGE / 上次 GE | $m \cdot O(P^3)$ | [cpp:1896-1925](../../source/RBFtools.cpp) |

### §4.3 Quat-group 列特殊处理

列 $c$ 若属于某个 `quatGroupStarts` 的 4 列范围（`isQuatMember[c] == true`），其 RHS 设为零向量（[cpp:1841-1845](../../source/RBFtools.cpp)），weights 列保持全零——**这些列不参与标量解，留给 §5.1 的 QWA 覆盖**。

### §4.4 病态条件诊断指引

当 $K$ 接近奇异（poses 高度共线、重复、或冗余）时：
- $\|\mathbf{w}_c\|_\infty$ 可能爆炸（实测可达 $10^3$ 以上）
- 推理时即使解出，外插场景输出会剧烈震荡

**建议**：用户可设 `regularization >= 1e-3` 注入 $\lambda I$。这是**数值条件问题**，不是算法层 bug。本文档的算法契约不解决此问题；后续单独 conditioning 提示词处理（M4.x 候选）。

---

## §5. 输出侧：Multi-driven Quaternion 输出

**两条独立但可共存的路径**。下文 §5.1 / §5.2 / §5.3 分别说明，§5.4 描述边界与 overlap 检测。

### §5.1 路径 B1 — QWA (Quaternion Weighted Average) Power Iteration

#### §5.1.1 数学

用户通过 `outputQuaternionGroupStart[]` 数组属性声明：output 列从下标 $s$ 开始的 4 列 $(s, s+1, s+2, s+3)$ 是一个 quat group。

定义：
- $q_i^{(g)} = \text{matValues}(i, s_g\!:\!s_g\!+\!4) \in S^3$ —— pose $i$ 在 group $g$ 上的目标 quat
- $\phi_i = \varphi(d(\mathbf{x}, \mathbf{p}_i), \sigma_i)$ —— 推理时 pose $i$ 的激活值

构造 4×4 加权 covariance：
$$
M_g = \sum_{i=0}^{P-1} \max(0, \phi_i) \cdot q_i^{(g)} (q_i^{(g)})^{\!\top}
$$

（clamp 到 $\geq 0$ 是为保 PSD，[cpp:4313-4317](../../source/RBFtools.cpp)）

输出 quat 由最大特征向量给出：
$$
q_{\text{out}}^{(g)} = \arg\max_{q \in S^3} \, q^{\!\top} M_g\, q
$$

这是 **Markley 2007 averaging method** 的标准形式：用样本外积的最大特征向量作平均。**比 nlerp 更稳健**——不依赖参考四元数选择，且权重可任意非负。

#### §5.1.2 Power Iteration 求解

Maya 实时性约束下，避免 SVD/Eigen，用幂迭代（[cpp:3695-3777](../../source/RBFtools.cpp)）：

$$
q_{k+1} = \frac{M_g \, q_k}{\|M_g \, q_k\|}, \quad q_0 = (0, 0, 0, 1)\ \text{(identity seed)}
$$

收敛判据（双重）：
- $\|q_{k+1} - q_k\| < \text{tol}$，或
- $|q_{k+1} \cdot q_k| > 1 - \text{tol}^2$（捕获 ± 振荡）

退化处理：
- $\text{tr}(M_g) < \epsilon$ → ZERO_MASS，输出 identity quat（[cpp:3791-3796](../../source/RBFtools.cpp)）
- 主 seed 不收敛 → 备用 seed = $M_g \cdot (1,1,1,1)^{\!\top}$（[cpp:3756-3767](../../source/RBFtools.cpp)）
- $q_w < 0$ → 翻号统一到 $q_w \geq 0$ 半球（[cpp:3770-3773](../../source/RBFtools.cpp)）

#### §5.1.3 代码链

| 步骤 | 行号 |
|---|---|
| 用户输入校验 → `quatGroupStarts` / `isQuatMember` | [cpp:1640-1690](../../source/RBFtools.cpp), [cpp:3820-3878](../../source/RBFtools.cpp) |
| 标量 sum 跳过 quat 列 | [cpp:4302](../../source/RBFtools.cpp) |
| $M_g$ 累积 | [cpp:4310-4337](../../source/RBFtools.cpp) |
| Power Iteration | [cpp:3695-3777](../../source/RBFtools.cpp) |
| 写回 `out[s..s+3]` | [cpp:4345-4355](../../source/RBFtools.cpp) |

### §5.2 路径 B2 — outputEncoding 节点级 inverse transform

#### §5.2.1 适用场景

输出是 Maya transform 节点的 rotateXYZ Euler triple（最常见的 rigging 场景）。**默认标量加权和会把 Euler 当独立 scalar 加权 → 大旋转下产生扭曲 / Gimbal 撕裂**。

`outputEncoding ∈ {0=Euler/None, 1=Quaternion, 2=ExpMap}` 控制输出三元组的重建方式。

#### §5.2.2 Quat path（[cpp:3475-3498](../../source/RBFtools.cpp)）

对每个 3-block $(s, s+1, s+2)$（即 rxs/rys/rzs）:

1. 每 pose $i$ 把 Euler 编码成 quat: $q_i = \mathcal{E}_{\text{quat}}(\text{poseVals}(i, s\!:\!s\!+\!3))$
2. nlerp 加权（短弧选择）：
$$
\mathbf{S} = \sum_{i} \phi_i \cdot \text{sign}(q_i \cdot q_0) \cdot q_i, \qquad q_{\text{out}} = \frac{\mathbf{S}}{\|\mathbf{S}\|}
$$
3. Decode 回 Euler，覆盖 `weightsArray[s..s+2]`

#### §5.2.3 ExpMap path（[cpp:3500-3525](../../source/RBFtools.cpp)）

1. $\ell_i = \log(q_i) \in \mathbb{R}^3$ —— quat → 3D 李代数
2. 线性加权（李代数空间是欧氏）：
$$
\boldsymbol{\ell}_{\text{out}} = \sum_i \phi_i \cdot \ell_i
$$
3. $q_{\text{out}} = \exp(\boldsymbol{\ell}_{\text{out}})$ → decode 回 Euler → 覆盖

#### §5.2.4 nlerp vs SLERP 选择理由

| 性质 | nlerp | SLERP |
|---|---|---|
| 关联性/可交换性 | ✓ | ✗ (多项加权时不闭合) |
| 权重梯度连续 | ✓ | ✗ (active set 切换瞬间不连续) |
| 角速度均匀 | ✗ | ✓ |
| 工业 PSD 标准 | ✓（Maya/Houdini）| ✗ |

RBF 在权重过渡时优先 **梯度连续性** > 角速度均匀（rigging 关心动画器手感），故选 nlerp。详见 [cpp:3317-3322](../../source/RBFtools.cpp) 注释。

#### §5.2.5 perPosePhi 重算

[cpp:3380-3418](../../source/RBFtools.cpp) `computePerPosePhi`：B2 路径需要 per-pose $\phi_i$ 但 `getPoseWeights` 已经把它们 sum 进了标量 weights。**重新跑一遍 per-pose distance + interpolateRbf 循环**才能拿到独立的 $\phi_i$ 数组（重复计算成本 $O(P)$，可接受）。**两次循环必须用同一 `widths` / `kernel` / `dist` 输入**保证数学一致。

### §5.3 路径 A — 标量加权和（默认 fallback）

对未被 B1（quatGroupStarts）覆盖、且 outputEncoding=0 时的所有列：

$$
\text{out}[c] = \sum_{i=0}^{P-1} W(i, c) \cdot \phi_i + \text{anchor}_c
$$

[cpp:4300-4304](../../source/RBFtools.cpp) 实现。这是 v4 legacy 行为，对 scale / 单维标量正确，对未声明的 Euler 三元组**会产生扭曲**（这是 B2 出现的动机）。

### §5.4 B1 vs B2 vs A 的边界

| 维度 | B1 (QWA quatGroupStarts) | B2 (outputEncoding) | A (default) |
|---|---|---|---|
| 输出列尺寸 | 4 列/group | 3 列/block | 1 列 |
| 几何意义 | 直接消费 quat 4-tuple | Euler triple inverse | 标量 / scale |
| 加权方法 | Markley 最大特征向量 | nlerp / ExpMap 线性 | $W \cdot \phi$ 加权和 |
| 数值稳健性 | 最强（全局最优）| 中（nlerp 短弧）| 弱（旋转扭曲）|
| 用户配置 | `outputQuaternionGroupStart[]` 多 int 数组 | `outputEncoding` 单 enum | （默认）|
| 适用 use case | 下游消费 quat（aim/orient constraint 后端）| Maya transform.rotateXYZ | scale, blendShape 权重等标量 |

#### §5.4.1 共存机制（M_P0_QUAT_RBF_OVERLAP_DISCLOSE）

**列下标域**：B1 占 `[s_g, s_g+4)` × G 个 group，B2 占 `[3b, 3b+3)` × $\lfloor C/3 \rfloor$ 个 block，A 占其他列。

**潜在冲突**：B1 group `[2, 6)` 与 B2 block 1 `[3, 6)` 重叠 → 没有保护时 B2 会覆盖 B1 的输出。

**安全网设计**（land 于 `M_P0_QUAT_RBF_OVERLAP_DISCLOSE`）：
- `applyOutputEncodingBlend` 接受 `isQuatMember` mask
- 对每个 3-block，若 mask 在 `[s, s+3)` 任一位置为 `true`，跳过该 block，B1 优先
- 触发一次 once-per-rig 警告：`": outputEncoding 3-block at [s] overlaps quaternion group; skipped to preserve B1 QWA output."`

---

## §6. 完整推理调用链（compute）

```
compute()  cpp:1132+
  ├─ 读 plug 值 (active/kernel/regularization/...)  cpp:1162-1236
  ├─ inputEncoding safety net + effectiveEncoding   cpp:1452-1505
  │    └─ getPoseData(...) → matPoses, matValues     cpp:2493+
  │         └─ encodeDriverVector + encode pose rows cpp:2683-2899
  ├─ resolveQuaternionGroups → quatGroupStarts /     cpp:1633-1693,
  │                            isQuatMember          cpp:3820-3878
  ├─ 训练 (evalInput == true)                        cpp:1746+
  │    ├─ getDistances → linMat (P×P)               cpp:1758, 3006
  │    ├─ getActivations(linMat, σ_j, kernel)       cpp:1785
  │    ├─ linMat += λI                              cpp:1800-1804
  │    ├─ y_c = matValues[:,c] - anchor_c           cpp:1829-1856
  │    │    └─ quat-group 列设零 RHS                cpp:1841-1845
  │    ├─ Cholesky / GE solve → wMat                cpp:1872-1925
  │    └─ wMat dump (exposeData≥3)                  cpp:1927-1928
  ├─ 推理                                            cpp:1937
  │    └─ getPoseWeights(...)                       cpp:4224+
  │         ├─ φ_i = φ(d(driver, p_i), σ_i)         cpp:4285-4295
  │         ├─ 路径 A: scalar accumulate            cpp:4300-4304
  │         │   (skip quat-member cols)             cpp:4302
  │         ├─ 路径 B1: M_g 累积                    cpp:4310-4337
  │         └─ 路径 B1: QWA Power Iter → out[s..s+3] cpp:4345-4355
  ├─ 路径 B2: outputEncoding inverse transform       cpp:1972+
  │    ├─ computePerPosePhi (重跑 per-pose)         cpp:3380
  │    └─ applyOutputEncodingBlend (3-block 覆盖)   cpp:3445-3527
  │        ├─ Quat path: encode→nlerp→decode        cpp:3475-3498
  │        ├─ ExpMap path: log→sum→exp→decode       cpp:3500-3525
  │        └─ overlap skip (B1 优先)                 cpp:M_P0_QUAT_RBF_OVERLAP_DISCLOSE
  ├─ 标量 post-processing                            cpp:2034-2100+
  │    └─ allowNegative / interpolate / scale /     
  │       baseline add-back（quat-member 列跳过）    cpp:2042-2043
  └─ setOutputValues → DG output                    cpp:4371+
```

---

## §7. 落地状态（landing snapshot）

| 模块 | 状态 | 关键 commit |
|---|---|---|
| Multi-driver Quat encode (4N 维通用) | ✅ Land | M_QUATERNION_BACKEND（基线）|
| Per-block quat distance | ✅ Land | M_QUATERNION_BACKEND |
| Tikhonov + Cholesky/GE 双 tier | ✅ Land | M1.4 |
| Per-pose σ | ✅ Land | M_PER_POSE_SIGMA |
| QWA Power Iteration (B1) | ✅ Land | M2.2 |
| outputEncoding inverse Quat (B2) | ✅ Land | ce136dd |
| outputEncoding ExpMap path | ✅ Land | eb27d68 / 8004606 (M_P0_OUTPUT_EXPMAP_FIX) |
| BendRoll / SwingTwist input | ✅ Land | M2.1b |
| Matrix↔encoding 互斥护栏 | ✅ Land | cpp:1539 |
| ExpMap output enum 编号 fix | ✅ Land | M_P0_OUTPUT_EXPMAP_FIX |
| 算法权威文档（本文档）| ✅ Land | M_P0_QUAT_RBF_LANDING_GUARDS |
| E2E + Unit + AST 守护 | ✅ Land | M_P0_QUAT_RBF_LANDING_GUARDS |
| B1↔B2 overlap disclose | ✅ Land | M_P0_QUAT_RBF_OVERLAP_DISCLOSE |

**未 land / 后续候选：**
- ill-conditioning warning（$\|\mathbf{w}\|_\infty > T$ 时 disclose）—— P2 conditioning 提示词
- Per-driver 混编 inputEncoding —— P3 schema 扩展
- Per-driven-block outputEncoding —— P3 schema 扩展
- Eigen::SelfAdjointEigenSolver 替换 Power Iteration —— M4.5 forward
- N > 16 driver stress —— P3 stress

---

## §8. 长期通用性保证

| 维度 | 是否已支持 | 边界 |
|---|---|---|
| Driver 数 N（Quat input）| ✅ N=K 通用，$D_{\text{eff}} = 4K$ | Maya `input[]` 数组上限（实测 K≤16 安全，经验 K≤32 上限）|
| Driven 端 quat group 数 G | ✅ 任意多个，仅靠 `outputQuaternionGroupStart[]` 长度 | overlap 由 §5.4.1 安全网保护 |
| Driven 端 Euler 3-block 数 | ✅ `applyOutputEncodingBlend` 跑 `count / 3` 个 block | 必须 contiguous，与 B1 不重叠 |
| 输入混编（部分 driver Quat、部分 Raw）| ❌ 不支持 | inputEncoding 是节点级单 enum |
| 输出混编（部分 quat、部分 Euler、部分 scalar）| ✅ 通过 B1+B2+A 列下标分割 | overlap 由安全网保护 |

**N=K 通用证明**（gripping 关键不变量）：

1. [cpp:2670](../../source/RBFtools.cpp): `groups = inDim / 3` 自动从 inDim 推 N
2. [cpp:2672/2674/2676](../../source/RBFtools.cpp): `effectiveInDim` 公式仅含 N、不含常数
3. [cpp:2683](../../source/RBFtools.cpp): `driver.assign(effectiveInDim, 0.0)` 不 hardcode
4. [cpp:2686/2699/2713/2725](../../source/RBFtools.cpp): 每条 encode 分支循环 `g=0..groups-1`
5. [cpp:2842/2855/2869/2882](../../source/RBFtools.cpp): pose row 同样循环
6. [cpp:2757](../../source/RBFtools.cpp): `poseData.setSize(poseCount, effectiveInDim)`
7. [cpp:2919-2921](../../source/RBFtools.cpp): bounds vec 同样用 `effectiveInDim`

以上 7 个不变量任一被 hardcode（如改成 `4`、`12`），AST 守护测试 `test_m_p0_quat_rbf_ast_guards.py` 立刻失败。

---

## §9. 验证矩阵

由 `M_P0_QUAT_RBF_LANDING_GUARDS` 三件套测试守护：

- **E2E**（[test_m_p0_quat_rbf_e2e.py](../../modules/RBFtools/tests/test_m_p0_quat_rbf_e2e.py)）：mayapy 端到端，N ∈ {1, 3, 5, 10, 16} × 4 encoding × 双输出路径
- **Unit**（[test_m_p0_quat_rbf_unit.py](../../modules/RBFtools/tests/test_m_p0_quat_rbf_unit.py)）：Pure-Python 数学性质验证（encode / distance / QWA / nlerp / ExpMap）
- **AST**（[test_m_p0_quat_rbf_ast_guards.py](../../modules/RBFtools/tests/test_m_p0_quat_rbf_ast_guards.py)）：22 项 cpp 字面量不变量

---

## §10. 引用 commits

- `M_QUATERNION_BACKEND` —— 基线 multi-driver quat encode + per-block 距离
- `M_PER_POSE_SIGMA` —— per-pose 核宽度
- `M2.1a/b` —— BendRoll / SwingTwist 编码 land
- `M2.2` —— QWA Power Iteration land（B1 路径）
- `ce136dd` (`M_P0_QUATERNION_BACKEND_LAND`) —— outputEncoding inverse transform land（B2 Quat）
- `M_P0_OUTPUT_EXPMAP_FIX` —— B2 ExpMap 编号修复
- `M_P0_QUATERNION_HONEST_DISCLOSURE` —— UI 端 honest disclosure
- `M_P0_QUAT_RBF_LANDING_GUARDS` —— 本次：算法文档 + 三件套测试
- `M_P0_QUAT_RBF_OVERLAP_DISCLOSE` —— 本次：B1↔B2 overlap 安全网
