"""主界面的协调者：持有界面状态、调用用例、把后端结论翻译成界面动作。

它的职责边界（`docs/figures/ui-interaction.md` 第 5 节）：

- **不做业务判断**。标题空不空、日期写法认不认得出来、记录存不存在，
  全部由服务层判定；controller 从不为了"少调用一次服务"而自己先判一遍。
- **不做日期时间解析**。表单交上来的是原始字符串，原样交给服务。
- **持有选中态与筛选日期**。哪些操作需要选中项、什么时候清空选中，由它决定。
- **不碰 Qt**。它只调用 `MainViewPort` 里的方法，因此可以在没有显示服务的
  机器上被完整测试——这也是 P09 敢在服务层没落地之前先写完的原因。

依赖通过构造函数注入，模块导入期不创建任何窗口、不连接数据库。
"""

from __future__ import annotations

import calendar
import datetime as dt
import logging
from dataclasses import dataclass, replace

from . import presenters
from .ports import MainViewPort, ScheduleServicePort, TodayProvider
from .view_models import FormMode, FormRequest, ScheduleDraft, ScheduleRow

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class _SaveResult:
    """一次写入的结果：成功带回后端确认的标题，失败带回要展示的提示。"""

    saved_title: str = ""
    error: tuple[str, str] | None = None


