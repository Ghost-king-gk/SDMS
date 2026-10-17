"""组合根：把基础设施实现注入应用层。

应用层只认识 ``ScheduleRepository`` 协议，不 import ``infrastructure``；
选择 SQLite 实现、决定数据库文件位置与连接所有权的责任集中在这里或入口脚本。
"""

from __future__ import annotations

import sqlite3

from schedule_management.application.service import ScheduleService
from schedule_management.infrastructure.sqlite_repository import SqliteScheduleRepository


def build_service(connection: sqlite3.Connection) -> ScheduleService:
    """用给定连接装配真实服务。

    连接归调用方所有：本函数不关闭它，数据库文件路径与生命周期由入口决定
    （见 ``docs/design/contracts.md``）。
    """
    return ScheduleService(SqliteScheduleRepository(connection))


__all__ = ["build_service"]
