"""测试专用内存存储。"""

from datetime import date, time

from schedule_management.application.errors import DuplicateScheduleError
from schedule_management.domain.schedule import Schedule


def sort_key(schedule: Schedule) -> tuple[date, bool, time, str]:
    """与 SQLite 仓储一致的排序键：日期、全天在前、时间、id。"""
    return (schedule.date, schedule.time is not None, schedule.time or time.min, schedule.id)


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
        return sorted(items, key=sort_key)

    def count_by_date(self, start: date, end: date) -> dict[date, int]:
        counts: dict[date, int] = {}
        for schedule in self._store.values():
            if start <= schedule.date <= end:
                counts[schedule.date] = counts.get(schedule.date, 0) + 1
        return counts

    def search_schedules(self, text: str) -> list[Schedule]:
        needle = text.strip().casefold()
        if not needle:
            return []
        matches = [
            schedule
            for schedule in self._store.values()
            if needle in schedule.title.casefold() or needle in schedule.notes.casefold()
        ]
        return sorted(matches, key=sort_key)

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
