"""领域层：日程的含义与有效性规则。"""

from schedule_management.domain.errors import ValidationError
from schedule_management.domain.schedule import Schedule, new_schedule_id

__all__ = ["Schedule", "ValidationError", "new_schedule_id"]
