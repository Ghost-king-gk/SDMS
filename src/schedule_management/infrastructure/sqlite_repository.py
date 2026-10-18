"""SQLite 日程存储适配器。"""

import sqlite3
from datetime import date, time

from schedule_management.application.errors import DuplicateScheduleError, StorageError
from schedule_management.domain.errors import ValidationError
from schedule_management.domain.schedule import Schedule

SCHEMA = """
CREATE TABLE IF NOT EXISTS schedules (
    id    TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    date  TEXT NOT NULL,
    time  TEXT NOT NULL,
    notes TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_schedules_date ON schedules(date);
"""


class SqliteScheduleRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._connection.executescript(SCHEMA)
        self._connection.commit()

    def _execute(self, sql: str, parameters: tuple[object, ...] = ()) -> sqlite3.Cursor:
        """执行一条语句，并只在游标上启用 Row 工厂。

        不在注入的连接上设置 ``row_factory``：连接归调用方所有，仓储不应
        悄悄改变它按元组取值的既有行为。
        """
        cursor = self._connection.execute(sql, parameters)
        cursor.row_factory = sqlite3.Row
        return cursor

    @staticmethod
    def _row_to_schedule(row: sqlite3.Row) -> Schedule:
        try:
            return Schedule(
                id=row["id"],
                title=row["title"],
                date=date.fromisoformat(row["date"]),
                time=time.fromisoformat(row["time"]),
                notes=row["notes"],
            )
        except (ValueError, TypeError, ValidationError) as exc:
            raise StorageError("存储中的日程数据无法解析", cause=exc) from exc

    def add(self, schedule: Schedule) -> None:
        try:
            self._execute(
                "INSERT INTO schedules (id, title, date, time, notes) VALUES (?, ?, ?, ?, ?)",
                (
                    schedule.id,
                    schedule.title,
                    schedule.date.isoformat(),
                    schedule.time.isoformat(),
                    schedule.notes,
                ),
            )
            self._connection.commit()
        except sqlite3.IntegrityError as exc:
            self._connection.rollback()
            message = str(exc)
            if "UNIQUE" in message or "PRIMARY KEY" in message:
                raise DuplicateScheduleError(f"日程 ID 已存在：{schedule.id}", cause=exc) from exc
            raise StorageError("写入日程失败", cause=exc) from exc
        except sqlite3.Error as exc:
            self._connection.rollback()
            raise StorageError("写入日程失败", cause=exc) from exc

    def get(self, schedule_id: str) -> Schedule | None:
        try:
            row = self._execute(
                "SELECT id, title, date, time, notes FROM schedules WHERE id = ?",
                (schedule_id,),
            ).fetchone()
        except sqlite3.Error as exc:
            raise StorageError("读取日程失败", cause=exc) from exc
        return None if row is None else self._row_to_schedule(row)

    def list_by_date(self, day: date) -> list[Schedule]:
        try:
            rows = self._execute(
                "SELECT id, title, date, time, notes FROM schedules "
                "WHERE date = ? ORDER BY time, id",
                (day.isoformat(),),
            ).fetchall()
        except sqlite3.Error as exc:
            raise StorageError("查询日程失败", cause=exc) from exc
        return [self._row_to_schedule(row) for row in rows]

    def update(self, schedule: Schedule) -> bool:
        try:
            cursor = self._execute(
                "UPDATE schedules SET title = ?, date = ?, time = ?, notes = ? WHERE id = ?",
                (
                    schedule.title,
                    schedule.date.isoformat(),
                    schedule.time.isoformat(),
                    schedule.notes,
                    schedule.id,
                ),
            )
            self._connection.commit()
        except sqlite3.Error as exc:
            self._connection.rollback()
            raise StorageError("更新日程失败", cause=exc) from exc
        return cursor.rowcount > 0

    def delete(self, schedule_id: str) -> bool:
        try:
            cursor = self._execute(
                "DELETE FROM schedules WHERE id = ?",
                (schedule_id,),
            )
            self._connection.commit()
        except sqlite3.Error as exc:
            self._connection.rollback()
            raise StorageError("删除日程失败", cause=exc) from exc
        return cursor.rowcount > 0
