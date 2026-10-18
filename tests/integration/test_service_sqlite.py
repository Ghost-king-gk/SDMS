"""服务层 + SQLite 组合根集成测试。"""

import sqlite3
from datetime import date, time
from pathlib import Path

import pytest

from schedule_management.application.errors import ScheduleNotFoundError, StorageError
from schedule_management.application.service import ScheduleService
from schedule_management.composition import build_service

DAY = date(2026, 10, 15)
NEXT_DAY = date(2026, 10, 16)


def test_service_persists_across_reopen(tmp_path: Path) -> None:
    """关闭连接后用新连接重建服务，数据仍在（V-14 的最小自动化版本）。"""
    db_path = tmp_path / "schedules.db"

    first_connection = sqlite3.connect(db_path)
    first_service = build_service(first_connection)
    morning = first_service.create_schedule("晨读", "2026-10-15", "9:05", "第 3 单元")
    evening = first_service.create_schedule("小组会", "2026/10/15", "18:00", "")
    assert [item.id for item in first_service.list_schedules(DAY)] == [morning.id, evening.id]
    first_connection.close()

    reopened = sqlite3.connect(db_path)
    try:
        service = build_service(reopened)
        restored = service.list_schedules(DAY)

        assert restored == [morning, evening]
        assert restored[0].time == time(9, 5)
        assert restored[0].notes == "第 3 单元"

        changed = service.update_schedule(
            morning.id, "晨读（改）", "2026.10.16", "10:00", "改到明天"
        )
        assert changed.id == morning.id
        assert service.list_schedules(DAY) == [evening]
        assert service.list_schedules(NEXT_DAY) == [changed]

        service.delete_schedule(evening.id)
        assert service.list_schedules(DAY) == []

        with pytest.raises(ScheduleNotFoundError, match="已经不在列表里"):
            service.delete_schedule(evening.id)
        with pytest.raises(ScheduleNotFoundError, match="no-such-id"):
            service.update_schedule("no-such-id", "幽灵", "2026-10-16", "11:00", "")
    finally:
        reopened.close()


def test_service_uses_injected_database_file(tmp_path: Path) -> None:
    """数据库位置由入口决定：服务只写传进来的连接，不在别处偷偷建库。"""
    db_path = tmp_path / "nested" / "custom.db"
    db_path.parent.mkdir()

    connection = sqlite3.connect(db_path)
    try:
        service = build_service(connection)
        service.create_schedule("只在指定文件里", "2026-10-15", "09:00", "")
    finally:
        connection.close()

    assert db_path.exists()
    reopened = sqlite3.connect(db_path)
    try:
        assert len(build_service(reopened).list_schedules(DAY)) == 1
    finally:
        reopened.close()


def test_storage_error_passes_through_from_sqlite(tmp_path: Path) -> None:
    """连接失效时仓储抛 StorageError，服务层不包装、不改类型。"""
    connection = sqlite3.connect(tmp_path / "schedules.db")
    service = build_service(connection)
    connection.close()

    with pytest.raises(StorageError, match="查询日程失败"):
        service.list_schedules(DAY)


def test_service_type_is_shared_by_composition_root(tmp_path: Path) -> None:
    connection = sqlite3.connect(tmp_path / "schedules.db")
    try:
        assert isinstance(build_service(connection), ScheduleService)
    finally:
        connection.close()
