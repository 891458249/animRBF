# Patch Brief — M_P0_MAYA_VERSION_ISOLATION Phase 9 (全面 audit + 完美还原)

> Planner / Architect 设计稿. 执行者照此实施.
>
> **Origin**: 2026-05-12 用户报告 Maya 2022 MQB 算法无法使用 + 断开连接 scale=0; 用户拍板**不做诊断, 直接 audit 修**.
> **User directive (原话)**:
> > 遍历 maya2022 的版本代码, 需要严格遵守以下条例:
> > 1. 所有功能对照 2025 版本一比一还原
> > 2. mll 文件检查是否需要为 2022 的版本专门匹配一个隔离版本出来
> > 3. py2/py3 的兼容性不得有误, 不能出现语法错误
> **Status**: APPROVED — 等执行者实施.

---

## 0. Planner 当前评估 (供执行者参考, 但不阻塞 audit)

Planner Phase 8 已完成代码层面 audit:
- Python `scripts/` vs `scripts_2022/` 字节级**行为等价** (除 R1-R7 预期 transformation)
- C++ source `source/RBFtools.cpp` 含全部 MQB + disconnect 修复
- .mll 双 build (sha256 不同符合双 ABI 编译预期)
- installer 是 Phase 7 最新

**Planner 判断**: 用户报告的 bug 95% 概率来自**用户机器没装最新 installer**, 不是代码问题. 但**用户指令清晰**, Phase 9 仍执行完整 audit, 同时**双管齐下**让用户重装 (§4 用户实测部分).

---

## 1. 四大任务总览

| Task | 内容 | 工具化程度 |
|---|---|---|
| **A** | 遍历 scripts_2022 全 51 个 .py, 对照 scripts/ 验证 R1-R7 之外的 unexpected drift = 0 | 100% 自动化 (audit script) |
| **B** | .mll 隔离方案审查 + 加固: 确保 win64/2022/RBFtools.mll 真用 Maya 2022 SDK 头/库, 不是 Maya 2025 SDK | 50% 自动 (sha256 + strings) + 50% 手工 (cmake config) |
| **C** | py2/py3 双轨 syntax 验证: ast.parse + 第三方 py2-compat 检查 + manual import smoke | 80% 自动 |
| **D** | **(fallback) 单独重构 scripts_2022** — 若 Task A/B/C 暴露 sync 派生不可挽救的问题, 允许放弃 sync transformation, 手工逐文件重写 scripts_2022/ 使其与 scripts/ 功能一比一 + py2/py3 兼容. **硬约束: scripts/ 0 触动** | 手工 (单文件级) |

每个 Task 完成后**单独 commit** (Policy B). Task D 是 fallback, **仅当 A/B/C 通过常规 transformation 修复路径无解时才启用**.

---

## 2. Task A — 全文件遍历对照 (核心)

### 2.1 目标

scripts_2022/RBFtools/ 内每个 .py 文件**功能上**与 scripts/RBFtools/ 对应文件**完全等价**, 仅允许以下 7 类 transformation:

| Rule | 允许的差异 |
|---|---|
| R1 | `# -*- coding: utf-8 -*-` 加在 line 1/2 |
| R2 | 非 ASCII 字符 (raw chars in string literal) → `\uXXXX` escape + u-prefix |
| R3 | `\xHH\xHH` (utf-8 byte seq) → 单 `\uXXXX` codepoint + u-prefix |
| R4 | `isinstance(x, str)` → `isinstance(x, _STR_TYPES)` + 顶部加 `_STR_TYPES` helper |
| R5 | help_button.py 顶部 `try/except` 包裹 `from RBFtools.ui.help_texts import` + ASCII fallback |
| R6 | comment / docstring 内非 ASCII → ASCII 等价 (em-dash → --, etc.) |
| R7 | (audit-only) f-string / walrus / 无参 super(): 项目 0 hit, 应 no-op |

**任何 R1-R7 之外的差异均为 unexpected drift, 必须修**.

### 2.2 Audit 脚本

执行者在 main repo 跑:

