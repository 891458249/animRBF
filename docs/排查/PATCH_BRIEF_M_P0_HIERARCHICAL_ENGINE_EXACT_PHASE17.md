# Patch Brief — M_P0_HIERARCHICAL_ENGINE_EXACT + PHASE17 (Phase 16.5 / 17)

> 执行者会话自查 + 设计稿 (2026-05-28). 用户指令: "用 Fable5 全面完善整个插件",
> Phase 16 实测检查由执行者用 mayapy 代跑.
>
> **Origin**: mayapy 双版本 (2022/2025) e2e 实测暴露 Phase 16 分层引擎数学不自洽
> (场景 D FAIL + delta 双重计入被 Output Clamp 掩盖). 本 patch 一次性:
> ① 修正 Phase 16 训练/推理数学; ② 落地 Phase 17a (scale 乘性 delta) +
> Phase 17b (quaternion so(3) delta).

---

## §1 mayapy 实测结果 + Bug 清单

### 1.1 实测 (场景 A-D, brief §12.2)

| 场景 | 2022 | 2025 | 结论 |
|---|---|---|---|
| A backward-compat (全 parent=-1) | PASS | PASS | 默认值/无 .ma 污染均正确 |
| B round-trip (parent/mask → save → reload) | PASS | PASS | SUBATTR_REFACTOR 修复生效 |
| C sibling mask 不一致 warn | — | PASS | union + warn 正确 |
| D quaternion 通道 = Base_Output | — | **FAIL** | delta 渗入 quat 通道 |

附带发现 **M_P0_INT32ARRAY_SETATTR_FIX** (已修): Maya Python `setAttr`
的 `Int32Array` 不接受 MEL 风格 count-prefix 形式 — `setAttr(plug, 2, 0, 2)`
静默存成 `[2]`, `setAttr(plug, 0)` 存成 `[0]` (语义反转: 空=全部 driver vs
[0]=仅 driver 0). 正确形式为单 list 参数 `setAttr(plug, [0, 2], type=...)`.
mayapy 2022/2025 实测一致. controller/core 写路径已改 + 防回归 guard.

### 1.2 源码审计 Bug 清单 (场景 D 根因展开)

| # | 位置 | 问题 |
|---|---|---|
| A | cpp getPoseWeights 调用点 | 推理 Base_Output 用 **legacy 全 pose wMat** (含 delta pose), 非 brief §3.1 的 baseNet. 后果: ① quat "= Base_Output" 实际含 delta pose (场景 D FAIL); ② delta 双重计入 (legacy 输出在 child pose 处已≈Actual, 再加 α·Δ), 靠 Output Clamp 钳回掩盖 (实测输出正好压在 trained max) |
| B | cpp inferSubNet (训练 Pred_base) | 用固定高斯近似, 与推理前向 kernel 不一致 → delta RHS 错位 |
| C | cpp Pass 2 phi_child | 推理 delta 前向也是高斯近似, 与 deltaNet 训练 kernel 不一致 → child pose 处插值条件破坏 |
| E | cpp trainSubNet | `getDistances` 后**缺 `getActivations`** — 拿原始距离矩阵当 K 解, 训练基与所选 kernel 无关 |
| F | cpp trainSubNet RHS | 缺 M1.2 anchor 减除 (finalize 会加回 anchor → base 输出系统性偏移) + 缺 quat 通道 RHS 置零 |
| G | cpp trainSubNet poly | polyMat 全零占位 — CPD kernel (TPS/MQ/Linear) 子网无多项式增广, anchor #4 在子网路径形同虚设 |
| H | mask-only 配置 | deltaNets 空但 mask 非空时, 推理仍走全 driver legacy 路径 — Driver Mask 单独使用完全无效 |

**历史澄清**: handoff §2 所述 Phase 15 "Shepard for Scale (Part B)" 在 C++
中无独立实现; scale 通道实际防 overshoot 机制 = anchor 1.0 baseline + Output
Clamp. 本 brief 据实修订.

---

## §2 数学 — 精确分层引擎

### 2.1 符号

- 驱动全向量 $x \in \mathbb{R}^{D}$ (post-encoding, post-normalize 列空间)
- base pose 集 $B$, 父 $p$ 的 children 集 $C_p$
- 子网 driver 子集投影 $\pi_S(x) = (x_{d})_{d \in S}$
- 核 $\varphi(d, \sigma)$ = 用户所选 kernel (`interpolateRbf`), per-pose
  $\sigma_i$, 训练 K 用 $\sigma_{ij} = (\sigma_i + \sigma_j)/2$ (M_PER_POSE_SIGMA 对称性)
- anchor $a_c$ = `outputIsScale[c] ? 1.0 : baseValue[c]` (M1.2)

### 2.2 训练

**baseNet** (driver 子集 $S_B$ = union(base masks)):

$$K^{B}_{ij} = \varphi\big(\|\pi_{S_B}(x_i) - \pi_{S_B}(x_j)\|, \sigma_{ij}\big) + \lambda \delta_{ij}, \quad i,j \in B$$

