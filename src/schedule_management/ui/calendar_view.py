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

from PySide6.QtCore import QDate, QEvent, QLocale, QPoint, QRect, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QContextMenuEvent,
    QDragEnterEvent,
    QDragLeaveEvent,
    QDragMoveEvent,
    QDropEvent,
    QFont,
    QPainter,
    QPen,
    QTextCharFormat,
    QWheelEvent,
)
from PySide6.QtWidgets import (
    QCalendarWidget,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QTableView,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from . import presenters, theme
from .ports import TodayProvider
from .view_models import SCHEDULE_DRAG_MIME

#: 底部提示的默认文案：把三种动作一次说清，省得用户去猜双击能不能用、滚轮能不能翻月。
_DEFAULT_HINT = "单击筛选 · 双击新增 · Ctrl+滚轮翻月"
#: 日历的最大高度：窗口拉到 1440x900 时，月历不该被拉成一张大网——
#: 每个日期格多出来的高度只是空，并不会让"哪天有日程"更好读。
_PANEL_MAX_HEIGHT = 460


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
        self._drop_hint: dt.date | None = None
        self._dark = False

    def set_counts(self, counts: Mapping[dt.date, int]) -> None:
        """记下这个月每个日期的条数并重绘；条数为 0 的日期按「没有」处理。"""
        self._counts = {day: total for day, total in counts.items() if total > 0}
        self.updateCells()

    def set_drop_hint(self, day: dt.date | None) -> None:
        """拖拽时给落点那一格描个框；传 None 清掉。"""
        if self._drop_hint == day:
            return
        self._drop_hint = day
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

        if self._drop_hint is not None and cell_date == self._drop_hint:
            painter.save()
            try:
                painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
                painter.setPen(QPen(QColor(colors.primary), 2))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRect(rect.adjusted(1, 1, -1, -1))
            finally:
                painter.restore()

    def set_dark(self, dark: bool) -> None:
        self._dark = dark
        self.updateCells()

    def date_at(self, pos: QPoint) -> dt.date | None:
        """把本控件的坐标换成日期格上的日期；不在有效日期格上时返回 None。

        `QCalendarWidget` 没有公开「坐标 → 日期」的接口，只能向内部
        `QTableView` 要 index，再按「当月 1 日、周一开头」的排布反推。
        右键菜单用它来确定用户实际点的是哪一天，而不是沿用旧的选中日。
        """
        view = self.findChild(QTableView)
        if view is None:
            return None
        index = view.indexAt(view.viewport().mapFrom(self, pos))
        if not index.isValid():
            return None
        first = dt.date(self.yearShown(), self.monthShown(), 1)
        day = first + dt.timedelta(days=index.row() * 7 + index.column() - first.weekday())
        # 月历只显示当月；首尾空格即使有 index 也不能当成相邻月份的一天。
        if (day.year, day.month) != (first.year, first.month):
            return None
        return day


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
    #: 有日程被拖到某一天：`(schedule_id, date)`。窗口把它交给 controller 去改日期。
    schedule_dropped = Signal(str, object)

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
        # 「当前选中的日期」只认一个真值：外部把日历挪到某天时置 True，
        # 屏蔽掉随之而来的 selectionChanged，避免"程序改选中 → 又当成用户点了"的回环。
        self._syncing = False
        self._last_notified: dt.date | None = None

        # 左卡片只放日历后仍有足够高度；360 是日期行不再被压扁的下限。
        self.setMinimumHeight(360)
        # 上限解决"窗口拉高、日历跟着被拉成一张大网"：多出来的高度应该给列表。
        self.setMaximumHeight(_PANEL_MAX_HEIGHT)

        self._calendar = _CountCalendar(self)
        self._calendar.setFirstDayOfWeek(Qt.DayOfWeek.Monday)
        self._calendar.setGridVisible(False)
        # 中文界面里出现 “Mon/Tue” 与 “October” 很突兀；月份与星期都跟着中文走。
        self._calendar.setLocale(QLocale(QLocale.Language.Chinese, QLocale.Country.China))
        # 内置星期条把周末染成红色，与 Apple 的克制配色冲突；换成自绘的一行小字，
        # 颜色跟着主题走，也避免深色模式下那排红字格外刺眼。
        self._calendar.setHorizontalHeaderFormat(
            QCalendarWidget.HorizontalHeaderFormat.NoHorizontalHeader
        )
        self._calendar.setVerticalHeaderFormat(
            QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader
        )
        # 默认会选中并翻到「真实今天」；注入的 today 才是这个界面认定的今天。
        self._calendar.setSelectedDate(_to_qdate(self._today()))
        self._calendar.set_today(self._today())
        # 内置导航条把月份、年份与两个箭头拆成三件互不对齐的控件；换成自绘的一行，
        # 顺序才是「月份导航 → 星期条 → 日期格」。
        self._calendar.setNavigationBarVisible(False)

        self._month_label = QLabel(self)
        self._month_label.setObjectName("CalendarMonth")
        self._month_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._prev_button = QToolButton(self)
        self._prev_button.setObjectName("CalendarNav")
        self._prev_button.setText("\u2039")
        self._prev_button.setToolTip("上一个月")
        self._prev_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._next_button = QToolButton(self)
        self._next_button.setObjectName("CalendarNav")
        self._next_button.setText("\u203a")
        self._next_button.setToolTip("下一个月")
        self._next_button.setCursor(Qt.CursorShape.PointingHandCursor)
        for button in (self._prev_button, self._next_button):
            button.setFixedSize(28, 28)
        nav_row = QHBoxLayout()
        nav_row.setContentsMargins(0, 0, 0, 0)
        nav_row.setSpacing(4)
        nav_row.addWidget(self._prev_button)
        nav_row.addStretch(1)
        nav_row.addWidget(self._month_label)
        nav_row.addStretch(1)
        nav_row.addWidget(self._next_button)

        self._weekday_bar = QWidget(self)
        self._weekday_bar.setFixedHeight(22)
        weekday_layout = QHBoxLayout(self._weekday_bar)
        weekday_layout.setContentsMargins(0, 0, 0, 0)
        weekday_layout.setSpacing(0)
        for name in ("周一", "周二", "周三", "周四", "周五", "周六", "周日"):
            weekday = QLabel(name, self._weekday_bar)
            weekday.setObjectName("Weekday")
            weekday.setAlignment(Qt.AlignmentFlag.AlignCenter)
            weekday_layout.addWidget(weekday, 1)

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
        layout.addLayout(nav_row)
        layout.addWidget(self._weekday_bar)
        layout.addWidget(self._calendar, 1)
        layout.addLayout(button_row)

        # 接住从右侧列表拖过来的日程：拖一下就能改日期，不用开表单。
        self.setAcceptDrops(True)
        self._calendar.clicked.connect(self._emit_clicked)
        self._calendar.selectionChanged.connect(self._emit_selection_changed)
        self._calendar.activated.connect(self._emit_activated)
        self._calendar.currentPageChanged.connect(self._emit_month_changed)
        self._calendar.currentPageChanged.connect(self._sync_month_label)
        self._prev_button.clicked.connect(lambda _checked=False: self._step_month(-1))
        self._next_button.clicked.connect(lambda _checked=False: self._step_month(1))
        self._today_button.clicked.connect(self.go_today)
        # Ctrl+滚轮翻月：滚轮单独用很容易和"滚页面"抢事件，加修饰键才不误触。
        self._calendar.installEventFilter(self)
        self._sync_month_label()

    # ------------------------------------------------------------------ 事件

    def eventFilter(self, watched: object, event: QEvent) -> bool:  # noqa: N802
        """Ctrl+滚轮翻月。

        要求按 Ctrl 才翻，是因为日历正处在整页布局里：普通滚轮应当是"滚页面"的，
        劫持它会让用户在看列表时手一滑就换了月份。翻月走
        `showPreviousMonth/showNextMonth`，`currentPageChanged` 会照常带动
        条数刷新，不需要在这里额外发信号。
        """
        if (
            watched is self._calendar
            and event.type() == QEvent.Type.Wheel
            and isinstance(event, QWheelEvent)
            and bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
        ):
            delta = event.angleDelta().y()
            if delta:
                self._step_month(-1 if delta > 0 else 1)
            return True
        return super().eventFilter(watched, event)  # type: ignore[arg-type]

    def _step_month(self, step: int) -> None:
        """往前/往后一个月。"""
        if step < 0:
            self._calendar.showPreviousMonth()
        else:
            self._calendar.showNextMonth()

    def _sync_month_label(self, *_args: object) -> None:
        """自绘导航条中间的「2026 年 10 月」跟着当前页走。"""
        self._month_label.setText(
            f"{self._calendar.yearShown()} 年 {self._calendar.monthShown()} 月"
        )

    # ------------------------------------------------------------------ 对外

    def selected_day(self) -> dt.date:
        return _to_date(self._calendar.selectedDate())

    def set_selected_day(self, day: dt.date) -> None:
        """外部要求选中某天；不发出 `day_picked`，避免和刷新形成回环。

        这是「当前日期只有一个真值」的落点：点摘要条目、搜索结果跳转等入口
        改的是 controller 的日期，日历在这里被要求跟上，而不是反过来通知一遍。
        """
        self._syncing = True
        try:
            self._calendar.setSelectedDate(_to_qdate(day))
        finally:
            self._syncing = False
        self._last_notified = day

    def set_hint(self, text: str) -> None:
        """日历底部那行小字；传空串时回到默认的「单击筛选 · 双击新增」。"""
        self._hint.setText(text or _DEFAULT_HINT)

    def go_today(self) -> None:
        today = _to_qdate(self._today())
        self._syncing = True
        try:
            self._calendar.setSelectedDate(today)
        finally:
            self._syncing = False
        self._last_notified = _to_date(today)
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

    # -------------------------------------------------------------- 拖放改期

    def _day_at(self, pos: QPoint) -> dt.date | None:
        """本面板坐标 → 日历格上的日期；落在非日期区（表头、按钮行）返回 None。"""
        return self._calendar.date_at(self._calendar.mapFrom(self, pos))

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802
        """只接受"我们自己的行"：别把随便一段文字或文件拖进来当成改期。"""
        if event.mimeData().hasFormat(SCHEDULE_DRAG_MIME):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:  # noqa: N802
        """落点跟着鼠标走：有效的日期格描框并接受，其他地方一律拒绝。"""
        day = self._day_at(event.position().toPoint())
        if day is None:
            self._calendar.set_drop_hint(None)
            event.ignore()
            return
        self._calendar.set_drop_hint(day)
        event.setDropAction(Qt.DropAction.MoveAction)
        event.accept()

    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:  # noqa: N802
        self._calendar.set_drop_hint(None)
        event.accept()

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802
        """松手才提交：落点日期与 id 一起发给窗口，由 controller 决定怎么写。"""
        day = self._day_at(event.position().toPoint())
        self._calendar.set_drop_hint(None)
        if day is None:
            event.ignore()
            return
        raw = event.mimeData().data(SCHEDULE_DRAG_MIME).data()
        schedule_id = bytes(raw).decode("utf-8").strip()
        if not schedule_id:
            event.ignore()
            return
        event.setDropAction(Qt.DropAction.MoveAction)
        event.accept()
        self.schedule_dropped.emit(schedule_id, day)

    # ------------------------------------------------------------ 右键菜单

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:  # noqa: N802
        """日历上右键：给「在这一天新增」与「回到今天」两个入口。

        日期取右键落点所在的日期格，而不是当前选中日：右键 26 号，菜单动作
        就作用于 26 号。只有落点不在日期格上时才退回当前选中日。
        """
        day = self._calendar.date_at(self._calendar.mapFrom(self, event.pos()))
        self._build_context_menu(day if day is not None else self.selected_day()).exec(
            event.globalPos()
        )
        event.accept()

    def _build_context_menu(self, day: dt.date) -> QMenu:
        """菜单的构建单独拆出来，测试可以只检查菜单项而不进入模态循环。"""
        menu = QMenu(self)
        add_action = menu.addAction(f"在这一天新增（{presenters.date_heading(day)}）")
        add_action.triggered.connect(lambda _checked=False: self.day_activated.emit(day))
        today_action = menu.addAction("回到今天")
        today_action.triggered.connect(self.go_today)
        return menu

    # ------------------------------------------------------------------ 内部

    def _paint_formats(self) -> None:
        """清空旧格式后重画：周末去红、有日程铺底色、今天最后叠加。

        Qt 默认把周末染成红色；那是日历控件的默认值，不是我们的视觉口径。
        这里把当月每个周六/周日的前景色改成弱化灰，再把"有日程"的底色合并进
        同一个 `QTextCharFormat`——`setDateTextFormat` 是整份替换而不是叠加，
        分两次调用会把周末的灰色覆盖回默认红。
        """
        colors = theme.palette(self._dark)
        blank = QTextCharFormat()
        for old in self._calendar.dateTextFormat():
            self._calendar.setDateTextFormat(old, blank)

        formats: dict[dt.date, QTextCharFormat] = {}
        day = dt.date(self._calendar.yearShown(), self._calendar.monthShown(), 1)
        while day.month == self._calendar.monthShown():
            if day.weekday() >= 5:
                weekend = QTextCharFormat()
                weekend.setForeground(QColor(colors.muted))
                formats[day] = weekend
            day += dt.timedelta(days=1)

        event = QColor(colors.event_background)
        for day in self._counts:
            fmt = formats.get(day, QTextCharFormat())
            fmt.setBackground(event)
            formats[day] = fmt

        for day, fmt in formats.items():
            self._calendar.setDateTextFormat(_to_qdate(day), fmt)

        today = self._today()
        today_format = QTextCharFormat()
        today_format.setFontWeight(QFont.Weight.Bold)
        today_format.setForeground(QColor(colors.today_foreground))
        if today in self._counts:
            # 今天 + 有日程：琥珀底色盖掉蓝色底，但徽标仍然在，两个信息都在。
            today_format.setBackground(QColor(colors.today_background))
        self._calendar.setDateTextFormat(_to_qdate(today), today_format)

    def _emit_clicked(self, day: QDate) -> None:
        self._emit_day(_to_date(day))

    def _emit_selection_changed(self) -> None:
        """选中日期变了就通知一次——**键盘换天也算**。

        `QCalendarWidget` 的方向键只改 `selectedDate`，既不发 `clicked` 也不发
        `activated`；只听 `clicked` 会让"方向键把选中挪到 21 号、右侧还是 20 号"。
        鼠标点击同样会走到这里，因此用 `_last_notified` 去重，保证一天只发一次。
        """
        if self._syncing:
            return
        self._emit_day(self.selected_day())

    def _emit_day(self, day: dt.date) -> None:
        if day == self._last_notified:
            return
        self._last_notified = day
        self.day_picked.emit(day)

    def _emit_activated(self, day: QDate) -> None:
        """双击日期或选中后按 Enter：交给窗口去打开预填日期的表单。"""
        self.day_activated.emit(_to_date(day))

    def _emit_month_changed(self, year: int, month: int) -> None:
        self.month_changed.emit(year, month)


__all__ = ["CalendarPanel"]
