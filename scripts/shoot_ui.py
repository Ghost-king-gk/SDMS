"""跑一遍真实窗口：产出截图，并把 V 清单里能断言的部分断言掉。

用法（**在有桌面的 Windows 上直接跑，不要设 `QT_QPA_PLATFORM=offscreen`**）：

    uv run python scripts/shoot_ui.py

为什么不加 offscreen：离屏平台在这台机器上 `QFontDatabase.families()` 返回 0 个
字体，抓出来的中文全是方块——图能生成，但作为文档素材是废的。所以这个脚本
**只用于本地出图**，不进 CI；自动化断言那部分（能离线跑）已经落在
`tests/unit/` 与 `scripts/qt_probe.py` 里。

为什么需要这个脚本而不是纯手工验收：

- 手工验收一次容易，**重复一次很难**，而改完界面要重验正是常态；
- 界面改动之后能立刻知道"有没有把哪一屏搞坏"，而不是等到答辩前；
- 截图是设计文档与 PPT 的素材来源，一次生成，多处复用。

模态流程怎么自动走：`QDialog.exec()` 会进入嵌套事件循环，而 `QTimer` 的
回调在嵌套循环里照样执行。所以"点新增 → 表单弹出 → 定时器填字段点保存 →
服务返回 → 列表刷新"可以一路自动完成，不需要人盯着点。`ModalDriver`
就是按计划依次处理弹出的模态框：表单、消息框、日期浮层各自认领自己的动作。

诚实边界（**没有假装已验**）：

- V-14 持久化：存储层落地后由 `scenario_real_service` 真验——真连接 + 真 SQLite，
  关窗关连接重开后数据还在；本文件同时保留替身版场景做界面回归；
- V-07 的"跨月灰显好不好看"、文字截断这类，仍然要人打开截图看一眼；
- V-17 的平台一致性只在 Windows 上验过（Linux 不做 GUI，见 1.1 节）。
"""

from __future__ import annotations

import datetime as dt
import sys
import tempfile
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Final, cast

from PySide6.QtCore import QDate, Qt, QTimer
from PySide6.QtWidgets import QApplication, QDialogButtonBox, QMessageBox, QWidget

from schedule_management import composition
from schedule_management.dev_stub_service import DevStubScheduleService
from schedule_management.ui.date_picker import DatePickerPopup
from schedule_management.ui.main_window import MainWindow
from schedule_management.ui.ports import ScheduleLike, ScheduleServicePort
from schedule_management.ui.schedule_form import ScheduleForm
from schedule_management.ui.view_models import FormRequest, ScheduleDraft

TODAY = dt.date(2026, 10, 15)
OUTPUT_DIR = Path(__file__).resolve().parents[1] / "docs" / "screenshots"
_TICK_MS = 30

_checks: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    _checks.append((name, bool(ok), detail))


def save(pixmap: object, filename: str) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / filename
    pixmap.save(str(path))  # type: ignore[attr-defined]
    return path


# ---------------------------------------------------------------------------
# 记录仪：委托给真替身，只多记一笔调用账。
#
# V-10 / V-11 / V-13 断言的是"服务一次都没被调用"——这类事肉眼看不出来，
# 列表没变不代表没调过服务（也可能是调了但没改成功）。所以必须记调用。
# ---------------------------------------------------------------------------


class RecordingService:
    """服务端口实现的委托包装：行为不变，只多记一笔调用账。

    替身和真服务都能包——构造时只要求满足 `ScheduleServicePort`，
    场景代码因此不用关心背后是内存还是 SQLite。
    """

    def __init__(self, inner: ScheduleServicePort) -> None:
        self._inner = inner
        self.calls: list[str] = []

    def list_schedules(self, day: dt.date) -> Sequence[ScheduleLike]:
        return list(self._inner.list_schedules(day))

    def create_schedule(
        self, title: str, date_text: str, time_text: str, notes: str
    ) -> ScheduleLike:
        self.calls.append("create")
        return self._inner.create_schedule(title, date_text, time_text, notes)

    def update_schedule(
        self,
        schedule_id: str,
        title: str,
        date_text: str,
        time_text: str,
        notes: str,
    ) -> ScheduleLike:
        self.calls.append("update")
        return self._inner.update_schedule(schedule_id, title, date_text, time_text, notes)

    def delete_schedule(self, schedule_id: str) -> None:
        self.calls.append("delete")
        self._inner.delete_schedule(schedule_id)


