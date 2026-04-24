**4.1.0 (2026-04-07)**

* Full UI refactor with PySide2/Qt MVC architecture.
完整的 UI 重构，采用 PySide2/Qt MVC 架构。
* Added bilingual UI support (English / Chinese).
新增中英双语界面支持。
* Added "?" help buttons with dynamic per-option tooltip for all controls.
为所有控件添加带动态选项说明的"?"帮助按钮。
* Separated Apply (data write) from Connect (attribute wiring).
分离了应用（写入数据）和连接（属性连线）功能。
* Added Disconnect button with unitConversion node cleanup.
新增断开按钮，支持自动清理 unitConversion 节点。
* RBF mode hides Icon Size (not applicable without locator).
RBF 模式下隐藏图标大小。

**4.0.1 (2026-03-28)**

* Fixed that poses don't produce a full output weight with the RBF mode set to Matrix.
修复了 RBF 模式设为 Matrix 时姿态未产生完整输出权重的问题。
* Fixed a vector angle weight output error.
修复了向量角度权重输出错误。

**4.0.0 (2026-03-21)**

* RBF algorithm update. This breaks compatibility with previous versions.
RBF 算法更新，与之前版本不兼容。
* Only Maya 2022 supported.
仅支持 Maya 2022。
* Added new kernel types and radius options.
新增核函数类型和半径选项。
* Removed the bias value.
移除了偏置值。
* Improved error message in case of a calculation error.
改进了计算错误时的错误提示。

**3.6.2 (2026-03-14)**

* Initial fork and project setup.
初始分支和项目搭建。
* Added support for Maya 2022 compilation with CMake.
新增 Maya 2022 CMake 编译支持。

**3.6.1 (2026-03-07)**

* Project started.
项目启动。
* Fixed the loss of stored data in generic mode after the Active checkbox has been toggled.
修复了在通用模式下切换启用复选框后存储数据丢失的问题。

