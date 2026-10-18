"""入口装配的集成测试：默认走 SQLite，首次启动为空库，连接由入口关闭。

不进入 Qt 事件循环：把 `app.QApplication` 换成立即以 0 退出的子类，
窗口仍会真实创建（offscreen），从而覆盖 `connect -> build_service -> close`
这条完整接线。
"""

from __future__ import annotations

import os
import sqlite3
from datetime import date
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from schedule_management import composition
from schedule_management.ui import app

DAY = date(2026, 10, 15)


class _ImmediateExitApplication(QApplication):
    """真实 QApplication 的子类，`exec()` 不阻塞。"""

    @staticmethod
    def exec() -> int:
        return 0


def test_main_uses_sqlite_and_closes_connection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "schedules.db"
    opened: list[sqlite3.Connection] = []
    real_connect = composition.connect

    def tracking_connect(path: Path | None = None) -> sqlite3.Connection:
        connection = real_connect(path)
        opened.append(connection)
        return connection

    monkeypatch.setattr(composition, "connect", tracking_connect)
    monkeypatch.setattr(app, "QApplication", _ImmediateExitApplication)

    rc = app.main(argv=[], seed_demo_data=False, db_path=db_path, clock=lambda: DAY)

    assert rc == 0
    assert db_path.exists()
    assert len(opened) == 1

    # 入口在 finally 里关闭了连接：对已关闭连接执行语句会抛 ProgrammingError。
    with pytest.raises(sqlite3.ProgrammingError):
        opened[0].execute("SELECT 1")

    # 新连接能再次打开，schedules 表存在且开箱为空（不是演示数据）。
    reopened = sqlite3.connect(db_path)
    try:
        rows = reopened.execute("SELECT COUNT(*) FROM schedules").fetchall()
    finally:
        reopened.close()
    assert rows == [(0,)]
