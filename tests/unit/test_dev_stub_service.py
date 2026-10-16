"""开发替身服务的行为测试。

替身终究会被删掉，但此刻它扛着"界面能跑起来"的责任，而且它那份宽容解析是
T-02 的参考实现——解析规则写错，用户看到的错误提示就是错的。所以这几条值得测。

另一个目的是**结构性兼容**：替身返回的对象必须能直接被 `presenters` 处理，
否则"真后端落地后换一行注入"这句话就不成立。
"""

from __future__ import annotations

import datetime as dt

import pytest

from schedule_management.dev_stub_service import (
    NOTES_LIMIT,
    TITLE_LIMIT,
    DevStubScheduleService,
    ScheduleNotFound,
    ValidationError,
    parse_date,
    parse_time,
)
from schedule_management.ui import presenters

TODAY = dt.date(2026, 10, 15)


class TestDateParsing:
    """宽容解析：只认分隔符差异，不认相对日期。范围以 T-02 为准。"""

    @pytest.mark.parametrize(
        "text",
        ["2026-10-15", "2026/10/15", "2026.10.15", "2026年10月15日"],
    )
    def test_accepts_separator_variants(self, text: str) -> None:
        assert parse_date(text) == TODAY

    def test_strips_surrounding_whitespace(self) -> None:
        assert parse_date("  2026/10/15  ") == TODAY

    @pytest.mark.parametrize("text", ["明天", "下周三", "", "15/10/2026", "2026-13-01"])
    def test_rejects_what_it_cannot_read(self, text: str) -> None:
        with pytest.raises(ValidationError):
            parse_date(text)

    def test_rejects_nonexistent_day_in_february(self) -> None:
        with pytest.raises(ValidationError, match="真实存在"):
            parse_date("2026-02-30")

    def test_error_message_echoes_what_the_user_typed(self) -> None:
        """提示里要带上用户原话，否则用户不知道该改哪一处。"""
        with pytest.raises(ValidationError, match="明天"):
            parse_date("明天")


class TestTimeParsing:
    def test_accepts_minutes_precision(self) -> None:
        assert parse_time("09:05") == dt.time(9, 5)

    def test_pads_single_digit_hour(self) -> None:
        assert parse_time("9:05") == dt.time(9, 5)

    @pytest.mark.parametrize("text", ["25:00", "09:60", "9点05", ""])
    def test_rejects_out_of_range_or_unreadable(self, text: str) -> None:
        with pytest.raises(ValidationError):
            parse_time(text)


class TestServiceBehaviour:
    def test_created_item_is_usable_by_presenters(self) -> None:
        """替身返回的对象必须能直接喂给界面层，否则"换一行注入"是空话。"""
        service = DevStubScheduleService()
        created = service.create_schedule("小组周会", "2026/10/15", "19:30", "讨论对接")

        row = presenters.to_row(created)
        assert row.title_text == "小组周会"
        assert row.time_text == "19:30"
        assert row.schedule_id == created.id

    def test_list_returns_only_the_requested_day(self) -> None:
        service = DevStubScheduleService()
        service.create_schedule("今天的事", "2026-10-15", "08:00", "")
        service.create_schedule("明天的事", "2026-10-16", "08:00", "")

        assert [item.title for item in service.list_schedules(TODAY)] == ["今天的事"]

    def test_list_is_sorted_by_time_deterministically(self) -> None:
        """排序在这里做：presenters 明确不排序，界面只照抄顺序。"""
        service = DevStubScheduleService()
        service.create_schedule("晚上的事", "2026-10-15", "20:00", "")
        service.create_schedule("早上的事", "2026-10-15", "07:00", "")
        service.create_schedule("下午的事", "2026-10-15", "14:00", "")

        titles = [item.title for item in service.list_schedules(TODAY)]
        assert titles == ["早上的事", "下午的事", "晚上的事"]

    def test_empty_day_returns_empty_list_instead_of_raising(self) -> None:
        service = DevStubScheduleService()
        assert list(service.list_schedules(TODAY)) == []

    def test_update_keeps_the_same_id(self) -> None:
        service = DevStubScheduleService()
        created = service.create_schedule("原标题", "2026-10-15", "09:00", "")

        updated = service.update_schedule(created.id, "新标题", "2026/10/15", "10:00", "补充")

        assert updated.id == created.id
        assert updated.title == "新标题"
        assert updated.time == dt.time(10, 0)

    def test_update_moving_to_another_day_leaves_the_old_list(self) -> None:
        """改到别的日期后从当天列表移出是正常行为，不是 bug（5.4 节）。"""
        service = DevStubScheduleService()
        created = service.create_schedule("要搬家的事", "2026-10-15", "09:00", "")

        service.update_schedule(created.id, "要搬家的事", "2026-10-16", "09:00", "")

        assert list(service.list_schedules(TODAY)) == []

    def test_delete_removes_the_item(self) -> None:
        service = DevStubScheduleService()
        created = service.create_schedule("待删除", "2026-10-15", "09:00", "")
        service.delete_schedule(created.id)

        assert list(service.list_schedules(TODAY)) == []

    def test_missing_record_raises_the_contract_error_name(self) -> None:
        """异常类名必须与契约一致：界面按类名分类错误。"""
        service = DevStubScheduleService()
        with pytest.raises(ScheduleNotFound):
            service.delete_schedule("不存在的 id")

    def test_update_on_missing_record_raises_schedule_not_found(self) -> None:
        service = DevStubScheduleService()
        with pytest.raises(ScheduleNotFound):
            service.update_schedule("不存在的 id", "标题", "2026-10-15", "09:00", "")


class TestFieldValidation:
    def test_title_of_only_spaces_is_rejected(self) -> None:
        service = DevStubScheduleService()
        with pytest.raises(ValidationError, match="标题"):
            service.create_schedule("   ", "2026-10-15", "09:00", "")

    def test_title_is_stripped_before_saving(self) -> None:
        service = DevStubScheduleService()
        created = service.create_schedule("  带空格  ", "2026-10-15", "09:00", "")
        assert created.title == "带空格"

    def test_notes_may_be_empty(self) -> None:
        service = DevStubScheduleService()
        created = service.create_schedule("有标题就够", "2026-10-15", "09:00", "")
        assert created.notes == ""

    def test_overlong_title_is_rejected(self) -> None:
        service = DevStubScheduleService()
        with pytest.raises(ValidationError, match="标题太长"):
            service.create_schedule("字" * (TITLE_LIMIT + 1), "2026-10-15", "09:00", "")

    def test_overlong_notes_is_rejected(self) -> None:
        service = DevStubScheduleService()
        with pytest.raises(ValidationError, match="备注太长"):
            service.create_schedule("标题", "2026-10-15", "09:00", "字" * (NOTES_LIMIT + 1))


def test_seed_defaults_creates_items_across_several_days() -> None:
    """演示数据要跨几天，否则"日历上哪天有日程"这件事根本看不出来。"""
    service = DevStubScheduleService()
    service.seed_defaults(TODAY)

    assert service.count_all() == 5
    assert len(service.list_schedules(TODAY)) == 3
    assert len(service.list_schedules(TODAY + dt.timedelta(days=1))) == 1
