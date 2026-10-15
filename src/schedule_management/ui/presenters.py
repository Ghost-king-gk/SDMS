"""界面文案与格式化：一组纯函数，没有状态、没有控件、没有 IO。

放在这里的东西有一个共同点：**输入是什么就返回什么，不查任何外部资源**。
这让"列表怎么显示""错误提示长什么样"可以脱离 Qt 被单测覆盖——
本项目 GUI 的人工验证很贵（要开两台机器），能在单测里穷举的就不留给手工。

另一个约束：本模块不定义业务规则。日期时间的写法是否合法由后端判定，
这里只负责把后端结论翻译成用户能读的句子。
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence

from .ports import ScheduleLike
from .view_models import ScheduleRow

DATE_FORMAT = "%Y-%m-%d"
TIME_FORMAT = "%H:%M"

#: 归类失败时的类别名；controller 用它判断要不要记诊断日志。
UNEXPECTED_CATEGORY = "Unexpected"

#: 星期几的中文简称，索引与 `date.weekday()`（周一为 0）对齐。
_WEEKDAY_NAMES = ("周一", "周二", "周三", "周四", "周五", "周六", "周日")

#: 已知的可解释错误 → 提示标题。键是**异常类名**，原因见 `error_category`。
_ERROR_HEADLINES = {
    "ValidationError": "无法保存",
    "ScheduleNotFound": "没有找到这条日程",
    "StorageError": "数据没能写入磁盘",
}

#: 已知的可解释错误 → 可执行的下一步。后端给出的具体原因优先，这是兜底文案。
_ERROR_SUGGESTIONS = {
    "ValidationError": (
        "请检查标题是否只填了空格、日期时间是否写得无法识别。"
        "已经填写的内容都还在，改完可以直接再试一次。"
    ),
    "ScheduleNotFound": "它可能已经被删除了。点「刷新」看看最新的列表。",
    "StorageError": "数据文件可能不可写或已损坏。已填写的内容没有丢失，处理好之后可以再试。",
}

_UNEXPECTED_HEADLINE = "操作没有完成"
_UNEXPECTED_SUGGESTION = (
    "程序遇到了一个没有预料到的情况，诊断信息已经记录。"
    "你可以重试一次，或者先换别的操作；不用担心，数据没有被改写。"
)


def format_date(day: dt.date) -> str:
    """回填与显示用的标准日期文本（YYYY-MM-DD）。"""
    return day.strftime(DATE_FORMAT)


def format_time(at: dt.time) -> str:
    """回填与显示用的标准时间文本（HH:MM，分钟精度）。"""
    return at.strftime(TIME_FORMAT)


def date_heading(day: dt.date) -> str:
    """日期条上的文案，例如 `2026-10-15 周四`。"""
    return f"{format_date(day)} {_WEEKDAY_NAMES[day.weekday()]}"


def to_row(item: ScheduleLike) -> ScheduleRow:
    """把一条日程换成列表行：展示文本与 id 同时保留，不丢 id。"""
    return ScheduleRow(
        schedule_id=item.id,
        time_text=format_time(item.time),
        title_text=item.title,
        notes_text=item.notes,
    )


def to_rows(items: Sequence[ScheduleLike]) -> list[ScheduleRow]:
    """批量转换。**不排序**：确定性排序由服务/仓储负责，界面只照抄顺序。"""
    return [to_row(item) for item in items]


def count_text(total: int) -> str:
    """条数文案，例如 `共 3 条`。零条也照实说，不留空白让人以为程序坏了。"""
    return f"共 {total} 条"


def selection_text(row: ScheduleRow | None) -> str:
    """选中项文案。没有选中时明确说出来，而不是显示一片空白。"""
    if row is None:
        return "未选中日程"
    return f"已选中：{row.time_text} {row.title_text}"


def ready_text(total: int) -> str:
    """启动或刷新完成后的状态栏文案。"""
    if total == 0:
        return "就绪：这一天还没有日程"
    return f"就绪：{count_text(total)}"


def refreshed_text(total: int) -> str:
    """手动刷新后的状态栏文案。"""
    if total == 0:
        return "已刷新：这一天还没有日程"
    return f"已刷新：{count_text(total)}"


def saved_text(mode: str, title: str) -> str:
    """写入成功后的状态栏文案。`title` 用后端返回的，不用界面原样输入。"""
    verb = "已新增" if mode == "create" else "已修改"
    return f"{verb}「{title}」"


def deleted_text(title: str) -> str:
    """删除成功后的状态栏文案。"""
    return f"已删除「{title}」"


def no_selection_text() -> str:
    """没有选中就点修改/删除时的提示。

    这句话必须是提醒而不是错误：**未选中是界面状态问题，不是业务错误**，
    它不能变成一次服务调用，更不能伪装成 `ScheduleNotFound`。
    """
    return "请先在列表里选中一条日程，再执行这个操作。"


def stale_selection_text() -> str:
    """选中项已经不在列表里时的提示（例如被别的路径删掉了）。"""
    return "刚才选中的日程已经不在列表里了，请重新选择。"


def cancelled_text() -> str:
    """用户主动取消（关闭表单、删除确认点取消）后的状态栏文案。"""
    return "已取消，没有做任何改动"


def error_category(exc: BaseException) -> str:
    """把异常归到一类可解释的错误；认不出来就返回 `"Unexpected"`。

    这里按**类名**判定而不是 `isinstance`，是因为 `domain/errors.py` 与
    `application/errors.py` 还没有落地（P05 / P07 归 zch），界面不能在导入期
    依赖它们，否则 import 一断整套 UI 测试就跑不起来。

    待真异常类可用后，把函数体换成 isinstance 判定即可，调用方无需改动。
    """
    name = type(exc).__name__
    if name in _ERROR_HEADLINES:
        return name
    return UNEXPECTED_CATEGORY


def describe_error(exc: BaseException) -> tuple[str, str]:
    """把后端抛出的异常翻译成 `(标题, 正文)` 供界面展示。

    两条原则：`ui-interaction.md` 5.2 节要求"提示后端给出的原因"，
    而 5.1 节要求界面不自己编造格式要求——所以已知错误的正文以**后端 reason
    打头**，再补一句能操作的下一步；认不出来的异常只给通用文案，
    不把 `str(exc)` 里的技术细节甩给用户（诊断信息由 controller 记日志）。
    """
    category = error_category(exc)
    if category == UNEXPECTED_CATEGORY:
        return _UNEXPECTED_HEADLINE, _UNEXPECTED_SUGGESTION

    reason = str(exc).strip()
    suggestion = _ERROR_SUGGESTIONS[category]
    message = f"{reason}\n{suggestion}" if reason else suggestion
    return _ERROR_HEADLINES[category], message
