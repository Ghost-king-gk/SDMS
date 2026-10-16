"""SQLite 日程存储适配器。

实现应用层定义的 ScheduleRepository 契约，负责把日程对象写入 SQLite 数据库，
并保证每次写操作原子完成或回滚。
"""

import sqlite3
from datetime import date, time

from schedule_management.application.errors import DuplicateScheduleError, StorageError
from schedule_management.domain.schedule import Schedule

SCHEMA = """
CREATE TABLE IF NOT EXISTS schedules (
    id    TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    date  TEXT NOT NULL,
    time  TEXT NOT NULL,
    notes TEXT NOT NULL DEFAULT ''
)
"""


class SqliteScheduleRepository:
    """基于 SQLite 的日程存储。

    连接由装配点创建并负责关闭；本类只负责 CRUD、序列化与异常转换。
    """

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._connection.row_factory = sqlite3.Row
        self._connection.execute(SCHEMA)
        self._connection.commit()

    @staticmethod
    def _row_to_schedule(row: sqlite3.Row) -> Schedule:
        """把数据库行还原为日程对象（字符串反序列化为 date/time）。"""
        return Schedule(
            id=row["id"],
            title=row["title"],
            date=date.fromisoformat(row["date"]),
            time=time.fromisoformat(row["time"]),
            notes=row["notes"],
        )

    def add(self, schedule: Schedule) -> None:
        """新增日程；ID 已存在时报告存储冲突，不覆盖原记录。"""
        try:
            self._connection.execute(
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
            raise DuplicateScheduleError(
                f"日程 ID 已存在：{schedule.id}", cause=exc
            ) from exc
        except sqlite3.Error as exc:
            self._connection.rollback()
            raise StorageError("写入日程失败", cause=exc) from exc

    def get(self, schedule_id: str) -> Schedule | None:
        """按 ID 查询；不存在返回 None。"""
        try:
            row = self._connection.execute(
                "SELECT id, title, date, time, notes FROM schedules WHERE id = ?",
                (schedule_id,),
            ).fetchone()
        except sqlite3.Error as exc:
            raise StorageError("读取日程失败", cause=exc) from exc
        return None if row is None else self._row_to_schedule(row)

    def list_by_date(self, day: date) -> list[Schedule]:
        """返回指定日期的全部日程，按 time、id 确定性排序。"""
        try:
            rows = self._connection.execute(
                "SELECT id, title, date, time, notes FROM schedules "
                "WHERE date = ? ORDER BY time, id",
                (day.isoformat(),),
            ).fetchall()
        except sqlite3.Error as exc:
            raise StorageError("查询日程失败", cause=exc) from exc
        return [self._row_to_schedule(row) for row in rows]

    def update(self, schedule: Schedule) -> bool:
        """更新日程；找不到记录返回 False。"""
        try:
            cursor = self._connection.execute(
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
        """删除日程；找不到记录返回 False。"""
        try:
            cursor = self._connection.execute(
                "DELETE FROM schedules WHERE id = ?",
                (schedule_id,),
            )
            self._connection.commit()
        except sqlite3.Error as exc:
            self._connection.rollback()
            raise StorageError("删除日程失败", cause=exc) from exc
        return cursor.rowcount > 0
