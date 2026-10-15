# 界面草图与交互说明

任务卡：P02 ｜ 主责：ljj ｜ 分支：`docs/ui-flow`

本文只描述**界面长什么样、用户怎么操作、每一步由谁负责**。不包含实现代码，也不定义业务不变量——业务规则属于 `domain/`，用例编排属于 `application/`，存储属于 `infrastructure/`。三者以 `docs/design/contracts.md` 为准，本文件只引用，不另立标准。

## 1. 依据与边界

| 依据 | 位置 |
| --- | --- |
| 原始需求 | `Requests/日程管理系统.md`、`docs/requirements.md` |
| 架构与分工 | `.hermes/plans/2026-09-14_210248-sdms-team-architecture.md` |
| 界面契约草案 | 上述计划第 4 节「UI 交互契约」 |
| 工程与协作约束 | `AGENTS.md`、`GITHUB_COLLABORATION.md` |

### 1.1 技术选型（2026-10-14 答复确认）

| 项 | 结论 | 说明 |
| --- | --- | --- |
| GUI 框架 | **PySide6（Qt for Python）** | ljj 2026-10-14 答复：用 PySide，版本取当时最新稳定版，理由是原生控件的呈现效果明显好于 Tkinter |
| 存储 | **SQLite** | 同上答复：比 MySQL 轻量，不需要起服务进程；用标准库 `sqlite3`，不引入 ORM |

**版本策略。** `pyproject.toml` 声明 `PySide6>=6.11.2,<7.0`，实际版本由 `uv.lock` 锁定，取该区间内最新稳定版。截至 2026-10-14，PyPI 上最新稳定版为 **6.12.0**（2026-10-08 发布，要求 Python `>=3.10,<3.16`，本项目 3.12.x 在范围内）。版本锁一次，中途不随手升级；确实要升就走 PR 并说明原因。

**依赖合规。** PySide6 是第三方包，按 `AGENTS.md` 要求记录来源、版本与许可证：来源 PyPI（`pypi.org/project/PySide6`），许可证 `LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only`（本项目按 LGPL-3.0-only 条款使用）。**这也是选 PySide6 而不是 PyQt6 的原因**：两者 API 基本一致，但 PyQt6 在 GPL 之外需要商业授权，PySide6 是 Qt 官方绑定，条款更宽松。

**一个必须解决的合规点。** `Requests/日程管理系统.md` 的「文档」节明文要求：**「如果有用到第三方的包，放在 src 目录下的 lib 子目录下」**。这条比 `AGENTS.md` 的软性表述更硬。这不是理论担心——本机实测安装后 `PySide6` 包目录为 **646.7 MB**（含 Qt 运行库与可选组件，见 8.2 节实测记录），且其中的二进制扩展绑定平台：把 Windows 上装好的 Qt 运行库整包拷进 `src/lib/`，Linux 侧无法复用，提交包还会大到交不上去。处理办法见第 9 节 T-01，属于**必须有人拍板**的合规项，不能默认跳过。

**选型代价与回退。** 代价是 `dependencies` 不再为空，环境搭建多一步 `uv sync`，且 Windows / Linux 两端都要验证 `import PySide6` 与创建窗口成功。若后期因环境原因回退 Tkinter，本文的布局、状态机、交互规则与验收用例全部成立，只需替换控件类名——这也是把它们写在文档里而不是写在代码里的原因。

**日期控件不再自绘。** 原先「标准库 `calendar` + `ttk` 自绘月历」的方案建立在 `dependencies = []` 之上，该前提已经消失。Qt 自带 `QCalendarWidget`，跨月、闰年、周起始都由控件保证，`tkcalendar` 更无必要。见 5.1 节。

## 2. 图表清单

