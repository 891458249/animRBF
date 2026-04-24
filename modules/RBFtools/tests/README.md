# RBFtools — Unit Tests

## 布局

- `test_m1_1_distance.py` — M1.1 距离计算规格测试（纯 Python, 无需 Maya）
- `_reference_impl.py` — C++ 侧距离辅助函数的 Python 镜像实现；
   作为 "数学规约" 存在，定义 C++ 侧须满足的行为。

## 运行

```bash
cd X:/Plugins/RBFtools
python -m pytest modules/RBFtools/tests/ -v
```

或

```bash
python -m unittest discover -s modules/RBFtools/tests/ -v
```

## 阶段性说明

- **M1.1（当前）**：仅纯数学规格测试，不触碰 Maya / C++ 插件。
- **M1.5**：补 `mayapy` headless 端到端集成测试，加载插件 + 构造已知 pose fixture
  + 对比 compute 输出，串通 C++ 实现与本目录定义的规约。
