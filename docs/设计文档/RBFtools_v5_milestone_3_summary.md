# RBFtools v5 — Milestone 3 — Workflow Tools (Closure Summary)

> **Status**: **Milestone 3 主体完工** ✅ — 7 sub-tasks + 3 spillover sections shipped
> **Test累计**: **424 / 424**
> **Roadmap reference**: 设计文档 PART F Milestone 3 (B7-B15 全部 ✅)
> **Detailed addendum**: `RBFtools_v5_addendum_20260424.md` §M3.0 / §M3.0-spillover §1/§2/§3 / §M3.1 / §M3.2 / §M3.3 / §M3.4 / §M3.5 / §M3.6 / §M3.7

本文档是 Milestone 3 收官 summary。8 子任务（含 M3.0 共享基础设施）+ 3 个 M3.0-spillover 章节全部 push 完成；**v5 设计文档 PART F Milestone 3 全部交付**。

---

## 1. 子任务进度矩阵

| Sub-task | Purpose | Commit | Tests | Addendum |
|---|---|---|---|---|
| **M3.0** | Shared infrastructure (ConfirmDialog / Progress / JSON IO / select_rig) | `74ed12c` | 18 | §M3.0 |
| **M3.0 doc** | Milestone 3 entry summary + sub-task progress matrix | `112f43f` | (same) | — |
| **M3.2** | Mirror Tool + spillover §1 (`add_tools_action` / `add_pose_row_action`) | `9cd02f2` | 31 | §M3.0-spillover §1 + §M3.2 |
| **M3.7** | aliasAttr auto-naming (M3.3 unblocker) | `c7e07f2` | 31 | §M3.7 |
| **M3.3** | JSON Import/Export + spillover §2 (`add_file_action`) | `67b0b3f` | 39 | §M3.0-spillover §2 + §M3.3 |
| **M3.1** | Pose Pruner | `862950e` | 26 | §M3.1 |
| **M3.6** | Auto neutral sample on fresh node | `f8925a3` | 18 | §M3.6 |
| **M3.5** | Pose Profiler + spillover §3 (`add_tools_panel_widget` / `remove_tools_panel_widget`) | `bf48bed` | 25 | §M3.0-spillover §3 + §M3.5 |
| **M3.4** | Live Edit Mode (algo) — final M3 sub-task | (this commit) | 25 | §M3.4 |

**累计测试**：76 (M1) → 211 (M2) → 229 (M3.0) → 260 (M3.2) → 291 (M3.7) → 330 (M3.3) → 356 (M3.1) → 374 (M3.6) → 399 (M3.5) → **424 (M3.4)**

---

## 2. v5 设计文档 PART F Milestone 3 覆盖矩阵

| 设计文档 PART F.M3.x | 铁律 | 子任务 | 状态 |
|---|---|---|---|
| **M3.1 Pose Pruner** | B8 + B12 | M3.1 | ✅ |
| **M3.2 Mirror Tool** | B13 | M3.2 + spillover §1 | ✅ |
| **M3.3 JSON Import/Export** | B15 | M3.3 + spillover §2 | ✅ |
| **M3.4 Live Edit Mode** | B11 | M3.4（algo；集成推 M1.5）| ✅ |
| **M3.5 Pose Profiler + 拆分建议** | B7 | M3.5 + spillover §3 | ✅ |
| **M3.6 自动中性样本** | E.9 | M3.6 | ✅ |
| **M3.7 aliasAttr 自动命名** | E.2 | M3.7 | ✅ |

铁律 B7 / B8 / B11 / B12 / B13 / B15 + E.2 / E.9 全部交付。

---

## 3. M3.0-spillover 完整 API 索引

§1 / §2 / §3 三章节构成 M3 全程的 UI 扩展接口面，未来 milestone 的所有窗口扩展必须走这套 helper（直接修改 `_build_menu_bar` / `_build_ui` 是红线）。

### §1 — Tools menu + pose-row right-click（M3.2 commit）

```python
RBFToolsWindow.add_tools_action(label_key, callback) -> QAction
_PoseEditorPanel.add_pose_row_action(label_key, callback, danger=False)
```

消费者：M3.2 mirror / M3.3 alias regen / M3.5 profile-to-script-editor / M3.6 neutral / M3.7 force regen / M3.1 prune (Tools menu)；M3.1 row-remove / M3.2 row-mirror（pose-row）。

### §2 — File menu（M3.3 commit）

```python
RBFToolsWindow.add_file_action(label_key, callback) -> QAction
```

消费者：M3.3 import / export-selected / export-all（3 entries）。M3 全程唯一 File 菜单消费者；M5 跨场景 import 工具是后续候选。

