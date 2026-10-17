"""日历区：把 `QCalendarWidget` 的默认行为改成项目要的样子。

Qt 的 `QCalendarWidget` 交叉平台可用性没问题，但两处默认值和我们要的不一样，
包这一层的目的就是把它们固定下来（第 3 节第四条约束）：

- **周起始必须是周一**。Qt 默认按周日起始，不改会让全组截图不一致。
- **回到今天**要有显式入口，不能让用户先认出控件底部那个箭头图标。

另外预留了「有日程的日期加标记」的能力（`mark_days`），但 P10 阶段**没有调用它**：
标记需要"这个月哪些日期有日程"的数据，那要求后端提供按月查询
（建议 `list_days_with_schedules(month)`），属于尚未确认的端口扩展。
与其让窗口绕开 controller 自己去遍历查询，不如先把能力备好、来源留白，
并在 `ui-interaction.md` 里记为待办。
"""

from __future__ import annotations

import datetime as dt

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtGui import QColor, QTextCharFormat
from PySide6.QtWidgets import (
    QCalendarWidget,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .ports import TodayProvider

_MARK_BACKGROUND = QColor("#E8F0FE")


def _to_qdate(day: dt.date) -> QDate:
    return QDate(day.year, day.month, day.day)


def _to_date(day: QDate) -> dt.date:
    value = day.toPython()
    assert isinstance(value, dt.date), "QDate.toPython() 应当给出 datetime.date"
    return value


class CalendarPanel(QWidget):
    """左侧日历区：一个月历 + 一行状态 + 一个「回到今天」按钮。

    `day_picked` 只在用户**点了某一天**时发出，翻月不会触发——
    翻月只是看日历，不该顺手把列表查一遍。

    `today` 是注入的“今天”：默认取系统日期，截图脚本可以把它固定成某一天，
    「回到今天」才不会跳回真实当天。
    """

    day_picked = Signal(object)

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        today: TodayProvider = dt.date.today,
    ) -> None:
        super().__init__(parent)
        self._today = today
        self._calendar = QCalendarWidget(self)
        self._calendar.setFirstDayOfWeek(Qt.DayOfWeek.Monday)
        self._calendar.setGridVisible(True)
        self._calendar.setVerticalHeaderFormat(
            QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader
        )

        self._today_button = QPushButton("回到今天", self)
        self._hint = QLabel("", self)
        self._hint.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        button_row = QHBoxLayout()
        button_row.addWidget(self._today_button)
        button_row.addStretch(1)
        button_row.addWidget(self._hint)

        layout = QVBoxLayout(self)
        layout.addWidget(self._calendar)
        layout.addLayout(button_row)

        self._calendar.clicked.connect(self._emit_clicked)
        self._today_button.clicked.connect(self.go_today)

    # ------------------------------------------------------------------ 对外

    def selected_day(self) -> dt.date:
        return _to_date(self._calendar.selectedDate())

    def set_selected_day(self, day: dt.date) -> None:
        """外部要求选中某天；不发出 `day_picked`，避免和刷新形成回环。"""
        self._calendar.setSelectedDate(_to_qdate(day))

    def set_hint(self, text: str) -> None:
        """日历底部那行小字，通常写当前选中哪一天。"""
        self._hint.setText(text)

    def go_today(self) -> None:
        today = _to_qdate(self._today())
        self._calendar.setSelectedDate(today)
        self.day_picked.emit(_to_date(today))

    def mark_days(self, days: frozenset[dt.date] | set[dt.date]) -> None:
        """给这些日期加上底色，其余恢复原样。

        P10 阶段没人调用（原因见模块 docstring），但方法本身是可用的：
        哪天拿到了按月查询的数据，一行就可以接上。
        """
        blank = QTextCharFormat()
        for old in self._calendar.dateTextFormat():
            self._calendar.setDateTextFormat(old, blank)

        marked = QTextCharFormat()
        marked.setBackground(_MARK_BACKGROUND)
        for day in days:
            self._calendar.setDateTextFormat(_to_qdate(day), marked)

    # ------------------------------------------------------------------ 内部

    def _emit_clicked(self, day: QDate) -> None:
        self.day_picked.emit(_to_date(day))


__all__ = ["CalendarPanel"]
