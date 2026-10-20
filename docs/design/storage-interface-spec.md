# 存储层接口规格单（界面侧要求）

> **这份文档是什么。** 它是界面负责人（ljj）从已落地的开发替身
> （`src/schedule_management/dev_stub_service.py`，33 项行为测试）中提炼出的
> **对服务/存储接口的精确要求**，供 application 层（zch）与 SQLite 存储层（xhy）
> 实现时对照。
>
> **它不是什么。** 它不是 `contracts.md` 的替代品。团队契约以组长的
> `docs/design/contracts.md` 为准；两者冲突时，**以契约为准**，并请在实现时
> 回来修订本文，避免两份文档各自漂移。
>
> **为什么现在写。** 界面已经能跑（P10 已落地，122 项门禁通过），但跑在内存
> 替身上：退出即丢，持久化（V-14）必然验不过。这份规格单的目的就是把
> "照着填"的成本降到最低——每个条目都来自一条已运行的测试，不是口头约定。

## 1. 接口签名（六个方法）

界面只通过 `ui/ports.py` 的 `ScheduleServicePort` 协议与服务层交互。
签名如下（Python 类型标注即契约）：

> **合流后的实现状态（2026-10）：** `ui/ports.py` 不再定义独立协议，
> `ScheduleServicePort` / `ScheduleLike` 分别是 `application.contracts.ScheduleUseCases`
> / `ScheduleView` 的别名；下面这段签名保留为界面侧的需求形状，
> 权威定义以 `contracts.md` 第 2 节为准。

```python
class ScheduleServicePort(Protocol):
    def list_schedules(self, day: dt.date) -> list[ScheduleLike]: ...

    def create_schedule(
        self,
        title: str,
        date_text: str,
        time_text: str,
        notes: str,
    ) -> ScheduleLike: ...

    def update_schedule(
        self,
        schedule_id: str,
        title: str,
        date_text: str,
        time_text: str,
        notes: str,
    ) -> ScheduleLike: ...

    def delete_schedule(self, schedule_id: str) -> None: ...

    def count_by_date(self, start: dt.date, end: dt.date) -> dict[dt.date, int]: ...

    def search_schedules(self, text: str) -> list[ScheduleLike]: ...


class ScheduleLike(Protocol):
    @property
    def id(self) -> str: ...
    @property
    def title(self) -> str: ...
    @property
    def date(self) -> dt.date: ...
    @property
    def time(self) -> dt.time | None: ...
    @property
    def notes(self) -> str: ...
```

**最关键的一条：`create_schedule` 与 `update_schedule` 的日期时间参数收的是
用户输入的原始字符串**，不是 `dt.date` / `dt.time` 对象。宽容解析
（`2026/10/15` → `date(2026,10,15)`）必须在服务层完成，界面不抢先校验
（zch 在 PR #5 的评审意见，已落入 `ui-interaction.md` 5.1 节）。
返回的 `ScheduleLike` 只需暴露五个只读属性，ORM 实体、dataclass、
`sqlite3.Row` 包装均可。

## 2. 行为规格（逐条来自替身测试）

下表每一行都对应 `tests/unit/test_dev_stub_service.py` 里一条已通过的用例。
真实现满足下表即视为与界面兼容。

### 2.1 list_schedules

| # | 规则 | 说明 |
| --- | --- | --- |
| L1 | 只返回 `day` 当天的记录 | 不过滤相邻日期 |
| L2 | 无记录时返回**空列表**，不抛异常 | 界面据此显示空状态（V-06） |
| L3 | 全天日程排最前，再按 `(时间, id)` 升序 | `presenters.to_rows` 明确不排序，界面只照抄顺序；`time` 为 `None` 表示全天，`id` 作为次级键保证同样输入永远同样顺序 |
| L4 | 同一天多条记录全部返回 | 不折叠、不去重 |

### 2.2 create_schedule

| # | 规则 | 说明 |
| --- | --- | --- |
| C1 | 标题去掉首尾空白后必须非空 | "是不是空的"以此为准；`"   "` 抛 `ValidationError`（V-03） |
| C2 | 保存的标题是去空白后的值 | `"  带空格  "` 存为 `"带空格"` |
| C3 | 日期宽容解析见第 3 节 | `2026-10-15`、`2026/10/15`、`2026.10.15`、`2026年10月15日` 等价（T-02 暂定范围） |
| C4 | 不存在的日期必须拒绝 | `2026-02-30` 抛 `ValidationError`，消息里出现"真实存在"字样 |
| C5 | 时间接受 `H:MM` 与 `HH:MM`；留空表示全天 | `9:05` 与 `09:05` 等价；`25:00`、`09:60` 拒绝；空串存为 `time=None` |
| C6 | 备注允许为空 | 空串是合法值，不转 None |
| C7 | 长度上限：标题 100、备注 500 字符 | 超限抛 `ValidationError`（T-04 暂定值） |
| C8 | 错误消息要回显用户原话 | 如"日期「明天」无法识别"，否则用户不知道该改哪一处（V-16 的预期文案） |
| C9 | 返回的对象带稳定唯一 id | 同一进程内不重复；界面用它做选中与修改的目标 |
| C10 | 保存成功后立即可被 `list_schedules` 查到 | 界面保存后立即刷新列表（V-02） |