| 文件 | 内容 | 用途 |
| --- | --- | --- |
| `ui-wireframe-main.svg` | 主窗口线框：顶部 CRUD 工具栏、日历区、列表区、状态栏 | 设计文档「总体设计」章、PPT 界面章 |
| `ui-wireframe-form.svg` | 新增 / 修改共用表单线框，含日期选择浮层与后端结论提示 | 设计文档「详细设计」章 |
| `ui-wireframe-dialogs.svg` | 删除确认、错误提示、空状态三个对话框 | 设计文档「异常处理」章 |
| `ui-delete-flow-unselected.svg` | 「未选中 → 点击删除」状态变化 | 设计文档流程图、本文第 5 节 |
| `ui-delete-flow-confirm-cancel.svg` | 「选中 → 确认 → 取消」分支 | 设计文档流程图、本文第 5 节 |
| `ui-state-transitions.svg` | 界面四主状态与错误提示的转换总图 | 设计文档「状态设计」章 |

所有图均为 SVG 源文件，可直接插入 Word（Office 2016 及以上支持）。如需位图，由制作人在本机导出 PNG 后另存同名 `.png`，并在此表补注导出环境。

## 3. 总体布局

主窗口采用**顶部工具栏、左日历、右列表、底部状态栏**的四段式，见 `ui-wireframe-main.svg`。

| 区域 | Qt 控件 | 职责 |
| --- | --- | --- |
| ① 日历选择区 | `QCalendarWidget` | 显示月历、跨月前后缀日期（控件内建）、切换月份、回到今天、标记有日程的日期 |
| ② 当前日期条 | `QLabel` | 显示当前筛选日期与当天日程条数 |
| ③ 日程列表 | `QTableWidget` | 三列（时间 / 标题 / 备注），每行 `Qt.UserRole` 绑定 `schedule_id`，按时间、id 确定性排序 |
| ④ CRUD 工具栏 | `QToolBar` + `QPushButton` × 6 | 新增、查看、修改、删除、刷新、退出，**统一置于画布上侧** |
| ⑤ 状态栏 | `QStatusBar`（内含 `QLabel`） | 显示最近一次操作结果与当前选中项 |

控件列的 Qt 类名是「推荐实现」，不是契约本身；契约是每行的职责与第 5 节的行为。换用 `QTableView + QAbstractTableModel` 这类 Model/View 写法同样允许，只要③的行为不变。

四条布局约束：

- **操作按钮置于上侧**。新增、查看、修改、删除、刷新、退出统一放进顶部工具栏，不放在窗口底部。工具栏是用户的第一落点，位置固定才能形成肌肉记忆。
- **行标识与显示分离**。列表显示的是格式化文本，但每一行必须通过 `Qt.UserRole` 关联 `schedule_id`（UUID 文本）。禁止用行号或标题反查记录——标题可重复，行号会随排序变化。
- **首次启动显示当天**。空库也要有清晰的空状态，不能是一片空白让人以为程序坏了。
- **日历必须覆盖跨月与闰年**。`QCalendarWidget` 内建这两项能力（`setMinimumDate` 等不当设置才是唯一风险），但仍要目验一次（V-07）；周起始按国内习惯设为**周一**（`setFirstDayOfWeek(Qt.Monday)`），默认周日是 Qt 的原生行为，不改会让全组截图不一致。

## 4. 六个界面状态

草图覆盖计划要求的全部六个状态。

| 状态 | 触发 | 界面表现 | 对应草图 |
| --- | --- | --- | --- |
| 列表态 | 启动 / 切换日期 / 刷新 | ③ 显示当天全部日程，② 显示条数，⑤ 显示「就绪」 | 主窗口 |
| 日历态 | 点击月份箭头、日期格、今天 | ① 重绘当月网格，选中格高亮，有日程的日期带标记点 | 主窗口 ① |
| 表单态 | 点击「新增」或「修改」 | 弹出 `ui-wireframe-form.svg`，四个字段；日期可直接输入或点「选择」打开 `QCalendarWidget` 浮层 | 表单草图 |
| 确认态 | 选中后点击「删除」 | 模态对话框，说明将删除哪一条且不可撤销 | 对话框草图（左） |
| 错误态 | 后端返回校验或写入失败结论 | 提示后端给出的具体原因，并说明下一步能做什么，不暴露堆栈 | 对话框草图（中） |
| 空状态 | 所选日期无记录 | 列表区显示「暂无日程」与下一步引导，② 显示「共 0 条」 | 对话框草图（右） |

