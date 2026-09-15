# SDMS 日程管理系统：架构与三人实践实施计划

**目标：** 在不提前代写业务代码的前提下，建立可解释、可测试、可协作的 Python 图形化日程管理系统设计与练习路线。

**架构：** 轻量分层单体。领域层定义有效日程，应用层编排用例，界面与存储作为外部适配器；仅在确有替换和测试需求的存储边界使用 Protocol，不建立通用框架。

**技术栈建议：** Python 3.12、uv、Tkinter/ttk、datetime、calendar、sqlite3、dataclasses、typing.Protocol；开发工具沿用 pytest、pytest-cov、Ruff、mypy。GUI 与持久化选型为待团队确认的建议，不是既成实现。

## 1. 已确认的上下文与操作边界

- 来源：https://github.com/Ghost-king-gk/SDMS。
- 本地目录：/home/ghost/repos/Python-Lab-SDMS。
- 已克隆 main，检查时 HEAD 为 07ed7ea，克隆后工作区干净。
- 仓库此前已初始化工程骨架；不需要再次 git init，不需要覆盖原有配置。
- 本轮只获取源码、阅读资料、保存本计划。没有业务实现、提交、推送、远程任务分配或依赖安装。
- 本轮不宣称 Python 虚拟环境、GUI 或测试已验证。环境初始化安排在 M0。
- 需求依据：Requests/日程管理系统.md:9-16、27-38；整理基线 docs/requirements.md；工程约束 AGENTS.md；协作约束 GITHUB_COLLABORATION.md。
- 原始 PDF 本轮未另行比对；如教师补充要求或 PDF 与 Markdown 不一致，先核对再冻结验收基线。Requests/ 保持只读。
- 团队：zch（本人，组长）、ljj、xhy。尚不知道成员熟练度和截止日期；按职责互补分工，不假定某人更弱，不承诺未经确认的工期。

## 2. 范围分级

### 必须完成：课程要求

F-01 图形界面、日程列表、日历选择、操作按钮。
F-02 新增标题、日期、时间、备注。
F-03 按选择日期查看当天全部日程。
F-04 修改选中日程。
F-05 安全准确地删除选中日程。
F-06 非法输入、无选中项、存储异常均给出友好提示。

### 建议纳入基础交付的工程增强

SQLite 本地持久化、重启后可恢复；稳定 ID；统一排序；失败不丢失旧数据；可复现工具链。持久化是本方案建议，不把它冒充原始硬性需求。

### 暂不实现

账号登录、网络后端、云同步、多人实时编辑、提醒推送、重复日程、复杂时区、微服务、ORM、插件系统。先完成可用闭环，再讨论增强。

## 3. 层级不是文件夹数量，而是依赖规则

```text
用户
  ↓ 操作 / ↑ 提示
界面层 ui                 ljj：窗口、表单、日历、选择、确认
  ↓ 调用用例
应用层 application        zch：新增/查询/修改/删除的流程与存储契约
  ↓ 使用领域对象
领域层 domain             zch：日程含义、有效性、不变量

存储适配器 infrastructure xhy：实现应用层定义的存储契约
启动装配 bootstrap        zch：创建 SQLite 存储、服务和界面
```

静态依赖：ui → application → domain；infrastructure → application 中的契约与 domain；bootstrap 了解具体对象并注入依赖。

运行时：界面调用服务，服务通过传入的存储对象执行读写。运行调用方向不等于源代码 import 方向。

禁止：领域层导入 Tkinter/SQLite；服务直接弹窗；按钮回调拼 SQL；存储层决定界面文案；模块导入时创建窗口或数据库；以全局可变列表共享状态。

只在真正的边界抽象：一个 ScheduleRepository Protocol 足够。无需每个类都有抽象基类，也无需“通用 CRUD 框架”、依赖注入容器或单独 UnitOfWork 框架。

### 建议文件地图（全部为未来路径，不在本轮创建）

