"""
Unit tests for ha-tools shared utilities.

Tests for parse_timeframe and other shared utility functions.
"""

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from ha_tools.lib.utils import (
    parse_datetime,
    parse_timeframe,
    parse_timeframe_to_timedelta,
)


class TestParseTimeframe:
    """Test timeframe parsing functionality."""

    def test_parse_timeframe_hours(self):
        """Test parsing timeframe in hours."""
        base_time = datetime(2024, 1, 1, 12, 0, 0)
        with patch("ha_tools.lib.utils.datetime") as mock_datetime:
            mock_datetime.now.return_value = base_time

            result = parse_timeframe("24h")
            expected = base_time - timedelta(hours=24)
            assert result == expected

    def test_parse_timeframe_hours_uppercase(self):
        """Test parsing timeframe with uppercase H."""
        base_time = datetime(2024, 1, 1, 12, 0, 0)
        with patch("ha_tools.lib.utils.datetime") as mock_datetime:
            mock_datetime.now.return_value = base_time

            result = parse_timeframe("24H")
            expected = base_time - timedelta(hours=24)
            assert result == expected

    def test_parse_timeframe_days(self):
        """Test parsing timeframe in days."""
        base_time = datetime(2024, 1, 1, 12, 0, 0)
        with patch("ha_tools.lib.utils.datetime") as mock_datetime:
            mock_datetime.now.return_value = base_time

            result = parse_timeframe("7d")
            expected = base_time - timedelta(days=7)
            assert result == expected

    def test_parse_timeframe_minutes(self):
        """Test parsing timeframe in minutes."""
        base_time = datetime(2024, 1, 1, 12, 0, 0)
        with patch("ha_tools.lib.utils.datetime") as mock_datetime:
            mock_datetime.now.return_value = base_time

            result = parse_timeframe("30m")
            expected = base_time - timedelta(minutes=30)
            assert result == expected

    def test_parse_timeframe_weeks(self):
        """Test parsing timeframe in weeks."""
        base_time = datetime(2024, 1, 1, 12, 0, 0)
        with patch("ha_tools.lib.utils.datetime") as mock_datetime:
            mock_datetime.now.return_value = base_time

            result = parse_timeframe("2w")
            expected = base_time - timedelta(weeks=2)
            assert result == expected

    def test_parse_timeframe_with_spaces(self):
        """Test parsing timeframe with leading/trailing spaces."""
        base_time = datetime(2024, 1, 1, 12, 0, 0)
        with patch("ha_tools.lib.utils.datetime") as mock_datetime:
            mock_datetime.now.return_value = base_time

            result = parse_timeframe("  24h  ")
            expected = base_time - timedelta(hours=24)
            assert result == expected

    def test_parse_timeframe_invalid_format(self):
        """Test parsing invalid timeframe format."""
        with pytest.raises(ValueError) as excinfo:
            parse_timeframe("24x")
        assert "Invalid timeframe format" in str(excinfo.value)
        assert "Use h (hours), d (days), m (minutes), or w (weeks)" in str(
            excinfo.value
        )

    def test_parse_timeframe_invalid_number(self):
        """Test parsing timeframe with invalid number."""
        with pytest.raises(ValueError):
            parse_timeframe("invalidh")

    def test_parse_timeframe_empty_number(self):
        """Test parsing timeframe with empty number."""
        with pytest.raises(ValueError):
            parse_timeframe("h")

    def test_parse_timeframe_zero(self):
        """Test parsing timeframe with zero value."""
        base_time = datetime(2024, 1, 1, 12, 0, 0)
        with patch("ha_tools.lib.utils.datetime") as mock_datetime:
            mock_datetime.now.return_value = base_time

            result = parse_timeframe("0h")
            expected = base_time - timedelta(hours=0)
            assert result == expected

    def test_parse_timeframe_large_value(self):
        """Test parsing timeframe with large value."""
        base_time = datetime(2024, 1, 1, 12, 0, 0)
        with patch("ha_tools.lib.utils.datetime") as mock_datetime:
            mock_datetime.now.return_value = base_time

            result = parse_timeframe("365d")
            expected = base_time - timedelta(days=365)
            assert result == expected


class TestParseDatetime:
    """Test datetime string parsing."""

    def test_parse_date_only(self):
        """Test parsing date-only string returns midnight."""
        result = parse_datetime("2026-01-18")
        from datetime import datetime

        assert result == datetime(2026, 1, 18, 0, 0, 0)

    def test_parse_datetime_with_time(self):
        """Test parsing full datetime string."""
        result = parse_datetime("2026-01-18T14:30:00")
        from datetime import datetime

        assert result == datetime(2026, 1, 18, 14, 30, 0)

    def test_parse_datetime_invalid(self):
        """Test parsing invalid string raises ValueError."""
        with pytest.raises(ValueError):
            parse_datetime("bad-date")

    def test_parse_datetime_empty(self):
        """Test parsing empty string raises ValueError."""
        with pytest.raises(ValueError):
            parse_datetime("")


class TestParseTimeframeToTimedelta:
    """Test timeframe to timedelta parsing."""

    def test_hours(self):
        """Test parsing hours to timedelta."""
        result = parse_timeframe_to_timedelta("24h")
        assert result == timedelta(hours=24)

    def test_days(self):
        """Test parsing days to timedelta."""
        result = parse_timeframe_to_timedelta("7d")
        assert result == timedelta(days=7)

    def test_minutes(self):
        """Test parsing minutes to timedelta."""
        result = parse_timeframe_to_timedelta("30m")
        assert result == timedelta(minutes=30)

    def test_weeks(self):
        """Test parsing weeks to timedelta."""
        result = parse_timeframe_to_timedelta("2w")
        assert result == timedelta(weeks=2)

    def test_invalid(self):
        """Test parsing invalid format raises ValueError."""
        with pytest.raises(ValueError):
            parse_timeframe_to_timedelta("24x")
