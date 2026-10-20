"""应用层定义的契约：界面可用的用例协议与存储端口。"""

import datetime as dt
from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from schedule_management.domain.schedule import Schedule


class ScheduleRepository(Protocol):
    def add(self, schedule: Schedule) -> None: ...

    def get(self, schedule_id: str) -> Schedule | None: ...

    def list_by_date(self, day: dt.date) -> list[Schedule]: ...

    def count_by_date(self, start: dt.date, end: dt.date) -> dict[dt.date, int]: ...

    def search_schedules(self, text: str) -> list[Schedule]: ...

    def update(self, schedule: Schedule) -> bool: ...

    def delete(self, schedule_id: str) -> bool: ...


class ScheduleView(Protocol):
    """界面可见的日程形状：五个只读属性。

    用例协议的返回类型用本协议而不是具体 ``Schedule``：领域对象当然满足它，
    但测试替身、CLI / WebUI 的其他适配同样可以结构性地满足——否则任何非
    ``Schedule`` 实现都被名义类型卡在契约外，"前端向契约对齐"就变成了
    "前端向领域类对齐"。

    集合类型用 ``Sequence`` 而不是 ``list``：``Sequence`` 协变，
    ``list[Schedule]`` 与替身的 ``list[StubSchedule]`` 都满足它。
    """

    @property
    def id(self) -> str: ...

    @property
    def title(self) -> str: ...

    @property
    def date(self) -> dt.date: ...

    @property
    def time(self) -> dt.time | None:
        """具体时刻；``None`` 表示全天日程（用户没有填写时间）。"""

    @property
    def notes(self) -> str: ...


@runtime_checkable
class ScheduleUseCases(Protocol):
    """界面依赖的服务用例协议，是三层接缝的权威定义。

    界面只按本协议调用服务，不得在 UI 侧复制或改写方法签名；需要新方法、
    新字段或改签名时，先改本协议并走 PR。``ScheduleService`` 显式实现本协议，
    返回的领域 ``Schedule`` 结构上满足 ``ScheduleView``（也满足界面
    ``ScheduleLike``：``id/title/date/time/notes`` 五个只读属性）。
    """

    def list_schedules(self, day: dt.date) -> Sequence[ScheduleView]:
        """返回 ``day`` 当天的全部日程，按时间升序；没有记录时返回空列表。"""
        ...

    def create_schedule(
        self,
        title: str,
        date_text: str,
        time_text: str,
        notes: str,
    ) -> ScheduleView:
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
    ) -> ScheduleView:
        """全量更新一条日程，返回新对象且 id 不变；找不到记录时抛 ``ScheduleNotFoundError``。

        ``date_text`` / ``time_text`` 同样是用户原始文本，由服务层解析。
        """
        ...

    def delete_schedule(self, schedule_id: str) -> None:
        """删除一条日程；找不到记录时抛 ``ScheduleNotFoundError``，不静默成功。"""
        ...

    def count_by_date(self, start: dt.date, end: dt.date) -> dict[dt.date, int]:
        """返回 ``[start, end]`` **闭区间**内每个有日程的日期及条数。

        供日历按月标记与“当天几条”徽标使用：键用于底色标记，值用于徽标；
        没有日程的日期不出现在字典里，区间为空或 ``start > end`` 时返回空字典。
        """
        ...

    def search_schedules(self, text: str) -> Sequence[ScheduleView]:
        """按标题或备注**包含** ``text`` 搜索，返回命中日程。

        ``text`` 去空白后为空时返回空列表；``%``、``_``、``\\`` 按字面量匹配，
        不做通配符解释。结果按日期升序、全天在前、再按时间与 id 排序。
        """
        ...
