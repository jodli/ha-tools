"""
Unit tests for ha-tools logs command.

Tests log analysis, log parsing, and correlation functionality.
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ha_tools.commands.logs import (
    _calculate_correlation_strength,
    _extract_entity_references,
    _filter_errors,
    _parse_level_options,
    _run_logs_command,
)
from ha_tools.lib.utils import parse_timeframe


class TestLogsCommand:
    """Test logs command functionality."""

    @pytest.mark.asyncio
    async def test_run_logs_command_success(self, test_config):
        """Test successful logs command execution."""
        with (
            patch("ha_tools.commands.logs.DatabaseManager") as mock_db_class,
            patch("ha_tools.commands.logs.HomeAssistantAPI") as mock_api_class,
            patch("ha_tools.commands.logs.RegistryManager") as mock_registry_class,
            patch("ha_tools.commands.logs._collect_errors") as mock_collect,
            patch("ha_tools.commands.logs._output_errors") as mock_output,
        ):
            # Mock database and API
            mock_db = AsyncMock()
            # Mock sync methods with MagicMock to avoid unawaited coroutines
            mock_db.is_connected = MagicMock(return_value=True)
            mock_db.get_connection_error = MagicMock(return_value=None)
            mock_db_class.return_value.__aenter__.return_value = mock_db
            mock_api = AsyncMock()
            mock_api_class.return_value.__aenter__.return_value = mock_api

            # Mock registry
            mock_registry = MagicMock()
            mock_registry_class.return_value = mock_registry

            # Mock error collection
            mock_collect.return_value = {
                "api_errors": [],
                "log_errors": [],
                "correlations": [],
            }

            result = await _run_logs_command(
                current=False,
                log="24h",
                levels={"error", "warning"},
                entity=None,
                integration=None,
                correlation=False,
                format="markdown",
            )

            assert result == 0
            mock_collect.assert_called_once()
            mock_output.assert_called_once()

    def test_parse_timeframe_hours(self):
        """Test parsing timeframe in hours."""
        base_time = datetime(2024, 1, 1, 12, 0, 0)
        with patch("ha_tools.lib.utils.datetime") as mock_datetime:
            mock_datetime.now.return_value = base_time

            result = parse_timeframe("24h")
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

    def test_parse_timeframe_invalid(self):
        """Test parsing invalid timeframe."""
        with pytest.raises(ValueError, match="Invalid timeframe format"):
            parse_timeframe("invalid")

    def test_filter_errors_entity(self):
        """Test filtering errors by entity pattern."""
        errors = [
            "Error in sensor.temperature: reading failed",
            "Error in switch.light: connection lost",
            "General system error",
        ]

        filtered = _filter_errors(errors, entity="temperature", integration=None)
        assert len(filtered) == 1
        assert "sensor.temperature" in filtered[0]

    def test_filter_errors_integration(self):
        """Test filtering errors by integration."""
        errors = [
            "KNX communication error",
            "Zigbee device unavailable",
            "MQTT connection failed",
        ]

        filtered = _filter_errors(errors, entity=None, integration="mqtt")
        assert len(filtered) == 1
        assert "MQTT" in filtered[0]

    def test_filter_errors_both(self):
        """Test filtering errors by both entity and integration."""
        errors = [
            "MQTT sensor.temperature error",
            "KNX sensor.temperature error",
            "MQTT switch.light error",
        ]

        filtered = _filter_errors(errors, entity="temperature", integration="mqtt")
        assert len(filtered) == 1
        assert "MQTT sensor.temperature error" in filtered[0]

    def test_filter_errors_no_filters(self):
        """Test error filtering with no filters."""
        errors = ["Error 1", "Error 2", "Error 3"]
        filtered = _filter_errors(errors, entity=None, integration=None)
        assert filtered == errors

    def test_extract_entity_references(self):
        """Test extracting entity IDs from error text."""
        text = "Error in sensor.temperature and switch.light, also sensor.humidity"
        entities = _extract_entity_references(text)

        assert "sensor.temperature" in entities
        assert "switch.light" in entities
        assert "sensor.humidity" in entities

    def test_extract_entity_references_various_patterns(self):
        """Test extracting entity IDs with various patterns."""
        text = """
        Entity sensor.temperature is not responding
        Failed to update switch.kitchen_light
        Automation automation.heating_control failed
        Binary sensor binary_sensor.motion detected
        """
        entities = _extract_entity_references(text)

        assert "sensor.temperature" in entities
        assert "switch.kitchen_light" in entities
        assert "automation.heating_control" in entities
        assert "binary_sensor.motion" in entities

    def test_extract_entity_references_invalid(self):
        """Test filtering invalid entity references."""
        text = "Error in abc and xyz, valid sensor.temp, invalid short"
        entities = _extract_entity_references(text)

        # Should only include valid-looking entity IDs
        assert "sensor.temp" in entities
        assert "abc" not in entities
        assert "xyz" not in entities
        assert "short" not in entities

    def test_calculate_correlation_strength_no_changes(self):
        """Test correlation strength with no state changes."""
        error_time = datetime(2024, 1, 1, 12, 0, 0)
        state_changes = []

        strength = _calculate_correlation_strength(error_time, state_changes)
        assert strength == 0.0


class TestParseLevelOptions:
    """Test level option parsing functionality."""

    def test_parse_level_options_default(self):
        """Test default level options when None provided."""
        result = _parse_level_options(None)
        assert result == {"error", "warning"}

    def test_parse_level_options_single(self):
        """Test parsing single level option."""
        result = _parse_level_options("error")
        assert result == {"error"}

    def test_parse_level_options_multiple(self):
        """Test parsing multiple level options."""
        result = _parse_level_options("error,warning,critical")
        assert result == {"error", "warning", "critical"}

    def test_parse_level_options_with_spaces(self):
        """Test parsing level options with spaces."""
        result = _parse_level_options("error , warning , critical")
        assert result == {"error", "warning", "critical"}

    def test_parse_level_options_invalid_filtered(self):
        """Test that invalid options are filtered out."""
        result = _parse_level_options("error,invalid,warning")
        assert result == {"error", "warning"}
        assert "invalid" not in result

    def test_parse_level_options_case_insensitive(self):
        """Test that level options are case insensitive."""
        result = _parse_level_options("ERROR,Warning,CRITICAL")
        assert result == {"error", "warning", "critical"}

    def test_parse_level_options_all_levels(self):
        """Test parsing all valid level options."""
        result = _parse_level_options("error,warning,critical,info,debug")
        assert result == {"error", "warning", "critical", "info", "debug"}

    def test_parse_level_options_empty_string(self):
        """Test parsing empty string returns default (same as None)."""
        result = _parse_level_options("")
        # Empty string is falsy, so returns default {"error", "warning"}
        assert result == {"error", "warning"}
