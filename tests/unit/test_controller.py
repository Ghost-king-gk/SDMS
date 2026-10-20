"""controller 的单测：用替身把 V-01~V-16 中可自动化的部分钉死。

这里断言的主角**不是数据对不对，而是"有没有调用服务、调用了几次"**。
最典型的是 V-10 与 V-11：列表看起来没变，并不代表服务没被调用过——
未选中就点删除、删除确认框点取消，都必须是 0 次。这类行为靠肉眼看界面
是看不出来的，只能靠调用计数。

另一条主线是 5.1 节的结论："界面不在前端拦截日期"。所以下面有两组成对用例：
能识别的写法与完全不能识别的写法，都必须原样抵达服务。
"""

from __future__ import annotations

import datetime as dt
import logging

import pytest

from schedule_management.ui.controller import ScheduleController
from schedule_management.ui.view_models import ScheduleDraft
from tests.unit.ui_fakes import (
    FakeMainView,
    FakeScheduleService,
    ScheduleNotFound,
    StorageError,
    StubSchedule,
    UnexpectedBoom,
    ValidationError,
)

TODAY = dt.date(2026, 10, 15)
TOMORROW = dt.date(2026, 10, 16)

ITEM_TODAY = StubSchedule(id="id-1", title="写周报", date=TODAY, time=dt.time(9, 30), notes="")
ITEM_LATER = StubSchedule(
    id="id-2", title="开组会", date=TODAY, time=dt.time(15, 0), notes="带上机"
)
ITEM_TOMORROW = StubSchedule(id="id-3", title="体检", date=TOMORROW, time=dt.time(8, 0))
ITEM_ALL_DAY = StubSchedule(id="id-4", title="休息", date=TODAY, time=None)


def build_controller(
    service: FakeScheduleService | None = None,
    view: FakeMainView | None = None,
    items: tuple[StubSchedule, ...] = (ITEM_TODAY, ITEM_LATER),
) -> tuple[ScheduleController, FakeScheduleService, FakeMainView]:
    """搭一套 controller + 替身。`clock` 固定为 2026-10-15，避免跨零点翻车。"""
    service = service if service is not None else FakeScheduleService(items)
    view = view if view is not None else FakeMainView()
    controller = ScheduleController(service, view, clock=lambda: TODAY)
    return controller, service, view


def a_draft(
    title: str = "买牛奶",
    date_text: str = "2026-10-15",
    time_text: str = "09:30",
    notes: str = "",
) -> ScheduleDraft:
    return ScheduleDraft(title=title, date_text=date_text, time_text=time_text, notes=notes)


# ------------------------------------------------------------------- 启动与列表


def test_start_shows_today_rows_with_count() -> None:
    controller, service, view = build_controller()

    controller.start()

    assert service.calls_of("list") == [("list", TODAY)]
    assert [row.schedule_id for row in view.last_rows] == ["id-1", "id-2"]
    assert view.counts[-1] == "共 2 条"
    assert view.selections[-1] == "未选中日程"


def test_start_on_empty_database_shows_empty_state_not_blank() -> None:
    controller, _service, view = build_controller(items=())

    controller.start()

    assert view.last_rows == (), "空库必须走空状态分支，不能什么都不推给界面"
    assert view.counts[-1] == "共 0 条"
    assert "还没有日程" in view.last_status


def test_switching_day_reloads_and_clears_selection() -> None:
    controller, service, view = build_controller(items=(ITEM_TODAY, ITEM_TOMORROW))
    controller.start()
    controller.select_row("id-1")
    assert controller.selected_id == "id-1"

    controller.select_day(TOMORROW)

    assert controller.selected_id is None, "换日期必须清空选中，否则会对着看不见的行操作"
    assert [row.schedule_id for row in view.last_rows] == ["id-3"]
    assert service.calls_of("list")[-1] == ("list", TOMORROW)


def test_refresh_reports_month_counts_to_view() -> None:
    """刷新列表后顺手把当月标记交给界面：日历靠它画底色与徽标。"""
    controller, service, view = build_controller(items=(ITEM_TODAY, ITEM_TOMORROW))

    controller.start()

    assert service.calls_of("count_by_date") == [
        ("count_by_date", dt.date(2026, 10, 1), dt.date(2026, 10, 31))
    ], "区间必须是当月首末日（闭区间），不能只查当天"
    assert view.month_counts[-1] == {TODAY: 1, TOMORROW: 1}