**表单只有一个。** 新增与修改共用 `schedule_form.py`，差别仅在窗口标题和是否预填。禁止复制一整套创建逻辑再复制一整套编辑逻辑——那是最容易让两处行为漂移的做法。

## 5. 交互规则

以下规则来自契约草案第 4 节，UI 侧必须遵守。每条都指向一项可以被单测或人工验证的行为。

### 5.1 日期与时间的输入

**界面不预先拦截用户的日期写法。** 它只做两件事：提供选择入口，把原始文本交给后端。

- **优先选，也允许写**。日期字段用 `QLineEdit`，旁边固定一个「选择」按钮，点开日历浮层（`ui/date_picker.py`，内部就是一个 `QCalendarWidget`），点选某天后回填标准格式文本；用户也可以直接在输入框里手写。两种入口地位对等，不因为提供了日历就禁用键盘输入。
- **不用 `QDateEdit` 当日日期框**。`QDateEdit` 会先按控件的显示格式做一次强校验，用户手写的 `2026/10/15`、`10月15日` 会被控件在提交前就拦掉，等于把「是否合法」的判断权拿回了界面层——这与下面的分工冲突。`QDateEdit` 只适合内部工具与其它不要求宽容输入的 Qt 场景。
- **主窗口日历不再自绘**。左侧①直接用 `QCalendarWidget`，`ui/date_picker.py` 只把它包成一个浮层小部件，两者共享同一个「有日程的日期如何标记」的绘制函数，不各自实现一遍月历算法。
- **宽容解析属于后端职责**。`2026/10/15`、`2026.10.15`、`10月15日` 这类写法的统一识别与转换是一条业务规则，放在后端的转换环节实现，界面不判断「格式对不对」，也不弹「日期格式不正确」。
- **界面的职责是呈现结论**。解析或校验失败时，显示的是**后端返回的原因**，而不是界面自己编的格式要求。字段级红框是后端结论的呈现方式，不是前端拦截的产物。
- 标准格式：日期 `YYYY-MM-DD`，时间 `HH:MM`，分钟精度，本地朴素时间，不处理时区。这是**回填与显示**用的格式，不是对用户输入的准入条件。
- 标题去首尾空白后非空；备注允许为空。这两条同样是后端判定的结论。

### 5.2 写入成功与失败

- **写入成功后**才刷新列表并提示成功。
- 写入失败时**保留表单与已填内容**，提示后端给出的失败原因。任何情况下不得假装成功。
- **异常处理的权威在后端**：是否合法、记录是否存在、存储是否可用，全部由服务层判定。界面不做平行判断，也不重复实现一遍校验规则，只把后端返回的结构化错误翻译成用户能读懂的句子。
- 只有可解释的预期错误（`ValidationError` / `ScheduleNotFound` / `StorageError`）被转换成用户提示；意外异常记录诊断信息并给通用提示，不静默吞掉，也不把裸堆栈甩给用户。
- 注意边界：服务层**不能弹窗**。后端负责「判定并抛出」，界面负责「捕获并呈现」，两者缺一不可。把异常「交给后端」不等于界面不显示错误。

### 5.3 删除的两条路径

这是本轮最容易写错的地方，两张流程图就是为它画的。

**未选中时点击删除**（`ui-delete-flow-unselected.svg`）：controller 读到 `selected is None`，就地提示「请先选择一条日程」并返回。**整条链路零次服务调用**——未选中是界面状态问题，不是业务错误，不应当产生一条 `ScheduleNotFound`。

**选中后点击删除**（`ui-delete-flow-confirm-cancel.svg`）：

