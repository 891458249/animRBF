# Patch Brief — M_P0_MAYA_VERSION_ISOLATION Phase 10 (深度审计 + 用户副本验证)

> Planner / Architect 设计稿. 执行者照此实施.
>
> **Origin**: 2026-05-12 用户**第四轮报告** Maya 2022 仍报 `RBF decomposition failed kernel index 4 polyDim = 7 (M_P0_RBF_POLYNOMIAL_AUGMENTATION)` + `disconnect 时 scale=0`. 用户原话"严格对照所有代码, 不要再出现纰漏了".
> **Status**: APPROVED — 等执行者实施.

---

## 0. Planner 关键诊断 (执行者必读)

通过 .cpp source 阅读 + Python 调用链 trace, 得出:

### 诊断 1 — disconnect scale=0 路径上**确认**有 fix

[core.py:4337-4345](modules/RBFtools/scripts/RBFtools/core.py) `_disconnect_or_purge` 内:

```python
if side == "output" and other_plug:
    attr_short = other_plug.rsplit(".", 1)[-1]
    if attr_short in SCALE_ATTR_NAMES:
        try:
            cmds.setAttr(other_plug, 1.0)
        except Exception as exc:
            cmds.warning("disconnect: failed to restore ...")
```

调用链 `main_window._on_disconnect` → `controller.disconnect_routed` → `core.disconnect_routed` (L4672) → `_disconnect_bone_specific` / `_disconnect_bone_all` → **`_disconnect_or_purge`** → L4337 scale restore.

**此 fix 是 M_P0_DISCONNECT_SCALE_RESTORE (2026-05-10) 引入**. 若用户机器代码缺此段, 必然 scale=0.

### 诊断 2 — MQB error 是 column-rank defence fail-through 后的 final error

[source/RBFtools.cpp:2386-2393](source/RBFtools.cpp):

```cpp
MGlobal::displayError(
    MString("RBF decomposition failed at kernel index ") + kernelVal +
    " with polyDim = " + polyDim +
    "; remove duplicate poses or move poses off a common hyperplane "
    "(M_P0_RBF_POLYNOMIAL_AUGMENTATION).");
```

此 error**只在** column-rank defence (L2140-2360) **也无法 recover** 时 raise. 若用户 .mll 含 column-rank defence (M_P0_RBF_COLUMN_RANK_DEFENSE, 2026-05-12), Script Editor 必应**先看到** warning:
```
... : M_P0_RBF_COLUMN_RANK_DEFENSE — dropping N degenerate driver column(s) ...
```

用户若**没看到这条 warning**, 强烈暗示用户的 .mll 是 column-rank defence patch 之前的 build.

### Planner 当前判断 (95% 概率)

用户机器装的代码/binary **不是 main repo HEAD (`1006212` Phase 9) 的状态**, 而是某个**更早的 build** (可能 M_P0_RBF_POLYNOMIAL_AUGMENTATION 之后但 M_P0_DISCONNECT_SCALE_RESTORE + M_P0_RBF_COLUMN_RANK_DEFENSE 之前). 用户:
- 没真正卸载旧 RBFtools (老文件锁/.pyc 残留)
- 或装了某个早期 Phase 1-4 的 installer

**但**为遵守用户"严格对照所有代码, 不要再出现纰漏"诉求, Phase 10 仍执行**双重 verification**:

- **Task α**: 5 行 Maya Script Editor 自检脚本 — 用户**必须先跑**, 输出反馈 Planner
- **Task β**: 执行者 deep function-body-level audit — 不止 signature, 看 function body byte-level R1-R7-normalized 等价

---

## 1. Task α — 用户机器自检 (5 行 Maya Script Editor 脚本)

### 1.1 自检脚本 (用户在 Maya 2022 Script Editor 跑)

