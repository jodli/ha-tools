"""Unit tests for the history command."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ha_tools.commands.history import (
    _compute_statistics,
    _output_csv_format,
    _output_markdown_format,
    _run_history_command,
)


class TestComputeStatistics:
    """Tests for _compute_statistics function."""

    def test_numeric_states(self):
        """Test statistics for numeric states."""
        states = [
            {"state": "20.0"},
            {"state": "21.5"},
            {"state": "19.0"},
            {"state": "22.0"},
        ]

        stats = _compute_statistics(states)

        assert stats["numeric"] is True
        assert stats["min"] == 19.0
        assert stats["max"] == 22.0
        assert stats["avg"] == 20.625
        assert stats["numeric_count"] == 4
        assert stats["total_records"] == 4

    def test_non_numeric_states(self):
        """Test statistics for non-numeric states."""
        states = [
            {"state": "on"},
            {"state": "off"},
            {"state": "on"},
            {"state": "on"},
        ]

        stats = _compute_statistics(states)

        assert stats["numeric"] is False
        assert stats["state_counts"] == {"on": 3, "off": 1}
        assert stats["total_records"] == 4
        assert stats["unique_states"] == 2

    def test_mixed_states_with_unavailable(self):
        """Test that unavailable/unknown states are counted but not in numeric stats."""
        states = [
            {"state": "20.0"},
            {"state": "unavailable"},
            {"state": "21.0"},
            {"state": "unknown"},
        ]

        stats = _compute_statistics(states)

        assert stats["numeric"] is True
        assert stats["numeric_count"] == 2
        assert stats["total_records"] == 4
        assert "unavailable" in stats["state_counts"]

    def test_empty_states(self):
        """Test statistics for empty state list."""
        stats = _compute_statistics([])

        assert stats["numeric"] is False
        assert stats["total_records"] == 0
        assert stats["unique_states"] == 0


class TestOutputFormats:
    """Tests for output formatting functions."""

    def test_csv_output_with_attributes(self, capsys):
        """Test CSV output includes entity-specific attribute columns."""
        states = [
            {
                "last_updated": "2024-01-01T12:00:00",
                "state": "20.0",
                "last_changed": "2024-01-01T12:00:00",
                "attributes": '{"state_class": "measurement", "min_temp": 15}',
            },
            {
                "last_updated": "2024-01-01T13:00:00",
                "state": "21.0",
                "last_changed": "2024-01-01T13:00:00",
                "attributes": '{"state_class": "measurement"}',
            },
        ]

        _output_csv_format(states)

        captured = capsys.readouterr()
        lines = captured.out.strip().split("\n")

        # Check headers include entity-specific attribute columns
        headers = [h.strip() for h in lines[0].split(",")]
        assert "timestamp" in headers
        assert "state" in headers
        assert "attr_state_class" in headers
        assert "attr_min_temp" in headers

    def test_csv_output_empty(self, capsys):
        """Test CSV output with empty states."""
        _output_csv_format([])
        captured = capsys.readouterr()
        assert captured.out == ""

    def test_csv_output_with_dict_attributes(self, capsys):
        """Test CSV output when attributes is already a dict."""
        states = [
            {
                "last_updated": "2024-01-01T12:00:00",
                "state": "20.0",
                "last_changed": "2024-01-01T12:00:00",
                "attributes": {"state_class": "measurement"},
            },
        ]

        _output_csv_format(states)

        captured = capsys.readouterr()
        lines = captured.out.strip().split("\n")
        assert len(lines) == 2  # header + 1 data row

    def test_csv_output_excludes_default_ha_attributes(self, capsys):
        """Test CSV output excludes default HA attributes."""
        states = [
            {
                "last_updated": "2024-01-01T12:00:00",
                "state": "20.0",
                "last_changed": "2024-01-01T12:00:00",
                "attributes": json.dumps(
                    {
                        # Default HA attributes (should be excluded)
                        "friendly_name": "Temperature Sensor",
                        "icon": "mdi:thermometer",
                        "unit_of_measurement": "°C",
                        "device_class": "temperature",
                        "supported_features": 0,
                        # Entity-specific attributes (should be included)
                        "state_class": "measurement",
                        "last_reset": None,
                    }
                ),
            },
        ]

        _output_csv_format(states)

        captured = capsys.readouterr()
        lines = captured.out.strip().split("\n")
        headers = [h.strip() for h in lines[0].split(",")]

        # Default HA attributes should NOT be in headers
        assert "attr_friendly_name" not in headers
        assert "attr_icon" not in headers
        assert "attr_unit_of_measurement" not in headers
        assert "attr_device_class" not in headers
        assert "attr_supported_features" not in headers

        # Entity-specific attributes should be in headers
        assert "attr_state_class" in headers
        assert "attr_last_reset" in headers

    def test_markdown_output_basic(self, capsys):
        """Test markdown output basic structure."""
        states = [
            {
                "state": "20.0",
                "last_updated": "2024-01-01T12:00:00",
                "last_changed": "2024-01-01T12:00:00",
            }
        ]

        _output_markdown_format(states, "sensor.test", "24h", None)

        captured = capsys.readouterr()
        assert "History: sensor.test" in captured.out
        assert "Summary" in captured.out
        assert "1" in captured.out  # state count

    def test_markdown_output_with_numeric_stats(self, capsys):
        """Test markdown output with numeric statistics."""
        states = [
            {
                "state": "20.0",
                "last_updated": "2024-01-01T12:00:00",
                "last_changed": "2024-01-01T12:00:00",
            }
        ]
        stats_data = {
            "numeric": True,
            "min": 19.0,
            "max": 22.0,
            "avg": 20.5,
            "numeric_count": 10,
            "total_records": 10,
        }

        _output_markdown_format(states, "sensor.test", "24h", stats_data)

        captured = capsys.readouterr()
        assert "Statistics" in captured.out
        assert "Min" in captured.out
        assert "Max" in captured.out
        assert "Average" in captured.out

    def test_markdown_output_with_state_counts(self, capsys):
        """Test markdown output with state count statistics."""
        states = [
            {
                "state": "on",
                "last_updated": "2024-01-01T12:00:00",
                "last_changed": "2024-01-01T12:00:00",
            }
        ]
        stats_data = {
            "numeric": False,
            "state_counts": {"on": 8, "off": 2},
            "total_records": 10,
        }

        _output_markdown_format(states, "switch.test", "24h", stats_data)

        captured = capsys.readouterr()
        assert "Statistics" in captured.out
        assert "State Distribution" in captured.out

    def test_markdown_output_truncation(self, capsys):
        """Test markdown output truncates at 50 rows."""
        states = [
            {
                "state": str(i),
                "last_updated": f"2024-01-01T{i:02d}:00:00",
                "last_changed": f"2024-01-01T{i:02d}:00:00",
            }
            for i in range(60)
        ]

        _output_markdown_format(states, "sensor.test", "24h", None)

        captured = capsys.readouterr()
        assert "Showing 50 of 60" in captured.out


@pytest.mark.asyncio
class TestRunHistoryCommand:
    """Tests for _run_history_command."""

    async def test_database_unavailable(self):
        """Test handling when database is unavailable."""
        mock_db = AsyncMock()
        mock_db.is_connected = MagicMock(return_value=False)
        mock_db.get_connection_error = MagicMock(
            return_value=Exception("Connection failed")
        )

        with patch("ha_tools.commands.history.HaToolsConfig") as mock_config_class:
            mock_config = MagicMock()
            mock_config_class.load.return_value = mock_config

            with patch("ha_tools.commands.history.DatabaseManager") as mock_db_class:
                mock_db_class.return_value.__aenter__ = AsyncMock(return_value=mock_db)
                mock_db_class.return_value.__aexit__ = AsyncMock(return_value=None)

                result = await _run_history_command(
                    entity_id="sensor.test",
                    timeframe="24h",
                    limit=100,
                    stats=False,
                    format="markdown",
                )

                assert result == 4  # Database error exit code

    async def test_empty_results(self):
        """Test handling of empty results."""
        mock_db = AsyncMock()
        mock_db.is_connected = MagicMock(return_value=True)
        mock_db.get_entity_states.return_value = []

        with patch("ha_tools.commands.history.HaToolsConfig") as mock_config_class:
            mock_config = MagicMock()
            mock_config_class.load.return_value = mock_config

            with patch("ha_tools.commands.history.DatabaseManager") as mock_db_class:
                mock_db_class.return_value.__aenter__ = AsyncMock(return_value=mock_db)
                mock_db_class.return_value.__aexit__ = AsyncMock(return_value=None)

                result = await _run_history_command(
                    entity_id="sensor.nonexistent",
                    timeframe="24h",
                    limit=100,
                    stats=False,
                    format="markdown",
                )

                # Empty result is valid - should return 0
                assert result == 0

    async def test_invalid_format(self):
        """Test handling of invalid format."""
        with patch("ha_tools.commands.history.HaToolsConfig") as mock_config_class:
            mock_config = MagicMock()
            mock_config_class.load.return_value = mock_config

            result = await _run_history_command(
                entity_id="sensor.test",
                timeframe="24h",
                limit=100,
                stats=False,
                format="invalid",
            )

            assert result == 2  # Validation error exit code

    async def test_invalid_timeframe(self):
        """Test handling of invalid timeframe."""
        with patch("ha_tools.commands.history.HaToolsConfig") as mock_config_class:
            mock_config = MagicMock()
            mock_config_class.load.return_value = mock_config

            result = await _run_history_command(
                entity_id="sensor.test",
                timeframe="invalid",
                limit=100,
                stats=False,
                format="markdown",
            )

            assert result == 2  # Validation error exit code

    async def test_config_error(self):
        """Test handling of configuration error."""
        with patch("ha_tools.commands.history.HaToolsConfig") as mock_config_class:
            mock_config_class.load.side_effect = Exception("Config not found")

            result = await _run_history_command(
                entity_id="sensor.test",
                timeframe="24h",
                limit=100,
                stats=False,
                format="markdown",
            )

            assert result == 3  # Config error exit code

    async def test_successful_run(self, capsys):
        """Test successful history command run."""
        mock_db = AsyncMock()
        mock_db.is_connected = MagicMock(return_value=True)
        mock_db.get_entity_states.return_value = [
            {
                "state": "20.0",
                "last_updated": "2024-01-01T12:00:00",
                "last_changed": "2024-01-01T12:00:00",
            }
        ]

        with patch("ha_tools.commands.history.HaToolsConfig") as mock_config_class:
            mock_config = MagicMock()
            mock_config_class.load.return_value = mock_config

            with patch("ha_tools.commands.history.DatabaseManager") as mock_db_class:
                mock_db_class.return_value.__aenter__ = AsyncMock(return_value=mock_db)
                mock_db_class.return_value.__aexit__ = AsyncMock(return_value=None)

                result = await _run_history_command(
                    entity_id="sensor.test",
                    timeframe="24h",
                    limit=100,
                    stats=False,
                    format="markdown",
                )

                assert result == 0
                captured = capsys.readouterr()
                assert "History: sensor.test" in captured.out

    async def test_limit_minus_one(self):
        """Test that limit=-1 is treated as no limit."""
        mock_db = AsyncMock()
        mock_db.is_connected = MagicMock(return_value=True)
        mock_db.get_entity_states.return_value = []

        with patch("ha_tools.commands.history.HaToolsConfig") as mock_config_class:
            mock_config = MagicMock()
            mock_config_class.load.return_value = mock_config

            with patch("ha_tools.commands.history.DatabaseManager") as mock_db_class:
                mock_db_class.return_value.__aenter__ = AsyncMock(return_value=mock_db)
                mock_db_class.return_value.__aexit__ = AsyncMock(return_value=None)

                await _run_history_command(
                    entity_id="sensor.test",
                    timeframe="24h",
                    limit=-1,
                    stats=False,
                    format="markdown",
                )

                # Verify get_entity_states was called with limit=None
                mock_db.get_entity_states.assert_called_once()
                call_kwargs = mock_db.get_entity_states.call_args[1]
                assert call_kwargs["limit"] is None

    async def test_start_with_timeframe(self):
        """Test --start with --timeframe calculates end from start + timeframe."""
        mock_db = AsyncMock()
        mock_db.is_connected = MagicMock(return_value=True)
        mock_db.get_entity_states.return_value = []

        with patch("ha_tools.commands.history.HaToolsConfig") as mock_config_class:
            mock_config = MagicMock()
            mock_config_class.load.return_value = mock_config

            with patch("ha_tools.commands.history.DatabaseManager") as mock_db_class:
                mock_db_class.return_value.__aenter__ = AsyncMock(return_value=mock_db)
                mock_db_class.return_value.__aexit__ = AsyncMock(return_value=None)

                await _run_history_command(
                    entity_id="sensor.test",
                    timeframe="24h",
                    limit=100,
                    stats=False,
                    format="markdown",
                    start="2026-01-18",
                    end=None,
                )

                mock_db.get_entity_states.assert_called_once()
                call_kwargs = mock_db.get_entity_states.call_args[1]
                from datetime import datetime

                assert call_kwargs["start_time"] == datetime(2026, 1, 18, 0, 0, 0)
                assert call_kwargs["end_time"] == datetime(2026, 1, 19, 0, 0, 0)

    async def test_start_with_end(self):
        """Test --start with --end passes both to DB."""
        mock_db = AsyncMock()
        mock_db.is_connected = MagicMock(return_value=True)
        mock_db.get_entity_states.return_value = []

        with patch("ha_tools.commands.history.HaToolsConfig") as mock_config_class:
            mock_config = MagicMock()
            mock_config_class.load.return_value = mock_config

            with patch("ha_tools.commands.history.DatabaseManager") as mock_db_class:
                mock_db_class.return_value.__aenter__ = AsyncMock(return_value=mock_db)
                mock_db_class.return_value.__aexit__ = AsyncMock(return_value=None)

                await _run_history_command(
                    entity_id="sensor.test",
                    timeframe=None,
                    limit=100,
                    stats=False,
                    format="markdown",
                    start="2026-01-18",
                    end="2026-01-19",
                )

                mock_db.get_entity_states.assert_called_once()
                call_kwargs = mock_db.get_entity_states.call_args[1]
                from datetime import datetime

                assert call_kwargs["start_time"] == datetime(2026, 1, 18, 0, 0, 0)
                assert call_kwargs["end_time"] == datetime(2026, 1, 19, 0, 0, 0)

    async def test_start_only_no_timeframe(self):
        """Test --start without --timeframe or --end queries from start to now."""
        mock_db = AsyncMock()
        mock_db.is_connected = MagicMock(return_value=True)
        mock_db.get_entity_states.return_value = []

        with patch("ha_tools.commands.history.HaToolsConfig") as mock_config_class:
            mock_config = MagicMock()
            mock_config_class.load.return_value = mock_config

            with patch("ha_tools.commands.history.DatabaseManager") as mock_db_class:
                mock_db_class.return_value.__aenter__ = AsyncMock(return_value=mock_db)
                mock_db_class.return_value.__aexit__ = AsyncMock(return_value=None)

                await _run_history_command(
                    entity_id="sensor.test",
                    timeframe=None,
                    limit=100,
                    stats=False,
                    format="markdown",
                    start="2026-01-18",
                    end=None,
                )

                mock_db.get_entity_states.assert_called_once()
                call_kwargs = mock_db.get_entity_states.call_args[1]
                from datetime import datetime

                assert call_kwargs["start_time"] == datetime(2026, 1, 18, 0, 0, 0)
                assert call_kwargs["end_time"] is None

    async def test_end_without_start_errors(self):
        """Test --end without --start returns exit code 2."""
        with patch("ha_tools.commands.history.HaToolsConfig") as mock_config_class:
            mock_config = MagicMock()
            mock_config_class.load.return_value = mock_config

            result = await _run_history_command(
                entity_id="sensor.test",
                timeframe=None,
                limit=100,
                stats=False,
                format="markdown",
                start=None,
                end="2026-01-19",
            )

            assert result == 2

    async def test_end_with_explicit_timeframe_errors(self):
        """Test --start + --end + --timeframe returns exit code 2."""
        with patch("ha_tools.commands.history.HaToolsConfig") as mock_config_class:
            mock_config = MagicMock()
            mock_config_class.load.return_value = mock_config

            result = await _run_history_command(
                entity_id="sensor.test",
                timeframe="7d",
                limit=100,
                stats=False,
                format="markdown",
                start="2026-01-18",
                end="2026-01-19",
            )

            assert result == 2

    async def test_start_after_end_errors(self):
        """Test --start after --end returns exit code 2."""
        with patch("ha_tools.commands.history.HaToolsConfig") as mock_config_class:
            mock_config = MagicMock()
            mock_config_class.load.return_value = mock_config

            result = await _run_history_command(
                entity_id="sensor.test",
                timeframe=None,
                limit=100,
                stats=False,
                format="markdown",
                start="2026-01-19",
                end="2026-01-18",
            )

            assert result == 2

    async def test_no_start_no_end_default_timeframe(self):
        """Test no --start, no --end, no --timeframe uses 24h default."""
        mock_db = AsyncMock()
        mock_db.is_connected = MagicMock(return_value=True)
        mock_db.get_entity_states.return_value = []

        with patch("ha_tools.commands.history.HaToolsConfig") as mock_config_class:
            mock_config = MagicMock()
            mock_config_class.load.return_value = mock_config

            with patch("ha_tools.commands.history.DatabaseManager") as mock_db_class:
                mock_db_class.return_value.__aenter__ = AsyncMock(return_value=mock_db)
                mock_db_class.return_value.__aexit__ = AsyncMock(return_value=None)

                with patch("ha_tools.commands.history.datetime") as mock_dt:
                    from datetime import datetime, timedelta

                    fake_now = datetime(2026, 2, 1, 12, 0, 0)
                    mock_dt.now.return_value = fake_now
                    mock_dt.strptime = datetime.strptime

                    await _run_history_command(
                        entity_id="sensor.test",
                        timeframe=None,
                        limit=100,
                        stats=False,
                        format="markdown",
                        start=None,
                        end=None,
                    )

                    mock_db.get_entity_states.assert_called_once()
                    call_kwargs = mock_db.get_entity_states.call_args[1]
                    assert call_kwargs["start_time"] == fake_now - timedelta(hours=24)
                    assert call_kwargs["end_time"] is None

    async def test_output_message_with_date_range(self, capsys):
        """Test that output says 'from ... to ...' for date range queries."""
        mock_db = AsyncMock()
        mock_db.is_connected = MagicMock(return_value=True)
        mock_db.get_entity_states.return_value = [
            {
                "state": "20.0",
                "last_updated": "2026-01-18T12:00:00",
                "last_changed": "2026-01-18T12:00:00",
            }
        ]

        with patch("ha_tools.commands.history.HaToolsConfig") as mock_config_class:
            mock_config = MagicMock()
            mock_config_class.load.return_value = mock_config

            with patch("ha_tools.commands.history.DatabaseManager") as mock_db_class:
                mock_db_class.return_value.__aenter__ = AsyncMock(return_value=mock_db)
                mock_db_class.return_value.__aexit__ = AsyncMock(return_value=None)

                result = await _run_history_command(
                    entity_id="sensor.test",
                    timeframe=None,
                    limit=100,
                    stats=False,
                    format="markdown",
                    start="2026-01-18",
                    end="2026-01-19",
                )

                assert result == 0
                captured = capsys.readouterr()
                assert "from 2026-01-18" in captured.out
                assert "to 2026-01-19" in captured.out
