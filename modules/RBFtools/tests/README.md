# RBFtools — Unit Tests

## 布局

| 文件 | 覆盖 |
|---|---|
| `_reference_impl.py` | C++ 辅助函数的 Python 镜像实现；作为数学规约存在，定义 C++ 侧须满足的行为 |
| `test_m1_1_distance.py` | M1.1 — Matrix 模式 twist wrap-aware L2 距离 + `getQuatDistance` 预留规约 |
| `test_m1_2_baseline.py` | M1.2 — Output Base Value + `outputIsScale` + dirty tracker + scale 保护 |
| `test_m1_3_clamp.py` | M1.3 — Driver Clamp（per-dim bounding box + inflation）+ Matrix twist 跳过 + 缓存生命周期 + 防御分支 |
| `test_m1_4_solver.py` | M1.4 — Tikhonov 绝对 λI + Cholesky/GE 两层 fallback + solver-tier 缓存 |

## 运行（双环境支持）

`conftest.py` 自动检测当前环境：

| 环境 | 命令 | 用途 | 用时 |
|---|---|---|---|
| **纯 Python** | `python -m unittest discover -s modules/RBFtools/tests/` | 开发期快速反馈（mock 框架） | ~0.4 s |
| **mayapy 2025** | `"/c/Program Files/Autodesk/Maya2025/bin/mayapy.exe" -m unittest discover -s modules/RBFtools/tests/` | 完整集成验证（真 Maya / PySide6） | ~5 s |

或：

```bash
python -m pytest modules/RBFtools/tests/ -v
```

`conftest.py` 通过 `_REAL_MAYA` 检测（`sys.executable` basename 起始 `mayapy` + `import maya.cmds` 探针双条件）决定是否安装 mock 框架。永久守护 **T_CONFTEST_DUAL_ENV** (#17) 锁定该契约。

mayapy 下少量测试因依赖 mock 行为（`cmds.reset_mock()` / `mock.patch` on `cmds.*`）而 class-level `skipIf(_REAL_MAYA, ...)`。这是设计选择，**不是缺陷**——纯 Python 测试覆盖算法层；mayapy 测试覆盖集成层。

### ⚠ Maya 版本兼容 caveat

**当前双环境支持仅在 Maya 2025 + Python 3.11.4 + PySide6 6.5.3 下验证**。

- ✅ Maya 2025（Python 3.11 + PySide6）
- ❌ Maya 2022（Python 3.7 + PySide2）—— **不在本次 scope**，推 M5 / 长尾兼容
- ❌ 其他 Maya 版本 —— 未测试

在 Maya 2022 下跑 mayapy 测试预期会因 PySide2 vs PySide6 API 差异 fail；用户应假定 mayapy 测试只在 Maya 2025 通过。详见 addendum §M1.5-conftest 顶部 caveat block。

## 依赖

- Python ≥ 3.7（`math.isclose`、`random`、`unittest` 来自 stdlib）
- `numpy` 2.x（M1.2 的减-加回恒等、M1.4 的 Cholesky / λI / dispatcher 规约测试均用 numpy）
- **Maya 2025**（仅 mayapy 集成验证时需要；纯 Python 路径无依赖）

## Milestone 1 测试分布（总 76 条，全绿）

| Milestone | 文件 | 测试类 × 子测试 | 小计 |
|---|---|---|---|
| **M1.1** | `test_m1_1_distance.py` | T1 轴向量角（4）· T2 twist seam 回归（4）· T3 多驱动块独立 + L2 聚合（2）· T4 L2 尺度非回归（1）· T5 `getQuatDistance` 规约（3） | **14** |
| **M1.2** | `test_m1_2_baseline.py` | T1 `_is_scale_attr`（3）· T2 减-加回恒等（2）· T3 scale 通道保护（3）· T4 捕获优先级（4）· T5 dirty tracker 触发重解（6） | **18** |
| **M1.3** | `test_m1_3_clamp.py` | T1 `compute_bounds`（4）· T2 标量 clamp（4）· T3 inflation 语义（3）· T4 Matrix twist passthrough（2）· T5 边界内恒等（1）· T6 退化 pose（2）· T7 Matrix xyz+twist 同向量（1）· T8 缓存生命周期（2）· T9 空/长度不匹配防御（2） | **21** |
| **M1.4** | `test_m1_4_solver.py` | T1 Cholesky 基础（3）· T2 非 SPD 检测（3）· T3 绝对 λ 非自适应（3）· T4 λ 恒等/扰动（2）· T5 dispatcher + ForceGE + sticky 缓存（4）· T6 Thin Plate 正则化门（3）· T7 多 RHS 等价（1）· T8 退化近重复 pose（1）· T9 `solverMethod` 变化重置缓存（3） | **23** |
| 合计 | | | **76** |

## C++ 集成测试（推迟）

当前测试全部为**纯 Python 数学规约**，不加载 Maya / 不编译 C++。定义 C++ 实现须满足的行为契约；当 C++ 改动时，若规约仍通过，即表示 C++ 与规约达成一致。

**C++ 端到端集成测试**（`mayapy` headless + 真实 `RBFtools` 节点 + 已知 pose fixture + compute 输出对比）**推迟到 M1.5**，触发条件：Maya 2024/2025 devkit 与 `mayapy` 可用的构建环境就位。届时一次性覆盖 M1.1–M1.4 的全部 C++ 路径，并验证 Python 规约与 C++ 实测结果一致。

## Addendum 参考

所有实施决议与规约契约详见：

```
docs/设计文档/RBFtools_v5_addendum_20260424.md
```

- §M1.1 twist wrap-aware 距离
- §M1.2 Output Base Value + outputIsScale
- §M1.3 Driver Clamp
- §M1.4 Regularized Solver + Cholesky/GE fallback
- §M4.5 （前瞻）Eigen 引入 + 完整四层 fallback chain
