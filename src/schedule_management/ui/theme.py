"""界面主题：浅色 / 深色两套 QSS，以及日历自绘要用的色板。

这个模块刻意**不 import PySide6**：QSS 只是一段文本，色板只是一组字符串。
把颜色与样式集中在这里，窗口模块只负责套用，不在各自的 `setStyleSheet`
里散落十六进制色值——否则改一次主色要翻五个文件，深色模式更是没法一致。

分层守卫（`tests/unit/test_ui_layering.py`）把本模块登记在「Qt 呈现资源」一档：
它讲的是 Qt 的样式语言，与呈现强相关，但没有 Qt 依赖，因此导入期零副作用。

设计口径（`docs/figures/ui-interaction.md` 第 3 节，2026-10-20 改为 Apple 视觉语言）：

- 浅色：页面底色 `#F5F5F7`、白色卡片、主色 `#0071E3`、正文 `#1D1D1F`、
  弱化文字 `#86868B`、边框 `#E5E5EA`、分隔线 `#D2D2D7`、有日程日期底色
  `#EAF3FF`、今天用橙色 `#FF9F0A` / `#C93400`；
- 深色：页面底色 `#000000`、卡片 `#1C1C1E`、次级表面 `#2C2C2E`、主色
  `#0A84FF`、正文 `#F5F5F7`、弱化文字 `#98989D`、边框与分隔线 `#38383A`；
- 圆角 18 px（卡片）/ 10-12 px（输入框、按钮），靠留白与细边框分层；
  **不用大面积渐变**。QSS 的 `box-shadow` 不被 Qt 支持，写了只会得到解析警告。

字阶（只有四档，字重只用 400 与 500/600，不再随机加粗）：

| 用途 | 字号 | 字重 | 例子 |
| --- | --- | --- | --- |
| 页面标题 | 18 | 600 | `10月20日 周二　共 3 条` |
| 列表主行 | 14 | 600 | 日程标题 |
| 正文 | 13 | 400 | 时间、表单、菜单、按钮 |
| 辅助 | 11-12 | 400/500 | 备注、日期列、表头、状态栏、分组头 |

列表的层次不靠"行线"分开：行高 44 px + 整行悬停底色，行与行靠留白分组；
列与列之间只有一条 1 px 的分隔线（由 `_RowDelegate` 与表头共同画出），
既让拖动边界可见，又不把列表变回电子表格。

字体栈由 `FONT_FAMILIES` 给出，窗口在构造时用 `QFont.setFamilies()` 一次性
装到应用上。Qt 的 QSS 对逗号分隔的 `font-family` 支持并不可靠，因此 QSS 只
负责字号与字重，字族由 QFont 的回退链承担：macOS 命中 SF Pro，Windows 命中
Segoe UI / 微软雅黑。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from string import Template
from typing import Final

#: 应用字体栈：优先 Apple 系统字体，其次 Windows 自带的无衬线字体。
#: `QFont.setFamilies()` 会按顺序命中第一个已安装的字族。
FONT_FAMILIES: Final[tuple[str, ...]] = (
    "SF Pro Text",
    "SF Pro Display",
    "Segoe UI",
    "Microsoft YaHei UI",
    "Noto Sans CJK SC",
    "sans-serif",
)

#: 正文基准字号；其余字号都在 QSS 或单元格字体里显式指定。
FONT_PIXEL_SIZE: Final = 13


@dataclass(frozen=True)
class Palette:
    """一套主题的颜色表。

    字段名就是 QSS 模板里的占位符名（`$primary` 等），因此模板与色板不会
    各写一套名字。日历的自绘（底色、今天、徽标）与表格的列分隔线也从这里取色，
    避免深色模式下「白底浅字」这种只在截图里才发现的对比度问题。
    """

    background: str
    surface: str
    surface_alt: str
    text: str
    muted: str
    border: str
    #: 表格列分隔线 / 表头分隔线。比 `border` 略深一档，拖动列宽时边界才看得见；
    #: 两套主题分别取 Apple 的系统分隔线色 `#D2D2D7` 与 `#38383A`。
    separator: str
    primary: str
    primary_hover: str
    primary_pressed: str
    on_primary: str
    hover: str
    #: 表格整行的悬停底色。与 `hover`（控件上的浅灰）分开：列表行铺满整行，
    #: 只在指针所在行上"轻轻抬一下"才不影响扫读。
    row_hover: str
    event_background: str
    today_accent: str
    today_foreground: str
    today_background: str
    badge_background: str
    badge_text: str
    danger: str
    on_danger: str
    #: 错误条 / 危险提示的浅底色。红字压在纯白或纯深底上都能读，但一个错误条
    #: 如果只有一行红字、没有底色，很容易被当成正文的一部分略过去。
    danger_soft: str


#: 浅色主题：默认主题，也是文档截图的基准。
LIGHT_PALETTE: Final = Palette(
    background="#F5F5F7",
    surface="#FFFFFF",
    surface_alt="#F5F5F7",
    text="#1D1D1F",
    muted="#86868B",
    border="#E5E5EA",
    separator="#D2D2D7",
    primary="#0071E3",
    primary_hover="#0077ED",
    primary_pressed="#0066CC",
    on_primary="#FFFFFF",
    hover="#F0F0F2",
    row_hover="#F5F5F7",
    event_background="#EAF3FF",
    today_accent="#FF9F0A",
    today_foreground="#C93400",
    today_background="#FFF4E5",
    badge_background="#0071E3",
    badge_text="#FFFFFF",
    danger="#FF3B30",
    on_danger="#FFFFFF",
    danger_soft="#FFEBEA",
)

#: 深色主题：页面纯黑，卡片与次级表面各亮一档，边框再亮一档。
DARK_PALETTE: Final = Palette(
    background="#000000",
    surface="#1C1C1E",
    surface_alt="#2C2C2E",
    text="#F5F5F7",
    muted="#98989D",
    border="#38383A",
    separator="#38383A",
    primary="#0A84FF",
    primary_hover="#3395FF",
    primary_pressed="#0066CC",
    on_primary="#FFFFFF",
    hover="#2C2C2E",
    row_hover="#2C2C2E",
    event_background="#102A43",
    today_accent="#FF9F0A",
    today_foreground="#FFB340",
    today_background="#3A2A12",
    #: 徽标比主色深一档：深色主题的 #0A84FF 配白字只有 3.6:1，
    #: 而徽标只有 8-10 px，必须拿到 4.5:1 以上才读得清。
    badge_background="#0066CC",
    badge_text="#FFFFFF",
    danger="#FF453A",
    on_danger="#FFFFFF",
    danger_soft="#3A1D1C",
)


_STYLESHEET_TEMPLATE: Final = Template(
    """
