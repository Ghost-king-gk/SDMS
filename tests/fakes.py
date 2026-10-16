"""测试专用内存存储。"""

from datetime import date

from schedule_management.application.errors import DuplicateScheduleError
from schedule_management.domain.schedule import Schedule


class InMemoryScheduleRepository:

    def __init__(self) -> None:
        self._store: dict[str, Schedule] = {}

    def add(self, schedule: Schedule) -> None:
        if schedule.id in self._store:
            raise DuplicateScheduleError(f"日程 ID 已存在：{schedule.id}")
        self._store[schedule.id] = schedule

    def get(self, schedule_id: str) -> Schedule | None:
        return self._store.get(schedule_id)

    def list_by_date(self, day: date) -> list[Schedule]:
        items = [schedule for schedule in self._store.values() if schedule.date == day]
        return sorted(items, key=lambda schedule: (schedule.time, schedule.id))

    def update(self, schedule: Schedule) -> bool:
        if schedule.id not in self._store:
            return False
        self._store[schedule.id] = schedule
        return True

    def delete(self, schedule_id: str) -> bool:
        if schedule_id not in self._store:
            return False
        del self._store[schedule_id]
        return True
