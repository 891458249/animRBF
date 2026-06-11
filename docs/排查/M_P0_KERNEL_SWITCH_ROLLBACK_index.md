# M_P0_KERNEL_SWITCH_ROLLBACK — 算法路径回退索引

**日期**: 2026-05-11
**worktree HEAD**: `ee6d63f` (M_P0_LAMBDA_CEIL_TIGHTEN, 已 FF 到 origin/main)
**oracle**: `X:\RBFtools` (用户上周备份, 切 kernel 不飘)
**current**: `X:\Plugins\RBFtools` (当前 main, 切 kernel 飘)

---

## §0.5 — Oracle 版本 git archaeology (2026-05-11)

**Oracle SHA256 (用户上周备份 `X:\RBFtools`)**:
```
RBFtools.cpp    D6DCCB574934AC87846C4CD1684AAB543A53CF5C85D0796EACBBF30724201DC7
RBFtools.h      AF8E1597B5DBEB4D8332DA2448847949FC86D3B2AFE58D60502E98936C2998B0
controller.py   091441C1895A920D0999FCD3F20B001D9A46B8E01DFB727201442B951F4D5FE8
```

**字面匹配 commit**: **NONE**. Oracle 不是任何 git commit 的字节级 snapshot. 含用户本地未提交修改, 或备份时间介于两 commit 之间.

**最接近行为锚点的 commit**: **`e249ec0`** (`156af4c~1`, 即 M_P0_AUTO_ADAPTIVE_LAMBDA 引入前的 parent)
- date: 2026-05-10 13:50
- title: `feat(controller): bump default regularization 1e-4 -> 1e-3 (M_P0_CREATE_NODE_REGULARIZATION followup)`
- 注: e249ec0 仅改 controller.py, 不动 cpp; 故 cpp 行为追溯到 `e249ec0~1` = `f2a3d0b` 同 cpp.

**`git show e249ec0:source/RBFtools.cpp` SHA256**: `def1791f6c57ae14b1ad2427f840d1b926e7d11b7f6dbba31b61d6aae122acb5` (≠ oracle 的 D6DCCB...). 字面 diff 估 ~50 LoC 用户本地小修.

**反向 cherry-pick 基准**: `git show e249ec0:source/RBFtools.cpp` 用作 ROLLBACK_1/2 的真值参照. 反向不取 oracle 文件本身 (含未知本地修改), 取 git 历史的 e249ec0 cpp 段.

**Step 0.3 行为锚点逐项 verify** (实测 oracle):

| 锚点 | 期望 | Oracle 实测 | 状态 |
|---|---|---|---|
| TPS r≤0 守卫 | `else result = value;` | grep 命中 cpp:3801-3808 `else result = value;` | ✓ 锚点匹配 |
| λ retry loop 不存在 | `grep -c "lambda retry\|adaptive λ\|adaptiveLambda" ` = 0 | 实测 0 | ✓ 锚点匹配 |
| C++ prev-tracker 仅 oracle 既有 (`prevSolverMethodVal` + `prevInputEncodingVal` + `prevQuatGroupConfigHash`) | 无 `prevKernel/prevDistance/prevRadius/prevRadiusType/prevRegularization` 5 个 4c379ad 新增项 | grep `prev[KDR]` (区分 4c379ad 命名) = 0; oracle 仅 3 既有 | ✓ 锚点匹配 |
| Python `_TRAINING_AFFECTING_ATTRS` frozenset 不存在 | grep oracle controller.py = 0 | 实测 0 | ✓ 锚点匹配 |

**4/4 锚点全 match → oracle ≈ commit e249ec0 时代行为**. ROLLBACK_1/2/5/6 反向回退到此基准是数学上正确的等价回退, 行为锚点 verifiable.

**Step 0.5 nit (Planner 要求, controller-side λ default 锚点)**:

| 锚点 | Oracle 实测 | 锁定 commit |
|---|---|---|
| controller.py `regularization` / `1e-[0-9]` 字面命中 | **0 hit** (oracle controller 完全无 λ override 块) | 必 ≤ `f2a3d0b~1` = `be93ef5` (M_P0_CREATE_NODE_REGULARIZATION 引入前) |
| core.py read-side fallback `g(shape+".regularization", 1.0e-8)` | `1e-8` (oracle core.py:368) | 与 cpp schema default 1e-8 (cpp:531) 一致 |
| Effective λ default (new node creation) | **1e-8** (来自 cpp schema, 因 oracle controller 不 override) | 与 cpp schema default 一致, 不依赖 controller |