### §3 — Per-node Tools panel（M3.5 commit）

```python
RBFToolsWindow.add_tools_panel_widget(widget_id, widget) -> QWidget
RBFToolsWindow.remove_tools_panel_widget(widget_id) -> bool
```

ToolsSection collapsible **懒创建于首次 add**，**一旦创建持久存在**（T_TOOLS_SECTION_PERSISTS PERMANENT）。重复 widget_id 触发 RuntimeError（不静默覆盖）。

消费者：M3.5 ProfileWidget（"profile_report"）/ M3.4 LiveEditWidget（"live_edit_toggle"）。M3.4 验证记录确认 forward-compat 契约成立 —— 第二消费者零 API 修改。

---

## 4. action_id 注册表（完整版）

M3.0 path A `controller.ask_confirm(action_id=...)` 全部消费者。optionVar 命名 `RBFtools_skip_confirm_<action_id>`，"Reset confirm dialogs" 菜单一键复位。

| action_id | Sub-task | 触发场景 |
|---|---|---|
| `mirror_create` | M3.2 | Mirror 创建新目标节点前 |
| `mirror_overwrite` | M3.2 | Mirror 目标已存在覆盖前 |
| `force_regenerate_aliases` | M3.7 | Force Regenerate Aliases（覆盖 user alias）前 |
| `import_replace` | M3.3 | Import Replace 模式至少一节点 will_overwrite=True 前 |
| `prune_poses` | M3.1 | Pose Pruner dry-run 后 execute 前 |
| `add_neutral_with_existing` | M3.6 | 手动 Add Neutral Sample + pose[0] 已有用户 pose |

**6 个 confirm 入口** 覆盖所有 M3 破坏性操作。读取-only 工具（M3.5 Profiler、M3.7 regenerate non-force、M3.6 auto-create-time）**不**走 confirm。

**5 次 path A 真实消费者**（按时间顺序）：M3.2 (1st) → M3.7 (2nd, force) → M3.3 (3rd) → M3.1 (4th) → M3.6 (5th)。M3.5 是 read-only 例外（不消费 path A）。M3.4 同样不消费（toggle 是 cheap 操作）。

---

## 5. Permanent Guards 完整清单（"宪法层" 14 条）

项目"宪法层"——任何 refactor 都受其约束。Source-text scan 守护方式：先剥 docstring + 注释再扫禁用词。

| # | Guard | 子任务 | 守护内容 |
|---|---|---|---|
| 1 | `T0` (test_schema_version_unchanged_M3_0) | M3.0 | `core_json.SCHEMA_VERSION = "rbftools.v5.m3"` |
| 2 | `T_MANAGED_ALIAS_DETECT` | M3.7 | `is_rbftools_managed_alias` 边界（in_/out_/quat sibling）|
| 3 | `T1b` (bijection) | M3.3 | `_ATTR_NAME_TO_JSON_KEY` 双射 |
| 4 | `T_M3_3_SCHEMA_FIELDS` | M3.3 | `EXPECTED_NODE_DICT_KEYS` / `EXPECTED_SETTINGS_KEYS` 冻结 |
| 5 | `T16` (meta read-only) | M3.3 | `dict_to_node` / `dry_run` 体内不读 `meta` |
| 6 | `T_FLOAT_ROUND_TRIP` | M3.3 | `dump(load(dump(d)))` byte-stable |
| 7 | `T_QUAT_GROUP_SHIFT` (7 sub) | M3.1 | `shift_quat_starts` 边界 |
| 8 | `T_ANALYSE_READ_ONLY` | M3.1 | `core_prune.analyse_node` 体内 0 mutation |
| 9 | `T_NEUTRAL_QUAT_W` (3 sub) | M3.6 | quat-leader W=1 强制 |
| 10 | `T_PROFILE_READ_ONLY` | M3.5 | `core_profile.profile_node` 体内 0 mutation |
| 11 | `T_CAVEAT_VISIBLE` (3 sub) | M3.5 | F1 / F2 / `_K_CHOL` caveat 显著 |
| 12 | `T_TOOLS_SECTION_PERSISTS` | M3.5 | `remove_tools_panel_widget` 不销毁 section |
| 13 | `T_LIVE_NO_DRIVEN_LISTEN` | M3.4 | `core_live` 体内 0 命中 driven 关键字 |
| 14 | `T_THROTTLE_TIME_INJECTION` | M3.4 | `core_live` 体内 0 命中 time.time() / monotonic / datetime |

未来 milestone 新增 guard 必须遵循同模式：纯函数可测、source-text scan、明文 PERMANENT 标注。

---

## 6. 项目文化沉淀（M3 期间确立的 4 个方法论）

