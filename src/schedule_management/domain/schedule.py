"""日程领域对象与业务不变量。"""

import uuid
from dataclasses import dataclass
from datetime import date, time

from schedule_management.domain.errors import ValidationError


@dataclass(frozen=True)
class Schedule:
    id: str
    title: str
    date: date
    time: time
    notes: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "title", self.title.strip())
        if not self.title:
            raise ValidationError("日程标题不能为空")
        if not self.id.strip():
            raise ValidationError("日程 ID 不能为空")


def new_schedule_id() -> str:
    return str(uuid.uuid4())