### 2.3 update_schedule

| # | 规则 | 说明 |
| --- | --- | --- |
| U1 | id 不存在时抛 `ScheduleNotFound` | 不要静默创建新记录 |
| U2 | **id 不变**，只更新内容 | 界面依赖它保持选中态（V-08） |
| U3 | 四个字段全量更新 | 不是增量补丁 |
| U4 | 校验规则与 create 完全相同 | C1–C8 全部适用 |
| U5 | 改到其他日期后，该条从原日期列表消失 | 这是正常行为不是 bug（V-09） |

### 2.4 delete_schedule

| # | 规则 | 说明 |
| --- | --- | --- |
| D1 | 成功删除后返回 None | 界面不关心返回内容 |
| D2 | id 不存在时抛 `ScheduleNotFound` | 不要静默成功——重复删除必须让界面能提示（V-13） |
| D3 | 删除后立即可在 `list_schedules` 中体现 | 界面删除后刷新（V-12） |

### 2.5 search_schedules

| # | 规则 | 说明 |
| --- | --- | --- |
| S1 | 标题或备注任一包含查询串即命中 | 大小写按 SQLite `LIKE` 的默认行为，中文按字面匹配 |
| S2 | `%`、`_`、`\` 按字面量搜索 | SQL 使用 `ESCAPE '\'`，用户输入先转义 |
| S3 | 空查询（含全空白）返回空列表 | 不返回全表，也不报错 |
| S4 | 排序为日期、全天在前、时间、id | 跨日期搜索时日期升序，便于直接展示 |

## 3. 宽容解析规则（T-02 暂定值）

界面把用户原文原样交给服务层，解析规则完全归后端。当前暂定范围：

**支持**（仅分隔符差异，前后空白忽略）：

- `2026-10-15`、`2026/10/15`、`2026.10.15`、`2026年10月15日`
- 月日可缺前导零：`2026-1-5` 等价 `2026-01-05`
- 时间：`9:05` 与 `09:05` 等价

**不支持**（抛 `ValidationError`，由界面显示原因）：

- 相对日期：`明天`、`下周三`、`今天`
- 日月年顺序：`15/10/2026`
- 越界值：`2026-13-01`、`2026-02-30`、`25:00`

这一条以 zch 的 `contracts.md` 为最终依据。若契约扩大了范围（比如支持"明天"），
只需改服务层与 V-16 的预期文案，界面代码不用动。

## 4. 异常类型命名（重要）

`ui/presenters.py` 的 `error_category` **按异常类名**分类
（真异常类落地前，界面不能在导入期依赖 `domain/errors.py`）。
因此服务层抛出的异常类名必须与下表一致：

| 类名 | 含义 | 界面呈现 |
| --- | --- | --- |
| `ValidationError` | 输入不合法 | 警告框，标题"输入有问题"，正文为异常消息 |
| `ScheduleNotFound` | 按 id 找不到记录 | 警告框，标题"记录不存在" |
| `StorageError` | 存储不可用（写失败、文件不可写、数据库锁超时等） | 警告框，标题"存储故障" |
| 其他任何异常 | 未预期 | 警告框 + 记日志；界面不显示堆栈 |

命名注意：类名**不带 `Error` 后缀**是有意的——`ValidationError` 是例外，
它与另两个名字的差异是历史决定，改后缀会让界面错误分类失效。真类落地后
（预计在 `domain/errors.py` 或 `application/errors.py`），删除替身里的三个
同名类即可，界面按 `isinstance` 切换的实现点已在 `presenters.py` 标注。

## 5. SQLite 实现检查清单（xhy）

以下是把替身换成真存储时的具体落地点。标准库 `sqlite3`，不引 ORM
（2026-10-14 团队结论）。

**表结构（建议，可调整）：**

