"""日程服务层：把界面的四个用例翻译成仓储调用。

服务层是界面唯一该看到的业务入口：

- ``create/update`` 接收用户原样的日期、时间文本，解析与校验都在这里完成；
- 仓储契约用 ``bool`` 表达“有没有改到/删到”，服务层负责把 ``False``
  翻译成 :class:`ScheduleNotFoundError`，界面不需要理解 ``bool``；
- 仓储抛出的 :class:`DuplicateScheduleError` / :class:`StorageError` 原样透传，
  不在这里包成别的类型——界面按异常类型给提示，包一层会让分类失准。
"""

from __future__ import annotations

import datetime as dt

from schedule_management.application.contracts import ScheduleRepository, ScheduleUseCases
from schedule_management.application.errors import ScheduleNotFoundError
from schedule_management.application.parsing import validate
from schedule_management.domain.errors import ValidationError
from schedule_management.domain.schedule import Schedule, new_schedule_id

#: 按 id 找不到记录时给用户看的话术；界面会补一句“点刷新看看”。
_NOT_FOUND_TEMPLATE = "这条日程已经不在列表里了（{schedule_id}）"


def _require_schedule_id(schedule_id: str) -> str:
    """规范化传入的 id；空 id 是调用方的输入错误，不是“记录不存在”。"""
    clean_id = schedule_id.strip()
    if not clean_id:
        raise ValidationError("日程 ID 不能为空")
    return clean_id


class ScheduleService(ScheduleUseCases):
    """实现 ``application.contracts.ScheduleUseCases``；界面端口直接复用该协议。

    界面 ``ui/ports.py`` 应 ``from schedule_management.application.contracts import
    ScheduleUseCases`` 并把它设为 ``ScheduleServicePort``，不再维护第二份签名。
    """

    def __init__(self, repository: ScheduleRepository) -> None:
        self._repository = repository

    def list_schedules(self, day: dt.date) -> list[Schedule]:
        """返回 ``day`` 当天的全部日程；没有记录时返回空列表。

        排序由仓储负责（``ORDER BY time, id``），服务层不再排一遍。
        """
        return self._repository.list_by_date(day)

    def create_schedule(
        self,
        title: str,
        date_text: str,
        time_text: str,
        notes: str,
    ) -> Schedule:
        """新增一条日程并返回保存后的对象；id 由服务层生成。"""
        clean_title, day, at, clean_notes = validate(title, date_text, time_text, notes)
        schedule = Schedule(
            id=new_schedule_id(),
            title=clean_title,
            date=day,
            time=at,
            notes=clean_notes,
        )
        self._repository.add(schedule)
        return schedule

    def update_schedule(
        self,
        schedule_id: str,
        title: str,
        date_text: str,
        time_text: str,
        notes: str,
    ) -> Schedule:
        """全量更新一条日程，id 保持不变；记录不存在时抛 ``ScheduleNotFoundError``。"""
        clean_id = _require_schedule_id(schedule_id)
        clean_title, day, at, clean_notes = validate(title, date_text, time_text, notes)
        schedule = Schedule(
            id=clean_id,
            title=clean_title,
            date=day,
            time=at,
            notes=clean_notes,
        )
        if not self._repository.update(schedule):
            raise ScheduleNotFoundError(_NOT_FOUND_TEMPLATE.format(schedule_id=clean_id))
        return schedule

    def delete_schedule(self, schedule_id: str) -> None:
        """删除一条日程；记录不存在时抛 ``ScheduleNotFoundError``，不静默成功。"""
        clean_id = _require_schedule_id(schedule_id)
        if not self._repository.delete(clean_id):
            raise ScheduleNotFoundError(_NOT_FOUND_TEMPLATE.format(schedule_id=clean_id))


__all__ = ["ScheduleService"]