**`1e-8` 的歧义解释** (避免 Planner 错指 ee6d63f):
- 用户表格规则把 1e-8 → ee6d63f, 但 ee6d63f 是 LAMBDA_CEIL_TIGHTEN (revert 1e-3 → 1e-8 + 收紧 retry ceil), 与"无 retry loop"锚点矛盾.
- 真相: oracle 时代 controller 完全没"自动写 default λ"块 (`f2a3d0b` 之前). 1e-8 来自 **cpp schema setDefault** (cpp:531 自 e91243a M1 regularized solver 起一直是 1e-8, 从未改过).
- ee6d63f 是把 controller-side override **revert** 回 1e-8, 表面值同 cpp default 但 control 路径不同 (ee6d63f 仍写 setAttr, oracle 不写).

**最终 oracle 锁定** (Planner 修正 2026-05-11, 不再单点 sha 字面对齐):

> **Oracle ≈ `e249ec0` (cpp 行为) + pre-`f2a3d0b` (controller 无 λ override 块)**, 非单点 sha 字面对齐.

理由: oracle effective λ default = 1e-8 由 cpp schema cpp:531 `setDefault(1.0e-8)` 保证, 自 e91243a (M1 regularized solver) 起从未改过. controller 层无须额外锚定 sha — 只要 controller 不引入 λ override 块 (即 `f2a3d0b` 之前) 即满足.

| 维度 | 锚点 commit | 验证 |
|---|---|---|
| **C++ 行为** | `e249ec0` (= 156af4c~1) | 4 行为锚点 (TPS r≤0 = `value` / 无 λ retry / 无 4c379ad 5 prev-tracker / cpp schema λ default 1e-8) 全 match |
| **Python controller** | `< f2a3d0b` (任意 pre-CREATE_NODE_REGULARIZATION 状态) | controller 无 λ override 字面 + 无 `_TRAINING_AFFECTING_ATTRS` |

**反向 cherry-pick 真值**:
- cpp 段: `git show e249ec0:source/RBFtools.cpp` (cpp 自 5ebf1a0 至 e249ec0 无变化, 任意 e249ec0~ 上行均可作真值)
- controller 段: `git show f2a3d0b~1:modules/RBFtools/scripts/RBFtools/controller.py` (= `be93ef5` 内容, 取 controller "无 λ override" 状态)

**注**: 早期 `be93ef5` 表述被废弃, 因 `be93ef5` subject = `M_P0_APPLY_FORCE_GENERIC` 与 regularization 无关, 用之锁 oracle controller 时代会误导. 改用 `< f2a3d0b` (M_P0_CREATE_NODE_REGULARIZATION 引入前) 的语义表述.

---

**Step 0.5 nit — process amend 记录** (Planner policy A 落盘要求, 2026-05-11):

| 时间 | 事件 | 处理 |
|---|---|---|
| 2026-05-11 | amend `5090bcf` → `91adfc9` (含 build error fix `λ → lambda` Unicode 清洁 + cpp:2076 字符串拼接括号修正) | Planner ACK 一次性, 但**今后禁止自决 amend / rebase / reset / push --force** (policy A); 清洁项 (Unicode 替换等) 必须独立 commit, message 前缀 `chore(plugin):` 或 `style:` (policy B scope discipline). 本次 amend 对 ROLLBACK_2 commit message 文案的语义无影响 (功能差异: 字符串显示 `λ` → `lambda`, audit-anchor 不变), 但合并到原 commit 违反单点 commit 原则, 记录在案以供未来审计追溯. |

**注**: oracle 既有 3 个 prev-tracker (`prevSolverMethodVal` + `prevInputEncodingVal` + `prevQuatGroupConfigHash`) 是 M1.4/M2.1a/M2.2 自 land 的设计, 与 4c379ad 引入的"切 kernel 自动 promote evalInput=true"机制**正交** — 既有 3 个不 promote evalInput (`prevSolverMethodVal` 仅 reset `lastSolveMethod` cache, `prevQuatGroupConfigHash` 在 cpp:1627/1677 自有路径). 用户决议方案 E **保留** 4c379ad 引入的 5 个新 prev-tracker (UX 价值), 仅回退 TPS PSD (3.c) + λ retry loop (4.a/4.b).

---

## §1 — 老版本 7 区域权威索引

### (1) kernel 枚举定义与映射

| # | 文件:行 | 关键代码 | 行为摘要 |
|---|---|---|---|
| 1.a | `source/RBFtools.cpp:212-218` | `kernel = eAttr.create("kernel","kn",1);` + 6 `addField` 行 (Linear=0..IMQB=5) | 枚举注册 |
| 1.b | `source/RBFtools.cpp:3777-3821` | `interpolateRbf(value, width, kernelType)` 6-branch dispatch (Linear/Gaussian1/Gaussian2/TPS/MQ/IMQ) | kernel id → φ 数学函数映射 |