- 确认框弹出时**服务尚未被调用**。
- 点「取消」→ 对话框关闭，列表与数据不变，`service.delete` 一次都不调用。
- 点「确定」→ 才调用 `service.delete(schedule_id)`；记录是否存在由服务层校验，UI 不替它判断。
- 成功 → 刷新列表；失败 → 提示并保留原状。

删除确认属于**交互策略**，不能替代服务层的有效性校验。即便 UI 已经确认过，服务内部仍要处理记录不存在的情况。

### 5.4 选中与切换

- 无选中项时点击「修改」或「删除」，提示先选择日程，**不把 `None` 传给服务**。
- 切换筛选日期后清空选中项并刷新列表。
- 修改日期后，被修改的记录从当前列表移出是**正常行为**，不是 bug；此时刷新当前筛选日期即可。

## 6. 人工 GUI 验收步骤

自动化测不到的部分由人工验证。每条记录：操作系统版本、Python 版本、**PySide6 与 Qt 版本**（`python -c "import PySide6, PySide6.QtCore; print(PySide6.__version__, PySide6.QtCore.qVersion())"`）、前置数据、操作步骤、预期结果、实际结果、截图路径（存 `docs/screenshots/`）。截图只用虚构日程，不要把个人真实安排写进提交材料。

采用 PySide6 后，**必须在 Windows 与 Linux 两台机器上各跑一遍完整清单**。Qt 是跨平台的，但字体度量与控件默认尺寸在两平台上不完全一致（例如同样 12 磅字，Linux 下中文行高可能更大），只在一端验过不能算通过。

| 编号 | 需求 | 步骤 | 预期 |
| --- | --- | --- | --- |
| V-01 | F-01 | 启动程序 | 窗口正常显示，默认选中当天，列表与顶部工具栏齐全 |
| V-02 | F-02 | 填写完整字段后保存 | 提示成功，列表立即出现该条，表单关闭 |
| V-03 | F-02 | 标题只输入空格后保存 | 给出字段级提示，不写入，已填内容保留 |
| V-04 | F-02 | 日期填 `2026/10/15` 后保存 | 后端宽容解析为 `2026-10-15` 并保存成功，界面不报格式错误 |
| V-05 | F-03 | 选择另一天 | 列表只显示当天日程，条数与标题栏一致 |
| V-06 | F-03 | 选择无任何日程的日期 | 显示空状态与「共 0 条」，不是空白或报错 |
| V-07 | F-01 | 在日历上跨月翻页，并定位到 2028-02 | 跨月前后缀日期灰显且不可选为本月；2028 年 2 月有 29 天 |
| V-08 | F-04 | 选中一条点「修改」，改标题后保存 | 列表更新，`schedule_id` 不变 |
| V-09 | F-04 | 修改日期为另一天 | 保存后该条从当前列表移出，切到新日期可见 |
| V-10 | F-05 | 未选中任何行点「删除」 | 提示先选择日程，**服务未被调用**，数据不变 |
| V-11 | F-05 | 选中后点「删除」，在确认框点「取消」 | 对话框关闭，列表与数据完全不变 |
| V-12 | F-05 | 选中后点「删除」，点「确定」 | 该条消失，条数减一 |
| V-13 | F-06 | 连续快速点击按钮、重复删除同一条 | 给出可理解提示，不出现裸堆栈，程序仍可继续操作 |
| V-14 | 工程增强 | 新增若干条后退出程序，重新启动 | 数据仍在，说明持久化生效 |
| V-15 | F-02 | 点日期旁「选择」打开日历浮层，点选某天 | 浮层关闭，日期框回填为标准格式文本，可继续编辑 |
| V-16 | F-02 | 日期填完全无法识别的内容（如 `明天`）后保存 | 显示后端返回的原因，已填内容保留，可改后重试 |
| V-17 | 工程增强 | Windows 与 Linux 各一次：`uv sync` 后启动程序 | 两端都能 `import PySide6`、主窗口显示无文字截断、日历周一开头一致，版本号记录到 screenshots 附录 |

