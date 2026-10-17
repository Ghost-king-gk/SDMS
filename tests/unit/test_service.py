"""服务层单元测试：用内存仓储验证用例编排。"""

from datetime import date, time

import pytest

from schedule_management.application.errors import (
    DuplicateScheduleError,
    ScheduleNotFoundError,
    StorageError,
)
from schedule_management.application.service import ScheduleService
from schedule_management.domain.errors import ValidationError
from schedule_management.domain.schedule import Schedule
from tests.fakes import InMemoryScheduleRepository

DAY = date(2026, 10, 15)
NEXT_DAY = date(2026, 10, 16)


class DuplicateOnAddRepository(InMemoryScheduleRepository):
    """模拟 id 冲突：仓储拒绝写入，服务层不得吞掉异常。"""

    def add(self, schedule: Schedule) -> None:
        raise DuplicateScheduleError(f"日程 ID 已存在：{schedule.id}")


class StorageFailingRepository(InMemoryScheduleRepository):
    """模拟磁盘故障：读取时抛 StorageError。"""

    error = StorageError("磁盘忙")

    def list_by_date(self, day: date) -> list[Schedule]:
        raise self.error


@pytest.fixture
def repository() -> InMemoryScheduleRepository:
    return InMemoryScheduleRepository()


@pytest.fixture
def service(repository: InMemoryScheduleRepository) -> ScheduleService:
    return ScheduleService(repository)


def test_create_returns_parsed_schedule(service: ScheduleService) -> None:
    created = service.create_schedule("  写周报  ", "2026/10/15", "9:05", "  备注  ")

    assert created.id
    assert created.title == "写周报"
    assert created.date == DAY
    assert created.time == time(9, 5)
    assert created.notes == "备注"


def test_create_is_immediately_listed(service: ScheduleService) -> None:
    created = service.create_schedule("写周报", "2026-10-15", "09:05", "")
    assert service.list_schedules(DAY) == [created]


def test_create_generates_distinct_ids(service: ScheduleService) -> None:
    first = service.create_schedule("第一条", "2026-10-15", "09:00", "")
    second = service.create_schedule("第二条", "2026-10-15", "10:00", "")
    assert first.id != second.id


def test_list_returns_empty_for_day_without_schedules(service: ScheduleService) -> None:
    service.create_schedule("写周报", "2026-10-15", "09:05", "")
    assert service.list_schedules(NEXT_DAY) == []


def test_update_keeps_id_and_overwrites_all_fields(service: ScheduleService) -> None:
    created = service.create_schedule("写周报", "2026-10-15", "09:05", "旧备注")

    updated = service.update_schedule(created.id, "改标题", "2026.10.16", "10:30", "新备注")

    assert updated.id == created.id
    assert (updated.title, updated.date, updated.time, updated.notes) == (
        "改标题",
        NEXT_DAY,
        time(10, 30),
        "新备注",
    )
    assert service.list_schedules(DAY) == []
    assert service.list_schedules(NEXT_DAY) == [updated]


def test_update_missing_schedule_raises(service: ScheduleService) -> None:
    with pytest.raises(ScheduleNotFoundError) as excinfo:
        service.update_schedule("no-such-id", "标题", "2026-10-15", "09:00", "")

    assert "no-such-id" in str(excinfo.value)
    assert "已经不在列表里" in str(excinfo.value)


def test_delete_removes_schedule(service: ScheduleService) -> None:
    created = service.create_schedule("写周报", "2026-10-15", "09:05", "")

    service.delete_schedule(created.id)
    assert service.list_schedules(DAY) == []


def test_delete_missing_schedule_raises(service: ScheduleService) -> None:
    with pytest.raises(ScheduleNotFoundError) as excinfo:
        service.delete_schedule("no-such-id")

    assert "no-such-id" in str(excinfo.value)


@pytest.mark.parametrize("blank_id", ["", "   "])
def test_update_blank_id_raises_validation_error(service: ScheduleService, blank_id: str) -> None:
    with pytest.raises(ValidationError, match="日程 ID 不能为空"):
        service.update_schedule(blank_id, "标题", "2026-10-15", "09:00", "")


@pytest.mark.parametrize("blank_id", ["", "   "])
def test_delete_blank_id_raises_validation_error(service: ScheduleService, blank_id: str) -> None:
    with pytest.raises(ValidationError, match="日程 ID 不能为空"):
        service.delete_schedule(blank_id)


def test_duplicate_error_passes_through_unchanged() -> None:
    service = ScheduleService(DuplicateOnAddRepository())

    with pytest.raises(DuplicateScheduleError) as excinfo:
        service.create_schedule("写周报", "2026-10-15", "09:00", "")

    assert str(excinfo.value).startswith("日程 ID 已存在：")


def test_storage_error_passes_through_unchanged() -> None:
    service = ScheduleService(StorageFailingRepository())

    with pytest.raises(StorageError) as excinfo:
        service.list_schedules(DAY)

    assert excinfo.value is StorageFailingRepository.error
