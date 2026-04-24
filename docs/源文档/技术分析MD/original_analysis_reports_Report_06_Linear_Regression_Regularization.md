# 第 6 份文件分析报告：Generalized Linear Regression with Regularization

## 1. 基础回归模型
定义特征向量 $\bar{x}^{(t)}$ 与标签 $y^{(t)}$ 之间的线性映射关系：$\bar{x}^{(t)} \cdot \bar{\theta} \approx y^{(t)}$。在 Rigging 中，x 是骨骼旋转，y 是辅助骨位移/缩放。

## 2. 损失函数与正则化 (Cost Function & Regularization)
为了防止过拟合，引入 **L2 正则化 (岭回归)**:
$$J(\bar{\theta}) = \frac{1}{n} \sum_{t=1}^{n} (y^{(t)} - (\bar{x}^{(t)})^T \bar{\theta} - \theta_o)^2 + \lambda \|\bar{\theta}\|^2$$
* **$\lambda$:** 控制平滑度。越大，生成的权重越趋向于 0，变形越平滑。
* **$	heta_o$:** 偏移量，确保在无驱动输入时回归到 Bind Pose。

## 3. 正则化正规方程
解析解公式：
$$(\frac{1}{n} X^T X + \lambda I) \bar{\theta} + (\frac{1}{n} X^T \bar{1}) \theta_o = \frac{1}{n} X^T \bar{y}$$
* **数值稳定性:** $+\lambda I$（Tikhonov Regularization）保证了矩阵始终可逆，从而确保 RBF 插件在极端姿态下不会崩溃。