V-10 与 V-11 是界面层的**核心断言**，必须用测试替身验证「服务调用次数为 0」，不能只靠肉眼看列表没变。V-04 与 V-16 是一组对照：**同一个字段，能识别的写法直接通过，不能识别的才报错**——两条都要跑，才能证明界面确实没有在前端先行拦截。

## 7. 与实现文件的映射

后续 P09、P10 落地时，本文各节对应到这些文件。P09 的四个非 GUI 模块已于 2026-10-15 落地（详见第 10 节），下表标注了各自的当前状态：

| 文件（未来路径） | 主要 Qt 类型 | 承接本文 | 状态 |
| --- | --- | --- | --- |
| `ui/view_models.py` | （无控件，纯数据） | 行模型、表单草稿与打开表单的上下文 | 已落地 |
| `ui/ports.py` | （无控件，Protocol） | 界面与外部世界的三个端口 | 已落地 |
| `ui/presenters.py` | （无控件，纯函数） | 显示格式化、条数文案、错误到提示的映射 | 已落地 |
| `ui/controller.py` | （无控件，纯协调） | 第 5 节全部：选中态、调用用例、错误转提示 | 已落地 |
| `ui/app.py` | `QApplication`、`QMainWindow`、`QToolBar`、`QStatusBar` | 第 3 节布局与事件接线；进程唯一的 `QApplication` 实例在本模块的 `main()` 中创建 | P10 |
| `ui/calendar_view.py` | `QCalendarWidget` | 第 3 节 ①，含标记绘制与周一起始 | P10 |
| `ui/date_picker.py` | `QCalendarWidget` 包一层浮层 | 第 5.1 节日期选择浮层；与 `calendar_view.py` 共用同一个「日期标记」绘制函数 | P10 |
| `ui/schedule_form.py` | `QDialog`、`QLineEdit`、`QTextEdit` | 第 4 节表单态，新增与修改共用 | P10 |

分层约束（违反即视为设计错误）：`ui` 不 import `sqlite3`，不拼 SQL；**领域层不 import `PySide6`**（也不 import `tkinter`——换框架不改这条）；服务层不弹窗；**模块导入时不得创建 `QApplication`、不得弹窗、不得连接数据库**（这是 CI 里最容易踩的一条：pytest 收集阶段一旦触发窗口创建，在没有显示服务的 Linux 上会直接挂）。

`QApplication` 只允许在 `ui/app.py` 的 `main()` 里出现一次。写成模块级 `app = QApplication([])` 会污染导入，也会让未来的 GUI 测试无法自行管理事件循环。

## 8. 审查意见处理记录

PR #5 审查（zch，2026-10-14）提出三条意见，处理如下。

| 意见 | 处理 | 落在哪 |
| --- | --- | --- |
| 日期不应弹「格式不正确」，应提供可交互日历供选择；用户也可输入，由后端写转换算法无感转成可用格式，不在前端拦截 | 采纳。表单新增日历浮层与「选择」按钮；删除「日期格式不正确」提示；把宽容解析明确划归后端；`ui-interaction.md` 第 5.1 节重写 | `ui-wireframe-form.svg`、`ui-wireframe-dialogs.svg`、本文第 5.1 节 |
| 新增、查看、修改、删除、刷新、退出等按钮放在画布上侧 | 采纳。六个按钮移入顶部工具栏，布局由三段式改为四段式 | `ui-wireframe-main.svg`、本文第 3 节 |
| 异常处理需交给后端，而不是仅前端弹一个红框 | 采纳并补一条边界说明：判定权威在后端，界面只负责呈现后端结论；同时明确服务层不弹窗，因此界面必须保留捕获与呈现的职责 | `ui-wireframe-form.svg`、`ui-wireframe-dialogs.svg`、本文第 5.1、5.2 节 |

第 5.1 节原表述「界面负责把字符串解析成 `date` / `time`」已按意见修订为**解析规则归后端**，界面只提供选择入口与呈现结论。这条修订会影响 P09 的职责划分，需在契约中同步体现。

