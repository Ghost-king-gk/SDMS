"""应用层错误类型。"""


class ScheduleNotFoundError(Exception):
    """按 id 找不到日程。

    服务层在仓储的 ``update()`` / ``delete()`` 返回 ``False`` 时抛出，
    界面据此提示“记录可能已被删除”。
    """


class StorageError(Exception):
    def __init__(self, message: str, *, cause: BaseException | None = None) -> None:
        super().__init__(message)
        self.cause = cause


class DuplicateScheduleError(StorageError):
    pass
