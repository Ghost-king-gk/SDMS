"""离屏生成 Apple 风主题截图：固定 today=2026-10-20，浅色 / 深色各一张。

用法：

    QT_QPA_PLATFORM=offscreen uv run python scripts/shoot_apple_theme.py

只用于 Linux 容器里的视觉复核：容器装有 Noto Sans CJK，中文不会变成方块。
它**不能替代** Windows 真机验收（SF Pro / Segoe UI 的实际字形、DPI 缩放与
原生滚动条仍要人工看）。

数据刻意覆盖：今天 4 条（含一条全天）、前一天 1 条、后两天各 2 条。这样一张图
能同时看到日历徽标、今天标记、列表的四列与列分隔线，以及「接下来 7 天」摘要。

脚本同时做布局自检：1080x720 与 960x640 两种尺寸下，表头四列标题非空、
最小段宽不小于 88、任何列都不会被拖到下限以下；失败时直接退出，不生成坏图。
"""

from __future__ import annotations

import datetime as dt
import sys
import tempfile
from pathlib import Path

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from schedule_management.dev_stub_service import DevStubScheduleService
from schedule_management.ui import theme
from schedule_management.ui.main_window import _MIN_COLUMN_WIDTH, MainWindow

TODAY = dt.date(2026, 10, 20)
OUTPUT_DIR = Path(__file__).resolve().parents[1] / "docs" / "screenshots"

#: (相对今天的天数, 时间文本, 标题, 备注)；时间留空表示全天。
_SEED: tuple[tuple[int, str, str, str], ...] = (
    (0, "09:30", "产品设计评审", "带上新版交互稿与走查清单"),
    (0, "", "整理本周课程笔记", "全天安排，不限具体时刻"),
    (0, "14:00", "数据结构习题课", "第 6 章：图与最短路径"),
    (0, "18:30", "小组周会", "对齐下周分工与提交时间"),
    (-1, "10:00", "数据库实验", "索引与查询计划"),
    (1, "08:00", "晨跑 5 公里", "滨江绿道，配速 6'00\""),
    (1, "", "提交课程设计初稿", ""),
    (2, "16:00", "导师答疑", "提前准备三个问题"),
    (3, "19:00", "英语角", "主题：校园生活"),
)


def _seed_service() -> DevStubScheduleService:
    service = DevStubScheduleService()
    for offset, time_text, title, notes in _SEED:
        service.create_schedule(
            title, (TODAY + dt.timedelta(days=offset)).isoformat(), time_text, notes
        )
    return service


def _settle(app: QApplication, rounds: int = 6) -> None:
    for _ in range(rounds):
        app.processEvents()


def _check(condition: bool, message: str) -> None:
    """截图脚本也要自检：布局退化时先让脚本红，而不是生成一张坏图。"""
    if not condition:
        raise SystemExit(f"布局自检失败：{message}")


def _columns(window: MainWindow) -> list[int]:
    header = window._table.horizontalHeader()
    return [c for c in range(window._table.columnCount()) if not header.isSectionHidden(c)]


def _check_layout(window: MainWindow, label: str) -> None:
    """两种尺寸共用的断言：表头不消失、列宽不低于下限。"""
    header = window._table.horizontalHeader()
    titles = [
        window._table.horizontalHeaderItem(column).text()
        for column in range(window._table.columnCount())
    ]
    _check(all(titles), f"{label}：表头文字为空 {titles}")
    _check(
        header.minimumSectionSize() >= _MIN_COLUMN_WIDTH,
        f"{label}：minimumSectionSize={header.minimumSectionSize()} 小于 {_MIN_COLUMN_WIDTH}",
    )
    _check(header.height() > 0, f"{label}：表头高度为 0")
    _check(
        header.height() >= header.fontMetrics().height(),
        f"{label}：表头高度 {header.height()} 放不下一行字",
    )
    for column in _columns(window):
        width = window._table.columnWidth(column)
        _check(
            width >= _MIN_COLUMN_WIDTH,
            f"{label}：第 {column} 列宽 {width} 小于 {_MIN_COLUMN_WIDTH}",
        )
        text = titles[column]
        needed = header.fontMetrics().horizontalAdvance(text) + 24
        _check(
            width >= needed,
            f"{label}：第 {column} 列「{text}」需要 {needed}px，实际只有 {width}px",
        )
    _check(
        window._calendar.width() >= 320,
        f"{label}：日历被压到 {window._calendar.width()}px",
    )
    _check(
        window._table.viewport().width() > 0,
        f"{label}：表格视口宽度为 {window._table.viewport().width()}",
    )