### 8.1 待确认项答复（ljj，2026-10-14）

第 9 节原待确认项的前两项已由 ljj 答复确认，本文据此修订：

| 原待确认项 | 答复 | 本文的连带修订 |
| --- | --- | --- |
| GUI 框架选型 | **PySide6**，版本取当时最新稳定版，理由是呈现效果更好 | 新增 1.1 节；第 3 节控件列与图注改为 Qt 类名；5.1 节日期浮层改用 `QCalendarWidget`；第 7 节补 Qt 类型与 `QApplication` 约束；新增 V-17 |
| 存储 | **SQLite**（标准库 `sqlite3`） | 1.1 节记录；UI 侧无直接依赖，`ui` 仍不得 import `sqlite3`；V-14 持久化验收继续有效 |
| 其余细节项 | 暂定，不追求一次到位，属细节打磨，后续统一调整 | 见第 9 节，全部标注为「暂定」 |

**一处连带收益**：原先「自绘月历」的唯一理由是绕开第三方依赖，PySide6 引入后该理由消失，主窗口月历与日期浮层都用 `QCalendarWidget`，第 7 节里那个“`calendar_view` 与 `date_picker` 共用日历网格”的自绘模块不再需要。少一块自写代码，跨平台与闰年也由 Qt 保证。

### 8.2 PySide6 环境实测（2026-10-15，Windows）

不是"应该能用"，是**真的装起来跑过**。命令：`uv run --python 3.12 --with PySide6 python scripts/qt_probe.py`（脚本已入库；Linux 无显示环境时前置 `QT_QPA_PLATFORM=offscreen`）。

| 探测项 | 实测结果 | 对应本文的哪条结论 |
| --- | --- | --- |
| PySide6 / Qt 版本 | **6.12.0 / 6.12.0** | 1.1 节版本策略；与 PyPI 上 2026-10-08 发布的最新稳定版一致 |
| 包目录体积 | **646.7 MB** | T-01 不能整包入库的定量依据 |
| 周起始可设为周一 | 是（`setFirstDayOfWeek(Qt.Monday)` 后读回确为 `DayOfWeek.Monday`） | 3 节第四条约束 |
| 闰年 | 2028-02 为 29 天，可选中 `2028-02-29` | **V-07 的闰年部分已被机器验证**，不用等到人工验收才发现日历少一天 |
| 列表列数 | `QTableWidget` 三列建立正常 | 3 节 ③ |
| 日期框宽容性 | `QLineEdit` 原样接受 `2026/10/15` | 5.1 节"不用 `QDateEdit`"的选择有了实测支撑 |
| `QDateEdit` 显示格式 | `yyyy-MM-dd` | 同上：它会按该格式先行强校验，所以不当日期框 |

两条从这次实测里得出的结论：

1. **V-07 的闰年分支降级为半自动**。翻页与跨月灰显仍要人眼看着截图确认，但"2028 年 2 月有 29 天、且能被选中"已经由探测脚本断言过。
2. **V-17 的 Linux 侧仍然必做**。Windows 侧能跑不代表 Linux 侧能跑：`QApplication` 在没有显示服务的环境里会直接失败（探测脚本因此需要 `QT_QPA_PLATFORM=offscreen`），这一条正好是第 7 节那条"导入期不得创建窗口"的现实来源。

## 9. 暂定项（不影响开工）

GUI 框架与存储已于 2026-10-14 定稿（见 1.1 节与 8.1 节），不再列入待确认。剩余各项按 ljj 意见**暂定**：先按下面的默认值开工，不阻塞 P09；等在 M0 冻结或打磨阶段一次性统一调整。