# ---------------------------------------------------------------------------
# 模态处理链
# ---------------------------------------------------------------------------


class ModalDriver:
    """按计划依次处理弹出的模态对话框。

    每个计划项认领一类模态框（表单 / 消息框 / 日期浮层），做完点掉或关掉它，
    然后等下一个模态出现。控制器在保存失败时会**再开一次表单**，所以一个
    用户操作背后可能连着两三个模态——按顺序走计划即可，不需要特殊分支。

    关键时序：**先把下一拍排定，再执行当前动作**。动作里点某个按钮可能
    同步弹出下一层模态（点「选择」→ 浮层 `exec()` 就阻塞在当前调用里），
    若按"动作返回后再排下一拍"写，下一拍永远排不上，浮层没人处理，整个
    脚本挂死；先排拍则下一拍会在嵌套事件循环里准时赶到。
    """

    def __init__(self, plan: list[Callable[[QWidget], None]], interval_ms: int = _TICK_MS) -> None:
        self._plan = plan
        self._interval = interval_ms
        self._index = 0

    def start(self) -> None:
        QTimer.singleShot(self._interval, self._tick)

    def _tick(self) -> None:
        if self._index >= len(self._plan):
            return
        modal = QApplication.activeModalWidget()
        if modal is None:
            # 模态还没弹出来（控件事件还在派发），下一拍再问。
            QTimer.singleShot(self._interval, self._tick)
            return
        action = self._plan[self._index]
        self._index += 1
        QTimer.singleShot(self._interval, self._tick)
        action(modal)


# ---------------------------------------------------------------------------
# 模态动作：每个函数返回一个「处理某个模态框」的闭包
# ---------------------------------------------------------------------------


def _expect(modal: QWidget, kind: type, label: str) -> bool:
    """认领模态框：类型不符就记一条失败，返回 False 让动作体整体跳过。

    这个脚本跑在**有人的真机**上，物理鼠标随时可能点掉正在自动处理的窗口
    （使用者就坐在电脑前）。类型不符说明流程被外部打断：记一条 FAIL 让人
    一眼看出是哪一步被破坏，后续计划继续走完，脚本不会挂住等一个
    永远不会来的模态。
    """
    if isinstance(modal, kind):
        return True
    check(
        f"模态类型符合预期（{label}）",
        False,
        f"实际弹出的是 {type(modal).__name__}，流程疑似被外部点击打断",
    )
    return False


def _ok_button(form: ScheduleForm) -> None:
    form._buttons.button(QDialogButtonBox.StandardButton.Ok).click()


def _cancel_button(form: ScheduleForm) -> None:
    form._buttons.button(QDialogButtonBox.StandardButton.Cancel).click()


def fill_and_submit(
    *,
    title: str = "",
    date_text: str = "",
    time_text: str = "",
    notes: str = "",
) -> Callable[[QWidget], None]:
    """填四字段并点保存。字段原样写入，不在这里做任何加工。"""

    def act(modal: QWidget) -> None:
        if not _expect(modal, ScheduleForm, "新增/修改表单"):
            return
        form = cast(ScheduleForm, modal)
        form._title.setText(title)
        form._date.setText(date_text)
        form._time.setText(time_text)
        form._notes.setPlainText(notes)
        _ok_button(form)

    return act


def edit_title_and_submit(
    new_title: str, new_date_text: str | None = None
) -> Callable[[QWidget], None]:
    """改标题（可顺带改日期）后保存；其余字段保持预填值不动。"""

    def act(modal: QWidget) -> None:
        if not _expect(modal, ScheduleForm, "修改表单"):
            return
        form = cast(ScheduleForm, modal)
        form._title.setText(new_title)
        if new_date_text is not None:
            form._date.setText(new_date_text)
        _ok_button(form)

    return act