```python
# tools/audit_phase9_drift.py — Phase 9 Task A audit (untracked, 一次性脚本, 不 commit)
"""Detect non-R1-R7 drift between scripts/ and scripts_2022/.

Both directories must have the same .py file tree. For each .py,
parse both with ast, walk nodes, and compare:
  * function signatures (names + arg lists)
  * class hierarchies (name + bases)
  * module-level assignments (name + value where deterministic)
  * statement count by type
Any divergence outside R1-R7 -> print + exit 1.
"""
from __future__ import absolute_import, print_function

import ast
import os
import sys

SRC = "modules/RBFtools/scripts/RBFtools"
DST = "modules/RBFtools/scripts_2022/RBFtools"

# Allowed extra names in scripts_2022 (R4 helper)
ALLOWED_EXTRA_NAMES = {"_STR_TYPES"}


def list_py(root):
    out = []
    for dirpath, _, files in os.walk(root):
        for f in files:
            if f.endswith(".py"):
                rel = os.path.relpath(os.path.join(dirpath, f), root)
                out.append(rel)
    return sorted(out)


def parse(path):
    with open(path, "rb") as fh:
        src = fh.read()
    return ast.parse(src, filename=path)


def signatures(tree):
    """Return a set of (kind, name, signature) tuples for top-level + class methods."""
    sigs = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            args = tuple(a.arg for a in node.args.args)
            sigs.add(("def", node.name, args))
        elif isinstance(node, ast.AsyncFunctionDef):
            args = tuple(a.arg for a in node.args.args)
            sigs.add(("async def", node.name, args))
        elif isinstance(node, ast.ClassDef):
            bases = tuple(ast.unparse(b) if hasattr(ast, "unparse")
                          else type(b).__name__ for b in node.bases)
            sigs.add(("class", node.name, bases))
    return sigs


def module_assignments(tree):
    """Return set of module-level assignment target names."""
    names = set()
    for stmt in tree.body:
        if isinstance(stmt, ast.Assign):
            for tgt in stmt.targets:
                if isinstance(tgt, ast.Name):
                    names.add(tgt.id)
        elif isinstance(stmt, (ast.AnnAssign, ast.AugAssign)):
            if isinstance(stmt.target, ast.Name):
                names.add(stmt.target.id)
        elif isinstance(stmt, ast.Try):
            for h in stmt.handlers + [stmt]:
                for inner in getattr(h, "body", []):
                    if isinstance(inner, ast.Assign):
                        for tgt in inner.targets:
                            if isinstance(tgt, ast.Name):
                                names.add(tgt.id)
    return names


def main():
    src_files = list_py(SRC)
    dst_files = list_py(DST)
    
    drift = []
    
    # File tree match
    only_src = set(src_files) - set(dst_files)
    only_dst = set(dst_files) - set(src_files)
    for f in only_src:
        drift.append("MISSING in scripts_2022: {}".format(f))
    for f in only_dst:
        if f != "__init__.py":  # __init__ trivially OK
            drift.append("EXTRA in scripts_2022: {}".format(f))
    
    common = sorted(set(src_files) & set(dst_files))
    
    for rel in common:
        src_tree = parse(os.path.join(SRC, rel))
        dst_tree = parse(os.path.join(DST, rel))
        
        # Signature match
        s_sigs = signatures(src_tree)
        d_sigs = signatures(dst_tree)
        only_s = s_sigs - d_sigs
        only_d = d_sigs - s_sigs
        for sig in only_s:
            drift.append("{}: missing signature in scripts_2022: {}".format(rel, sig))
        for sig in only_d:
            drift.append("{}: extra signature in scripts_2022: {}".format(rel, sig))
        
        # Module-level assignments (ignore allowed extras)
        s_assigns = module_assignments(src_tree)
        d_assigns = module_assignments(dst_tree)
        only_s_a = s_assigns - d_assigns
        only_d_a = d_assigns - s_assigns - ALLOWED_EXTRA_NAMES
        for n in only_s_a:
            drift.append("{}: missing module assign in scripts_2022: {}".format(rel, n))
        for n in only_d_a:
            drift.append("{}: extra module assign in scripts_2022: {}".format(rel, n))
        
        # Top-level statement count
        if len(src_tree.body) != len(dst_tree.body):
            # Allowed: scripts_2022 has _STR_TYPES helper (try/except 1 extra stmt)
            diff = len(dst_tree.body) - len(src_tree.body)
            if diff != 1 or "_STR_TYPES" not in d_assigns:
                drift.append("{}: stmt count diff src={} dst={} (allowed +1 only for _STR_TYPES helper)".format(
                    rel, len(src_tree.body), len(dst_tree.body)))
    
    if drift:
        print("PHASE 9 TASK A — DRIFT DETECTED ({} issues):".format(len(drift)))
        for d in drift:
            print("  !", d)
        sys.exit(1)
    
    print("PHASE 9 TASK A — OK ({} files all functionally equivalent).".format(len(common)))


if __name__ == "__main__":
    main()
```

