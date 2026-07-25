"""Time-window helpers."""

from datetime import datetime, timedelta

import pytest

from ha_tools.utils import parse_datetime, parse_timeframe_to_timedelta


def test_timeframe_units():
    assert parse_timeframe_to_timedelta("30m") == timedelta(minutes=30)
    assert parse_timeframe_to_timedelta("24h") == timedelta(hours=24)
    assert parse_timeframe_to_timedelta("14d") == timedelta(days=14)
    assert parse_timeframe_to_timedelta("2w") == timedelta(weeks=2)


def test_timeframe_case_and_whitespace():
    assert parse_timeframe_to_timedelta(" 5H ") == timedelta(hours=5)


def test_timeframe_invalid():
    with pytest.raises(ValueError):
        parse_timeframe_to_timedelta("5x")


def test_parse_datetime_formats():
    assert parse_datetime("2026-01-01") == datetime(2026, 1, 1)
    assert parse_datetime("2026-01-01T08:30:00") == datetime(2026, 1, 1, 8, 30, 0)
    assert parse_datetime("2026-01-01 08:30:00") == datetime(2026, 1, 1, 8, 30, 0)
    assert parse_datetime(datetime(2026, 1, 1)) == datetime(2026, 1, 1)


def test_parse_datetime_invalid():
    with pytest.raises(ValueError):
        parse_datetime("not-a-date")
