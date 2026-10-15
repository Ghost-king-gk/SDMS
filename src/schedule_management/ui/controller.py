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

    # ---------------------------------------------------------------- 日历与列表

    def start(self) -> None:
        """首次启动落到当天——空库也必须显示空状态，不能是白板。"""
        self.select_day(self._clock())

    def select_day(self, day: dt.date) -> None:
        """切换筛选日期：清空选中项并重查列表（5.4 节的第二条）。"""
        self._current_day = day
        self._selected_id = None
        self.refresh()

    def refresh(self) -> None:
        """重查当前筛选日期并整体重绘列表。

        查询失败不向上抛：服务抛什么都翻译成提示，界面保留上一次的样子，
        不做"假装成功"的事。
        """
        day = self._current_day
        if day is None:
            return

        try:
            rows = presenters.to_rows(self._service.list_schedules(day))
        except Exception as exc:  # 后端异常一律转为界面提示，不向上传播
            headline, message = self._describe(exc, "查询日程")
            self._view.show_error(headline, message)
            return

        self._rows = rows
        self._view.show_rows(rows)
        self._view.show_count(presenters.count_text(len(rows)))
        self._sync_selection()
        self._view.show_status(presenters.ready_text(len(rows)))

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
        """点击「新增」：打开空白表单，用户取消则什么都不发生。"""
        self._run_form(FormRequest(mode="create", heading="新增日程"))

    def request_edit(self) -> None:
        """点击「修改」：必须有选中项，否则一次服务都不调用。

        预填的来源有两个：三个字段取自列表行，日期取当前筛选日期——
        列表只显示三列（时间/标题/备注），日期隐含在筛选条件里。
        """
        row = self._require_selection()
        if row is None:
            return

        day = self._current_day
        initial = ScheduleDraft(
            title=row.title_text,
            date_text=presenters.format_date(day) if day is not None else "",
            time_text=row.time_text,
            notes=row.notes_text,
        )
        self._run_form(
            FormRequest(mode="edit", heading="修改日程", initial=initial),
            schedule_id=row.schedule_id,
        )

    def request_delete(self) -> None:
        """点击「删除」：未选中不调服务，确认框取消也不调服务（V-10 / V-11）。

        确认框只是交互策略，替代不了服务层的校验：即便用户点了确定，
        记录不存在仍然是服务层要抛的错误，controller 不替它判断。
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

        self._selected_id = None
        self.refresh()
        self._view.show_status(presenters.deleted_text(row.title_text))

    # ---------------------------------------------------------------- 内部实现

    def _run_form(self, request: FormRequest, *, schedule_id: str | None = None) -> None:
        """反复打开表单，直到写入成功或用户主动取消。

        失败时把用户上一次的草稿塞回 `initial` 再开一次，这样
        "写入失败保留表单与已填内容"（5.2 节）不需要界面自己记状态。
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
            self._view.show_error(headline, message)
            pending = replace(request, initial=draft)

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
        """
        if presenters.error_category(exc) == presenters.UNEXPECTED_CATEGORY:
            _LOGGER.exception("执行%s时出现未预期的异常", action, exc_info=exc)
        return presenters.describe_error(exc)
