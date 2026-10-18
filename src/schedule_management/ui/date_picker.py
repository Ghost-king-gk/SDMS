"""日期选择浮层：给「选择」按钮用的小日历。

存在的原因写在第 5.1 节：日期字段是一个普通输入框（`QLineEdit`），旁边配一个
「选择」按钮，**两种入口地位对等**。日历只是省事的输入方式，它回填之后
用户仍然可以继续手改那段文本——所以这里回填的是**文本**，不是某个控件内部状态。

刻意不用 `QDateEdit` 做主日期框：那个控件会先按自己的显示格式拦一道，
把用户手写的 `2026/10/15` 判为非法，等于把"合不合法"的判定权收回了界面。
浮层里用 `QCalendarWidget` 则没有这个问题：点出来的结果只会是确定的某一天。
"""

from __future__ import annotations

import datetime as dt

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtWidgets import (
    QCalendarWidget,
    QDialog,
    QHBoxLayout,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


def _to_qdate(day: dt.date) -> QDate:
    return QDate(day.year, day.month, day.day)


class DatePickerPopup(QDialog):
    """一个贴着按钮弹出来的日历；点选即关闭，Esc 或失焦表示取消。

    用 `Popup` 窗口标志：点击其它地方会自动关闭，符合浮层的手感，
    也不会在任务栏上留下一个多余的窗口。
    """

    date_selected = Signal(object)

    def __init__(self, initial: dt.date | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent, Qt.WindowType.Popup)
        self._calendar = QCalendarWidget(self)
        self._calendar.setFirstDayOfWeek(Qt.DayOfWeek.Monday)
        self._calendar.setGridVisible(True)
        self._calendar.setVerticalHeaderFormat(
            QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader
        )
        if initial is not None:
            self._calendar.setSelectedDate(_to_qdate(initial))

        self._today_button = QPushButton("今天", self)
        buttons = QHBoxLayout()
        buttons.addWidget(self._today_button)
        buttons.addStretch(1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.addWidget(self._calendar)
        layout.addLayout(buttons)

        self._calendar.clicked.connect(self._accept_day)
        self._today_button.clicked.connect(self._pick_today)

    # ------------------------------------------------------------------ 对外

    def pick(self) -> dt.date | None:
        """弹出来让用户点；点了就返回那天的 `date`，取消返回 None。"""
        result = self.exec()
        if result != QDialog.DialogCode.Accepted:
            return None
        day = self._calendar.selectedDate().toPython()
        assert isinstance(day, dt.date), "QDate.toPython() 应当给出 datetime.date"
        return day

    # ------------------------------------------------------------------ 内部

    def _accept_day(self, day: QDate) -> None:
        self.date_selected.emit(day.toPython())
        self.accept()

    def _pick_today(self) -> None:
        self._accept_day(QDate.currentDate())


def pick_date(initial: dt.date | None = None, parent: QWidget | None = None) -> dt.date | None:
    """弹出日期浮层并返回结果；取消返回 None。`None` 什么都不会写回输入框。"""
    return DatePickerPopup(initial=initial, parent=parent).pick()


__all__ = ["DatePickerPopup", "pick_date"]
