# 第 7 份文件分析报告：Introduction to Radial Basis Function Networks

## 1. RBF 网络的线性本质
RBF 网络输出是基函数的线性组合：$f(\mathbf{x}) = \sum w_j h_j(\mathbf{x})$。
这种线性结构使得数学分析简单且计算开销低。权重可通过解析解直接求出。

## 2. 径向函数分类与特性
* **高斯核 (Gaussian):** 局部响应，仅在中心点附近有显著影响。适合模拟肌肉隆起。
* **多拟合核 (Multiquadric):** 全局响应。

## 3. 最优权重求解与正则化
* **岭回归 (Ridge Regression):** 对应统计学权重衰减，处理非良置问题。
* **GCV (广义交叉验证):** 用于预测误差的估计工具，帮助选择合适的正则化参数。
* **前向选择 (Forward Selection):** 启发式搜索过程，用于修剪不必要的骨骼节点或权重，平衡性能。
