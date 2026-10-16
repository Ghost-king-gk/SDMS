"""跑一遍真实窗口：产出截图，并把 V 清单里能断言的部分断言掉。

用法（**在有桌面的 Windows 上直接跑，不要设 `QT_QPA_PLATFORM=offscreen`**）：

    uv run python scripts/shoot_ui.py

为什么不加 offscreen：离屏平台在这台机器上 `QFontDatabase.families()` 返回 0 个
字体，抓出来的中文全是方块——图能生成，但作为文档素材是废的。所以这个脚本
**只用于本地出图**，不进 CI；自动化断言那部分（能离线跑）已经落在
`tests/unit/` 与 `scripts/qt_probe.py` 里。

为什么需要这个脚本而不是纯手工验收：

- 手工验收一次容易，**重复一次很难**，而改完界面要重验正是常态；
- 界面改动之后能立刻知道"有没有把哪一屏搞坏"，而不是等到答辩前；
- 截图是设计文档与 PPT 的素材来源，一次生成，多处复用。

它只覆盖**不需要人眼判断**的部分。V-07 的"灰显好不好看"、主窗口有没有
文字截断这类，仍然要人打开看一眼——脚本能做的是把那一屏稳定地抓出来。
"""

from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from schedule_management.dev_stub_service import DevStubScheduleService
from schedule_management.ui.main_window import MainWindow
from schedule_management.ui.schedule_form import ScheduleForm
from schedule_management.ui.view_models import FormRequest, ScheduleDraft

TODAY = dt.date(2026, 10, 15)
OUTPUT_DIR = Path(__file__).resolve().parents[1] / "docs" / "screenshots"

_checks: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    _checks.append((name, bool(ok), detail))


def save(pixmap: object, filename: str) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / filename
    pixmap.save(str(path))  # type: ignore[attr-defined]
    return path


def main() -> int:
    """跑一遍全部场景；返回失败条数。"""
    app = QApplication(sys.argv)

    service = DevStubScheduleService()
    service.seed_defaults(TODAY)
    window = MainWindow(service=service, clock=lambda: TODAY)
    window.show()
    app.processEvents()

    # V-01 启动显示当天，列表与工具栏齐全
    check(
        "V-01 启动显示当天日程",
        window._table.rowCount() == 3,
        f"表格行数={window._table.rowCount()}",
    )
    check("V-01 顶部工具栏六个按钮", len(window._actions) == 6, str(list(window._actions)))
    save(window.grab(), "main-window.png")

    # V-05 选中一行，选中文案跟着变
    window._table.selectRow(0)
    app.processEvents()
    selection = window._selection_label.text()
    check(
        "V-05 选中行后同步选中文案",
        selection.startswith("已选中：08:30"),
        selection,
    )
    save(window.grab(), "main-window-selected.png")

    # 刷新按钮走真实路径
    window._actions["refresh"].trigger()
    app.processEvents()
    status = window._status_label.text()
    check("刷新按钮更新状态栏", status.startswith("已刷新"), status)

    # V-06 空状态：切到没有日程的日期
    empty_day = dt.date(2026, 10, 20)
    window._on_day_picked(empty_day)
    app.processEvents()
    first_cell = window._table.item(0, 0)
    check(
        "V-06 空日期显示空状态而不是白板",
        first_cell is not None and "还没有日程" in first_cell.text(),
        first_cell.text() if first_cell else "<空格子>",
    )
    check("V-06 空状态显示共 0 条", "共 0 条" in window._day_label.text(), window._day_label.text())
    save(window.grab(), "empty-state.png")

    # V-07 闰年：定位到 2028-02 抓一屏，供人眼确认
    leap_day = dt.date(2028, 2, 1)
    window._on_day_picked(leap_day)
    app.processEvents()
    leap_exists = True
    try:
        dt.date(2028, 2, 29)
    except ValueError:
        leap_exists = False
    check("V-07 2028-02-29 是可构造的日期", leap_exists)
    save(window.grab(), "calendar-leap-2028-02.png")

    # V-16 界面不拦日期写法：写完原样交出去
    request = FormRequest(
        mode="create",
        heading="新增日程",
        initial=ScheduleDraft(title="测试标题", date_text="明天", time_text="10:00", notes=""),
    )
    form = ScheduleForm(request)
    form.show()
    app.processEvents()
    draft = form.draft()
    check(
        "V-16 无法识别的日期原样离开表单（界面不拦）",
        draft.date_text == "明天" and draft.title == "测试标题",
        f"date_text={draft.date_text!r}",
    )
    save(form.grab(), "form-dialog.png")

    # 退出 clean
    window.close()
    app.processEvents()

    print(f"截图目录：{OUTPUT_DIR}")
    failed = 0
    for name, ok, detail in _checks:
        mark = "PASS" if ok else "FAIL"
        suffix = f"  ({detail})" if detail else ""
        print(f"[{mark}] {name}{suffix}")
        if not ok:
            failed += 1
    print(f"\n合计 {len(_checks)} 项，失败 {failed} 项")
    return failed


__all__ = ["main"]


if __name__ == "__main__":
    raise SystemExit(main())
