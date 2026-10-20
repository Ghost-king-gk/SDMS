"""开发期替身服务：让界面在后端还没落地时也能真的跑起来。

**这是替身，不是正式实现，也不是替谁的活。**

真服务（`application/service.py` 归 zch、`infrastructure` 归 xhy）落地之后，
本文件应当被删掉或搬到 `examples/` 下。`ui/app.py` 里注入的地方只有一行，
换成真实现不需要动任何界面代码——这正是 `MainViewPort` /
`ScheduleServicePort` 两个端口存在的意义（见 `ui-interaction.md` 第 11 节）。

为什么现在需要它：

- 界面能够**真的开起来**，而不是只存在于文档里——这才好在截图、
  截图进设计文档，也才好在答辩时演示；
- V-01 到 V-17 里凡是不依赖真实磁盘的部分，可以提前一遍遍地跑；
- zch 与 xhy 拿到一个能运行的东西，比拿到一份契约文档更容易进入状态。

它做了三件本来该由后端做的事，标注清楚以便后来替换：

1. **日期时间的宽容解析**。仅支持分隔符差异（`2026/10/15`、`2026.10.15`、
   `2026年10月15日`），不支持相对日期（`明天`、`下周三`）——按 T-02 的暂定值，
   最终以支持范围为准，以 `contracts.md` 为准。
2. **字段校验**。标题去空白后非空、备注允许为空，长度上限按 T-04 的暂定值。
3. **持久化**。只存在内存里，退出即丢。**因此 V-14（重启后数据仍在）在本替身
   下必然验不过**，那条要等 xhy 的 SQLite。这里不假装它被验过了。
"""

from __future__ import annotations

import datetime as dt
import re
import uuid
from dataclasses import dataclass, replace
from typing import Final

# ----------------------------------------------------------------------------
# 假异常：类名必须与契约里的名字一致。
#
# `ui/presenters.py` 按**异常类名**分类（`error_category`），因为真异常类还
# 没落地——界面不能在导入期依赖 `domain/errors.py`。等真类可用后，
# 这里的三个类整体删除，换成 import 即可。
# ----------------------------------------------------------------------------


# 下面三个名字不带 Error 后缀是有意的：`presenters.error_category` 按
# **异常类名**匹配，界面侧契约里这三个名字已经写定，改后缀会让错误类型识别失效。
class ValidationError(Exception):
    """输入不合法：例如标题只有空格、日期写法无法识别。"""


class ScheduleNotFound(Exception):  # noqa: N818  名字由契约决定，见上方注释
    """按 id 找不到记录：通常意味着它已经被删除了。"""


class StorageError(Exception):
    """存储不可用：写入失败、文件不可写等。"""


TITLE_LIMIT: Final = 100
NOTES_LIMIT: Final = 500


@dataclass(frozen=True)
class SimpleSchedule:
    """一条日程的最小实现：只有界面要求的五个只读属性。

    它结构性满足 `ui/ports.py` 的 `ScheduleLike`，因此 `presenters` 可以直接处理，
    两边都不需要互相 import。
    """

    id: str
    title: str
    date: dt.date
    time: dt.time | None
    notes: str


_DATE_PATTERNS: Final = (
    re.compile(r"^(\d{4})-(\d{1,2})-(\d{1,2})$"),
    re.compile(r"^(\d{4})/(\d{1,2})/(\d{1,2})$"),
    re.compile(r"^(\d{4})\.(\d{1,2})\.(\d{1,2})$"),
    re.compile(r"^(\d{4})年(\d{1,2})月(\d{1,2})日$"),
)

_TIME_PATTERN: Final = re.compile(r"^(\d{1,2}):(\d{2})$")


def parse_date(text: str) -> dt.date:
    """把用户手写的日期文本转成 `date`；认不出来就抛出 `ValidationError`。

    宽容在这里是有边界的：只认分隔符差异，不认相对日期。理由写在模块
    docstring 的第 1 条。**这条规则最终属于后端**，此处只是替身的最小实现。
    """
    raw = text.strip()
    for pattern in _DATE_PATTERNS:
        matched = pattern.match(raw)
        if matched is None:
            continue
        year, month, day = (int(part) for part in matched.groups())
        try:
            return dt.date(year, month, day)
        except ValueError as exc:
            raise ValidationError(f"日期「{raw}」不是一个真实存在的日期：{exc}") from exc

    raise ValidationError(f"日期「{raw}」无法识别")


def parse_time(text: str) -> dt.time | None:
    """把 `HH:MM` 转成 `time`；留空表示全天返回 `None`，否则抛 `ValidationError`。"""
    raw = text.strip()
    if not raw:
        return None

    matched = _TIME_PATTERN.match(raw)
    if matched is None:
        raise ValidationError(f"时间「{raw}」无法识别，请写成 09:30 这样")

    hour, minute = (int(part) for part in matched.groups())
    try:
        return dt.time(hour, minute)
    except ValueError as exc:
        raise ValidationError(f"时间「{raw}」不是一个真实存在的时间：{exc}") from exc


