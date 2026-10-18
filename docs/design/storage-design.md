# 存储层设计与测试矩阵（P03）

作者：xhy　负责模块：`src/schedule_management/infrastructure/`、`tests/fakes.py`、契约测试与集成测试

本文档描述日程持久化的数据组织、契约、失败场景与测试方案，供设计评审使用。实现代码以 `src/schedule_management/` 为准，本文档随实现同步更新。

## 1. 职责与边界

存储层只做一件事：把领域对象 `Schedule` 安全地写入 SQLite，并按需读回。它实现应用层定义的 `ScheduleRepository` 契约，不包含任何业务规则和界面文案。

边界约束：

- 连接由装配点（bootstrap）创建并负责关闭，仓储不 open、不 close。
- 仓储不修改调用方传入连接的状态（例如 `row_factory` 只在游标上设置）。
- 原生 `sqlite3` 异常一律转换为应用层错误，不让底层异常穿透到界面。
- 数据库文件路径从装配点传入，测试只使用内存库或临时目录，绝不复用真实日程库。

## 2. 数据语义与字段映射

`Schedule` 是冻结数据类，字段语义见 `domain/schedule.py`。SQLite 只有 TEXT 存储，因此日期和时间在写入时序列化为字符串，读回时再还原为对象。

| Python 字段 | Python 类型 | SQLite 列 | SQLite 类型 | 写入（序列化） | 读回（反序列化） |
| --- | --- | --- | --- | --- | --- |
| `id` | `str` | `id` | `TEXT PRIMARY KEY` | 原样 | 原样 |
| `title` | `str` | `title` | `TEXT NOT NULL` | 原样（已去除首尾空白） | 原样 |
| `date` | `datetime.date` | `date` | `TEXT NOT NULL` | `isoformat()` → `YYYY-MM-DD` | `date.fromisoformat()` |
| `time` | `datetime.time` | `time` | `TEXT NOT NULL` | `isoformat()` → `HH:MM:SS` | `time.fromisoformat()` |
| `notes` | `str` | `notes` | `TEXT NOT NULL DEFAULT ''` | 原样 | 原样 |

说明：

- 时间精度为分钟。`Schedule.__post_init__` 会把秒和微秒截断为 0，因此 `time.isoformat()` 实际恒为 `HH:MM:00`。
- `date` 与 `time` 存字符串后，字典序即时间序，可直接用于 `ORDER BY`，不需要额外转换。
- `id` 是服务层生成的 UUID 文本，主键约束保证同一 ID 无法新增第二次。

## 3. 表结构

```sql
CREATE TABLE IF NOT EXISTS schedules (
    id    TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    date  TEXT NOT NULL,
    time  TEXT NOT NULL,
    notes TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_schedules_date ON schedules(date);
```

- 主键 `id`：同一日程不可重复插入。
- `idx_schedules_date`：按日期筛选是最高频查询，建索引避免全表扫描。
- 建表语句幂等（`IF NOT EXISTS`），仓储实例化时可安全重复执行。

## 4. 仓储契约

`ScheduleRepository` 是 Protocol，内存实现（`tests/fakes.py`）与 SQLite 实现（`infrastructure/sqlite_repository.py`）行为一致、可互换：

| 方法 | 签名 | 语义 |
| --- | --- | --- |
| `add` | `add(schedule) -> None` | 新增；ID 已存在时抛 `DuplicateScheduleError`，不覆盖 |
| `get` | `get(schedule_id) -> Schedule \| None` | 按 ID 查询；不存在返回 `None` |
| `list_by_date` | `list_by_date(day) -> list[Schedule]` | 返回当天全部日程，按 `time`、`id` 升序 |
| `update` | `update(schedule) -> bool` | 更新；找不到记录返回 `False` |
| `delete` | `delete(schedule_id) -> bool` | 删除；找不到记录返回 `False` |

`update` / `delete` 返回 `False` 表示记录不存在，由服务层转换为 `ScheduleNotFoundError`；仓储自身不抛该异常。

## 5. 原子性与异常转换

每次写操作（`add` / `update` / `delete`）独立提交，失败时先 `rollback` 再抛错，不允许出现"改了一半"的中间状态。

异常映射规则：