def check_prefill_and_cancel(expected_title: str) -> Callable[[QWidget], None]:
    """保存失败后表单会带着上次的草稿重开：先确认内容还在，再取消。"""

    def act(modal: QWidget) -> None:
        if not _expect(modal, ScheduleForm, "重开的表单"):
            return
        form = cast(ScheduleForm, modal)
        actual = form._title.text()
        check(
            "V-03 保存失败后已填内容原样保留在重新打开的表单里",
            actual == expected_title,
            f"title={actual!r}",
        )
        _cancel_button(form)

    return act


def dismiss_message_box(
    button: QMessageBox.StandardButton, shot: str | None = None
) -> Callable[[QWidget], None]:
    """点掉消息框；需要留证时顺手截一张图。"""

    def act(modal: QWidget) -> None:
        if not _expect(modal, QMessageBox, "消息框"):
            return
        box = cast(QMessageBox, modal)
        if shot:
            save(box.grab(), shot)
        target = box.button(button)
        if target is not None:
            target.click()

    return act


def open_date_picker(modal: QWidget) -> None:
    """点表单里的「选择」按钮，打开日期浮层。"""
    if not _expect(modal, ScheduleForm, "新增/修改表单"):
        return
    cast(ScheduleForm, modal)._pick_button.click()


def pick_day(day: dt.date, shot: str | None = None) -> Callable[[QWidget], None]:
    """在浮层里选中某天并确认；需要留证时截一张图。"""

    def act(modal: QWidget) -> None:
        if not _expect(modal, DatePickerPopup, "日期浮层"):
            return
        popup = cast(DatePickerPopup, modal)
        popup._calendar.setSelectedDate(QDate(day.year, day.month, day.day))
        if shot:
            save(popup.grab(), shot)
        popup.accept()

    return act


def check_backfill_and_cancel(expected_text: str) -> Callable[[QWidget], None]:
    """浮层选完回到表单：日期框应已是标准格式文本，且仍可继续手改。"""

    def act(modal: QWidget) -> None:
        if not _expect(modal, ScheduleForm, "浮层关闭后回到的表单"):
            return
        form = cast(ScheduleForm, modal)
        actual = form._date.text()
        check(
            "V-15 浮层点选后日期框回填为标准格式文本", actual == expected_text, f"date={actual!r}"
        )
        _cancel_button(form)

    return act


# ---------------------------------------------------------------------------
# 场景辅助
# ---------------------------------------------------------------------------


def build_window(service: RecordingService) -> MainWindow:
    return MainWindow(service=service, clock=lambda: TODAY)


def stub_service(today: dt.date) -> RecordingService:
    """内存替身 + 种子数据，包上记录仪（界面回归场景用）。"""
    stub = DevStubScheduleService()
    stub.seed_defaults(today)
    return RecordingService(stub)


#: 真服务场景的种子数据：与替身 `seed_defaults` 同形（3 条今天 + 相邻两天各 1）。
_REAL_SEED: Final[tuple[tuple[int, str, str, str], ...]] = (
    (0, "08:30", "晨读英语", "第 3 单元单词"),
    (0, "14:00", "数据结构习题课", "带上机报告"),
    (0, "19:30", "小组周会", "讨论接口对接"),
    (1, "10:00", "数据库实验", ""),
    (3, "15:00", "体育测试补测", "操场东侧集合"),
)


def _seed_real(service: RecordingService, today: dt.date) -> None:
    """经**真实服务**建种子数据——走的就是界面那份宽容解析，不是后门插入。"""
    for offset, time_text, title, notes in _REAL_SEED:
        service.create_schedule(
            title, (today + dt.timedelta(days=offset)).isoformat(), time_text, notes
        )