```text
src/schedule_management/
  __init__.py
  __main__.py                  启动入口；不承载业务
  bootstrap.py                 唯一装配点、资源关闭
  domain/
    __init__.py
    schedule.py                Schedule 与业务不变量
    errors.py                  ValidationError 等领域错误
  application/
    __init__.py
    contracts.py               ScheduleRepository Protocol
    errors.py                  ScheduleNotFound / StorageError
    service.py                 ScheduleService 与四类用例
  infrastructure/
    __init__.py
    sqlite_repository.py       参数化 SQL、事务、序列化、连接管理
  ui/
    __init__.py
    app.py                     主窗口与事件接线
    controller.py              输入解析、用例调用、错误转提示
    schedule_form.py           新增/编辑共用表单
    calendar_view.py           calendar 生成日期网格，ttk 呈现
    presenters.py              显示格式与提示映射，尽量纯函数

tests/
  unit/test_schedule.py
  unit/test_service.py
  unit/test_controller.py
  unit/test_presenters.py
  fakes.py                      测试专用内存 Repository
  contract/test_repository_contract.py
  integration/test_sqlite_repository.py
  integration/test_workflow.py

docs/
  design/architecture.md
  design/contracts.md
  design/zch-design.docx
  design/ljj-design.docx
  design/xhy-design.docx
  figures/
  screenshots/
  presentation/sdms.pptx
```

保持这些职责边界；如果早期模块很小，可合并同层文件，但不要混合 UI、规则和 SQL。Word 文件名目前仅为建议，交付前按教师正式命名要求调整。

## 4. 先冻结契约，再并行开发

以下为契约草案，而非已实现 API。三人共同评审 docs/design/contracts.md 后再编码。

### 数据语义

- Schedule：id、title、date、time、notes。
- id：由服务创建的 UUID，存储为文本；修改时保持不变；不能以列表行号或标题作为标识。
- title：去除首尾空白后非空；notes 允许空。字段长度上限如需设置，应三人确认后记录，不随意冒充课程规定。
- date/time：内存使用 datetime.date、datetime.time；界面约定 YYYY-MM-DD、HH:MM；分钟精度、本地朴素时间，不处理跨时区。
- 推荐不可变 dataclass；修改产生新值，不就地偷偷改变共享对象。
- 相同标题或相同时间可存在不同日程，原题没有禁止重叠。相同 ID 不可新增第二次。
- 查询按 time、id 确定性排序；无记录返回空列表，不报错。

### 服务草案

- create_schedule(title, day, at, notes) → Schedule。
- list_schedules(day) → list[Schedule]。
- update_schedule(schedule_id, title, day, at, notes) → Schedule。
- delete_schedule(schedule_id) → None。
- create/update 的 day 与 at 已经是日期/时间对象；GUI 字符串解析在 controller，业务不变量在 domain。服务不能依赖 UI 校验才能保持正确。
- 预期错误：ValidationError、ScheduleNotFound、StorageError。展示层只捕获可解释的预期错误；意外异常记录诊断信息并给通用提示，不静默吞掉。

### Repository 草案

- add(schedule) → None；已有 ID 不覆盖，作为存储冲突报告。
- get(schedule_id) → Schedule | None。
- list_by_date(day) → list[Schedule]；负责约定排序。
- update(schedule) → bool；找不到记录返回 False。
- delete(schedule_id) → bool；找不到记录返回 False。
- 更新/删除结果由 service 转成 ScheduleNotFound。每次写操作必须原子完成或回滚，不允许先清空再写入。
- SQLite 路径从装配点传入；测试使用临时目录，绝不复用真实日程库。
- 原生 SQLite 异常在适配器转成 StorageError，并保留异常原因供诊断。
- 连接由装配点管理关闭；初版 GUI 单线程本地操作，不引入线程与并发连接问题。

### UI 交互契约

- 显示文本可格式化，但 Treeview 行应关联 schedule_id。
- 删除确认由界面负责；取消时不能调用删除服务。服务仍校验记录是否存在。
- 写入成功后再更新列表与成功提示；写入失败保留表单，不能假装成功。
- 修改日期后刷新当前筛选日期，新日期与当前日期不同时记录从当前列表移出是正常行为。
- 无选中项提示选择日程，不把 None 传给服务。
- 首次启动显示当天；无数据有清晰空状态；日历跨月与闰年需验证。

