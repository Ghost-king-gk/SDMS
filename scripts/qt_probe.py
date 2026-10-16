"""PySide6 与 Qt 环境探测脚本（**不是业务代码**，只是取证工具）。

用途：在目标机器上验证 GUI 选型真的可用，并把取到的版本号、体积、控件行为
写进设计文档与 `docs/figures/ui-interaction.md` 第 8.2 节。

为什么需要它：
- 「装不上」「打不开窗口」这类环境问题的排查成本很高，早一步把它验掉，
  后面的界面开发与验收才有地基；
- V-17 的实测结果要落到设计文档里，跑同一份脚本才能保证别人复现的是同一件事；
- 第 6 节的验收记录要写明 PySide6 与 Qt 版本，版本号必须是实测的，不是抄 PyPI 的。

跑法（不污染项目虚拟环境，用 uv 的临时环境）：

    uv run --python 3.12 --with PySide6 python scripts/qt_probe.py

目标平台是 Windows（GUI 适配只做这一端，见 ui-interaction.md 第 11 节）。
若日后要在无显示服务的环境里跑这份脚本，前置 `QT_QPA_PLATFORM=offscreen`
即可——但那属于扩展情形，不在当前验收范围内。

退出码为 0 且最后一行输出 `ALL QT PROBES OK` 才算通过。
"""

from __future__ import annotations

import calendar
import pathlib

import PySide6
import PySide6.QtCore as QtCore
import PySide6.QtWidgets as QtWidgets


def report_package_size(package_root: pathlib.Path) -> float:
    """统计包目录实际占用的字节数换算成 MB（rglob 递归，跳过读不到的文件）。"""
    total = 0
    for path in package_root.rglob("*"):
        if path.is_file():
            try:
                total += path.stat().st_size
            except OSError:
                continue
    return round(total / 1024 / 1024, 1)


def probe_calendar() -> tuple[bool, int, str]:
    """验证日历三件事：周起始可改为周一、闰年可选到 2 月 29 日、QDate 回读正常。"""
    widget = QtWidgets.QCalendarWidget()
    widget.setFirstDayOfWeek(QtCore.Qt.Monday)
    week_starts_monday = widget.firstDayOfWeek() == QtCore.Qt.Monday

    leap_year, leap_month = 2028, 2
    days_in_month = calendar.monthrange(leap_year, leap_month)[1]
    widget.setSelectedDate(QtCore.QDate(leap_year, leap_month, days_in_month))
    selected = widget.selectedDate().toString("yyyy-MM-dd")

    print("week starts Monday:", week_starts_monday, "| enum:", widget.firstDayOfWeek())
    print(f"leap {leap_year}-{leap_month:02d} days:", days_in_month, "| selected:", selected)
    return week_starts_monday, days_in_month, selected


def probe_widgets() -> tuple[int, str, str]:
    """验证列表是三列、日期框能装自由文本，并顺带记录 QDateEdit 的显示格式。"""
    table = QtWidgets.QTableWidget(0, 3)
    table.setHorizontalHeaderLabels(["时间", "标题", "备注"])

    line_edit = QtWidgets.QLineEdit()
    line_edit.setText("2026/10/15")

    date_edit = QtWidgets.QDateEdit()
    date_edit.setCalendarPopup(True)
    date_edit.setDisplayFormat("yyyy-MM-dd")

    print("QTableWidget cols:", table.columnCount())
    print("QLineEdit accepts free text:", line_edit.text())
    print("QDateEdit display format:", date_edit.displayFormat())
    return table.columnCount(), line_edit.text(), date_edit.displayFormat()


def main() -> None:
    print("PySide6:", PySide6.__version__)
    print("Qt runtime:", QtCore.qVersion())
    package_root = pathlib.Path(PySide6.__file__).parent
    print("module path:", package_root)
    print("PySide6 dir size MB:", report_package_size(package_root))

    # QApplication 必须存在才能创建控件；这里是脚本，不是被 import 的模块，
    # 所以写在 main() 里是安全的（对应 ui-interaction.md 第 7 节那条约束）。
    QtWidgets.QApplication([])

    probe_calendar()
    probe_widgets()
    print("ALL QT PROBES OK")


if __name__ == "__main__":
    main()
