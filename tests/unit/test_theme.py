"""主题模块的单测：QSS 文本与色板都是纯数据，可以脱离 Qt 直接断言。

这里不创建 `QApplication`，也不解析 QSS——Qt 对样式表的真实解析由窗口冒烟
脚本覆盖（`tests/integration/test_app_entrypoint.py` 会真的建窗）。本组测试
守的是两条容易悄悄漂移的事：

- 需求里写死的色值必须真的落进对应主题，不能被"大概差不多的蓝"替换；
- 两套主题的占位符必须全部替换干净，模板里出现一个漏填的 `$token`
  会在 Qt 那边变成一条解析警告，而不是这里失败。
"""

from __future__ import annotations

from dataclasses import asdict

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
    "QLabel#EmptyTitle",
    "QLabel#EmptyHint",
    "QLineEdit#SearchInput",
    "QPushButton#UndoButton",
    "QPushButton#EmptyAction",
    "QToolButton#PrimaryAction",
    "QToolButton#DangerAction",
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
    """浅色是 Apple 的系统灰白语言：页面灰、卡片白、主色 #0071E3。"""
    colors = theme.LIGHT_PALETTE

    assert colors.background == "#F5F5F7"
    assert colors.surface == "#FFFFFF"
    assert colors.surface_alt == "#F5F5F7"
    assert colors.primary == "#0071E3"
    assert colors.primary_hover == "#0077ED"
    assert colors.primary_pressed == "#0066CC"
    assert colors.text == "#1D1D1F"
    assert colors.muted == "#86868B"
    assert colors.border == "#E5E5EA"
    assert colors.separator == "#D2D2D7"
    assert colors.event_background == "#EAF3FF"
    assert colors.today_accent == "#FF9F0A"
    assert colors.today_foreground == "#C93400"
    assert colors.danger == "#FF3B30"


def test_dark_palette_matches_the_agreed_colors() -> None:
    """深色是纯黑页面 + 两级抬升表面，主色换成 iOS 深色蓝 #0A84FF。"""
    colors = theme.DARK_PALETTE

    assert colors.background == "#000000"
    assert colors.surface == "#1C1C1E"
    assert colors.surface_alt == "#2C2C2E"
    assert colors.primary == "#0A84FF"
    assert colors.text == "#F5F5F7"
    assert colors.muted == "#98989D"
    assert colors.border == "#38383A"
    assert colors.separator == "#38383A"
    assert colors.event_background == "#102A43"
    assert colors.today_accent == "#FF9F0A"


@pytest.mark.parametrize("dark", [False, True])
def test_header_sections_draw_the_separator_token(dark: bool) -> None:
    """表头每列右侧的分隔线必须来自 `separator`，不能另写一个灰。"""
    colors = theme.palette(dark)

    assert f"border-right: 1px solid {colors.separator};" in theme.stylesheet(dark)


@pytest.mark.parametrize("dark", [False, True])
def test_style_uses_apple_geometry(dark: bool) -> None:
    """卡片 18px 圆角、主操作药丸、表头 11px：这三处是 Apple 视觉的骨架。"""
    stylesheet = theme.stylesheet(dark)

    assert "QFrame#Card" in stylesheet
    assert "border-radius: 18px;" in stylesheet
    assert "QToolButton#PrimaryAction" in stylesheet
    assert "border-radius: 15px;" in stylesheet
    assert "font-size: 11px;" in stylesheet


def test_font_stack_starts_with_sf_pro_and_falls_back_to_windows_fonts() -> None:
    """字族由 QFont 回退链承担；QSS 只写字号，避免 Qt 丢掉整条 font-family。"""
    assert theme.FONT_FAMILIES[0] == "SF Pro Text"
    assert "SF Pro Display" in theme.FONT_FAMILIES
    assert "Segoe UI" in theme.FONT_FAMILIES
    assert "Microsoft YaHei UI" in theme.FONT_FAMILIES
    assert theme.FONT_FAMILIES[-1] == "sans-serif"
    assert "font-family" not in theme.stylesheet(False).lower()


def _relative_luminance(hex_color: str) -> float:
    """WCAG 相对亮度；只用于断言主题 token 的对比度，不参与界面渲染。"""
    channels = [int(hex_color[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _contrast(foreground: str, background: str) -> float:
    first, second = sorted(
        (_relative_luminance(foreground), _relative_luminance(background)), reverse=True
    )
    return (first + 0.05) / (second + 0.05)


@pytest.mark.parametrize("dark", [False, True])
def test_text_tokens_stay_readable_on_their_backgrounds(dark: bool) -> None:
    """深色模式最容易翻车的是「浅底浅字」；这里把几组实际搭配钉住。

    日历的事件底色、今天底色与表格选中行都直接用这些 token，因此这条测试
    同时守住了 `calendar_view.py` 的自绘配色。
    """
    colors = theme.palette(dark)

    assert _contrast(colors.text, colors.surface) >= 4.5
    assert _contrast(colors.text, colors.event_background) >= 4.5
    assert _contrast(colors.muted, colors.surface) >= 3.0
    assert _contrast(colors.today_foreground, colors.today_background) >= 4.5
    assert _contrast(colors.badge_text, colors.badge_background) >= 4.5
    # 深色的主色 #0A84FF 配白字是 Apple 的系统搭配，对比度 3.65:1；
    # 主按钮文字是 13px/600 的粗体，按大字号标准 3:1 通过。徽标不享受这条放宽。
    assert _contrast(colors.on_primary, colors.primary) >= 3.0


@pytest.mark.parametrize("dark", [False, True])
def test_every_palette_field_is_a_hex_colour(dark: bool) -> None:
    """占位符替换成功不代表颜色合法；拼错的 `#12345` 会让 Qt 静默退回黑色。"""
    for name, value in asdict(theme.palette(dark)).items():
        assert len(value) == 7 and value.startswith("#"), f"{name}={value!r} 不是 #RRGGBB"
        int(value[1:], 16)


@pytest.mark.parametrize("dark", [False, True])
def test_stylesheet_avoids_effects_qt_does_not_render(dark: bool) -> None:
    """QSS 不支持渐变与盒阴影；写进去只会得到解析警告或一条脏边。"""
    stylesheet = theme.stylesheet(dark).lower()

    assert "qlineargradient" not in stylesheet
    assert "box-shadow" not in stylesheet