## 5. 用一次新增解释全部架构

1. 用户在 ttk 表单填写标题、日期、时间、备注。
2. controller 把字符串解析为 date/time，解析失败给字段级提示。
3. service 调用领域规则校验，创建稳定 ID 和日程对象。
4. service 调用注入的 Repository.add；不关心具体 SQL。
5. SQLite 适配器参数化写入并提交；出错回滚且转换错误。
6. service 返回已保存对象。
7. UI 刷新当前日期列表并显示成功；失败则保留输入。

测试从不同边界切入：领域规则不用 GUI；服务使用测试 Fake；SQLite 用临时文件；GUI 人工验证显示与交互。相同流程体现职责分离、依赖倒置和可测试性，不靠堆设计模式名词。

## 6. 人员主责、审查与学习目标

### zch：技术负责人 + 领域/应用 + 集成

主责：需求冻结、架构图、契约；domain/、application/、bootstrap.py、__main__.py；可安装 src 布局、README 启动说明和最终集成。

交付：有效日程模型、四类用例、类型化错误、服务单元测试、装配入口、架构决策记录、个人报告、组级 PPT 整合。

学习重点：把需求转成不变量；依赖倒置；用例编排；接口兼容性；评审与范围控制。组长职责是保持边界与质量，不是代替成员写模块。

审查安排：xhy 审存储契约与失败路径，ljj 审服务接口对交互是否可用；zch 自己的 PR 也必须由另一成员审查。

### ljj：界面负责人 + 可用性验证

主责：ui/、界面原型、日历选择、列表、共用编辑表单、详情展示、删除确认、错误提示、日期切换与刷新。

交付：主界面与交互流程图、controller/presenters 单测、GUI 验收记录与截图、个人报告、PPT 交互章节。

学习重点：事件驱动、界面状态、纯函数解析、只在边界处理输入。不是把所有逻辑塞入按钮回调。

审查安排：zch 审依赖与用例接线；xhy 按验收步骤验证空态、非法输入及失败交互。

### xhy：持久化负责人 + 可靠性/测试基础

主责：infrastructure/、存储契约测试、tests/fakes.py、SQLite 集成测试、数据库路径与资源生命周期建议、重启恢复与回滚验证。

交付：SQLite Repository、表结构图、内存与 SQLite 共用契约测试、异常/重启测试、个人报告、PPT 可靠性章节。

学习重点：参数化 SQL、事务、序列化、临时资源隔离、通过测试证明行为。不是“最后替所有人测试”的角色。

审查安排：zch 审契约与异常语义；ljj 验证重启后列表恢复和用户可理解的提示。

### 共同规则

每个人实现自己模块的测试、维护自己的报告证据；交叉审查不转移作者责任。贡献以实际代码、测试、文档、评审和集成证据为依据，不按组长身份或代码行数预先排名。

## 7. 可分配任务卡（本地计划编号，不是已创建的 GitHub Issue）