| 编号 | 暂定项 | 暂定值 | 由谁、何时拍板 |
| --- | --- | --- | --- |
| T-01 | **第三方包如何满足「放 `src/lib/`」的课程要求**（合规项，非风格问题） | 暂按：`src/lib/README.md` 写明来源、版本、许可证与安装命令，附依赖清单；不把二进制整包入库（**实测依据：包目录 646.7 MB 且绑定平台**，见 8.2 节） | zch 在 M0 冻结前向任课教师确认。若坚持整包入库，需另议（体积与跨平台见 1.1 节） |
| T-02 | 后端宽容解析的支持范围 | 支持 `2026/10/15`、`2026.10.15`、`2026-10-15` 等分隔符差异；**不支持** `明天`、`下周三` 一类相对日期 | zch 在写 `contracts.md` 时给出清单，界面不设限，需写进契约以便验收（V-04、V-16） |
| T-03 | 数据库文件位置 | 跨平台用户数据目录下的 `sdms/schedules.db`，不依赖运行时当前工作目录；测试始终注入临时路径 | xhy 在基础设施落地时确定，UI 只消费路径，不参与决定 |
| T-04 | 字段长度上限 | 标题 100 字符，备注 500 字符；超限的行为与提示文案由后端返回 | 三人确认后写入契约，不冒充课程规定 |

T-02 与 T-04 会影响 V-03、V-04、V-16 的预期文案，拍板后回来改这三行的「预期」列即可，不动流程。

## 10. P09 落地说明（2026-10-15）

界面层**不依赖任何 GUI 运行库**的那部分已经写完并通过测试。这一节记录它落在哪些文件、和草案差在哪、以及哪些验收项从「人工点头」升级成了「机器断言」。

### 10.1 已落地与尚未落地的文件

| 文件 | 状态 | 内容 |
| --- | --- | --- |
| `src/schedule_management/ui/view_models.py` | 已落地 | `ScheduleRow`、`ScheduleDraft`、`FormRequest` 三个纯数据信封 |
| `src/schedule_management/ui/ports.py` | 已落地 | 三个端口协议：`ScheduleLike`、`ScheduleServicePort`、`MainViewPort` |
| `src/schedule_management/ui/presenters.py` | 已落地 | 纯函数：格式化、条数文案、错误到提示的映射 |
| `src/schedule_management/ui/controller.py` | 已落地 | 选中态、筛选日期、六类操作的服务调用与错误呈现 |
| `tests/unit/ui_fakes.py` | 已落地 | UI 自己的测试替身：假服务（记录调用）+ 假窗口（记录输出） |
| `tests/unit/test_presenters.py` | 已落地 | 文案与错误映射的穷举 |
| `tests/unit/test_controller.py` | 已落地 | V-01~V-16 中可自动化部分的断言，重点是调用次数 |
| `tests/unit/test_ui_layering.py` | 已落地 | 用 AST 扫描源码，禁止 `ui` 包 import `PySide6` / `tkinter` / `sqlite3` |
| `ui/app.py`、`calendar_view.py`、`date_picker.py`、`schedule_form.py` | **未落地** | P10，需要先把 PySide6 装起来（T-01 定论后才能动） |

**为什么 `controller.py` 与 `presenters.py` 不许碰 Qt。** 这两块是全部交互规则所在地，一旦 import 了 `PySide6`，在没有显示服务的 Linux 上 pytest 收集阶段就会挂掉。第 7 节那条约束现在有测试兜底了：谁手滑 import 了 Qt，`tests/unit/test_ui_layering.py` 会直接失败，并且报错信息会写清原因。

### 10.2 三个端口（界面层唯一的对外依赖方式）

| 端口 | 谁来实现 | 界面拿它干什么 |
| --- | --- | --- |
| `ScheduleLike` | 领域层的 `Schedule` 只要具备 `id / title / date / time / notes` 五个属性即可 | `presenters` 把它转成列表行，不需要 import 领域类 |
| `ScheduleServicePort` | 由 zch 的 `application/service.py` 落地；在此之前用 `ui_fakes.FakeScheduleService` | 四个用例：`list / create / update / delete` |
| `MainViewPort` | 由 P10 的窗口代码适配 | 九个单向输出 + 两个提问（`ask_delete_confirm`、`open_schedule_form`） |

