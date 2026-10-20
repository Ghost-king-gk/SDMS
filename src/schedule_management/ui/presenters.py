"""界面文案与格式化：一组纯函数，没有状态、没有控件、没有 IO。

放在这里的东西有一个共同点：**输入是什么就返回什么，不查任何外部资源**。
这让"列表怎么显示""错误提示长什么样"可以脱离 Qt 被单测覆盖——
本项目 GUI 的人工验证很贵（要开两台机器），能在单测里穷举的就不留给手工。

另一个约束：本模块不定义业务规则。日期时间的写法是否合法由后端判定，
这里只负责把后端结论翻译成用户能读的句子。
"""

from __future__ import annotations

import datetime as dt
import importlib
from collections.abc import Sequence
from functools import cache

from .ports import ScheduleLike
from .view_models import FormMode, ScheduleRow

DATE_FORMAT = "%Y-%m-%d"
TIME_FORMAT = "%H:%M"

#: 归类失败时的类别名；controller 用它判断要不要记诊断日志。
UNEXPECTED_CATEGORY = "Unexpected"

#: 星期几的中文简称，索引与 `date.weekday()`（周一为 0）对齐。
_WEEKDAY_NAMES = ("周一", "周二", "周三", "周四", "周五", "周六", "周日")

#: 已知的可解释错误 → 提示标题。键是 `error_category` 给出的**分类名**。
#:
#: `Duplicate` 的文案刻意不写"已经存在"：该分类只表示存储层 ID 主键冲突，
#: 不表示同标题/同时段/同内容冲突——内容相同、ID 不同的两条日程是合法的
#: （见 `docs/design/contracts.md` 错误类型一节）。文案不能暗示内容重复。
_ERROR_HEADLINES = {
    "ValidationError": "无法保存",
    "ScheduleNotFound": "没有找到这条日程",
    "Duplicate": "保存冲突",
    "StorageError": "数据没能写入磁盘",
}

#: 已知的可解释错误 → 可执行的下一步。后端给出的具体原因优先，这是兜底文案。
_ERROR_SUGGESTIONS = {
    "ValidationError": (
        "请检查标题是否只填了空格、日期时间是否写得无法识别。"
        "已经填写的内容都还在，改完可以直接再试一次。"
    ),
    "ScheduleNotFound": "它可能已经被删除了。点「刷新」看看最新的列表。",
    "Duplicate": (
        "可能是记录 ID 冲突。先点「刷新」看看最新的列表，"
        "已经填写的内容都还在，刷新后可以直接再试一次。"
    ),
    "StorageError": "数据文件可能不可写或已损坏。已填写的内容没有丢失，处理好之后可以再试。",
}

#: 真异常类不可用时的兜底：异常类名 → 分类名。
#:
#: `ScheduleNotFound` 是开发替身与旧契约用的名字，`ScheduleNotFoundError` 是
#: 应用层落地后的真名，两者必须归到同一类；`DuplicateScheduleError` 是
#: `StorageError` 的子类，查表时按 MRO 从子类往父类走，因此会先命中 Duplicate。
_CATEGORY_BY_CLASS_NAME = {
    "ValidationError": "ValidationError",
    "ScheduleNotFound": "ScheduleNotFound",
    "ScheduleNotFoundError": "ScheduleNotFound",
    "DuplicateScheduleError": "Duplicate",
    "StorageError": "StorageError",
}


_UNEXPECTED_HEADLINE = "操作没有完成"
_UNEXPECTED_SUGGESTION = (
    "程序遇到了一个没有预料到的情况，诊断信息已经记录。"
    "你可以重试一次，或者先换别的操作；不用担心，数据没有被改写。"
)


def format_date(day: dt.date) -> str:
    """回填与显示用的标准日期文本（YYYY-MM-DD）。"""
    return day.strftime(DATE_FORMAT)


def format_time(at: dt.time | None) -> str:
    """回填与显示用的时间文本（HH:MM，分钟精度）；``None`` 显示“全天”。"""
    if at is None:
        return "全天"
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
        all_day=item.time is None,
        date=item.date,
    )


def to_rows(items: Sequence[ScheduleLike]) -> list[ScheduleRow]:
    """批量转换。**不排序**：确定性排序由服务/仓储负责，界面只照抄顺序。"""
    return [to_row(item) for item in items]


def count_text(total: int) -> str:
    """条数文案，例如 `共 3 条`。零条也照实说，不留空白让人以为程序坏了。"""
    return f"共 {total} 条"


def search_heading(text: str, total: int) -> str:
    """搜索结果标题：说明“这是搜索，不是在看待办日期”。

    搜索结果可以横跨多天，如果仍然显示某个日期，用户会误以为列表只属于那天。
    标题必须同时给出关键词与条数，零条也要说清，不能让人以为搜索没生效。
    """
    return f"搜索“{text}” · 共 {total} 条"