/* ---------------------------------------------------------------- 基底 */
QMainWindow, QDialog, QMessageBox {
    background-color: $background;
}

QWidget {
    color: $text;
    font-size: 13px;
}

QToolTip {
    background-color: $surface;
    color: $text;
    border: 1px solid $border;
    border-radius: 6px;
    padding: 4px 8px;
}

/* ------------------------------------------------------------ 顶部工具栏 */
/* Apple 的工具栏是一条安静的白带：没有边框盒子，只有一条极浅的底线。
   品牌与主操作靠字重和蓝色药丸分层，其余入口退成纯文字。 */
QToolBar {
    background-color: $surface;
    border: none;
    border-bottom: 1px solid $border;
    padding: 10px 18px;
    spacing: 4px;
}

QToolBar::separator {
    width: 1px;
    background-color: $border;
    margin: 6px 12px;
}

QToolButton {
    background-color: transparent;
    color: $text;
    border: 1px solid transparent;
    border-radius: 8px;
    padding: 6px 10px;
    font-size: 13px;
    font-weight: 500;
}

QToolButton:hover {
    background-color: $hover;
    border-color: transparent;
}

QToolButton:pressed {
    background-color: $event_background;
}

QToolButton:checked {
    background-color: $event_background;
    color: $primary;
    border-color: transparent;
}

