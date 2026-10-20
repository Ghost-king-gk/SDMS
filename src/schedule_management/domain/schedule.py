"""日程领域对象与业务不变量。

``time`` 允许为 ``None``，表示**全天日程**（用户没有填写具体时刻）；
非 ``None`` 时时间精度为分钟：构造 ``Schedule`` 时会把秒和微秒截断为 0，
与界面 ``HH:MM`` 的输入/显示格式保持一致，避免编辑往返时丢秒。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, time

from schedule_management.domain.errors import ValidationError


@dataclass(frozen=True)
class Schedule:
    id: str
    title: str
    date: date
    time: time | None = None
    notes: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", self.id.strip())
        object.__setattr__(self, "title", self.title.strip())
        if self.time is not None:
            object.__setattr__(self, "time", self.time.replace(second=0, microsecond=0))
        if not self.id:
            raise ValidationError("日程 ID 不能为空")
        if not self.title:
            raise ValidationError("日程标题不能为空")
        if not isinstance(self.notes, str):
            raise ValidationError("备注必须是文本")


def new_schedule_id() -> str:
    return str(uuid.uuid4())
