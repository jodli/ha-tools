"""
Unit tests for ha-tools errors command.

Tests error analysis, log parsing, and correlation functionality.
"""

import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from ha_tools.commands.errors import (
    _run_errors_command, _filter_errors,
    _extract_entity_references, _calculate_correlation_strength
)
from ha_tools.lib.utils import parse_timeframe


class TestErrorsCommand:
    """Test errors command functionality."""

    @pytest.mark.asyncio
    async def test_run_errors_command_success(self, test_config):
        """Test successful errors command execution."""
        with patch('ha_tools.commands.errors.DatabaseManager') as mock_db_class, \
             patch('ha_tools.commands.errors.HomeAssistantAPI') as mock_api_class, \
             patch('ha_tools.commands.errors.RegistryManager') as mock_registry_class, \
             patch('ha_tools.commands.errors._collect_errors') as mock_collect, \
             patch('ha_tools.commands.errors._output_errors') as mock_output:

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
                "database_errors": [],
                "correlations": []
            }

            result = await _run_errors_command(
                current=False,
                log="24h",
                entity=None,
                integration=None,
                correlation=False,
                format="markdown"
            )

            assert result == 0
            mock_collect.assert_called_once()
            mock_output.assert_called_once()

    def test_parse_timeframe_hours(self):
        """Test parsing timeframe in hours."""
        base_time = datetime(2024, 1, 1, 12, 0, 0)
        with patch('ha_tools.lib.utils.datetime') as mock_datetime:
            mock_datetime.now.return_value = base_time

            result = parse_timeframe("24h")
            expected = base_time - timedelta(hours=24)
            assert result == expected

    def test_parse_timeframe_days(self):
        """Test parsing timeframe in days."""
        base_time = datetime(2024, 1, 1, 12, 0, 0)
        with patch('ha_tools.lib.utils.datetime') as mock_datetime:
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
            "General system error"
        ]

        filtered = _filter_errors(errors, entity="temperature", integration=None)
        assert len(filtered) == 1
        assert "sensor.temperature" in filtered[0]

    def test_filter_errors_integration(self):
        """Test filtering errors by integration."""
        errors = [
            "KNX communication error",
            "Zigbee device unavailable",
            "MQTT connection failed"
        ]

        filtered = _filter_errors(errors, entity=None, integration="mqtt")
        assert len(filtered) == 1
        assert "MQTT" in filtered[0]

    def test_filter_errors_both(self):
        """Test filtering errors by both entity and integration."""
        errors = [
            "MQTT sensor.temperature error",
            "KNX sensor.temperature error",
            "MQTT switch.light error"
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


