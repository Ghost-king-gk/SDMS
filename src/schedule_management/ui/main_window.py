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

import contextlib
import datetime as dt
import math
from collections.abc import Callable, Sequence
from functools import cmp_to_key
from html import escape
from typing import Final

from PySide6.QtCore import (
    QByteArray,
    QCollator,
    QEvent,
    QLocale,
    QMimeData,
    QModelIndex,
    QPersistentModelIndex,
    QPoint,
    QPointF,
    QSettings,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import (
    QAction,
    QCloseEvent,
    QColor,
    QCursor,
    QFont,
    QIcon,
    QKeySequence,
    QMouseEvent,
    QPainter,
    QPalette,
    QPen,
    QPixmap,
    QResizeEvent,
    QShortcut,
    QShowEvent,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableWidget,
    QTableWidgetItem,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from . import presenters, theme
from .calendar_view import CalendarPanel
from .controller import ScheduleController
from .ports import ScheduleServicePort, TodayProvider
from .schedule_form import ScheduleForm
from .view_models import SCHEDULE_DRAG_MIME, FormRequest, ScheduleDraft, ScheduleRow

_COLUMN_HEADERS: Final = ("日期", "时间", "标题", "备注")
_ID_ROLE: Final = Qt.ItemDataRole.UserRole
_UPCOMING_DAY_ROLE: Final = int(Qt.ItemDataRole.UserRole) + 1
_EMPTY_DAY_TITLE: Final = "这一天还没有日程"
_EMPTY_DAY_HINT: Final = "双击日历上的日期，或点下面的按钮记一条。"
_EMPTY_ACTION: Final = "新增这一天"
#: 「一条都没有」与「这一天没有」是两种空：前者要解释数据存在哪、打消"是不是坏了"的疑虑，
#: 后者只需要给下一步。同一句话会让首次打开的人以为程序把日期切到了空的一天。
_FIRST_RUN_TITLE: Final = "还没有任何日程"
_FIRST_RUN_HINT: Final = "日程存在本机，关掉再打开也还在。先记一条试试。"
_FIRST_RUN_ACTION: Final = "记第一条"
_WINDOW_TITLE: Final = "日程管理系统"
_BRAND: Final = "日程管理"
_DARK_SETTING: Final = "ui/dark"
_GEOMETRY_SETTING: Final = "ui/geometry"
_SPLITTER_SETTING: Final = "ui/splitter"
_COLUMNS_SETTING: Final = "ui/columns"
_SORT_SETTING: Final = "ui/sort"
_SECTION_UPCOMING: Final = "接下来 7 天"
_SEARCH_PLACEHOLDER: Final = "搜索标题或备注…"

#: 行高 40 而不是 36：去掉行间分割线之后，行与行的分组只能靠留白，
#: 36px 会让四列内容看起来挤成一整块。
_ROW_HEIGHT: Final = 40
_HEADER_HEIGHT: Final = 34
_CARD_MARGIN: Final = 16
_OUTER_MARGIN: Final = 18
_SEARCH_DEBOUNCE_MS: Final = 250
_SEARCH_INPUT_WIDTH: Final = 220
#: 摘要区不再写死高度：给它一个下限，剩下的交给拉伸因子，窗口变高它跟着变高。
#: 恒定 170px 在 1440x900 下会显得局促，窗口缩小时又会把表格压得太矮。
_UPCOMING_MIN_HEIGHT: Final = 96
#: 撤销窗口：删除之后 5 秒内可以反悔。超过之后还留着入口，等于把"最近一次删除"
#: 永久挂在状态栏上，用户会以为随时能撤、结果撤回来一条早就放下的记录。
_UNDO_WINDOW_MS: Final = 5000

_BUTTONS: Final = (
    ("create", "新增", "新增一条日程（Ctrl+N）"),
    ("view", "查看", "查看选中日程的详情（Enter）"),
    ("edit", "修改", "修改选中的日程"),
    ("delete", "删除", "删除选中的日程（Delete）"),
    ("duplicate", "复制", "复制选中的日程（Ctrl+D）"),
    ("refresh", "刷新", "重新载入当前日期的日程（F5）"),
    ("quit", "退出", "退出程序"),
)

#: 窗口级快捷键。表格内的 Delete / Enter 另有 WidgetWithChildrenShortcut，
#: 只在表格获得焦点时生效，不会在搜索框或表单里误触。
_ACTION_SHORTCUTS: Final = {
    "create": "Ctrl+N",
    "duplicate": "Ctrl+D",
    "refresh": "F5",
}

#: 列宽跟着字体走：日期与时间都有确定的内容宽度，给够就行，剩下的都留给标题与备注。
_TITLE_COLUMN_WIDTH: Final = 200
_DATE_COLUMN_WIDTH: Final = 104
_TIME_COLUMN_WIDTH: Final = 72
#: 备注列的默认宽度与下限。它以前是 `Stretch`：能吃满剩余宽度，但**双击分隔线
#: 自适应内容会失效**（Qt 只对 Interactive 段响应），而且窗口一窄就被压到三十几像素。
_NOTES_COLUMN_WIDTH: Final = 240
_NOTES_COLUMN_MIN_WIDTH: Final = 120
#: 表格的最小宽度：日历最低 320 + 这段宽度，窗口缩到 900 时备注列仍有一百多像素。
#: 不设这条下限，Stretch 的备注列会被压到三十几像素，表头连「备注」两个字都放不下。
_TABLE_MIN_WIDTH: Final = 520
#: 需要在没有选中项时置灰的动作：这些语义上都要求"先有一条日程"。
_SELECTION_ACTIONS: Final = ("view", "edit", "delete", "duplicate")
#: 行内「⋯」按钮：只在鼠标悬停到某一行时浮出来，省得为改一条把鼠标拉回顶部。
_ROW_MENU_SIZE: Final = 24
_ROW_MENU_MARGIN: Final = 8
#: 选中行左侧竖条的宽度。
_SELECTION_BAR_WIDTH: Final = 3


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


def _as_int(value: object) -> int:
    """把 QSettings 读回来的东西转成整数；转不了就返回 0（当没存过）。

    QSettings 在 Windows 注册表与 INI 两种后端下返回的类型不一样（int 或 str），
    配置项又可能是别人手改过的，所以这里不做假设、失败即忽略。
    """
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return 0


def _clear_icon(color: str) -> QIcon:
    """搜索框末尾那颗 ✕。

    不用 `QLineEdit.setClearButtonEnabled(True)`：它取的是系统标准图标，深色主题下
    会变成一团看不清的深灰。自己画两笔，颜色跟着当前主题走。
    """
    size = 16
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        pen = QPen(QColor(color), 1.6)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawLine(5, 5, 11, 11)
        painter.drawLine(11, 5, 5, 11)
    finally:
        painter.end()
    return QIcon(pixmap)


def _danger_icon(color: str) -> QIcon:
    """菜单里破坏项的标记：一只小垃圾桶。

    右键菜单没法只给某一个菜单项换字色（QSS 的 `QMenu::item` 认不出是哪一个），
    除非整项换成 `QWidgetAction`；画一个红色图标是最省的做法，也能被高对比度主题
    直接读懂——颜色不是唯一的信号。
    """
    size = 14
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        pen = QPen(QColor(color), 1.4)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawLine(2, 4, 12, 4)  # 盖
        painter.drawLine(5, 2, 9, 2)  # 提手
        painter.drawLine(4, 4, 4, 12)  # 桶身左
        painter.drawLine(10, 4, 10, 12)  # 桶身右
        painter.drawLine(4, 12, 10, 12)  # 底
    finally:
        painter.end()
    return QIcon(pixmap)


def _theme_icon(dark: bool, color: str) -> QIcon:
    """主题开关的图标：浅色主题下画月亮（点一下变暗），深色下画太阳。

    图标承担"点了会变成什么"，文字固定写「深色模式」，两者不再互相矛盾。
    不用系统标准图标：深色主题下它们会糊成一团。
    """
    size = 16
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        center = QPointF(8.0, 8.0)
        if dark:
            pen = QPen(QColor(color), 1.5)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.drawEllipse(center, 3.2, 3.2)
            for step in range(8):
                radians = math.radians(step * 45)
                painter.drawLine(
                    QPointF(8 + 5.6 * math.cos(radians), 8 + 5.6 * math.sin(radians)),
                    QPointF(8 + 7.2 * math.cos(radians), 8 + 7.2 * math.sin(radians)),
                )
        else:
            # 月牙就是一个实心圆减去一个偏移的圆；用 Clear 合成直接挖掉，不必算路径。
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(color))
            painter.drawEllipse(center, 4.8, 4.8)
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
            painter.drawEllipse(QPointF(11.0, 6.2), 4.4, 4.4)
    finally:
        painter.end()
    return QIcon(pixmap)


def _tabular(font: QFont) -> QFont:
    """把数字排成等宽（tabular figures）。

    时间列右对齐之后，"09:30" 与 "10:00" 里的 `1` 与 `0` 宽度不同会让整列看起来
    参差；等宽数字是这一列唯一的对齐依据。旧版 PySide6 没有这个 API 时静默跳过。
    """
    with contextlib.suppress(AttributeError, TypeError):
        font.setFeature(QFont.Tag("tnum"), 1)
    return font


class _RowDelegate(QStyledItemDelegate):
    """行级绘制：悬停时整行换底色，选中行左边缘画一条主色竖条。

    两件事都不能靠 QSS：

    - `QTableWidget::item:hover` 只把**鼠标所在的那一个单元格**染色，指针压在
      备注列上就只有备注列变灰，整行看起来断成两截；
    - 选中底色与日历里"这天有日程"的底色是同一个浅蓝，只靠底色分不清
      "我选中了这条"与"这天有安排"。

    竖条画在**第一列可见列**上而不是固定第 0 列：单日视图里日期列是收起的，
    固定第 0 列会让这条线彻底消失。`first_column` 由表格提供。
    """

    def __init__(
        self,
        accent: str,
        hover: str,
        first_column: Callable[[], int],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._accent = QColor(accent)
        self._hover = QColor(hover)
        self._hover_row: int | None = None
        self._first_column = first_column

    @property
    def hover_row(self) -> int | None:
        return self._hover_row

    def set_hover_row(self, row: int | None) -> None:
        self._hover_row = row

    def set_colors(self, accent: str, hover: str) -> None:
        """主题切换时只换颜色，不重建 delegate。"""
        self._accent = QColor(accent)
        self._hover = QColor(hover)

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex | QPersistentModelIndex,
    ) -> None:
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        # 选中行有自己的底色，悬停不该把它盖掉——否则鼠标扫过时"选中的是哪条"会消失。
        if index.row() == self._hover_row and not selected:
            painter.fillRect(option.rect, self._hover)
        super().paint(painter, option, index)
        if not selected or index.column() != self._first_column():
            return
        rect = option.rect
        painter.fillRect(
            rect.left(),
            rect.top() + 6,
            _SELECTION_BAR_WIDTH,
            max(0, rect.height() - 12),
            self._accent,
        )


class _DragTable(QTableWidget):
    """表格唯一的改动：拖拽载荷里只放一个 `schedule_id`。

    默认实现会把整行序列化成一串 item 数据，落点那头还得反解出"这是哪一条"；
    而本项目的规矩是**只用 id 指认记录**，所以拖拽载荷与行身份是同一个东西。
    """

    def mimeData(self, items: Sequence[QTableWidgetItem]) -> QMimeData:  # noqa: N802
        data = QMimeData()
        for item in items:
            value = item.data(_ID_ROLE)
            if value is not None:
                data.setData(SCHEDULE_DRAG_MIME, str(value).encode("utf-8"))
                break
        return data


class _EmptyState(QWidget):
    """列表没有内容时整块替换表格的空状态：居中标题 + 一句说明 + 一个行动按钮。

    以前这里只是往表格里插一行灰字，占着第一行却什么也点不了；空状态真正该做的
    是**把下一步交到手上**——这一天没安排就给「新增这一天」，搜不到就给「清空搜索」。
    """

    action_clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("EmptyState")

        self._title = QLabel("", self)
        self._title.setObjectName("EmptyTitle")
        self._title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._title.setWordWrap(True)

        self._hint = QLabel("", self)
        self._hint.setObjectName("EmptyHint")
        self._hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._hint.setWordWrap(True)

        self._action = QPushButton("", self)
        self._action.setObjectName("EmptyAction")
        self._action.setCursor(Qt.CursorShape.PointingHandCursor)
        self._action.clicked.connect(self.action_clicked)

        action_row = QHBoxLayout()
        action_row.addStretch(1)
        action_row.addWidget(self._action)
        action_row.addStretch(1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(8)
        layout.addStretch(1)
        layout.addWidget(self._title)
        layout.addWidget(self._hint)
        layout.addSpacing(6)
        layout.addLayout(action_row)
        layout.addStretch(1)

    def set_content(self, title: str, hint: str, action_text: str) -> None:
        self._title.setText(title)
        self._hint.setText(hint)
        self._hint.setVisible(bool(hint))
        self._action.setText(action_text)

    @property
    def title_text(self) -> str:
        return self._title.text()

    @property
    def action_text(self) -> str:
        return self._action.text()


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
        self._search_summary: tuple[str, int] | None = None
        # 排序状态：None 表示没点过表头，保持后端给的顺序（全天在前、再按时间）。
        self._sort_column: int | None = None
        self._sort_desc = False
        # 本次运行有没有出现过任何一行。为空时空状态要说的话取决于它。
        self._seen_rows = False
        self._collator = QCollator(QLocale(QLocale.Language.Chinese, QLocale.Country.China))
        self._day_label = QLabel("", self)
        self._day_label.setObjectName("DayHeading")
        self._table = _DragTable(0, len(_COLUMN_HEADERS), self)
        self._table.setMinimumWidth(_TABLE_MIN_WIDTH)
        self._status_label = QLabel("就绪", self)
        self._selection_label = QLabel(presenters.selection_text(None), self)
        # 状态栏右侧常驻的一行事实：这一屏有几条、上次刷新到几点。
        # 左下角那个位置留给操作反馈（"已保存""已删除"），两者不该互相顶掉。
        self._summary_label = QLabel("", self)

        self._search_input = QLineEdit(self)
        self._search_input.setObjectName("SearchInput")
        self._search_input.setPlaceholderText(_SEARCH_PLACEHOLDER)
        self._search_input.setFixedWidth(_SEARCH_INPUT_WIDTH)
        self._search_input.setToolTip("按标题或备注搜索全部日程（Ctrl+F）")
        # 清空入口收进输入框内部：有字才出现，不再常驻一颗占位按钮。
        self._clear_search_action = self._search_input.addAction(
            _clear_icon(theme.palette(self._dark).muted),
            QLineEdit.ActionPosition.TrailingPosition,
        )
        self._clear_search_action.setToolTip("清空搜索并回到当前日期（Esc）")
        self._clear_search_action.setVisible(False)
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(_SEARCH_DEBOUNCE_MS)

        self._upcoming_list = QListWidget(self)
        self._upcoming_list.setObjectName("UpcomingList")
        self._upcoming_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._upcoming_list.setMinimumHeight(_UPCOMING_MIN_HEIGHT)
        self._upcoming_list.setToolTip("点击条目跳到对应日期并选中该日程")

        self._build_layout()
        self._build_row_menu_button()
        self._build_toolbar()
        self._connect_signals()

        # controller 放在 UI 建完之后创建：它需要把自己登记为 view，
        # 而写法的 `__init__` 走完后 `self` 才算可用。
        self._controller: ScheduleController = ScheduleController(
            service=service, view=self, clock=clock
        )

        self._controller.start()
        self._restore_layout()

    # -------------------------------------------------------- 窗口状态的记忆

    def _restore_layout(self) -> None:
        """恢复上次退出时的窗口大小、分栏位置、列宽与排序。

        这四项都是"每天都要重新调一次"的东西：不记的话每次启动都得重新拉窗口、
        拉分栏、拖列宽，再点一次表头。它们不改变任何业务语义，存与不存只差
        几行 QSettings 读写，却省掉每天重复的手工调整。
        """
        geometry = self._settings.value(_GEOMETRY_SETTING)
        if isinstance(geometry, QByteArray):
            self.restoreGeometry(geometry)
        splitter_state = self._settings.value(_SPLITTER_SETTING)
        if isinstance(splitter_state, QByteArray):
            self._splitter.restoreState(splitter_state)

        widths = self._settings.value(_COLUMNS_SETTING)
        if isinstance(widths, (list, tuple)):
            for column, raw in enumerate(list(widths)[:3]):
                width = _as_int(raw)
                if width > 0:
                    self._table.setColumnWidth(column, width)

        sort = self._settings.value(_SORT_SETTING)
        if isinstance(sort, str) and ":" in sort:
            column_text, _, order_text = sort.partition(":")
            column = _as_int(column_text)
            if 0 <= column < len(_COLUMN_HEADERS):
                self._sort_column = column
                self._sort_desc = order_text == "desc"
                self._update_header_labels()
                self._paint_rows(self._controller.rows)

    def _persist_layout(self) -> None:
        """把窗口状态写进 QSettings；关窗时调用一次。"""
        self._settings.setValue(_GEOMETRY_SETTING, self.saveGeometry())
        self._settings.setValue(_SPLITTER_SETTING, self._splitter.saveState())
        self._settings.setValue(
            _COLUMNS_SETTING,
            [self._table.columnWidth(column) for column in range(self._table.columnCount())],
        )
        if self._sort_column is None:
            # 从没点过表头就清掉旧值：否则"取消排序"会被上一次的方向悄悄复活。
            self._settings.remove(_SORT_SETTING)
        else:
            order = "desc" if self._sort_desc else "asc"
            self._settings.setValue(_SORT_SETTING, f"{self._sort_column}:{order}")

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        """关窗前记下窗口状态，下一次启动原样回来。"""
        self._persist_layout()
        super().closeEvent(event)

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        """窗口变宽时把多出来的空间补给备注列，别在右边留一条空白。"""
        super().resizeEvent(event)
        self._fill_notes_column()

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802
        """首次显示时补一次列宽：此时视口才有真实宽度。"""
        super().showEvent(event)
        self._fill_notes_column()

    def _fill_notes_column(self) -> None:
        """备注列吃掉视口的剩余宽度，**只增不减**。

        四列都是 Interactive 之后表格不会自己撑满，不补这一步窗口拉宽时右边
        会空出一条，看起来像列没加载出来。只增不减是为了不跟用户抢方向盘：
        手动把备注拖窄之后，不该在下一次 resize 时被悄悄改回去。
        """
        viewport = self._table.viewport()
        if viewport.width() <= 0:
            return
        used = sum(
            self._table.columnWidth(column)
            for column in range(self._table.columnCount() - 1)
            if not self._table.isColumnHidden(column)
        )
        target = max(_NOTES_COLUMN_MIN_WIDTH, viewport.width() - used)
        if target > self._table.columnWidth(3) + 1:
            self._table.setColumnWidth(3, target)

    # ------------------------------------------------------------ 构建 UI

    def _build_layout(self) -> None:
        self._configure_table()

        calendar_card = QFrame(self)
        calendar_card.setObjectName("Card")
        calendar_layout = QVBoxLayout(calendar_card)
        calendar_layout.setContentsMargins(_CARD_MARGIN, _CARD_MARGIN, _CARD_MARGIN, _CARD_MARGIN)
        calendar_layout.setSpacing(10)
        # 摘要不再塞进左卡片：日历拿到整张卡片的高度，日期行与徽标才有呼吸空间。
        calendar_layout.addWidget(self._calendar, 1)

        right_card = QFrame(self)
        right_card.setObjectName("Card")
        right_layout = QVBoxLayout(right_card)
        right_layout.setContentsMargins(_CARD_MARGIN, _CARD_MARGIN, _CARD_MARGIN, _CARD_MARGIN)
        right_layout.setSpacing(10)
        title_row = QHBoxLayout()
        title_row.setSpacing(8)
        title_row.addWidget(self._day_label, 1)
        title_row.addWidget(self._search_input)
        right_layout.addLayout(title_row)
        # 表格与空状态二选一：空状态占满表格那块区域，而不是往表格里插一行灰字。
        self._empty_state = _EmptyState(right_card)
        self._stack = QStackedWidget(right_card)
        self._stack.addWidget(self._table)
        self._stack.addWidget(self._empty_state)
        # 表格 : 摘要 = 3 : 1：摘要随窗口一起长，不再钉死在一个高度上。
        right_layout.addWidget(self._stack, 3)

        # 摘要放在表格下方：搜索态下右侧只剩两行结果，原来那段空白正好被摘要填上。
        upcoming_title = QLabel(_SECTION_UPCOMING, right_card)
        upcoming_title.setObjectName("SectionTitle")
        right_layout.addWidget(upcoming_title)
        right_layout.addWidget(self._upcoming_list, 1)

        # 日历卡片按内容高度贴合，剩下的空间留给页面底色：日历被限高之后，
        # 如果让卡片自己撑满，下面会留一片"卡片里的空白"，看着像内容没加载完。
        left_column = QWidget(self)
        left_layout = QVBoxLayout(left_column)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(calendar_card, 0)
        left_layout.addStretch(1)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(left_column)
        splitter.addWidget(right_card)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([340, 660])
        self._splitter = splitter

        outer = QWidget(self)
        outer_layout = QHBoxLayout(outer)
        outer_layout.setContentsMargins(_OUTER_MARGIN, _OUTER_MARGIN, _OUTER_MARGIN, _OUTER_MARGIN)
        outer_layout.setSpacing(16)
        outer_layout.addWidget(splitter)
        self.setCentralWidget(outer)

        status = QStatusBar(self)
        status.addWidget(self._status_label, 1)
        self._undo_button = QPushButton("撤销删除", self)
        self._undo_button.setObjectName("UndoButton")
        self._undo_button.setToolTip("恢复最近一次删除的日程（5 秒内有效，Ctrl+Z）")
        status.addPermanentWidget(self._summary_label)
        status.addPermanentWidget(self._selection_label)
        status.addPermanentWidget(self._undo_button)
        # QStatusBar 会在加入时显示子控件；这里再明确收起，启动时不出现空入口。
        self._undo_button.setVisible(False)
        # 撤销只在删除后的几秒内成立：入口自己会消失，`Ctrl+Z` 也按同一个时限判断。
        self._undo_available = False
        self._undo_timer = QTimer(self)
        self._undo_timer.setSingleShot(True)
        self._undo_timer.setInterval(_UNDO_WINDOW_MS)
        self._undo_timer.timeout.connect(self._expire_undo)
        self.setStatusBar(status)
        status.setSizeGripEnabled(False)

    def _configure_table(self) -> None:
        """表格的呈现细节：无网格、固定行高、四列各自的伸缩方式。"""
        self._table.setHorizontalHeaderLabels(list(_COLUMN_HEADERS))
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setShowGrid(False)
        # 斑马纹退掉：`#F9FAFB` 与白底的对比度只有 1.02，等于白配一条规则，
        # 还会与"选中行"的浅蓝、行悬停的浅灰混成三种几乎一样的分组信号。
        # 行与行改用 40px 行高留白区分，加上悬停底色就够定位了。
        self._table.setAlternatingRowColors(False)
        self._table.setWordWrap(False)
        self._table.verticalHeader().setVisible(False)
        self._table.verticalHeader().setDefaultSectionSize(_ROW_HEIGHT)
        self._row_delegate = _RowDelegate(
            theme.palette(self._dark).primary,
            theme.palette(self._dark).row_hover,
            self._first_visible_column,
            self._table,
        )
        self._table.setItemDelegate(self._row_delegate)
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.horizontalHeader().sectionClicked.connect(self._on_header_clicked)
        # 只做拖源：拖到日历上改日期。表格自身不接受放到它上面的东西。
        self._table.setDragEnabled(True)
        self._table.setDragDropMode(QAbstractItemView.DragDropMode.DragOnly)
        self._table.setDefaultDropAction(Qt.DropAction.MoveAction)
        self._table.setDragDropOverwriteMode(False)

        header = self._table.horizontalHeader()
        header.setFixedHeight(_HEADER_HEIGHT)
        header.setStretchLastSection(False)
        # 四列全部 Interactive：只有 Interactive 的段才响应"双击分隔线自适应内容"，
        # 备注列以前是 Stretch，双击一直没反应。宽度仍会被记住，窗口拉宽时由
        # `_fill_notes_column()` 把多出来的空间补到备注列上，避免右侧留一片空白。
        for column in range(len(_COLUMN_HEADERS)):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.Interactive)
        self._table.setColumnWidth(0, _DATE_COLUMN_WIDTH)
        self._table.setColumnWidth(1, _TIME_COLUMN_WIDTH)
        self._table.setColumnWidth(2, _TITLE_COLUMN_WIDTH)
        self._table.setColumnWidth(3, _NOTES_COLUMN_WIDTH)

    def _build_row_menu_button(self) -> None:
        """行内操作入口：鼠标停在哪一行，右上角就浮出一个「⋯」。

        它是 viewport 的子控件而不是表格的列：不占列宽、不进 Tab 链，
        鼠标移开就消失；点它等价于在那一行上右键。
        """
        self._row_menu_button = QToolButton(self._table.viewport())
        self._row_menu_button.setObjectName("RowMenu")
        self._row_menu_button.setText("⋯")
        self._row_menu_button.setToolTip("这一行的操作")
        self._row_menu_button.setCursor(Qt.CursorShape.PointingHandCursor)
        # QToolButton 默认是「只显示图标」，没有图标就什么都不画，字也一起没了。
        self._row_menu_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self._row_menu_button.setFixedSize(_ROW_MENU_SIZE, _ROW_MENU_SIZE)
        self._row_menu_button.hide()
        self._row_menu_button.clicked.connect(self._open_row_menu_from_button)
        self._row_menu_row: int | None = None

        viewport = self._table.viewport()
        viewport.setMouseTracking(True)
        viewport.installEventFilter(self)
        # 滚动之后原来那一行已经不在指针下面了，按钮与行底色必须一起收起。
        self._table.verticalScrollBar().valueChanged.connect(self._clear_hover)
        self._table.horizontalScrollBar().valueChanged.connect(self._clear_hover)

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
            shortcut = _ACTION_SHORTCUTS.get(key)
            if shortcut is not None:
                action.setShortcut(QKeySequence(shortcut))
                # 窗口级：主窗口激活时可用，不要求焦点在某个控件上。
                action.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
            toolbar.addAction(action)
            self._actions[key] = action
            # QToolBar 里的 QToolButton 默认是 NoFocus：纯键盘用户按 Tab 根本走不到
            # 工具栏，而「修改」又没有快捷键，等于只有鼠标能用。显式给 TabFocus 补上。
            button = toolbar.widgetForAction(action)
            if button is not None:
                button.setFocusPolicy(Qt.FocusPolicy.TabFocus)
                # 七个入口不该同一音量：「新增」是主要动作，「删除」是唯一不可逆的动作。
                if key == "create":
                    button.setObjectName("PrimaryAction")
                elif key == "delete":
                    button.setObjectName("DangerAction")

        # 主题开关与业务动作不是一类东西，推到工具栏右端：它不该夹在「刷新」和
        # 「退出」中间，让人以为也是某个业务入口。
        spacer = QWidget(self)
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(spacer)
        toolbar.addSeparator()
        self._dark_action = QAction("深色模式", self)
        # 不做成可勾选的开关：文字写的是"点下去会变成什么"（在深色下写「浅色模式」），
        # 再挂一个勾选态，读者要同时理解"勾着"和"写着浅色"两个互相矛盾的信息。
        self._dark_action.setCheckable(False)
        toolbar.addAction(self._dark_action)
        dark_button = toolbar.widgetForAction(self._dark_action)
        if dark_button is not None:
            dark_button.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self._sync_dark_action()

        # 接转发方法而不是直接接 controller：这里按下就算一次用户操作，
        # 具体该怎么办由 controller 说了算，窗口本身不做判断。
        self._actions["create"].triggered.connect(self._on_create)
        self._actions["view"].triggered.connect(self._on_view)
        self._actions["edit"].triggered.connect(self._on_edit)
        self._actions["delete"].triggered.connect(self._on_delete)
        self._actions["duplicate"].triggered.connect(self._on_duplicate)
        self._actions["refresh"].triggered.connect(self._on_refresh)
        self._actions["quit"].triggered.connect(self.close)
        self._dark_action.triggered.connect(self._toggle_dark)

    def _connect_signals(self) -> None:
        self._table.itemSelectionChanged.connect(self._on_row_selected)
        # 双击一行等于修改。桌面列表里这是最不用解释的动作，缺了会让人以为程序只会读。
        self._table.itemDoubleClicked.connect(self._on_row_double_clicked)
        # 点空白处取消选中：QTableWidget 自己不这么做，得在 viewport 上看按下事件。
        self._table.viewport().installEventFilter(self)
        self._calendar.day_picked.connect(self._on_day_picked)
        self._calendar.day_activated.connect(self._on_day_activated)
        self._calendar.month_changed.connect(self._on_month_changed)
        self._search_input.textChanged.connect(self._on_search_text_changed)
        self._search_input.returnPressed.connect(self._trigger_search)
        self._clear_search_action.triggered.connect(self._on_clear_search_clicked)
        self._search_timer.timeout.connect(self._trigger_search)
        self._upcoming_list.itemClicked.connect(self._on_upcoming_clicked)
        self._table.customContextMenuRequested.connect(self._show_table_context_menu)
        self._empty_state.action_clicked.connect(self._on_empty_action)
        self._calendar.schedule_dropped.connect(self._on_schedule_dropped)
        self._undo_button.clicked.connect(self._on_undo_delete)
        self._search_shortcut = QShortcut(QKeySequence("Ctrl+F"), self)
        self._search_shortcut.activated.connect(self._focus_search)
        # Esc 是"退一层"：有搜索先退搜索，没有搜索再取消选中。窗口级快捷键，
        # 表单打开时主窗口不是激活窗口，因此不会抢走表单自己的 Esc。
        self._escape_shortcut = QShortcut(QKeySequence("Escape"), self)
        self._escape_shortcut.activated.connect(self._on_escape)
        # Ctrl+Z 与状态栏那个「撤销删除」等价：同一次删除，两个入口。
        self._undo_shortcut = QShortcut(QKeySequence.StandardKey.Undo, self)
        self._undo_shortcut.activated.connect(self._on_undo_delete)
        # 只在表格和它的子控件获得焦点时生效：焦点在搜索框或表单里时，
        # Delete 应当是编辑文本，绝不能变成删除整条日程。
        self._table_shortcuts: tuple[QShortcut, ...] = (
            self._make_table_shortcut("Delete", self._on_delete),
            self._make_table_shortcut("Return", self._on_view),
            self._make_table_shortcut("Enter", self._on_view),
        )

    def _make_table_shortcut(self, key: str, handler: Callable[[], None]) -> QShortcut:
        """把表格内的按键绑成表格作用域快捷键。"""
        shortcut = QShortcut(QKeySequence(key), self._table)
        shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        shortcut.activated.connect(handler)
        return shortcut

    # --------------------------------------------------- MainViewPort 实现

    def show_rows(self, rows: Sequence[ScheduleRow]) -> None:
        """整体重绘列表。每行都带着 id 存在角色数据里，绝不按行号反查记录。"""
        # 见过任何一条就记住：之后某一天为空，说明的是"这天没安排"，
        # 而不是"你还没开始用"，两种空该说不同的话。
        if rows:
            self._mark_seen()
        self._paint_rows(rows)
        # 摘要刷新放在列表重绘之后，且不在 controller.refresh 里调用：
        # 保存、删除、切日期、搜索都会走到这里，一处接线覆盖全部路径，
        # 同时 controller 单测的服务调用次数保持不变。
        QTimer.singleShot(0, self._refresh_upcoming)

    def _paint_rows(self, rows: Sequence[ScheduleRow]) -> None:
        """按当前排序列出表格；排序只在呈现层做，行身份仍靠 id。"""
        rows = self._sorted_rows(rows)
        colors = theme.palette(self._dark)
        self._table.blockSignals(True)
        try:
            self._table.setRowCount(0)
            self._table.clearSpans()
            for row in rows:
                index = self._table.rowCount()
                self._table.insertRow(index)
                values = (
                    row.date.isoformat() if row.date is not None else "—",
                    row.time_text,
                    row.title_text,
                    row.notes_text,
                )
                for column, text in enumerate(values):
                    item = QTableWidgetItem(text)
                    item.setData(_ID_ROLE, row.schedule_id)
                    self._style_cell(item, column, colors, row.all_day)
                    self._table.setItem(index, column, item)
            self._restore_selection(self._controller.selected_id)
        finally:
            self._table.blockSignals(False)
        self._clear_hover()
        self._sync_date_column(bool(self._controller.search_text))
        self._update_empty_state(bool(rows))
        # 重绘后按钮可用性必须跟着选中态走，否则会出现"行没了、按钮还亮着"。
        self._apply_selection_state()
        self._update_summary()

    def _first_visible_column(self) -> int:
        """最左边那一列的 logical index；日期列收起时它就是时间列。

        `QHeaderView.logicalIndex(0)` 在这里不合用：隐藏的 section 仍然占着
        视觉索引位，它照样返回 0，竖条就会画在一条根本不被绘制的列上。
        """
        header = self._table.horizontalHeader()
        for column in range(self._table.columnCount()):
            if not header.isSectionHidden(column):
                return column
        return 0

    def _cell_font(self, pixel_size: int, weight: QFont.Weight) -> QFont:
        """以表格当前字体为底，只改字号与字重，不指定字族（跟着系统走）。"""
        font = QFont(self._table.font())
        font.setPixelSize(pixel_size)
        font.setWeight(weight)
        return font

    def _style_cell(
        self,
        item: QTableWidgetItem,
        column: int,
        colors: theme.Palette,
        all_day: bool,
    ) -> None:
        """四列各有各的音量：标题最重、时间次之、日期与备注退到辅助层。

        所有单元格同字号同字重的时候，四列在扫读时是平权的，眼睛没有落点；
        字阶拉开之后，"是哪一条"由标题承担，"什么时候"由时间承担，
        日期与备注只需要"在需要时读得到"。
        """
        if column == 0:
            item.setFont(self._cell_font(12, QFont.Weight.Normal))
            item.setForeground(QColor(colors.muted))
        elif column == 1:
            item.setFont(_tabular(self._cell_font(13, QFont.Weight.Medium)))
            item.setForeground(QColor(colors.muted if all_day else colors.text))
            item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        elif column == 2:
            item.setFont(self._cell_font(14, QFont.Weight.Medium))
        else:
            item.setFont(self._cell_font(12, QFont.Weight.Normal))
            item.setForeground(QColor(colors.muted))
        # 标题与备注会被列宽截断；截断后唯一的出口是「查看」，
        # 所以这里挂全文 tooltip——用户不必为看全一句话多开一个框。
        if column in (1, 2, 3) and item.text():
            item.setToolTip(item.text())

    def _sync_date_column(self, searching: bool) -> None:
        """单日视图里每行日期都一样，日期列是纯重复，收起来把宽度让给标题。

        搜索会跨日期命中，"这条在哪天"只能靠日期列回答，所以搜索态必须显示。
        """
        self._table.setColumnHidden(0, not searching)

    def _update_summary(self) -> None:
        """状态栏右侧常驻：这一屏数据是什么时候取回来的。

        条数由左侧的 `ready_text` 说过了，这里不重复，只补时间。
        """
        self._summary_label.setText(presenters.synced_at_text(dt.datetime.now().strftime("%H:%M")))

    def _sorted_rows(self, rows: Sequence[ScheduleRow]) -> list[ScheduleRow]:
        """按 `_sort_column` / `_sort_desc` 排序；没点过表头就保持后端顺序。

        后端的顺序（全天在前、再按时间）是有意义的默认值，用户没要求就不动它。
        字符串列用 `QCollator` 而不是 Python 的字典序：中文按拼音、数字按数值，
        直接 `sorted()` 会得到"10 在 2 前面"这种结果。
        """
        column = self._sort_column
        if column is None or len(rows) < 2:
            return list(rows)

        if column == 0:
            ordered = sorted(rows, key=lambda row: (row.date is None, row.date or dt.date.min))
        elif column == 1:
            # 全天在一天的最前面，这一点与后端一致；其余按 HH:MM 文本比较即可（补零）。
            ordered = sorted(rows, key=lambda row: (0 if row.all_day else 1, row.time_text))
        else:
            use_title = column == 2

            def compare(left: ScheduleRow, right: ScheduleRow) -> int:
                left_text = left.title_text if use_title else left.notes_text
                right_text = right.title_text if use_title else right.notes_text
                return self._collator.compare(left_text, right_text)

            ordered = sorted(rows, key=cmp_to_key(compare))
        if self._sort_desc:
            ordered.reverse()
        return ordered

    def _on_header_clicked(self, column: int) -> None:
        """点表头排序：同一列再点一次反向，换列则从升序开始。"""
        if self._sort_column == column:
            self._sort_desc = not self._sort_desc
        else:
            self._sort_column = column
            self._sort_desc = False

        header = self._table.horizontalHeader()
        # 方向由表头文字里的箭头说明，不再画 Qt 那个小三角：两个指示器叠在一起时
        # 反而是小三角更显眼、更含糊。
        header.setSortIndicatorShown(False)
        header.setSortIndicator(
            column,
            Qt.SortOrder.DescendingOrder if self._sort_desc else Qt.SortOrder.AscendingOrder,
        )
        self._update_header_labels()
        self._paint_rows(self._controller.rows)

    def _update_header_labels(self) -> None:
        """把排序方向写进表头文字：上升/下降箭头画在原位上，文字必须自己说清。

        只留 Qt 自带的小三角时，"排的是哪一列、是升还是降"要靠凑近看才能分辨；
        文字带箭头是一眼能读的，而且深浅色主题下都不会糊。
        """
        for column, base in enumerate(_COLUMN_HEADERS):
            label = base
            if column == self._sort_column:
                label = f"{base} {'↓' if self._sort_desc else '↑'}"
            item = self._table.horizontalHeaderItem(column)
            if item is None:
                continue
            item.setText(label)

    def show_count(self, text: str) -> None:
        """日期标题与条数：标题用大字号，条数退成弱化的正文，避免一行全是重音。"""
        self._count_text = text
        self._search_summary = None
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

    def show_search_state(self, text: str, total: int) -> None:
        """搜索态标题：明确写出关键词与命中数，不再显示某个具体日期。"""
        self._search_summary = (text, total)
        self._day_label.setText(presenters.search_heading(escape(text), total))

    def clear_search(self) -> None:
        """清空搜索框；屏蔽信号，避免 `clear()` 又触发一次搜索。"""
        self._search_timer.stop()
        self._search_summary = None
        self._search_input.blockSignals(True)
        try:
            self._search_input.clear()
        finally:
            self._search_input.blockSignals(False)
        # 清空是屏蔽信号做的，`textChanged` 不会发，✕ 得手动收起。
        self._clear_search_action.setVisible(False)

    def show_upcoming(self, rows: Sequence[ScheduleRow]) -> None:
        """未来 7 天摘要：空列表放一个不可选中的占位项，不留空白。"""
        self._upcoming_list.clear()
        if rows:
            # "见过日程"的判据之一：今天为空、但未来 7 天有，说明用户不是第一次打开。
            self._mark_seen()
        if not rows:
            placeholder = QListWidgetItem(presenters.upcoming_empty_text())
            placeholder.setFlags(Qt.ItemFlag.NoItemFlags)
            self._upcoming_list.addItem(placeholder)
            return

        previous_day: dt.date | None = None
        for row in rows:
            item = QListWidgetItem(presenters.upcoming_line(row, new_day=row.date != previous_day))
            item.setData(_ID_ROLE, row.schedule_id)
            item.setData(_UPCOMING_DAY_ROLE, row.date)
            item.setToolTip(row.notes_text or "（无备注）")
            self._upcoming_list.addItem(item)
            previous_day = row.date

    def show_selection(self, text: str) -> None:
        self._selection_label.setText(text)

    def show_status(self, text: str) -> None:
        self._status_label.setText(text)

    def show_undo_available(self, available: bool) -> None:
        """状态栏「撤销删除」入口的显隐；controller 决定什么时候还有可撤销的删除。

        出现时给一个 5 秒窗口，超时自动收起。入口一直挂着会让用户以为随时能撤，
        结果撤回来一条十分钟前就放下的记录——撤销的语义是"反悔一次"，不是"历史列表"。
        """
        self._undo_available = available
        self._undo_button.setVisible(available)
        if available:
            self._undo_timer.start()
        else:
            self._undo_timer.stop()

    def _expire_undo(self) -> None:
        """5 秒到：收起入口，并让 Ctrl+Z 给出同一句话而不是默默无事发生。"""
        self._undo_available = False
        self._undo_button.setVisible(False)

    def show_month_counts(self, counts: dict[dt.date, int]) -> None:
        """把这个月「哪天有几条」交给日历去标记。"""
        if counts:
            # 判据之二：当月任何一天有日程，也不算"一条都没有"。
            # 只靠当天列表判断会把"今天空、别天有"的人误判成首次使用。
            self._mark_seen()
        self._calendar.set_counts(counts)

    def select_calendar_day(self, day: dt.date) -> None:
        """让日历的选中格跟上当前筛选日期。

        `CalendarPanel.set_selected_day` 会屏蔽由本次移动产生的选中信号，
        因此这里不会反过来再触发一次「用户选了某天」。
        """
        self._calendar.set_selected_day(day)

    def show_info(self, message: str) -> None:
        """提醒而不是报错：未选中是界面状态问题，不该看起来像出了故障。"""
        QMessageBox.information(self, "提示", message)

    def show_error(self, headline: str, message: str) -> None:
        QMessageBox.warning(self, headline, message)

    def show_detail(self, row: ScheduleRow) -> None:
        """详情用列表已有的数据展示，不再查一次服务（controller 已经解释了为什么）。"""
        QMessageBox.information(self, "日程详情", presenters.detail_text(row))

    def ask_delete_confirm(self, row: ScheduleRow) -> bool:
        """删除确认。**调用它不等于已经删了**，只有返回 True 才会真的调 delete。

        按钮自己指定中文文案而不是用 `Yes` / `No`：Qt 的内置标准按钮要加载
        翻译包才会变成中文，漏装时用户看到的就是英文。这里同时把「删除」
        放进 DestructiveRole、把默认焦点放在「取消」——破坏性动作不该是回车
        就执行的那一个。
        """
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("确认删除")
        box.setText(f"确定要删除「{row.title_text}」（{row.time_text}）吗？")
        box.setInformativeText("删除后状态栏会出现「撤销删除」，可恢复最近一次删除。")
        delete_button = box.addButton("删除", QMessageBox.ButtonRole.DestructiveRole)
        # 破坏性动作用危险色：蓝色主色是"推荐你点"，红色才是"想清楚再点"。
        colors = theme.palette(self._dark)
        delete_button.setStyleSheet(
            f"QPushButton {{ background-color: {colors.danger};"
            f" color: {colors.on_danger}; border: 1px solid {colors.danger};"
            " border-radius: 6px; padding: 5px 18px; font-weight: bold; }"
        )
        cancel_button = box.addButton("取消", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(cancel_button)
        box.setEscapeButton(cancel_button)
        box.exec()
        return box.clickedButton() is delete_button

    def open_schedule_form(self, request: FormRequest) -> ScheduleDraft | None:
        """打开表单，结果交给 controller；取消返回 None。

        复用同一个对话框实例：保存失败时 controller 会带着原草稿与错误结论
        再来一次，如果每次都新建窗口，用户看到的是"框闪一下、位置跳到屏幕中央"，
        会以为刚才填的东西丢了。
        """
        form = getattr(self, "_form", None)
        if form is None:
            form = ScheduleForm(request, self)
            self._form = form
        else:
            form.apply(request)
        if form.exec() != QDialog.DialogCode.Accepted:
            return None
        return form.draft()

    # ------------------------------------------------------------------ 内部

    def _apply_theme(self) -> None:
        """把当前主题的 QSS 与调色板套到整个应用；窗口、表单、消息框一起生效。"""
        colors = theme.palette(self._dark)
        app = QApplication.instance()
        if isinstance(app, QApplication):
            app.setPalette(_application_palette(colors))
            app.setStyleSheet(theme.stylesheet(self._dark))
        # 下面两样是"画出来的颜色"，QSS 管不到，主题切换时必须手动跟着换：
        # 整行悬停底色与选中竖条来自 delegate 的画笔，搜索框的 ✕ 是一张位图。
        if hasattr(self, "_row_delegate"):
            self._row_delegate.set_colors(colors.primary, colors.row_hover)
        if hasattr(self, "_clear_search_action"):
            self._clear_search_action.setIcon(_clear_icon(colors.muted))

    def _sync_dark_action(self) -> None:
        """文字固定写「深色模式」，改由图标与 tooltip 说清"现在是什么、点了变什么"。

        以前文字写的是"点下去会变成什么"（深色下写「浅色模式」），同时又挂着
        一个勾选态，读者要同时理解"勾着"和"写着浅色"两个互相矛盾的信息。
        """
        colors = theme.palette(self._dark)
        self._dark_action.setText("深色模式")
        self._dark_action.setIcon(_theme_icon(self._dark, colors.muted))
        self._dark_action.setToolTip(
            "当前是深色主题，点击切换到浅色" if self._dark else "当前是浅色主题，点击切换到深色"
        )

    def _toggle_dark(self) -> None:
        """主题开关：点一下就在两套主题之间换一次。

        不是可勾选开关，所以没有 `toggled(checked)` 可用——这里自己取反。
        """
        self._on_dark_toggled(not self._dark)

    def _on_dark_toggled(self, dark: bool) -> None:
        self._dark = dark
        self._sync_dark_action()
        self._apply_theme()
        self._calendar.set_dark(dark)
        if self._search_summary is not None:
            self.show_search_state(*self._search_summary)
        elif self._count_text:
            self.show_count(self._count_text)
        # 单元格的字号与字色是逐格设的（不走 QSS），换主题后必须整表重画：
        # 否则上一套主题的深灰字会压在深色底上——时间那一列会直接看不见。
        if hasattr(self, "_controller"):
            self._paint_rows(self._controller.rows)
        self._settings.setValue(_DARK_SETTING, dark)

    def _on_create(self) -> None:
        self._controller.request_create()

    def _on_view(self) -> None:
        self._controller.request_view()

    def _on_edit(self) -> None:
        self._controller.request_edit()

    def _on_delete(self) -> None:
        self._controller.request_delete()

    def _on_duplicate(self) -> None:
        self._controller.request_duplicate()

    def _on_undo_delete(self) -> None:
        """撤销入口：按钮与 Ctrl+Z 共用；过了 5 秒就说清楚为什么不行。

        用状态栏而不是消息框：这不是错误，只是"晚了一步"，为它弹一个要手动
        点掉的框，比什么都不做更烦。
        """
        if not self._undo_available:
            self.show_status(presenters.undo_expired_text())
            return
        self._undo_timer.stop()
        self._controller.undo_delete()

    def _on_refresh(self) -> None:
        """手动刷新列表；只有查询成功才宣称“已刷新”，失败时保留错误框与旧列表。"""
        if self._controller.refresh():
            self.show_status(presenters.refreshed_text(len(self._controller.rows)))

    def _on_row_selected(self) -> None:
        self._controller.select_row(self._selected_row_id())
        self._apply_selection_state()

    def _apply_selection_state(self) -> None:
        """有选中项才让「查看/修改/删除/复制」可点。

        没有选中时把它们灰掉，比让人点完再看一句「请先选中一条日程」好：
        灰掉的按钮自己就在说明条件，不需要额外一次点击和一次弹框。
        """
        has_selection = self._controller.selected_id is not None
        for key in _SELECTION_ACTIONS:
            action = self._actions.get(key)
            if action is not None:
                action.setEnabled(has_selection)

    def _on_row_double_clicked(self, item: QTableWidgetItem) -> None:
        """双击一行直接进入修改；双击空状态提示行不做任何事。"""
        if item.data(_ID_ROLE) is None:
            return
        self._on_edit()

    def eventFilter(self, watched: object, event: QEvent) -> bool:  # noqa: N802
        """表格 viewport 上的三件小事：点空白取消选中、悬停出「⋯」、空白双击新增。

        `QTableWidget` 点空白不会清空选择，用户点完空白仍看到底部写着
        「已选中：…」，与刚做的动作相反。这里在按下时判断落点是否落在有 id
        的单元格上，不是就清掉选中（同时清 currentItem，否则它会立刻把选中复原）。
        """
        if watched is self._table.viewport():
            if event.type() == QEvent.Type.MouseMove and isinstance(event, QMouseEvent):
                self._sync_row_menu(event.position().toPoint())
            elif event.type() == QEvent.Type.Leave:
                self._hide_row_menu_unless_hovered()
            elif (
                event.type() == QEvent.Type.MouseButtonPress
                and isinstance(event, QMouseEvent)
                and event.button() == Qt.MouseButton.LeftButton
                and self._row_id_at(event.position().toPoint()) is None
            ):
                self._clear_selection()
            elif (
                event.type() == QEvent.Type.MouseButtonDblClick
                and isinstance(event, QMouseEvent)
                and event.button() == Qt.MouseButton.LeftButton
                and self._row_id_at(event.position().toPoint()) is None
            ):
                self._on_blank_double_clicked()
        return super().eventFilter(watched, event)  # type: ignore[arg-type]

    def _on_blank_double_clicked(self) -> None:
        """列表空白处双击等于新增这一天，与日历上双击某个日期是同一个语义。

        搜索态下不接这个手势：这时列表说的是"全库里命中这些"，空白处到底
        代表哪一天是含糊的，宁可不响应也不要猜。
        """
        if self._controller.search_text:
            return
        day = self._controller.current_day
        self._controller.request_create_for_day(day)

    def _sync_row_menu(self, pos: QPoint) -> None:
        """把「⋯」挪到鼠标所在行的右端；落在空白处就收起。

        横向位置钉在 viewport 右侧而不是"指针所在那一列的右边缘"：后者会让按钮
        跟着鼠标左右跳，同一个动作每次出现在不同地方。纵向跟着行，这样"哪一行"
        始终是明确的。
        """
        index = self._table.indexAt(pos)
        if not index.isValid() or self._row_id_at(pos) is None:
            self._clear_hover()
            return

        rect = self._table.visualRect(index)
        viewport_width = self._table.viewport().width()
        x = max(0, viewport_width - _ROW_MENU_SIZE - _ROW_MENU_MARGIN)
        y = rect.top() + max(0, (rect.height() - _ROW_MENU_SIZE) // 2)
        self._row_menu_row = index.row()
        self._set_hover_row(index.row())
        self._row_menu_button.move(x, y)
        self._row_menu_button.show()
        self._row_menu_button.raise_()

    def _set_hover_row(self, row: int | None) -> None:
        """整行悬停底色由 delegate 画，所以这里只需告诉它换到哪一行。"""
        if self._row_delegate.hover_row == row:
            return
        self._row_delegate.set_hover_row(row)
        self._table.viewport().update()

    def _clear_hover(self) -> None:
        """收起行内入口与行底色：滚动、指针离开、列表重绘都走这里。"""
        self._row_menu_button.hide()
        self._row_menu_row = None
        self._set_hover_row(None)

    def _hide_row_menu_unless_hovered(self) -> None:
        """鼠标离开表格时收起「⋯」，但移到自己身上不算离开（否则点不到）。

        鼠标从 viewport 移进它自己的子控件时，viewport 会收到 Leave；此时指针
        其实正压在那颗按钮上，直接隐藏会让按钮"一靠近就消失"。同理行底色也要
        留着——指针还在这一行上。
        """
        if not self._row_menu_button.isVisible():
            self._clear_hover()
            return
        button_rect = self._row_menu_button.geometry()
        # 按钮的父控件就是表格 viewport，`geometry()` 与 `mapFromGlobal` 用同一个坐标系。
        cursor = self._table.viewport().mapFromGlobal(QCursor.pos())
        if button_rect.contains(cursor):
            return
        self._clear_hover()

    def _open_row_menu_from_button(self) -> None:
        """点「⋯」：先选中那一行，再把菜单弹在按钮下方。"""
        menu = self._prepare_row_menu(self._row_menu_row)
        if menu is not None:
            menu.exec(self._row_menu_button.mapToGlobal(QPoint(0, _ROW_MENU_SIZE)))

    def _prepare_row_menu(self, row: int | None) -> QMenu | None:
        """选中第 `row` 行并造出它的菜单；行不存在时返回 None（不弹空菜单）。"""
        if row is None:
            return None
        item = self._table.item(row, 0)
        if item is None or item.data(_ID_ROLE) is None:
            return None
        self._table.selectRow(row)
        self._controller.select_row(str(item.data(_ID_ROLE)))
        self._apply_selection_state()
        return self._build_row_menu()

    def _clear_selection(self) -> None:
        """清空选中与当前格：只清选择的话，currentRow 会把选中立刻还原。"""
        self._table.clearSelection()
        self._table.setCurrentCell(-1, -1)
        self._controller.select_row(None)
        self._apply_selection_state()

    def _row_id_at(self, pos: QPoint) -> str | None:
        """坐标对应的行 id；空白处、空状态提示行都返回 None（无副作用）。"""
        index = self._table.indexAt(pos)
        if not index.isValid():
            return None
        item = self._table.item(index.row(), 0)
        if item is None:
            return None
        value = item.data(_ID_ROLE)
        return None if value is None else str(value)

    def _on_escape(self) -> None:
        """Esc 退一层：先退搜索，没有搜索再取消选中。"""
        if self._controller.search_text:
            self._search_timer.stop()
            self._controller.set_search("")
            return
        self._clear_selection()

    def _on_search_text_changed(self, text: str) -> None:
        """输入时不立即查服务：250ms 防抖，只有停下来才触发一次搜索。

        清空输入框是一个明确的“退出搜索”动作，立即执行；继续等防抖会让
        用户以为清空没生效。
        """
        # ✕ 只在有内容时出现：空输入框上挂一颗按不动的按钮，等于多一个死目标。
        self._clear_search_action.setVisible(bool(text))
        if text.strip():
            self._search_timer.start()
            return
        self._search_timer.stop()
        self._trigger_search()

    def _trigger_search(self) -> None:
        """把搜索框内容交给 controller；窗口本身永远不直接调用服务。"""
        self._search_timer.stop()
        if hasattr(self, "_controller"):
            self._controller.set_search(self._search_input.text())

    def _on_clear_search_clicked(self) -> None:
        """清空按钮：明确退出搜索，回到当前日期列表。"""
        self._search_timer.stop()
        if hasattr(self, "_controller"):
            self._controller.set_search("")

    def _focus_search(self) -> None:
        self._search_input.setFocus()
        self._search_input.selectAll()

    def _refresh_upcoming(self) -> None:
        """列表重绘后刷新未来 7 天摘要；controller 尚未建好时静默跳过。"""
        if hasattr(self, "_controller"):
            self._controller.load_upcoming()

    def _on_upcoming_clicked(self, item: QListWidgetItem) -> None:
        """点击摘要条目：跳到那一天并选中对应行，不直接打开表单。"""
        day = item.data(_UPCOMING_DAY_ROLE)
        schedule_id = item.data(_ID_ROLE)
        if day is None or schedule_id is None:
            return
        self._controller.select_upcoming(day, str(schedule_id))

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

    def _show_table_context_menu(self, pos: QPoint) -> None:
        """表格右键：有行弹行菜单，空白处弹全局菜单。

        空白处以前什么都不弹，看起来像右键没被接住。但空选中时「修改/删除/复制」
        确实没有意义，所以空白处换成两个不需要选中项的动作，而不是把整份行菜单置灰。
        """
        if self._select_row_at(pos) is not None:
            menu = self._build_row_menu()
        else:
            menu = self._build_blank_menu()
        menu.exec(self._table.viewport().mapToGlobal(pos))

    def _build_blank_menu(self) -> QMenu:
        """空白处右键：只放"不需要先选一条"的动作。"""
        menu = QMenu(self._table)
        create = menu.addAction("新增这一天\tCtrl+N")
        create.triggered.connect(self._on_create)
        refresh = menu.addAction("刷新\tF5")
        refresh.triggered.connect(self._on_refresh)
        return menu

    def _select_row_at(self, pos: QPoint) -> str | None:
        """把右键位置对应的行选中；空白、空状态提示行都返回 None。"""
        schedule_id = self._row_id_at(pos)
        if schedule_id is None:
            return None
        index = self._table.indexAt(pos)
        self._table.selectRow(index.row())
        # 已经选中的行不会再发 itemSelectionChanged，这里显式同步一次。
        self._controller.select_row(schedule_id)
        self._apply_selection_state()
        return schedule_id

    def _build_row_menu(self) -> QMenu:
        """行菜单与工具栏共用同一批转发方法，入口不同、行为只有一份。

        快捷键画在菜单里（`\\t` 之后是快捷键列，不注册成真的 QAction 快捷键，
        免得和表格已有的 Delete/Enter 抢事件）：`Delete`、`Ctrl+D` 本来就实现了，
        不写出来只有读过 README 的人知道。删除单独一条分隔线 + 红色垃圾桶图标，
        把破坏性动作与「查看/修改/复制」分开。
        """
        menu = QMenu(self._table)
        colors = theme.palette(self._dark)
        entries = (
            ("查看", "Enter", self._on_view),
            ("修改", "双击", self._on_edit),
            ("复制到…", "Ctrl+D", self._on_duplicate),
        )
        for text, hint, handler in entries:
            action = menu.addAction(f"{text}\t{hint}")
            action.triggered.connect(handler)
        menu.addSeparator()
        delete_action = menu.addAction("删除\tDelete")
        delete_action.setIcon(_danger_icon(colors.danger))
        delete_action.triggered.connect(self._on_delete)
        return menu

    def _mark_seen(self) -> None:
        """记下"库里确实有东西"，并立刻把当前那句首启文案换成"这天没有"。

        三个入口都可能先于空状态渲染完成（列表为空、摘要与月度条数是延迟取的），
        所以翻转时要把已经画出来的空状态就地刷新一次，否则用户会先看到
        「还没有任何日程」再看它跳到正常文案。
        """
        if self._seen_rows:
            return
        self._seen_rows = True
        if hasattr(self, "_stack") and self._stack.currentWidget() is self._empty_state:
            self._update_empty_state(False)

    def _update_empty_state(self, has_rows: bool) -> None:
        """在表格与空状态之间切换，并按"为什么空"给出不同的下一步。

        搜索无命中与“这一天没有日程”是两种不同的空：前者要提示换关键词并给
        「清空搜索」，后者要告诉用户怎么新增。同一条文案会让人以为搜索把日期切走了。
        """
        if has_rows:
            self._stack.setCurrentWidget(self._table)
            return

        searching = getattr(self, "_controller", None) is not None and bool(
            self._controller.search_text
        )
        if searching:
            self._empty_state.set_content(
                presenters.search_empty_text(self._controller.search_text), "", "清空搜索"
            )
        elif not self._seen_rows:
            # 一次都还没见过日程：这句要回答"数据会不会丢""是不是装坏了"，
            # 而不是让用户以为日期被切到了空的一天。
            self._empty_state.set_content(_FIRST_RUN_TITLE, _FIRST_RUN_HINT, _FIRST_RUN_ACTION)
        else:
            self._empty_state.set_content(_EMPTY_DAY_TITLE, _EMPTY_DAY_HINT, _EMPTY_ACTION)
        self._stack.setCurrentWidget(self._empty_state)

    def _on_schedule_dropped(self, schedule_id: str, day: object) -> None:
        """日历上松手：把"这条改到那天"交给 controller，窗口不自己判断。"""
        if isinstance(day, dt.date):
            self._controller.request_move_to_day(schedule_id, day)

    def _on_empty_action(self) -> None:
        """空状态那颗按钮：搜索空了就退搜索，日期空了就给这一天新增。"""
        if self._controller.search_text:
            self._search_timer.stop()
            self._controller.set_search("")
            return
        self._controller.request_create_for_day(self._controller.current_day)

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
