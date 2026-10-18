"""宽容解析与字段校验测试。"""

from datetime import date, time

import pytest

from schedule_management.application.parsing import (
    NOTES_LIMIT,
    TITLE_LIMIT,
    clean_fields,
    parse_date,
    parse_time,
    validate,
)
from schedule_management.domain.errors import ValidationError


def test_limits_match_contract() -> None:
    """长度上限属于团队契约，改动必须同步改 contracts.md。"""
    assert TITLE_LIMIT == 100
    assert NOTES_LIMIT == 500


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("2026-10-15", date(2026, 10, 15)),
        ("2026/10/15", date(2026, 10, 15)),
        ("2026.10.15", date(2026, 10, 15)),
        ("2026年10月15日", date(2026, 10, 15)),
        ("2026-1-5", date(2026, 1, 5)),
        ("2026/1/5", date(2026, 1, 5)),
        ("2026.1.5", date(2026, 1, 5)),
        ("2026年1月5日", date(2026, 1, 5)),
        ("  2026-10-15  ", date(2026, 10, 15)),
        ("\t2026年1月5日\n", date(2026, 1, 5)),
    ],
)
def test_parse_date_supported_formats(text: str, expected: date) -> None:
    assert parse_date(text) == expected


@pytest.mark.parametrize(
    "text",
    ["明天", "今天", "下周三", "15/10/2026", "10-15-2026", "2026-10", "2026年10月", "", "   "],
)
def test_parse_date_rejects_unrecognized(text: str) -> None:
    with pytest.raises(ValidationError) as excinfo:
        parse_date(text)
    message = str(excinfo.value)
    assert f"日期「{text.strip()}」" in message
    assert "无法识别" in message


@pytest.mark.parametrize(
    "text",
    ["2026-02-30", "2026-13-01", "2026-4-31", "2026年2月30日", "0000-01-01"],
)
def test_parse_date_rejects_nonexistent(text: str) -> None:
    with pytest.raises(ValidationError) as excinfo:
        parse_date(text)
    message = str(excinfo.value)
    assert f"日期「{text}」" in message
    assert "真实存在" in message


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("9:05", time(9, 5)),
        ("09:05", time(9, 5)),
        ("0:00", time(0, 0)),
        ("23:59", time(23, 59)),
        ("  7:30  ", time(7, 30)),
    ],
)
def test_parse_time_supported_formats(text: str, expected: time) -> None:
    assert parse_time(text) == expected


@pytest.mark.parametrize("text", ["25:00", "24:00", "09:60", "9:60"])
def test_parse_time_rejects_out_of_range(text: str) -> None:
    with pytest.raises(ValidationError) as excinfo:
        parse_time(text)
    message = str(excinfo.value)
    assert f"时间「{text}」" in message
    assert "真实存在" in message


@pytest.mark.parametrize("text", ["9:5", "0930", "上午九点", "09:05:30", ""])
def test_parse_time_rejects_unrecognized(text: str) -> None:
    with pytest.raises(ValidationError) as excinfo:
        parse_time(text)
    message = str(excinfo.value)
    assert f"时间「{text}」" in message
    assert "无法识别" in message


def test_clean_fields_strips_title_and_notes() -> None:
    assert clean_fields("  写周报  ", "  带备注  ") == ("写周报", "带备注")


def test_empty_notes_is_valid() -> None:
    assert clean_fields("写周报", "") == ("写周报", "")
    assert clean_fields("写周报", "   ") == ("写周报", "")


@pytest.mark.parametrize("title", ["", "   ", "\u3000"])
def test_blank_title_rejected(title: str) -> None:
    with pytest.raises(ValidationError, match="标题不能为空"):
        clean_fields(title, "")


def test_title_length_boundary_counts_characters() -> None:
    longest = "周" * TITLE_LIMIT
    assert clean_fields(longest, "")[0] == longest

    with pytest.raises(ValidationError) as excinfo:
        clean_fields("周" * (TITLE_LIMIT + 1), "")
    message = str(excinfo.value)
    assert str(TITLE_LIMIT + 1) in message
    assert str(TITLE_LIMIT) in message


def test_notes_length_boundary_counts_characters() -> None:
    longest = "注" * NOTES_LIMIT
    assert clean_fields("写周报", longest)[1] == longest

    with pytest.raises(ValidationError) as excinfo:
        clean_fields("写周报", "注" * (NOTES_LIMIT + 1))
    message = str(excinfo.value)
    assert str(NOTES_LIMIT + 1) in message
    assert str(NOTES_LIMIT) in message


def test_validate_returns_clean_values() -> None:
    result = validate("  写周报 ", "2026/10/15", "9:05", "  备注 ")
    assert result == ("写周报", date(2026, 10, 15), time(9, 5), "备注")


def test_validate_reports_title_before_date() -> None:
    """多个字段都不合法时先报标题，保证提示稳定、可预测。"""
    with pytest.raises(ValidationError, match="标题不能为空"):
        validate("   ", "明天", "25:00", "")
