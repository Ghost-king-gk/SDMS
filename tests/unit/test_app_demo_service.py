"""演示服务工厂：只服务截图/演示，不碰数据库，也不创建 QApplication。"""

from __future__ import annotations

import datetime as dt

import pytest

from schedule_management import composition
from schedule_management.dev_stub_service import DevStubScheduleService
from schedule_management.ui import app

DAY = dt.date(2026, 10, 15)


def test_build_demo_service_seeds_five_schedules() -> None:
    service = app.build_demo_service(DAY)

    assert isinstance(service, DevStubScheduleService)
    assert service.count_all() == 5
    assert len(service.list_schedules(DAY)) == 3


def test_build_demo_service_does_not_create_qapplication(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("演示工厂不应创建 QApplication")

    monkeypatch.setattr(app, "QApplication", _forbidden)

    assert isinstance(app.build_demo_service(DAY), DevStubScheduleService)


def test_build_demo_service_does_not_open_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("演示工厂不应打开数据库")

    monkeypatch.setattr(composition, "connect", _forbidden)

    assert isinstance(app.build_demo_service(DAY), DevStubScheduleService)