### (2) σ / radius 估计 (与 kernel 耦合)

| # | 文件:行 | 关键代码 | 行为摘要 |
|---|---|---|---|
| 2.a | `source/RBFtools.cpp:2905-2914` | `getRadiusValue()` 依 `radiusTypeVal` ∈ {0,1,2,custom} 返回 `meanVal`/`varianceVal`/`sqrt(varianceVal)`/`radiusVal` | radiusType → σ 源 dispatch (kernel-independent) |
| 2.b | `source/RBFtools.cpp:1761-1768` | 训练分支内 `meanVal = linMat.mean(); varianceVal = linMat.variance();` + `meanPlug.setValue(...)` | σ 在训练时从距离矩阵估计, 写回 plug 缓存 |
| 2.c | `source/RBFtools.cpp:1235-1236` | compute() 入口 `meanVal = meanPlug.asDouble(); varianceVal = variancePlug.asDouble();` | 推理读取缓存 σ |

### (3) K 矩阵构造 (kernel branch + TPS r=0 守卫位置)

| # | 文件:行 | 关键代码 | 行为摘要 |
|---|---|---|---|
| 3.a | `source/RBFtools.cpp:3705-3722` | `getActivations(BRMatrix &mat, double width, short kernelType)` — 单 σ 重载 | K = φ(d, σ) 双重循环 |
| 3.b | `source/RBFtools.cpp:3730-3760` | `getActivations(...,widths[],fallback,kernelType)` — per-pose σ 重载 (M_PER_POSE_SIGMA) | K[i,j] 用 σ_pair=(widths[i]+widths[j])/2 |
| 3.c | `source/RBFtools.cpp:3801-3808` (TPS branch) | `value /= width; if (value > 0) result = value*value*log(value); else result = value;` | **TPS r≤0 → 返回 r 本身** (oracle 行为) |

### (4) 求解器入口 (kernel 切换触发的重训 + λ 行为)

| # | 文件:行 | 关键代码 | 行为摘要 |
|---|---|---|---|
| 4.a | `source/RBFtools.cpp:1746-1929` | `if (evalInput) { ... getActivations + Cholesky tier 1 + GE tier 2 fallback ... }` | **单次求解, 无 λ retry loop** |
| 4.b | `source/RBFtools.cpp:1865-1925` | `bool usedCholesky = false; ...` (Cholesky tier 1) → `if (!usedCholesky) {...solve(yCols[c],w,singularIndex)}` (GE tier 2) | 两 tier dispatch, 失败即 `kFailure` |
| 4.c | `source/RBFtools.cpp:1217` | `evalInput = evaluatePlug.asBool();` (默认 false) | 仅 evaluate=1 时训练; **kernel 切换不主动触发** |

### (5) prev-tracker (与 kernel/radius/radiusType 相关)

| # | 文件:行 | 关键代码 | 行为摘要 |
|---|---|---|---|
| 5.a | `source/RBFtools.cpp:158` ctor | `prevSolverMethodVal(0)` (M1.4) | **唯一**的 prev-tracker, 仅 reset `lastSolveMethod` cache, **不 promote evalInput** |
| 5.b | `source/RBFtools.cpp:1816-1819` | `if (solverMethodVal != prevSolverMethodVal) { lastSolveMethod = 0; prevSolverMethodVal = solverMethodVal; }` | 切 solverMethod 时清 Cholesky 粘滞标记 |
| 5.c | (不存在) | — | **oracle 无 prevKernel/prevRadius/prevRadiusType/prevDistanceType/prevRegularization** |
| 5.d | (不存在) | — | **oracle 无 trainingAttrChanged → evalInput 提升路径** |

### (6) attributeAffects 表 (kernel-relevant)

| # | 文件:行 | 关键代码 | 行为摘要 |
|---|---|---|---|
| 6.a | `source/RBFtools.cpp:1013` | `attributeAffects(RBFtools::kernel, RBFtools::output);` | kernel → output dirty |
| 6.b | `source/RBFtools.cpp:990,997,1030,984` | `radius/distanceType/radiusType/regularization → output` 各一行 | 同, 全到 output, **不到 evalInput** |

### (7) UI kernel 下拉框 slot → controller → setAttr