### 6.1 复用 > 新建

M3.1 / M3.6 / M3.5 / M3.4 **四连续 0 行 core.py 改动**：

| Sub-task | 复用的 core API |
|---|---|
| M3.1 Pruner | `apply_poses` 主路径 + `write_quat_group_starts` |
| M3.6 Neutral | `_write_pose_to_node` / `clear_node_data` / `read_quat_group_starts` |
| M3.5 Profiler | `core_prune.analyse_node` + 既有 read helpers |
| M3.4 Live Edit | `controller.update_pose` thin wrapper |

每个子任务的 core.py 改动量都通过现状核查的 F-checks 提前验证可复用性。新基础设施仅在**真正缺失**时引入（如 M3.7 alias 系统、M3.3 JSON IO、M3.0 共享基础设施）。

### 6.2 Verify-before-design

**5 次连续使用**：

| 子任务 | F-checks 数量 | 关键发现 |
|---|---|---|
| M3.7 commit (retrospective) | — | reverse-then-reapply 取代 git add -p |
| M3.1 | F1-F4 | helper 行为预核查 |
| M3.6 | F0 | 直读 CMT 源码发现"3-pose"是误读 |
| M3.5 | F1-F4 | `lastSolveMethod` 不可读 + 无 benchmark |
| M3.4 | F1-F4 | scriptJob 项目首次 + active row accessor 缺失 |

通用规则：任何子任务涉及"参考第三方实现"或"依赖现有 API 行为"时，**先核查事实**再做设计。每个 F-check 直接驱动决议项的修订或确认（最高价值形态：M3.5 / M3.6）。

### 6.3 Reverse-then-Reapply（commit 拆分模板）

工作树多子任务混杂时（M3.7 commit retrospective，executor commit `c7e07f2`）：

```
1. Save M3.x-only NEW files into a holdout directory
2. Edit-revert M3.x changes from shared files → M3.{x-1}-only state
3. Verify M3.{x-1} test count passes
4. Stage M3.{x-1} files + commit + push
5. Restore holdout files
6. Edit-reapply M3.x changes (operation log = forward patch)
7. Verify M3.x test count passes
8. Stage + commit + push M3.x
```

deterministic（无 git add -p 交互），idempotent，留下干净 per-sub-task commit 边界。详见 addendum §M3.0 appendix。

### 6.4 0 C++ 红线绝对优先

M3 全程**0 行 C++ 改动**。M3.5 验证：`lastSolveMethod` 是诊断字段价值高，但暴露需要 C++ MObject 改动 → 红线绝对优先 → Profile 仅显示 `solver_method` 配置值 + caveat。**开了这个口子整个 M3 系列零 C++ 契约就崩**。

未来 milestone（M4 附加 solver / M4.5 Eigen / M5 性能）允许 C++ 改动，但 M3 的红线锁定证明了 Python-only 路径能交付完整工作流工具。

---

## 7. 测试矩阵（424 条全分类）

| Milestone | 测试文件 | 子测试数 | 关键守护 |
|---|---|---|---|
| M1.1 | `test_m1_1_distance.py` | 14 | twist wrap、quat 距离规约 |
| M1.2 | `test_m1_2_baseline.py` | 18 | scale 通道保护、dirty tracker |
| M1.3 | `test_m1_3_clamp.py` | 21 | bounds + inflation + Matrix twist 跳过 |
| M1.4 | `test_m1_4_solver.py` | 23 | Cholesky、绝对 λ、SPD 退化 |
| M2.1a | `test_m2_1a_encoding.py` | 26 | Raw/Quat/ExpMap、Bug 2、安全网 |
| M2.1b | `test_m2_1b_encoding.py` | 28 | BendRoll、SwingTwist、Swing-Twist 分解 |
| M2.2 | `test_m2_2_qwa.py` | 23 | 交换律、Power Iteration、PSD guard |
| M2.3 | `test_m2_3_local_transform.py` | 15 | t/q/s 分解、shear 处理 |
| M2.4a | `test_m2_4a_*.py` | 19 | transactional multi-attr、widget API、i18n key |
| M2.4b | `test_m2_4b_widgets.py` | 23 | 基类 API、signal 契约、set_values 零 emit |
| M3.0 | `test_m3_0_infrastructure.py` | 18 | T0 schema_version + path A |
| M3.0-spillover | `test_m3_0_spillover.py` | 3 | spillover §1 守护 |
| M3.2 | `test_m3_2_mirror.py` | 28 | mirror 数学 + naming + T_ROLLBACK |
| M3.7 | `test_m3_7_alias.py` | 31 | T_MANAGED_ALIAS_DETECT + alias 命名 |
| M3.3 | `test_m3_3_jsonio.py` | 39 | T1b + T_M3_3_SCHEMA_FIELDS + T16 + T_FLOAT_ROUND_TRIP |
| M3.1 | `test_m3_1_prune.py` | 26 | T_QUAT_GROUP_SHIFT + T_ANALYSE_READ_ONLY |
| M3.6 | `test_m3_6_neutral.py` | 18 | T_NEUTRAL_QUAT_W |
| M3.5 | `test_m3_5_profile.py` | 25 | T_PROFILE_READ_ONLY + T_CAVEAT_VISIBLE + T_TOOLS_SECTION_PERSISTS |
| M3.4 | `test_m3_4_live_edit.py` | 25 | T_LIVE_NO_DRIVEN_LISTEN + T_THROTTLE_TIME_INJECTION |
| 永久守护 | `test_i18n_no_hardcoded_strings.py` | 1 | 0 容忍硬编码 |

