"""组合根测试：默认库路径与 ``connect`` 的建目录、连接归属行为。"""

import sqlite3
import sys
from datetime import date
from pathlib import Path

import pytest

from schedule_management import composition
from schedule_management.application.contracts import ScheduleUseCases

DAY = date(2026, 10, 15)


def test_default_path_windows_uses_localappdata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "LocalAppData"))

    assert composition.default_database_path() == (
        tmp_path / "LocalAppData" / "sdms" / "schedules.db"
    )


def test_default_path_windows_falls_back_to_home(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.delenv("LOCALAPPDATA", raising=False)

    assert composition.default_database_path() == (
        Path.home() / "AppData" / "Local" / "sdms" / "schedules.db"
    )


def test_default_path_macos_uses_application_support(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "darwin")

    assert composition.default_database_path() == (
        Path.home() / "Library" / "Application Support" / "sdms" / "schedules.db"
    )


def test_default_path_linux_uses_xdg_data_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))

    assert composition.default_database_path() == tmp_path / "xdg" / "sdms" / "schedules.db"


def test_default_path_linux_falls_back_to_local_share(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)

    assert composition.default_database_path() == (
        Path.home() / ".local" / "share" / "sdms" / "schedules.db"
    )


def test_connect_creates_parent_directories_and_persists(tmp_path: Path) -> None:
    db_path = tmp_path / "nested" / "data" / "schedules.db"
    assert not db_path.parent.exists()

    connection = composition.connect(db_path)
    try:
        assert isinstance(connection, sqlite3.Connection)
        service = composition.build_service(connection)
        assert isinstance(service, ScheduleUseCases)
        created = service.create_schedule("写周报", "2026/10/15", "9:05", "备注")
    finally:
        connection.close()

    assert db_path.exists()
    reopened = composition.connect(db_path)
    try:
        service = composition.build_service(reopened)
        assert service.list_schedules(DAY) == [created]
    finally:
        reopened.close()


def test_connect_without_argument_uses_default_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "default" / "schedules.db"
    monkeypatch.setattr(composition, "default_database_path", lambda: db_path)

    connection = composition.connect()
    try:
        assert isinstance(connection, sqlite3.Connection)
        assert db_path.exists()
    finally:
        connection.close()