| # | 文件:行 | 关键代码 | 行为摘要 |
|---|---|---|---|
| 7.a | `modules/RBFtools/scripts/RBFtools/ui/widgets/rbf_section.py:35,61,581-583` | `kernelChanged = QtCore.Signal(int)` + `_cmb_kernel.currentIndexChanged.connect(self._on_kernel)` + `_on_kernel(self,idx): self.attributeChanged.emit("kernel",idx); self.kernelChanged.emit(idx)` | UI 信号双发: 通用 setAttr + kernel 专用 |
| 7.b | `modules/RBFtools/scripts/RBFtools/ui/main_window.py:1166-1167` | `self._rbf_section.attributeChanged.connect(ctrl.set_attribute)` + `self._rbf_section.kernelChanged.connect(ctrl.on_kernel_changed)` | 双信号路由 |
| 7.c | `modules/RBFtools/scripts/RBFtools/controller.py:1349` `set_attribute` body | `core.set_node_attr(self._current_node, attr, value)` (无 toggle, 无 frozenset) | **直接写 attr, 无 evaluate=0/1 toggle** |
| 7.d | `modules/RBFtools/scripts/RBFtools/controller.py:1425-1430` `on_kernel_changed` | `core.lock_radius_type(self._current_node); self._emit_radius_state()` | 切 kernel 后锁/解锁 radiusType (Linear 时锁) + 刷新 UI |
| 7.e | `modules/RBFtools/scripts/RBFtools/core.py:2667` | `cmds.setAttr(shape + ".radiusType", lock=is_linear_kernel)` | radiusType lock 实现 (Linear 时禁用 σ 估计 dropdown) |

---

## §2 — 新版本对应位置 + 差异分类 (EQ / DIVERGE)

### 区域 (1) kernel 枚举 + φ 映射

| # | 老 | 新 | 分类 | 是否回退 |
|---|---|---|---|---|
| 1.a | `cpp:212-218` | `cpp:222-228` | **EQ** (字面一致, 6 field 名 + 索引完全相同) | 否 |
| 1.b | `cpp:3777-3821` | `cpp:4496-4555` | **EQ** (5 kernel 公式字面相同; **TPS branch 1 行差异见 3.c**) | 否 (TPS 单独处理) |

### 区域 (2) σ / radius 估计

| # | 老 | 新 | 分类 | 是否回退 |
|---|---|---|---|---|
| 2.a | `cpp:2905-2914` | `cpp:3187-3196` | **EQ** (`getRadiusValue` 字面相同, 4 分支同) | 否 |
| 2.b | `cpp:1761-1768` | `cpp:1849-1856` | **EQ** (σ 估计代码字面相同, 写 plug 同) | 否 |
| 2.c | `cpp:1235-1236` | `cpp:1253-1254` | **EQ** (字面相同) | 否 |

### 区域 (3) K 矩阵构造

| # | 老 | 新 | 分类 | 是否回退 |
|---|---|---|---|---|
| 3.a | `cpp:3705-3722` | `cpp:4372-4389` | **EQ** | 否 |
| 3.b | `cpp:3730-3760` | `cpp:4397-4427` | **EQ** | 否 |
| 3.c | `cpp:3801-3808` (TPS r≤0 → return value) | `cpp:4519-4561` (TPS r≤0 → return 0.0, M_P0_KERNEL_ALGO_AUDIT) | **DIVERGE** | **是** |

**3.c DIVERGE 说明**: M_P0_KERNEL_ALGO_AUDIT (`2600d3e`) 把 TPS 的 `else result = value;` 改成 `else result = 0.0;`. 改动声明动机是"`normalizeColumns` 浮点噪声产生 r ≈ -1e-15, 写负对角破坏 K PSD". 但**老版本就是 `result = value;` 行为, 用户实测不飘**, 说明老版本路径下浮点噪声不产生破坏性后果 (要么 normalize 不出负值, 要么 GE 路径吞掉负对角). 改成 `0.0` 把 K[i,i] 写 0 → K 矩阵的对角主导性丢失 → 病态 → drift. 这是切 TPS kernel 时的一个具体路径差异.

### 区域 (4) 求解器入口 + λ 行为

| # | 老 | 新 | 分类 | 是否回退 |
|---|---|---|---|---|
| 4.a | `cpp:1746-1929` (单次求解) | `cpp:1834-2125` (λ retry loop) | **DIVERGE** | **是** |
| 4.b | `cpp:1865-1925` (Cholesky tier 1 + GE tier 2 单次) | `cpp:2001-2110` (同 tier dispatch, 但包在 retry loop 内, λ 从 user 值 progressively 加到 ceil 1e-3) | **DIVERGE** (tier 逻辑同, retry 包装 = 新增) | **是** (移除 retry 包装, 保留 tier 逻辑) |
| 4.c | `cpp:1217` (evalInput from plug) | `cpp:1217` (字面相同) | **EQ** | 否 |