def test_load_month_counts_uses_closed_interval_and_reports_to_view() -> None:
    """闰年二月也要算准：2028-02 的末日是 29 号。"""
    controller, service, view = build_controller(items=())

    assert controller.load_month_counts(2028, 2) is True

    assert service.calls_of("count_by_date")[-1] == (
        "count_by_date",
        dt.date(2028, 2, 1),
        dt.date(2028, 2, 29),
    )
    assert view.month_counts[-1] == {}, "空月也要回一个空字典，界面才能清掉旧标记"


def test_load_month_counts_failure_returns_false_without_dialog() -> None:
    """翻月遇到存储故障：只记日志，不弹框，也不假装给了标记。"""
    service = FakeScheduleService(count_error=StorageError("数据库忙"))
    controller, _service, view = build_controller(service)

    assert controller.load_month_counts(2026, 10) is False

    assert view.errors == [], "翻月不该被存储故障打断"
    assert view.month_counts == []


def test_count_failure_does_not_turn_list_refresh_into_failure() -> None:
    """月度标记是辅助信息：查不到也不能把成功的列表刷新拖成失败。"""
    service = FakeScheduleService((ITEM_TODAY,), count_error=StorageError("汇总查询失败"))
    controller, _service, view = build_controller(service)

    controller.start()

    assert [row.schedule_id for row in view.last_rows] == ["id-1"]
    assert view.errors == [], "列表成功时不弹任何错误框"
    assert view.month_counts == []
    assert controller.refresh() is True


def test_load_month_counts_rejects_invalid_month() -> None:
    controller, service, view = build_controller()

    assert controller.load_month_counts(2026, 13) is False

    assert service.calls_of("count_by_date") == [], "参数不合法时不该去查库"
    assert view.errors == []


def test_rows_property_is_a_read_only_snapshot() -> None:
    controller, _service, _view = build_controller()
    controller.start()

    snapshot = controller.rows
    assert [row.schedule_id for row in snapshot] == ["id-1", "id-2"]
    assert isinstance(snapshot, tuple), "只读快照不能被外部 list 操作改动"


# ------------------------------------------------------------- V-10 / V-11 删除


def test_delete_without_selection_never_calls_service() -> None:
    """V-10：未选中点删除，整条链路零次服务调用。"""
    controller, service, view = build_controller()
    controller.start()
    calls_before = service.call_count

    controller.request_delete()

    assert service.call_count == calls_before, "除了启动时的查询不应有任何调用"
    assert service.calls_of("delete") == []
    assert view.errors == [], "未选中是状态提醒，不是错误"
    assert len(view.infos) == 1 and "选中" in view.infos[0]


def test_delete_cancelled_confirmation_never_calls_service() -> None:
    """V-11：确认框点了取消，`delete` 一次都不能调用。"""
    service = FakeScheduleService((ITEM_TODAY,))
    view = FakeMainView(confirm_answer=False)
    controller, service, view = build_controller(service, view)
    controller.start()
    controller.select_row("id-1")

    controller.request_delete()

    assert view.confirmations == ["id-1"], "确认框必须先问过"
    assert service.calls_of("delete") == []
    assert view.last_status == "已取消，没有做任何改动"
    assert service.items, "数据不能被改"


def test_delete_with_cancel_still_calls_service_once_when_confirmed() -> None:
    """V-12：点确定才真的删，并且要带着 id 而不是行号或标题。"""
    controller, service, view = build_controller(items=(ITEM_TODAY,))
    controller.start()
    controller.select_row("id-1")

    controller.request_delete()

    assert service.calls_of("delete") == [("delete", "id-1")]
    assert view.last_rows == (), "删除后必须刷新列表"
    assert view.last_status == "已删除「写周报」"
    assert controller.selected_id is None


def test_delete_reports_backend_reason_when_record_is_gone() -> None:
    service = FakeScheduleService((ITEM_TODAY,), delete_error=ScheduleNotFound("日程已被删除"))
    controller, service, view = build_controller(service)
    controller.start()
    controller.select_row("id-1")

    controller.request_delete()

    headline, message = view.errors[-1]
    assert headline == "没有找到这条日程"
    assert "日程已被删除" in message, "要说后端给出的原因，不是界面自己编一句"
    assert view.last_rows, "失败不能刷新成空列表假装成功"