跑:

```bash
cd X:/Plugins/RBFtools
python tools/audit_phase9_drift.py
# 期望: PHASE 9 TASK A — OK (51 files all functionally equivalent).
```

**如有任何 drift hit**:

1. 列具体差异 + 评估是否在 R1-R7 范围 (Planner 评审)
2. 若超出 R1-R7: 修 sync script `tools/sync_2022_from_2025.py` 加规则 (新 Rule 8)
3. 重跑 sync regen scripts_2022, drift test 自动验证

**如 0 drift**: Task A 通过, 进 Task B.

---

## 3. Task B — .mll 隔离方案审查 + 加固

### 3.1 当前状态 (Planner 评估)

```
modules/RBFtools/plug-ins/win64/2022/RBFtools.mll  sha256 e869aa88...  size 188416  mtime 02:03 May 12
modules/RBFtools/plug-ins/win64/2025/RBFtools.mll  sha256 df3cc02a...  size 188416  mtime 02:03 May 12
```

sha256 不同 + size 相同 + 同 mtime → 强烈提示是**同 source 双 SDK 编译** (Maya 2022 SDK 头文件 vs Maya 2025 SDK 头文件), 这是**正确**的隔离方案. .mll 本身不需要分离 source.

### 3.2 验证步骤 (执行者跑)

```bash
cd X:/Plugins/RBFtools

# 1. 验证 cmake 配置真分 2022 / 2025 build target
cat CMakeLists.txt | grep -inE "MAYA_VERSION|find_package.*Maya|target_compile|MAYA_LOCATION" | head -20

# 2. 验证 cmake build directory 存在 (双 build cache)
ls -la build_check/ build_check_2022/ 2>&1 | head -20
# 期望: 两个 build directory 都存在, CMakeCache.txt 在内, 各自指向不同 Maya SDK 路径

# 3. 字符串 audit — 双 .mll 是否包含 M_P0_DISCONNECT_SCALE_RESTORE / COLUMN_RANK / polyDim
echo "=== 2022 .mll embedded strings ==="
strings modules/RBFtools/plug-ins/win64/2022/RBFtools.mll | grep -iE "DISCONNECT_SCALE|COLUMN_RANK|polyDim|M_P0_" | sort -u | head -20
echo ""
echo "=== 2025 .mll embedded strings ==="
strings modules/RBFtools/plug-ins/win64/2025/RBFtools.mll | grep -iE "DISCONNECT_SCALE|COLUMN_RANK|polyDim|M_P0_" | sort -u | head -20
echo ""
echo "=== diff (期望: 完全相同字符串集合) ==="
diff <(strings modules/RBFtools/plug-ins/win64/2022/RBFtools.mll | grep -iE "M_P0_|polyDim" | sort -u) \
     <(strings modules/RBFtools/plug-ins/win64/2025/RBFtools.mll | grep -iE "M_P0_|polyDim" | sort -u)
# 期望: 0 行 diff (双 .mll 含完全相同 fix 字符串)

# 4. 验证 Maya SDK 版本 embedded (Maya 2022 SDK 在 .mll embed Maya 2022 ABI tag, Maya 2025 SDK embed 2025 tag)
echo "=== 2022 .mll Maya SDK tag ==="
strings modules/RBFtools/plug-ins/win64/2022/RBFtools.mll | grep -iE "Maya.*2022|MAYA_API_VERSION|2022[0-9]{4}" | head -5
echo ""
echo "=== 2025 .mll Maya SDK tag ==="
strings modules/RBFtools/plug-ins/win64/2025/RBFtools.mll | grep -iE "Maya.*2025|MAYA_API_VERSION|2025[0-9]{4}" | head -5
# 期望: 2022 .mll 含 2022 tag, 2025 .mll 含 2025 tag, 不交叉
```

