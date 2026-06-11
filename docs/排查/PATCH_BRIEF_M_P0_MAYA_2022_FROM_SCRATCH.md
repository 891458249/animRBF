# Patch Brief — M_P0_MAYA_2022_FROM_SCRATCH (Phase 11)

> Planner / Architect 设计稿 v11. 执行者照此实施.
>
> **Origin**: 2026-05-12 用户拍板**根本性策略转向** — 把 Maya 2022 当作**全新插件项目**, 从 Maya 2025 source 一比一推导. 不再 audit / 修补现有 scripts_2022.
> **User directive (原话)**:
> > 1. 全网查询 maya2022.5.1 (py2/py3) 与 maya2025.3 的代码差异
> > 2. 分析插件 2025 版本的所有代码
> > 3. 根据 2025 的所有代码完美编写一个 2022 的一比一复刻版
> > 4. 不要再去对比 2022 的源代码, 就当作当前插件只有 2025 版本, 然后需要为 maya2022.3 也写一个一模一样的插件来制定计划和方案
> **Status**: APPROVED — 等执行者实施.

---

## 0. Phase 11 与历史 Phase 的关系

| Phase | 状态 | 关系 |
|---|---|---|
| Phase 1-7 (sync script 派生) | SUPERSEDED | 现有 scripts_2022 由 sync 派生, audit 显示与 scripts/ 等价但用户实测仍 fail. 信任度归零. |
| Phase 8 (诊断) | SUPERSEDED | 假设"用户没装新 installer", 用户拒绝该 hypothesis |
| Phase 9 (audit pass) | 历史参考 | Phase 9 audit 显示 0 drift — 但 Phase 11 把这当作"现有 scripts_2022 不可信"前提下重做 |
| Phase 10 (deep dive) | SUPERSEDED | 双轨 verification 思路被用户否决 |
| **Phase 11 (本 brief)** | **CURRENT** | **从 0 写 Maya 2022 版**, 不再依赖现有 scripts_2022 任何字节 |

**关键变化**: Phase 1-10 把 scripts_2022 视为"sync 派生 + 修补". Phase 11 把它视为"**独立 codebase, 从 Maya 2025 source 重新设计**".

---

## 1. Maya 2022.5.1 vs Maya 2025.3 完整兼容性蓝图 (Planner web research 结果)

### 1.1 Python 版本

| 项 | Maya 2022.5.1 | Maya 2025.3 |
|---|---|---|
| 默认 Python | **3.7** | **3.11** |
| 备用 | mayapy2 (py2.7) on Win/Linux 通过 flag | **无** py2 模式 |
| 关键 stdlib 行为 | dict 插入顺序 (3.7+), `/` 浮点, `str` 是 unicode | 同 + 更稳定的 dict 保证 |

**关键启示**: Maya 2022 默认 py3, **不应**假设 py2. 但用户可能切 mayapy2, 需双轨兼容.

### 1.2 PySide / Qt 版本

| 项 | Maya 2022.5.1 | Maya 2025.3 |
|---|---|---|
| Qt | **5.15.2** | **6.5.3** |
| PySide | **PySide2** | **PySide6** |
| binding | **shiboken2** | **shiboken6** |

#### ⚠️ PySide6 → PySide2 关键 breaks (Maya 2022 复刻必读)

1. **Import path**: `from PySide2.QtCore import ...` ≠ `from PySide6.QtCore import ...`
2. **Class 位置移动**:
   - `QAction` / `QActionGroup` / `QShortcut` / `QFileSystemModel` — Qt6 在 `QtGui`, Qt5 在 **`QtWidgets`** ⚠️
3. **Enum 行为**: Qt6 是 true Python enums (不能 inherit, 需显式 value); Qt5 旧 enum (可隐式 int)
4. **Regex**: Qt6 `QRegularExpression`; Qt5 `QtRegEx` (Qt6 已删 `QtRegEx`)
5. **High DPI**: Qt6 永远 on; Qt5 需显式 `Qt.AA_EnableHighDpiScaling`
6. **Platform**: Qt6 `QNativeInterface`; Qt5 `Qt<platform>Extras` (Qt6 已删)
7. **Maya 内嵌**: `mayaSharedGLWidget` (2022) → `mayaSharedQOpenGLContext` (2025)

### 1.3 C++ SDK / 编译

| 项 | Maya 2022 | Maya 2025 |
|---|---|---|
| MSVC | VS 2017 / VS 2019 | **VS 2022 (17.8.3+)** |
| CMake | older | **3.27.3+** |
| C++ standard | C++11/14 | C++17 |
| .mll 跨版本 | ⚠️ **不二进制兼容** — 必须各自重新编译 |

