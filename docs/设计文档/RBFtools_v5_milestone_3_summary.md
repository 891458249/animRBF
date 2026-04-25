# RBFtools v5 — Milestone 3 — Workflow Tools

> **Status**: M3.0 + M3.2 Complete ✅ | M3.1, M3.3-M3.7 Pending
> **Test累计**: 260 / 260
> **Roadmap reference**: 设计方案 PART F Milestone 3
> **Top-level decisions**: addendum §M3 顶层核查（本会话内决议）
> **Detailed addendum**: `RBFtools_v5_addendum_20260424.md` §M3.0 (+ future §M3.x)

本文档是 Milestone 3 的**总入口**：列出 7 个子任务的 commit / 测试累计 / 状态 + 顶层执行顺序理由 + 跨子任务契约（action_id 注册表 / SCHEMA_VERSION / 访问路径）+ M3.x 子任务复用模板。

---

## 1. 子任务进度矩阵

| Sub-task | Purpose | Status | Commit | Tests | Addendum |
|---|---|---|---|---|---|
| **M3.0** | Shared infrastructure (ConfirmDialog / Progress / JSON IO / select_rig) | ✅ | `74ed12c` | 18 | §M3.0 |
| **M3.2** | Mirror Tool (L↔R quat/translate flip + name remap) | ✅ | (this commit) | 31 | §M3.0-spillover + §M3.2 |
| **M3.7** | aliasAttr auto-naming（M3.3 阻塞项）| ⏳ Next | — | — | — |
| **M3.3** | JSON Import/Export（消费 M3.7 + M2.3）| ⏳ | — | — | — |
| **M3.1** | Pose Pruner | ⏳ | — | — | — |
| **M3.6** | Auto neutral samples（CMT 风格）| ⏳ | — | — | — |
| **M3.5** | Pose Profiler + 拆分建议 | ⏳ | — | — | — |
| **M3.4** | Live Edit Mode（algo only；mayapy 集成 → M1.5）| ⏳ | — | — | — |

---

## 2. 执行顺序理由（顶层核查决议）

```
M3.0 (共享基础设施 — 预备)
  ↓
M3.2 (Mirror — 最高频用户工具)
  ↓
M3.7 → M3.3 (关键路径：aliasAttr 锁 JSON schema → JSON IO)
  ↓
M3.1 (Pose Pruner)
  ↓
M3.6 (自动中性样本)
  ↓
M3.5 (Pose Profiler — debug 工具)
  ↓
M3.4 (Live Edit — 复杂度最高 + 优先级最低)
```

**理由汇总**：

- **M3.0 first**：基础设施预备，所有后续子任务复用
- **M3.2 second**：左右对称 rig 是 TD 每日必备工具；缺失时手工复制粘贴每条 pose 极度繁琐
- **M3.7 → M3.3 关键路径**：JSON schema 用 alias 名 vs 数字索引会改变文件格式；M3.3 之前必须 M3.7 完工
- **M3.1 / M3.6 / M3.5** 中频工具按用户感知排序
- **M3.4 末位**：scriptJob 监听复杂 + 大部分用户已习惯非 live 工作流；性价比最差

---

## 3. 跨子任务契约（M3.0 锁定）

### 3.1 — `action_id` 注册表

每个 M3.x 子任务在实现 confirm 流程时**必须**在此表登记：

| action_id | Sub-task | Confirm 触发场景 |
|---|---|---|
| `(reset_confirms)` | M3.0 baseline | 无（reset 菜单本身就是 confirm 复位入口）|
| `prune_poses` | M3.1（待登记）| Pose Pruner 删除批量 poses 前 |
| `mirror_create` | M3.2 ✅ | Mirror 创建新目标节点前 |
| `mirror_overwrite` | M3.2 ✅ | Mirror 目标已存在时覆盖前 |
| `import_solver_overwrite` | M3.3（待登记）| Import 覆盖现有节点前 |
| `live_edit_enable` | M3.4（待登记，可选）| Live Edit Mode 首次启用提示 |

**命名规则**：`snake_case`，全局唯一。Maya optionVar 名是 `RBFtools_skip_confirm_<action_id>`（addendum §M3.0.3 锁定）。

### 3.2 — `SCHEMA_VERSION` 永久不变量

- **当前值**：`"rbftools.v5.m3"`
- **修改禁止**：任何 schema 演化必须**引入新版本字符串** + 多版本 reader（addendum §M3.0.2）
- **三层守护**：
  - Layer 1 — 源码注释（`core_json.py` 模块 docstring + `SCHEMA_VERSION` 行尾注释）
  - Layer 2 — addendum §M3.0.2 Schema Version Immutability Contract
  - Layer 3 — 永久测试 `tests/test_m3_0_infrastructure.py::T0_SchemaVersionImmutability::test_schema_version_unchanged_M3_0`（标注 `# PERMANENT GUARD — DO NOT REMOVE`）

### 3.3 — 访问路径契约（M3.x → M3.0 基础设施）

**路径 A（推荐 + 默认）**：经 `MainController`

```python
# Sub-task widget code:
ctrl = self.controller  # the MainController instance

# Confirm prompt
proceed = ctrl.ask_confirm(
    title=tr("title_xxx"),
    summary=tr("summary_xxx"),
    preview_text=preview_str,
    action_id="xxx",     # snake_case, register in §3.1 above
)
if not proceed:
    return

# Progress feedback
prog = ctrl.progress()
if prog:
    prog.begin(tr("status_xxx_starting"))
    # ... work loop ...
    prog.step(i, total, tr("status_xxx_step"))
    prog.end(tr("status_xxx_done"))
```