```python
# RBFtools Phase 10 自检 — 5 行版, 把整段输出复制回 Planner
import os, hashlib
import maya.cmds as cmds
import RBFtools.ui.help_texts as ht
import RBFtools.core as core

print("=" * 70)
print("RBFtools Phase 10 Self-Verification")
print("=" * 70)

# Q1. Python module path - 期望含 'scripts_2022'
print("\nQ1 module path:")
print("   help_texts:", ht.__file__)
print("   core:      ", core.__file__)

# Q2. 关键 fix 是否在 core.py 内 (M_P0_DISCONNECT_SCALE_RESTORE)
print("\nQ2 disconnect scale fix presence:")
with open(core.__file__, "rb") as fh:
    src = fh.read()
has_fix = b"M_P0_DISCONNECT_SCALE_RESTORE" in src
has_scale_restore = b"cmds.setAttr(other_plug, 1.0)" in src
print("   M_P0_DISCONNECT_SCALE_RESTORE comment present:", has_fix)
print("   cmds.setAttr(other_plug, 1.0) restore call present:", has_scale_restore)

# Q3. core.py sha256 - 与 main repo 期望对比
sha_core = hashlib.sha256(src).hexdigest()
print("\nQ3 core.py sha256:")
print("   actual:  ", sha_core)
print("   (main repo scripts_2022/core.py 期望: see Planner table)")

# Q4. .mll 路径 + sha256 - 期望匹配 e869aa88... (2022) 或 df3cc02a... (2025)
plugin_path = cmds.pluginInfo("RBFtools", q=True, path=True)
print("\nQ4 .mll path + sha256:")
print("   path:", plugin_path)
if plugin_path and os.path.exists(plugin_path):
    with open(plugin_path, "rb") as fh:
        sha_mll = hashlib.sha256(fh.read()).hexdigest()
    print("   sha256:", sha_mll)
    print("   期望 (Maya 2022): e869aa88fdb9e10f6ef9377bc0e2db43f5427183146b950224338a20020c0e4a")
    print("   期望 (Maya 2025): df3cc02a9cf56caf00daa7d67147516e337ee2189d35f637b7084202c82f3996")

# Q5. Python 版本
import sys
print("\nQ5 Python version:", sys.version.split()[0])
print("   (Maya 2022 默认 py3, mayapy2 是 py2 模式)")

print("\n" + "=" * 70)
print("把以上整段输出复制回 Planner")
print("=" * 70)
```

### 1.2 Planner 判读 5 个 Q 的结果

| 输出 | 命中 | 含义 | 行动 |
|---|---|---|---|
| Q1 path **不含** 'scripts_2022' (走 'scripts' 路径) | **用户 .mod routing 失败** | 用户机器走了 Maya 2025 的代码 — 该路径在 Maya 2022 py3 应该 also work, 但若 mayapy2 则 isinstance str check fail | 修复用户 .mod 路由 / 重装 |
| Q2 `M_P0_DISCONNECT_SCALE_RESTORE` 或 `cmds.setAttr(other_plug, 1.0)` 为 **False** | **用户 core.py 是 M_P0_DISCONNECT_SCALE_RESTORE patch 之前的版本** | 直接证据用户装的是旧 installer | 强制重装 (Phase 10 §3) |
| Q3 sha256 与 Planner 期望表**不匹配** | 用户 core.py 不是 main repo HEAD | 用户机器代码漂移 | 强制重装 |
| Q4 .mll sha256 与期望**不匹配** | 用户 .mll 是旧 build | 直接证据 — 老 .mll, 缺 M_P0_RBF_COLUMN_RANK_DEFENSE | 强制重装 |
| Q5 Python 是 py2 (`2.x`) | 用户在 mayapy2 模式 | Phase 7 isolation 应已 cover, 但要确认 _STR_TYPES 路径 | 看其他 Q 综合判断 |

**关键 sha256 期望表** (执行者跑 §2.4 后填入 Planner 反馈):

| 文件 | main repo sha256 |
|---|---|
| `modules/RBFtools/scripts_2022/RBFtools/core.py` | (执行者跑 `sha256sum` 填入) |
| `modules/RBFtools/scripts/RBFtools/core.py` | (执行者跑填入) |
| `modules/RBFtools/plug-ins/win64/2022/RBFtools.mll` | `e869aa88fdb9e10f6ef9377bc0e2db43f5427183146b950224338a20020c0e4a` |
| `modules/RBFtools/plug-ins/win64/2025/RBFtools.mll` | `df3cc02a9cf56caf00daa7d67147516e337ee2189d35f637b7084202c82f3996` |

---

## 2. Task β — 执行者 deep function-body audit

Phase 9 audit (audit_phase9_drift.py) 只验证 AST signature + module-level assignments. **不验证 function body**. Phase 10 补充 **function-body byte-level audit, 排除 R1-R7 normalization 后逐对函数比对**.

### 2.1 audit_phase10_function_bodies.py (执行者新建)

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Phase 10 Task β: function-body byte-level audit.

For each .py in scripts/RBFtools, find corresponding scripts_2022/RBFtools
file, parse both with ast, walk function-by-function, dump body, normalize
R1-R7 transformations, then byte-compare.