### 1.4 cmds (Python API 1.0) 差异

无官方完整 deprecation list. 经验:
- `cmds.ls`, `cmds.getAttr`, `cmds.setAttr`, `cmds.connectAttr`, `cmds.disconnectAttr` 等核心 API **跨版本稳定**
- Alembic HDF5 variants 在 2022 删除

### 1.5 .mod 模块系统

✓ **MAYAVERSION + PLATFORM 路由在两版都支持** (Phase 9 验证) — scripts_2022/ 路由方案不变.

### 1.6 RBFtools scripts/ inventory (Planner audit, "as if 2025 only")

把 scripts/ 当唯一 source, audit 结果:
- 48 个 .py, 全部 `from __future__ import absolute_import` (历史 py2-aware)
- **f-string / walrus / async / nonlocal / dataclass / pathlib / type annotation runtime**: **0 hit**
- `super(Cls, self).__init__()`: 6 hit (已 py2-compat)
- `__slots__` hand-rolled: 7 class (代替 dataclass)
- `isinstance(x, str)`: **3 hit** (core.py:64, core.py:1956, core_json.py:610)
- 非 ASCII 字符串: 主要在 ui/help_texts.py (em-dash / star / Chinese / Greek phi 等)
- `ui/compat.py` 已抽象 PySide6/2 import — try PySide6, fall back PySide2
- 第三方依赖: **0** pip 包, 全 stdlib + Maya cmds + PySide2/6
- 文件编码 declaration: 48/48 文件齐全

---

## 2. Maya 2022 复刻规则集 (从 0 设计)

把 scripts/ 当唯一 source, 推导 scripts_2022 需要的完整 transformation. 不参考现有 scripts_2022 任何字节.

### Rule 1 — 文件编码 declaration

每个 .py 文件 line 1: `# -*- coding: utf-8 -*-` (即使内容 ASCII, 防御).

scripts/ 已 100% 满足 → scripts_2022 复制即 OK.

### Rule 2 — String literal: 非 ASCII → ASCII-safe

**所有** string literal 内非 ASCII 字符必须转换:

| Pattern | 处理 |
|---|---|
| `"em dash —"` (无 u 前缀, 非 ASCII) | → `u"em dash —"` (加 u 前缀 + \u escape) |
| `u"em dash —"` (u 前缀) | → `u"em dash —"` (替换非 ASCII) |
| `"\xcf\x86"` (utf-8 byte escape) | → `u"φ"` (合并到 \u codepoint) |
| Triple-quoted docstring `"""含非 ASCII"""` | → 同 string literal 规则 |

**目标**: scripts_2022 全部 .py `bytes.decode('ascii')` 成功.

### Rule 3 — Comment / docstring 非 ASCII: 保留 (受 R1 保护) 或 transliterate

由于 R1 declaration 已加, comment 内的非 ASCII 在 py2/py3 都能正确 parse. 但**防御性**做法: 把 comment 内非 ASCII transliterate 为 ASCII 等价:

| Char | ASCII 替代 |
|---|---|
| `—` em dash | `--` |
| `·` middle dot | `*` |
| `★` star | `*` |
| `≈ ≤ ≥ ×` | `~=, <=, >=, x` |
| `°` | ` deg` |
| `φ θ π λ Δ ∞` 等希腊/数学 | `phi theta pi lambda Delta inf` |
| Chinese (i18n keys 内): | 保留 — 这些是用户可见字符串, 必须保中文 |

### Rule 4 — isinstance(x, str) → isinstance(x, _STR_TYPES)

scripts/ 内 3 hit:
- [core.py:64](modules/RBFtools/scripts/RBFtools/core.py) DriverSource
- [core.py:1956](modules/RBFtools/scripts/RBFtools/core.py) DrivenSource
- [core_json.py:610](modules/RBFtools/scripts/RBFtools/core_json.py) name validation

scripts_2022 同位置改为:

```python
if not isinstance(node, _STR_TYPES):
    raise TypeError("DriverSource.node must be a str, got {!r}".format(
        type(node).__name__))
```

同时各文件顶部 (在 import 之后) 注入:

```python
try:
    _STR_TYPES = (str, unicode)  # noqa: F821 — py2 only
except NameError:
    _STR_TYPES = (str,)  # py3
```

### Rule 5 — PySide2 hard pin (ui/compat.py)

**关键 Maya 2022 specific 修复** (Phase 11 新增):

