"""应用层定义的存储契约。"""

from datetime import date
from typing import Protocol

from schedule_management.domain.schedule import Schedule


class ScheduleRepository(Protocol):
    def add(self, schedule: Schedule) -> None: ...

    def get(self, schedule_id: str) -> Schedule | None: ...

    def list_by_date(self, day: date) -> list[Schedule]: ...

    def update(self, schedule: Schedule) -> bool: ...

    def delete(self, schedule_id: str) -> bool: ...