**路径 B（不推荐）**：直接 import widget，仅当工具是"独立 utility 而非 sub-task widget"时使用，且必须在子任务 addendum 论证。

### 3.4 — 单子任务规模上限

`≤ 800 行生产代码`（不计测试 / addendum）。超过则拆 a/b。M3.0 实测 ~520 行，M3.x 预算 ~700-800。

---

## 4. M3.x → M3.0 标准复用模板

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
    action_id="prune_poses",   # → RBFtools_skip_confirm_prune_poses
):
    return

# Step 2: progress feedback
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
    # ... payload ...
})
data = core_json.read_json_with_schema_check(path)   # raises SchemaVersionError on mismatch

# Step 4: rig role selection (utility — "show me the driver")
from RBFtools import core
core.select_rig_for_node(self._ctrl.current_node(), "driver")
```

每 M3.x 子任务在自己的 addendum 里记录"使用了哪些 M3.0 helper"以便 review 追溯。

---

## 5. UI 入口矩阵（顶层决议）

| 工具 | 主入口 | 副入口 |
|---|---|---|
| M3.1 Pruner | `Tools → Prune Poses...` | 右键 pose 表 → `Remove this pose` |
| M3.2 Mirror | `Tools → Mirror Node...` | 右键 pose 表 → `Mirror this pose` |
| M3.3 IO | `File → Import...` / `File → Export...` | — |
| M3.4 Live Edit | Tools 面板（新 collapsible）→ Toggle | — |
| M3.5 Profiler | `Tools → Analyze Node` | — |
| M3.6 自动中性样本 | Tools 面板 → "Add Neutral Samples" 按钮 | — |
| M3.7 aliasAttr | （隐式后台，M3.3 内部调用） | — |

**新增 UI 顶层结构（M3.0 已落）**：

```
RBFToolsWindow (QMainWindow)
├── menuBar()                        ← M3.0 ✅
│   ├── File: (M3.3 add Import / Export)
│   ├── Edit: (预留)
│   ├── Tools: Reset confirm dialogs ✅ (M3.0 baseline)
│   │          + (M3.1 add Prune Poses)
│   │          + (M3.2 add Mirror Node)
│   │          + (M3.5 add Analyze Node)
│   └── Help: (预留)
├── NodeSelector (M2.4 之前)
├── Sections (M2.4 之前 + M3 新增)
│   ├── General / VectorAngle / RBFSection / PoseEditor (M2.4)
│   └── ToolsSection (M3.4 / M3.6 add)
└── StatusBar (M2.4 之前 + M3.0 progress controller wrapper) ✅
```

---

## 6. 测试范式

**沿用 M1/M2 纯 mock + 算法层测试范式**（顶层决议 D①）：

- 每个 M3.x 工具的算法层（70%-85% 纯函数化）继续走 mock 测试
- 场景操作部分（`cmds.setAttr` / 节点创建 / scriptJob）推迟到 **M1.5 mayapy headless 集成测试**
- 不引入第三方 testing harness（如 `mayatest`）

**例外**：M3.4 Live Edit Mode 仅 30% 纯函数化，子任务核查时单独决定 algo 部分的 spillover 边界。

---

## 7. Bug-hunt 清单（M2 遗留 + M3 新增）

| # | 来源 | 描述 |
|---|---|---|
| BH-1 | M2.2 | T12 near-degenerate λ ratio：构造 λ₁/λ₂ < 1.1 的 4×4 SPD，验证 `qwaDegenerateWarningIssued` 路径 + identity fallback |

M3 进行中如发现新 bug-hunt 项，append 到此表。

---

## 8. Roadmap 总览（更新到 M3.0）

```
M1 数值正确性 ✅ (76 测试)
M2 输入/输出编码闭环 ✅ (211 测试，主体收官)
  └── M2.5 pose 分字段缓存 (forward-compat 锁定，可任意插入)
M3 工作流工具 ← 进行中
  ├── M3.0 共享基础设施 ✅ (229 测试)
  ├── M3.2 Mirror ← 下一站
  ├── M3.7 aliasAttr
  ├── M3.3 JSON IO
  ├── M3.1 Pose Pruner
  ├── M3.6 自动中性样本
  ├── M3.5 Pose Profiler
  └── M3.4 Live Edit Mode
M4 附加 Solver
M4.5 Eigen + 四层 fallback
M5 性能与引擎对接
M1.5 mayapy headless C++ 集成测试 (环境就位时)
```

---

## 9. Key References

- **设计方案**：[`RBFtools_v5_设计方案.md`](RBFtools_v5_设计方案.md) PART F Milestone 3
- **决议日志**：[`RBFtools_v5_addendum_20260424.md`](RBFtools_v5_addendum_20260424.md) §M3.0（+ future §M3.x）
- **Milestone 2 入口**：[`RBFtools_v5_milestone_2_summary.md`](RBFtools_v5_milestone_2_summary.md)
- **顶层核查报告**：本会话内（commit `74ed12c` 之前的 conversation）

---

**本文档结束**。M3.x 执行者打开此文件即可对齐当前进度 + 已锁定契约 + 复用模式，无需回溯 commit 历史。每个 M3.x 子任务完工后**更新本文档第 1 节进度矩阵 + 第 3.1 节 action_id 注册表**。