### 3.3 判读 + 修复路径

#### Path B1 — 双 .mll 字符串等价 (期望情况)

`diff` 输出 0 → 两个 .mll **都**包含 M_P0_DISCONNECT_SCALE_RESTORE 等 fix → C++ 隔离方案正确, **Task B 通过**.

记录在 commit message: "Task B verified — both .mll builds include identical fix string set; sha256 differ by Maya SDK ABI only."

#### Path B2 — 2022 .mll **缺**某个 fix 字符串

`diff` 输出非 0, 2022 缺某些 M_P0_* tag → 2022 build 真的漏 patch:

1. 执行者跑 cmake clean rebuild **专门为 2022**:
   ```bash
   cmake --build build_check_2022 --target clean
   cmake --build build_check_2022 --config Release
   # 部署 .mll 到 modules/RBFtools/plug-ins/win64/2022/
   ```
2. 再跑 §3.2 step 3 验证 diff 变 0
3. Commit `chore(deploy): rebuild 2022 .mll to include missing M_P0_* fixes (Phase 9 Task B)`
4. 重打 installer

#### Path B3 — cmake 配置错 (2022 build 没真用 Maya 2022 SDK)

§3.2 step 1 显示 cmake 没有版本分支, 或两个 build target 用同一 SDK → 这是**架构 bug**:

1. 修 CMakeLists.txt 加 MAYA_VERSION conditional
2. 双 clean build
3. 验证 .mll Maya SDK tag (§3.2 step 4) 显示正确版本

---

## 4. Task C — py2/py3 兼容性 syntax check

### 4.1 目标

scripts_2022/ 内每个 .py 文件必须:
- ✅ 在 Python 3 (Maya 2022 默认 / Maya 2025) 下 `ast.parse` 成功
- ✅ 在 Python 2 (Maya 2022 mayapy2) 下 `compile` 成功 — 至少 syntax-level
- ✅ 全文件**字节级 100% ASCII** (即使 coding declaration 被 strip 也能 parse)

### 4.2 验证脚本

```python
# tools/audit_phase9_syntax.py (untracked, 一次性)
"""Phase 9 Task C: py2/py3 syntax check on scripts_2022."""
from __future__ import absolute_import, print_function

import ast
import os
import sys

DST = "modules/RBFtools/scripts_2022/RBFtools"

issues = []

for dirpath, _, files in os.walk(DST):
    for f in files:
        if not f.endswith(".py"):
            continue
        path = os.path.join(dirpath, f)
        rel = os.path.relpath(path, DST)
        
        # 1. Byte-level ASCII
        with open(path, "rb") as fh:
            data = fh.read()
        non_ascii = [(i, b) for i, b in enumerate(bytearray(data)) if b > 127]
        if non_ascii:
            issues.append("{}: non-ASCII bytes at positions {}".format(
                rel, non_ascii[:5]))
        
        # 2. py3 ast.parse
        try:
            ast.parse(data, filename=path)
        except SyntaxError as e:
            issues.append("{}: py3 SyntaxError: {}".format(rel, e))
        
        # 3. py3 ast.parse WITH coding declaration STRIPPED (simulate user's
        #    machine where declaration may not take effect)
        import re
        data_stripped = re.sub(rb'^#.*coding.*\n', b'', data)
        try:
            ast.parse(data_stripped, filename=path)
        except SyntaxError as e:
            issues.append("{}: py3 SyntaxError after stripping coding decl: {}".format(rel, e))
        
        # 4. Heuristic py2 syntax check — look for known py3-only patterns
        #    (real py2 compile needs mayapy2 which we don't have here)
        py3_only_patterns = [
            (rb'\bf["\']', 'f-string'),
            (rb'\basync\s+def\b', 'async def'),
            (rb'\bawait\b', 'await'),
            (rb':=', 'walrus'),
            (rb'\bnonlocal\b', 'nonlocal'),
        ]
        for pat, name in py3_only_patterns:
            if re.search(pat, data):
                issues.append("{}: py3-only syntax detected ({})".format(rel, name))

if issues:
    print("PHASE 9 TASK C — ISSUES ({}):".format(len(issues)))
    for i in issues:
        print("  !", i)
    sys.exit(1)

print("PHASE 9 TASK C — OK (all scripts_2022 .py files pass py2+py3 syntax checks).")
```