**4.a/4.b DIVERGE 说明**: M_P0_AUTO_ADAPTIVE_LAMBDA (`156af4c`) + M_P0_LAMBDA_CEIL_TIGHTEN (`ee6d63f`) 引入 retry loop, 切 kernel 后若 K 病态 (e.g. TPS) 则 λ 从 1e-8 progressively 加 (×10 每次) 直到 1e-3 ceil. 老版本无 retry, K 病态直接 `kFailure` 弹出报错. 用户报"算法数据紊乱"→ 高度可疑 retry loop 跑到 ceil 时给出**数值垃圾**而非诚实失败. 老版本"诚实失败"行为反而避免了 driven 飘.

### 区域 (5) prev-tracker

| # | 老 | 新 | 分类 | 是否回退 |
|---|---|---|---|---|
| 5.a | `cpp:158` (仅 prevSolverMethodVal) | `cpp:158` 同 + `cpp:170-174` 多 5 prev-tracker (prevKernel/prevDistanceType/prevRadiusType/prevRadius/prevRegularization) | **DIVERGE** | **是** |
| 5.b | `cpp:1816-1819` (solverMethod 切换清 lastSolveMethod) | `cpp:1816-1819` 字面相同 | **EQ** | 否 (保留 solverMethod tracker) |
| 5.c | (不存在) | `cpp:1282-1311` (kernel/dist/radius/radiusType/reg 比较 → trainingAttrChanged → evalInput=true) | **DIVERGE** | **是** |
| 5.d | (不存在) | `cpp:1222-1226` (`inputEncodingChangedThisFrame` flag) | **DIVERGE** | **是** |

**5.a/5.c/5.d DIVERGE 说明**: M_P0_TRAINING_AFFECTING_ATTRS (`4c379ad`) 引入. 设计意图: 切 kernel 后强制 retrain. 但 oracle 无此机制, 用户实测不飘, 说明 oracle 的"切 kernel 后用 OLD wMat × NEW kernel φ"行为反而**不产生 visible drift** (可能 driven 还在 driver 当前 driver 值附近 → wMat 与 kernel 错配的影响小). 加上 retrain 反而让 K 病态 → λ retry → 数值垃圾 → drift. **保留 prevSolverMethodVal** (5.b, oracle 既有).

### 区域 (6) attributeAffects 表

| # | 老 | 新 | 分类 | 是否回退 |
|---|---|---|---|---|
| 6.a | `cpp:1013` | `cpp:1023` | **EQ** | 否 |
| 6.b | `cpp:984/990/997/1030` | `cpp:994/1000/1007/1040` | **EQ** | 否 |

### 区域 (7) UI → controller

| # | 老 | 新 | 分类 | 是否回退 |
|---|---|---|---|---|
| 7.a | `rbf_section.py:35,61,581-583` | `rbf_section.py:35,61,649-651` | **EQ** (slot 字面相同, 双信号 emit) | 否 |
| 7.b | `main_window.py:1166-1167` | `main_window.py:1278` 同 connection | **EQ** | 否 |
| 7.c | `controller.py:1349` set_attribute (直接写 attr) | `controller.py:1472-1505` set_attribute + `_TRAINING_AFFECTING_ATTRS` frozenset + post-write `setAttr(.evaluate, 0); setAttr(.evaluate, 1)` toggle | **DIVERGE** | **是** |
| 7.d | `controller.py:1425-1430` on_kernel_changed | `controller.py:1565-1570` 字面相同 | **EQ** | 否 |
| 7.e | `core.py:2667` lock_radius_type | (current 同位置, 字面相同, 未 grep 但前序确认无变更) | **EQ** | 否 |

**7.c DIVERGE 说明**: M_P0_TRAINING_ATTRS_FORCE_RETRAIN (`a707bac`) 在 Python 层加 belt-and-suspenders — 切 kernel 时 controller 先 setAttr(kernel), 然后 setAttr(.evaluate, 0); setAttr(.evaluate, 1). 设计意图: 即使 C++ prev-tracker 漏触发, 也强制 evalInput=true 重训. 但 (a) C++ prev-tracker 本身就是新 bug (5), (b) 双重 toggle 在 Maya 2025 EM 下可能引入 race / 副作用. 配合 (5) 一起回退.

---

## §2.5 — DIVERGE 总数

**6 个 DIVERGE 项** (待回退):
- 3.c: TPS r≤0 分支 (1 行)
- 4.a/4.b: λ retry loop 移除 (恢复单次求解)
- 5.a: ctor 删除 5 个 prev-tracker init
- 5.c: 删除 trainingAttrChanged 提升块 (~30 LoC)
- 5.d: 删除 inputEncodingChangedThisFrame flag (~5 LoC)
- 7.c: Python set_attribute 删除 frozenset + toggle (~25 LoC)