QToolButton:disabled {
    color: $muted;
}

/* 键盘焦点必须看得见：`outline: none` 之后 Tab 过去只剩极细的一圈边框变化，
   纯键盘用户根本找不到自己在哪。焦点环用 2px 主色描边，不动布局。 */
QToolButton:focus {
    border: 2px solid $primary;
    padding: 5px 9px;
}

QToolButton#RowMenu:focus {
    padding: 0;
}

/* 「新增」是这一屏唯一的主要动作：Apple 蓝药丸，其余入口都是文字按钮。
   七个入口如果全是同一种文字按钮，扫一眼分不出"通常点哪个"。 */
QToolButton#PrimaryAction {
    background-color: $primary;
    color: $on_primary;
    border: 1px solid transparent;
    border-radius: 15px;
    padding: 7px 18px;
    font-weight: 600;
}

QToolButton#PrimaryAction:hover {
    background-color: $primary_hover;
}

QToolButton#PrimaryAction:pressed {
    background-color: $primary_pressed;
}

QToolButton#PrimaryAction:disabled {
    background-color: $surface_alt;
    color: $muted;
}

/* 删除是破坏性动作：常态与其它入口同权重（避免整个工具栏冒红），
   悬停时才转红提示"这一个点了会没"。 */
QToolButton#DangerAction:hover {
    color: $danger;
    background-color: $danger_soft;
}

QLabel#Brand {
    color: $text;
    font-size: 17px;
    font-weight: 600;
    padding: 0 12px 0 4px;
}

QLabel#DayHeading {
    color: $text;
    font-size: 18px;
    font-weight: 600;
    padding: 2px 2px 2px 2px;
}

/* 今天是橙色：与主色蓝明确分工——蓝色回答"有日程"，橙色回答"就是今天"。 */
QLabel#TodayLabel {
    color: $today_foreground;
    font-size: 12px;
    font-weight: 600;
    border-left: 3px solid $today_accent;
    padding: 2px 2px 4px 9px;
}

QLabel#Hint {
    color: $muted;
    font-size: 11px;
}

/* 自绘的星期条：替换 QCalendarWidget 内置那一行（内置版把周末染红）。 */
QLabel#Weekday {
    color: $muted;
    font-size: 11px;
    font-weight: 500;
    padding: 2px 0;
}

/* ---------------------------------------------------------------- 卡片 */
/* 18 px 圆角 + 1 px 极浅描边，是 Apple 分组容器的基本形状。
   不用投影：QSS 不支持，QGraphicsDropShadowEffect 又会让日历与表格
   多一层离屏合成，滚动重绘明显变慢。 */
QFrame#Card {
    background-color: $surface;
    border: 1px solid $border;
    border-radius: 18px;
}

QSplitter::handle {
    background-color: transparent;
}

QSplitter::handle:horizontal {
    width: 16px;
}

/* ---------------------------------------------------------------- 菜单 */
QMenu {
    background-color: $surface;
    color: $text;
    border: 1px solid $border;
    border-radius: 12px;
    padding: 5px;
}

QMenu::item {
    background-color: transparent;
    padding: 6px 22px 6px 14px;
    border-radius: 7px;
    min-width: 150px;
}

/* 菜单选中是实心主色：这是 Apple 菜单最容易被认出的一个细节。 */
QMenu::item:selected {
    background-color: $primary;
    color: $on_primary;
}

QMenu::item:disabled {
    color: $muted;
}

QMenu::separator {
    height: 1px;
    background-color: $border;
    margin: 4px 10px;
}

