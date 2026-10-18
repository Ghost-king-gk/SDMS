"""SQLite 存储集成测试。"""

import sqlite3
from contextlib import closing
from datetime import date, time
from pathlib import Path

import pytest

from schedule_management.application.errors import DuplicateScheduleError, StorageError
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
    return Schedule(id=new_schedule_id(), title=title, date=day, time=at, notes=notes)


def test_schedule_survives_reopen(tmp_path: Path) -> None:
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


def test_duplicate_add_keeps_original(tmp_path: Path) -> None:
    """重复 ID 的写入被拒绝（回滚），原记录保持完好。"""
    connection = sqlite3.connect(tmp_path / "schedule.db")
    repo = SqliteScheduleRepository(connection)
    schedule = make_schedule()
    repo.add(schedule)

    with pytest.raises(DuplicateScheduleError):
        repo.add(schedule)

    assert repo.get(schedule.id) == schedule
    connection.close()


def test_update_persists_across_reopen(tmp_path: Path) -> None:
    """修改结果在重启后同样保留。"""
    db_path = tmp_path / "schedule.db"

    connection = sqlite3.connect(db_path)
    repo = SqliteScheduleRepository(connection)
    schedule = make_schedule()
    repo.add(schedule)
    changed = Schedule(id=schedule.id, title="新标题", date=DAY, time=time(12, 0), notes="改过")
    assert repo.update(changed) is True
    connection.close()

    reopened = sqlite3.connect(db_path)
    reopened_repo = SqliteScheduleRepository(reopened)
    restored = reopened_repo.get(schedule.id)
    reopened.close()

    assert restored == changed


def test_connection_row_factory_is_not_modified(tmp_path: Path) -> None:
    """仓储只在游标上设置 Row 工厂，不改变调用方连接的状态。"""
    with closing(sqlite3.connect(tmp_path / "schedule.db")) as connection:
        assert connection.row_factory is None
        repo = SqliteScheduleRepository(connection)
        assert connection.row_factory is None
        schedule = make_schedule()
        repo.add(schedule)
        assert repo.get(schedule.id) == schedule
        assert repo.list_by_date(DAY) == [schedule]
        assert connection.row_factory is None


def test_date_index_exists(tmp_path: Path) -> None:
    with closing(sqlite3.connect(tmp_path / "schedule.db")) as connection:
        SqliteScheduleRepository(connection)
        row = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'index' AND name = 'idx_schedules_date'"
        ).fetchone()
    assert row == ("idx_schedules_date",)


def test_get_corrupted_date_raises_storage_error(tmp_path: Path) -> None:
    """坏行不能被 ValueError 穿透，必须转换成 StorageError。"""
    with closing(sqlite3.connect(tmp_path / "schedule.db")) as connection:
        repo = SqliteScheduleRepository(connection)
        connection.execute(
            "INSERT INTO schedules (id, title, date, time, notes) VALUES (?, ?, ?, ?, ?)",
            ("bad-date", "坏行", "2026-13-45", "09:30:00", ""),
        )
        connection.commit()

        with pytest.raises(StorageError, match="存储中的日程数据无法解析"):
            repo.get("bad-date")


def test_list_by_date_corrupted_time_raises_storage_error(tmp_path: Path) -> None:
    """按日期查询遇到坏行时同样转换成 StorageError。"""
    with closing(sqlite3.connect(tmp_path / "schedule.db")) as connection:
        repo = SqliteScheduleRepository(connection)
        connection.execute(
            "INSERT INTO schedules (id, title, date, time, notes) VALUES (?, ?, ?, ?, ?)",
            ("bad-time", "坏行", DAY.isoformat(), "09:99:99", ""),
        )
        connection.commit()

        with pytest.raises(StorageError, match="存储中的日程数据无法解析"):
            repo.list_by_date(DAY)


def test_get_blank_title_row_raises_storage_error(tmp_path: Path) -> None:
    """违反领域不变量的坏行也属于数据损坏，不能以 ValidationError 穿透。"""
    with closing(sqlite3.connect(tmp_path / "schedule.db")) as connection:
        repo = SqliteScheduleRepository(connection)
        connection.execute(
            "INSERT INTO schedules (id, title, date, time, notes) VALUES (?, ?, ?, ?, ?)",
            ("bad-title", "   ", DAY.isoformat(), "09:30:00", ""),
        )
        connection.commit()

        with pytest.raises(StorageError, match="存储中的日程数据无法解析"):
            repo.get("bad-title")


def test_closed_connection_raises_storage_error(tmp_path: Path) -> None:
    """底层 sqlite3 错误统一转换成 StorageError。"""
    connection = sqlite3.connect(tmp_path / "schedule.db")
    repo = SqliteScheduleRepository(connection)
    connection.close()

    with pytest.raises(StorageError, match="读取日程失败"):
        repo.get("any-id")


def test_non_unique_integrity_error_becomes_storage_error(tmp_path: Path) -> None:
    """非 UNIQUE 约束冲突（如 notes 为 NULL）不能被误报成重复 ID。"""
    with closing(sqlite3.connect(tmp_path / "schedule.db")) as connection:
        repo = SqliteScheduleRepository(connection)
        schedule = make_schedule()
        object.__setattr__(schedule, "notes", None)

        with pytest.raises(StorageError, match="写入日程失败"):
            repo.add(schedule)
