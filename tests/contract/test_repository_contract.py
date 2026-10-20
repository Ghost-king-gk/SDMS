"""存储契约测试。"""

import sqlite3
from collections.abc import Iterator
from datetime import date, time

import pytest

from schedule_management.application.contracts import ScheduleRepository
from schedule_management.application.errors import DuplicateScheduleError
from schedule_management.domain.schedule import Schedule, new_schedule_id
from schedule_management.infrastructure.sqlite_repository import SqliteScheduleRepository
from tests.fakes import InMemoryScheduleRepository

DAY = date(2026, 10, 14)


def make_schedule(
    *,
    title: str = "买菜",
    day: date = DAY,
    at: time | None = time(9, 30),
    notes: str = "",
) -> Schedule:
    return Schedule(id=new_schedule_id(), title=title, date=day, time=at, notes=notes)


@pytest.fixture(params=["memory", "sqlite"])
def repo(request: pytest.FixtureRequest) -> Iterator[ScheduleRepository]:
    if request.param == "memory":
        yield InMemoryScheduleRepository()
    else:
        connection = sqlite3.connect(":memory:")
        try:
            yield SqliteScheduleRepository(connection)
        finally:
            connection.close()


def test_add_then_get_returns_same_schedule(repo: ScheduleRepository) -> None:
    schedule = make_schedule()
    repo.add(schedule)
    assert repo.get(schedule.id) == schedule


def test_add_duplicate_raises_and_keeps_original(repo: ScheduleRepository) -> None:
    schedule = make_schedule()
    repo.add(schedule)
    with pytest.raises(DuplicateScheduleError):
        repo.add(schedule)
    assert repo.get(schedule.id) == schedule


def test_get_missing_returns_none(repo: ScheduleRepository) -> None:
    assert repo.get("no-such-id") is None


def test_list_by_date_only_returns_that_day(repo: ScheduleRepository) -> None:
    same_day = make_schedule(title="同一天")
    other_day = make_schedule(title="另一天", day=date(2026, 10, 15))
    repo.add(same_day)
    repo.add(other_day)
    result = repo.list_by_date(DAY)
    assert [item.id for item in result] == [same_day.id]


def test_list_by_date_sorted_by_time_then_id(repo: ScheduleRepository) -> None:
    later = make_schedule(title="较晚", at=time(18, 0))
    earlier = make_schedule(title="较早", at=time(8, 0))
    repo.add(later)
    repo.add(earlier)
    result = repo.list_by_date(DAY)
    assert [item.id for item in result] == [earlier.id, later.id]


def test_list_by_date_same_time_sorted_by_id(repo: ScheduleRepository) -> None:
    """同一时刻的记录按 id 升序排列，覆盖 ORDER BY time, id 的次级排序。"""
    second = Schedule(id="b", title="乙", date=DAY, time=time(9, 30))
    first = Schedule(id="a", title="甲", date=DAY, time=time(9, 30))
    repo.add(second)
    repo.add(first)
    result = repo.list_by_date(DAY)
    assert [item.id for item in result] == ["a", "b"]


def test_all_day_schedule_round_trips(repo: ScheduleRepository) -> None:
    all_day = make_schedule(title="全天的事", at=None)
    repo.add(all_day)

    assert repo.get(all_day.id) == all_day
    assert repo.list_by_date(DAY) == [all_day]


def test_all_day_schedules_sort_before_timed_ones(repo: ScheduleRepository) -> None:
    """全天日程没有具体时刻，排在同日 timed 之前，符合日历从上到下的阅读顺序。"""
    early = make_schedule(title="清晨", at=time(0, 0))
    all_day = make_schedule(title="全天", at=None)
    late = make_schedule(title="深夜", at=time(23, 59))
    for schedule in (late, early, all_day):
        repo.add(schedule)

    result = repo.list_by_date(DAY)
    assert [item.id for item in result] == [all_day.id, early.id, late.id]


def test_count_by_date_uses_closed_interval(repo: ScheduleRepository) -> None:
    before = make_schedule(day=date(2026, 10, 13))
    start = make_schedule(day=date(2026, 10, 14))
    end = make_schedule(day=date(2026, 10, 16))
    also_start = make_schedule(day=date(2026, 10, 14))
    after = make_schedule(day=date(2026, 10, 17))
    for schedule in (before, start, end, also_start, after):
        repo.add(schedule)

    assert repo.count_by_date(date(2026, 10, 14), date(2026, 10, 16)) == {
        start.date: 2,
        end.date: 1,
    }


def test_count_by_date_empty_interval(repo: ScheduleRepository) -> None:
    repo.add(make_schedule(day=DAY))

    assert repo.count_by_date(date(2026, 10, 15), date(2026, 10, 20)) == {}
    assert repo.count_by_date(date(2026, 10, 15), DAY) == {}


def test_search_matches_title_or_notes(repo: ScheduleRepository) -> None:
    by_title = make_schedule(title="周报整理")
    by_notes = make_schedule(title="买牛奶", notes="顺便打印周报")
    unrelated = make_schedule(title="无关事项")
    for schedule in (by_title, by_notes, unrelated):
        repo.add(schedule)

    assert {item.id for item in repo.search_schedules("周报")} == {by_title.id, by_notes.id}


def test_search_treats_wildcards_literally(repo: ScheduleRepository) -> None:
    percent = make_schedule(title="完成 100%")
    underscore = make_schedule(title="a_b")
    backslash = make_schedule(title="back\\slash")
    plain = make_schedule(title="aXb")
    for schedule in (percent, underscore, backslash, plain):
        repo.add(schedule)

    assert [item.id for item in repo.search_schedules("%")] == [percent.id]
    assert [item.id for item in repo.search_schedules("_")] == [underscore.id]
    assert [item.id for item in repo.search_schedules("\\")] == [backslash.id]


def test_search_orders_by_date_then_all_day_then_time(repo: ScheduleRepository) -> None:
    later_day = make_schedule(title="搜索词", day=date(2026, 10, 16))
    early_all_day = make_schedule(title="搜索词", day=DAY, at=None)
    early_timed = make_schedule(title="搜索词", day=DAY, at=time(8, 0))
    for schedule in (later_day, early_timed, early_all_day):
        repo.add(schedule)

    assert [item.id for item in repo.search_schedules("搜索词")] == [
        early_all_day.id,
        early_timed.id,
        later_day.id,
    ]


def test_search_blank_query_returns_empty(repo: ScheduleRepository) -> None:
    repo.add(make_schedule(title="周报"))

    assert repo.search_schedules("") == []
    assert repo.search_schedules("   ") == []


def test_list_by_date_empty_when_no_records(repo: ScheduleRepository) -> None:
    assert repo.list_by_date(DAY) == []


def test_update_existing_returns_true_and_applies(repo: ScheduleRepository) -> None:
    schedule = make_schedule()
    repo.add(schedule)
    changed = Schedule(id=schedule.id, title="新标题", date=DAY, time=time(12, 0), notes="改过")
    assert repo.update(changed) is True
    assert repo.get(schedule.id) == changed


def test_update_missing_returns_false(repo: ScheduleRepository) -> None:
    ghost = make_schedule()
    assert repo.update(ghost) is False


def test_delete_existing_returns_true(repo: ScheduleRepository) -> None:
    schedule = make_schedule()
    repo.add(schedule)
    assert repo.delete(schedule.id) is True
    assert repo.get(schedule.id) is None


def test_delete_missing_returns_false(repo: ScheduleRepository) -> None:
    assert repo.delete("no-such-id") is False
