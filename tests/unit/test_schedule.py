"""日程领域不变量测试。"""

from datetime import date, time

import pytest

from schedule_management.domain.errors import ValidationError
from schedule_management.domain.schedule import Schedule

DAY = date(2026, 10, 14)


def make_schedule(*, schedule_id: str = "id-1") -> Schedule:
    return Schedule(id=schedule_id, title="写周报", date=DAY, time=time(9, 30))


def test_id_is_stripped() -> None:
    assert make_schedule(schedule_id="  id-9  ").id == "id-9"


def test_blank_id_rejected() -> None:
    with pytest.raises(ValidationError, match="日程 ID 不能为空"):
        make_schedule(schedule_id="   ")


def test_title_is_stripped() -> None:
    schedule = Schedule(id="id-1", title="  写周报  ", date=DAY, time=time(9, 30))
    assert schedule.title == "写周报"


def test_time_truncated_to_minute() -> None:
    schedule = Schedule(id="id-1", title="写周报", date=DAY, time=time(9, 30, 45, 123456))
    assert schedule.time == time(9, 30)
    assert schedule.time.second == 0
    assert schedule.time.microsecond == 0


def test_notes_must_be_text() -> None:
    with pytest.raises(ValidationError, match="备注必须是文本"):
        Schedule(
            id="id-1",
            title="写周报",
            date=DAY,
            time=time(9, 30),
            notes=None,  # type: ignore[arg-type]
        )