def test_stale_selection_is_reported_without_calling_service() -> None:
    """选中项已经不在列表里时（例如被别的路径删掉），只提醒、不调用服务。"""
    controller, service, _view = build_controller(items=(ITEM_TODAY,))
    controller.start()
    controller.select_row("ghost-id")
    assert controller.selected_id is None, "失效的选中应在未来列表同步时清理"

    controller.request_delete()

    assert service.calls_of("delete") == []


# ------------------------------------------------------------- 日期：界面不拦截


def test_create_forwards_raw_date_text_without_parsing() -> None:
    """V-04：认得出的写法原样到后端，界面不做任何处理。"""
    ok_draft = a_draft(date_text="2026/10/15")
    controller, service, view = build_controller(view=FakeMainView(form_results=(ok_draft,)))
    controller.start()

    controller.request_create()

    assert service.calls_of("create") == [("create", "买牛奶", "2026/10/15", "09:30", "")]
    assert view.last_status == "已新增「买牛奶」"


def test_create_forwards_unrecognizable_date_text_to_backend() -> None:
    """V-16：界面照发不误，把"认不认得出来"这件事留给后端。"""
    service = FakeScheduleService(create_error=ValidationError("无法识别的日期：明天"))
    controller, service, view = build_controller(
        service, FakeMainView(form_results=(a_draft(date_text="明天"), None))
    )
    controller.start()

    controller.request_create()

    assert service.calls_of("create")[0][2] == "明天", "界面不能替后端先判一次"
    headline, message = view.errors[-1]
    assert headline == "无法保存"
    assert "无法识别的日期：明天" in message
    assert headline != "日期格式不正确", "不能再回到前端先拦一道的老说法"


def test_failed_save_reopens_form_with_previous_values() -> None:
    """写入失败要保留已填内容：第二次打开表单必须带着上一次的草稿。"""
    draft = a_draft(title="改周报", time_text="20:00", notes="别忘了")
    service = FakeScheduleService(create_error=ValidationError("标题去除空格后为空"))
    controller, _service, view = build_controller(service, FakeMainView(form_results=(draft, None)))
    controller.start()

    controller.request_create()

    assert len(view.form_requests) == 2, "失败后要再开一次表单"
    second = view.form_requests[1]
    assert second.initial == draft, "已填内容必须还给用户"
    assert view.last_status == "已取消，没有做任何改动"


def test_cancelled_form_does_not_touch_service() -> None:
    controller, service, view = build_controller(view=FakeMainView(form_results=(None,)))
    controller.start()
    calls_before = service.call_count

    controller.request_create()

    assert service.call_count == calls_before, "取消表单不能产生任何写入调用"
    assert view.last_status == "已取消，没有做任何改动"


def test_create_for_day_prefills_date_and_forwards_it_verbatim() -> None:
    """双击日历某天：表单预填该日期，其余字段留空；保存时日期文本原样交给后端。"""
    draft = a_draft(date_text="2026-10-15")
    controller, service, view = build_controller(view=FakeMainView(form_results=(draft,)))
    controller.start()

    controller.request_create_for_day(TODAY)

    request = view.form_requests[0]
    assert request.mode == "create"
    assert request.heading == "新增日程"
    assert request.initial is not None
    assert request.initial.date_text == "2026-10-15"
    assert request.initial.title == ""
    assert request.initial.time_text == ""
    assert request.initial.notes == ""
    assert service.calls_of("create") == [("create", "买牛奶", "2026-10-15", "09:30", "")]
    assert view.last_status == "已新增「买牛奶」"


# --------------------------------------------------------------------- 修改与查看


def test_edit_without_selection_never_calls_service() -> None:
    controller, service, view = build_controller()
    controller.start()

    controller.request_edit()

    assert service.calls_of("update") == []
    assert len(view.infos) == 1


def test_edit_prefills_from_row_and_calls_update_with_id() -> None:
    controller, service, view = build_controller(
        view=FakeMainView(form_results=(a_draft(title="写周报（终稿）"),))
    )
    controller.start()
    controller.select_row("id-1")

    controller.request_edit()

    first = view.form_requests[0]
    assert first.mode == "edit"
    assert first.initial is not None and first.initial.time_text == "09:30"
    assert first.initial is not None and first.initial.date_text == "2026-10-15"
    update_call = service.calls_of("update")[0]
    assert update_call[1] == "id-1", "必须按 id 修改，标题会重复"
    assert update_call[2] == "写周报（终稿）"
    assert view.last_status == "已修改「写周报（终稿）」"