/* ---------------------------------------------------------------- 表格 */
QTableWidget {
    background-color: $surface;
    color: $text;
    border: 1px solid transparent;
    border-radius: 12px;
    selection-background-color: $event_background;
    selection-color: $text;
    /* 选中行的当前格会带一圈虚线焦点框，看起来像渲染没擦干净；
       键盘导航不靠这圈线也认得出选中行，因此只去掉描边，不动焦点策略。 */
    outline: none;
}

/* 表格自己有焦点时给一层主色描边：光标进了列表，接下来的 Delete / Enter
   才会作用在行上——这件事必须能看出来。平时是透明边框，不占布局。 */
QTableWidget:focus {
    border-color: $primary;
}

/* 行与行不画分割线：`border-bottom` 每行都画会变成电子表格。
   靠 44 px 行高留白分组；整行悬停底色由 `_RowDelegate` 画——QSS 的
   `::item:hover` 只给鼠标所在的那一个单元格上色，整行会断成两截。 */
QTableWidget::item {
    padding: 0 12px;
    border: none;
}

/* 写在 `:hover` 之后：同一行既被悬停又被选中时，选中的底色说了算。 */
QTableWidget::item:selected {
    background-color: $event_background;
    color: $text;
}

QTableCornerButton::section {
    background-color: $surface;
    border: none;
}

QHeaderView {
    background-color: $surface;
    border: none;
}

/* 表头是安静的一行小字：11 px、弱化色、只有底部一条线与一条列分隔线。
   列分隔线让拖动边界可见，同时不恢复横网格（列表不是电子表格）。 */
QHeaderView::section {
    background-color: $surface;
    color: $muted;
    border: none;
    border-bottom: 1px solid $border;
    border-right: 1px solid $separator;
    padding: 0 12px;
    font-size: 11px;
    font-weight: 600;
}

QHeaderView::section:hover {
    background-color: $surface_alt;
    color: $text;
}

QHeaderView::section:pressed {
    background-color: $surface_alt;
}

/* 最后一列不再多画一条右边界：表格自身已经有圆角描边。 */
QHeaderView::section:last {
    border-right: none;
}

/* 滚动条压成细条，不抢内容；无箭头，符合系统覆盖式滚动条的手感。 */
QScrollBar:vertical {
    background: transparent;
    width: 10px;
    margin: 2px;
}

QScrollBar::handle:vertical {
    background: $separator;
    border-radius: 3px;
    min-height: 30px;
}

QScrollBar:horizontal {
    background: transparent;
    height: 10px;
    margin: 2px;
}

QScrollBar::handle:horizontal {
    background: $separator;
    border-radius: 3px;
    min-width: 30px;
}

QScrollBar::add-line, QScrollBar::sub-line {
    width: 0;
    height: 0;
    background: transparent;
    border: none;
}

QScrollBar::add-page, QScrollBar::sub-page {
    background: transparent;
}

/* ---------------------------------------------------------------- 日历 */
QCalendarWidget {
    background-color: $surface;
    border: none;
}

QCalendarWidget QWidget#qt_calendar_navigationbar {
    background-color: $surface;
    border: none;
    padding: 2px 0 4px 0;
}

/* 自绘的月份导航：左箭头 + 月份 + 右箭头。内置导航条在 Windows 上把年份、
   月份和箭头排成三件对不齐的控件，Apple 的日历只有一个居中的月份标题。 */
QLabel#CalendarMonth {
    color: $text;
    font-size: 14px;
    font-weight: 600;
}

QToolButton#CalendarNav {
    background-color: transparent;
    color: $text;
    border: none;
    border-radius: 8px;
    padding: 0;
    font-size: 18px;
    font-weight: 500;
}

QToolButton#CalendarNav:hover {
    background-color: $hover;
}

QToolButton#CalendarNav:pressed {
    background-color: $event_background;
}

QCalendarWidget QToolButton {
    background-color: transparent;
    color: $text;
    border: 1px solid transparent;
    border-radius: 8px;
    padding: 4px 8px;
    font-size: 14px;
    font-weight: 600;
}

