"""基础设施层：持久化等外部适配器。"""

from schedule_management.infrastructure.sqlite_repository import SqliteScheduleRepository

__all__ = ["SqliteScheduleRepository"]
