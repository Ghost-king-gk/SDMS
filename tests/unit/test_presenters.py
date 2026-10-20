"""presenters 的单测：全部是纯函数，穷举文案与映射规则。

这组测试的意义是**把人工验收里最贵的部分搬到断言里**：GUI 的人工验收要开两台
机器、要点十几步；而"条数文案怎么说""错误提示长什么样"完全可以在这里穷举。
详见 `docs/figures/ui-interaction.md` 第 6 节对 V-01~V-17 的说明。
"""

from __future__ import annotations

import datetime as dt
from typing import cast

import pytest

from schedule_management.ui import presenters
from schedule_management.ui.ports import ScheduleLike
from schedule_management.ui.view_models import FormMode, ScheduleRow
from tests.unit.ui_fakes import (
    DuplicateScheduleError,
    ScheduleNotFound,
    StorageError,
    StubSchedule,
    UnexpectedBoom,
    ValidationError,
)

A_DAY = dt.date(2026, 10, 15)
A_TIME = dt.time(9, 5)
A_ROW = ScheduleRow(schedule_id="id-1", time_text="09:30", title_text="写周报", notes_text="")


def a_schedule(
    identifier: str = "id-1",
    title: str = "写周报",
    *,
    at: dt.time = A_TIME,
    notes: str = "给导师",
) -> ScheduleLike:
    """构造一个结构兼容的最小条目：不依赖尚未落地的领域类。"""
    return StubSchedule(id=identifier, title=title, date=A_DAY, time=at, notes=notes)


def test_format_date_pads_month_and_day() -> None:
    assert presenters.format_date(dt.date(2026, 1, 5)) == "2026-01-05"


def test_format_time_uses_minute_precision() -> None:
    assert presenters.format_time(A_TIME) == "09:05"
    assert presenters.format_time(dt.time(18, 0)) == "18:00"


def test_date_heading_carries_weekday() -> None:
    # 2026-10-15 是周四：这条断言同时兜住星期表的顺序（周一必须先出场）。
    assert presenters.date_heading(A_DAY) == "2026-10-15 周四"
    assert presenters.date_heading(dt.date(2026, 10, 19)) == "2026-10-19 周一"


def test_to_row_keeps_id_alongside_display_text() -> None:
    row = presenters.to_row(a_schedule())

    assert row.schedule_id == "id-1", "行必须携带 id，否则后续操作只能靠行号或标题反查"
    assert (row.time_text, row.title_text, row.notes_text) == ("09:05", "写周报", "给导师")


def test_to_rows_preserves_service_order() -> None:
    later = a_schedule("id-9", "下班打车", at=dt.time(23, 59), notes="")

    rows = presenters.to_rows([a_schedule(), later])

    assert [row.schedule_id for row in rows] == ["id-1", "id-9"], "排序由服务/仓储负责"
    assert [row.time_text for row in rows] == ["09:05", "23:59"]


@pytest.mark.parametrize("total", [0, 1, 2, 12])
def test_count_text_reports_zero_honestly(total: int) -> None:
    assert presenters.count_text(total) == f"共 {total} 条"


def test_selection_text_states_both_cases() -> None:
    assert presenters.selection_text(None) == "未选中日程"
    assert presenters.selection_text(A_ROW) == "已选中：09:30 写周报"


def test_ready_text_distinguishes_empty_state() -> None:
    assert "没有日程" in presenters.ready_text(0), "空状态要说清楚，不能留白"
    assert presenters.ready_text(3) == "就绪：共 3 条"


def test_saved_text_uses_backend_title() -> None:
    assert presenters.saved_text("create", "买牛奶") == "已新增「买牛奶」"
    assert presenters.saved_text("edit", "买牛奶") == "已修改「买牛奶」"


def test_saved_text_rejects_unknown_mode() -> None:
    """拼错的 mode 不能被静默当成“已修改”，否则状态栏会说反话。"""
    with pytest.raises(ValueError, match="archive"):
        presenters.saved_text(cast(FormMode, "archive"), "买牛奶")


def test_no_selection_text_is_a_reminder_not_an_error() -> None:
    assert "选中" in presenters.no_selection_text()


def test_error_category_knows_contract_names() -> None:
    assert presenters.error_category(ValidationError("标题不能为空")) == "ValidationError"
    assert presenters.error_category(ScheduleNotFound("id")) == "ScheduleNotFound"
    assert presenters.error_category(StorageError("db")) == "StorageError"


def test_duplicate_is_classified_before_its_storage_error_base() -> None:
    """DuplicateScheduleError 是 StorageError 子类，必须先命中 Duplicate。"""
    exc = DuplicateScheduleError("日程 ID 已存在：id-dup")

    assert isinstance(exc, StorageError), "替身必须继承 StorageError，才能验证判定顺序"
    assert presenters.error_category(exc) == "Duplicate"

    headline, message = presenters.describe_error(exc)
    # 文案不能暗示"内容重复"：该分类只表示存储层 ID 主键冲突
    assert headline == "保存冲突"
    assert "刷新" in message


def test_real_backend_error_classes_are_recognized() -> None:
    """真异常类落地后（PR #6 合流）按 isinstance 分类；本分支单独跑时跳过。"""
    errors = pytest.importorskip("schedule_management.application.errors")
    domain_errors = pytest.importorskip("schedule_management.domain.errors")

    assert presenters.error_category(errors.ScheduleNotFoundError("id")) == "ScheduleNotFound"
    assert presenters.error_category(errors.DuplicateScheduleError("dup")) == "Duplicate"
    assert presenters.error_category(errors.StorageError("db")) == "StorageError"
    assert presenters.error_category(domain_errors.ValidationError("bad")) == "ValidationError"


def test_error_category_falls_back_for_unknown_types() -> None:
    assert presenters.error_category(UnexpectedBoom("x")) == presenters.UNEXPECTED_CATEGORY
    assert presenters.error_category(RuntimeError("x")) == presenters.UNEXPECTED_CATEGORY


def test_describe_error_leads_with_backend_reason() -> None:
    headline, message = presenters.describe_error(ValidationError("标题去除空格后为空"))

    assert headline == "无法保存"
    assert message.startswith("标题去除空格后为空"), "提示必须以后端结论打头"
    assert "已经填写的内容都还在" in message, "还要给出能操作的下一步"


def test_describe_error_falls_back_when_backend_says_nothing() -> None:
    headline, message = presenters.describe_error(ValidationError())

    assert headline == "无法保存"
    assert message and "请检查标题" in message


def test_describe_error_hides_technical_detail_for_unexpected_errors() -> None:
    headline, message = presenters.describe_error(UnexpectedBoom("sqlite trace /secret/x.db"))

    assert headline == "操作没有完成"
    assert "/secret/x.db" not in message, "未预期的异常只能进日志，不能甩给用户"
    assert "诊断信息" in message


@pytest.mark.parametrize(
    "exc",
    [
        ScheduleNotFound("id-9"),
        StorageError("disk"),
        ValidationError("bad"),
    ],
)
def test_describe_error_never_returns_empty_text(exc: Exception) -> None:
    headline, message = presenters.describe_error(exc)

    assert headline and message
