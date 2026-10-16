"""应用层错误类型。

展示层只捕获这些可解释的预期错误；意外异常记录诊断信息后给出通用提示。
"""


class ScheduleNotFoundError(Exception):
    """按 ID 查询或操作时记录不存在。"""


class StorageError(Exception):
    """持久化存储失败，保留原始原因供诊断。"""

    def __init__(self, message: str, *, cause: BaseException | None = None) -> None:
        super().__init__(message)
        self.cause = cause


class DuplicateScheduleError(StorageError):
    """写入时 ID 已存在，作为存储冲突报告。"""