def run_scenario(
    app: QApplication,
    service: RecordingService,
    plan: list[Callable[[QWidget], None]],
    trigger: Callable[[MainWindow], None],
    window: MainWindow | None = None,
) -> MainWindow:
    """装载模态计划并触发一次用户操作，返回窗口供断言。

    默认每次新建窗口（场景之间互相隔离）；传入 `window` 则在既有窗口上继续
    操作——V-10 到 V-13 是同一窗口上的连续操作，后一步依赖前一步留下的
    选中态，不能各建新窗。
    """
    if window is None:
        window = build_window(service)
        window.show()
        app.processEvents()
    driver = ModalDriver(plan)
    driver.start()
    trigger(window)
    app.processEvents()
    return window


_TITLE_COLUMN: Final = 1  # 列表列序：0=时间 1=标题 2=备注


def _first_row_id(window: MainWindow) -> str | None:
    """按与 `main_window` 相同的角色取单元格里的 schedule_id。"""
    item = window._table.item(0, 0)
    return None if item is None else str(item.data(Qt.ItemDataRole.UserRole))


def _first_row_title(window: MainWindow) -> str:
    item = window._table.item(0, _TITLE_COLUMN)
    return "" if item is None else item.text()


def _titles(window: MainWindow) -> list[str]:
    """当前列表每行标题列的标题（供"某条在不在当前视图"类断言用）。"""
    titles: list[str] = []
    for row in range(window._table.rowCount()):
        item = window._table.item(row, _TITLE_COLUMN)
        titles.append("" if item is None else item.text())
    return titles


# ---------------------------------------------------------------------------
# 场景
# ---------------------------------------------------------------------------


def scenario_visuals(app: QApplication) -> None:
    """不出模态的基础画面：启动、选中、空态、闰月、表单。"""
    service = DevStubScheduleService()
    service.seed_defaults(TODAY)
    window = MainWindow(service=service, clock=lambda: TODAY)
    window.show()
    app.processEvents()

    # V-01 启动显示当天，列表与工具栏齐全
    check(
        "V-01 启动显示当天日程",
        window._table.rowCount() == 3,
        f"表格行数={window._table.rowCount()}",
    )
    check("V-01 顶部工具栏六个按钮", len(window._actions) == 6, str(list(window._actions)))
    save(window.grab(), "main-window.png")

    # V-05 选中一行，选中文案跟着变
    window._table.selectRow(0)
    app.processEvents()
    selection = window._selection_label.text()
    check(
        "V-05 选中行后同步选中文案",
        selection.startswith("已选中：08:30"),
        selection,
    )
    save(window.grab(), "main-window-selected.png")

    # 刷新按钮走真实路径
    window._actions["refresh"].trigger()
    app.processEvents()
    status = window._status_label.text()
    check("刷新按钮更新状态栏", status.startswith("已刷新"), status)

    # V-06 空状态：切到没有日程的日期
    empty_day = dt.date(2026, 10, 20)
    window._on_day_picked(empty_day)
    app.processEvents()
    first_cell = window._table.item(0, 0)
    check(
        "V-06 空日期显示空状态而不是白板",
        first_cell is not None and "还没有日程" in first_cell.text(),
        first_cell.text() if first_cell else "<空格子>",
    )
    check("V-06 空状态显示共 0 条", "共 0 条" in window._day_label.text(), window._day_label.text())
    save(window.grab(), "empty-state.png")

    # V-07 闰年：定位到 2028-02 抓一屏，供人眼确认
    leap_day = dt.date(2028, 2, 1)
    window._on_day_picked(leap_day)
    app.processEvents()
    leap_exists = True
    try:
        dt.date(2028, 2, 29)
    except ValueError:
        leap_exists = False
    check("V-07 2028-02-29 是可构造的日期", leap_exists)
    save(window.grab(), "calendar-leap-2028-02.png")

    # V-16 界面不拦日期写法：写完原样交出去
    request = FormRequest(
        mode="create",
        heading="新增日程",
        initial=ScheduleDraft(title="测试标题", date_text="明天", time_text="10:00", notes=""),
    )
    form = ScheduleForm(request)
    form.show()
    app.processEvents()
    draft = form.draft()
    check(
        "V-16 无法识别的日期原样离开表单（界面不拦）",
        draft.date_text == "明天" and draft.title == "测试标题",
        f"date_text={draft.date_text!r}",
    )
    save(form.grab(), "form-dialog.png")

    window.close()
    app.processEvents()


