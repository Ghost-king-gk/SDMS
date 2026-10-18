"""图形界面包。

本包只放两样东西：**不含控件的纯逻辑**（controller、presenters、端口与视图模型）
和**已经落地的 Qt 窗口代码**（app.py 等）。两者的分界线写在
`docs/figures/ui-interaction.md` 第 7 节，核心约定是：

- controller 与 presenters 不得 import `PySide6`，也不得 import `tkinter`——
  它们必须能在没有显示服务的机器上被 pytest 直接运行；
- `QApplication` 只能出现在窗口模块的 `main()` 里，任何模块的导入期
  都不得创建窗口（`controller` 与 `presenters` 因此天然安全）；
- 本包不 import `sqlite3`，不拼 SQL，不重复实现业务校验。

界面下方的领域规则、用例编排与持久化分别属于 `domain/`、`application/`
与 `infrastructure/`，本包通过 `ports.py` 里的结构性协议消费它们。
"""

from __future__ import annotations
