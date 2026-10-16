"""主窗口：`MainViewPort` 的 Qt 实现，整个界面唯一的 Qt 装订点。

这一模块的自我要求只有一条：**它只做适配，不做决定**。

- 六个按钮点了之后该调什么组织组合式调用，一概不问，转手交给 `controller`；
- 列表怎么排序、选中未选中算什么、报错该说什么话，也一概不问——
  那都是 `presenters` 与后端给的结论；
- 它负责的就是"这些数据在 Qt 上怎么摆出来、用户动了哪个控件"。

按第 3 节的四段式布局：顶部工具栏（六按钮）、左日历、右列表、底部状态栏。
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence
from typing import Final

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from . import presenters
from .calendar_view import CalendarPanel
from .controller import ScheduleController
from .ports import ScheduleServicePort, TodayProvider
from .schedule_form import open_schedule_form
from .view_models import FormRequest, ScheduleDraft, ScheduleRow

_COLUMN_HEADERS: Final = ("时间", "标题", "备注")
_ID_ROLE: Final = Qt.ItemDataRole.UserRole
_EMPTY_HINT: Final = "这一天还没有日程。点「新增」记一条。"

_BUTTONS: Final = (
    ("create", "新增", "新增一条日程"),
    ("view", "查看", "查看选中日程的详情"),
    ("edit", "修改", "修改选中的日程"),
    ("delete", "删除", "删除选中的日程"),
    ("refresh", "刷新", "重新载入当前日期的日程"),
    ("quit", "退出", "退出程序"),
)


class MainWindow(QMainWindow):
    """主界面：实现 `MainViewPort`，把 Qt 控件的所有输入输出翻译成端口调用。"""

    def __init__(
        self,
        service: ScheduleServicePort,
        clock: TodayProvider = dt.date.today,
    ) -> None:
        super().__init__()
        self.setWindowTitle("日程管理系统")
        self.resize(920, 600)

        self._calendar = CalendarPanel()
        self._calendar.setMinimumWidth(320)
        self._day_label = QLabel("")
        self._table = QTableWidget(0, len(_COLUMN_HEADERS))
        self._status_label = QLabel("就绪")
        self._selection_label = QLabel(presenters.selection_text(None))

        self._build_layout()
        self._build_toolbar()
        self._wire_table()

        # controller 放在 UI 建完之后创建：它需要把自己登记为 view，
        # 而写法的 `__init__` 走完后 `self` 才算可用。
        self._controller: ScheduleController = ScheduleController(
            service=service, view=self, clock=clock
        )

        self._controller.start()

    # ------------------------------------------------------------ 构建 UI

    def _build_layout(self) -> None:
        self._table.setHorizontalHeaderLabels(list(_COLUMN_HEADERS))
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.verticalHeader().setVisible(False)
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)

        right = QVBoxLayout()
        right.addWidget(self._day_label)
        right.addWidget(self._table, 1)

        right_widget = QWidget()
        right_widget.setLayout(right)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._calendar)
        splitter.addWidget(right_widget)
        splitter.setStretchFactor(1, 1)
        self.setCentralWidget(splitter)

        status = QStatusBar()
        status.addWidget(self._status_label, 1)
        status.addPermanentWidget(self._selection_label)
        self.setStatusBar(status)
        status.setSizeGripEnabled(False)

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("主操作", self)
        toolbar.setMovable(False)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)

        self._actions: dict[str, QAction] = {}
        for key, text, tip in _BUTTONS:
            action = QAction(text, self)
            action.setToolTip(tip)
            toolbar.addAction(action)
            self._actions[key] = action

        # 接转发方法而不是直接接 controller：这里按下就算一次用户操作，
        # 具体该怎么办由 controller 说了算，窗口本身不做判断。
        self._actions["create"].triggered.connect(self._on_create)
        self._actions["view"].triggered.connect(self._on_view)
        self._actions["edit"].triggered.connect(self._on_edit)
        self._actions["delete"].triggered.connect(self._on_delete)
        self._actions["refresh"].triggered.connect(self._on_refresh)
        self._actions["quit"].triggered.connect(self.close)

    def _wire_table(self) -> None:
        self._table.itemSelectionChanged.connect(self._on_row_selected)
        self._calendar.day_picked.connect(self._on_day_picked)

    # --------------------------------------------------- MainViewPort 实现

    def show_rows(self, rows: Sequence[ScheduleRow]) -> None:
        """整体重绘列表。每行都带着 id 存在角色数据里，绝不按行号反查记录。"""
        self._table.blockSignals(True)
        try:
            self._table.setRowCount(0)
            if not rows:
                self._show_empty_hint()
                return
            for row in rows:
                index = self._table.rowCount()
                self._table.insertRow(index)
                for column, text in enumerate((row.time_text, row.title_text, row.notes_text)):
                    item = QTableWidgetItem(text)
                    item.setData(_ID_ROLE, row.schedule_id)
                    self._table.setItem(index, column, item)
            self._restore_selection(self._controller.selected_id)
        finally:
            self._table.blockSignals(False)

    def show_count(self, text: str) -> None:
        day = self._controller.current_day
        if day is not None:
            self._day_label.setText(f"{presenters.date_heading(day)}　{text}")
        else:
            self._day_label.setText(text)

    def show_selection(self, text: str) -> None:
        self._selection_label.setText(text)

    def show_status(self, text: str) -> None:
        self._status_label.setText(text)

    def show_info(self, message: str) -> None:
        """提醒而不是报错：未选中是界面状态问题，不该看起来像出了故障。"""
        QMessageBox.information(self, "提示", message)

    def show_error(self, headline: str, message: str) -> None:
        QMessageBox.warning(self, headline, message)

    def show_detail(self, row: ScheduleRow) -> None:
        """详情用列表已有的数据展示，不再查一次服务（controller 已经解释了为什么）。"""
        QMessageBox.information(
            self,
            "日程详情",
            f"时间：{row.time_text}\n标题：{row.title_text}\n备注：{row.notes_text or '（空）'}",
        )

    def ask_delete_confirm(self, row: ScheduleRow) -> bool:
        """删除确认。**调用它不等于已经删了**，只有返回 True 才会真的调 delete。"""
        answer = QMessageBox.question(
            self,
            "确认删除",
            f"确定要删除「{row.title_text}」（{row.time_text}）吗？\n删除之后无法撤销。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

    def open_schedule_form(self, request: FormRequest) -> ScheduleDraft | None:
        """打开表单，结果交给 controller；取消返回 None。"""
        return open_schedule_form(request, self)

    # ------------------------------------------------------------------ 内部

    def _on_create(self) -> None:
        self._controller.request_create()

    def _on_view(self) -> None:
        self._controller.request_view()

    def _on_edit(self) -> None:
        self._controller.request_edit()

    def _on_delete(self) -> None:
        self._controller.request_delete()

    def _on_refresh(self) -> None:
        """手动刷新列表；文案与"启动就绪"区分开，让人知道这次真的查过了。"""
        self._controller.refresh()
        self.show_status(presenters.refreshed_text(len(self._controller.rows)))

    def _on_row_selected(self) -> None:
        self._controller.select_row(self._selected_row_id())

    def _on_day_picked(self, day: dt.date) -> None:
        self._controller.select_day(day)

    def _selected_row_id(self) -> str | None:
        row = self._table.currentRow()
        if row < 0:
            return None
        item = self._table.item(row, 0)
        if item is None:
            return None
        value = item.data(_ID_ROLE)
        return None if value is None else str(value)

    def _show_empty_hint(self) -> None:
        """空状态不能是一片空白：一片空白会被当成程序坏了（第 4 节空状态）。"""
        self._table.insertRow(0)
        hint = QTableWidgetItem(_EMPTY_HINT)
        hint.setFlags(Qt.ItemFlag.NoItemFlags)
        hint.setForeground(Qt.GlobalColor.gray)
        self._table.setItem(0, 0, hint)
        self._table.setSpan(0, 0, 1, len(_COLUMN_HEADERS))

    def _restore_selection(self, schedule_id: str | None) -> None:
        """重绘之后把之前选中的那一行重新选上；找不到就维持未选中。"""
        if schedule_id is None:
            return
        for row in range(self._table.rowCount()):
            item = self._table.item(row, 0)
            if item is None:
                continue
            if str(item.data(_ID_ROLE)) == schedule_id:
                self._table.selectRow(row)
                return


__all__ = ["MainWindow"]