**总计：424 / 424**（M3 单 milestone 内贡献 213 条 = 18+3+28+31+39+26+18+25+25）。

---

## 8. 后续 Milestone 路径（roadmap 推进决策）

Milestone 3 主体收官，roadmap 进入下一阶段决策。候选下一站：

| Milestone | 优先级 | 描述 |
|---|---|---|
| **M1.5** | 中 | mayapy headless C++ 集成测试（环境就位时一次性覆盖 M1.1–M2.3 的 C++ 路径 + M3.4 scriptJob 真实触发回归）|
| **M4** | 中 | 附加 solver（Jiggle / Aim Constraint / `solverType` 分支） |
| **M4.5** | 中 | Eigen + 完整四层 fallback chain（独立 milestone）|
| **M2.5** | 低 | pose 分字段缓存（性能优化，与 M4/M5 并行）|
| **M5** | 低 | 性能与引擎对接（BRMatrix 对称存储 + SIMD / `solverStats` / 每目标 sigma / UE5 runtime / 245 补助骨 benchmark）|

**M1.5 的 M3.4 spillover** 已在 addendum §M3.4.7 锁定 scope —— `core_live.py` pure-function API 是 M1.5 的 forward-compat 接口，不会变更。

---

## 9. Roadmap 总览

```
M1 数值正确性 ✅ (76 测试)
M2 输入/输出编码闭环 ✅ (211 测试)
M3 工作流工具 ✅ (424 测试)  ← 本节
  ├── M3.0 共享基础设施 ✅
  ├── M3.0-spillover §1 ✅ (M3.2 commit, Tools menu + pose-row)
  ├── M3.0-spillover §2 ✅ (M3.3 commit, File menu)
  ├── M3.0-spillover §3 ✅ (M3.5 commit, ToolsSection panel)
  ├── M3.2 Mirror ✅
  ├── M3.7 aliasAttr ✅ (M3.3 unblocker)
  ├── M3.3 JSON IO ✅
  ├── M3.1 Pose Pruner ✅
  ├── M3.6 Auto neutral sample ✅
  ├── M3.5 Pose Profiler ✅
  └── M3.4 Live Edit Mode ✅ (algo; M1.5 spillover for integration)

M1.5 mayapy headless C++ 集成测试 (pending)
  + M3.4 scriptJob 真实触发回归

M4 附加 Solver (pending)
M4.5 Eigen + 四层 fallback (pending)
M2.5 pose 分字段缓存 (pending, low priority)
M5 性能与引擎对接 (pending)
```

---

## 10. Key References

- **设计方案**：[`RBFtools_v5_设计方案.md`](RBFtools_v5_设计方案.md) PART F Milestone 3
- **决议日志**：[`RBFtools_v5_addendum_20260424.md`](RBFtools_v5_addendum_20260424.md) §M3.0 / §M3.0-spillover §1/§2/§3 / §M3.1 / §M3.2 / §M3.3 / §M3.4 / §M3.5 / §M3.6 / §M3.7
- **Milestone 1 / 2 入口**：[`RBFtools_v5_milestone_2_summary.md`](RBFtools_v5_milestone_2_summary.md)

---

**本文档结束**。Milestone 3 的 7 个子任务（含 M3.0 基础设施）+ 3 个 spillover 章节 + 14 条 PERMANENT GUARD + 4 个项目文化沉淀方法论构成了 v5 工作流工具的完整交付。

后续 milestone 的执行者请把本文档作为 M3 全部成果的入口；最重要的是吸收**复用 > 新建**、**verify-before-design**、**reverse-then-reapply**、**0 C++ 红线绝对优先**这 4 个在 M3 期间确立的方法论 —— 它们将驱动 M1.5 / M4 / M4.5 / M5 的稳健交付。
