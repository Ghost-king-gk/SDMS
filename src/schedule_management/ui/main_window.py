"""主窗口：`MainViewPort` 的 Qt 实现，整个界面唯一的 Qt 装订点。

这一模块的自我要求只有一条：**它只做适配，不做决定**。

- 六个按钮点了之后该调什么组织组合式调用，一概不问，转手交给 `controller`；
- 列表怎么排序、选中未选中算什么、报错该说什么话，也一概不问——
  那都是 `presenters` 与后端给的结论；
- 它负责的就是“这些数据在 Qt 上怎么摆出来、用户动了哪个控件”。

布局按第 3 节的卡片式：顶部工具栏（品牌 + 六按钮 + 主题开关）、
中间左右两张 `QFrame#Card`（左日历、右列表）、底部状态栏。
深浅色主题只在这里与 `calendar_view` 套用，颜色本身集中在 `theme.py`。
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence
from typing import Final

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QAction, QColor, QPalette
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QFrame,
    QHBoxLayout,
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

from . import presenters, theme
from .calendar_view import CalendarPanel
from .controller import ScheduleController
from .ports import ScheduleServicePort, TodayProvider
from .schedule_form import open_schedule_form
from .view_models import FormRequest, ScheduleDraft, ScheduleRow

_COLUMN_HEADERS: Final = ("时间", "标题", "备注")
_ID_ROLE: Final = Qt.ItemDataRole.UserRole
_EMPTY_HINT: Final = "这一天还没有日程。双击日历日期，或点「新增」记一条。"
_WINDOW_TITLE: Final = "日程管理系统"
_BRAND: Final = "日程管理"
_DARK_SETTING: Final = "ui/dark"

_ROW_HEIGHT: Final = 36
_HEADER_HEIGHT: Final = 38
_CARD_MARGIN: Final = 16
_OUTER_MARGIN: Final = 18

_BUTTONS: Final = (
    ("create", "新增", "新增一条日程"),
    ("view", "查看", "查看选中日程的详情"),
    ("edit", "修改", "修改选中的日程"),
    ("delete", "删除", "删除选中的日程"),
    ("refresh", "刷新", "重新载入当前日期的日程"),
    ("quit", "退出", "退出程序"),
)

_TITLE_COLUMN_WIDTH: Final = 240


def _application_palette(colors: theme.Palette) -> QPalette:
    """按主题给应用调色板。

    QSS 覆盖的是控件，不是所有**自绘**细节：`QCalendarWidget` 的星期条
    由 Qt 内部按调色板绘制，只改 QSS 会在深色模式下留一条白带。把
    Base / AlternateBase / ButtonText 一并设好，这类区域才会跟着主题走。
    """
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(colors.background))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(colors.text))
    palette.setColor(QPalette.ColorRole.Base, QColor(colors.surface))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(colors.surface_alt))
    palette.setColor(QPalette.ColorRole.Text, QColor(colors.text))
    palette.setColor(QPalette.ColorRole.Button, QColor(colors.surface))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(colors.text))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(colors.primary))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(colors.on_primary))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(colors.surface))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(colors.text))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(colors.muted))
    palette.setColor(QPalette.ColorRole.Link, QColor(colors.primary))
    for role in (
        QPalette.ColorRole.Light,
        QPalette.ColorRole.Midlight,
        QPalette.ColorRole.Mid,
        QPalette.ColorRole.Dark,
        QPalette.ColorRole.Shadow,
    ):
        palette.setColor(role, QColor(colors.border))
    for role in (
        QPalette.ColorRole.WindowText,
        QPalette.ColorRole.Text,
        QPalette.ColorRole.ButtonText,
    ):
        palette.setColor(QPalette.ColorGroup.Disabled, role, QColor(colors.muted))
    return palette


class MainWindow(QMainWindow):
    """主界面：实现 `MainViewPort`，把 Qt 控件的所有输入输出翻译成端口调用。"""

    def __init__(
        self,
        service: ScheduleServicePort,
        clock: TodayProvider = dt.date.today,
    ) -> None:
        super().__init__()
        self.setWindowTitle(_WINDOW_TITLE)
        self.resize(1040, 680)
        self.setMinimumSize(900, 600)

        # 主题存在 QSettings 里：重启后保持上次的选择（第 6 节 V-21）。
        # 读取放在建控件之前，第一次 polish 就已经是目标主题，不会闪一下白底。
        self._settings = QSettings("SDMS", "SDMS")
        self._dark: bool = bool(self._settings.value(_DARK_SETTING, False, type=bool))
        self._apply_theme()

        self._calendar = CalendarPanel(today=clock)
        self._calendar.set_dark(self._dark)
        self._calendar.setMinimumWidth(320)

        self._count_text = ""
        self._day_label = QLabel("", self)
        self._day_label.setObjectName("DayHeading")
        self._table = QTableWidget(0, len(_COLUMN_HEADERS), self)
        self._status_label = QLabel("就绪", self)
        self._selection_label = QLabel(presenters.selection_text(None), self)

        self._build_layout()
        self._build_toolbar()
        self._connect_signals()

        # controller 放在 UI 建完之后创建：它需要把自己登记为 view，
        # 而写法的 `__init__` 走完后 `self` 才算可用。
        self._controller: ScheduleController = ScheduleController(
            service=service, view=self, clock=clock
        )

        self._controller.start()

    # ------------------------------------------------------------ 构建 UI

    def _build_layout(self) -> None:
        self._configure_table()

        calendar_card = QFrame(self)
        calendar_card.setObjectName("Card")
        calendar_layout = QVBoxLayout(calendar_card)
        calendar_layout.setContentsMargins(_CARD_MARGIN, _CARD_MARGIN, _CARD_MARGIN, _CARD_MARGIN)
        calendar_layout.addWidget(self._calendar)

        right_card = QFrame(self)
        right_card.setObjectName("Card")
        right_layout = QVBoxLayout(right_card)
        right_layout.setContentsMargins(_CARD_MARGIN, _CARD_MARGIN, _CARD_MARGIN, _CARD_MARGIN)
        right_layout.setSpacing(10)
        right_layout.addWidget(self._day_label)
        right_layout.addWidget(self._table, 1)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(calendar_card)
        splitter.addWidget(right_card)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([340, 660])

        outer = QWidget(self)
        outer_layout = QHBoxLayout(outer)
        outer_layout.setContentsMargins(_OUTER_MARGIN, _OUTER_MARGIN, _OUTER_MARGIN, _OUTER_MARGIN)
        outer_layout.setSpacing(16)
        outer_layout.addWidget(splitter)
        self.setCentralWidget(outer)

        status = QStatusBar(self)
        status.addWidget(self._status_label, 1)
        status.addPermanentWidget(self._selection_label)
        self.setStatusBar(status)
        status.setSizeGripEnabled(False)

    def _configure_table(self) -> None:
        """表格的呈现细节：无网格、隔行底色、固定行高、三列各自的伸缩方式。"""
        self._table.setHorizontalHeaderLabels(list(_COLUMN_HEADERS))
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setShowGrid(False)
        self._table.setAlternatingRowColors(True)
        self._table.setWordWrap(False)
        self._table.verticalHeader().setVisible(False)
        self._table.verticalHeader().setDefaultSectionSize(_ROW_HEIGHT)

        header = self._table.horizontalHeader()
        header.setFixedHeight(_HEADER_HEIGHT)
        header.setStretchLastSection(False)
        # 日期列下一分支再加；现在只有 时间 / 标题 / 备注 三列。
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._table.setColumnWidth(1, _TITLE_COLUMN_WIDTH)

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("主操作", self)
        toolbar.setMovable(False)
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)

        brand = QLabel(_BRAND, self)
        brand.setObjectName("Brand")
        brand.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        toolbar.addWidget(brand)
        toolbar.addSeparator()

        self._actions: dict[str, QAction] = {}
        for key, text, tip in _BUTTONS:
            action = QAction(text, self)
            action.setToolTip(tip)
            toolbar.addAction(action)
            self._actions[key] = action

        toolbar.addSeparator()
        self._dark_action = QAction("深色模式", self)
        self._dark_action.setCheckable(True)
        self._dark_action.setChecked(self._dark)
        toolbar.addAction(self._dark_action)
        self._sync_dark_action()

        # 接转发方法而不是直接接 controller：这里按下就算一次用户操作，
        # 具体该怎么办由 controller 说了算，窗口本身不做判断。
        self._actions["create"].triggered.connect(self._on_create)
        self._actions["view"].triggered.connect(self._on_view)
        self._actions["edit"].triggered.connect(self._on_edit)
        self._actions["delete"].triggered.connect(self._on_delete)
        self._actions["refresh"].triggered.connect(self._on_refresh)
        self._actions["quit"].triggered.connect(self.close)
        self._dark_action.toggled.connect(self._on_dark_toggled)

    def _connect_signals(self) -> None:
        self._table.itemSelectionChanged.connect(self._on_row_selected)
        self._calendar.day_picked.connect(self._on_day_picked)
        self._calendar.day_activated.connect(self._on_day_activated)
        self._calendar.month_changed.connect(self._on_month_changed)

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
        """日期标题与条数：标题用大字号，条数退成弱化的正文，避免一行全是重音。"""
        self._count_text = text
        day = self._controller.current_day
        if day is None:
            self._day_label.setText(text)
            return
        muted = theme.palette(self._dark).muted
        self._day_label.setText(
            f"{presenters.date_heading(day)}"
            f'<span style="font-size: 13px; font-weight: normal; color: {muted};">'
            f"　{text}</span>"
        )

    def show_selection(self, text: str) -> None:
        self._selection_label.setText(text)

    def show_status(self, text: str) -> None:
        self._status_label.setText(text)

    def show_month_counts(self, counts: dict[dt.date, int]) -> None:
        """把这个月「哪天有几条」交给日历去标记。"""
        self._calendar.set_counts(counts)

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

    def _apply_theme(self) -> None:
        """把当前主题的 QSS 与调色板套到整个应用；窗口、表单、消息框一起生效。"""
        app = QApplication.instance()
        if isinstance(app, QApplication):
            app.setPalette(_application_palette(theme.palette(self._dark)))
            app.setStyleSheet(theme.stylesheet(self._dark))

    def _sync_dark_action(self) -> None:
        """勾选态表示“现在是不是深色”，文字说“点下去会变成什么”。"""
        if self._dark:
            self._dark_action.setText("浅色模式")
            self._dark_action.setToolTip("切换到浅色模式")
        else:
            self._dark_action.setText("深色模式")
            self._dark_action.setToolTip("切换到深色模式")

    def _on_dark_toggled(self, dark: bool) -> None:
        self._dark = dark
        self._sync_dark_action()
        self._apply_theme()
        self._calendar.set_dark(dark)
        if self._count_text:
            self.show_count(self._count_text)
        self._settings.setValue(_DARK_SETTING, dark)

    def _on_create(self) -> None:
        self._controller.request_create()

    def _on_view(self) -> None:
        self._controller.request_view()

    def _on_edit(self) -> None:
        self._controller.request_edit()

    def _on_delete(self) -> None:
        self._controller.request_delete()

    def _on_refresh(self) -> None:
        """手动刷新列表；只有查询成功才宣称“已刷新”，失败时保留错误框与旧列表。"""
        if self._controller.refresh():
            self.show_status(presenters.refreshed_text(len(self._controller.rows)))

    def _on_row_selected(self) -> None:
        self._controller.select_row(self._selected_row_id())

    def _on_day_picked(self, day: dt.date) -> None:
        self._controller.select_day(day)

    def _on_day_activated(self, day: dt.date) -> None:
        """双击日历（或选中后按 Enter）：先切到该日期，再打开预填日期的表单。"""
        if self._controller.current_day != day:
            self._controller.select_day(day)
        self._controller.request_create_for_day(day)

    def _on_month_changed(self, year: int, month: int) -> None:
        """翻月只更新日历标记，不重查列表：换个视角看不该动筛选条件。

        失败不弹框（`load_month_counts` 只记日志）：存储故障不该拦住翻日历。
        """
        self._controller.load_month_counts(year, month)

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
