"""用户输入的宽容解析与字段规范化。

界面把用户原样输入的日期、时间交到服务层，解析在这里完成（T-02）。宽容是
**有边界**的：只接受分隔符差异与缺失的前导零，不接受相对日期或日月年顺序。
认不出来时抛 :class:`~schedule_management.domain.errors.ValidationError`，
消息里回显用户原文，让界面能指出到底哪一处要改。

长度上限按字符数计算（``len(str)``），标题 100、备注 500，与契约
``docs/design/contracts.md`` 一致。
"""

from __future__ import annotations

import datetime as dt
import re
from typing import Final

from schedule_management.domain.errors import ValidationError

#: 标题规范化后的最大字符数。
TITLE_LIMIT: Final = 100

#: 备注规范化后的最大字符数。
NOTES_LIMIT: Final = 500

# 只认 ASCII 数字：全角数字或其他 Unicode 数字一律按“无法识别”处理，
# 避免不同输入法下同一串文本被解释成不同日期。
_DATE_PATTERNS: Final = (
    re.compile(r"^([0-9]{4})-([0-9]{1,2})-([0-9]{1,2})$"),
    re.compile(r"^([0-9]{4})/([0-9]{1,2})/([0-9]{1,2})$"),
    re.compile(r"^([0-9]{4})\.([0-9]{1,2})\.([0-9]{1,2})$"),
    re.compile(r"^([0-9]{4})年([0-9]{1,2})月([0-9]{1,2})日$"),
)

# 分钟必须是两位，与界面 ``HH:MM`` 的输入/显示格式一致。
_TIME_PATTERN: Final = re.compile(r"^([0-9]{1,2}):([0-9]{2})$")


def parse_date(text: str) -> dt.date:
    """把日期文本转成 :class:`datetime.date`。

    支持 ``2026-10-15``、``2026/10/15``、``2026.10.15``、``2026年10月15日``，
    月、日可缺前导零，前后空白忽略。相对日期（``明天``）、日月年顺序
    （``15/10/2026``）与不存在的日期（``2026-02-30``）都抛 ``ValidationError``。
    """
    raw = text.strip()
    for pattern in _DATE_PATTERNS:
        matched = pattern.match(raw)
        if matched is None:
            continue
        year, month, day = (int(part) for part in matched.groups())
        try:
            return dt.date(year, month, day)
        except ValueError as exc:
            raise ValidationError(f"日期「{raw}」不是一个真实存在的日期") from exc

    raise ValidationError(f"日期「{raw}」无法识别，请写成 2026-10-15 这样")


def parse_time(text: str) -> dt.time:
    """把时间文本转成 :class:`datetime.time`，精度到分钟。

    接受 ``H:MM`` 与 ``HH:MM``（``9:05`` 与 ``09:05`` 等价）；``25:00``、
    ``09:60`` 这类越界值抛 ``ValidationError``，消息回显原文。
    """
    raw = text.strip()
    matched = _TIME_PATTERN.match(raw)
    if matched is None:
        raise ValidationError(f"时间「{raw}」无法识别，请写成 09:30 这样")

    hour, minute = (int(part) for part in matched.groups())
    try:
        return dt.time(hour, minute)
    except ValueError as exc:
        raise ValidationError(f"时间「{raw}」不是一个真实存在的时间") from exc


def clean_fields(title: str, notes: str) -> tuple[str, str]:
    """规范化标题与备注，返回去空白后的值。

    标题去空白后不能为空，备注允许为空串；超长抛 ``ValidationError``。
    """
    clean_title = title.strip()
    if not clean_title:
        raise ValidationError("标题不能为空，也不能只有空格")
    if len(clean_title) > TITLE_LIMIT:
        raise ValidationError(f"标题太长了（{len(clean_title)} 字，最多 {TITLE_LIMIT} 字）")

    clean_notes = notes.strip()
    if len(clean_notes) > NOTES_LIMIT:
        raise ValidationError(f"备注太长了（{len(clean_notes)} 字，最多 {NOTES_LIMIT} 字）")

    return clean_title, clean_notes


def validate(
    title: str,
    date_text: str,
    time_text: str,
    notes: str,
) -> tuple[str, dt.date, dt.time, str]:
    """校验四个字段并按「标题、日期、时间、备注」的顺序返回干净值。

    这是服务层创建与修改共用的唯一校验入口，保证两条路径规则完全一致。
    """
    clean_title, clean_notes = clean_fields(title, notes)
    return clean_title, parse_date(date_text), parse_time(time_text), clean_notes


__all__ = [
    "NOTES_LIMIT",
    "TITLE_LIMIT",
    "clean_fields",
    "parse_date",
    "parse_time",
    "validate",
]