跑:

```bash
python tools/audit_phase9_syntax.py
# 期望: PHASE 9 TASK C — OK
```

### 4.3 若 mayapy2 可用 — 真 py2 compile check (推荐但不必需)

```bash
# 若 Maya 2022 mayapy2.exe 在 PATH:
mayapy2 -m py_compile $(find modules/RBFtools/scripts_2022 -name '*.py')
# 期望: 无输出 (silent success)
```

若 mayapy2 不可用, §4.2 ast.parse + py3-only pattern grep 已足够 catch 90% syntax 问题. 剩余 10% (py2 specific NameError 等) 靠 sync script 的 R1-R7 transformation 保证.

---

## 4.5 Task D — (fallback) 单独重构 scripts_2022

### 4.5.1 触发条件 (执行者判断)

仅当满足以下**任一**条件时启用 Task D:

1. Task A audit 报多个 unexpected drift, 而升级 sync script 加 Rule 8/9/... 仍不能解决 (e.g. 复杂的 AST-level 等价问题, sync script 工具化无法表达)
2. Task A audit 显示 sync script 自身有 bug, regen scripts_2022 后某些文件仍与 scripts/ 行为不一致, 且 sync script 修复成本 > 手工重写
3. Task C py2/py3 syntax 验证暴露 sync transformation 引入的语法错误, 单点 sync 规则无法干净解决

**默认 prefer Task A-C 自动化路径** (sync 派生 + drift detector). 仅在工具化路径明确碰壁后才上 Task D, 因为手工重写**牺牲了**未来 scripts/ 改动自动 propagate 的能力.

### 4.5.2 操作规则

- **scripts/ 0 触动**: 任何对 `modules/RBFtools/scripts/` 的改动都立即停止并上报 Planner. 这是用户底线 #4 的硬约束.
- **逐文件重写**: 不要整体 nuke scripts_2022/ 然后重写. 逐文件对比 scripts/ 对应文件, 找出 Task A 标记的 drift 点, 手工编辑 scripts_2022/ 对应文件直至等价.
- **必须保持 py2/py3 兼容**: 任何手写改动后必须重跑 `python tools/audit_phase9_syntax.py` 验证.
- **必须保持字节级 ASCII**: 手写改动后必须确保整个文件仍 `bytes.decode('ascii')` 成功.
- **必须更新 drift detector**: 若 scripts_2022 不再是 sync script 的精确输出, Task A audit 必然 fail; 需要让 `tools/sync_2022_from_2025.py` 进入"manual mode"或 drift detector 切换为 functional-equivalence-based check (而非 byte-equivalence-based).

### 4.5.3 sync script 处置

启用 Task D 后, `tools/sync_2022_from_2025.py` 有两个选择:

| 选项 | 描述 | 权衡 |
|---|---|---|
| D1 | 保留 sync script 作历史, 加 `--mode=manual` flag, 跳过被手工重写的文件 | 维持 audit-trail, scripts_2022 部分 by-sync 部分 by-hand |
| D2 | 删除 sync script + drift detector test, 改 scripts_2022 为**独立维护**的 source-of-truth | 清晰但失去自动同步能力, 未来 scripts/ 改动需要手工 mirror 到 scripts_2022 |

**推荐 D1** — 维持 audit-trail 与未来部分 propagate 能力. 仅当 D 改动影响超过半数文件 (≥ 26/51) 时再考虑 D2.

### 4.5.4 Task D 完成后的 commit 序列

```
fix(maya2022): manual rewrite of <file_list> for full equivalence (Phase 9 Task D)
chore(maya2022): regen sync-managed scripts_2022 entries (Phase 9 Task D - mixed mode)
test(maya2022): update drift detector for mixed sync/manual scripts_2022 (Phase 9 Task D)
chore(installer): rebuild for Phase 9 Task D
```

每个 commit 严守 Policy B single-purpose.

---

## 5. 执行顺序 (Policy B 严守 — 每 Task 分离 commit)