def _clean_fields(
    title: str,
    date_text: str,
    time_text: str,
    notes: str,
) -> tuple[str, dt.date, dt.time | None, str]:
    """校验四个字段并返回干净值；任何一条不合法就地抛 `ValidationError`。

    校验规则按 T-04 的暂定值（标题 100、备注 500），最终以契约为准。
    注意 `title` 的去空白：这是"标题是不是空的"的唯一判定口径。
    """
    clean_title = title.strip()
    if not clean_title:
        raise ValidationError("标题不能为空，也不能只有空格")
    if len(clean_title) > TITLE_LIMIT:
        raise ValidationError(f"标题太长了（{len(clean_title)} 字，最多 {TITLE_LIMIT} 字）")

    clean_notes = notes.strip()
    if len(clean_notes) > NOTES_LIMIT:
        raise ValidationError(f"备注太长了（{len(clean_notes)} 字，最多 {NOTES_LIMIT} 字）")

    return clean_title, parse_date(date_text), parse_time(time_text), clean_notes


def _sort_key(item: SimpleSchedule) -> tuple[dt.date, bool, dt.time, str]:
    """统一排序：日期升序、全天在前、再按时间与 id。"""
    return (item.date, item.time is not None, item.time or dt.time.min, item.id)


class DevStubScheduleService:
    """内存版服务：接口满足 `ScheduleServicePort`，数据只存在进程内存里。

    `seed_defaults` 可以造几条示例数据，方便截图——用**虚构日程**，
    不要把真实安排写进提交材料（第 6 节的要求）。
    """

    def __init__(self, seed: tuple[SimpleSchedule, ...] = ()) -> None:
        self._items: dict[str, SimpleSchedule] = {item.id: item for item in seed}

    # ------------------------------------------------------------ 端口六个方法

    def list_schedules(self, day: dt.date) -> list[SimpleSchedule]:
        """按日期查；无记录返回空列表而不是报错，由界面显示空状态。

        排序在这里做：`presenters.to_rows` 明确不排序（界面只照抄顺序），
        确定性排序由服务/仓储负责。全天日程（`time is None`）排在最前，
        再按 (时间, id) 排，保证同样的输入永远同样的顺序。
        """
        same_day = [item for item in self._items.values() if item.date == day]
        return sorted(same_day, key=_sort_key)

    def count_by_date(self, start: dt.date, end: dt.date) -> dict[dt.date, int]:
        """扫描内存，返回闭区间 `[start, end]` 内每个有日程的日期及条数。"""
        counts: dict[dt.date, int] = {}
        for item in self._items.values():
            if start <= item.date <= end:
                counts[item.date] = counts.get(item.date, 0) + 1
        return counts

    def search_schedules(self, text: str) -> list[SimpleSchedule]:
        """按标题或备注包含搜索；空查询返回空列表，`%`/`_`/`\\` 按字面量匹配。"""
        needle = text.strip().casefold()
        if not needle:
            return []
        matches = [
            item
            for item in self._items.values()
            if needle in item.title.casefold() or needle in item.notes.casefold()
        ]
        return sorted(matches, key=_sort_key)

    def create_schedule(
        self,
        title: str,
        date_text: str,
        time_text: str,
        notes: str,
    ) -> SimpleSchedule:
        clean_title, day, at, clean_notes = _clean_fields(title, date_text, time_text, notes)
        created = SimpleSchedule(
            id=str(uuid.uuid4()),
            title=clean_title,
            date=day,
            time=at,
            notes=clean_notes,
        )
        self._items[created.id] = created
        return created

    def update_schedule(
        self,
        schedule_id: str,
        title: str,
        date_text: str,
        time_text: str,
        notes: str,
    ) -> SimpleSchedule:
        existing = self._items.get(schedule_id)
        if existing is None:
            raise ScheduleNotFound(f"这条日程已经不在列表里了（{schedule_id}）")

        clean_title, day, at, clean_notes = _clean_fields(title, date_text, time_text, notes)
        updated = replace(existing, title=clean_title, date=day, time=at, notes=clean_notes)
        self._items[schedule_id] = updated
        return updated

    def delete_schedule(self, schedule_id: str) -> None:
        if schedule_id not in self._items:
            raise ScheduleNotFound(f"这条日程已经不在列表里了（{schedule_id}）")
        del self._items[schedule_id]

    # ---------------------------------------------------------------- 便于演示

    def seed_defaults(self, today: dt.date) -> None:
        """放几条虚构日程，让第一屏不是空的。

        刻意分布在今天与相邻几天：这样"有日程的日期在日历上有标记"这条也能被看到，
        而不是截一张空图。
        """
        samples = (
            (0, "08:30", "晨读英语", "第 3 单元单词"),
            (0, "14:00", "数据结构习题课", "带上机报告"),
            (0, "19:30", "小组周会", "讨论接口对接"),
            (1, "10:00", "数据库实验", ""),
            (3, "15:00", "体育测试补测", "操场东侧集合"),
        )
        for offset, time_text, title, notes in samples:
            day = today + dt.timedelta(days=offset)
            self.create_schedule(title, day.isoformat(), time_text, notes)

    def count_all(self) -> int:
        """替身特有的辅助方法，便于测试和截图脚本断言数据量。"""
        return len(self._items)


__all__ = [
    "NOTES_LIMIT",
    "TITLE_LIMIT",
    "DevStubScheduleService",
    "ScheduleNotFound",
    "SimpleSchedule",
    "StorageError",
    "ValidationError",
    "parse_date",
    "parse_time",
]
