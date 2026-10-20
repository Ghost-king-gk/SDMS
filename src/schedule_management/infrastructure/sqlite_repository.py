"""SQLite 日程存储适配器。

``time`` 列保持 ``TEXT NOT NULL`` 以兼容既有数据库，**空串是全天日程的哨兵**：
全天日程写入 ``""``，读出时还原为 ``None``。因此旧库无需重建或迁移——旧数据
里的 ``HH:MM`` 仍然有效，新写入的全天日程也不会违反 NOT NULL。
"""

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
    time  TEXT NOT NULL,  -- HH:MM；空串表示全天日程
    notes TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_schedules_date ON schedules(date);
"""


def _escape_like(text: str) -> str:
    """转义 LIKE 通配符，让用户输入的 ``%``、``_``、``\\`` 按字面量匹配。"""
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _encode_time(at: time | None) -> str:
    """把可选时间编码成存储值：``None``（全天）写成空串。"""
    return at.isoformat() if at is not None else ""


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
            raw_time = row["time"]
            at = None if raw_time in (None, "") else time.fromisoformat(raw_time)
            return Schedule(
                id=row["id"],
                title=row["title"],
                date=date.fromisoformat(row["date"]),
                time=at,
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
                    _encode_time(schedule.time),
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
                "WHERE date = ? "
                "ORDER BY CASE WHEN time = '' THEN 0 ELSE 1 END, time, id",
                (day.isoformat(),),
            ).fetchall()
        except sqlite3.Error as exc:
            raise StorageError("查询日程失败", cause=exc) from exc
        return [self._row_to_schedule(row) for row in rows]

    def count_by_date(self, start: date, end: date) -> dict[date, int]:
        """返回闭区间 ``[start, end]`` 内每个有日程的日期及条数。"""
        try:
            rows = self._execute(
                "SELECT date, COUNT(*) AS total FROM schedules "
                "WHERE date >= ? AND date <= ? GROUP BY date ORDER BY date",
                (start.isoformat(), end.isoformat()),
            ).fetchall()
        except sqlite3.Error as exc:
            raise StorageError("查询有日程的日期失败", cause=exc) from exc

        try:
            return {date.fromisoformat(row["date"]): int(row["total"]) for row in rows}
        except (ValueError, TypeError) as exc:
            raise StorageError("存储中的日程数据无法解析", cause=exc) from exc

    def search_schedules(self, text: str) -> list[Schedule]:
        """按标题或备注包含搜索；``%``、``_``、``\\`` 按字面量匹配。"""
        needle = text.strip()
        if not needle:
            return []

        pattern = f"%{_escape_like(needle)}%"
        try:
            rows = self._execute(
                "SELECT id, title, date, time, notes FROM schedules "
                "WHERE title LIKE ? ESCAPE '\\' OR notes LIKE ? ESCAPE '\\' "
                "ORDER BY date, CASE WHEN time = '' THEN 0 ELSE 1 END, time, id",
                (pattern, pattern),
            ).fetchall()
        except sqlite3.Error as exc:
            raise StorageError("搜索日程失败", cause=exc) from exc
        return [self._row_to_schedule(row) for row in rows]

    def update(self, schedule: Schedule) -> bool:
        try:
            cursor = self._execute(
                "UPDATE schedules SET title = ?, date = ?, time = ?, notes = ? WHERE id = ?",
                (
                    schedule.title,
                    schedule.date.isoformat(),
                    _encode_time(schedule.time),
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
