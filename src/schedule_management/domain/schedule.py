"""日程领域对象与业务不变量。

本模块只表达"一条日程是什么、什么算有效"，不依赖界面或存储。
"""

import uuid
from dataclasses import dataclass
from datetime import date, time

from schedule_management.domain.errors import ValidationError


@dataclass(frozen=True)
class Schedule:
    """一条有效的日程记录。

    属性：
        id: 稳定标识，文本形式，修改时保持不变。
        title: 标题，去除首尾空白后非空。
        date: 本地朴素日期。
        time: 本地朴素时间，分钟精度。
        notes: 备注，允许为空字符串。
    """

    id: str
    title: str
    date: date
    time: time
    notes: str = ""

    def __post_init__(self) -> None:
        # 冻结数据类不能直接赋值，改用 object.__setattr__ 写入归一化结果。
        object.__setattr__(self, "title", self.title.strip())
        if not self.title:
            raise ValidationError("日程标题不能为空")
        if not self.id.strip():
            raise ValidationError("日程 ID 不能为空")


def new_schedule_id() -> str:
    """生成新的日程标识（UUID 文本）。"""
    return str(uuid.uuid4())
