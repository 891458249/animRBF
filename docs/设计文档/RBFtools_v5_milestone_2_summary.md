# Milestone 2 — Deliverables Summary

> **状态**：主体收官 ✅（M2.5 性能补丁性质，可任意时刻插入）
> **基线**：v5 设计方案 v1.0 + addendum 2026-04-24
> **测试覆盖**：211 / 211（截至 M2.4b）
> **C++ 集成测试**：推迟到 M1.5（mayapy headless 环境就位时一次性补齐）

本文档是 Milestone 2 的**总入口**：列出 7 个子任务的 commit / 测试累计 / addendum 章节索引 + 关键交付摘要 + M2.5 forward-compat 契约 + M3 / M4 / M5 后续路径。

---

## 1. 子任务索引

| 子任务 | Commit | 测试累计 | 主交付 | Addendum |
|---|---|---|---|---|
| **M2.1a** | [`6368bb7`](#) | 105 | inputEncoding 框架 + Raw/Quat/ExpMap 三档 + Bug 2 修复（Matrix+Angle 静默退化 → encoding-aware dispatch） | [§M2.1a](RBFtools_v5_addendum_20260424.md#m21a) |
| **M2.1b** | [`89197b4`](#) | 130 | BendRoll + SwingTwist 两档实现；Swing-Twist 分解 helper + ε=1e-4 立体投影 | [§M2.1b](RBFtools_v5_addendum_20260424.md#m21b) |
| **M2.2** | [`39f8225`](#) | 153 | QWA 输出编码（Power Iteration dual-seed + PSD guard + 交换律证明 + isQuatMember 单源掩码） | [§M2.2](RBFtools_v5_addendum_20260424.md#m22) |
| **M2.3** | [`9f3e11f`](#) | 168 | local Transform 双存储（per-pose t/q/s 10-tuple，single-sever/single-restore 生命周期，non-driven-channel freeze 契约） | [§M2.3](RBFtools_v5_addendum_20260424.md#m23) |
| **M2.4a** | [`f326447`](#) | 188 | UI scalar/enum/bool 控件（M1.3 + M1.4 + M2.1a + M1.2 outputIsScale）+ i18n 永久守护扫描器 + transactional set_node_multi_attr | [§M2.4a](RBFtools_v5_addendum_20260424.md#m24a) |
| **M2.4b** | [`1bd2afc`](#) | **211** | OrderedIntListEditor + OrderedEnumListEditor + 公共基类（销毁重建 + suspend-emit guard + setSizeHint 4 路径覆盖） | [§M2.4b](RBFtools_v5_addendum_20260424.md#m24b) |
| **M2.5** | (排队) | (forward-compat) | pose 分字段缓存（`poseSwingQuat` / `poseTwistAngle` / `poseSwingWeight` / `poseTwistWeight` / `poseSigma`），性能优化性质 | (待立) |

---

## 2. v5 设计文档 PART 覆盖映射

| v5 PART | 子任务覆盖 |
|---|---|
| **C.2.2** — 输入编码枚举（5 档） | M2.1a (Raw / Quaternion / ExpMap) + M2.1b (BendRoll / SwingTwist) |
| **C.2.7** — Pose 存储 swing-twist 分字段 | M2.5（推迟，forward-compat 契约已锁定） |
| **D.4** — QWA 四元数输出 | M2.2 |
| **D.5** — local Transform 双存储 | M2.3 |
| **F.M2.4** — UI Encoding 下拉框 | M2.4a (scalar / enum) + M2.4b (multi list editors) |
| **G.2 / G.3 / G.4 / G.5 / G.6** — 数学公式 | M2.1a/b（编码 encode 函数）+ M2.2（QWA 协方差 + 交换律证明） |
| **铁律 B3** — 严格 MVC 解耦 | M2.4a/b 全程守护，i18n 永久扫描器永久强制 |
| **铁律 B10** — local Transform 引擎一致性 | M2.3 |

---

## 3. 关键架构决策（按 milestone 锁定）

### M2.1a/b — 输入编码

- **节点级单一 `inputEncoding`**（per-source encoding 推迟到 M3+）
- **硬约定**：`inputEncoding != Raw` 时 driver attrs 必须 `(rx, ry, rz)` 三元组
- **`driverInputRotateOrder[]`** 复用 Maya 原生 rotateOrder enum (xyz=0…zyx=5)
- **安全网**：inDim 非 3 倍数 / placeholder 编码 → fall-back to Raw + 一次性 warning，**永不** kFailure
- **Bug 2 修复**：Matrix 模式删除 `distanceTypeVal = 0` 强制；新增 `getMatrixModeAngleDistance` helper

### M2.2 — QWA 输出

- **Path (b) 直接 QWA**（交换律证明 path (a) ≡ (b) 对常数 q_base）
- **Power Iteration dual-seed**（identity 主 + `M·(1,1,1,1)` 副）
- **PSD guard**：负权重 `max(0, φ)` 截断，仅 QWA 路径，标量 M1.2 路径完全不动
- **isQuatMember[] 单一来源**：`compute()` 构建一次，4 个使用点只读消费（M1.2 yCols / M1.4 solve / M1.2 add-back / QWA 累加）
- **退化 fallback**：identity quat + 一次性 warning（zero-mass / non-converge / config invalid）

### M2.3 — local Transform 双存储

- **schema**：`poses[p].poseLocalTransform.{poseLocalTranslate, poseLocalQuat, poseLocalScale}` (3+4+3 = 10-dim)
- **decompose path**：`MTransformationMatrix.rotation(asQuaternion=True)` → rotateOrder-independent
- **Single-sever / single-restore**：incoming 连接在 replay 循环之前**一次**断开、之后**一次**恢复；禁止循环内断连重连
- **Non-driven-channel freeze 契约**：未在 `driven_attrs` 中的通道在 replay 时保持 Apply 时刻场景值，写入 addendum + 用户教育
- **compute() 零消费** `poseLocalTransform`：纯数据通道，仅 M3 JSON Export 消费

### M2.4a/b — UI 视图层

- **零 C++ 改动**（schema 已冻结，M2.4 只暴露已有 attr）
- **MVC 严守**：widget 不 import core，conftest mock 守护
- **i18n 100% tr()**：`test_i18n_no_hardcoded_strings.py` 永久扫描，KNOWN_VIOLATIONS 白名单维护合法例外
- **`set_node_multi_attr` 事务性**：undo_chunk + clear-then-write，禁止 partial recovery
- **set_values 零 emit 契约**：避免 controller round-trip 死循环
- **PySide mock 陷阱**：conftest 用最小真实类 shim 替代纯 MagicMock 解决 metaclass 陷阱
- **PySide setItemWidget 行高陷阱**：必须显式 `item.setSizeHint(widget.sizeHint())`

---

## 4. 测试矩阵（211 条全分类）

| Milestone | 测试文件 | 子测试数 | 关键守护 |
|---|---|---|---|
| M1.1 | `test_m1_1_distance.py` | 14 | twist wrap、quat 距离规约 |
| M1.2 | `test_m1_2_baseline.py` | 18 | scale 通道保护、dirty tracker |
| M1.3 | `test_m1_3_clamp.py` | 21 | bounds + inflation + Matrix twist 跳过 |
| M1.4 | `test_m1_4_solver.py` | 23 | Cholesky、绝对 λ、SPD 退化 |
| M2.1a | `test_m2_1a_encoding.py` | 26 | Raw/Quat/ExpMap、Bug 2、安全网 |
| M2.1b | `test_m2_1b_encoding.py` | 28 | BendRoll、SwingTwist、Swing-Twist 分解 |
| M2.2 | `test_m2_2_qwa.py` | 23 | 交换律、Power Iteration、PSD guard |
| M2.3 | `test_m2_3_local_transform.py` | 15 | t/q/s 分解、单 sever/restore、shear 处理 |
| M2.4a | `test_m2_4a_core.py` + `test_m2_4a_widgets.py` | 19 | transactional multi-attr、widget API、i18n key |
| M2.4b | `test_m2_4b_widgets.py` | 23 | 基类 API、signal 契约、set_values 零 emit |
| 永久守护 | `test_i18n_no_hardcoded_strings.py` | 1 | 0 容忍硬编码字符串 |

**总计**：211 / 211（11 测试文件，零 C++ 集成测试，纯 Python spec + 结构性 mock）

---

## 5. M2.5 forward-compat 契约（**锁定**）

详见 [§M2.4b 末尾](RBFtools_v5_addendum_20260424.md#m24b)，要点：

- **M2.5 scope**：v5 PART C.2.7 分字段 pose 存储（`poseSwingQuat` / `poseTwistAngle` / `poseSwingWeight` / `poseTwistWeight` / `poseSigma`）
- **M2.4 UI 不消费 pose 内部存储** —— UI 通过 controller `set_attribute` 写入，不 introspect storage layout
- **M2.5 schema 变更不影响 M2.4 任何 widget 的行为或测试** —— M2.4 的 211 条测试在 M2.5 完工后必须依然全绿
- **M2.5 与 M3（工作流工具）可并行** —— M3 优先级高于 M2.5
- **M2.5 可任意时刻插入** —— 不阻塞 M3 启动

---

## 6. Bug-hunt 待办（不阻塞主流程）

| # | 来源 | 描述 |
|---|---|---|
| BH-1 | M2.2 | T12 near-degenerate λ ratio：构造 $\lambda_1/\lambda_2 < 1.1$ 的 4×4 SPD，验证 `qwaDegenerateWarningIssued` 路径 + identity fallback |

---

## 7. 后续 Milestone 路径

| Milestone | 优先级 | 描述 |
|---|---|---|
| **M3** | **高（推荐下一站）** | 工作流工具：Pose Pruner / Mirror / JSON Import-Export / Live Edit Mode / Pose Profiler / 自动中性样本 / aliasAttr |
| **M2.5** | 低 | pose 分字段缓存（性能优化，与 M3 并行）|
| **M1.5** | 中 | mayapy headless C++ 集成测试（环境就位时一次性覆盖 M1.1–M2.3 的 C++ 路径）|
| **M4** | 中 | 附加 solver（Jiggle / Aim Constraint / `solverType` 分支） |
| **M4.5** | 中 | Eigen + 完整四层 fallback chain（独立 milestone）|
| **M5** | 低 | 性能与引擎对接（BRMatrix 对称存储 + SIMD / `solverStats` / 每目标 sigma / UE5 runtime / 245 补助骨 benchmark） |

### M3 子任务建议拆分

| 子任务 | scope | 估算复杂度 |
|---|---|---|
| **M3.1** | Pose Pruner（删重复 / 同值 / 未连接）| 中 |
| **M3.2** | Mirror Tool（L/R 对称命名规则 + axis flip） | 中 |
| **M3.3** | JSON Import/Export（消费 M2.3 的 poseLocalTransform）| 高 |
| **M3.4** | Live Edit Mode（视口实时回写 pose） | 中 |
| **M3.5** | Pose Profiler + 拆分建议 | 低 |
| **M3.6** | 自动中性样本（CMT 风格 rest+swing+twist 三个） | 低 |
| **M3.7** | aliasAttr 自动命名（用于 JSON export） | 低 |

每子任务独立 commit，~200-400 行规模。M3 整体可在 6-8 个 commit 内完工。

---

## 8. Roadmap 总览图

```
M1 数值正确性 ✅
  ├── M1.1 twist wrap
  ├── M1.2 baseline + isScale
  ├── M1.3 driver clamp
  ├── M1.4 Cholesky + λI
  └── M1.5 mayapy C++ 集成测试 (推迟)

M2 输入/输出编码闭环 ✅ (主体)
  ├── M2.1a Raw/Quat/ExpMap + Bug 2
  ├── M2.1b BendRoll + SwingTwist
  ├── M2.2 QWA 输出
  ├── M2.3 local Transform 双存储
  ├── M2.4a UI scalar/enum 控件
  ├── M2.4b UI multi list editors
  └── M2.5 pose 分字段缓存 (forward-compat 锁定，可任意插入)

M3 工作流工具 ← 下一站
  ├── M3.1 Pose Pruner
  ├── M3.2 Mirror Tool
  ├── M3.3 JSON Import/Export
  ├── M3.4 Live Edit Mode
  ├── M3.5 Pose Profiler
  ├── M3.6 自动中性样本
  └── M3.7 aliasAttr

M4 附加 Solver
M4.5 Eigen + 四层 fallback
M5 性能与引擎对接
```

---

**本文档结束**。Milestone 2 主体完工是 v5 roadmap 上**最大单一里程碑**的达成节点；后续 milestone 的执行者请以本文档为入口快速对齐 Milestone 2 的交付边界与契约。