[scripts/RBFtools/ui/compat.py](modules/RBFtools/scripts/RBFtools/ui/compat.py) 当前 try PySide6 first, fall back PySide2. 对 Maya 2022 单一版本, 应**直接 hardcode PySide2** (避免 PySide6 try 失败 + 异常累积). 同时:

```python
# scripts_2022 版 ui/compat.py:
from PySide2 import QtCore, QtGui, QtWidgets
from PySide2.QtCore import Signal, Slot, Property
from shiboken2 import wrapInstance

# Qt5 specific — QAction, QActionGroup, QShortcut, QFileSystemModel
# 在 QtWidgets (Qt5), NOT QtGui (Qt6).
# 故 scripts/ 中的 `from QtGui import QAction` 在 scripts_2022 应为
# `from QtWidgets import QAction`. 但因为 scripts/ 自己也走 QtWidgets
# 路径 (PySide2 fallback), 此规则一般 no-op.
```

**Sub-Rule 5a**: 全代码 grep `QAction|QActionGroup|QShortcut|QFileSystemModel` import 来源. 若 scripts/ 有 `from PySide6.QtGui import QAction` 这类 Qt6-only 语法, scripts_2022 必须改 `from PySide2.QtWidgets import QAction`.

**Sub-Rule 5b**: enum 用法 audit. 若 scripts/ 用 Qt6 style `Qt.AlignmentFlag.AlignCenter`, scripts_2022 改 `Qt.AlignCenter` (Qt5).

**Sub-Rule 5c**: `QRegularExpression` 在 Qt5 通过 `QtCore.QRegularExpression`, 在 Qt6 同 — 两版都用. 若 scripts/ 用 `QtCore.QRegExp` (Qt5 老 API), scripts_2022 保留即可.

### Rule 6 — Triple-quoted docstring u-prefix

py3 string literal 默认 unicode, u 前缀无意义 (no-op). py2 三引号 string 含非 ASCII 时需 u 前缀.

scripts/ 内若 module / class / function docstring 含非 ASCII (e.g. em-dash), scripts_2022 加 u 前缀:

```python
# scripts:
"""Help text dictionary for all UI controls — English and Chinese."""

# scripts_2022:
u"""Help text dictionary for all UI controls -- English and Chinese."""
# 或保留 em-dash 但加 u 前缀:
u"""Help text dictionary for all UI controls — English and Chinese."""
```

### Rule 7 — Defensive try/except 在 help_button.py

对未来 import 失败有防御 (belt-and-suspenders):

```python
# scripts_2022/ui/widgets/help_button.py:
try:
    from RBFtools.ui.help_texts import get_help_text as _get_help_text
except Exception as _exc:
    import warnings as _w
    _w.warn("RBFtools help_texts import failed: {}".format(_exc))
    def _get_help_text(key):
        return "[Help unavailable - see Script Editor warning]"
```

### Rule 8 — 不动 (验证)

以下**不需 transformation**:
- `from __future__ import absolute_import` — scripts/ 已有
- `super(Cls, self).__init__()` — scripts/ 已 py2-compat
- `__slots__` hand-rolled class — scripts/ 已是
- 字符串 `.format()` (非 f-string) — scripts/ 已是
- 文件 I/O `open(path, "r", encoding="utf-8")` — scripts/ 已是
- `json.load` 用 explicit encoding — scripts/ 已是

### Rule 9 — Maya 2022 specific cmds API smoke test

scripts/ 用 27 个 cmds. Phase 11 必须**在 Maya 2022 实测** (用户机器或 mayapy2 batch) 跑 import + 基本调用 smoke, 验证:
- `cmds.pluginInfo`, `cmds.loadPlugin` 行为
- `cmds.ls(selection=True, type="transform")` 返回类型 (str / unicode in mayapy2)
- `cmds.setAttr(plug, 1.0)` 在 nodeState=1 后的行为 (M_P0_DISCONNECT_SCALE_RESTORE 路径)
- `cmds.removeMultiInstance` 在 multi attr 上的行为

### Rule 10 — C++ .mll: Maya 2022 SDK 单独编译

[Phase 9 Task B 已验证](AUDIT_PHASE9_RESULTS.md) 双 .mll 是 dual-SDK clean isolation:
- `modules/RBFtools/plug-ins/win64/2022/RBFtools.mll` 用 Maya 2022 SDK + MSVC 2017/2019
- `modules/RBFtools/plug-ins/win64/2025/RBFtools.mll` 用 Maya 2025 SDK + MSVC 2022
- 同 `source/RBFtools.cpp`, 不同 SDK header