**EQ 项总数**: 14 (不动)

**必须保留的新功能** (与本回退**正交**, diff 验证全部不在 DIVERGE 触及行内):
- ✅ multi-driver quaternion RBF — 在 cpp:2670-2860 (encodeDriverVector / getPoseData), 远离 §1746+ 训练块
- ✅ B1 QWA Markley / B2 nlerp — 在 cpp:1995-2060+ (compute 内 quat group block) + cpp:3995+ (nlerpQuaternions / decodeQuaternionToEuler), 远离回退点
- ✅ poses I/O 文件菜单 — Python ui/main_window.py 文件菜单, 不触 rbf_section
- ✅ apply_poses freeze (M_P0_APPLY_FREEZE_DURING_WRITE) — controller.apply_poses 内, 不触 set_attribute
- ✅ disconnect 后 scale 恢复 — controller.disconnect_outputs, 不触
- ✅ rbfMode UI resync + apply 强制 Generic — rbf_section + controller.apply_poses, 不触
- ✅ rest-pose tolerance 1e-3 — controller._collect_pose_input 调用域, 不触
- ✅ TPS 改动 (3.c) 仅影响 TPS branch 1 行, 不影响 multi-driver quat / outputEncoding 路径
- ✅ λ retry 移除仅影响 K 病态时的处理, oracle 单次求解失败 → kFailure 报错, 是诚实行为, 不影响其他功能
- ✅ prev-tracker 移除仅影响 evalInput trigger, 不动 prevSolverMethodVal (lastSolveMethod 缓存仍工作)

---

## §3 — 回退计划 (待 Planner 验收, 等批后 Step 4 实施)

每项独立 commit, 标签 `M_P0_KERNEL_SWITCH_ROLLBACK_<n>`, message 引用老版本 文件:行号.

### Commit ROLLBACK_1 — TPS r≤0 分支恢复 oracle 行为 (3.c)

| 文件 | 改动 | LoC |
|---|---|---|
| `source/RBFtools.cpp:4519-4561` | TPS branch `else result = 0.0;` → `else result = value;` (对齐 oracle `cpp:3801-3808`); 同步删/改注释段 (M_P0_KERNEL_ALGO_AUDIT 解释段保留为 audit history, 加 ROLLBACK 注释) | -30/+10 |
| `modules/RBFtools/tests/test_m_p0_kernel_algo_audit.py` | TPS PSD assertion 由"必须 0.0"改为"接受 value 或 0.0" (允许 oracle 行为) | -5/+10 |

**风险**: M_P0_KERNEL_ALGO_AUDIT 测试 a-b 两 case 会断言 0.0, 必须放宽. 不影响其他守护 (c/d/e/f/g 守 Raw+Angle / 文档块 / 标签).

**风险规避**: 相关测试调整 + 在 commit message 引用 oracle 行为 + 加 `M_P0_KERNEL_SWITCH_ROLLBACK_1` 反向锚.

### Commit ROLLBACK_2 — λ retry loop 移除 (4.a/4.b)

| 文件 | 改动 | LoC |
|---|---|---|
| `source/RBFtools.cpp:1834-2125` | 移除 `for (lambda retry)` 包装 + ceil 逻辑 + retry counter, 恢复 oracle 单次 Cholesky tier 1 / GE tier 2 dispatch | -120/+30 |
| `modules/RBFtools/tests/test_m_p0_auto_adaptive_lambda.py` | retry assertion 全删或改为反向 (`assert NOT in src`) | -50/+30 |
| `modules/RBFtools/tests/test_m_p0_lambda_ceil_tighten.py` | 同, ceil-related assertion 删 | -30/+15 |

**风险**: K 病态时 oracle 单次 Cholesky+GE 都失败 → `MS::kFailure` 弹出"RBF decomposition failed". 用户必须手动调高 λ. 但**老版本就是这行为, 用户接受**. 加 commit message 强调"恢复 oracle 诚实失败模式".

**风险规避**: 测试调整 + 用户实测引导加一行"若 K 病态切回 oracle 行为后会 kFailure, 需手动提 λ".

### Commit ROLLBACK_3 — 5 prev-tracker 移除 (5.a/5.c/5.d)