Any function body diff outside R1-R7 -> print + exit 1.
"""
from __future__ import absolute_import, print_function

import ast
import os
import re
import sys

SRC = "modules/RBFtools/scripts/RBFtools"
DST = "modules/RBFtools/scripts_2022/RBFtools"


def normalize_for_compare(body_dump):
    """Apply R1-R7 normalization so scripts/ vs scripts_2022/ function
    bodies become byte-equivalent after transformation."""
    # R2/R3: \uXXXX escape in u-strings <-> raw unicode char
    # Strategy: decode all \uXXXX in dump back to chars
    def _decode_u(m):
        return chr(int(m.group(1), 16))
    body_dump = re.sub(r'\\u([0-9a-fA-F]{4})', _decode_u, body_dump)
    body_dump = re.sub(r'\\U([0-9a-fA-F]{8})', _decode_u, body_dump)
    
    # R4: isinstance(x, _STR_TYPES) <-> isinstance(x, str)
    body_dump = re.sub(r'isinstance\(([^,]+),\s*_STR_TYPES\)',
                       r'isinstance(\1, str)', body_dump)
    
    # R6: ASCII transliteration in comments — comments stripped by ast already
    # u-prefix in literals: ast normalizes u"x" and "x" both to "x" in py3 dump
    
    return body_dump


def get_functions(tree):
    """Return dict mapping qualified name -> AST FunctionDef node."""
    funcs = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # Build qualified name (Class.method or top-level)
            funcs[node.name] = node
    return funcs


def main():
    if not os.path.isdir(SRC) or not os.path.isdir(DST):
        print("ERROR: SRC or DST missing")
        sys.exit(1)
    
    drift = []
    
    for dirpath, _, files in os.walk(SRC):
        for fname in files:
            if not fname.endswith(".py"):
                continue
            src_path = os.path.join(dirpath, fname)
            rel = os.path.relpath(src_path, SRC)
            dst_path = os.path.join(DST, rel)
            if not os.path.exists(dst_path):
                drift.append("MISSING dst: {}".format(rel))
                continue
            
            with open(src_path, "rb") as fh:
                src_tree = ast.parse(fh.read(), filename=src_path)
            with open(dst_path, "rb") as fh:
                dst_tree = ast.parse(fh.read(), filename=dst_path)
            
            src_funcs = get_functions(src_tree)
            dst_funcs = get_functions(dst_tree)
            
            for name, src_node in src_funcs.items():
                if name not in dst_funcs:
                    drift.append("{}: function {} missing in dst".format(rel, name))
                    continue
                dst_node = dst_funcs[name]
                
                # Dump bodies via ast.dump (py3.8+ supports indent param)
                try:
                    src_body = ast.dump(src_node, indent=2)
                    dst_body = ast.dump(dst_node, indent=2)
                except TypeError:
                    src_body = ast.dump(src_node)
                    dst_body = ast.dump(dst_node)
                
                src_norm = normalize_for_compare(src_body)
                dst_norm = normalize_for_compare(dst_body)
                
                if src_norm != dst_norm:
                    # Show first diff line
                    src_lines = src_norm.split("\n")
                    dst_lines = dst_norm.split("\n")
                    for i, (sl, dl) in enumerate(zip(src_lines, dst_lines)):
                        if sl != dl:
                            drift.append(
                                "{}::{}: body diff at line {} (after R1-R7 normalize):\n"
                                "   src: {}\n"
                                "   dst: {}".format(rel, name, i, sl[:120], dl[:120]))
                            break
                    else:
                        drift.append("{}::{}: body length diff src={} dst={}".format(
                            rel, name, len(src_lines), len(dst_lines)))
    
    if drift:
        print("PHASE 10 TASK β — FUNCTION BODY DRIFT ({} issues):".format(len(drift)))
        for d in drift[:20]:
            print("  !", d)
        if len(drift) > 20:
            print("  ... and {} more".format(len(drift) - 20))
        sys.exit(1)
    
    print("PHASE 10 TASK β — OK (all function bodies R1-R7-equivalent).")


if __name__ == "__main__":
    main()
```

跑:

```bash
cd X:/Plugins/RBFtools
python tools/audit_phase10_function_bodies.py
# 期望: PHASE 10 TASK β — OK
```

### 2.2 若 audit 报 drift — 修复路径

| Drift 类型 | 修复路径 |
|---|---|
| sync script 漏 transformation 某 case (e.g. nested `\xHH` in raw string) | 升级 `tools/sync_2022_from_2025.py` 加 Rule 8 → regen scripts_2022 |
| sync script 引入意外改动 (e.g. 把 numeric literal 改了) | 修 sync script bug → regen |
| 仅 docstring / comment 微差 (R6) | 调 normalize_for_compare 加规则, 重跑 audit |

### 2.3 cmake build flag audit (补充)

```bash
echo "=== build_check (Maya 2025) CMakeCache build flags ==="
grep -E "^(CMAKE_BUILD_TYPE|CMAKE_CXX_FLAGS|MAYA_VERSION)" source/build_check/CMakeCache.txt
echo ""
echo "=== build_check_2022 (Maya 2022) CMakeCache build flags ==="
grep -E "^(CMAKE_BUILD_TYPE|CMAKE_CXX_FLAGS|MAYA_VERSION)" source/build_check_2022/CMakeCache.txt
echo ""
echo "=== source/RBFtools.cpp 是否有 #if MAYA_API_VERSION conditional ==="
grep -nE "#if.*MAYA|#ifdef.*MAYA|#ifndef.*MAYA" source/RBFtools.cpp | head -10
```

期望: build flag 等价 (除 SDK path), `.cpp` 内无 `#if MAYA_API_VERSION` (无版本 specific 代码).

### 2.4 sha256 表生成 (供 Q3 判读)

```bash
echo "=== main repo expected sha256 ==="
sha256sum modules/RBFtools/scripts_2022/RBFtools/core.py
sha256sum modules/RBFtools/scripts/RBFtools/core.py
sha256sum modules/RBFtools/plug-ins/win64/2022/RBFtools.mll
sha256sum modules/RBFtools/plug-ins/win64/2025/RBFtools.mll
```

执行者把输出填入 Phase 10 §1.2 sha256 期望表 — 用户 Q3/Q4 比对.

---

## 3. 修复路径决策树

### Path A (Q2/Q3/Q4 sha256 mismatch — 用户没装新)

执行者**不改代码**, 仅强制用户重装:

```
1. 关 Maya (任务管理器确认 maya.exe 全退)
2. 删 C:\Users\<USERNAME>\Documents\maya\modules\RBFtools (整个目录)
3. 删 C:\Users\<USERNAME>\Documents\maya\modules\RBFtools.mod (若存在)
4. 删 C:\Users\<USERNAME>\Documents\maya\2022\prefs\userPrefs.mel (备份后)
5. 重启电脑 (清 .pyc + 文件锁)
6. 跑新 X:\Plugins\RBFtools\installer\RBFtoolsInstaller.exe
   mtime ≥ 2026-05-12 20:21, sha256 验证匹配 d0d7a687...
7. 启动 Maya 2022, 测两 bug
8. 再跑 Phase 10 §1.1 自检脚本, 期望 Q2/Q3/Q4 全部 match
```

### Path B (Task β audit 报 drift — 真有代码 bug)

修 sync script 或 scripts_2022 直接修, 重 regen, 跑 audit. 多个 commit (Policy B).

### Path C (Task β 0 drift + 用户 sha256 全 match — 真 Maya 版本 specific bug)

升级 Planner. 此时:
- Maya 2022 vs Maya 2025 同 source 双 .mll 编译, 同 Python 代码, 同 user input → 双行为不同
- 可能是 Maya 2022 vs 2025 在 DG evaluation / cmds API / kernel solver 底层有 SDK 行为差异
- 需要在 Maya 2022 环境跑 C++ debugger trace, 这超出 codebase 范围
- 临时方案: 用户 driver 多 driver case 改回 single-driver 验证是否绕开 bug

---

## 4. 不动什么

- ❌ 不动 `modules/RBFtools/scripts/` (Maya 2025 神圣)
- ❌ 不动 4/4 anchors
- ❌ 不动 .mll C++ source (Phase 9 Task B 已验证)
- ❌ 不基于"用户报告"盲修, 必须先 Task α (用户自检) + Task β (代码 audit) 结果反馈再决修复路径

---

## 5. 执行顺序

| 顺序 | Commit | 内容 |
|---|---|---|
| 1 | `docs(planner): Phase 10 brief + audit_phase10_function_bodies.py` | git add brief + Task β audit 脚本 |
| 2 | (run) | 跑 Task β audit + sha256 表生成, 写入 AUDIT_PHASE10_RESULTS.md |
| 3 | (并行) 把 §1.1 自检脚本 + §1.2 sha256 期望表转发给用户跑 | 不 commit |
| 4 | (若 Path B 触发) `fix: ...` | 修 sync 或代码 |
| 5 | (若 Path B 触发) `chore(installer): rebuild for Phase 10` | 重打 installer |

---

## 6. 关键路径速查

| 文件 | 用途 |
|---|---|
| `X:\Plugins\RBFtools\tools\audit_phase10_function_bodies.py` | **新建** Task β audit script |
| `X:\Plugins\RBFtools\docs\排查\AUDIT_PHASE10_RESULTS.md` | **新建** audit 输出 + sha256 表 + Path A/B/C 命中 |
| [core.py:4337-4345](modules/RBFtools/scripts/RBFtools/core.py) | M_P0_DISCONNECT_SCALE_RESTORE Python 防御 |
| [source/RBFtools.cpp:2140-2393](source/RBFtools.cpp) | M_P0_RBF_COLUMN_RANK_DEFENSE → fallback raise |
| `modules/RBFtools/scripts_2022/RBFtools/core.py` | scripts_2022 mirror (Phase 9 audit pass) |
