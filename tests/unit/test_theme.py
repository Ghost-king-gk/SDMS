"""主题模块的单测：QSS 文本与色板都是纯数据，可以脱离 Qt 直接断言。

这里不创建 `QApplication`，也不解析 QSS——Qt 对样式表的真实解析由窗口冒烟
脚本覆盖（`tests/integration/test_app_entrypoint.py` 会真的建窗）。本组测试
守的是两条容易悄悄漂移的事：

- 需求里写死的色值必须真的落进对应主题，不能被"大概差不多的蓝"替换；
- 两套主题的占位符必须全部替换干净，模板里出现一个漏填的 `$token`
  会在 Qt 那边变成一条解析警告，而不是这里失败。
"""

from __future__ import annotations

import pytest

from schedule_management.ui import theme

_SELECTORS = (
    "QToolBar",
    "QToolButton",
    "QFrame#Card",
    "QLabel#Brand",
    "QLabel#DayHeading",
    "QLabel#TodayLabel",
    "QLabel#Hint",
    "QLabel#SectionTitle",
    "QLineEdit#SearchInput",
    "QPushButton#ClearSearch",
    "QPushButton#UndoButton",
    "QListWidget#UpcomingList",
    "QTableWidget",
    "QHeaderView",
    "QCalendarWidget",
    "QMenu",
    "QStatusBar",
    "QPushButton",
    "QDialog",
)


def test_stylesheet_switches_with_the_flag() -> None:
    assert theme.stylesheet(False) is theme.LIGHT_STYLESHEET
    assert theme.stylesheet(True) is theme.DARK_STYLESHEET
    assert theme.LIGHT_STYLESHEET != theme.DARK_STYLESHEET


def test_palette_switches_with_the_flag() -> None:
    assert theme.palette(False) is theme.LIGHT_PALETTE
    assert theme.palette(True) is theme.DARK_PALETTE


@pytest.mark.parametrize("dark", [False, True])
@pytest.mark.parametrize("selector", _SELECTORS)
def test_stylesheet_covers_required_selectors(dark: bool, selector: str) -> None:
    assert selector in theme.stylesheet(dark), f"{selector} 缺少样式，界面会退回系统默认外观"


@pytest.mark.parametrize("dark", [False, True])
def test_stylesheet_has_no_unfilled_placeholder(dark: bool) -> None:
    """`$` 在 QSS 里没有别的含义；出现即说明模板与色板对不上。"""
    assert "$" not in theme.stylesheet(dark)


def test_light_palette_matches_the_agreed_colors() -> None:
    colors = theme.LIGHT_PALETTE

    assert colors.background == "#F4F6FA"
    assert colors.surface == "#FFFFFF"
    assert colors.primary == "#2563EB"
    assert colors.text == "#1F2937"
    assert colors.muted == "#6B7280"
    assert colors.border == "#E5E7EB"
    assert colors.event_background == "#DBEAFE"
    assert colors.today_accent == "#F59E0B"
    assert colors.today_foreground == "#B45309"


def test_dark_palette_matches_the_agreed_colors() -> None:
    colors = theme.DARK_PALETTE

    assert colors.background == "#111827"
    assert colors.surface == "#1F2937"
    assert colors.primary == "#60A5FA"
    assert colors.text == "#F9FAFB"
    assert colors.muted == "#9CA3AF"
    assert colors.border == "#374151"


@pytest.mark.parametrize("dark", [False, True])
def test_stylesheet_avoids_effects_qt_does_not_render(dark: bool) -> None:
    """QSS 不支持渐变与盒阴影；写进去只会得到解析警告或一条脏边。"""
    stylesheet = theme.stylesheet(dark).lower()

    assert "qlineargradient" not in stylesheet
    assert "box-shadow" not in stylesheet