| 场景 | 底层表现 | 转换结果 |
| --- | --- | --- |
| 新增时 ID 已存在 | `IntegrityError` 且含 `UNIQUE` / `PRIMARY KEY` | `DuplicateScheduleError` |
| 新增时其他约束冲突（如 `notes` 为 NULL） | `IntegrityError` 但非唯一冲突 | `StorageError` |
| 读回坏行：日期/时间无法解析 | `ValueError` | `StorageError`（原因保留在 `cause`） |
| 读回坏行：违反领域不变量（空白标题等） | `ValidationError` | `StorageError`（原因保留在 `cause`） |
| 连接已关闭或其他 `sqlite3` 错误 | `sqlite3.Error` | `StorageError` |

关键点：读路径上任何一行解析失败，都不能让 `ValueError` / `ValidationError` 穿透——它们只代表"本行数据损坏"，应统一按存储故障处理。

## 6. 临时库与资源隔离

- 契约测试的 SQLite 实例使用 `sqlite3.connect(":memory:")`，测试结束关闭连接，不落盘。
- 集成测试使用 pytest 的 `tmp_path` 创建临时数据库文件，测试后自动清理。
- 重启恢复测试必须对同一个临时文件先 `close()` 再重新 `connect()`，以证明数据真正落盘，而不是停留在连接缓存中。
- 所有测试均使用虚构日程，不写入任何个人真实安排。

## 7. 测试矩阵

### 7.1 契约测试（内存 + SQLite 各跑一遍）

`tests/contract/test_repository_contract.py` 通过 `params=["memory", "sqlite"]` 让两种实现运行同一套断言，确保可互换。

| 行为 | 测试函数 |
| --- | --- |
| 新增后可查回相同内容 | `test_add_then_get_returns_same_schedule` |
| 重复 ID 抛错且原记录保留 | `test_add_duplicate_raises_and_keeps_original` |
| 查询不存在 ID 返回 `None` | `test_get_missing_returns_none` |
| 只返回指定日期 | `test_list_by_date_only_returns_that_day` |
| 按 time、id 排序 | `test_list_by_date_sorted_by_time_then_id` |
| 同一时刻按 id 次级排序 | `test_list_by_date_same_time_sorted_by_id` |
| 无记录返回空列表 | `test_list_by_date_empty_when_no_records` |
| 更新存在记录返回 `True` 且生效 | `test_update_existing_returns_true_and_applies` |
| 更新不存在记录返回 `False` | `test_update_missing_returns_false` |
| 删除存在记录返回 `True` | `test_delete_existing_returns_true` |
| 删除不存在记录返回 `False` | `test_delete_missing_returns_false` |

### 7.2 SQLite 集成测试（持久化与异常）

`tests/integration/test_sqlite_repository.py` 使用真实临时文件，验证契约测试覆盖不到的存储特性。

| 场景 | 测试函数 |
| --- | --- |
| 关闭并重开同一文件后数据仍在 | `test_schedule_survives_reopen` |
| 修改结果重启后保留 | `test_update_persists_across_reopen` |
| 重复 ID 被拒绝且原记录完好 | `test_duplicate_add_keeps_original` |
| 不修改调用方连接的 `row_factory` | `test_connection_row_factory_is_not_modified` |
| `date` 索引存在 | `test_date_index_exists` |
| 坏日期行转为 `StorageError` | `test_get_corrupted_date_raises_storage_error` |
| 坏时间行转为 `StorageError` | `test_list_by_date_corrupted_time_raises_storage_error` |
| 空白标题行转为 `StorageError` | `test_get_blank_title_row_raises_storage_error` |
| 连接已关闭转为 `StorageError` | `test_closed_connection_raises_storage_error` |
| 非唯一约束冲突转为 `StorageError` | `test_non_unique_integrity_error_becomes_storage_error` |

### 7.3 领域单元测试

`tests/unit/test_schedule.py` 覆盖 `Schedule` 的字段归一化与不变量（时间截断、空标题、备注类型等），属领域层职责，在服务层测试中联动验证。

## 8. 验证命令

```powershell
uv run pytest -q
uv run ruff check .
uv run mypy src
uv run python -m compileall src
```

当前结果：`pytest` 46 项全部通过，`ruff` 与 `mypy` 无报错。