def scenario_create(app: QApplication, service: RecordingService) -> None:
    """V-02 新增保存成功；V-04 顺带验 `2026/10/15` 宽容解析。"""
    before = len(service.list_schedules(TODAY))
    window = run_scenario(
        app,
        service,
        [
            fill_and_submit(
                title="宽容解析验证", date_text="2026/10/15", time_text="07:45", notes=""
            )
        ],
        lambda w: w._actions["create"].trigger(),
    )
    after = len(service.list_schedules(TODAY))
    check(
        "V-02 保存成功后列表立即出现该条",
        window._table.rowCount() == before + 1,
        f"{before} -> {window._table.rowCount()} 行",
    )
    check(
        "V-02 保存后状态栏提示成功且表单已关闭",
        window._status_label.text().startswith("已新增"),
        window._status_label.text(),
    )
    check(
        "V-02 服务确实收到一次 create 调用", service.calls.count("create") == 1, str(service.calls)
    )
    check(
        "V-04 日期 2026/10/15 被后端宽容解析后保存成功",
        after == before + 1,
        f"当天条目 {before} -> {after}",
    )
    window.close()


def scenario_invalid_title(app: QApplication, service: RecordingService) -> None:
    """V-03 标题只空格：提示、不写入、内容保留。"""
    before = len(service.list_schedules(TODAY))
    window = run_scenario(
        app,
        service,
        [
            fill_and_submit(title="   ", date_text="2026-10-15", time_text="09:00", notes=""),
            dismiss_message_box(QMessageBox.StandardButton.Ok),
            check_prefill_and_cancel("   "),
        ],
        lambda w: w._actions["create"].trigger(),
    )
    check(
        "V-03 标题只空格时不予写入",
        len(service.list_schedules(TODAY)) == before,
        f"当天条目 {before} -> {len(service.list_schedules(TODAY))}",
    )
    # 界面层的纪律是**不校验、原样上交**（`ports.py` 与表单模块的约定）：
    # 只空格标题也照样调 create，由后端拒绝写入。所以"服务收到调用"在这里
    # 恰恰是正确行为——真正的"不予写入"由上一条断言覆盖。
    check(
        "V-03 界面不自己拦截：原始标题仍被交给后端（由后端拒绝）",
        "create" in service.calls,
        str(service.calls),
    )
    window.close()


def scenario_edit_keeps_id(app: QApplication, service: RecordingService) -> None:
    """V-08 修改标题后保存：列表更新、id 不变。"""
    window = build_window(service)
    window.show()
    app.processEvents()
    window._table.selectRow(0)
    app.processEvents()
    id_before = _first_row_id(window)

    driver = ModalDriver([edit_title_and_submit("晨读英语（改）")])
    driver.start()
    window._actions["edit"].trigger()
    app.processEvents()

    check(
        "V-08 修改后标题更新",
        _first_row_title(window) == "晨读英语（改）",
        _first_row_title(window),
    )
    check("V-08 修改后 schedule_id 不变", _first_row_id(window) == id_before, f"{id_before}")
    check(
        "V-08 行数不变（是修改不是新增）",
        window._table.rowCount() == 3,
        str(window._table.rowCount()),
    )
    check("V-08 服务收到一次 update 调用", service.calls.count("update") == 1, str(service.calls))
    window.close()