def _check_separators(window: MainWindow, label: str) -> None:
    """抓表头与首行像素，确认列分隔线真的画出来了、颜色来自当前色板。"""
    header = window._table.horizontalHeader()
    expected = theme.palette(window._dark).separator.lower()
    header_image = header.grab().toImage()
    row_image = window._table.viewport().grab().toImage()
    first_row_y = window._table.rowViewportPosition(0) + window._table.rowHeight(0) // 2
    columns = _columns(window)
    for column in columns[:-1]:
        boundary_x = header.sectionViewportPosition(column) + header.sectionSize(column) - 1
        header_pixel = header_image.pixelColor(boundary_x, header.height() // 2).name()
        row_pixel = row_image.pixelColor(boundary_x, first_row_y).name()
        _check(header_pixel == expected, f"{label}：表头第 {column} 列右侧没有分隔线")
        _check(row_pixel == expected, f"{label}：首行第 {column} 列右侧没有分隔线")
    last = columns[-1]
    right_edge = header.sectionViewportPosition(last) + header.sectionSize(last) - 1
    _check(
        header_image.pixelColor(right_edge, header.height() // 2).name() != expected,
        f"{label}：最后一列右侧不该再画分隔线",
    )


def _save(window: MainWindow, name: str) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / name
    if not window.grab().save(str(path)):
        raise SystemExit(f"截图保存失败：{path}")
    return path


def _report(window: MainWindow, label: str) -> None:
    header = window._table.horizontalHeader()
    widths = {column: window._table.columnWidth(column) for column in _columns(window)}
    print(
        f"{label}：窗口 {window.width()}x{window.height()}，表格视口 "
        f"{window._table.viewport().width()}x{window._table.viewport().height()}，"
        f"日历 {window._calendar.width()}x{window._calendar.height()}，"
        f"表头 {header.height()}px 最小段宽 {header.minimumSectionSize()}px"
    )
    print(f"{label}：可见列宽 {widths}")


def main() -> int:
    app = QApplication(sys.argv)
    # 与其它截图脚本一样把 QSettings 落到临时 INI：不隔离就会改写跑脚本的人
    # 真机上的主题、窗口几何与列宽。
    settings_root = Path(tempfile.gettempdir()) / "sdms-shoot-qsettings"
    settings_root.mkdir(parents=True, exist_ok=True)
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(settings_root))
    QSettings("SDMS", "SDMS").clear()

    window = MainWindow(service=_seed_service(), clock=lambda: TODAY)
    window.show()
    _settle(app)

    # 选中第二条，让截图里同时有选中底色与左侧主色竖条；悬停放在第三行，
    # 这样能看出整行悬停与选中不是同一种信号。
    window._table.selectRow(1)
    window._row_delegate.set_hover_row(2)
    window._table.viewport().update()
    _settle(app)

    window._on_dark_toggled(False)
    _settle(app)
    _check_layout(window, "1080x720 浅色")
    _check_separators(window, "1080x720 浅色")
    _report(window, "1080x720 浅色")
    light = _save(window, "apple-light-2026-10-20.png")

    window._on_dark_toggled(True)
    _settle(app)
    _check_layout(window, "1080x720 深色")
    _check_separators(window, "1080x720 深色")
    _report(window, "1080x720 深色")
    dark = _save(window, "apple-dark-2026-10-20.png")

    # 最小窗口：960x640。表头与列宽都要原样成立；截图写到临时目录供人看，
    # 不作为交付素材（交付图固定 1080x720）。
    window._on_dark_toggled(False)
    window.resize(960, 640)
    _settle(app)
    _check_layout(window, "960x640 浅色")
    _check_separators(window, "960x640 浅色")
    _report(window, "960x640 浅色")
    small = _save(window, "apple-light-960x640-preview.png")
    small.unlink()

    # 把四列都往 0 拖一遍，验证 sectionResized 的兜底（Qt 对 0 有特例）。
    for column in _columns(window):
        window._table.setColumnWidth(column, 0)
    _settle(app)
    _check_layout(window, "960x640 拖到 0 之后")
    for column in _columns(window):
        width = window._table.columnWidth(column)
        _check(
            width >= _MIN_COLUMN_WIDTH,
            f"拖到 0 之后第 {column} 列仍只有 {width}px",
        )

    print(f"浅色截图：{light}")
    print(f"深色截图：{dark}")
    print(f"960x640 预览（已删除）：{small}")
    print(f"分隔线色：浅色 {theme.LIGHT_PALETTE.separator} / 深色 {theme.DARK_PALETTE.separator}")

    window.close()
    return 0


__all__ = ["main"]


if __name__ == "__main__":
    raise SystemExit(main())
