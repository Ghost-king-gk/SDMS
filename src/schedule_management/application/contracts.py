"""应用层定义的契约：界面可用的用例协议与存储端口。"""

import datetime as dt
from typing import Protocol, runtime_checkable

from schedule_management.domain.schedule import Schedule


class ScheduleRepository(Protocol):
    def add(self, schedule: Schedule) -> None: ...

    def get(self, schedule_id: str) -> Schedule | None: ...

    def list_by_date(self, day: dt.date) -> list[Schedule]: ...

    def update(self, schedule: Schedule) -> bool: ...

    def delete(self, schedule_id: str) -> bool: ...


@runtime_checkable
class ScheduleUseCases(Protocol):
    """界面依赖的服务用例协议，是三层接缝的权威定义。

    界面只按本协议调用服务，不得在 UI 侧复制或改写方法签名；需要新方法、
    新字段或改签名时，先改本协议并走 PR。``ScheduleService`` 显式实现本协议，
    返回值 ``Schedule`` 结构上满足界面 ``ScheduleLike``（``id/title/date/time/notes``
    五个只读属性）。
    """

    def list_schedules(self, day: dt.date) -> list[Schedule]:
        """返回 ``day`` 当天的全部日程，按时间升序；没有记录时返回空列表。"""
        ...

    def create_schedule(
        self,
        title: str,
        date_text: str,
        time_text: str,
        notes: str,
    ) -> Schedule:
        """新增一条日程并返回保存后的对象。

        ``date_text`` / ``time_text`` 是用户原样输入的文本，解析与校验归服务层；
        界面不预解析、不抢先校验。
        """
        ...

    def update_schedule(
        self,
        schedule_id: str,
        title: str,
        date_text: str,
        time_text: str,
        notes: str,
    ) -> Schedule:
        """全量更新一条日程，返回新对象且 id 不变；找不到记录时抛 ``ScheduleNotFoundError``。

        ``date_text`` / ``time_text`` 同样是用户原始文本，由服务层解析。
        """
        ...

    def delete_schedule(self, schedule_id: str) -> None:
        """删除一条日程；找不到记录时抛 ``ScheduleNotFoundError``，不静默成功。"""
        ...
