"""界面层对外部世界的端口。

端口分两类，都刻意使用**结构性类型**（Protocol），运行时不做 isinstance 检查：

- **后端契约的别名**：``ScheduleLike`` / ``ScheduleServicePort`` 不在此重复定义，
  直接别名到 ``application.contracts.ScheduleView`` / ``ScheduleUseCases``。
  服务用例协议的唯一定义在后端（P07 归 zch）；界面侧再抄一份签名，就会出现
  "两边各改各的"的漂移。保留旧名只是为了让 controller / presenters / 测试替身
  里的引用不必全部改名——它们与权威契约本就是同一个类型。需要新方法、新字段
  或改签名时，改后端协议并走 PR，不得在这里单独扩展。
- **界面自己的端口**：``MainViewPort`` 把 Qt 控件挡在 controller 之外——
  controller 调的是端口，由 ``app.py`` / 窗口适配器把真正的按钮和列表接上来。

真实实现替换进来时，controller 不需要改一行代码，只需要 mypy 证明它
结构性地满足协议。
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable, Sequence
from typing import Protocol

from ..application.contracts import ScheduleUseCases, ScheduleView
from .view_models import FormMode, FormRequest, ScheduleDraft, ScheduleRow

#: 后端权威契约 ``application.contracts.ScheduleView`` 的别名：界面能接受的
#: 一条日程，五个只读属性。领域 ``Schedule``、测试替身、其他前端的适配器都可以
#: 结构性地满足它；声明为只读是为了防止界面偷偷改领域对象。
ScheduleLike = ScheduleView

#: 后端权威契约 ``application.contracts.ScheduleUseCases`` 的别名：界面期待的
#: 服务形状。``create_schedule`` / ``update_schedule`` 接收原始字符串而不是
#: ``date`` / ``time`` 对象——解析与校验归后端，界面不预解析、不抢先校验；
#: ``list_schedules`` 按 ``dt.date`` 查询，该值来自日历控件的点选结果，
#: 本身就是日期对象，不存在"用户手写"的问题。
ScheduleServicePort = ScheduleUseCases


class MainViewPort(Protocol):
    """controller 会用到的全部界面输出。

    方法命名统一为 `show_*` / `ask_*` / `open_*`：前者是单向输出，
    后两者需要等用户的回答。所有跨线程的 Qt 细节都留在实现里，
    这里的方法都假定是同步调用（Qt 的模态对话框本来就是同步的）。
    """

    def show_rows(self, rows: Sequence[ScheduleRow]) -> None:
        """整体重绘列表；传入空序列即空状态，由界面决定怎么显示。"""

    def show_count(self, text: str) -> None:
        """显示条数文案（② 区）。"""

    def show_search_state(self, text: str, total: int) -> None:
        """进入搜索态：② 区改成搜索标题，并显示命中条数。

        搜索结果可能横跨多个日期，普通日期标题会误导；窗口应把 `DayHeading`
        设为 `搜索“...” · 共 N 条`。
        """

    def clear_search(self) -> None:
        """退出搜索态：清空搜索框（不得再次触发搜索）并恢复普通日期标题。"""

    def show_upcoming(self, rows: Sequence[ScheduleRow]) -> None:
        """显示未来 7 天摘要（含今天），按日期与时间顺序；空序列显示占位文案。"""

    def select_calendar_day(self, day: dt.date) -> None:
        """让日历把选中格移到 `day`，**不得反过来再发一次"用户选了某天"**。

        这是"当前日期只有一个真值"的落地方式：日期可能是被别的入口改的
        （点摘要条目、键盘在日历上换天、将来从搜索结果跳转），日历必须跟着走。
        窗口实现要屏蔽由本次移动产生的选中变化信号，否则会形成回环。
        """

    def show_month_counts(self, counts: dict[dt.date, int]) -> None:
        """用「当月每个有日程的日期 → 条数」标记日历（① 区）。

        `counts` 只包含有日程的日期；空字典表示这个月一条都没有，界面应当
        把所有旧标记清掉（今天的高亮不属于标记，由界面自己维护）。
        """

    def show_selection(self, text: str) -> None:
        """显示当前选中项文案（⑤ 区右侧）。"""

    def show_status(self, text: str) -> None:
        """显示最近一次操作的结果（⑤ 区）。"""

    def show_undo_available(self, available: bool) -> None:
        """显示或隐藏「撤销删除」入口。

        `True` 表示最近一次删除可以被撤销；撤销成功、没有可撤销的删除时
        传 `False`。窗口只负责切换入口的可见性，是否真的能撤销由 controller
        的快照决定。
        """

    def show_info(self, message: str) -> None:
        """非错误的提醒，例如"请先选择一条日程"。"""

    def show_error(self, headline: str, message: str) -> None:
        """错误提示：`headline` 是短标题，`message` 是后端结论加可执行的下一步。"""

    def show_detail(self, row: ScheduleRow) -> None:
        """展示一条日程的详情，数据来自列表已有内容，不再查一次服务。"""

    def ask_delete_confirm(self, row: ScheduleRow) -> bool:
        """弹出删除确认；返回 True 才真的删。**调用它不代表已经删了。**"""

    def open_schedule_form(self, request: FormRequest) -> ScheduleDraft | None:
        """打开表单并把结果交回来；返回 None 表示用户取消（不可写的范围为零）。"""


#: 取得"今天"的函数类型。注入而不是直接调用 `dt.date.today()`，
#: 是为了让测试可以固定日期，避免跨零点运行得到不同结果。
TodayProvider = Callable[[], dt.date]

__all__ = [
    "FormMode",
    "MainViewPort",
    "ScheduleDraft",
    "ScheduleLike",
    "ScheduleRow",
    "ScheduleServicePort",
    "TodayProvider",
]