**关键**: 包含全部 fix:
- M_P0_RBF_POLYNOMIAL_AUGMENTATION (489fb34)
- M_P0_RBF_COLUMN_RANK_DEFENSE (d6f5c9b)
- M_P0_DISCONNECT_SCALE_RESTORE (2026-05-10, in C++ source)

Phase 11 **重新 verify 双 build**:

```bash
strings modules/RBFtools/plug-ins/win64/2022/RBFtools.mll | grep -E "M_P0_RBF_COLUMN_RANK|M_P0_DISCONNECT_SCALE" | sort -u
strings modules/RBFtools/plug-ins/win64/2025/RBFtools.mll | grep -E "M_P0_RBF_COLUMN_RANK|M_P0_DISCONNECT_SCALE" | sort -u
diff <(...) <(...)
# 期望: 两版都含 M_P0_RBF_COLUMN_RANK_DEFENSE + M_P0_DISCONNECT_SCALE_RESTORE 字符串, diff = 0
```

若任一 .mll 缺 M_P0_DISCONNECT_SCALE_RESTORE 字符串 (注: source/RBFtools.cpp 是否含这个 patch?), 需要 `cmake clean rebuild` 双 .mll.

---

## 3. 实施计划 (6 个 Phase, 11 个 commit)

### Phase 11A — 完全删除现有 scripts_2022/, 从 scratch 重建

```bash
# 1. Backup audit (Policy A: 不删 git history)
git mv modules/RBFtools/scripts_2022 modules/RBFtools/scripts_2022_DEPRECATED_phase11
git commit -m "chore(maya2022): archive obsolete scripts_2022 (M_P0_MAYA_2022_FROM_SCRATCH Phase 11A)"

# 2. (后续 Phase 11B 重建 scripts_2022)
```

⚠️ 注: `git mv` 保留 history. 不用 `git rm -rf` (Policy A).

### Phase 11B — 改写 `tools/sync_2022_from_2025.py` (从 R1-R10 重新设计)

重新写 sync script, 应用 §2 R1-R10 完整规则集. 与 Phase 7 版**不兼容** — 是新 implementation.

```bash
python tools/sync_2022_from_2025.py
# 期望: 输出 "PHASE 11 SYNC: 48 files generated"
```

scripts_2022 完全重建, 字节级 ASCII + py2/py3 兼容 + PySide2 hard-pin.

### Phase 11C — Maya 2022 specific smoke test

```bash
python tools/audit_phase11_maya2022_smoke.py
# 测试:
#   1. ast.parse 全 48 文件
#   2. byte-level ASCII
#   3. import _STR_TYPES try/except 块 in core.py / core_json.py
#   4. ui/compat.py only imports PySide2 (no PySide6 ref)
#   5. 全文件无 PySide6 import
#   6. defensive try/except in help_button.py
```

### Phase 11D — Cmake double-build verify

```bash
strings modules/RBFtools/plug-ins/win64/2022/RBFtools.mll | grep -E "M_P0_" | sort -u
strings modules/RBFtools/plug-ins/win64/2025/RBFtools.mll | grep -E "M_P0_" | sort -u
diff <(...) <(...)
```

若 diff 非 0 或某 .mll 缺 fix → `cmake clean rebuild`.

### Phase 11E — 更新 .mod template + installer

[resources/module_template.mod](resources/module_template.mod) MAYAVERSION:2022 行 `[r] scripts: scripts_2022`. (Phase 4 已做, Phase 11 verify.)

installer rebuild:

```bash
tools\build_installer.bat
```

### Phase 11F — Drift detector test 更新

[modules/RBFtools/tests/unit/test_m_p0_maya_version_isolation_drift.py](modules/RBFtools/tests/unit/test_m_p0_maya_version_isolation_drift.py) 更新, 兼容 Phase 11 新 sync script 输出.

### Commit 序列 (Policy B 严守)

| # | Commit | 内容 |
|---|---|---|
| 1 | `docs(planner): Phase 11 from-scratch Maya 2022 blueprint` | git add brief + audit scripts |
| 2 | `chore(maya2022): archive obsolete scripts_2022 (Phase 11A)` | `git mv` 老 scripts_2022 → `_DEPRECATED_phase11` |
| 3 | `fix(tooling): rewrite sync_2022_from_2025.py from-scratch (Phase 11B)` | 新 sync script |
| 4 | `feat(maya2022): regenerate scripts_2022 from scratch (Phase 11B)` | 跑新 sync, 创建新 scripts_2022 |
| 5 | `test(maya2022): Phase 11 smoke + drift detector update (Phase 11C+F)` | smoke + drift test |
| 6 | (若 .mll 缺 fix) `chore(deploy): rebuild .mll 2022 + 2025 (Phase 11D)` | cmake clean rebuild |
| 7 | `chore(installer): rebuild for Phase 11` | installer .exe 重打 |

