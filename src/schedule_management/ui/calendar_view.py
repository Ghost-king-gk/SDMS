"""日历区：把 `QCalendarWidget` 的默认行为改成项目要的样子。

Qt 的 `QCalendarWidget` 交叉平台可用性没问题，但几处默认值和我们要的不一样，
包这一层的目的就是把它们固定下来（第 3 节第四条约束）：

- **周起始必须是周一**。Qt 默认按周日起始，不改会让全组截图不一致。
- **回到今天**要有显式入口，不能让用户先认出控件底部那个箭头图标。
- **有日程的日期要有标记**。底色来自按月条数（`set_counts`），条数徽标由
  `_CountCalendar.paintCell` 自绘；数据由 controller 通过 `count_by_date`
  取得，本模块不查任何东西，也不 import controller。

「今天」是注入的：默认取系统日期，截图脚本可以把它固定成某一天，
「回到今天」与今天高亮才不会跳回真实当天。

今天的高亮与「有日程」的底色叠加时用浅琥珀色：琥珀色是**今天**的身份，
蓝色是**有日程**的身份，两者同时出现时必须都看得出来。
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping

from PySide6.QtCore import QDate, QLocale, QRect, Qt, Signal
from PySide6.QtGui import QColor, QContextMenuEvent, QFont, QPainter, QPen, QTextCharFormat
from PySide6.QtWidgets import (
    QCalendarWidget,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from . import presenters, theme
from .ports import TodayProvider

#: 底部提示的默认文案：把两种鼠标动作一次说清，省得用户去猜双击能不能用。
_DEFAULT_HINT = "单击筛选 · 双击新增"


def _to_qdate(day: dt.date) -> QDate:
    return QDate(day.year, day.month, day.day)


def _to_date(day: QDate) -> dt.date:
    value = day.toPython()
    assert isinstance(value, dt.date), "QDate.toPython() 应当给出 datetime.date"
    return value


class _CountCalendar(QCalendarWidget):
    """在日期格右上角画条数徽标的月历。

    徽标只表达「这一天有几条」这个事实，不参与命中判定：点格子的行为仍然由
    `QCalendarWidget` 自己决定，`CalendarPanel` 再转成信号。
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._counts: dict[dt.date, int] = {}
        self._today_marker: dt.date | None = None
        self._dark = False

    def set_counts(self, counts: Mapping[dt.date, int]) -> None:
        """记下这个月每个日期的条数并重绘；条数为 0 的日期按「没有」处理。"""
        self._counts = {day: total for day, total in counts.items() if total > 0}
        self.updateCells()

    def set_today(self, day: dt.date) -> None:
        """今天在格底画一道琥珀色短线：即使今天被选中（蓝底盖住文字色）也认得出。"""
        self._today_marker = day
        self.updateCells()

    def paintCell(self, painter: QPainter, rect: QRect, date: QDate) -> None:  # noqa: N802
        """先让 Qt 画完日期，再补今天的短线与右上角条数徽标。

        1-9 显示数字，两位数以上显示 `9+`：格子只有三十来像素，两位数挤进去
        会糊成一团，而「超过 9 条」在这个场景里已经不需要精确值。
        """
        super().paintCell(painter, rect, date)
        colors = theme.palette(self._dark)
        cell_date = _to_date(date)

        painter.save()
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            if self._today_marker is not None and cell_date == self._today_marker:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(colors.today_accent))
                painter.drawRect(
                    QRect(rect.left() + 6, rect.bottom() - 2, max(8, rect.width() - 12), 2)
                )

            total = self._counts.get(cell_date)
            if total is None:
                return

            side = min(16, max(12, min(rect.width(), rect.height()) - 12))
            badge = QRect(rect.right() - side - 2, rect.top() + 2, side, side)
            # 徽标自带一圈与文字同色的描边：今天被选中时格子也是蓝底，
            # 纯蓝圆点会整块“消失”，描边让它仍然看得出是个独立的徽标。
            painter.setPen(QPen(QColor(colors.badge_text), 1))
            painter.setBrush(QColor(colors.badge_background))
            painter.drawEllipse(badge)

            font = QFont(painter.font())
            font.setPixelSize(max(8, side - 6))
            font.setBold(True)
            painter.setFont(font)
            painter.setPen(QColor(colors.badge_text))
            painter.drawText(badge, Qt.AlignmentFlag.AlignCenter, "9+" if total > 9 else str(total))
        finally:
            painter.restore()

    def set_dark(self, dark: bool) -> None:
        self._dark = dark
        self.updateCells()


