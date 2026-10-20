"""界面层对外部世界的三个端口（Protocol）。

这三个协议是本包唯一的对外依赖方式，刻意使用**结构性类型**：

- 服务层还没有落地（P07 归 zch），界面不需要等它——只要方法签名对得上，
  谁来当服务都可以被注入；P09 因此可以先拿测试替身把界面逻辑写完跑通；
- 真实实现替换进来时，controller 不需要改一行代码，只需要 mypy 证明它
  结构性地满足协议；
- `MainViewPort` 把 Qt 控件挡在 controller 之外：controller 调的是端口，
  由 `app.py` / 未来的窗口适配器把真正的按钮和列表接上来。

运行时不做 isinstance 检查，也不注册实现类——协议只用于类型声明与静态检查。
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable, Sequence
from typing import Protocol

from .view_models import FormMode, FormRequest, ScheduleDraft, ScheduleRow


class ScheduleLike(Protocol):
    """界面能接受的一条日程：只要求五个只读属性。

    领域层将来的 `Schedule` 只要具备这些成员就能被 `presenters` 直接处理，
    界面不关心它还有别的什么方法。刻意声明成只读，是为了防止界面偷偷改领域对象。
    """

    @property
    def id(self) -> str:
        """稳定标识，修改后保持不变。"""

    @property
    def title(self) -> str: ...

    @property
    def date(self) -> dt.date: ...

    @property
    def time(self) -> dt.time | None:
        """具体时刻；``None`` 表示全天日程。"""

    @property
    def notes(self) -> str: ...


class ScheduleServicePort(Protocol):
    """界面期待的服务形状。

    与计划第 4 节「服务草案」的**唯一偏差**：`create_schedule` / `update_schedule`
    接收原始字符串而不是 `date` / `time` 对象。草案原文写的是
    「create/update 的 day 与 at 已经是日期/时间对象；GUI 字符串解析在 controller」，
    zch 在 PR #5 审查中改为「用户也可输入，由后端写转换算法，无感转成可用格式」，
    界面据此交出原始文本。**这条偏差必须写进 `docs/design/contracts.md` 才算定稿**，
    详见 `ui-interaction.md` 第 10 节。

    `list_schedules` 仍然按 `dt.date` 查询：这个值来自日历控件的点选结果，
    本身就是日期对象，不存在"用户手写"的问题。

    权威定义是 `schedule_management.application.contracts.ScheduleUseCases`；
    本协议只是界面侧的结构性镜像，方法签名必须与它保持一致，不得单独扩展。
    """

    def list_schedules(self, day: dt.date) -> Sequence[ScheduleLike]:
        """返回指定日期的全部日程；无记录返回空序列，不报错。"""

    def create_schedule(
        self,
        title: str,
        date_text: str,
        time_text: str,
        notes: str,
    ) -> ScheduleLike:
        """新增一条日程；日期时间是原始文本，由后端解析与校验。"""

    def update_schedule(
        self,
        schedule_id: str,
        title: str,
        date_text: str,
        time_text: str,
        notes: str,
    ) -> ScheduleLike:
        """修改指定日程；`schedule_id` 在修改前后保持不变。"""

    def delete_schedule(self, schedule_id: str) -> None:
        """删除指定日程；记录不存在是业务错误，由服务层抛出。"""

    def count_by_date(self, start: dt.date, end: dt.date) -> dict[dt.date, int]:
        """返回闭区间 `[start, end]` 内每个有日程的日期及条数，供日历标记与徽标使用。"""
        ...

    def search_schedules(self, text: str) -> Sequence[ScheduleLike]:
        """按标题或备注包含搜索；空查询返回空列表。"""
        ...


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

    def show_selection(self, text: str) -> None:
        """显示当前选中项文案（⑤ 区右侧）。"""

    def show_status(self, text: str) -> None:
        """显示最近一次操作的结果（⑤ 区）。"""

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