全部用 `typing.Protocol` 的**结构性类型**：真实现换进来时 controller 不用改一行，`mypy` 负责证明它对得上（`mypy src tests` 当前全绿，说明替身与协议是严格匹配的，不是"跑得通就算"）。

### 10.3 与契约草案的唯一偏差：create / update 收原始字符串

计划第 4 节写的是「create/update 的 `day` 与 `at` 已经是日期/时间对象；GUI 字符串解析在 controller」。**这句话已经被 zch 在 PR #5 的第 1 条意见改写**：日期由用户手写或日历点选，统一交给后端的转换算法处理，界面不做准入检查。因此端口签名为：

```text
list_schedules(day: date) -> Sequence[ScheduleLike]
create_schedule(title: str, date_text: str, time_text: str, notes: str) -> ScheduleLike
update_schedule(schedule_id: str, title: str, date_text: str, time_text: str, notes: str) -> ScheduleLike
delete_schedule(schedule_id: str) -> None
```

`list_schedules` 仍然收 `date`：这个值来自日历控件的点选结果，本身就不是自由文本，不涉及"宽容解析"。

**这条偏差必须写进 `docs/design/contracts.md` 才算定稿**，否则 zch 按原草案写出 `day: dt.date` 的签名，两边就对不上了。

另一个关联决定：`presenters.error_category` 目前按**异常类名**判定而不是 `isinstance`，因为 `domain/errors.py` 与 `application/errors.py` 还没落地，界面不能在导入期依赖它们。`tests/unit/ui_fakes.py` 里的三个假异常类特意与契约同名（`ValidationError` / `ScheduleNotFound` / `StorageError`），就是为了覆盖到这条路径。真异常类可用后，把该函数体换成 `isinstance` 判定即可，调用方无需改动。

### 10.4 哪些验收项从人工升级成了机器断言

| 编号 | 断言位置 | 断言内容 |
| --- | --- | --- |
| V-01 / V-06 | `test_start_shows_today_rows_with_count`、`test_start_on_empty_database_...` | 启动即查当天；空库走空状态分支而不是白板 |
| V-05 | `test_switching_day_reloads_and_clears_selection` | 换日期重查并清空选中 |
| **V-10** | `test_delete_without_selection_never_calls_service` | **`delete` 调用 0 次**，只出一条提醒，且不进错误区 |
| **V-11** | `test_delete_cancelled_confirmation_never_calls_service` | **确认框取消后 `delete` 调用 0 次**，数据一字节未改 |
| V-12 | `test_delete_with_cancel_still_calls_service_once_when_confirmed` | 点确定才调一次，参数是 `schedule_id` 而不是标题或行号 |
| V-04 / V-16 | `test_create_forwards_raw_date_text_without_parsing`、`test_create_forwards_unrecognizable_...` | 对照组：`2026/10/15` 与 `明天` **都原样抵达服务**；失败时显示后端原因，标题不是「日期格式不正确」 |
| V-02（失败分支） | `test_failed_save_reopens_form_with_previous_values` | 写入失败重开表单，`initial` 必须是上一次的草稿 |
| V-08 / V-09 | `test_edit_prefills_from_row_and_calls_update_with_id`、`test_updated_row_can_leave_current_day_list` | 按 id 修改；改到别的日期后当前列表变短是正常的 |
| V-13（部分） | `test_unexpected_exception_gives_generic_hint_only`、`test_failed_refresh_keeps_last_good_rows` | 未预期异常只给通用提示且不泄露技术细节；刷新失败保留上一次的数据 |
| F-06（部分） | `test_storage_error_points_at_the_data_file` | 存储类错误指向数据文件并给出下一步 |

跑法：`uv run pytest tests/unit -v`；类型验证：`uv run mypy src tests`（当前 11 个文件全绿）。其余带界面外观的部分（V-07 跨月闰年、V-15 浮层回填、V-17 双平台）只能留在 P10 之后人工验收。
