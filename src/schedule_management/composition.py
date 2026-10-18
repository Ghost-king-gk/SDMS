"""组合根：把基础设施实现注入应用层。

应用层只认识 ``ScheduleRepository`` 协议，不 import ``infrastructure``；
选择 SQLite 实现、决定数据库文件位置与连接所有权的责任集中在这里或入口脚本。
"""

from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

from schedule_management.application.service import ScheduleService
from schedule_management.infrastructure.sqlite_repository import SqliteScheduleRepository


def default_database_path() -> Path:
    """返回当前平台的默认数据库路径；父目录不一定存在，由 :func:`connect` 创建。

    - Windows：``%LOCALAPPDATA%\\sdms\\schedules.db``，未设置时用 ``~/AppData/Local``；
    - macOS：``~/Library/Application Support/sdms/schedules.db``；
    - 其他：``$XDG_DATA_HOME/sdms/schedules.db``，未设置时用 ``~/.local/share``。

    默认路径只属于组合根；``application`` 层不感知文件系统位置。
    """
    if sys.platform == "win32":
        local_app_data = os.environ.get("LOCALAPPDATA")
        root = Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local"
    elif sys.platform == "darwin":
        root = Path.home() / "Library" / "Application Support"
    else:
        data_home = os.environ.get("XDG_DATA_HOME")
        root = Path(data_home) if data_home else Path.home() / ".local" / "share"
    return root / "sdms" / "schedules.db"


def connect(path: Path | None = None) -> sqlite3.Connection:
    """打开数据库连接并返回；``path`` 为空时使用 :func:`default_database_path`。

    自动创建父目录，``timeout=5.0`` 秒用于等待写锁。连接归调用方所有：
    本函数不关闭连接，也不装配服务；入口负责在 ``finally`` 中关闭。
    """
    db_path = default_database_path() if path is None else path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(db_path, timeout=5.0)


def build_service(connection: sqlite3.Connection) -> ScheduleService:
    """用给定连接装配真实服务。

    连接归调用方所有：本函数不关闭它，数据库文件路径与生命周期由入口决定
    （见 ``docs/design/contracts.md``）。
    """
    return ScheduleService(SqliteScheduleRepository(connection))


__all__ = ["build_service", "connect", "default_database_path"]