QCalendarWidget QToolButton:hover {
    background-color: $hover;
}

QCalendarWidget QToolButton:pressed {
    background-color: $event_background;
}

QCalendarWidget QMenu {
    background-color: $surface;
    color: $text;
    border: 1px solid $border;
    border-radius: 12px;
}

QCalendarWidget QSpinBox {
    background-color: $surface_alt;
    color: $text;
    border: 1px solid transparent;
    border-radius: 8px;
    padding: 2px 6px;
}

QCalendarWidget QAbstractItemView:enabled {
    background-color: $surface;
    color: $text;
    selection-background-color: $primary;
    selection-color: $on_primary;
    outline: none;
    font-size: 13px;
}

QCalendarWidget QAbstractItemView:disabled {
    color: $muted;
}

/* 星期条复用 QHeaderView，但日历里的它不该有表格表头那条底边与列线。 */
QCalendarWidget QHeaderView::section {
    background-color: $surface;
    color: $muted;
    border: none;
    padding: 0;
    font-size: 11px;
    font-weight: 500;
}

/* ------------------------------------------------------------ 按钮与输入 */
QPushButton {
    background-color: $primary;
    color: $on_primary;
    border: 1px solid transparent;
    border-radius: 10px;
    padding: 7px 16px;
    font-weight: 600;
}

QPushButton:hover {
    background-color: $primary_hover;
}

QPushButton:pressed {
    background-color: $primary_pressed;
}

QPushButton:disabled {
    background-color: $surface_alt;
    color: $muted;
}

QPushButton:focus {
    border: 2px solid $primary_pressed;
    padding: 6px 15px;
}

/* 「回到今天」「选择」是次级动作：浅灰底、无边框，悬停只加深一档。 */
QPushButton#TodayButton, QPushButton#PickButton {
    background-color: $surface_alt;
    color: $text;
    border: 1px solid transparent;
    border-radius: 10px;
    padding: 6px 12px;
    font-weight: 500;
}

QPushButton#TodayButton:hover, QPushButton#PickButton:hover {
    background-color: $hover;
    border-color: $separator;
}

QDialog QPushButton {
    background-color: $surface_alt;
    color: $text;
    border: 1px solid transparent;
}

QDialog QPushButton:hover {
    background-color: $hover;
    border-color: $separator;
}

QDialog QPushButton:default {
    background-color: $primary;
    color: $on_primary;
    border-color: transparent;
}

QLineEdit, QTextEdit, QPlainTextEdit {
    background-color: $surface;
    color: $text;
    border: 1px solid $separator;
    border-radius: 10px;
    padding: 7px 10px;
    selection-background-color: $primary;
    selection-color: $on_primary;
}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {
    border-color: $primary;
}

QCheckBox {
    color: $text;
    spacing: 8px;
}

/* 标题为空时把边框染红：这是"提示"而不是"拦截"——保存照样会发到后端，
   判定权仍在服务层，这里只是把一定会被拒的情况提前说出来。
   属性选择器写在 `:focus` 之后，避免聚焦时被主色盖掉。 */
QLineEdit[requiredMissing="true"] {
    border-color: $danger;
}

QLineEdit[requiredMissing="true"]:focus {
    border-color: $danger;
}

/* 表单顶部的错误条：保存失败时就地显示，取代"弹框 → 关表单 → 重开"那一路。 */
QLabel#FormError {
    background-color: $danger_soft;
    color: $danger;
    border: none;
    border-radius: 10px;
    padding: 8px 12px;
}

/* 必填标记与字段提示。 */
QLabel#RequiredMark {
    color: $danger;
    font-weight: 600;
}

QLabel#FieldHint {
    color: $muted;
    font-size: 12px;
}

/* ------------------------------------------------------ 搜索与 7 天摘要 */
QLineEdit#SearchInput {
    background-color: $surface_alt;
    color: $text;
    border: 1px solid transparent;
    border-radius: 10px;
    padding: 6px 10px;
    selection-background-color: $primary;
    selection-color: $on_primary;
}

