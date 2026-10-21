"""界面主题：浅色 / 深色两套 QSS，以及日历自绘要用的色板。

这个模块刻意**不 import PySide6**：QSS 只是一段文本，色板只是一组字符串。
把颜色与样式集中在这里，窗口模块只负责套用，不在各自的 `setStyleSheet`
里散落十六进制色值——否则改一次主色要翻五个文件，深色模式更是没法一致。

分层守卫（`tests/unit/test_ui_layering.py`）把本模块登记在「Qt 呈现资源」一档：
它讲的是 Qt 的样式语言，与呈现强相关，但没有 Qt 依赖，因此导入期零副作用。

设计口径（`docs/figures/ui-interaction.md` 第 3 节）：

- 浅色：页面底色 `#F4F6FA`、白色卡片、主色 `#2563EB`、正文 `#1F2937`、
  弱化文字 `#6B7280`、边框 `#E5E7EB`、有日程日期底色 `#DBEAFE`、
  今天用琥珀色 `#F59E0B` / `#B45309`；
- 深色：页面底色 `#111827`、卡片 `#1F2937`、主色 `#60A5FA`、正文 `#F9FAFB`、
  弱化文字 `#9CA3AF`、边框 `#374151`；
- 圆角 8-10 px，靠留白与边框分层，**不用渐变、不用投影**：QSS 的阴影伪效
  在 Windows 高 DPI 下容易糊成一条脏边，也会拖慢表格重绘。

字阶（只有四档，字重只用 400 与 500/600，不再随机加粗）：

| 用途 | 字号 | 字重 | 例子 |
| --- | --- | --- | --- |
| 页面标题 | 18 | 600 | `10月20日 周二　共 3 条` |
| 列表主行 | 14 | 500 | 日程标题 |
| 正文 | 13 | 400 | 时间、表单、菜单、按钮 |
| 辅助 | 12 | 400 | 备注、日期列、状态栏、分组头 |

列表的层次不靠"行线"分开：`border-bottom` 每行都画会让它长得像电子表格，
改成 40px 行高 + 悬停底色，行与行靠留白分组。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from string import Template
from typing import Final


@dataclass(frozen=True)
class Palette:
    """一套主题的颜色表。

    字段名就是 QSS 模板里的占位符名（`$primary` 等），因此模板与色板不会
    各写一套名字。日历的自绘（底色、今天、徽标）也从这里取色，避免深色模式下
    「白底浅字」这种只在截图里才发现的对比度问题。
    """

    background: str
    surface: str
    surface_alt: str
    text: str
    muted: str
    border: str
    primary: str
    primary_hover: str
    primary_pressed: str
    on_primary: str
    hover: str
    #: 表格整行的悬停底色。与 `hover`（按钮上的浅主色调）分开：列表行铺满整行，
    #: 用主色调会整片发蓝，只在指针所在行上"轻轻抬一下"才不影响扫读。
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
    background="#F4F6FA",
    surface="#FFFFFF",
    surface_alt="#F9FAFB",
    text="#1F2937",
    muted="#6B7280",
    border="#E5E7EB",
    primary="#2563EB",
    primary_hover="#1D4ED8",
    primary_pressed="#1E40AF",
    on_primary="#FFFFFF",
    hover="#EFF6FF",
    row_hover="#F3F4F6",
    event_background="#DBEAFE",
    today_accent="#F59E0B",
    today_foreground="#B45309",
    today_background="#FEF3C7",
    badge_background="#2563EB",
    badge_text="#FFFFFF",
    danger="#DC2626",
    on_danger="#FFFFFF",
    danger_soft="#FEE2E2",
)

#: 深色主题：卡片比页面底色亮一档，边框比卡片再亮一档。
DARK_PALETTE: Final = Palette(
    background="#111827",
    surface="#1F2937",
    surface_alt="#182230",
    text="#F9FAFB",
    muted="#9CA3AF",
    border="#374151",
    primary="#60A5FA",
    primary_hover="#93C5FD",
    primary_pressed="#3B82F6",
    on_primary="#0B1220",
    hover="#1E293B",
    row_hover="#243244",
    event_background="#1E3A5F",
    today_accent="#F59E0B",
    today_foreground="#FBBF24",
    today_background="#422006",
    badge_background="#1D4ED8",
    badge_text="#FFFFFF",
    danger="#DC2626",
    on_danger="#FFFFFF",
    danger_soft="#3F1D1D",
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

/* ------------------------------------------------------------ 顶部工具栏 */
QToolBar {
    background-color: $surface;
    border: none;
    border-bottom: 1px solid $border;
    padding: 8px 12px;
    spacing: 6px;
}

QToolBar::separator {
    width: 1px;
    background-color: $border;
    margin: 6px 10px;
}

QToolButton {
    background-color: transparent;
    color: $text;
    border: 1px solid transparent;
    border-radius: 8px;
    padding: 6px 12px;
}

QToolButton:hover {
    background-color: $hover;
    border-color: $border;
}

QToolButton:pressed {
    background-color: $event_background;
}

QToolButton:checked {
    background-color: $event_background;
    color: $primary;
    border-color: $primary;
}

QToolButton:disabled {
    color: $muted;
}

/* 键盘焦点必须看得见：`outline: none` 之后 Tab 过去只剩极细的一圈边框变化，
   纯键盘用户根本找不到自己在哪。焦点环用 2px 主色描边，不动布局。 */
QToolButton:focus {
    border: 2px solid $primary;
    padding: 5px 11px;
}

QToolButton#RowMenu:focus {
    padding: 0;
}

/* 「新增」是这一屏唯一的主要动作：实心主色，其余入口保持次级。
   七个入口如果全是同一种文字按钮，扫一眼分不出"通常点哪个"。 */
QToolButton#PrimaryAction {
    background-color: $primary;
    color: $on_primary;
    font-weight: 600;
}

QToolButton#PrimaryAction:hover {
    background-color: $primary_hover;
    border-color: $primary_hover;
}

QToolButton#PrimaryAction:pressed {
    background-color: $primary_pressed;
}

QToolButton#PrimaryAction:disabled {
    background-color: $border;
    color: $muted;
    border-color: $border;
}

/* 删除是破坏性动作：常态与其它入口同权重（避免整个工具栏冒红），
   悬停时才转红提示"这一个点了会没"。 */
QToolButton#DangerAction:hover {
    color: $danger;
    background-color: $surface;
    border-color: $danger;
}

/* 行内悬停的「⋯」：24x24 的小方块，通用 QToolButton 的 12px 横向内边距会把
   字挤没（宽度直接算成 0），所以这里把 padding 归零，并给它自己的描边。 */
QToolButton#RowMenu {
    background-color: $surface;
    color: $muted;
    border: 1px solid $border;
    border-radius: 6px;
    padding: 0;
    font-size: 15px;
    font-weight: bold;
}

QToolButton#RowMenu:hover {
    background-color: $event_background;
    color: $primary;
    border-color: $primary;
}

QLabel#Brand {
    color: $primary;
    font-size: 17px;
    font-weight: bold;
    padding: 0 6px;
}

QLabel#DayHeading {
    color: $text;
    font-size: 18px;
    font-weight: bold;
    padding: 2px 2px 1px 2px;
}

QLabel#TodayLabel {
    color: $today_foreground;
    font-size: 13px;
    font-weight: bold;
    border-left: 3px solid $today_accent;
    padding: 2px 2px 4px 8px;
}

QLabel#Hint {
    color: $muted;
    font-size: 12px;
}

/* ---------------------------------------------------------------- 卡片 */
QFrame#Card {
    background-color: $surface;
    border: 1px solid $border;
    border-radius: 10px;
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
    border-radius: 8px;
    padding: 4px;
}

QMenu::item {
    background-color: transparent;
    padding: 6px 22px 6px 14px;
    border-radius: 6px;
    min-width: 140px;
}

QMenu::item:selected {
    background-color: $hover;
    color: $primary;
}

QMenu::item:disabled {
    color: $muted;
}

QMenu::separator {
    height: 1px;
    background-color: $border;
    margin: 4px 8px;
}

/* ---------------------------------------------------------------- 表格 */
QTableWidget {
    background-color: $surface;
    color: $text;
    border: 1px solid transparent;
    border-radius: 8px;
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
   靠 40px 行高留白分组；整行悬停底色由 `_RowDelegate` 画——QSS 的
   `::item:hover` 只给鼠标所在的那一个单元格上色，整行会断成两截。 */
QTableWidget::item {
    padding: 0 10px;
    border: none;
}

/* 写在 `:hover` 之后：同一行既被悬停又被选中时，选中的底色说了算。 */
QTableWidget::item:selected {
    background-color: $event_background;
    color: $text;
}

QHeaderView {
    background-color: transparent;
}

QHeaderView::section {
    background-color: $surface_alt;
    color: $muted;
    border: none;
    border-bottom: 1px solid $border;
    padding: 0 10px;
    font-size: 12px;
    font-weight: 500;
}

/* ---------------------------------------------------------------- 日历 */
QCalendarWidget {
    background-color: $surface;
    border: none;
}

QCalendarWidget QWidget#qt_calendar_navigationbar {
    background-color: $surface;
    border: none;
}

QCalendarWidget QToolButton {
    background-color: transparent;
    color: $text;
    border: 1px solid transparent;
    border-radius: 6px;
    padding: 4px 8px;
    font-weight: bold;
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
}

QCalendarWidget QSpinBox {
    background-color: $surface;
    color: $text;
    border: 1px solid $border;
    border-radius: 6px;
    padding: 2px 4px;
}

QCalendarWidget QAbstractItemView:enabled {
    background-color: $surface;
    color: $text;
    selection-background-color: $primary;
    selection-color: $on_primary;
    outline: none;
}

QCalendarWidget QAbstractItemView:disabled {
    color: $muted;
}

/* ------------------------------------------------------------ 按钮与输入 */
QPushButton {
    background-color: $primary;
    color: $on_primary;
    border: 1px solid $primary;
    border-radius: 8px;
    padding: 7px 16px;
    font-weight: bold;
}

QPushButton:hover {
    background-color: $primary_hover;
    border-color: $primary_hover;
}

QPushButton:pressed {
    background-color: $primary_pressed;
    border-color: $primary_pressed;
}

QPushButton:disabled {
    background-color: $surface_alt;
    color: $muted;
    border-color: $border;
}

QPushButton:focus {
    border: 2px solid $primary;
    padding: 6px 15px;
}

QPushButton#TodayButton, QPushButton#PickButton {
    background-color: $surface;
    color: $primary;
    border: 1px solid $border;
    font-weight: normal;
}

QPushButton#TodayButton:hover, QPushButton#PickButton:hover {
    background-color: $hover;
    border-color: $primary;
}

QDialog QPushButton {
    background-color: $surface;
    color: $text;
    border: 1px solid $border;
}

QDialog QPushButton:hover {
    background-color: $hover;
    border-color: $primary;
}

QDialog QPushButton:default {
    background-color: $primary;
    color: $on_primary;
    border-color: $primary;
}

QLineEdit, QTextEdit {
    background-color: $surface;
    color: $text;
    border: 1px solid $border;
    border-radius: 8px;
    padding: 6px 8px;
    selection-background-color: $primary;
    selection-color: $on_primary;
}

QLineEdit:focus, QTextEdit:focus {
    border-color: $primary;
}

/* 标题为空时把边框染红：这是"提示"而不是"拦截"——保存照样会发到后端，
   判定权仍在服务层，这里只是把一定会被拒的情况提前说出来。
   属性选择器写在 `:focus` 之后，避免聚焦时被主色盖掉。 */
QLineEdit[requiredMissing="true"] {
    border-color: $danger;
}

/* 表单顶部的错误条：保存失败时就地显示，取代"弹框 → 关表单 → 重开"那一路。 */
QLabel#FormError {
    background-color: $danger_soft;
    color: $danger;
    border: 1px solid $danger;
    border-radius: 6px;
    padding: 6px 10px;
}

/* 必填标记与字段提示。 */
QLabel#RequiredMark {
    color: $danger;
    font-weight: bold;
}

QLabel#FieldHint {
    color: $muted;
    font-size: 12px;
}

/* ------------------------------------------------------ 搜索与 7 天摘要 */
QLineEdit#SearchInput {
    background-color: $surface_alt;
    color: $text;
    border: 1px solid $border;
    border-radius: 8px;
    padding: 5px 10px;
    selection-background-color: $primary;
    selection-color: $on_primary;
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
    border: 1px solid $border;
    border-radius: 8px;
    padding: 2px 12px;
    font-weight: normal;
}

QPushButton#UndoButton:hover {
    background-color: $hover;
    border-color: $primary;
}

QLabel#SectionTitle {
    color: $muted;
    font-size: 12px;
    font-weight: 500;
    padding: 2px 2px 0 2px;
}

/* ---------------------------------------------- 列表为空时的整页空状态 */
/* 空状态只有三行字，必须靠字号把"这是什么情况 / 我该做什么"分开；
   三者同样大小的时候，看起来像一段没排过版的说明文字。 */
QLabel#EmptyTitle {
    color: $text;
    font-size: 17px;
    font-weight: 600;
}

QLabel#EmptyHint {
    color: $muted;
    font-size: 13px;
}

QPushButton#EmptyAction {
    padding: 7px 18px;
    font-weight: 500;
}

/* 摘要里的分组头（`10-21 周三 · 2 条`）：不可点，只做分隔与计数。 */
QListWidget#UpcomingList::item:disabled {
    color: $muted;
    font-size: 12px;
    font-weight: 500;
    padding-top: 6px;
}

QListWidget#UpcomingList {
    background-color: $surface_alt;
    color: $text;
    border: 1px solid $border;
    border-radius: 8px;
    padding: 4px;
    outline: none;
}

QListWidget#UpcomingList::item {
    padding: 5px 6px;
    border-radius: 6px;
}

QListWidget#UpcomingList::item:hover {
    background-color: $hover;
}

QListWidget#UpcomingList::item:selected {
    background-color: $event_background;
    color: $text;
}

/* ---------------------------------------------------------------- 状态栏 */
QStatusBar {
    background-color: $surface;
    border-top: 1px solid $border;
    color: $muted;
    padding: 2px 18px;
}

QStatusBar QLabel {
    color: $muted;
    font-size: 12px;
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
    "LIGHT_PALETTE",
    "LIGHT_STYLESHEET",
    "Palette",
    "palette",
    "stylesheet",
]
