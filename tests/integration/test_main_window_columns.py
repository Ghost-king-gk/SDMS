"""列分隔线与最小列宽的窗口级守卫。

这些问题只有把真控件建出来、真的抓一次像素才看得见：

- 表头与数据行之间有没有那条 1px 竖线（QSS 写了不等于画得出来）；
- 把列宽设成 1 或 0 时，表头文字会不会被挤没；
- 窗口缩到 960x640 时，四列是否还放得下、会不会出现横向滚动。

运行在 offscreen 平台；断言的是控件几何与渲染出的颜色，不依赖桌面环境。
"""

from __future__ import annotations

import datetime as dt
import os
from collections.abc import Iterator

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from schedule_management.ui import theme
from schedule_management.ui.main_window import _MIN_COLUMN_WIDTH, MainWindow
from tests.unit.ui_fakes import FakeScheduleService, StubSchedule

TODAY = dt.date(2026, 10, 20)


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    app = QApplication.instance()
    if not isinstance(app, QApplication):
        app = QApplication([])
    yield app


def build_window(width: int = 1080, height: int = 720) -> MainWindow:
    service = FakeScheduleService(
        (
            StubSchedule(id="a", title="产品设计评审", date=TODAY, time=dt.time(9, 30)),
            StubSchedule(id="b", title="整理课程笔记", date=TODAY, time=None),
            StubSchedule(id="c", title="小组周会", date=TODAY, time=dt.time(18, 30)),
        )
    )
    window = MainWindow(service=service, clock=lambda: TODAY)
    window.resize(width, height)
    window.show()
    QApplication.processEvents()
    return window


def header_text(window: MainWindow, column: int) -> str:
    item = window._table.horizontalHeaderItem(column)
    assert item is not None, f"第 {column} 列没有表头"
    return item.text()


def visible_columns(window: MainWindow) -> list[int]:
    header = window._table.horizontalHeader()
    return [
        column
        for column in range(window._table.columnCount())
        if not header.isSectionHidden(column)
    ]


def test_header_declares_the_minimum_and_keeps_all_four_titles(qapp: QApplication) -> None:
    """最小段宽必须真的设到表头上；四个表头标题一个都不能少。"""
    window = build_window()
    try:
        header = window._table.horizontalHeader()
        assert header.minimumSectionSize() >= _MIN_COLUMN_WIDTH
        assert _MIN_COLUMN_WIDTH >= 88, "下限低于 88 时表头文字仍可能被挤掉"

        titles = [header_text(window, column) for column in range(window._table.columnCount())]
        assert titles == ["日期", "时间", "标题", "备注"]
        assert all(title.strip() for title in titles)
        assert header.height() >= header.fontMetrics().height()
    finally:
        window.close()


def test_dragging_a_column_to_one_or_zero_is_clamped(qapp: QApplication) -> None:
    """Qt 会把 1px 夹到 minimumSectionSize，但 `setColumnWidth(col, 0)` 是特例。

    两种写法都要被 `_on_section_resized()` 兜住，否则列宽归零之后表头文字与
    拖拽把手一起消失，用户没有入口把它拖回来。
    """
    window = build_window()
    try:
        header = window._table.horizontalHeader()
        for column in visible_columns(window):
            window._table.setColumnWidth(column, 1)
            QApplication.processEvents()
            assert window._table.columnWidth(column) >= _MIN_COLUMN_WIDTH

            window._table.setColumnWidth(column, 0)
            QApplication.processEvents()
            assert window._table.columnWidth(column) >= _MIN_COLUMN_WIDTH

        # 保护逻辑不能把"日期列收起"误判成 0 宽：收起后紧跟的列必须从 0 开始。
        window._sync_date_column(False)
        QApplication.processEvents()
        assert header.isSectionHidden(0)
        assert header.sectionViewportPosition(1) == 0, "隐藏的日期列仍在占宽度"
    finally:
        window.close()


def test_960x640_keeps_header_and_all_columns_visible(qapp: QApplication) -> None:
    """最小窗口尺寸下：表头不消失、列宽不低于下限、单日视图没有横向滚动。"""
    window = build_window(960, 640)
    try:
        header = window._table.horizontalHeader()
        assert header.height() > 0
        assert window._table.viewport().width() > 0
        assert window._calendar.width() >= 320

        for column in visible_columns(window):
            width = window._table.columnWidth(column)
            assert width >= _MIN_COLUMN_WIDTH, f"第 {column} 列被压到 {width}px"
            text = header_text(window, column)
            assert width >= header.fontMetrics().horizontalAdvance(text) + 24

        assert header.minimumSectionSize() >= _MIN_COLUMN_WIDTH
        assert header.length() <= window._table.viewport().width() + 1, "出现横向滚动"
    finally:
        window.close()


def test_restoring_a_corrupt_column_width_still_clamps(qapp: QApplication) -> None:
    """旧版本可能存过 0 或二三十像素的列宽；恢复时必须夹回下限。"""
    settings = QSettings("SDMS", "SDMS")
    settings.setValue("ui/columns", [1, 0, 20, 0])
    settings.sync()

    window = build_window()
    try:
        # 单日视图默认收起日期列；先切到搜索态让四列都参与布局，
        # 才能同时验证被恢复的第 0 列。
        window._sync_date_column(True)
        QApplication.processEvents()
        for column in (0, 1, 2):
            assert window._table.columnWidth(column) >= _MIN_COLUMN_WIDTH
    finally:
        window.close()


@pytest.mark.parametrize("dark", [False, True])
def test_separator_lines_are_actually_rendered(qapp: QApplication, dark: bool) -> None:
    """抓表头与第一行，确认两条 1px 分隔线真的画成了 separator 色。

    只检查 QSS 文本不够：`QHeaderView::section` 的 `border-right` 与
    `_RowDelegate` 的 `fillRect` 是两条独立路径，哪一条没生效都只会在截图里
    表现为"列边界不见了"。
    """
    window = build_window()
    try:
        window._on_dark_toggled(dark)
        QApplication.processEvents()
        expected = theme.palette(dark).separator
        header = window._table.horizontalHeader()

        header_image = header.grab().toImage()
        row_image = window._table.viewport().grab().toImage()
        first_row_y = window._table.rowViewportPosition(0) + window._table.rowHeight(0) // 2

        for column in visible_columns(window)[:-1]:
            boundary_x = header.sectionViewportPosition(column) + header.sectionSize(column) - 1
            header_pixel = header_image.pixelColor(boundary_x, header.height() // 2)
            row_pixel = row_image.pixelColor(boundary_x, first_row_y)
            assert header_pixel.name() == expected.lower()
            assert row_pixel.name() == expected.lower()

        # 最后一列右侧不该再多一条线：表格自身的圆角描边已经在那儿了。
        last = visible_columns(window)[-1]
        right_edge = header.sectionViewportPosition(last) + header.sectionSize(last) - 1
        assert header_image.pixelColor(right_edge, header.height() // 2).name() != expected.lower()
    finally:
        window.close()
