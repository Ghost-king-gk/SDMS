"""应用层错误类型。"""


class ScheduleNotFoundError(Exception):
    pass


class StorageError(Exception):
    def __init__(self, message: str, *, cause: BaseException | None = None) -> None:
        super().__init__(message)
        self.cause = cause


class DuplicateScheduleError(StorageError):
    pass
