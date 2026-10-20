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
    event_background: str
    today_accent: str
    today_foreground: str
    today_background: str
    badge_background: str
    badge_text: str


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
    event_background="#DBEAFE",
    today_accent="#F59E0B",
    today_foreground="#B45309",
    today_background="#FEF3C7",
    badge_background="#2563EB",
    badge_text="#FFFFFF",
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
    event_background="#1E3A5F",
    today_accent="#F59E0B",
    today_foreground="#FBBF24",
    today_background="#422006",
    badge_background="#1D4ED8",
    badge_text="#FFFFFF",
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

/* ---------------------------------------------------------------- 表格 */
QTableWidget {
    background-color: $surface;
    alternate-background-color: $surface_alt;
    color: $text;
    border: none;
    gridline-color: $border;
    selection-background-color: $event_background;
    selection-color: $text;
}

QTableWidget::item {
    padding: 0 10px;
    border-bottom: 1px solid $border;
}

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
    font-weight: bold;
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

/* ---------------------------------------------------------------- 状态栏 */
QStatusBar {
    background-color: $surface;
    border-top: 1px solid $border;
    color: $muted;
    padding: 2px 18px;
}

QStatusBar QLabel {
    color: $muted;
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
