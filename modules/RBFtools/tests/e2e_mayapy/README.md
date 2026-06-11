# e2e_mayapy — 真实 Maya 端到端验证脚本

这些脚本在 **mayapy**（Maya 自带 Python 解释器）下运行, 加载真实
`.mll` 做端到端验证 — 与 `modules/RBFtools/tests/` 下的纯 Python
sweep 互补 (后者 mock 了 `maya.cmds`, 无法发现 setAttr 语义、.ma
序列化、DG compute 这一类只在真实 Maya 中出现的问题).

文件名用 `e2e_` 前缀 (非 `test_`), pytest 不会收集; 退出码 0 = 全部
PASS.

## 运行

```bash
# Maya 2025
"C:/Program Files/Autodesk/Maya2025/bin/mayapy.exe" \
    e2e_phase16_roundtrip.py \
    X:/Plugins/RBFtools/modules/RBFtools/plug-ins/win64/2025/RBFtools.mll

# Maya 2022 (同脚本, 换 mayapy + .mll 路径)
"C:/Program Files/Autodesk/Maya2022/bin/mayapy.exe" \
    e2e_phase17_engine.py \
    X:/Plugins/RBFtools/modules/RBFtools/plug-ins/win64/2022/RBFtools.mll
```

## 覆盖

| 脚本 | 场景 |
|---|---|
| `e2e_phase16_roundtrip.py` | A backward-compat 默认值 + 无 .ma 污染; B 设 parent/mask → save → reopen → 字段保真 (11 checks) |
| `e2e_phase17_engine.py` | C sibling mask warn; G 加性 delta 凸混合 + far-driver anti-leak; E 乘性 scale delta (PHASE17a); D so(3) quat delta + 单位范数 + anti-leak (PHASE17b); H mask-only driver 投影; A 普通 rig 回归 (14 checks) |

## 历史战绩

2026-05-28 首跑即抓到两个纯 Python sweep 永远抓不到的 bug:
1. `M_P0_INT32ARRAY_SETATTR_FIX` — Maya Python setAttr 的 Int32Array
   不接受 MEL count-prefix 形式, 静默存错数据.
2. `M_P0_HIERARCHICAL_ENGINE_EXACT` Bug A — 分层推理的 Base_Output
   误用全 pose legacy 网络, quat 通道 delta 渗漏 + 加性通道双重计入
   (被 Output Clamp 掩盖).