| 文件 | 改动 | LoC |
|---|---|---|
| `source/RBFtools.h` | 删除 `prevKernelVal/prevDistanceTypeVal/prevRadiusTypeVal/prevRadiusVal/prevRegularizationVal` 5 成员 (保留 `prevSolverMethodVal` + `prevInputEncodingVal` + `prevQuatGroupConfigHash`) | -10 |
| `source/RBFtools.cpp:170-174` ctor | 删除 5 个 prev-tracker 初始化 (`-1` / `-1.0`) | -10 |
| `source/RBFtools.cpp:1222-1226` | 删除 `inputEncodingChangedThisFrame` flag | -5 |
| `source/RBFtools.cpp:1282-1311` | 删除 `trainingAttrChanged` 提升块 (kernel/dist/radius/radiusType/reg → evalInput=true) | -30 |
| `source/RBFtools.cpp:1207-1220` | 恢复 `if (inputEncodingVal != prevInputEncodingVal) { inputEncodingWarningIssued = false; prevInputEncodingVal = inputEncodingVal; }` 直接写, 删 `inputEncodingChangedThisFrame = true;` 一行 | -1 |
| `modules/RBFtools/tests/test_m_p0_training_affecting_attrs.py` | 18 PERMANENT 守护反向 (`assert NOT in src`) 或整文件删除 | -180/+50 |

**风险**: 切 kernel/distanceType/radius/radiusType/regularization 后, evalInput 不再自动 promote. 用户必须按 Apply 才生效. **老版本就是这行为, 用户接受**.

**风险规避**: 配合 7.c 的 frozenset toggle 同 commit (Python 层 fallback) 移除, 行为统一. 在 user-facing tooltip 加注释 "切 kernel 后需 Apply 重训".

### Commit ROLLBACK_4 — Python set_attribute frozenset toggle 移除 (7.c)

| 文件 | 改动 | LoC |
|---|---|---|
| `modules/RBFtools/scripts/RBFtools/controller.py:1455-1505` | 删除 `_TRAINING_AFFECTING_ATTRS = frozenset({...})` + 删除 set_attribute 内 `if attr in self._TRAINING_AFFECTING_ATTRS: cmds.setAttr(.evaluate, 0); cmds.setAttr(.evaluate, 1)` toggle 块 | -25 |
| `modules/RBFtools/tests/test_m_p0_training_attrs_force_retrain.py` | 6 PERMANENT 守护反向 (`assert NOT in src`) 或删除 | -80/+30 |

**风险**: 切 kernel 后 evalInput 不会自动 promote (与 ROLLBACK_3 同). **是预期回退**.

**风险规避**: 配合 ROLLBACK_3 同时 land 即可.

### Commit ROLLBACK_5 — 双 .mll 重 build + 部署

| 文件 | 改动 | LoC |
|---|---|---|
| `modules/RBFtools/plug-ins/win64/2022/RBFtools.mll` | cmake build_check_2022 → 部署 | bin |
| `modules/RBFtools/plug-ins/win64/2025/RBFtools.mll` | cmake build_check → 部署 | bin |

无 Python 改动, 单独 deploy commit (复用既建 chore(deploy) commit pattern).

### Commit ROLLBACK_6 — addendum 落地状态 + 测试守护 + diag 脚本

| 文件 | 改动 | LoC |
|---|---|---|
| `docs/设计文档/RBFtools_v5_multi_quat_implementation.md` (§7) | 加 `M_P0_KERNEL_SWITCH_ROLLBACK` 行 (取代 M_P0_KERNEL_ALGO_AUDIT/AUTO_ADAPTIVE_LAMBDA/TRAINING_AFFECTING_ATTRS/TRAINING_ATTRS_FORCE_RETRAIN/LAMBDA_CEIL_TIGHTEN 的"已修复"声明, 改"已回退") | +30 |
| `modules/RBFtools/tests/unit/test_kernel_rollback_parity.py` (新) | 6 kernel 顺序切换, 训练点 max \|Δ\| < 1e-3 断言; σ/radius 在 kernel 切换后值断言 (对齐 oracle) | +200 |
| `modules/RBFtools/tests/scratch/diag_kernel_rollback.py` (新) | Phase 5 数据等价性诊断脚本 (oracle vs current CSV diff) | +250 |

---

## §4 — 副作用清单 (回退后失去的新功能)

| # | 失去的新功能 | 影响评估 | 备注 |
|---|---|---|---|
| 1 | TPS r≤0 → 0.0 PSD 守护 | 极小: 老版本就 work, 用户实测无问题 | 浮点噪声场景假设的修复, 实证无必要 |
| 2 | 自适应 λ retry loop | 中: K 病态时回到 kFailure 报错 | 老版本就是这行为, 用户接受 |
| 3 | 切 kernel/dist/radius/radiusType/reg 后自动重训 | 大 (UX 倒退): 用户须按 Apply | 老版本就是这行为, 用户接受 |
| 4 | Python set_attribute belt-and-suspenders toggle | 同 3 (附属于同一行为) | 老版本就是这行为 |