class ScheduleController:
    """把用户的六类操作翻译成服务调用与界面输出。

    `service` 只需结构性满足 `ScheduleServicePort`；`view` 只需满足 `MainViewPort`。
    两者都是注入的，因此同一个 controller 既能接真实窗口，也能接测试替身。
    """

    def __init__(
        self,
        service: ScheduleServicePort,
        view: MainViewPort,
        clock: TodayProvider = dt.date.today,
    ) -> None:
        self._service = service
        self._view = view
        self._clock = clock
        self._current_day: dt.date | None = None
        self._selected_id: str | None = None
        self._rows: list[ScheduleRow] = []
        self._search_text = ""
        # 最近一次成功删除的快照；只保留一份，新的删除覆盖旧的。
        self._last_deleted: ScheduleDraft | None = None

    # ---------------------------------------------------------------- 只读状态

    @property
    def current_day(self) -> dt.date | None:
        """当前筛选日期；未调用 `start()` 之前是 None。"""
        return self._current_day

    @property
    def selected_id(self) -> str | None:
        """当前选中行的标识；没有选中为 None。"""
        return self._selected_id

    @property
    def rows(self) -> tuple[ScheduleRow, ...]:
        """列表区当前展示的行（只读快照）。"""
        return tuple(self._rows)

    @property
    def search_text(self) -> str:
        """当前搜索词；空串表示正在看某一天的列表。"""
        return self._search_text

    # ---------------------------------------------------------------- 日历与列表

    def start(self) -> None:
        """首次启动落到当天——空库也必须显示空状态，不能是白板。"""
        self.select_day(self._clock())

    def select_day(self, day: dt.date) -> None:
        """切换筛选日期：清空搜索与选中项，重查该日列表（5.4 节的第二条）。

        搜索结果横跨多天，切日期时必须显式退出搜索态；否则会出现“点了 16 号
        却仍然看到全库结果”的错位。清空搜索框用 `clear_search`，窗口负责
        屏蔽信号，避免清空动作又触发一次搜索。
        """
        self._current_day = day
        self._selected_id = None
        self._search_text = ""
        self._view.clear_search()
        # 日历必须跟着走：日期是**一个**真值，不能日历一份、controller 一份。
        # 点摘要条目、键盘换天都汇到这里，界面因此不会出现"左边 20 号、右边 23 号"。
        self._view.select_calendar_day(day)
        self.refresh()

    def refresh(self) -> bool:
        """重查当前列表并整体重绘。

        处于搜索态时重查的是搜索词而不是当天列表：保存、删除、手动刷新之后
        都应停在用户当前的搜索视图里，不能悄悄跳回某一天。

        查询失败不向上抛：服务抛什么都翻译成提示，界面保留上一次的样子，
        不做“假装成功”的事。返回值告诉调用方这次到底成没成：成功 `True`，
        查询失败或尚未 `start()`（没有筛选日期）都是 `False`。
        """
        if self._search_text:
            return self._run_search(self._search_text)

        day = self._current_day
        if day is None:
            return False

        try:
            rows = presenters.to_rows(self._service.list_schedules(day))
        except Exception as exc:  # 后端异常一律转为界面提示，不向上传播
            headline, message = self._describe(exc, "查询日程")
            self._view.show_error(headline, message)
            return False

        self._rows = rows
        self._view.show_rows(rows)
        self._view.show_count(presenters.count_text(len(rows)))
        self._sync_selection()
        self._view.show_status(presenters.ready_text(len(rows)))
        # 列表成功之后再补日历标记：存储只允许读列表、读不了月度汇总时，
        # 列表仍然是成功的，不该被一条辅助查询拖成失败。
        self.load_month_counts(day.year, day.month)
        return True

    def set_search(self, text: str) -> bool:
        """按标题/备注搜索全部日程；空查询等价于退出搜索、回到当天列表。

        搜索词只在这里抵达服务，窗口的输入框**不得直接查服务**：防抖、
        回车与清空三种入口都汇到本方法，查询次数与错误处理才只有一份。

        查询失败时保留旧列表与旧搜索态，只弹错误提示。搜索失败不能把界面
        清成空列表——那会让用户以为“没有结果”，而不是“这次没查成”。
        """
        needle = text.strip()
        if not needle:
            self._search_text = ""
            self._view.clear_search()
            return self.refresh()
        return self._run_search(needle)

    def _run_search(self, needle: str) -> bool:
        """执行一次搜索并更新列表；成功后才提交 `_search_text`。"""
        try:
            rows = presenters.to_rows(self._service.search_schedules(needle))
        except Exception as exc:
            headline, message = self._describe(exc, "搜索日程")
            self._view.show_error(headline, message)
            return False

        self._search_text = needle
        self._rows = rows
        self._view.show_rows(rows)
        self._view.show_search_state(needle, len(rows))
        self._sync_selection()
        self._view.show_status(presenters.search_status_text(len(rows)))
        return True

    def load_upcoming(self) -> bool:
        """汇总从今天起 7 天（含今天）的日程，交给左侧摘要列表。

        起点来自注入的 `clock`，测试可以固定“今天”。逐日调用
        `list_schedules`，按天拼接即可——服务已保证同一天内全天在前、
        再按时间排序，跨天顺序由循环顺序决定。

        任何一天查询失败都只记日志、返回 `False`，**不弹框**：摘要是浏览
        辅助信息，不该用错误对话框打断正在进行的操作。失败时不调用
        `show_upcoming`，界面上保留上一次成功的摘要。
        """
        start = self._clock()
        rows: list[ScheduleRow] = []
        try:
            for offset in range(7):
                day = start + dt.timedelta(days=offset)
                rows.extend(presenters.to_rows(self._service.list_schedules(day)))
        except Exception as exc:
            _LOGGER.warning("加载未来 7 天摘要失败：%s", exc)
            return False

        self._view.show_upcoming(rows)
        return True

    def select_upcoming(self, day: dt.date, schedule_id: str) -> None:
        """点击未来 7 天摘要：先切到该日期，再选中对应行。

        顺序不能反：`select_day` 会清空选中项，先 `select_row` 会被随后
        的刷新清掉。若该条已经被删除，刷新后选中自然落空，这是正确结果。
        """
        self.select_day(day)
        self.select_row(schedule_id)

    def load_month_counts(self, year: int, month: int) -> bool:
        """把这个月「哪天有几条」交给界面标记日历。

        区间是**闭区间**的当月首末日，与 `ScheduleUseCases.count_by_date` 的
        契约一致。查询失败只记日志、返回 `False`，**不弹错误框**：翻月是浏览
        动作，存储一时不可用不该把人堵在日历上；返回值留给需要区分的调用方。

        参数不合法（例如 `month=13`）同样只记日志：这是调用方的编程错误，
        不该变成一条用户看不懂的提示。
        """
        try:
            first = dt.date(year, month, 1)
            last = dt.date(year, month, calendar.monthrange(year, month)[1])
        except ValueError:
            _LOGGER.warning("无法计算 %r 年 %r 月的日期区间，已跳过日历标记", year, month)
            return False

        try:
            counts = self._service.count_by_date(first, last)
        except Exception as exc:  # 辅助查询失败不打断浏览，也不弹框
            _LOGGER.warning("加载 %s 的日程标记失败：%s", (first, last), exc)
            return False

        self._view.show_month_counts(dict(counts))
        return True

    def select_row(self, schedule_id: str | None) -> None:
        """记录用户在列表里点了哪一行。`None` 表示点到了空白处。"""
        self._selected_id = schedule_id
        self._sync_selection()

    # ---------------------------------------------------------------- 六类操作

    def request_view(self) -> None:
        """查看选中项详情。

        详情用列表里已有的数据展示，**不再查一次服务**：列表刚才是按同一天查出来的，
        重复查一次既浪费也让"详情与列表不一致"成为可能。
        """
        row = self._require_selection()
        if row is None:
            return
        self._view.show_detail(row)

    def request_create(self) -> None:
        """点击顶部「新增」：打开空白表单，用户取消则什么都不发生。"""
        self.request_create_for_day(None)

    def request_create_for_day(self, day: dt.date | None) -> None:
        """打开新增表单；给了日期就预填日期，其余字段留空。

        双击日历某天走这条路径。`date_text` 只是表单初始文本，保存时
        仍以原始字符串交给服务层解析，controller 不在这里做日期处理。
        """
        initial: ScheduleDraft | None = None
        if day is not None:
            initial = ScheduleDraft(
                title="",
                date_text=presenters.format_date(day),
                time_text="",
                notes="",
            )
        self._run_form(FormRequest(mode="create", heading="新增日程", initial=initial))

    def request_edit(self) -> None:
        """点击「修改」：必须有选中项，否则一次服务都不调用。

        预填的来源：三个字段取自列表行，日期优先取行上的 `date`——
        搜索结果可以横跨多个日期，用当前筛选日期回填会把记录改到错误的一天。
        只有旧构造的行（`date is None`，例如当天列表的测试替身）才退回
        当前筛选日期；两者都没有时留空，交给后端判定。

        全天日程在表单里是空时间：`time_text` 的“全天”只是展示文案，
        原样回填会在保存时被服务层当成非法时间解析，因此必须还原成空串。
        """
        row = self._require_selection()
        if row is None:
            return

        self._run_form(
            FormRequest(mode="edit", heading="修改日程", initial=self._draft_from_row(row)),
            schedule_id=row.schedule_id,
        )

    def request_duplicate(self) -> None:
        """复制选中日程：用「新增」路径打开一份预填好的表单。

        副本必须是**新记录**，所以走 `create` 而不是 `update`，也绝不把原
        `schedule_id` 带过去。日期取行上的日期（搜索结果可跨天），没有时退回
        当前筛选日期；全天日程的时间还原成空串，理由与修改相同。

        标题与备注保留原文，用户可以改日期后再保存——这就是“复制到其他日期”
        的用法，controller 不额外弹日期选择框。
        """
        row = self._require_selection()
        if row is None:
            return

        self._run_form(
            FormRequest(mode="create", heading="复制日程", initial=self._draft_from_row(row))
        )

    def request_move_to_day(self, schedule_id: str, day: dt.date) -> bool:
        """把一条日程改到另一天：拖到日历上时走这条路径。

        只有一个字段变了，所以**不打开表单**——拖一下弹一个填好的表单，
        等于把这个手势的意义抵消掉了。其余字段原样回填，交给同一个
        `update_schedule` 用例，失败处理也与「修改」完全一致。

        返回值：真的写成功了才 True；拖回原日期不算一次修改，直接返回 True
        且不调用服务（少一次无意义的写库）。
        """
        row = self._row_by_id(schedule_id)
        if row is None:
            self._selected_id = None
            self._sync_selection()
            self._view.show_info(presenters.stale_selection_text())
            return False

        if row.date == day:
            self._view.show_status(presenters.moved_same_day_text(row.title_text))
            return True

        draft = replace(self._draft_from_row(row), date_text=presenters.format_date(day))
        result = self._save_once(draft, mode="edit", schedule_id=schedule_id)
        if result.error is not None:
            headline, message = result.error
            self._view.show_error(headline, message)
            return False

        self.refresh()
        self._view.show_status(presenters.moved_text(result.saved_title, day))
        return True

    def request_delete(self) -> None:
        """点击「删除」：未选中不调服务，确认框取消也不调服务（V-10 / V-11）。

        确认框只是交互策略，替代不了服务层的校验：即便用户点了确定，
        记录不存在仍然是服务层要抛的错误，controller 不替它判断。

        删除成功后把这一行压成 `ScheduleDraft` 快照，供「撤销删除」重建。
        取消或失败时**不碰快照**：前者没有发生删除，后者数据还在，都不该
        点亮撤销入口；已经存在的快照也不因此丢失。
        """
        row = self._require_selection()
        if row is None:
            return

        if not self._view.ask_delete_confirm(row):
            self._view.show_status(presenters.cancelled_text())
            return

        try:
            self._service.delete_schedule(row.schedule_id)
        except Exception as exc:
            headline, message = self._describe(exc, "删除日程")
            self._view.show_error(headline, message)
            return

        self._last_deleted = self._draft_from_row(row)
        self._view.show_undo_available(True)
        self._selected_id = None
        self.refresh()
        self._view.show_status(presenters.deleted_text(row.title_text))

    def undo_delete(self) -> None:
        """撤销最近一次删除：按快照重新 `create`，不恢复原 id。

        新记录由服务层分配 id 是正确的：原 id 已经不存在，硬塞回去会和
        存储层的主键约束打架，也会让“撤销”变成一次伪装的回滚。失败时保留
        快照与撤销入口，用户可以处理完存储问题后再点一次。
        """
        draft = self._last_deleted
        if draft is None:
            self._view.show_info(presenters.undo_unavailable_text())
            return

        try:
            saved = self._service.create_schedule(
                draft.title, draft.date_text, draft.time_text, draft.notes
            )
        except Exception as exc:
            headline, message = self._describe(exc, "撤销删除")
            self._view.show_error(headline, message)
            return

        self._last_deleted = None
        self._view.show_undo_available(False)
        self.refresh()
        self._view.show_status(presenters.undo_done_text(saved.title))

    # ---------------------------------------------------------------- 内部实现

    def _draft_from_row(self, row: ScheduleRow) -> ScheduleDraft:
        """把列表行还原成表单草稿：修改、复制、删除快照共用同一套规则。

        日期优先取行上的 `date`；搜索结果跨天，用当前筛选日期回填会把记录
        带到错误的一天。全天日程的 `time_text` 是展示文案“全天”，回填表单
        必须是空串，否则服务层会把它当成非法时间。
        """
        day = row.date if row.date is not None else self._current_day
        return ScheduleDraft(
            title=row.title_text,
            date_text=presenters.format_date(day) if day is not None else "",
            time_text="" if row.all_day else row.time_text,
            notes=row.notes_text,
        )

    def _run_form(self, request: FormRequest, *, schedule_id: str | None = None) -> None:
        """反复打开表单，直到写入成功或用户主动取消。

        失败时不弹消息框：把用户上一次的草稿塞回 `initial`、把后端结论放进
        `error` 再开一次。窗口那边会复用同一个对话框，错误就显示在表单顶部，
        用户能一边看原因一边改——弹框还得先点掉、再看一眼、再重填（5.2 节）。
        """
        pending = request
        while True:
            draft = self._view.open_schedule_form(pending)
            if draft is None:
                self._view.show_status(presenters.cancelled_text())
                return

            result = self._save_once(draft, mode=request.mode, schedule_id=schedule_id)
            if result.error is None:
                self.refresh()
                self._view.show_status(presenters.saved_text(request.mode, result.saved_title))
                return

            headline, message = result.error
            # 标题与正文一起交给表单：错误条第一行是结论（"数据没能写入磁盘"），
            # 第二行是下一步。只留正文会把"这属于哪一类问题"丢掉。
            pending = replace(request, initial=draft, error=f"{headline}\n{message}")

    def _save_once(
        self,
        draft: ScheduleDraft,
        *,
        mode: FormMode,
        schedule_id: str | None,
    ) -> _SaveResult:
        """执行一次写入。成功返回后端确认的标题，失败返回要展示的提示。"""
        if mode == "edit" and schedule_id is None:
            raise ValueError("修改必须指定 schedule_id；缺 id 说明调用方写错了")
        mode_is_create = mode == "create"

        try:
            if mode_is_create:
                saved = self._service.create_schedule(
                    draft.title, draft.date_text, draft.time_text, draft.notes
                )
            else:
                # schedule_id 必然不是 None：edit 模式下上面已经拦过。
                saved = self._service.update_schedule(
                    schedule_id or "", draft.title, draft.date_text, draft.time_text, draft.notes
                )
        except Exception as exc:
            return _SaveResult(error=self._describe(exc, "保存日程"))

        return _SaveResult(saved_title=saved.title)

    def _require_selection(self) -> ScheduleRow | None:
        """取出当前选中行；没有选中或选中项已失效时给出提醒并返回 None。

        这是「未选中」的唯一出口，也是 V-10 的关键：**它只动界面，不调服务**，
        不会把 None 传给服务，也不会把界面状态伪装成 `ScheduleNotFound`。
        """
        if self._selected_id is None:
            self._view.show_info(presenters.no_selection_text())
            return None

        row = self._row_by_id(self._selected_id)
        if row is None:
            self._selected_id = None
            self._sync_selection()
            self._view.show_info(presenters.stale_selection_text())
            return None
        return row

    def _row_by_id(self, schedule_id: str) -> ScheduleRow | None:
        for row in self._rows:
            if row.schedule_id == schedule_id:
                return row
        return None

    def _sync_selection(self) -> None:
        """选中项与列表不一致时清空选中，并把结果同步给界面（5.4 节）。"""
        row = self._row_by_id(self._selected_id) if self._selected_id is not None else None
        if row is None:
            self._selected_id = None
        self._view.show_selection(presenters.selection_text(row))

    def _describe(self, exc: Exception, action: str) -> tuple[str, str]:
        """记录诊断信息并把异常转成 `(标题, 正文)`。

        认不出来的异常要留证据（记日志）但不甩给用户；认得出的交给 presenters 翻译。
        存储类错误虽然对用户是"已知"的，真正的 sqlite 原因在 `StorageError.cause`
        里，必须单独记一条 warning，否则锁表、磁盘满、权限问题在日志里完全消失。
        """
        category = presenters.error_category(exc)
        if category == presenters.UNEXPECTED_CATEGORY:
            _LOGGER.exception("执行%s时出现未预期的异常", action, exc_info=exc)
        elif category == "StorageError":
            cause = getattr(exc, "cause", None)
            if cause is not None:
                _LOGGER.warning("执行%s时存储层报错：%s", action, cause)
        return presenters.describe_error(exc)