def scenario_edit_moves_day(app: QApplication, service: RecordingService) -> None:
    """V-09 把日期改到另一天：该条从当前列表移出，新日期下可见。"""
    window = build_window(service)
    window.show()
    app.processEvents()
    window._table.selectRow(0)
    app.processEvents()
    before = window._table.rowCount()

    driver = ModalDriver([edit_title_and_submit("体育测试补测（改）", new_date_text="2026-10-16")])
    driver.start()
    window._actions["edit"].trigger()
    app.processEvents()

    check(
        "V-09 改到其他日期后该条从当前列表移出",
        window._table.rowCount() == before - 1,
        f"{before} -> {window._table.rowCount()} 行",
    )
    window._on_day_picked(dt.date(2026, 10, 16))
    app.processEvents()
    titles = _titles(window)
    check(
        "V-09 切换到新日期后能看到该条",
        "体育测试补测（改）" in titles,
        str(titles),
    )
    window.close()


def scenario_delete_guards(app: QApplication, service: RecordingService) -> None:
    """V-10 未选中不调服务；V-11 取消不删；V-12 确定删除；V-13 重复删除不炸。"""
    # V-10：未选中任何行
    window = build_window(service)
    window.show()
    app.processEvents()
    before = window._table.rowCount()
    window = run_scenario(
        app,
        service,
        [dismiss_message_box(QMessageBox.StandardButton.Ok)],
        lambda w: w._actions["delete"].trigger(),
        window=window,
    )
    check(
        "V-10 未选中点删除时服务调用次数为 0",
        service.calls.count("delete") == 0,
        str(service.calls),
    )
    check("V-10 数据不变", window._table.rowCount() == before, str(window._table.rowCount()))

    # V-11：确认框点取消
    window._table.selectRow(0)
    app.processEvents()
    window = run_scenario(
        app,
        service,
        [dismiss_message_box(QMessageBox.StandardButton.No, shot="delete-confirm.png")],
        lambda w: w._actions["delete"].trigger(),
        window=window,
    )
    check(
        "V-11 确认框点取消后服务调用次数仍为 0",
        service.calls.count("delete") == 0,
        str(service.calls),
    )
    check(
        "V-11 列表与数据完全不变", window._table.rowCount() == before, str(window._table.rowCount())
    )

    # V-12：确认框点确定
    window._table.selectRow(0)
    app.processEvents()
    window = run_scenario(
        app,
        service,
        [dismiss_message_box(QMessageBox.StandardButton.Yes)],
        lambda w: w._actions["delete"].trigger(),
        window=window,
    )
    check(
        "V-12 确认删除后该条消失",
        window._table.rowCount() == before - 1,
        f"{before} -> {window._table.rowCount()} 行",
    )
    check("V-12 服务收到一次 delete 调用", service.calls.count("delete") == 1, str(service.calls))

    # V-13：删除后再点删除（此时已无选中项），不能崩、不能调服务
    status_after_delete = window._status_label.text()
    window = run_scenario(
        app,
        service,
        [dismiss_message_box(QMessageBox.StandardButton.Ok)],
        lambda w: w._actions["delete"].trigger(),
        window=window,
    )
    check(
        "V-13 重复删除不导致服务被再次调用",
        service.calls.count("delete") == 1,
        str(service.calls),
    )
    check(
        "V-13 删除成功时状态栏给出可理解提示",
        status_after_delete.startswith("已删除"),
        status_after_delete,
    )
    check(
        "V-13 程序仍可继续操作（列表行数稳定）",
        window._table.rowCount() == before - 1,
        str(window._table.rowCount()),
    )
    window.close()


def scenario_date_picker(app: QApplication, service: RecordingService) -> None:
    """V-15 日期浮层：打开、点选、回填、仍可继续编辑。"""
    window = run_scenario(
        app,
        service,
        [
            open_date_picker,
            pick_day(dt.date(2026, 11, 3), shot="date-picker-popup.png"),
            check_backfill_and_cancel("2026-11-03"),
        ],
        lambda w: w._actions["create"].trigger(),
    )
    check(
        "V-15 浮层流程走完后表单已关闭、没有误写入",
        "create" not in service.calls,
        str(service.calls),
    )
    window.close()