| 编号 | 主责 | 工作及路径 | 依赖 | 可验收产物 |
|---|---|---|---|---|
| P01 | zch，三人评审 | docs/design/architecture.md、contracts.md | 无 | 六条需求映射、契约、技术取舍和未决点 |
| P02 | ljj | docs/figures/ 下界面草图及交互说明 | 无，可并行 P01 | 列表/日历/表单/确认/错误与空状态 |
| P03 | xhy | docs/design/ 下存储设计、测试矩阵 | 无，可并行 P01 | 字段映射、失败场景、临时库方案 |
| P04 | zch，所有人各自执行 | pyproject.toml、README.md 环境方案 | P01 | Python 3.12、uv 锁文件和 Tk 可用性证据 |
| P05 | zch | domain/schedule.py、domain/errors.py、tests/unit/test_schedule.py | P01/P04 | 有效对象与空标题等边界测试 |
| P06 | zch+xhy，zch 主责 | application/contracts.py、errors.py、tests/fakes.py、tests/contract/test_repository_contract.py | P05 | Fake 契约测试、统一缺失记录和排序语义 |
| P07 | zch | application/service.py、tests/unit/test_service.py | P06 | 四类用例、非法输入无写入、存储失败向上传递 |
| P08 | xhy | infrastructure/sqlite_repository.py、tests/integration/test_sqlite_repository.py | P06 | 契约通过，重新打开持久库可读，失败不破坏旧数据 |
| P09 | ljj | ui/controller.py、presenters.py 及对应单测 | P01/P05；先使用测试替身 | 解析、未选择、取消删除不调用服务、错误映射 |
| P10 | ljj | ui/app.py、schedule_form.py、calendar_view.py | P02/P09 | 基于替身演示界面与日历；不依赖 SQLite 实现进度 |
| P11 | zch，三人联调 | bootstrap.py、__main__.py、pyproject.toml、README.md、tests/integration/test_workflow.py | P07/P08/P10 | 实际新增→查询→修改→取消删除→确认删除；重启恢复 |
| P12 | 三人分别负责各自产物 | docs/design/*.docx、docs/screenshots/、docs/presentation/sdms.pptx | 各阶段持续收集，P11 后收口 | 每人正文不少于20页，组PPT不少于20页，真实证据和贡献标注 |

分支建议：docs/architecture-contracts、docs/ui-flow、docs/storage-test-plan；实现阶段按任务使用 feature/domain-model、feature/schedule-service、feature/sqlite-storage、feature/schedule-ui、feature/app-integration。不要三人长期共用一个功能分支。

## 8. 里程碑：先走通一条，再补齐一面

M0 设计与环境：P01—P04；确认目标操作系统、截止日期、Tk 可用性与数据目录。冻结契约后，GUI 与 SQLite 才真正可以独立推进。

M1 第一条纵向闭环：领域 + 新增/按日期查询服务 + SQLite 新增/查询 + 最小 GUI + 装配；实际演示新增并在所选日期看到记录。P07/P08/P10/P11 应拆成这个小切片先合并，不等所有 CRUD 写完。

M2 功能完整：在同一分层上增量加入详情、修改、删除、取消删除和所有提示。复用表单，不复制整套创建与编辑逻辑。

M3 可靠性：持久化重启、事务失败、非法输入、跨月闰年、删除后再操作、修改日期后的筛选一致性、全量质量检查。

M4 交付：全新环境复现、截图、三份 Word、组 PPT、贡献记录、README 实际命令与结果。

不设虚假完成日期：收到教师截止时间和三人每周可投入时间后，再把任务卡映射到日历。

## 9. 实践方式：先解释，再测试，再实现

本计划刻意不提供可直接抄完的业务代码，保留用户实践空间。对每张实现任务卡，按短步骤推进：

1. 作者用自己的话复述输入、输出、不变量、失败场景。
2. 先写一个最小失败测试；确认失败是目标行为缺失，不是环境错误。
3. 自己实现最小逻辑；助手优先提示和解释，不直接包办。
4. 运行该测试，再运行相关回归；记录真实结果。
5. 去除重复、补类型和公共文档；确认测试仍通过。
6. 检查 diff，由一名非作者审查，作者明确确认后才提交、推送和合并。

首个练习由 zch 完成：用文字回答“日程有哪些字段？空白标题为何无效？同名日程为何不是同一条？为什么日期不是核心业务字符串？为什么模型不应弹窗？”之后再开始 test_schedule.py。

ljj 首个练习：画出“未选中→点击删除”和“选中→确认→取消”的状态变化，明确哪些步骤不能调用服务。

xhy 首个练习：画出 Python 对象与 SQLite 字段映射，说明重启测试为什么必须关闭并重新打开同一个临时数据库文件。

助手后续反馈格式：你做对的点 / 具体风险及原因 / 最小改进 / 下一项小练习。避免一次生成整个应用，让每个人能够口头解释自己的实现。

## 10. 环境与验证计划（以下命令尚未执行）

环境准备：

```text
uv --version
uv venv --python 3.12
uv sync --locked --dev
uv run python --version
uv run python -m tkinter
```

注意：Tkinter 属于标准库接口，但依赖可用的 Tcl/Tk 和图形显示环境；不能因为没有 pip 运行时依赖就假定任何机器都能显示窗口。Linux 无显示环境时不把 GUI 启动失败当业务失败；需要目标桌面手工验证。系统依赖缺失时先解释再安装，不修改全局 Python 包。

当前 pyproject.toml 中 package=false。首个应用包落地时，由 zch 明确配置支持 src 布局的构建后端、调整包安装配置并验证 import，不用临时 PYTHONPATH 掩盖打包问题。之后统一入口建议为 `uv run python -m schedule_management`，目前尚不存在。

代码存在后的检查：

```text
uv lock --check
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest tests/unit/test_schedule.py -v
uv run pytest tests/unit/test_service.py -v
uv run pytest tests/contract/test_repository_contract.py -v
uv run pytest tests/integration/test_sqlite_repository.py -v
uv run pytest tests/unit/test_controller.py -v
uv run pytest tests/integration/test_workflow.py -v
uv run pytest --cov=schedule_management --cov-report=term-missing
uv run python -m compileall src
```

期望是检查退出成功、各行为断言通过；不预先捏造测试数量或覆盖率。无测试时 pytest 的无用例结果不能记为成功验收。覆盖率用于寻找遗漏，不为了数字写无意义断言。

### 需求—验证对应

| 需求 | 自动化重点 | 人工 GUI 验收 |
|---|---|---|
| F-01 | 日历日期计算、显示格式、controller 状态 | 列表、日历、按钮、空态、跨月/闰年 |
| F-02 | 空标题/非法日期时间解析、服务写入、存储失败 | 成功才刷新；失败保留输入 |
| F-03 | 仅当天、无记录、相同时间稳定排序 | 切换日期列表正确 |
| F-04 | 保持ID、缺失记录、更新失败旧值保留 | 修改日期后当前筛选一致 |
| F-05 | 存在/不存在、取消不调用服务 | 未选中提示、取消不变、确认才删除 |
| F-06 | 已知异常转换、非法输入不写入 | 无裸堆栈、可理解提示、还能继续操作 |
| 工程增强 | 同一临时文件关闭重开、事务回滚 | 退出重启仍存在已保存数据 |

GUI 证据记录：操作系统/Python/Tk 版本、前置数据、步骤、预期、实际、截图路径。测试仅用虚构日程，避免把个人真实安排写入提交材料。

## 11. 工程取舍与风险

- Tkinter/ttk：运行时无需引入第三方 Python GUI 包，适合课程与学习；月历控件需自己用 calendar+ttk 组合。若团队更熟 PyQt，可在 M0 改选，但记录部署与许可证处理，不中途无理由重写。
- SQLite：标准库支持、事务比手写 JSON 覆盖文件更可靠；比纯内存多一点 SQL 学习成本。第一版仅单用户本地，不宣称适合多人并发系统。
- 轻量分层：让三人平行协作与测试替换有实际收益；若一层只有简单函数就保留简单函数，不强行设计多层继承。
- 删除确认属于交互策略，领域规则属于业务安全；不能误以为弹窗代替服务层有效性检查。
- 接口变更必须在契约文档说明并通知另两人；公共配置与入口由 zch 集中维护，避免无关文件冲突。
- 数据库应放入明确可写的用户数据目录，不依赖运行时 cwd；具体跨平台路径在 M0 确认并写入 README，测试始终注入临时路径。
- 本轮不安装依赖、不启动 GUI、不创建 GitHub Issue/指派账号、不提交推送。任务卡是本地人员分工建议，不代表已通知或获得成员确认。

## 12. 完成定义与下一步

每张任务卡完成需要：需求对应、实现或设计产物、边界测试、真实验证结果、非作者审查、相关说明与证据。项目完成还必须包含全部课程文档，不能只演示程序。

下一次优先开展 P01—P03 的设计评审；先让三人解释自己的契约和失败路径，再确认 M0 环境及进入第一项测试练习。任何业务编码都等用户明确同意。
