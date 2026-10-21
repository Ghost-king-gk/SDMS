"""主窗口的交互细节：置灰、双击、点空白、日历与列表同步、Esc、全天勾选。

还包括三条"只有真控件才验得出来"的：拖拽改期的载荷与落点、行内悬停的「⋯」、
表头排序。它们都不是 controller 的判断题，而是窗口这一层的事件与几何。

这些行为都属于"只有把真控件建出来才看得见"的一类：QAction 的可用性、
焦点与事件过滤器、日历内部 `QTableView` 的键盘处理。controller 单测覆盖不到，
`test_main_window_search.py` 也不该被塞成什么都测的大文件，因此单开一份。

运行在 offscreen 平台：这里断言的是控件状态与信号接线，不比较像素。
"""

from __future__ import annotations

import datetime as dt
import os
import re
from collections.abc import Iterator

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, QMimeData, QPoint, QPointF, Qt, QTimer
from PySide6.QtGui import (
    QDragEnterEvent,
    QDragLeaveEvent,
    QDragMoveEvent,
    QDropEvent,
    QMouseEvent,
    QWheelEvent,
)
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QTableView,
    QTableWidget,
    QToolBar,
    QToolButton,
)

from schedule_management.ui import theme
from schedule_management.ui.main_window import MainWindow
from schedule_management.ui.schedule_form import ScheduleForm
from schedule_management.ui.view_models import SCHEDULE_DRAG_MIME, FormRequest, ScheduleDraft
from tests.unit.ui_fakes import FakeScheduleService, StubSchedule, ValidationError

TODAY = dt.date(2026, 10, 20)
TOMORROW = dt.date(2026, 10, 21)


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    app = QApplication.instance()
    if not isinstance(app, QApplication):
        app = QApplication([])
    yield app


