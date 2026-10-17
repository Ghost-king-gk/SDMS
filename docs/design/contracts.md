# 服务层 / 存储层团队契约

- 状态：2026-10-17 定稿（分支 `feature/application-service`，负责人 zch）
- 权威性：本文件是三层接缝的最终依据。`storage-interface-spec.md` 是界面侧需求规格、
  `ui-interaction.md` 是交互稿；两者与本文件冲突时以本文件为准，并回头修订它们。
- 对应代码：`application/parsing.py`、`service.py`、`contracts.py`、`errors.py` 与 `composition.py`。

## 1. 分层与依赖方向

```text
ui  ->  application  ->  domain
              ^
       infrastructure（实现 application.contracts.ScheduleRepository）
composition.py（包根，唯一同时认识 application 与 infrastructure 的模块）
```

- `application` 不 import `infrastructure`；仓储以 `ScheduleRepository` 协议注入。
- 界面**不得直接 import `schedule_management.infrastructure`**，只调用 `composition.build_service`。
- `domain` 不依赖任何外层；`Schedule` 是不可变 dataclass，构造时执行领域不变量。

## 2. 服务层签名

```python
class ScheduleService:
    def __init__(self, repository: ScheduleRepository) -> None: ...
    def list_schedules(self, day: dt.date) -> list[Schedule]: ...
    def create_schedule(
        self, title: str, date_text: str, time_text: str, notes: str
    ) -> Schedule: ...
    def update_schedule(
        self, schedule_id: str, title: str, date_text: str, time_text: str, notes: str
    ) -> Schedule: ...
    def delete_schedule(self, schedule_id: str) -> None: ...
```

- `create_schedule` / `update_schedule` 接收**用户原样输入的字符串**日期与时间，解析归服务层
  （这是相对早期草案的唯一偏差，已由界面负责人确认）。界面不预解析、不抢先校验。
- `list_schedules` 接收 `dt.date`（来自日历点选），返回 `list[Schedule]`；无记录返回空列表。
- `update_schedule` 返回新对象但 **id 不变**；四个字段全量覆盖，不是增量补丁。
- 返回值 `Schedule` 结构上满足界面 `ScheduleLike`（`id/title/date/time/notes` 五个只读属性）。
- `composition.build_service(connection) -> ScheduleService` 是唯一装配点；连接归调用方所有。

## 3. 错误类型

| 类型 | 定义位置 | 含义 | 谁抛出 |
| --- | --- | --- | --- |
| `ValidationError` | `domain/errors.py` | 用户输入不合法（空标题、无法解析的日期时间、超长、空 id） | 解析/领域/服务层 |
| `ScheduleNotFoundError` | `application/errors.py` | 按 id 找不到记录 | 服务层把仓储 `False` 翻译而来 |
| `DuplicateScheduleError` | `application/errors.py` | 主键冲突 | 仓储，服务层原样透传 |
| `StorageError` | `application/errors.py` | 存储不可用（锁、只读、坏行、连接失效） | 仓储，服务层原样透传 |

- `DuplicateScheduleError` 是 `StorageError` 子类，**分类时先判 `Duplicate` 再判 `Storage`**，否则重复 ID 会被误报成存储故障。
- 服务层不把仓储异常包成新类型；`except` 后重新抛同一实例，保留原始消息与 `cause`。
- 类名带 `Error` 后缀是最终名。界面 `presenters.error_category` 已改为优先 `isinstance` 判定真类，
  并按类名/MRO 兜底兼容开发替身；`Duplicate` 必须先于 `StorageError`，本契约不为迁就按名匹配而改名。

## 4. 仓储契约与 bool 语义

```python
class ScheduleRepository(Protocol):
    def add(self, schedule: Schedule) -> None: ...
    def get(self, schedule_id: str) -> Schedule | None: ...
    def list_by_date(self, day: dt.date) -> list[Schedule]: ...
    def update(self, schedule: Schedule) -> bool: ...
    def delete(self, schedule_id: str) -> bool: ...
```

- `update` / `delete` 返回 `True` 表示确实改到/删到一行，`False` 表示 **id 不存在**；
  服务层把 `False` 翻成 `ScheduleNotFoundError`，界面永远看不到裸 `bool`。
- `add` 遇到重复 id 抛 `DuplicateScheduleError`；其余 `sqlite3.Error` 抛 `StorageError`。
- `list_by_date` 在仓储内完成 `ORDER BY time, id` 升序；服务层与界面都不再排序。
- 仓储不修改注入连接的 `row_factory`，也不关闭连接；事务按单次写操作 commit/rollback。

## 5. 宽容解析（T-02）

只接受分隔符差异与前导零缺失，前后空白忽略：

| 输入 | 结果 |
| --- | --- |
| `2026-10-15` / `2026/10/15` / `2026.10.15` / `2026年10月15日` | `date(2026, 10, 15)` |
| `2026-1-5` 等四种写法 | `date(2026, 1, 5)` |
| `9:05` / `09:05` | `time(9, 5)` |

一律 `ValidationError`，消息回显原文（形如“日期「明天」无法识别”）：

- 相对日期：`明天`、`今天`、`下周三`；
- 非“年月日”顺序：`15/10/2026`；缺少任一分量：`2026-10`；
- 不存在的日期：`2026-02-30`、`2026-13-01`（消息含“真实存在”）；
- 时间越界或格式不符：`25:00`、`09:60`、`9:5`、`上午九点`。

不引入第三方日期库；只认 ASCII 数字；`datetime` 的异常转换成 `ValidationError` 并保留 cause。

## 6. 字段规范化、长度与时间精度

- 标题：`strip()` 后必须非空；最长 **100 字符**（`len()`，中文按字计）。
- 备注：`strip()` 后保存；最长 **500 字符**；空串合法，不转 `None`。
- 保存的是去空白后的值（标题 `"  周报  "` → `"周报"`）。
- 时间精度为**分钟**：`Schedule.__post_init__` 把秒与微秒截断为 0，界面 `HH:MM` 往返不丢数据。
- 空 id：`update_schedule` / `delete_schedule` 抛 `ValidationError("日程 ID 不能为空")`，
  与“记录不存在”区分开；传入 id 先 `strip()` 再查。

## 7. 数据库文件位置与连接所有权

- 库文件位置**由入口/组合根决定**，库代码不提供默认路径、不读当前工作目录；入口建好父目录后 connect。
- 测试用 `tmp_path` 注入临时文件；`":memory:"` 仅用于契约测试。
- 一个服务一个连接，只在 GUI 线程使用（`check_same_thread` 默认）；连接由创建者关闭，长期驻留由入口负责。
- 真服务开箱为空，不预置演示数据；示例数据只能来自显式 seed 脚本或测试夹具。

## 8. 验收

```bash
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run mypy src tests
```

结构兼容性以 mypy 为准：`ScheduleService` 赋给界面 `ScheduleServicePort` 必须通过，
且 `presenters.to_row(service.create_schedule(...))` 可直接工作。