RHS 取 **anchored 空间**: $\tilde{y}_{i,c} = y_{i,c} - a_c$; quat 通道 RHS = 0
(QWA 不走 wMat). CPD kernel ($\text{polyDim} = 1+|S_B|$) 解增广鞍点系统
$\begin{pmatrix} K+\lambda I & P \\ P^\top & 0 \end{pmatrix}$, 含 C-lite 退化列
丢弃 (anchor #3/#4 与 legacy 主路径完全同构, 仅作用于子集).

**Base 前向** (训练与推理共用同一代码路径 — 修 Bug B 的结构保证):

$$f^{B}_c(x) = \sum_{i \in B} w^{B}_{i,c}\,\varphi(\|\pi_{S_B}(x) - \pi_{S_B}(x_i)\|, \sigma_i) + \sum_k a^{B}_{k,c}\, p_k(\pi_{S_B}(x))$$

quat group $g$ (列 $s..s{+}3$): $q_b(x) = \mathrm{QWA}\big(\{q_i\}_{i \in B}, \{\varphi_i(x)\}\big)$ (Markley 最大特征向量, M2.2 现成).

**deltaNet$_p$** (driver 子集 $S_p$ = union(children masks), K 同构于上):

按通道类型构造 RHS (全部在 anchored / 相对 / 切空间 — 三者皆为线性空间, 标量
RBF 插值合法):

| 通道类型 | RHS $\Delta_{i,c}$ ($i \in C_p$) |
|---|---|
| translate/rotate (加性) | $(y_{i,c} - a_c) - f^{B}_c(x_i)$ |
| scale (乘性, **Phase 17a**) | $\dfrac{y_{i,c}}{f^{B}_c(x_i) + 1} - 1$, 防御: $\|f^{B}_c(x_i)+1\| < 10^{-6}$ 时置 0 + warn |
| quat group (so(3), **Phase 17b**) | $\delta_i = \log\big(q_b(x_i)^{-1} \otimes q_{a,i}\big) \in \mathbb{R}^3$ 写入列 $s..s{+}2$, 列 $s{+}3$ 置 0; $q_{a,i}$ 先归一化 + 半球对齐 ($\langle q_a, q_b \rangle < 0 \Rightarrow q_a \leftarrow -q_a$) |

**delta 前向 = 纯标量插值** (传空 quat group → 全列走 scalar 路径):

$$\Delta_c^{(p)}(x) = \sum_{i \in C_p} w^{(p)}_{i,c}\,\varphi(\|\pi_{S_p}(x) - \pi_{S_p}(x_i)\|, \sigma_i) + \text{poly}$$

### 2.3 推理 (Three-Pass, 修正版)

启用条件 `subnetEngaged` = 训练时 anyExplicitParent **或** anyExplicitMask
(修 Bug H: mask-only 也走子网). 否则 fast path = legacy 全网 (Phase 15 数值等价).

1. **Pass 1**: `weightsArray` ← 子集 getPoseWeights(baseNet) — 真 Base_Output
   (scalar + QWA 一体). 同时算 gate 核 $\phi_i(x)$ (见 §2.4).
2. **Pass 2**: 每个 parent $p$: $\alpha_p = \phi_p / \sum_{k \in B} \phi_k$
   (partition of unity; $\sum_k \phi_k < 10^{-12}$ → 全 $\alpha=0$, 纯 base 输出);
   $\Delta^{(p)}(x)$ ← 子集 getPoseWeights(deltaNet$_p$, 空 quat group).
3. **Pass 3** 按通道合成 (全部在 anchored 空间操作 weightsArray, finalize 再加 anchor):
   - 加性: $\tilde{y}_c \mathrel{+}= \sum_p \alpha_p \Delta^{(p)}_c$
   - 乘性 (scale): $\tilde{y}_c \leftarrow \big(\tilde{y}_c + 1\big) \prod_p \big(1 + \alpha_p \Delta^{(p)}_c\big) - 1$
     (finalize 加回 $a_c{=}1$ 后即 $y = y_{\text{base}} \prod (1+\alpha\Delta^{\text{rel}})$)
   - quat group: $v_g = \sum_p \alpha_p\, \delta^{(p)}_g(x) \in \mathbb{R}^3$ (切空间线性叠加),
     $q_{\text{final}} = q_b \otimes \exp(v_g)$, 归一化后写回 4 通道.
     $\|v_g\| < 10^{-12}$ → $\exp = $ identity.

插值条件自洽性 ($\lambda \to 0$): 在 child pose $x_i$ 处 $\Delta^{(p)}(x_i) = \Delta_{i}$
(RBF 插值性质), 故加性通道 $y(x_i) = f^B(x_i) + \alpha_p\,[y_i - f^B(x_i)]$;
$\alpha_p < 1$ 为 Shepard gate 的有意设计 (部分贡献, 远离 parent 衰减为 0) —
与 Combo BlendShape "corrective 按 driver 接近度激活" 工业语义一致.

### 2.4 Gate 核独立性 (brief v2.5 纠错)

原 brief §3.1 要求 gate 用 $\varphi(\cdot, \text{kernelType})$. **数学上不可行**:
gate 必须满足 ① $\phi(0) = \max$; ② 随距离单调递减 → 0. Gaussian 满足;
**TPS ($r^2 \log r$, 增函数) / MQ ($\sqrt{d^2+w^2}$, 增函数) / Linear ($d$) 均违反**
— 用作 gate 会让"远 parent 贡献最大", 反转 anti-leak 保证. 故 gate 固定用
Gaussian $\phi_i = e^{-d_i^2/\sigma^2}$ (插值核仍随用户选择). Shepard 1968
partition of unity 只要求权函数衰减, 不要求与插值基一致.

### 2.5 文献

- Shepard 1968 (partition of unity); Hoeffding 1948 (ANOVA 分解)
- Grassia 1998, *Practical parameterization of rotations using the exponential map* (so(3) log/exp)
- Markley et al. 2007 (QWA 四元数平均); Wendland SDA Thm 10.3 (CPD + poly 增广)

---

## §3 实施清单 (source/RBFtools.cpp, 全部锁在 subnetEngaged 路径内)

| # | 改动 |
|---|---|
| 1 | `RBFtools.h`: 成员 `bool subnetEngaged;` (构造 false); RBFSubNet 不变 |
| 2 | trainSubNet lambda: + `getActivations(linMatSub, subWidths, fallback, kernelVal)` (subWidths = perPoseWidths 子集); polyDim>0 走子集版增广 GE (detectDegeneratePolyCols + reduced P + 解展开, 复刻 legacy 2467-2650 模式); 失败语义不变 |
| 3 | 训练 orchestration: baseNet RHS = anchored matValues (quat 列置 0); delta RHS 按 §2.2 表格三类通道构造; `subnetEngaged = anyExplicitParent \|\| anyExplicitMask` 训练时落盘 |
| 4 | 新 lambda `inferSubNetExact(net, driverRaw, useQuat)` — 子集化包装 getPoseWeights (poses/values/widths/norms 子集; useQuat=true 传真实 quat group [base 用], false 传空 [delta 用]); 训练 Pred_base 与推理共用 |
| 5 | 推理: `subnetEngaged && genericMode` 时 Pass 1 用 inferSubNetExact(baseNet, true) 替代 legacy getPoseWeights 调用; 否则原路径不动 |
| 6 | Pass 2/3 重写: 删高斯 phi_child 内联前向; 改为 inferSubNetExact(deltaNet, false) + 三类通道合成 (加性 / 乘性累积 / so(3) 累积 + exp 回写) |
| 7 | quat 工具: `quatLogSO3 / quatExpSO3 / quatMulWXYZ / quatHemiAlign` (静态自由函数, 16 行内) |
| 8 | 老 inferSubNet (高斯近似) 删除; prevPoseParentArr 拓扑解析的 self-parent/OOB 守卫保留 |

**Python/UI/schema: 零改动** (本 patch 纯 C++ 数学层).

## §4 不动什么 (4/4 anchors)

1. TPS r≤0 oracle — `interpolateRbf` 不动 (子网通过 getActivations 复用它)
2. Honest-failure — trainSubNet 失败仍 displayError + legacy fallback; 新增 scale 除零 warn
3. Column-rank C-lite — 子网增广路径调用同一 `detectDegeneratePolyCols` (从"结构占位"升为"真跑")
4. polyDim = 1+d — 子网 CPD 增广真解 (Bug G 修复即 anchor #4 强化)
5. Phase 15 路径 (fast path / Output Clamp / Input Clamp / anchor 流) 完全不动; 全 parent=-1 + 空 mask 数值等价保持

## §5 验证

1. mayapy e2e v2 (双版本): 场景 A/B/C/D 全 PASS + 新增:
   - E (乘性): scale 通道在 child pose 处 ≈ Actual (clamp off, λ=0, 容差 1e-3)
   - F (so(3)): quat 通道分层后 = $q_b \otimes \exp(\alpha\delta)$; 远 driver → $q_b$
   - G (插值条件): driver = child pose → 加性通道输出 = $f^B + \alpha(y_i - f^B)$ 解析值
   - H (mask-only): 无 parent 仅 mask → 输出仅依赖 mask 内 driver (改 mask 外 driver 输出不变)
2. 纯 Python 镜像测试: case 9/10 改 Phase 17 语义; 新增乘性/so(3) 参考实现 case
3. 全 sweep 0 回归; 双 .mll strings 含 "PHASE17" marker

## §6 Commit chain (Policy B)

1. `fix(py): Int32Array setAttr list-form (M_P0_INT32ARRAY_SETATTR_FIX)` — 已含 e2e 防回归 guard
2. `fix(plugin/train): subnet exact training — activations + anchored RHS + subset poly augmentation (Bug E/F/G)`
3. `fix(plugin/infer): Base_Output from baseNet + unified subnet forward (Bug A/B/C/H)`
4. `feat(plugin): Phase 17a multiplicative scale delta`
5. `feat(plugin): Phase 17b quaternion so(3) delta blending`
6. `chore(deploy): dual .mll rebuild (PHASE17)`
7. `test: e2e v2 + math mirror updates + sweep`
8. `chore(installer): rebuild`
9. `docs: this brief + handoff update`