class CalendarPanel(QWidget):
    """左侧日历区：今天提示 + 一个月历 + 一行按钮与提示。

    `day_picked` 只在用户**点了某一天**时发出，翻月不会触发——
    翻月只是看日历，不该顺手把列表查一遍；翻月要看的是「新的一页哪些天有日程」，
    走 `month_changed`。

    `day_activated` 在用户**双击某一天**、或选中某天后按 Enter 时发出
    （Qt 的 `activated` 信号）。它不改变 `day_picked` 的语义：单击仍然只做筛选，
    只有明确“打开这一天”的动作才走激活路径。

    `month_changed(year, month)` 在用户翻到另一个月时发出，供窗口去取当月条数。
    """

    day_picked = Signal(object)
    day_activated = Signal(object)
    month_changed = Signal(int, int)

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        today: TodayProvider = dt.date.today,
    ) -> None:
        super().__init__(parent)
        self._today = today
        self._counts: dict[dt.date, int] = {}
        self._dark = False

        # 左卡片只放日历后仍有足够高度；360 是日期行不再被压扁的下限。
        self.setMinimumHeight(360)

        self._calendar = _CountCalendar(self)
        self._calendar.setFirstDayOfWeek(Qt.DayOfWeek.Monday)
        self._calendar.setGridVisible(False)
        # 中文界面里出现 “Mon/Tue” 与 “October” 很突兀；月份与星期都跟着中文走。
        self._calendar.setLocale(QLocale(QLocale.Language.Chinese, QLocale.Country.China))
        self._calendar.setVerticalHeaderFormat(
            QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader
        )
        # 默认会选中并翻到「真实今天」；注入的 today 才是这个界面认定的今天。
        self._calendar.setSelectedDate(_to_qdate(self._today()))
        self._calendar.set_today(self._today())

        self._today_label = QLabel(self)
        self._today_label.setObjectName("TodayLabel")
        self._today_label.setText(f"今天 · {presenters.date_heading(self._today())}")

        self._today_button = QPushButton("回到今天", self)
        self._today_button.setObjectName("TodayButton")

        self._hint = QLabel(_DEFAULT_HINT, self)
        self._hint.setObjectName("Hint")
        self._hint.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        button_row = QHBoxLayout()
        button_row.setSpacing(8)
        button_row.addWidget(self._today_button)
        button_row.addStretch(1)
        button_row.addWidget(self._hint)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self._today_label)
        layout.addWidget(self._calendar, 1)
        layout.addLayout(button_row)

        self._calendar.clicked.connect(self._emit_clicked)
        self._calendar.activated.connect(self._emit_activated)
        self._calendar.currentPageChanged.connect(self._emit_month_changed)
        self._today_button.clicked.connect(self.go_today)

    # ------------------------------------------------------------------ 对外

    def selected_day(self) -> dt.date:
        return _to_date(self._calendar.selectedDate())

    def set_selected_day(self, day: dt.date) -> None:
        """外部要求选中某天；不发出 `day_picked`，避免和刷新形成回环。"""
        self._calendar.setSelectedDate(_to_qdate(day))

    def set_hint(self, text: str) -> None:
        """日历底部那行小字；传空串时回到默认的「单击筛选 · 双击新增」。"""
        self._hint.setText(text or _DEFAULT_HINT)

    def go_today(self) -> None:
        today = _to_qdate(self._today())
        self._calendar.setSelectedDate(today)
        self.day_picked.emit(_to_date(today))

    def set_counts(self, counts: Mapping[dt.date, int]) -> None:
        """标出这个月有日程的日期与各自条数。

        底色只给有日程的日期；今天的格式每次都重新写一遍，因此**清空标记不会
        把今天的高亮一起清掉**。`counts` 里出现月外的日期也不会出事——
        `QCalendarWidget.setDateTextFormat` 对不可见日期只是存着不画。
        """
        self._counts = {day: total for day, total in counts.items() if total > 0}
        self._calendar.set_counts(self._counts)
        self._paint_formats()

    def set_dark(self, dark: bool) -> None:
        """跟随窗口主题重写日期格式的颜色（深色模式下浅蓝底会看不清）。"""
        self._dark = dark
        self._calendar.set_dark(dark)
        self._paint_formats()

    # ------------------------------------------------------------ 右键菜单

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:  # noqa: N802
        """日历空白处/日期格上右键：给「在这一天新增」与「回到今天」两个入口。

        右键不要求改变当前选中日（`QCalendarWidget` 自己会处理日期格的右键），
        因此菜单文案必须把**当前选中的日期**写出来，避免用户在别的日子上
        右键、却按菜单新增到另一个日期。
        """
        self._build_context_menu().exec(event.globalPos())
        event.accept()

    def _build_context_menu(self) -> QMenu:
        """菜单的构建单独拆出来，测试可以只检查菜单项而不进入模态循环。"""
        day = self.selected_day()
        menu = QMenu(self)
        add_action = menu.addAction(f"在这一天新增（{presenters.date_heading(day)}）")
        add_action.triggered.connect(lambda _checked=False: self.day_activated.emit(day))
        today_action = menu.addAction("回到今天")
        today_action.triggered.connect(self.go_today)
        return menu

    # ------------------------------------------------------------------ 内部

    def _paint_formats(self) -> None:
        """清空旧格式后重画：先有日程底色，再叠加今天的加粗与琥珀色。"""
        colors = theme.palette(self._dark)
        blank = QTextCharFormat()
        for old in self._calendar.dateTextFormat():
            self._calendar.setDateTextFormat(old, blank)

        if self._counts:
            event = QTextCharFormat()
            event.setBackground(QColor(colors.event_background))
            for day in self._counts:
                self._calendar.setDateTextFormat(_to_qdate(day), event)

        today = self._today()
        today_format = QTextCharFormat()
        today_format.setFontWeight(QFont.Weight.Bold)
        today_format.setForeground(QColor(colors.today_foreground))
        if today in self._counts:
            # 今天 + 有日程：琥珀底色盖掉蓝色底，但徽标仍然在，两个信息都在。
            today_format.setBackground(QColor(colors.today_background))
        self._calendar.setDateTextFormat(_to_qdate(today), today_format)

    def _emit_clicked(self, day: QDate) -> None:
        self.day_picked.emit(_to_date(day))

    def _emit_activated(self, day: QDate) -> None:
        """双击日期或选中后按 Enter：交给窗口去打开预填日期的表单。"""
        self.day_activated.emit(_to_date(day))

    def _emit_month_changed(self, year: int, month: int) -> None:
        self.month_changed.emit(year, month)


__all__ = ["CalendarPanel"]