预期: 5-7 个 commit (Phase 11D 取决于 .mll 状态).

---

## 4. 不动什么

- ❌ 不动 `modules/RBFtools/scripts/` (Maya 2025 神圣)
- ❌ 不动 C++ source (除非 Phase 11D 发现 .mll 缺 fix 需 rebuild)
- ❌ 不动 git history (Policy A — `git mv` 不是 `git rm`)
- ❌ 不动 4/4 anchors
- ❌ 不参考现有 scripts_2022 任何字节 — Phase 11 是 from-scratch 设计

---

## 5. 关键差异 vs Phase 1-10 (用户角度)

| 方面 | Phase 1-10 | Phase 11 |
|---|---|---|
| 起点 | 现有 scripts_2022 (sync 派生) | scripts/ 唯一 source |
| 修复策略 | 增量 audit + patch | from-scratch rewrite |
| sync script | 累积 7 个 Rule, history sync 派生 | 重新设计, 包含 R1-R10 完整集 |
| PySide2 | 通过 ui/compat.py fallback (隐式) | **scripts_2022 hard-pin PySide2**, 不 try PySide6 |
| 信任度 | 现有 scripts_2022 audit pass 但用户实测 fail | 假设现有 scripts_2022 是错的, 重做 |

---

## 6. 验证

### 6.1 静态

```bash
# Phase 11B 后:
python tools/sync_2022_from_2025.py --check    # OK
python -c "
import os
for r,_,fs in os.walk('modules/RBFtools/scripts_2022'):
    for f in fs:
        if f.endswith('.py'):
            open(os.path.join(r,f),'rb').read().decode('ascii')
print('All ASCII')
"

# Phase 11C 后:
python tools/audit_phase11_maya2022_smoke.py   # OK

# Phase 11D 后:
diff <(strings .../win64/2022/RBFtools.mll | grep M_P0_ | sort -u) \
     <(strings .../win64/2025/RBFtools.mll | grep M_P0_ | sort -u)
# 期望 0 diff

# Full sweep:
python -m pytest modules/RBFtools/tests --continue-on-collection-errors -q
# 期望: 614+ passed, 0 回归
```

### 6.2 用户实测 (双 Maya 必跑)

**Maya 2022.5.1**:
1. 完全卸载旧 RBFtools (删 `~/Documents/maya/modules/RBFtools` 整目录 + `.mod`)
2. 重启电脑
3. 装新 installer (Phase 11 build, mtime 应 > 2026-05-12 22:00)
4. 启动 Maya 2022, 跑 Phase 10 §1.1 自检脚本验证:
   - module path 含 `scripts_2022`
   - core.py 含 `M_P0_DISCONNECT_SCALE_RESTORE` 关键字
   - .mll sha256 匹配期望
5. 测试 MQB 切换 + Apply (driver multi-source case) → 期望无 kFailure
6. 测试 disconnect → 期望 driven.scaleX = 1.0
7. 测试帮助气泡 → 期望显示

**Maya 2025.3**:
8. 共用 modules 重启 Maya 2025
9. 同样 5-7 测试 → 期望与 milestone `RBF-MQB-correct-2026-05-12` 行为一致

---

## 7. 关键文件路径速查

| 文件 | 操作 |
|---|---|
| `X:\Plugins\RBFtools\modules\RBFtools\scripts\` | **不动** (Maya 2025 神圣) |
| `X:\Plugins\RBFtools\modules\RBFtools\scripts_2022\` | **archive 为 scripts_2022_DEPRECATED_phase11, 重建** |
| `X:\Plugins\RBFtools\tools\sync_2022_from_2025.py` | **重写** (Phase 11B) |
| `X:\Plugins\RBFtools\tools\audit_phase11_maya2022_smoke.py` | **新建** (Phase 11C) |
| `X:\Plugins\RBFtools\resources\module_template.mod` | Phase 4 已正确, verify |
| `X:\Plugins\RBFtools\source\RBFtools.cpp` | 不动 (Phase 9 验证含全部 fix) |
| `X:\Plugins\RBFtools\modules\RBFtools\plug-ins\win64\2022\RBFtools.mll` | Phase 11D verify, 必要时 rebuild |
| `X:\Plugins\RBFtools\installer\RBFtoolsInstaller.exe` | Phase 11E 重打 |
| `X:\Plugins\RBFtools\modules\RBFtools\tests\unit\test_m_p0_maya_version_isolation_drift.py` | Phase 11F update |