def search_status_text(total: int) -> str:
    """搜索完成后的状态栏文案。"""
    return f"搜索到 {total} 条"


def search_empty_text(text: str) -> str:
    """搜索无命中时的列表空状态：说明“没搜到”，而不是“这天没有日程”。"""
    return f"没有找到匹配「{text}」的日程，换个关键词试试。"


def upcoming_item_text(row: ScheduleRow) -> str:
    """“未来 7 天”列表的一行，例如 `10-20 周二 · 全天 · 整理课程笔记`。

    日期用 `MM-DD` 而不是完整年份：摘要只覆盖 7 天，年份是噪声；但星期必须带，
    用户判断“明天还是下周一”靠的是它。日期缺失时显示破折号，不静默省略字段。
    """
    day_text = "—"
    if row.date is not None:
        day_text = f"{row.date:%m-%d} {_WEEKDAY_NAMES[row.date.weekday()]}"
    return f"{day_text} · {row.time_text} · {row.title_text}"


def upcoming_empty_text() -> str:
    """未来 7 天没有任何日程时的占位文案。"""
    return "未来 7 天没有日程"


def detail_text(row: ScheduleRow) -> str:
    """详情对话框正文；日期缺失时显示破折号而不是整行消失。"""
    day_text = row.date.isoformat() if row.date is not None else "—"
    return (
        f"日期：{day_text}\n"
        f"时间：{row.time_text}\n"
        f"标题：{row.title_text}\n"
        f"备注：{row.notes_text or '（空）'}"
    )


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


def saved_text(mode: FormMode, title: str) -> str:
    """写入成功后的状态栏文案。`title` 用后端返回的，不用界面原样输入。

    `mode` 只接受表单模型定义的两个值；拼错时直接报错，不能静默显示成
    “已修改”——那会让“新增成功”与“修改成功”在状态栏上无法区分。
    """
    if mode == "create":
        return f"已新增「{title}」"
    if mode == "edit":
        return f"已修改「{title}」"
    raise ValueError(f"未知的表单模式：{mode!r}")


def deleted_text(title: str) -> str:
    """删除成功后的状态栏文案。"""
    return f"已删除「{title}」"


def undo_done_text(title: str) -> str:
    """撤销删除成功后的状态栏文案；`title` 用后端确认的标题。"""
    return f"已撤销删除「{title}」"


def undo_unavailable_text() -> str:
    """没有可撤销的删除时的提醒。

    这不是错误：可能是撤销已经完成，也可能是这次运行里还没有删除过。
    """
    return "没有可以撤销的删除。"


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


_RealErrorTypes = tuple[
    type[BaseException], type[BaseException], type[BaseException], type[BaseException]
]


@cache
def _real_error_types() -> _RealErrorTypes | None:
    """延迟加载真实后端的异常类；这些模块还没落地时返回 `None`。

    用 `importlib` 而不是函数内 `import`：PR #5 所在分支还没有 `application` /
    `domain` 包，静态 import 即使包在 `try/except ImportError` 里，也会让
    `mypy src` 直接报 `import-not-found`。模块名仍是显式写死的，不存在猜路径。

    返回顺序即判定顺序：`DuplicateScheduleError` 必须排在它的基类
    `StorageError` 前面。
    """
    try:
        application_errors = importlib.import_module("schedule_management.application.errors")
        domain_errors = importlib.import_module("schedule_management.domain.errors")
    except ImportError:
        return None

    try:
        return (
            domain_errors.ValidationError,
            application_errors.DuplicateScheduleError,
            application_errors.ScheduleNotFoundError,
            application_errors.StorageError,
        )
    except AttributeError:
        return None


def error_category(exc: BaseException) -> str:
    """把异常归到一类可解释的错误；认不出来就返回 `"Unexpected"`。

    真异常类可用时优先用 `isinstance` 判定，类名不再参与；真类不可用（本分支
    尚未合入后端模块），或异常来自刻意复制契约名字的开发替身时，按 MRO 里的
    类名兜底。兜底同样从子类往父类查，因此 `DuplicateScheduleError` 会先命中
    `Duplicate`，不会被它的基类 `StorageError` 抢走。
    """
    real_types = _real_error_types()
    if real_types is not None:
        validation_error, duplicate_error, not_found_error, storage_error = real_types
        if isinstance(exc, validation_error):
            return "ValidationError"
        if isinstance(exc, duplicate_error):
            return "Duplicate"
        if isinstance(exc, not_found_error):
            return "ScheduleNotFound"
        if isinstance(exc, storage_error):
            return "StorageError"

    for cls in type(exc).__mro__:
        category = _CATEGORY_BY_CLASS_NAME.get(cls.__name__)
        if category is not None:
            return category
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
