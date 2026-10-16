"""存储契约测试。

让内存实现与 SQLite 实现运行同一套行为断言，确保两者行为一致、可以互换。
"""

import sqlite3
from datetime import date, time

import pytest

from schedule_management.application.errors import DuplicateScheduleError
from schedule_management.domain.schedule import Schedule, new_schedule_id
from schedule_management.infrastructure.sqlite_repository import SqliteScheduleRepository
from tests.fakes import InMemoryScheduleRepository

DAY = date(2026, 10, 14)


def make_schedule(
    *,
    title: str = "买菜",
    day: date = DAY,
    at: time = time(9, 30),
    notes: str = "",
) -> Schedule:
    """构造一条合法日程，每次使用全新 ID。"""
    return Schedule(id=new_schedule_id(), title=title, date=day, time=at, notes=notes)


@pytest.fixture(params=["memory", "sqlite"])
def repo(request):
    """分别用内存和 SQLite 实现运行同一套测试。"""
    if request.param == "memory":
        yield InMemoryScheduleRepository()
    else:
        connection = sqlite3.connect(":memory:")
        try:
            yield SqliteScheduleRepository(connection)
        finally:
            connection.close()


def test_add_then_get_returns_same_schedule(repo):
    schedule = make_schedule()
    repo.add(schedule)
    assert repo.get(schedule.id) == schedule


def test_add_duplicate_raises_and_keeps_original(repo):
    schedule = make_schedule()
    repo.add(schedule)
    with pytest.raises(DuplicateScheduleError):
        repo.add(schedule)
    assert repo.get(schedule.id) == schedule


def test_get_missing_returns_none(repo):
    assert repo.get("no-such-id") is None


def test_list_by_date_only_returns_that_day(repo):
    same_day = make_schedule(title="同一天")
    other_day = make_schedule(title="另一天", day=date(2026, 10, 15))
    repo.add(same_day)
    repo.add(other_day)
    result = repo.list_by_date(DAY)
    assert [item.id for item in result] == [same_day.id]


def test_list_by_date_sorted_by_time_then_id(repo):
    later = make_schedule(title="较晚", at=time(18, 0))
    earlier = make_schedule(title="较早", at=time(8, 0))
    repo.add(later)
    repo.add(earlier)
    result = repo.list_by_date(DAY)
    assert [item.id for item in result] == [earlier.id, later.id]


def test_list_by_date_empty_when_no_records(repo):
    assert repo.list_by_date(DAY) == []


def test_update_existing_returns_true_and_applies(repo):
    schedule = make_schedule()
    repo.add(schedule)
    changed = Schedule(
        id=schedule.id, title="新标题", date=DAY, time=time(12, 0), notes="改过"
    )
    assert repo.update(changed) is True
    assert repo.get(schedule.id) == changed


def test_update_missing_returns_false(repo):
    ghost = make_schedule()
    assert repo.update(ghost) is False


def test_delete_existing_returns_true(repo):
    schedule = make_schedule()
    repo.add(schedule)
    assert repo.delete(schedule.id) is True
    assert repo.get(schedule.id) is None


def test_delete_missing_returns_false(repo):
    assert repo.delete("no-such-id") is False
