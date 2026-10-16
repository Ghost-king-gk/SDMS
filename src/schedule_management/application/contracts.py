"""应用层定义的存储契约。

任何实现（SQLite 适配器或测试用内存实现）都必须遵守本契约，
这样业务层可以在不关心具体存储的情况下读写日程。
"""

from datetime import date
from typing import Protocol

from schedule_management.domain.schedule import Schedule


class ScheduleRepository(Protocol):
    """日程存储契约。"""

    def add(self, schedule: Schedule) -> None:
        """新增日程；ID 已存在时报告存储冲突，不覆盖原记录。"""
        ...

    def get(self, schedule_id: str) -> Schedule | None:
        """按 ID 查询；不存在返回 None。"""
        ...

    def list_by_date(self, day: date) -> list[Schedule]:
        """返回指定日期的全部日程，按 time、id 确定性排序。"""
        ...

    def update(self, schedule: Schedule) -> bool:
        """更新日程；找不到记录返回 False。"""
        ...

    def delete(self, schedule_id: str) -> bool:
        """删除日程；找不到记录返回 False。"""
        ...