def scenario_real_service(app: QApplication) -> None:
    """真服务 + 真 SQLite 的接线验收：V-01 / V-02 / V-14 的真实版。

    存储层落地前这条场景不存在（替身退出即丢，V-14 无从验起）；现在
    `composition.connect() -> build_service()` 是真链路，重开连接即验持久化。
    数据库放在系统临时目录，不碰用户真实日程库。
    """
    db_dir = Path(tempfile.gettempdir()) / "sdms-acceptance"
    db_path = db_dir / "schedules.db"
    db_dir.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()

    created_title = "09:30 接线验证日程"

    # 第一幕：真连接 + 真服务，空库经服务建 5 条种子，再走表单新增一条。
    connection = composition.connect(db_path)
    service = RecordingService(composition.build_service(connection))
    _seed_real(service, TODAY)

    window = build_window(service)
    window.show()
    app.processEvents()
    check(
        "V-01 真服务版：空库建 3 条当天种子后启动即显示",
        window._table.rowCount() == 3,
        f"表格行数={window._table.rowCount()}",
    )

    window = run_scenario(
        app,
        service,
        [
            fill_and_submit(
                title=created_title,
                date_text=TODAY.isoformat(),
                time_text="9:30",
                notes="真服务写入",
            )
        ],
        lambda w: w._actions["create"].trigger(),
        window=window,
    )
    check(
        "V-02 真服务版：表单新增后列表立即出现该条",
        created_title in _titles(window),
        str(_titles(window)),
    )
    check(
        "V-02 真服务版：服务确实收到一次 create 调用",
        service.calls.count("create") == 1 + len(_REAL_SEED),
        str(service.calls),
    )
    check(
        "V-02 真服务版：状态栏提示成功且表单已关闭",
        window._status_label.text().startswith("已新增"),
        window._status_label.text(),
    )
    save(window.grab(), "main-window-real-service.png")

    # 直接查库：不经界面，证明真的落盘了。
    probe = composition.connect(db_path)
    try:
        rows = probe.execute(
            "SELECT title FROM schedules WHERE date = ?", (TODAY.isoformat(),)
        ).fetchall()
    finally:
        probe.close()
    check(
        "V-02 真服务版：直查 SQLite 当天已有该条",
        (created_title,) in rows,
        str(rows),
    )

    # 第二幕：关窗、关连接，再原样打开——V-14 的真身。
    window.close()
    connection.close()

    reopened = composition.connect(db_path)
    service2 = RecordingService(composition.build_service(reopened))
    window2 = build_window(service2)
    window2.show()
    app.processEvents()
    check(
        "V-14 真服务版：关窗关连接重开后数据还在",
        created_title in _titles(window2),
        str(_titles(window2)),
    )
    save(window2.grab(), "main-window-real-restart.png")
    window2.close()
    reopened.close()
    print(f"真服务验收数据库：{db_path}")


def main() -> int:
    """跑一遍全部场景；返回失败条数。"""
    app = QApplication(sys.argv)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    scenario_visuals(app)

    service = stub_service(TODAY)
    scenario_create(app, service)

    service = stub_service(TODAY)
    scenario_invalid_title(app, service)

    service = stub_service(TODAY)
    scenario_edit_keeps_id(app, service)

    service = stub_service(TODAY)
    scenario_edit_moves_day(app, service)

    service = stub_service(TODAY)
    scenario_delete_guards(app, service)

    service = stub_service(TODAY)
    scenario_date_picker(app, service)

    scenario_real_service(app)

    print(f"截图目录：{OUTPUT_DIR}")
    failed = 0
    for name, ok, detail in _checks:
        mark = "PASS" if ok else "FAIL"
        suffix = f"  ({detail})" if detail else ""
        print(f"[{mark}] {name}{suffix}")
        if not ok:
            failed += 1
    print(f"\n合计 {len(_checks)} 项，失败 {failed} 项")
    return failed


__all__ = ["main"]


if __name__ == "__main__":
    raise SystemExit(main())