**未触及的新功能** (确认 0 回归):
- multi-driver quaternion RBF (cpp:2670-2860)
- B1 QWA Markley + B2 nlerp 输出编码 (cpp:3995+ + 1995-2060)
- poses I/O 文件菜单 (M_P0_POSES_IO + 两次 CTD_FIX)
- apply_poses freeze (M_P0_APPLY_FREEZE_DURING_WRITE)
- disconnect scale restore
- rbfMode UI resync + apply 强制 Generic
- rest-pose tolerance 1e-3
- B24 driverSource 多源 schema + Python wiring
- M_P0_DUPLICATE_POSE_DETECT
- M_P0_BLEND_SHAPE_TYPO_FIX
- 全部 outputEncoding (Quat/ExpMap) inverse transform
- 1377 既有测试 (除 4c379ad/156af4c/2600d3e/a707bac/ee6d63f 直接相关的 ~50 测试外, 全保持)

---

## §5 — Phase 5 数据等价性验证设计 (Step 4 完成后跑)

```
modules/RBFtools/tests/scratch/diag_kernel_rollback.py
```

(略 — 与 Step 1 期间已交付的 `diag_kernel_switch.py` 同结构, 参 §1 报告)

**完成判据**:

$$\max_{k\in\{0..5\},\,i\in\{0..19\},\,j\in\{joints\},\,a\in\{attrs\}}\bigl|\,\text{new}(k,i,j,a)-\text{old}(k,i,j,a)\bigr| < 10^{-3}$$

---

## §6 — 实际 land commit list (方案 E, 4 commits)

| # | sha | 标签 | 文件 | 状态 |
|---|---|---|---|---|
| 1 | `c924b1c` | `M_P0_KERNEL_SWITCH_ROLLBACK_1` | `source/RBFtools.cpp` (TPS r≤0 → value) + `tests/test_m_p0_kernel_algo_audit.py` (test_PERMANENT_a 放宽) | ✅ Planner APPROVED |
| 2 | `91adfc9` | `M_P0_KERNEL_SWITCH_ROLLBACK_2` | `source/RBFtools.cpp` (移除 λ retry loop, 恢复 Cholesky tier 1 / GE tier 2 单次 + honest kFailure) + `tests/test_m_p0_auto_adaptive_lambda.py` (class-level skip) | ✅ Planner APPROVED (含 amend ACK, policy A 已落 §0.5) |
| 3 | `7e6c25f` | `M_P0_KERNEL_SWITCH_ROLLBACK_5` | `modules/RBFtools/plug-ins/win64/{2022,2025}/RBFtools.mll` (双 build 183,296 B / parity 0.000% size diff) | ✅ Planner APPROVED |
| 4 | (本 commit) | `M_P0_KERNEL_SWITCH_ROLLBACK_6` | `docs/排查/M_P0_KERNEL_SWITCH_ROLLBACK_index.md` (本 §6 + §0.5 nit amend 记录) + `docs/设计文档/RBFtools_v5_multi_quat_implementation.md` (§7 ROLLBACK row + §10 引用) + `modules/RBFtools/tests/unit/test_kernel_rollback_parity.py` (新, 6 必备断言) + `modules/RBFtools/tests/scratch/diag_kernel_rollback.py` (从 diag_kernel_switch.py 重命名 + --baseline/--compare CLI) | ⏳ 等 Planner 复审 |

**未做的 ROLLBACK** (方案 E 决议保留):
- ~~ROLLBACK_3~~: 5 prev-tracker (kernel/distanceType/radiusType/radius/regularization) — 用户决议保留 UX 价值
- ~~ROLLBACK_4~~: Python `_TRAINING_AFFECTING_ATTRS` frozenset + `evaluate=0/1` toggle — 同上, UX

**Phase 5 (用户驱动验证)** — 不在 ROLLBACK_6 内:
- 用户在 Maya 跑 `tests/scratch/diag_kernel_rollback.py` 在 oracle (`X:\RBFtools`) + current (deploy 后) 两侧
- diff CSV → max\|Δ\| < 1e-3 over 6 kernel × 20 pose × 10 driven × 9 attr (10800 cell)
- 视觉: 切 6 kernel + 手动 Apply, driven 关节肉眼无 drift
- Phase 5 通过 → 4 commit 一次性 push origin/main + main repo pull + installer 重打

**Push 阻塞**: 按方案 E "等所有 ROLLBACK 完成 + Phase 5 通过后一次性 push", 4 commit 当前**仅本地 land** (worktree HEAD `<未 push>`).
