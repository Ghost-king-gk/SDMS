"""UI 单测专用的测试替身。**仅供测试使用，不属于交付源码。**

为什么单独一个文件：`tests/fakes.py` 按计划在 P06 归 xhy（仓储替身），
这里放的是界面自己的假服务和假窗口。两者分开，避免出现"UI 想加一个假对象
就得改别人的文件"这种互相阻塞。

假异常类的名字刻意与真实契约一致（`ValidationError` / `ScheduleNotFound` /
`StorageError`，外加作为 `StorageError` 子类的 `DuplicateScheduleError`）：
真类尚未落地时 `presenters.error_category` 按类名/MRO 兜底，用同名替身
才能真正覆盖到"已知错误走具体文案"这条路径。
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence
from dataclasses import dataclass

from schedule_management.ui.view_models import FormRequest, ScheduleDraft, ScheduleRow


class ValidationError(Exception):
    """替身：`domain/errors.py` 落地前的同名占位。"""


class ScheduleNotFound(Exception):  # noqa: N818 - 名字必须与契约草案一致，改名会失去替身的意义
    """替身：`application/errors.py` 落地前的同名占位。"""


class StorageError(Exception):
    """替身：`application/errors.py` 落地前的同名占位；保留真实类的 `cause`。"""

    def __init__(self, message: str, *, cause: BaseException | None = None) -> None:
        super().__init__(message)
        self.cause = cause


class DuplicateScheduleError(StorageError):
    """替身：真实 `DuplicateScheduleError` 是 `StorageError` 的子类。

    分类时必须先判它再判 `StorageError`，否则重复日程会被当成普通存储错误。
    """


class UnexpectedBoom(Exception):  # noqa: N818 - 故意不叫 Error，强调它是意料之外的类型
    """谁也没料到的异常，用来验证界面不会把它的细节甩给用户。"""


@dataclass(frozen=True)
class StubSchedule:
    """界面能接受的最小日程形状（对应 `ports.ScheduleLike`）。"""

    id: str
    title: str
    date: dt.date
    time: dt.time | None
    notes: str = ""


def _day_from(text: str) -> dt.date:
    """把常见写法转成日期。**这是假对象的解析，不代表真后端的能力。**

    UI 测试只需要一个"后端确实会收到原始字符串"的证据：这里识别几种分隔符，
    认不出来就按契约抛出 `ValidationError`。真实后端的宽松程度另由 P07 决定。
    """
    normalized = text.strip().replace("/", "-").replace(".", "-")
    normalized = normalized.replace("年", "-").replace("月", "-").replace("日", "")
    try:
        return dt.date.fromisoformat(normalized)
    except ValueError as exc:
        raise ValidationError(f"无法识别的日期：{text}") from exc


def _time_from(text: str) -> dt.time | None:
    normalized = text.strip().replace("：", ":")
    if not normalized:
        return None
    try:
        return dt.time.fromisoformat(normalized)
    except ValueError as exc:
        raise ValidationError(f"无法识别的时间：{text}") from exc


class FakeScheduleService:
    """服务替身：记录每一次调用，按脚本抛出下一次要抛的错。

    UI 断言的核心不是"数据对不对"，而是**调用过没有、调用了几次、参数是什么**——
    V-10 与 V-11 要的就是"0 次"，这类断言只能靠替身做，肉眼看列表看不出来。
    """

    def __init__(
        self,
        items: tuple[StubSchedule, ...] = (),
        *,
        list_error: Exception | None = None,
        count_error: Exception | None = None,
        create_error: Exception | None = None,
        update_error: Exception | None = None,
        delete_error: Exception | None = None,
        search_error: Exception | None = None,
        fail_list_on: dt.date | None = None,
    ) -> None:
        self._items: list[StubSchedule] = list(items)
        self._fail_list_on = fail_list_on
        self._errors = {
            "list": list_error,
            "count": count_error,
            "create": create_error,
            "update": update_error,
            "delete": delete_error,
            "search": search_error,
        }
        self.calls: list[tuple[object, ...]] = []

    # ---------------------------------------------------------- 断言用只读状态

    @property
    def call_count(self) -> int:
        return len(self.calls)

    def calls_of(self, name: str) -> list[tuple[object, ...]]:
        return [call for call in self.calls if call[0] == name]

    @property
    def items(self) -> tuple[StubSchedule, ...]:
        """当前存着的数据：删没删掉、改没改成，用它断言。"""
        return tuple(self._items)

    def fail_next(self, name: str, exc: Exception | None) -> None:
        """运行时替换下一次要抛的错，用来模拟"前一次成功、下一次失败"。"""
        self._errors[name] = exc

    # ---------------------------------------------------------------- 服务协议

    def list_schedules(self, day: dt.date) -> list[StubSchedule]:
        self.calls.append(("list", day))
        if self._errors["list"] is not None:
            raise self._errors["list"]
        if day == self._fail_list_on:
            raise StorageError(f"读取 {day} 的日程失败")
        return [item for item in self._items if item.date == day]

    def count_by_date(self, start: dt.date, end: dt.date) -> dict[dt.date, int]:
        self.calls.append(("count_by_date", start, end))
        if self._errors["count"] is not None:
            raise self._errors["count"]
        counts: dict[dt.date, int] = {}
        for item in self._items:
            if start <= item.date <= end:
                counts[item.date] = counts.get(item.date, 0) + 1
        return counts

    def search_schedules(self, text: str) -> list[StubSchedule]:
        self.calls.append(("search", text))
        if self._errors["search"] is not None:
            raise self._errors["search"]
        needle = text.strip().casefold()
        if not needle:
            return []
        return [
            item
            for item in self._items
            if needle in item.title.casefold() or needle in item.notes.casefold()
        ]

    def create_schedule(
        self, title: str, date_text: str, time_text: str, notes: str
    ) -> StubSchedule:
        self.calls.append(("create", title, date_text, time_text, notes))
        if self._errors["create"] is not None:
            raise self._errors["create"]
        item = StubSchedule(
            id=f"new-{len(self._items) + 1}",
            title=title,
            date=_day_from(date_text),
            time=_time_from(time_text),
            notes=notes,
        )
        self._items.append(item)
        return item

    def update_schedule(
        self,
        schedule_id: str,
        title: str,
        date_text: str,
        time_text: str,
        notes: str,
    ) -> StubSchedule:
        self.calls.append(("update", schedule_id, title, date_text, time_text, notes))
        if self._errors["update"] is not None:
            raise self._errors["update"]
        updated = StubSchedule(
            id=schedule_id,
            title=title,
            date=_day_from(date_text),
            time=_time_from(time_text),
            notes=notes,
        )
        self._items = [updated if item.id == schedule_id else item for item in self._items]
        if not any(item.id == schedule_id for item in self._items):
            raise ScheduleNotFound(f"日程 {schedule_id} 不存在")
        return updated

    def delete_schedule(self, schedule_id: str) -> None:
        self.calls.append(("delete", schedule_id))
        if self._errors["delete"] is not None:
            raise self._errors["delete"]
        remaining = [item for item in self._items if item.id != schedule_id]
        if len(remaining) == len(self._items):
            raise ScheduleNotFound(f"日程 {schedule_id} 不存在")
        self._items = remaining


class FakeMainView:
    """窗口替身：记录 controller 的每一次输出，并按脚本回答提问。

    `form_results` 是"用户每次表单会交回什么"的队列，取空之后一律返回 None
    （表示用户取消），避免测试里出现停不下来的重试循环；
    `confirm_answer` 固定删除确认的回答。
    """

    def __init__(
        self,
        *,
        confirm_answer: bool = True,
        form_results: tuple[ScheduleDraft | None, ...] = (),
    ) -> None:
        self.confirm_answer = confirm_answer
        self.rows: list[tuple[ScheduleRow, ...]] = []
        self.counts: list[str] = []
        self.search_states: list[tuple[str, int]] = []
        self.clear_search_calls = 0
        self.upcoming: list[tuple[ScheduleRow, ...]] = []
        self.month_counts: list[dict[dt.date, int]] = []
        self.selections: list[str] = []
        self.statuses: list[str] = []
        self.infos: list[str] = []
        self.errors: list[tuple[str, str]] = []
        self.details: list[ScheduleRow] = []
        self.confirmations: list[str] = []
        self.form_requests: list[FormRequest] = []
        self._form_results = list(form_results)

    # ---------------------------------------------------------- 断言用小工具

    @property
    def last_rows(self) -> tuple[ScheduleRow, ...]:
        return self.rows[-1] if self.rows else ()

    @property
    def last_status(self) -> str:
        return self.statuses[-1] if self.statuses else ""

    @property
    def last_form(self) -> FormRequest | None:
        return self.form_requests[-1] if self.form_requests else None

    # ------------------------------------------------------------ MainViewPort

    def show_rows(self, rows: Sequence[ScheduleRow]) -> None:
        self.rows.append(tuple(rows))

    def show_count(self, text: str) -> None:
        self.counts.append(text)

    def show_search_state(self, text: str, total: int) -> None:
        self.search_states.append((text, total))

    def clear_search(self) -> None:
        self.clear_search_calls += 1

    def show_upcoming(self, rows: Sequence[ScheduleRow]) -> None:
        self.upcoming.append(tuple(rows))

    def show_month_counts(self, counts: dict[dt.date, int]) -> None:
        self.month_counts.append(dict(counts))

    def show_selection(self, text: str) -> None:
        self.selections.append(text)

    def show_status(self, text: str) -> None:
        self.statuses.append(text)

    def show_info(self, message: str) -> None:
        self.infos.append(message)

    def show_error(self, headline: str, message: str) -> None:
        self.errors.append((headline, message))

    def show_detail(self, row: ScheduleRow) -> None:
        self.details.append(row)

    def ask_delete_confirm(self, row: ScheduleRow) -> bool:
        self.confirmations.append(row.schedule_id)
        return self.confirm_answer

    def open_schedule_form(self, request: FormRequest) -> ScheduleDraft | None:
        self.form_requests.append(request)
        if not self._form_results:
            return None
        return self._form_results.pop(0)