def test_edit_prefills_all_day_with_empty_time_then_saves_it_empty() -> None:
    """全天行显示“全天”，但表单里必须是空时间，否则保存会被服务层拒绝。"""
    controller, service, view = build_controller(
        items=(ITEM_ALL_DAY,),
        view=FakeMainView(form_results=(a_draft(title="休息一天", time_text=""),)),
    )
    controller.start()
    controller.select_row("id-4")

    controller.request_edit()

    first = view.form_requests[0]
    assert first.initial is not None
    assert first.initial.time_text == "", "“全天”只是展示文本，不能回填进时间输入框"
    assert service.calls_of("update") == [("update", "id-4", "休息一天", "2026-10-15", "", "")], (
        "提交时也必须把空时间原样交给服务层"
    )
    assert view.last_rows[0].time_text == "全天", "列表仍然显示“全天”"
    assert view.last_status == "已修改「休息一天」"


def test_updated_row_can_leave_current_day_list() -> None:
    """V-09：改到别的日期后，该条从当前列表消失是正常结果，不是 bug。"""
    controller, _service, view = build_controller(
        items=(ITEM_TODAY,),
        view=FakeMainView(form_results=(a_draft(date_text="2026-10-16"),)),
    )
    controller.start()
    controller.select_row("id-1")

    controller.request_edit()

    assert view.last_rows == (), "改到明天后当前日期下自然查不到"
    assert view.counts[-1] == "共 0 条"


def test_view_detail_uses_rows_without_extra_service_call() -> None:
    controller, service, view = build_controller()
    controller.start()
    controller.select_row("id-2")
    calls_before = service.call_count

    controller.request_view()

    assert service.call_count == calls_before, "列表刚查过，详情不必再查一次"
    assert [row.schedule_id for row in view.details] == ["id-2"]


# --------------------------------------------------------------------- 异常处理


def test_unexpected_exception_gives_generic_hint_only() -> None:
    service = FakeScheduleService(list_error=UnexpectedBoom("WindowsError: 句柄无效"))
    controller, _service, view = build_controller(service)

    controller.start()

    headline, message = view.errors[-1]
    assert headline == "操作没有完成"
    assert "句柄无效" not in message, "未预期的异常只进日志，不甩给用户"


def test_storage_error_points_at_the_data_file() -> None:
    service = FakeScheduleService(create_error=StorageError("数据库文件不可写"))
    controller, _service, view = build_controller(
        service, FakeMainView(form_results=(a_draft(), None))
    )
    controller.start()

    controller.request_create()

    headline, message = view.errors[-1]
    assert headline == "数据没能写入磁盘"
    assert "数据库文件不可写" in message
    assert "再试" in message, "异常提示必须带下一步，不能只说失败"


def test_refresh_returns_true_on_success() -> None:
    controller, _service, _view = build_controller()
    controller.start()

    assert controller.refresh() is True


def test_failed_refresh_keeps_last_good_rows() -> None:
    service = FakeScheduleService((ITEM_TODAY,))
    controller, service, view = build_controller(service)
    controller.start()
    good_rows = view.last_rows

    service.fail_next("list", StorageError("连接中断"))

    assert controller.refresh() is False, "查询失败必须让调用方知道，不能假装刷新成功"
    assert view.last_rows == good_rows, "刷新失败要保留上一次的数据，不能清空列表"
    assert view.errors[-1][0] == "数据没能写入磁盘"


def test_refresh_before_start_does_nothing() -> None:
    controller, service, _view = build_controller()

    assert controller.refresh() is False, "尚未 start 时没有筛选日期，只能返回失败"
    assert service.call_count == 0, "没有筛选日期时不该去查库"
    assert controller.current_day is None


def test_storage_error_cause_is_logged_as_warning(caplog: pytest.LogCaptureFixture) -> None:
    """已知的 StorageError 也要把真实原因（sqlite 锁、磁盘满等）留在日志里。"""
    cause = OSError("磁盘已满 /dev/sda1")
    service = FakeScheduleService(list_error=StorageError("读取日程失败", cause=cause))
    controller, _service, _view = build_controller(service)

    with caplog.at_level(logging.WARNING, logger="schedule_management.ui.controller"):
        controller.start()

    warnings = [record for record in caplog.records if record.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert "磁盘已满" in warnings[0].getMessage()