QLineEdit#SearchInput:hover {
    border-color: $separator;
}

QLineEdit#SearchInput:focus {
    background-color: $surface;
    border-color: $primary;
}

/* 搜索框尾巴上那颗 ✕：只有输入框里有字才出现，走 QLineEdit 的
   trailing action，不再单独占一个「清空」按钮的位置。 */
QLineEdit#SearchInput QToolButton {
    background-color: transparent;
    border: none;
    padding: 0;
    margin-right: 2px;
}

QLineEdit#SearchInput QToolButton:hover {
    background-color: $border;
    border-radius: 8px;
}

QPushButton#UndoButton {
    background-color: transparent;
    color: $primary;
    border: 1px solid transparent;
    border-radius: 8px;
    padding: 2px 8px;
    font-weight: 500;
}

QPushButton#UndoButton:hover {
    background-color: $event_background;
}

QLabel#SectionTitle {
    color: $muted;
    font-size: 11px;
    font-weight: 600;
    padding: 4px 2px 0 2px;
}

/* ---------------------------------------------- 列表为空时的整页空状态 */
/* 空状态只有三行字，必须靠字号把"这是什么情况 / 我该做什么"分开；
   三者同样大小的时候，看起来像一段没排过版的说明文字。 */
QLabel#EmptyTitle {
    color: $text;
    font-size: 20px;
    font-weight: 600;
}

QLabel#EmptyHint {
    color: $muted;
    font-size: 13px;
}

QPushButton#EmptyAction {
    padding: 8px 20px;
    font-weight: 600;
}

/* 摘要里的分组头（`10-21 周三 · 2 条`）：不可点，只做分隔与计数。 */
QListWidget#UpcomingList::item:disabled {
    color: $muted;
    font-size: 11px;
    font-weight: 600;
    padding-top: 8px;
}

/* 摘要列表是卡片里的分组列表：不套第二层边框，靠悬停与留白分区。 */
QListWidget#UpcomingList {
    background-color: transparent;
    color: $text;
    border: none;
    padding: 0;
    outline: none;
}

QListWidget#UpcomingList::item {
    padding: 6px 8px;
    border-radius: 8px;
}

QListWidget#UpcomingList::item:hover {
    background-color: $hover;
}

QListWidget#UpcomingList::item:selected {
    background-color: $event_background;
    color: $text;
}

/* ---------------------------------------------------------------- 状态栏 */
/* 状态栏退到页面底色上，只留一条极浅的上边线：它是"事实"，不是操作区。 */
QStatusBar {
    background-color: $background;
    border-top: 1px solid $border;
    color: $muted;
    padding: 4px 20px;
}

QStatusBar QLabel {
    color: $muted;
    font-size: 11px;
}

QStatusBar::item {
    border: none;
}
"""
)


def _render(colors: Palette) -> str:
    """把色板代入 QSS 模板；缺字段会在这里直接抛 `KeyError`，不会静默留空。"""
    return _STYLESHEET_TEMPLATE.substitute(asdict(colors))


LIGHT_STYLESHEET: Final = _render(LIGHT_PALETTE)
DARK_STYLESHEET: Final = _render(DARK_PALETTE)


def palette(dark: bool) -> Palette:
    """返回对应主题的色板。"""
    return DARK_PALETTE if dark else LIGHT_PALETTE


def stylesheet(dark: bool) -> str:
    """返回对应主题的完整 QSS。"""
    return DARK_STYLESHEET if dark else LIGHT_STYLESHEET


__all__ = [
    "DARK_PALETTE",
    "DARK_STYLESHEET",
    "FONT_FAMILIES",
    "FONT_PIXEL_SIZE",
    "LIGHT_PALETTE",
    "LIGHT_STYLESHEET",
    "Palette",
    "palette",
    "stylesheet",
]