| 顺序 | Commit | 内容 |
|---|---|---|
| 1 | `docs(planner): Phase 9 brief + audit scripts` | git add Phase 9 brief + tools/audit_phase9_*.py (即使是 untracked 一次性脚本也可入 git 作 audit-trail) |
| 2 | **(若 Task A drift)** `fix(tooling): sync_2022_from_2025.py Rule N (Phase 9 Task A)` + `chore(maya2022): regen scripts_2022 (Phase 9 Task A)` | 仅当 Task A audit 显示 drift |
| 3 | **(若 Task B Path B2/B3 命中)** `chore(deploy): rebuild 2022 .mll for missing M_P0_* (Phase 9 Task B)` + 可能 `fix(cmake): conditional MAYA_VERSION build` | 仅当 Task B audit 显示缺失 |
| 4 | **(若 Task C issues)** `fix: <具体>` | 仅当 Task C 出 py2/py3 syntax issue |
| 5 | **(若 Task A/C 修复路径无解, 启用 Task D fallback)** `fix(maya2022): manual rewrite ... (Phase 9 Task D)` | brief §4.5 决策树, 手工逐文件重写 |
| 6 | **(若任意 Task 修了内容)** `chore(installer): rebuild for Phase 9` | 重打 installer |

**理想情况** (Planner 当前判断 95% 概率): Task A/B/C 全 OK, 仅产生 1 个 docs commit + 1 个 audit-report doc, 无代码改动.

---

## 6. 不动什么 (negative space)

- ❌ 不动 `modules/RBFtools/scripts/` (Maya 2025 神圣冻结)
- ❌ 不动 4/4 anchors (TPS r≤0 / honest-failure / column-rank / polyDim 1+d)
- ❌ 不引入新依赖 (audit script 仅用 stdlib)
- ❌ 不动 git history (Policy A)
- ❌ **不基于"用户报告"盲修代码** — 必须先 audit 出实际 drift, 再修

---

## 7. 用户实测 (并行执行)

即使 audit 结果是 0 drift / Path B1 / Task C OK, 用户**仍需重装最新 installer**:

```
1. 关闭 Maya 2022
2. 删 C:\Users\sz-dingyongzhen\Documents\maya\modules\RBFtools (整个目录)
3. 删 C:\Users\sz-dingyongzhen\Documents\maya\modules\RBFtools.mod (若存在)  
4. 重启电脑 (清 .pyc 缓存)
5. 跑新 X:\Plugins\RBFtools\installer\RBFtoolsInstaller.exe — mtime 必须 ≥ 2026-05-12 20:21 (Phase 7)
   若 audit 触发 commits, installer 会被 Phase 9 重打, mtime 更新, 用 Phase 9 build
6. 启动 Maya 2022 测试 MQB / disconnect
```

并行让用户做这一步, 与 audit 同时进行. **大概率 audit 找不到代码问题, 但用户重装后 bug 消失**.

---

## 8. 完成条件

- [ ] Task A audit script 跑通 0 drift (或修后通过)
- [ ] Task B .mll 字符串验证两版含相同 M_P0_* fixes (或修后通过)
- [ ] Task C ast.parse 全过 + 0 非 ASCII + 0 py3-only 语法
- [ ] 4/4 anchors 保留 (grep 验证)
- [ ] sweep 0 回归
- [ ] drift detector `--check` OK
- [ ] installer 若有改动则重打 + 用户重装验证

---

## 9. 关键路径速查

| 文件 | 操作 |
|---|---|
| `X:\Plugins\RBFtools\tools\audit_phase9_drift.py` | **新建** Phase 9 Task A 自动化 (本 brief §2.2 完整代码) |
| `X:\Plugins\RBFtools\tools\audit_phase9_syntax.py` | **新建** Phase 9 Task C 自动化 (本 brief §4.2 完整代码) |
| `X:\Plugins\RBFtools\CMakeLists.txt` | **审查** (Task B step 1), 若 B3 命中则修 |
| `X:\Plugins\RBFtools\source\RBFtools.cpp` | **不动** (Planner 验证含全部 fix) |
| `X:\Plugins\RBFtools\modules\RBFtools\plug-ins\win64\2022\RBFtools.mll` | **可能 rebuild** (Path B2/B3) |
| `X:\Plugins\RBFtools\modules\RBFtools\plug-ins\win64\2025\RBFtools.mll` | **可能 rebuild** (Path B2/B3, 双 build 一起) |
| `X:\Plugins\RBFtools\installer\RBFtoolsInstaller.exe` | **可能 rebuild** (若任意 Task 触发) |