```sql
CREATE TABLE IF NOT EXISTS schedules (
    id     TEXT PRIMARY KEY,          -- uuid4 字符串，与替身一致
    title  TEXT NOT NULL,
    date   TEXT NOT NULL,             -- ISO 格式 YYYY-MM-DD，便于按天查询
    time   TEXT NOT NULL,             -- HH:MM；空串表示全天（哨兵）
    notes  TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_schedules_date ON schedules(date);
```

**必须做到的：**

1. **参数化查询**，所有用户输入走 `?` 占位符，不拼 SQL 字符串；
2. **写操作用事务**，失败即回滚，并把 `sqlite3.Error` 转换抛
   `StorageError`（不要让它以 `sqlite3.OperationalError` 的面目穿过端口——
   界面会把它归为"未预期异常"并记日志，用户看到的是泛化提示）；
3. **首次使用时建表**（`CREATE TABLE IF NOT EXISTS`），不需要迁移框架；
4. **数据库文件位置**不依赖运行时当前工作目录（T-03 暂定：
   跨平台用户数据目录下 `sdms/schedules.db`；测试注入临时路径）；
5. **排序在 SQL 里做**：全天在前，再 `ORDER BY time, id`，与 L3 一致；
   可用 `ORDER BY CASE WHEN time = '' THEN 0 ELSE 1 END, time, id`；
6. **`list_schedules` 的日期参数是 `dt.date` 对象**，在仓储层转 ISO 字符串，
   不要把格式化责任推回界面；
7. **全天日程的存储**：`time` 列保持 `TEXT NOT NULL`，用**空串**表示 `time=None`，
   读出空串还原为 `None`；不要改 schema 版本或做迁移，旧库可直接继续使用；
8. **`count_by_date(start, end)`**：闭区间，`SELECT date, COUNT(*) ... WHERE date >= ? AND date <= ? GROUP BY date`，
   返回 `dict[dt.date, int]`；键供日历标记、值供当天条数徽标；
9. **`search_schedules(text)`**：标题或备注包含匹配，SQL 用 `LIKE ? ESCAPE '\'`；
   先把用户输入的 `\`、`%`、`_` 转义，再拼 `%...%`；空查询返回空列表；
   排序为 `date, 全天在前, time, id`。

**`V-14` 持久化验收（这条现在必然验不过，等你）：**

新增若干条 → 退出程序 → 重新启动 → 数据仍在，且日期、时间、备注与退出前一致。
跑法：`uv run python scripts/shoot_ui.py` 之前先真新增两条，重启后检查列表。

**已知边界（提前说明，避免返工）：**

- SQLite 的写锁是库级并发限制。本系统是单用户桌面应用，默认配置即可；
  若遇到 `database is locked`，设 `timeout` 参数（如 5 秒）而不是静默重试。
- 不要为"演示效果"在库里预置数据——界面启动时的示例数据由
  `dev_stub_service.seed_defaults` 那类机制负责，真服务应当开箱为空，
  否则 V-06（空状态）在干净环境下永远验不到。

## 6. 替身与真实现的差异声明

诚实列出，免得日后对不上：

| 项 | 替身（现状） | 真实现（期望） |
| --- | --- | --- |
| 持久化 | 内存 dict，退出即丢 | SQLite 文件 |
| `StorageError` | 定义了但没有任何触发路径 | 写失败、锁超时等场景抛出 |
| 解析与校验规则 | 本文第 3 节与 C1–C8 的暂定值 | 以 `contracts.md` 为准 |
| 示例数据 | `seed_defaults()` 造 5 条虚构日程 | 无，开箱为空 |
| 位置 | `src/schedule_management/dev_stub_service.py` | 落地后替身应删除或移至 `examples/` |

**替换方式：** `ui/app.py` 的 `build_service()` 是唯一改动点——把返回
`DevStubScheduleService` 换成返回真服务实例即可，界面五个窗口模块、
`controller.py`、`presenters.py` 与全部测试一行不改。这正是
`ui-interaction.md` 第 11 节那条可验收判据的实践：换后端时若需要动
`controller.py`，说明接缝破了，应当回头修而不是将就。

## 7. 联调时的最小验证顺序

1. xhy 实现仓储 + zch 实现服务层，按第 2、4 节对照自测；
2. 在 `ui/app.py` 的 `build_service()` 换入真服务；
3. 跑 `uv run pytest -q`（界面层 113 项断言此时已用真服务适配器验证一遍）；
4. 跑 `uv run python scripts/shoot_ui.py`，重点看 V-02、V-12、V-14 三条；
5. V-14 通过后，把 `ui-interaction.md` 第 6 节里标注"依赖 SQLite"的行
   更新为已验收。
