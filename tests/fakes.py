"""测试专用内存存储。

用字典实现与 SQLite 适配器相同的 ScheduleRepository 契约，
供业务层单元测试和契约测试使用，避免每次测试都创建数据库文件。
"""

from datetime import date

from schedule_management.application.errors import DuplicateScheduleError
from schedule_management.domain.schedule import Schedule


class InMemoryScheduleRepository:
    """基于字典的内存存储，行为与 SQLite 适配器保持一致。

    注意：本类不继承 ScheduleRepository Protocol，因为继承 Protocol 的类
    无法实例化；它通过"实现相同方法"满足结构类型，由契约测试验证一致性。
    """

    def __init__(self) -> None:
        self._store: dict[str, Schedule] = {}

    def add(self, schedule: Schedule) -> None:
        """新增日程；ID 已存在时报告存储冲突，不覆盖原记录。"""
        if schedule.id in self._store:
            raise DuplicateScheduleError(f"日程 ID 已存在：{schedule.id}")
        self._store[schedule.id] = schedule

    def get(self, schedule_id: str) -> Schedule | None:
        """按 ID 查询；不存在返回 None。"""
        return self._store.get(schedule_id)

    def list_by_date(self, day: date) -> list[Schedule]:
        """返回指定日期的全部日程，按 time、id 确定性排序。"""
        items = [schedule for schedule in self._store.values() if schedule.date == day]
        return sorted(items, key=lambda schedule: (schedule.time, schedule.id))

    def update(self, schedule: Schedule) -> bool:
        """更新日程；找不到记录返回 False。"""
        if schedule.id not in self._store:
            return False
        self._store[schedule.id] = schedule
        return True

    def delete(self, schedule_id: str) -> bool:
        """删除日程；找不到记录返回 False。"""
        if schedule_id not in self._store:
            return False
        del self._store[schedule_id]
        return True
