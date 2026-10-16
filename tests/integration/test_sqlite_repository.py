"""SQLite 存储集成测试。

使用真实临时数据库文件，重点验证重启恢复与失败不破坏旧数据。
"""

import sqlite3
from datetime import date, time

import pytest

from schedule_management.application.errors import DuplicateScheduleError
from schedule_management.domain.schedule import Schedule, new_schedule_id
from schedule_management.infrastructure.sqlite_repository import SqliteScheduleRepository

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


def test_schedule_survives_reopen(tmp_path):
    """关闭并重新打开同一个数据库文件后，数据仍然存在。

    关键在于先 close 再 connect 同一个文件：只有这样才能证明数据真正落盘，
    而不是还留在连接的内存缓存里。
    """
    db_path = tmp_path / "schedule.db"

    first_connection = sqlite3.connect(db_path)
    first_repo = SqliteScheduleRepository(first_connection)
    schedule = make_schedule()
    first_repo.add(schedule)
    first_connection.close()

    second_connection = sqlite3.connect(db_path)
    second_repo = SqliteScheduleRepository(second_connection)
    restored = second_repo.get(schedule.id)
    second_connection.close()

    assert restored == schedule


def test_duplicate_add_keeps_original(tmp_path):
    """重复 ID 的写入被拒绝（回滚），原记录保持完好。"""
    connection = sqlite3.connect(tmp_path / "schedule.db")
    repo = SqliteScheduleRepository(connection)
    schedule = make_schedule()
    repo.add(schedule)

    with pytest.raises(DuplicateScheduleError):
        repo.add(schedule)

    assert repo.get(schedule.id) == schedule
    connection.close()


def test_update_persists_across_reopen(tmp_path):
    """修改结果在重启后同样保留。"""
    db_path = tmp_path / "schedule.db"

    connection = sqlite3.connect(db_path)
    repo = SqliteScheduleRepository(connection)
    schedule = make_schedule()
    repo.add(schedule)
    changed = Schedule(
        id=schedule.id, title="新标题", date=DAY, time=time(12, 0), notes="改过"
    )
    assert repo.update(changed) is True
    connection.close()

    reopened = sqlite3.connect(db_path)
    reopened_repo = SqliteScheduleRepository(reopened)
    restored = reopened_repo.get(schedule.id)
    reopened.close()

    assert restored == changed