def hover_move(window: MainWindow, point: QPoint) -> None:
    """向表格 viewport 投递一次鼠标移动。

    离屏平台没有真实指针，`QTest.mouseMove` 发出的事件到不了 viewport；
    而这里要验的正是 window 的 eventFilter 接线，直接投事件最贴近被测行为。
    """
    event = QMouseEvent(
        QEvent.Type.MouseMove,
        QPointF(point),
        QPointF(point),
        Qt.MouseButton.NoButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    window.eventFilter(window._table.viewport(), event)


def build_window() -> tuple[MainWindow, FakeScheduleService]:
    service = FakeScheduleService(
        (
            StubSchedule(id="today", title="写周报", date=TODAY, time=dt.time(9, 30), notes=""),
            StubSchedule(id="tomorrow", title="体检", date=TOMORROW, time=dt.time(8, 0)),
        )
    )
    window = MainWindow(service=service, clock=lambda: TODAY)
    window.resize(1040, 680)
    window.show()
    QApplication.processEvents()
    return window, service


# --------------------------------------------------------------- 选中与置灰


def test_actions_requiring_selection_are_disabled_until_a_row_is_selected(
    qapp: QApplication,
) -> None:
    """没选中时「查看/修改/删除/复制」必须是灰的——灰掉的按钮自己就在说条件。"""
    window, _service = build_window()
    try:
        for key in ("view", "edit", "delete", "duplicate"):
            assert not window._actions[key].isEnabled(), f"{key} 不该在未选中时可用"
        assert window._actions["create"].isEnabled()
        assert window._actions["refresh"].isEnabled()

        window._table.selectRow(0)
        QApplication.processEvents()

        for key in ("view", "edit", "delete", "duplicate"):
            assert window._actions[key].isEnabled(), f"{key} 选中后应当可用"
    finally:
        window.close()


def test_clicking_blank_area_clears_selection(qapp: QApplication) -> None:
    """点列表空白处等于取消选中，底部不再显示「已选中」。"""
    window, _service = build_window()
    try:
        window._table.selectRow(0)
        QApplication.processEvents()
        assert window._controller.selected_id == "today"

        viewport = window._table.viewport()
        blank = viewport.rect().bottomLeft()
        QTest.mouseClick(viewport, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, blank)
        QApplication.processEvents()

        assert window._controller.selected_id is None
        assert not window._selection_label.text().startswith("已选中")
        assert not window._actions["delete"].isEnabled()
    finally:
        window.close()


def test_double_clicking_a_row_opens_edit(qapp: QApplication) -> None:
    """双击一行等于修改：不要求先去顶部工具栏点一下。"""
    window, _service = build_window()
    try:
        calls: list[str] = []
        window._controller.request_edit = lambda: calls.append("edit")  # type: ignore[method-assign]
        table = window.findChild(QTableWidget)
        assert table is not None

        table.itemDoubleClicked.emit(table.item(0, 2))
        QApplication.processEvents()

        assert calls == ["edit"]
    finally:
        window.close()


def test_empty_day_swaps_in_the_empty_state_with_a_create_action(qapp: QApplication) -> None:
    """空的那一天：表格整块换成空状态，并直接给一个「新增这一天」的入口。

    以前是往表格里插一行灰字，占着第一行却什么也点不了；空状态该把下一步交出来。
    """
    window, _service = build_window()
    try:
        window._on_day_picked(dt.date(2026, 12, 25))
        QApplication.processEvents()

        table = window.findChild(QTableWidget)
        assert table is not None and table.rowCount() == 0, "空状态不该再往表格插提示行"
        assert window._stack.currentWidget() is window._empty_state
        assert window._empty_state.title_text == "这一天还没有日程"
        assert window._empty_state.action_text == "新增这一天"

        asked: list[dt.date | None] = []

        def record_request(day: dt.date | None) -> None:
            asked.append(day)

        window._controller.request_create_for_day = record_request  # type: ignore[method-assign]
        window._empty_state.action_clicked.emit()
        QApplication.processEvents()

        assert asked == [dt.date(2026, 12, 25)], "按钮应当为当前这一天打开新增表单"
    finally:
        window.close()


def test_empty_search_offers_clearing_the_search(qapp: QApplication) -> None:
    """搜不到时那颗按钮是「清空搜索」，不是「新增」——两种空给不同的下一步。"""
    window, _service = build_window()
    try:
        search = window.findChild(QLineEdit, "SearchInput")
        assert search is not None
        search.setText("不存在的东西")
        search.returnPressed.emit()
        QApplication.processEvents()

        assert window._stack.currentWidget() is window._empty_state
        assert "没有找到匹配" in window._empty_state.title_text
        assert window._empty_state.action_text == "清空搜索"

        window._empty_state.action_clicked.emit()
        QApplication.processEvents()

        assert window._controller.search_text == ""
        assert window._stack.currentWidget() is window._table
    finally:
        window.close()


# ------------------------------------------------------- 日历与列表不会各说各话


def test_clicking_upcoming_item_moves_the_calendar_too(qapp: QApplication) -> None:
    """点摘要条目跳到 10-21：左侧日历的选中格必须一起走。"""
    window, _service = build_window()
    try:
        window._on_upcoming_clicked(window._upcoming_list.item(1))
        QApplication.processEvents()

        assert window._controller.current_day == TOMORROW
        assert window._calendar.selected_day() == TOMORROW, "左侧日历还停在旧日期"
    finally:
        window.close()


def test_arrow_key_on_calendar_filters_the_list(qapp: QApplication) -> None:
    """方向键换天也算换筛选日期：右侧列表与标题必须跟上。"""
    window, _service = build_window()
    try:
        view = window._calendar._calendar.findChild(QTableView)
        assert view is not None
        view.setFocus()
        QApplication.processEvents()

        QTest.keyClick(view, Qt.Key.Key_Right)
        QApplication.processEvents()

        assert window._controller.current_day == TOMORROW
        table = window.findChild(QTableWidget)
        assert table is not None
        assert table.rowCount() == 1
        title_cell = table.item(0, 2)
        assert title_cell is not None and title_cell.text() == "体检"
    finally:
        window.close()


# ------------------------------------------------------------------- 键盘


def test_escape_shortcut_exists_and_leaves_search_first(qapp: QApplication) -> None:
    """Esc 先退搜索：有搜索词时清搜索，没有时才取消选中。"""
    window, _service = build_window()
    try:
        assert window._escape_shortcut.key().toString() == "Esc"

        search = window.findChild(QLineEdit, "SearchInput")
        assert search is not None
        search.setText("周报")
        search.returnPressed.emit()
        QApplication.processEvents()
        assert window._controller.search_text == "周报"

        window._on_escape()
        QApplication.processEvents()

        assert window._controller.search_text == ""
        assert search.text() == ""
    finally:
        window.close()


def test_ctrl_z_is_wired_to_undo_delete(qapp: QApplication) -> None:
    """Ctrl+Z 与状态栏那个「撤销删除」等价，不能只留一个够不着的小按钮。"""
    window, _service = build_window()
    try:
        assert window._undo_shortcut.key().toString() == "Ctrl+Z"
        calls: list[str] = []
        window._controller.undo_delete = lambda: calls.append("undo")  # type: ignore[method-assign]

        # 撤销只在删除之后的 5 秒窗口里有效，所以先摆出"刚删过一条"的状态。
        window.show_undo_available(True)
        window._undo_shortcut.activated.emit()
        QApplication.processEvents()

        assert calls == ["undo"]
    finally:
        window.close()


def test_undo_entry_disappears_after_the_five_second_window(qapp: QApplication) -> None:
    """过了 5 秒：入口收起，Ctrl+Z 只在状态栏说一句"晚了"，不弹框也不真撤。"""
    window, _service = build_window()
    try:
        calls: list[str] = []
        window._controller.undo_delete = lambda: calls.append("undo")  # type: ignore[method-assign]
        window.show_undo_available(True)
        assert window._undo_button.isVisible()
        assert window._undo_timer.isActive(), "撤销窗口应当在显示入口时就启动"

        window._expire_undo()
        assert not window._undo_button.isVisible()

        window._undo_shortcut.activated.emit()
        QApplication.processEvents()

        assert calls == [], "窗口过了就不能再撤"
        assert "5 秒" in window._status_label.text()
    finally:
        window.close()


# ------------------------------------------------------------------- 表单


def _form(initial: ScheduleDraft | None, mode: str = "create") -> ScheduleForm:
    request = FormRequest(
        mode=mode,  # type: ignore[arg-type]
        heading="新增日程" if mode == "create" else "修改日程",
        initial=initial,
    )
    return ScheduleForm(request)


def test_all_day_checkbox_clears_and_disables_the_time_field(qapp: QApplication) -> None:
    """勾「全天」→ 时间框清空并禁用，提交的时间是空串。"""
    form = _form(ScheduleDraft(title="整理笔记", date_text="2026-10-20", time_text="", notes=""))
    try:
        assert form._time.isEnabled(), "新建时默认应当可以填时间"

        form._time.setText("19:30")
        form._all_day.setChecked(True)
        QApplication.processEvents()

        assert not form._time.isEnabled()
        assert form._time.text() == ""
        assert form.draft().time_text == ""

        form._all_day.setChecked(False)
        QApplication.processEvents()

        assert form._time.isEnabled()
    finally:
        form.close()


def test_all_day_checkbox_is_pre_checked_only_when_editing_an_all_day_item(
    qapp: QApplication,
) -> None:
    """修改一条全天日程时预勾；新建同名空白表单时不预勾，否则时间框一开就灰着。"""
    editing = _form(
        ScheduleDraft(title="整理笔记", date_text="2026-10-20", time_text="", notes=""),
        mode="edit",
    )
    creating = _form(ScheduleDraft(title="", date_text="2026-10-20", time_text="", notes=""))
    try:
        assert editing._all_day.isChecked()
        assert not creating._all_day.isChecked()
    finally:
        editing.close()
        creating.close()


# --------------------------------------------------------------- 删除确认框


def _answer_delete_box(seen: list[tuple[list[str], str]]) -> None:
    """在确认框弹出的那一刻记下按钮文案与默认按钮，然后点「取消」。"""
    box = QApplication.activeModalWidget()
    if not isinstance(box, QMessageBox):
        return
    texts = [button.text().replace("&", "") for button in box.buttons()]
    default = box.defaultButton()
    seen.append((texts, default.text().replace("&", "") if default is not None else ""))
    cancel = next(button for button in box.buttons() if button.text().replace("&", "") == "取消")
    cancel.click()


def test_delete_confirm_uses_chinese_buttons_and_defaults_to_cancel(qapp: QApplication) -> None:
    """弹框按钮说中文，且破坏性的「删除」不是默认按钮。"""
    window, _service = build_window()
    seen: list[tuple[list[str], str]] = []
    try:
        window._table.selectRow(0)
        QApplication.processEvents()
        row = window._controller.rows[0]

        QTimer.singleShot(50, lambda: _answer_delete_box(seen))
        answer = window.ask_delete_confirm(row)

        assert answer is False, "点「取消」不应返回 True"
        assert seen, "确认框没有按预期弹出"
        texts, default = seen[0]
        assert set(texts) == {"删除", "取消"}, texts
        assert default == "取消", "破坏性按钮不该是回车就执行的那一个"
    finally:
        window.close()


# ------------------------------------------------------------------- 排序


def build_sorted_window() -> MainWindow:
    """三条：一条全天、两条定时，用来验排序的默认顺序与反向。

    同时显式 show + resize：行内悬停按钮要靠真实几何定位，窗口没布局过就没有格子。
    """
    service = FakeScheduleService(
        (
            StubSchedule(id="b", title="Bravo", date=TODAY, time=dt.time(9, 30)),
            StubSchedule(id="a", title="Alpha", date=TODAY, time=dt.time(8, 0)),
            StubSchedule(id="c", title="Charlie", date=TODAY, time=None),
        )
    )
    window = MainWindow(service=service, clock=lambda: TODAY)
    window.resize(1040, 680)
    window.show()
    QApplication.processEvents()
    return window


def column_values(table: QTableWidget, column: int) -> list[str]:
    values: list[str] = []
    for row in range(table.rowCount()):
        item = table.item(row, column)
        values.append("" if item is None else item.text())
    return values


def test_time_header_sorts_all_day_first_then_toggles_desc(qapp: QApplication) -> None:
    """点「时间」列：全天在最前，再按 HH:MM；再点一次整体反向。"""
    window = build_sorted_window()
    try:
        table = window.findChild(QTableWidget)
        assert table is not None
        assert column_values(table, 2) == ["Bravo", "Alpha", "Charlie"], "默认应保持后端顺序"

        window._on_header_clicked(1)
        QApplication.processEvents()
        assert column_values(table, 2) == ["Charlie", "Alpha", "Bravo"], "全天应排在最前"

        window._on_header_clicked(1)
        QApplication.processEvents()
        assert column_values(table, 2) == ["Bravo", "Alpha", "Charlie"], "再点应反向"
        assert table.horizontalHeader().sortIndicatorSection() == 1
    finally:
        window.close()


def test_title_header_uses_collation_not_raw_codepoint_order(qapp: QApplication) -> None:
    """标题列用 QCollator 排序：直接 sorted() 会得到与语言无关的乱序。"""
    window = build_sorted_window()
    try:
        table = window.findChild(QTableWidget)
        assert table is not None

        window._on_header_clicked(2)
        QApplication.processEvents()

        assert column_values(table, 2) == ["Alpha", "Bravo", "Charlie"]
    finally:
        window.close()


def test_sorted_column_says_its_direction_in_the_header_text(qapp: QApplication) -> None:
    """表头文字自带箭头：只靠 Qt 那个小三角，排的是哪一列、升还是降都看不清。"""
    window = build_sorted_window()
    try:
        table = window.findChild(QTableWidget)
        assert table is not None

        def headers() -> list[str]:
            items = [table.horizontalHeaderItem(index) for index in range(4)]
            return ["" if item is None else item.text() for item in items]

        assert headers() == ["日期", "时间", "标题", "备注"], "没排过序时不该带箭头"

        window._on_header_clicked(1)
        QApplication.processEvents()
        assert headers() == ["日期", "时间 ↑", "标题", "备注"]

        window._on_header_clicked(1)
        QApplication.processEvents()
        assert headers() == ["日期", "时间 ↓", "标题", "备注"], "换个方向箭头要跟着翻"

        window._on_header_clicked(2)
        QApplication.processEvents()
        assert headers() == ["日期", "时间", "标题 ↑", "备注"], "换列时上一列的箭头必须撤掉"
    finally:
        window.close()


# --------------------------------------------------------------- 键盘可达


def test_toolbar_buttons_are_in_the_tab_chain(qapp: QApplication) -> None:
    """Tab 必须能走到工具栏：QToolButton 默认 NoFocus，「修改」又没有快捷键。"""
    window, _service = build_window()
    try:
        window.activateWindow()
        window.setFocus()
        QApplication.processEvents()

        seen: list[str] = []
        for _ in range(16):
            window.focusNextChild()
            QApplication.processEvents()
            focused = window.focusWidget()
            if isinstance(focused, QToolButton):
                seen.append(focused.text())

        assert "新增" in seen, f"Tab 链里没有工具栏按钮：{seen}"
    finally:
        window.close()


def test_time_field_offers_common_time_suggestions(qapp: QApplication) -> None:
    """时间框带候选，但仍然是可以自由输入的普通输入框。"""
    form = _form(ScheduleDraft(title="", date_text="2026-10-20", time_text="", notes=""))
    try:
        completer = form._time.completer()
        assert completer is not None
        model = completer.model()
        assert model is not None
        suggestions = [model.index(row, 0).data() for row in range(model.rowCount())]
        assert "09:00" in suggestions and "19:30" in suggestions
    finally:
        form.close()


# ------------------------------------------------------------- 拖动改期
#
# 拖放不经过 controller 的表单路径：拖起一行 → 落到日历某天 → 松手即提交。
# 这里要验三件事：载荷里只有 id（不带整行副本）、落点算得准、松手才写。


def panel_point_for(panel: object, day: dt.date) -> QPoint:
    """日历面板坐标里，`day` 那一格的正中点。

    `date_at()` 是从坐标反推日期，这里做它的逆运算：按「当月 1 日、周一开头」
    算出行列，再取该格中心换算到面板坐标系。两步互为逆函数，落点才可信。
    """
    calendar = panel._calendar  # type: ignore[attr-defined]
    view = calendar.findChild(QTableView)
    assert view is not None
    first = dt.date(calendar.yearShown(), calendar.monthShown(), 1)
    row, column = divmod((day - first).days + first.weekday(), 7)
    model = view.model()
    assert model is not None
    rect = view.visualRect(model.index(row, column))
    assert rect.width() > 0 and rect.height() > 0, "目标日期格没有绘制出来，窗口尺寸可能太小"
    in_calendar = view.viewport().mapTo(calendar, rect.center())
    point: QPoint = calendar.mapTo(panel, in_calendar)
    return point


class Drag:
    """一次拖放：载荷 + 由它派生的事件。

    **载荷必须和事件同时活着**。Qt 侧保存的是裸指针，事件本身不持有载荷；
    载荷被回收之后再去读 `mimeData()` 会直接段错误，而不是抛异常——所以这里
    把两者放同一个对象里，谁用谁就自然一起活着。
    """

    def __init__(self, payload: bytes = b"today", mime: QMimeData | None = None) -> None:
        self.mime = QMimeData() if mime is None else mime
        if mime is None:
            self.mime.setData(SCHEDULE_DRAG_MIME, payload)

    def enter(self, point: QPoint) -> QDragEnterEvent:
        return QDragEnterEvent(
            QPointF(point),
            Qt.DropAction.MoveAction,
            self.mime,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )

    def move(self, point: QPoint) -> QDragMoveEvent:
        return QDragMoveEvent(
            QPointF(point),
            Qt.DropAction.MoveAction,
            self.mime,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )

    def drop(self, point: QPoint) -> QDropEvent:
        return QDropEvent(
            QPointF(point),
            Qt.DropAction.MoveAction,
            self.mime,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )


def test_drag_payload_carries_only_the_schedule_id(qapp: QApplication) -> None:
    """拖拽载荷里只有一个 id：不要整行副本，落点那头就不必反解"这是哪条"。"""
    window, _service = build_window()
    try:
        table = window.findChild(QTableWidget)
        assert table is not None
        assert table.dragDropMode() == QTableWidget.DragDropMode.DragOnly

        item = table.item(0, 0)
        assert item is not None
        mime = table.mimeData([item])
        assert mime is not None

        assert mime.formats() == [SCHEDULE_DRAG_MIME]
        assert mime.data(SCHEDULE_DRAG_MIME).data() == b"today"
    finally:
        window.close()


def test_calendar_accepts_our_rows_and_refuses_foreign_payloads(qapp: QApplication) -> None:
    """只认自己的行：别把随便一段文字或一个文件拖进日历就当成改期。"""
    window, _service = build_window()
    try:
        panel = window._calendar
        assert panel.acceptDrops()

        ours = Drag()
        enter_ours = ours.enter(QPoint(10, 10))
        panel.dragEnterEvent(enter_ours)
        assert enter_ours.isAccepted()

        foreign_mime = QMimeData()
        foreign_mime.setText("随便一段文字")
        enter_foreign = Drag(mime=foreign_mime).enter(QPoint(10, 10))
        panel.dragEnterEvent(enter_foreign)
        assert not enter_foreign.isAccepted()
    finally:
        window.close()


def test_drop_hint_follows_the_pointer_and_is_cleared_on_leave(qapp: QApplication) -> None:
    """拖动经过时落点格描边，移出日期区或离开面板就清掉——不然框会留在原地。"""
    window, _service = build_window()
    try:
        panel = window._calendar
        target = panel_point_for(panel, TOMORROW)
        assert panel._day_at(target) == TOMORROW, "逆运算没有落回目标日期"

        drag = Drag()
        panel.dragMoveEvent(drag.move(target))
        assert panel._calendar._drop_hint == TOMORROW

        panel.dragLeaveEvent(QDragLeaveEvent())
        assert panel._calendar._drop_hint is None
    finally:
        window.close()


def test_dropping_a_row_on_a_calendar_day_reschedules_it(qapp: QApplication) -> None:
    """把「写周报」拖到 10-21：松手就写库，标题时间不变、只改日期，且不弹表单。"""
    window, service = build_window()
    try:
        panel = window._calendar
        rows_before = len(window._controller.rows)
        drag = Drag()
        panel.dropEvent(drag.drop(panel_point_for(panel, TOMORROW)))
        QApplication.processEvents()

        moved = next(item for item in service.items if item.id == "today")
        assert moved.date == TOMORROW, "拖到哪天就该是哪天"
        assert moved.time == dt.time(9, 30), "改期不该顺手把时间改掉"
        assert moved.title == "写周报"
        updates = service.calls_of("update")
        assert updates and updates[-1][1] == "today"
        assert rows_before == 1, "拖放前列表里只有当天这一条"
        assert window._controller.rows == (), "改完之后这一天就没有日程了"
    finally:
        window.close()


def test_dropping_outside_the_date_grid_does_nothing(qapp: QApplication) -> None:
    """松手在表头/按钮行上（不是日期格）：什么都不写，也不报错。"""
    window, service = build_window()
    try:
        panel = window._calendar
        before = tuple(service.items)

        header_point = QPoint(panel.width() // 2, 2)
        assert panel._day_at(header_point) is None
        drag = Drag()
        event = drag.drop(header_point)
        panel.dropEvent(event)

        assert not event.isAccepted()
        assert tuple(service.items) == before
        assert service.calls_of("update") == []
    finally:
        window.close()


# --------------------------------------------------------- 行内悬停「⋯」
#
# 悬停浮出的按钮不占列、不进 Tab 链，只在指针压在某一行上时出现；
# 点它等价于在那行右键。用几何位置直接驱动，比合成鼠标移动稳定。


def test_hovering_a_row_floats_the_row_menu_button_there(qapp: QApplication) -> None:
    """指针落在第 2 行上，「⋯」出现在这一行右端并记住是哪一行。"""
    window = build_sorted_window()
    try:
        table = window.findChild(QTableWidget)
        assert table is not None
        assert table.columnCount() == 4, "悬停按钮是浮层，不该多出一列"

        # 用**可见**的标题列取几何：日期列在单日视图里是收起的，
        # 隐藏列的 visualRect 是空矩形，拿它算落点会落到第 0 行。
        rect = table.visualRect(table.model().index(1, 2))
        assert rect.height() > 0
        window._sync_row_menu(rect.center())

        assert window._row_menu_button.isVisible()
        assert window._row_menu_row == 1
        assert window._row_menu_button.parentWidget() is table.viewport()
        geometry = window._row_menu_button.geometry()
        assert rect.top() <= geometry.center().y() <= rect.bottom(), "按钮没落在悬停的那一行"
    finally:
        window.close()


def test_row_menu_button_hides_over_blank_space(qapp: QApplication) -> None:
    """指针滑到表格下方空白处，按钮收起，不会一直挂在最后一行上。"""
    window = build_sorted_window()
    try:
        table = window.findChild(QTableWidget)
        assert table is not None
        rect = table.visualRect(table.model().index(0, 0))
        window._sync_row_menu(rect.center())
        assert window._row_menu_button.isVisible()

        window._sync_row_menu(table.viewport().rect().bottomLeft())
        assert not window._row_menu_button.isVisible()
        assert window._row_menu_row is None
    finally:
        window.close()


def test_row_menu_selects_that_row_and_offers_the_same_four_actions(
    qapp: QApplication,
) -> None:
    """点「⋯」：先选中那一行，菜单与工具栏共用同一批动作，不另立一套。"""
    window = build_sorted_window()
    try:
        table = window.findChild(QTableWidget)
        assert table is not None
        # 用**可见**的标题列取几何：日期列在单日视图里是收起的，
        # 隐藏列的 visualRect 是空矩形，拿它算落点会落到第 0 行。
        rect = table.visualRect(table.model().index(1, 2))
        window._sync_row_menu(rect.center())

        menu = window._prepare_row_menu(window._row_menu_row)
        assert isinstance(menu, QMenu)
        try:
            labels = [action.text() for action in menu.actions() if not action.isSeparator()]
            # 快捷键画在文字里（`\t` 之后是快捷键列）：实现了却不写出来，
            # 等于只有读过 README 的人知道。
            assert labels == ["查看\tEnter", "修改\t双击", "复制到…\tCtrl+D", "删除\tDelete"]
            assert any(action.isSeparator() for action in menu.actions()), "删除应当被分隔线隔开"
            delete_action = menu.actions()[-1]
            assert delete_action.text().startswith("删除")
            assert not delete_action.icon().isNull(), "破坏项要带图标，不能只靠文字"
            assert window._controller.selected_id == "a", "菜单应当先选中被点的那一行"
            assert table.currentRow() == 1
            assert window._actions["delete"].isEnabled()
        finally:
            menu.deleteLater()
    finally:
        window.close()


def test_prepare_row_menu_returns_none_when_the_row_is_gone(qapp: QApplication) -> None:
    """行已经不存在（刷新掉了）时返回 None，不能弹出一个空菜单。"""
    window, _service = build_window()
    try:
        assert window._prepare_row_menu(None) is None
        assert window._prepare_row_menu(window._table.rowCount() + 5) is None
    finally:
        window.close()


# ------------------------------------------------ 视觉层级与窗口状态的记忆


def test_hovering_a_row_tints_the_whole_row_not_just_one_cell(qapp: QApplication) -> None:
    """整行悬停由 delegate 画：QSS 的 `::item:hover` 只染鼠标所在的那一个格子。

    指针压在备注列上时，只让备注列变灰会把一行断成两截——扫读时反而更乱。
    """
    window = build_sorted_window()
    try:
        table = window.findChild(QTableWidget)
        assert table is not None
        assert table.rowCount() == 3
        # 故意停在最后一列（备注），确认整行都跟着变。
        # 这里直接投递 MouseMove 而不是 QTest.mouseMove：离屏平台不产生真实指针，
        # QTest 发出的移动事件到不了 viewport。
        hover_move(window, table.visualRect(table.model().index(1, 3)).center())

        assert window._row_delegate.hover_row == 1

        # 指针滑到表格下方空白：底色跟着收起，不会留在最后一行上
        window._sync_row_menu(table.viewport().rect().bottomLeft())
        assert window._row_delegate.hover_row is None
    finally:
        window.close()


def test_selection_bar_lands_on_the_first_visible_column(qapp: QApplication) -> None:
    """单日视图收起日期列之后，选中竖条必须改画在时间列上。

    `QHeaderView.logicalIndex(0)` 在这里不可靠：隐藏的 section 仍占着视觉索引位，
    它照样返回 0，竖条就会画在一条根本不被绘制的列上——界面上什么都看不到。
    """
    window, _service = build_window()
    try:
        table = window.findChild(QTableWidget)
        assert table is not None
        assert table.isColumnHidden(0), "前提：单日视图默认收起日期列"
        assert window._first_visible_column() == 1
    finally:
        window.close()


def test_toolbar_gives_create_and_delete_their_own_weight(qapp: QApplication) -> None:
    """七个入口不该同一音量：「新增」是主要动作，「删除」是唯一不可逆的动作。"""
    window, _service = build_window()
    try:
        toolbar = window.findChild(QToolBar)
        assert toolbar is not None
        create = toolbar.widgetForAction(window._actions["create"])
        delete = toolbar.widgetForAction(window._actions["delete"])
        view = toolbar.widgetForAction(window._actions["view"])

        assert create.objectName() == "PrimaryAction"
        assert delete.objectName() == "DangerAction"
        assert view.objectName() == "", "其余入口保持同一种次级样式，不再分档"
    finally:
        window.close()


def test_double_clicking_blank_space_also_starts_a_new_item(qapp: QApplication) -> None:
    """列表空白双击等于新增这一天，与日历上双击某个日期是同一个手势。"""
    window, _service = build_window()
    try:
        asked: list[dt.date | None] = []
        window._controller.request_create_for_day = asked.append  # type: ignore[assignment]
        table = window.findChild(QTableWidget)
        assert table is not None

        blank = QPoint(60, table.viewport().height() - 20)
        assert table.indexAt(blank).isValid() is False, "前提：这个点必须在行下方"
        QTest.mouseDClick(table.viewport(), Qt.MouseButton.LeftButton, pos=blank)
        QApplication.processEvents()

        assert asked == [TODAY]
    finally:
        window.close()


def test_double_click_on_blank_space_is_ignored_while_searching(qapp: QApplication) -> None:
    """搜索态列表说的是"全库里命中这些"，空白处代表哪一天是含糊的，不猜。"""
    window, _service = build_window()
    try:
        asked: list[dt.date | None] = []
        window._controller.request_create_for_day = asked.append  # type: ignore[assignment]
        window._controller.set_search("不存在的东西")
        QApplication.processEvents()

        window._on_blank_double_clicked()

        assert asked == []
    finally:
        window.close()


def test_column_width_and_sort_survive_a_restart(qapp: QApplication) -> None:
    """列宽与排序方向存进 QSettings：下次启动不必重新拖一遍、点一次表头。"""
    window, _service = build_window()
    try:
        window._table.setColumnWidth(2, 260)
        window._on_header_clicked(2)
        QApplication.processEvents()
        assert window._sort_column == 2
    finally:
        window.close()

    reopened, _service2 = build_window()
    try:
        assert reopened._table.columnWidth(2) == 260, "列宽没记住"
        assert reopened._sort_column == 2
        assert reopened._sort_desc is False
        header = reopened._table.horizontalHeaderItem(2)
        assert header is not None and header.text() == "标题 ↑", "排序方向也要跟着回来"
    finally:
        reopened.close()


def test_switching_theme_repaints_cells_with_the_new_text_colour(qapp: QApplication) -> None:
    """时间/标题的字色是逐格设的（不走 QSS），换主题后必须整表重画。

    漏了这一步的表现是：切到深色后时间列整列消失——上一套主题的深灰字
    压在深色底上，看起来像数据没加载出来。
    """
    window, _service = build_window()
    try:
        window._on_dark_toggled(True)
        QApplication.processEvents()

        item = window._table.item(0, 1)
        assert item is not None
        assert item.foreground().color().name() == theme.DARK_PALETTE.text.lower()
    finally:
        window.close()


def test_theme_switch_keeps_its_label_and_speaks_through_icon_and_tooltip(
    qapp: QApplication,
) -> None:
    """文字固定写「深色模式」，改由图标与 tooltip 说清"现在是什么、点了变什么"。

    以前文字是"点下去会变成什么"（深色下写「浅色模式」），同时又挂着勾选态，
    读者要同时理解"勾着"和"写着浅色"两个互相矛盾的信息。
    """

    def icon_pixels() -> bytes:
        """图标画出来的像素：QIcon.cacheKey 每次新建都变，比不了内容。"""
        image = window._dark_action.icon().pixmap(16, 16).toImage()
        return bytes(image.constBits())

    window, _service = build_window()
    try:
        assert not window._dark_action.isCheckable()
        assert window._dark_action.text() == "深色模式"
        light_icon = icon_pixels()
        assert "浅色" in window._dark_action.toolTip()

        window._dark_action.trigger()
        QApplication.processEvents()
        assert window._dark is True
        assert window._dark_action.text() == "深色模式", "文字不随状态改名"
        assert icon_pixels() != light_icon, "图标要换（月亮↔太阳）"
        assert "深色" in window._dark_action.toolTip()

        window._dark_action.trigger()
        QApplication.processEvents()
        assert window._dark is False
        assert icon_pixels() == light_icon, "切回浅色要画回月亮"
    finally:
        window.close()


def test_status_bar_says_when_the_list_was_synced(qapp: QApplication) -> None:
    """「就绪」什么都不说明；「21:03 更新」回答"我看到的是不是刚才那一次"。"""
    window, _service = build_window()
    try:
        assert re.fullmatch(r"\d{2}:\d{2} 更新", window._summary_label.text())
        # 条数在左侧状态里已经写过，右侧不重复
        assert "共" not in window._summary_label.text()
    finally:
        window.close()


def test_upcoming_groups_items_of_the_same_day_under_one_date(qapp: QApplication) -> None:
    """同一天的第二条起不再重复日期：重复的两段会把时间与标题挤到后半行。"""
    service = FakeScheduleService(
        (
            StubSchedule(id="a", title="晨读英语", date=TODAY, time=dt.time(8, 30)),
            StubSchedule(id="b", title="数据结构习题课", date=TODAY, time=dt.time(14, 0)),
            StubSchedule(id="c", title="数据库实验", date=TOMORROW, time=dt.time(10, 0)),
        )
    )
    window = MainWindow(service=service, clock=lambda: TODAY)
    window.resize(1040, 680)
    window.show()
    QApplication.processEvents()
    try:
        upcoming = window._upcoming_list
        texts = [upcoming.item(row).text() for row in range(upcoming.count())]
        assert texts[0] == "10-20 周二 · 08:30 · 晨读英语"
        assert texts[1] == "14:00 · 数据结构习题课", "同一天的第二条不该再写日期"
        assert texts[2].startswith("10-21 周三"), "换了一天就要重新写日期"
    finally:
        window.close()


# ------------------------------------------------- 本轮补齐的 11 项里的窗口侧


def test_blank_context_menu_offers_create_and_refresh(qapp: QApplication) -> None:
    """空白处右键不再毫无反应：给两个不需要先选一条的动作。"""
    window, _service = build_window()
    try:
        menu = window._build_blank_menu()
        try:
            labels = [action.text() for action in menu.actions() if not action.isSeparator()]
            assert labels == ["新增这一天\tCtrl+N", "刷新\tF5"]
        finally:
            menu.deleteLater()
    finally:
        window.close()


def test_first_run_empty_state_explains_where_the_data_lives(qapp: QApplication) -> None:
    """一条都没有时说的是"数据存在本机，先记一条"，而不是"这一天没有日程"。"""
    window = MainWindow(service=FakeScheduleService(()), clock=lambda: TODAY)
    QApplication.processEvents()
    try:
        assert window._seen_rows is False
        assert window._empty_state.title_text == "还没有任何日程"
        assert window._empty_state.action_text == "记第一条"
    finally:
        window.close()


def test_empty_day_after_seeing_rows_uses_the_day_wording(qapp: QApplication) -> None:
    """见过日程之后再遇到空的一天，说的是"这天没安排"，不是"你还没开始用"。"""
    service = FakeScheduleService(
        (StubSchedule(id="a", title="体检", date=TOMORROW, time=dt.time(8, 0)),)
    )
    window = MainWindow(service=service, clock=lambda: TODAY)
    QApplication.processEvents()
    try:
        assert window._seen_rows is True, "只要求今天为空、但别的日子有内容"
        assert window._empty_state.title_text == "这一天还没有日程"
    finally:
        window.close()


def test_failed_save_reuses_the_same_dialog_and_shows_the_error_inside(
    qapp: QApplication,
) -> None:
    """保存失败不再"弹框 → 关表单 → 重开"：同一实例再 exec 一次，错误在顶部。"""
    service = FakeScheduleService((), create_error=ValidationError("标题不能为空"))
    window = MainWindow(service=service, clock=lambda: TODAY)
    seen: list[tuple[int, bool, str]] = []
    instances: list[ScheduleForm] = []
    original_exec = ScheduleForm.exec

    def fake_exec(form: ScheduleForm) -> int:
        instances.append(form)
        # 用 isHidden 而不是 isVisible：假 exec 没有真正显示窗口，
        # 未显示的父窗口会让所有子控件的 isVisible() 都是 False。
        seen.append((len(seen), not form._error_label.isHidden(), form._error_label.text()))
        if len(seen) == 1:
            form._title.setText("写周报")
            return QDialog.DialogCode.Accepted
        return QDialog.DialogCode.Rejected

    ScheduleForm.exec = fake_exec  # type: ignore[assignment]
    try:
        window._controller.request_create()
    finally:
        ScheduleForm.exec = original_exec  # type: ignore[method-assign]
        window.close()

    assert len(seen) == 2, "失败后应当再问一次"
    assert instances[0] is instances[1], "必须是同一个对话框，不是新建一个"
    assert seen[0][1] is False, "第一次打开不该有错误条"
    assert seen[1][1] is True and "标题不能为空" in seen[1][2]


def test_title_field_marks_required_and_warns_only_when_too_long(qapp: QApplication) -> None:
    """红点常驻说"必填"；超长只提示会截断，不拦保存。"""
    form = _form(None)
    try:
        marks = [
            child for child in form.findChildren(QLabel) if child.objectName() == "RequiredMark"
        ]
        assert len(marks) == 1 and marks[0].text() == "*"
        assert form._title.property("requiredMissing") is True, "空标题时边框应当变红"

        form._title.setText("x" * 10)
        assert form._title_hint.isHidden(), "10 字不该提示"
        assert form._title.property("requiredMissing") is False

        form._title.setText("x" * 81)
        assert not form._title_hint.isHidden()
        assert "81" in form._title_hint.text()
    finally:
        form.close()


def test_notes_column_is_interactive_and_still_readable(qapp: QApplication) -> None:
    """四列全部 Interactive：只有这样才能双击分隔线自适应内容。"""
    window, _service = build_window()
    try:
        header = window._table.horizontalHeader()
        for column in range(window._table.columnCount()):
            assert header.sectionResizeMode(column) == QHeaderView.ResizeMode.Interactive
        assert window._table.columnWidth(3) >= 120, "备注列不能被压到看不见"
    finally:
        window.close()


def _wheel(delta_y: int, modifiers: Qt.KeyboardModifier) -> QWheelEvent:
    point = QPointF(10.0, 10.0)
    return QWheelEvent(
        point,
        point,
        QPoint(0, 0),
        QPoint(0, delta_y),
        Qt.MouseButton.NoButton,
        modifiers,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )


def test_ctrl_wheel_turns_the_month_but_a_plain_wheel_does_not(qapp: QApplication) -> None:
    """Ctrl+滚轮翻月；不按 Ctrl 的滚轮不该被日历吃掉（否则一滑就换月）。"""
    window, _service = build_window()
    try:
        panel = window._calendar
        calendar = panel._calendar
        before = (calendar.yearShown(), calendar.monthShown())

        assert panel.eventFilter(calendar, _wheel(120, Qt.KeyboardModifier.NoModifier)) is False
        assert (calendar.yearShown(), calendar.monthShown()) == before

        assert panel.eventFilter(calendar, _wheel(120, Qt.KeyboardModifier.ControlModifier)) is True
        assert (calendar.yearShown(), calendar.monthShown()) != before, "Ctrl+上滚应当翻到上个月"
    finally:
        window.close()


def test_calendar_and_summary_stop_growing_with_the_window(qapp: QApplication) -> None:
    """日历有最大高度、摘要随窗口拉伸：窗口变高时多出来的空间给列表。"""
    window, _service = build_window()
    try:
        assert window._calendar.maximumHeight() < 1000, "日历不该被拉成一张大网"
        assert window._upcoming_list.minimumHeight() >= 90
        assert window._upcoming_list.maximumHeight() > 1000, "摘要不再钉死高度"
    finally:
        window.close()
