"""契约测试：服务实现必须满足 ``ScheduleUseCases`` 运行时协议。"""

from datetime import date

from schedule_management.application.contracts import ScheduleUseCases
from schedule_management.application.service import ScheduleService
from schedule_management.domain.schedule import Schedule
from tests.fakes import InMemoryScheduleRepository


class PartialService:
    """只实现了一个方法的假服务，不能冒充完整用例协议。"""

    def list_schedules(self, day: date) -> list[Schedule]:
        return []


def test_schedule_service_satisfies_use_cases_protocol() -> None:
    service = ScheduleService(InMemoryScheduleRepository())

    assert isinstance(service, ScheduleUseCases)


def test_incomplete_service_is_rejected_by_protocol() -> None:
    assert not isinstance(PartialService(), ScheduleUseCases)
