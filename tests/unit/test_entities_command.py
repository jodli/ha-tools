"""
Unit tests for ha-tools entities command.

Tests entity discovery, filtering, history retrieval, and output formatting.
"""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from ha_tools.commands.entities import (
    _run_entities_command, _parse_include_options,
    _get_entities, _output_results, _output_table_format, _output_markdown_format
)
from ha_tools.lib.utils import parse_timeframe


class TestEntitiesCommand:
    """Test entities command functionality."""

    

    
    def test_parse_include_options_valid(self):
        """Test parsing valid include options."""
        options = _parse_include_options("state,history,relations")
        assert options == {"state", "history", "relations"}

    def test_parse_include_options_with_metadata(self):
        """Test parsing include options with metadata."""
        options = _parse_include_options("state,metadata")
        assert options == {"state", "metadata"}

    def test_parse_include_options_empty(self):
        """Test parsing empty include options."""
        options = _parse_include_options("")
        assert options == set()

    def test_parse_include_options_none(self):
        """Test parsing None include options."""
        options = _parse_include_options(None)
        assert options == set()

    def test_parse_include_options_case_insensitive(self):
        """Test parsing include options with mixed case."""
        options = _parse_include_options("STATE,History")
        assert options == {"state", "history"}

    def test_parse_include_options_invalid_filtered(self):
        """Test parsing include options with invalid options filtered out."""
        options = _parse_include_options("state,invalid,history,fake")
        assert options == {"state", "history"}

    def test_parse_include_options_with_spaces(self):
        """Test parsing include options with extra spaces."""
        options = _parse_include_options(" state , history , relations ")
        assert options == {"state", "history", "relations"}

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

    def test_parse_timeframe_minutes(self):
        """Test parsing timeframe in minutes."""
        base_time = datetime(2024, 1, 1, 12, 0, 0)
        with patch('ha_tools.lib.utils.datetime') as mock_datetime:
            mock_datetime.now.return_value = base_time

            result = parse_timeframe("30m")
            expected = base_time - timedelta(minutes=30)
            assert result == expected

    def test_parse_timeframe_weeks(self):
        """Test parsing timeframe in weeks."""
        base_time = datetime(2024, 1, 1, 12, 0, 0)
        with patch('ha_tools.lib.utils.datetime') as mock_datetime:
            mock_datetime.now.return_value = base_time

            result = parse_timeframe("2w")
            expected = base_time - timedelta(weeks=2)
            assert result == expected

    def test_parse_timeframe_invalid(self):
        """Test parsing invalid timeframe."""
        with pytest.raises(ValueError, match="Invalid timeframe format"):
            parse_timeframe("invalid")

    @pytest.mark.asyncio
    async def test_get_entities_all(self):
        """Test getting all entities without search."""
        mock_registry = AsyncMock()
        mock_db = AsyncMock()
        mock_api = AsyncMock()

        mock_registry._entity_registry = [
            {
                "entity_id": "sensor.temperature",
                "friendly_name": "Temperature",
                "device_class": "temperature"
            },
            {
                "entity_id": "switch.light",
                "friendly_name": "Light",
                "disabled_by": None
            }
        ]

        entities = await _get_entities(
            mock_registry, mock_db, mock_api,
            search=None,
            include_options=set(),
            history_timeframe=None,
            limit=None
        )

        assert len(entities) == 2
        assert entities[0]["entity_id"] == "sensor.temperature"
        assert entities[1]["entity_id"] == "switch.light"

    

    @pytest.mark.asyncio
    async def test_get_entities_with_state(self):
        """Test getting entities with current state."""
        mock_registry = AsyncMock()
        mock_db = AsyncMock()
        mock_api = AsyncMock()

        mock_registry._entity_registry = [
            {
                "entity_id": "sensor.temperature",
                "friendly_name": "Temperature"
            }
        ]

        mock_api.get_entity_state.return_value = {
            "entity_id": "sensor.temperature",
            "state": "20.5",
            "attributes": {"unit_of_measurement": "°C"},
            "last_changed": "2024-01-01T12:00:00+00:00",
            "last_updated": "2024-01-01T12:00:00+00:00"
        }

        entities = await _get_entities(
            mock_registry, mock_db, mock_api,
            search=None,
            include_options={"state"},
            history_timeframe=None,
            limit=None
        )

        assert len(entities) == 1
        assert entities[0]["current_state"] == "20.5"
        assert entities[0]["last_changed"] == "2024-01-01T12:00:00+00:00"
        assert entities[0]["attributes"]["unit_of_measurement"] == "°C"

    @pytest.mark.asyncio
    async def test_get_entities_with_history(self):
        """Test getting entities with historical data."""
        mock_registry = AsyncMock()
        mock_db = AsyncMock()
        mock_api = AsyncMock()

        mock_registry._entity_registry = [
            {
                "entity_id": "sensor.temperature",
                "friendly_name": "Temperature"
            }
        ]

        history_timeframe = datetime.now() - timedelta(hours=24)
        mock_db.get_entity_states.return_value = [
            {
                "entity_id": "sensor.temperature",
                "state": "19.0",
                "last_changed": "2024-01-01T11:00:00+00:00"
            },
            {
                "entity_id": "sensor.temperature",
                "state": "20.5",
                "last_changed": "2024-01-01T12:00:00+00:00"
            }
        ]

        entities = await _get_entities(
            mock_registry, mock_db, mock_api,
            search=None,
            include_options={"history"},
            history_timeframe=history_timeframe,
            limit=None
        )

        assert len(entities) == 1
        assert entities[0]["history_count"] == 2
        assert len(entities[0]["history"]) == 2
        assert entities[0]["history"][0]["state"] == "19.0"

    

    @pytest.mark.asyncio
    async def test_get_entities_with_metadata(self):
        """Test getting entities with full metadata."""
        mock_registry = AsyncMock()
        mock_db = AsyncMock()
        mock_api = AsyncMock()

        full_metadata = {
            "entity_id": "sensor.temperature",
            "friendly_name": "Temperature",
            "device_class": "temperature",
            "unit_of_measurement": "°C",
            "disabled_by": None,
            "hidden_by": None,
            "original_issue_id": None
        }

        mock_registry._entity_registry = [full_metadata]

        entities = await _get_entities(
            mock_registry, mock_db, mock_api,
            search=None,
            include_options={"metadata"},
            history_timeframe=None,
            limit=None
        )

        assert len(entities) == 1
        assert entities[0]["full_metadata"] == full_metadata

    @pytest.mark.asyncio
    async def test_get_entities_with_limit(self):
        """Test getting entities with limit applied."""
        mock_registry = AsyncMock()
        mock_db = AsyncMock()
        mock_api = AsyncMock()

        # Create 5 entities
        entities_list = [
            {"entity_id": f"sensor.test_{i}", "friendly_name": f"Test {i}"}
            for i in range(5)
        ]
        mock_registry._entity_registry = entities_list

        entities = await _get_entities(
            mock_registry, mock_db, mock_api,
            search=None,
            include_options=set(),
            history_timeframe=None,
            limit=3
        )

        assert len(entities) == 3
        assert entities[0]["entity_id"] == "sensor.test_0"
        assert entities[2]["entity_id"] == "sensor.test_2"

    @pytest.mark.asyncio
    async def test_get_entities_state_api_error(self):
        """Test handling API errors when getting entity state."""
        mock_registry = AsyncMock()
        mock_db = AsyncMock()
        mock_api = AsyncMock()

        mock_registry._entity_registry = [
            {
                "entity_id": "sensor.temperature",
                "friendly_name": "Temperature"
            }
        ]

        mock_api.get_entity_state.side_effect = Exception("API Error")

        entities = await _get_entities(
            mock_registry, mock_db, mock_api,
            search=None,
            include_options={"state"},
            history_timeframe=None,
            limit=None
        )

        # Should still return entity, but without state data
        assert len(entities) == 1
        assert "current_state" not in entities[0]

    @pytest.mark.asyncio
    async def test_get_entities_history_db_error(self):
        """Test handling database errors when getting history."""
        mock_registry = AsyncMock()
        mock_db = AsyncMock()
        mock_api = AsyncMock()

        mock_registry._entity_registry = [
            {
                "entity_id": "sensor.temperature",
                "friendly_name": "Temperature"
            }
        ]

        history_timeframe = datetime.now() - timedelta(hours=24)
        mock_db.get_entity_states.side_effect = Exception("Database Error")

        entities = await _get_entities(
            mock_registry, mock_db, mock_api,
            search=None,
            include_options={"history"},
            history_timeframe=history_timeframe,
            limit=None
        )

        # Should still return entity with error info instead of silently failing
        assert len(entities) == 1
        assert entities[0]["history"] == []
        assert entities[0]["history_count"] == 0
        assert entities[0]["history_error"] == "Database Error"

    @pytest.mark.asyncio
    async def test_output_results_markdown(self):
        """Test outputting results in markdown format."""
        entities_data = [
            {
                "entity_id": "sensor.temperature",
                "friendly_name": "Temperature",
                "domain": "sensor",
                "device_class": "temperature",
                "unit_of_measurement": "°C"
            }
        ]

        with patch('builtins.print') as mock_print:
            await _output_results(entities_data, "markdown", set())

            mock_print.assert_called_once()
            call_args = mock_print.call_args[0][0]
            assert "Entity Discovery Results" in call_args
            assert "sensor.temperature" in call_args

    @pytest.mark.asyncio
    async def test_output_results_json(self):
        """Test outputting results in JSON format."""
        entities_data = [
            {
                "entity_id": "sensor.temperature",
                "friendly_name": "Temperature",
                "domain": "sensor"
            }
        ]

        with patch('builtins.print') as mock_print:
            await _output_results(entities_data, "json", set())

            mock_print.assert_called_once()
            call_args = mock_print.call_args[0][0]
            # Check that it's valid JSON
            import json
            parsed = json.loads(call_args)
            assert len(parsed) == 1
            assert parsed[0]["entity_id"] == "sensor.temperature"

    @pytest.mark.asyncio
    async def test_output_results_table(self):
        """Test outputting results in table format."""
        entities_data = [
            {
                "entity_id": "sensor.temperature",
                "friendly_name": "Temperature",
                "domain": "sensor",
                "current_state": "20.5",
                "history_count": 5
            }
        ]

        with patch('ha_tools.commands.entities._output_table_format') as mock_table:
            await _output_results(entities_data, "table", {"state", "history"})

            mock_table.assert_called_once_with(entities_data, {"state", "history"})

    def test_output_table_format_empty(self):
        """Test table format with no entities."""
        with patch('builtins.print') as mock_print:
            _output_table_format([], set())
            mock_print.assert_called_with("No entities found.")

    def test_output_table_format_basic(self):
        """Test basic table format output."""
        entities_data = [
            {
                "entity_id": "sensor.temperature",
                "friendly_name": "Temperature",
                "domain": "sensor",
                "current_state": "20.5"
            }
        ]

        with patch('rich.console.Console.print') as mock_console_print:
            _output_table_format(entities_data, set())

            mock_console_print.assert_called_once()
            # Check that a table object was printed
            call_args = mock_console_print.call_args[0][0]
            assert hasattr(call_args, 'add_column')  # Rich table object

    def test_output_table_format_with_history(self):
        """Test table format with history column."""
        entities_data = [
            {
                "entity_id": "sensor.temperature",
                "friendly_name": "Temperature",
                "domain": "sensor",
                "current_state": "20.5",
                "history_count": 10
            }
        ]

        with patch('rich.console.Console.print') as mock_console_print:
            _output_table_format(entities_data, {"history"})

            mock_console_print.assert_called_once()

    def test_output_markdown_format_empty(self):
        """Test markdown format with no entities."""
        entities_data = []

        with patch('builtins.print') as mock_print:
            _output_markdown_format(entities_data, set())

            mock_print.assert_called_once()
            call_args = mock_print.call_args[0][0]
            assert "No Entities Found" in call_args

    def test_output_markdown_format_basic(self):
        """Test basic markdown format output."""
        entities_data = [
            {
                "entity_id": "sensor.temperature",
                "friendly_name": "Temperature",
                "domain": "sensor",
                "device_class": "temperature",
                "unit_of_measurement": "°C"
            }
        ]

        with patch('builtins.print') as mock_print:
            _output_markdown_format(entities_data, set())

            mock_print.assert_called_once()
            call_args = mock_print.call_args[0][0]
            assert "Entity Discovery Results" in call_args
            assert "Found **1** entities" in call_args
            assert "sensor.temperature" in call_args

    def test_output_markdown_format_with_includes(self):
        """Test markdown format with include options."""
        entities_data = [
            {
                "entity_id": "sensor.temperature",
                "friendly_name": "Temperature",
                "domain": "sensor",
                "device_class": "temperature",
                "unit_of_measurement": "°C",
                "current_state": "20.5",
                "last_changed": "2024-01-01T12:00:00+00:00",
                "history_count": 15,
                "relations": {
                    "area": {"name": "Living Room"},
                    "device": {"name": "Weather Station", "manufacturer": "Test Corp"}
                }
            }
        ]

        with patch('builtins.print') as mock_print:
            _output_markdown_format(entities_data, {"state", "history", "relations"})

            mock_print.assert_called_once()
            call_args = mock_print.call_args[0][0]
            assert "Found **1** entities with history data with current state with relations" in call_args
            assert "Current State" in call_args
            assert "History Count" in call_args
            assert "Detailed Information" in call_args


class TestMultiPatternSearch:
    """Test multi-pattern search functionality."""

    def test_search_single_pattern(self):
        """Test single pattern search (backward compatibility)."""
        from ha_tools.lib.registry import RegistryManager
        from unittest.mock import MagicMock

        registry = MagicMock(spec=RegistryManager)
        registry._entity_registry = [
            {"entity_id": "sensor.temperature", "friendly_name": "Temperature"},
            {"entity_id": "sensor.humidity", "friendly_name": "Humidity"},
            {"entity_id": "switch.light", "friendly_name": "Light"},
        ]

        # Call the real methods
        registry._pattern_matches = RegistryManager._pattern_matches.__get__(registry)
        registry.search_entities = RegistryManager.search_entities.__get__(registry)

        results = registry.search_entities("temp")
        assert len(results) == 1
        assert results[0]["entity_id"] == "sensor.temperature"

    def test_search_multiple_patterns(self):
        """Test multiple patterns with | separator."""
        from ha_tools.lib.registry import RegistryManager
        from unittest.mock import MagicMock

        registry = MagicMock(spec=RegistryManager)
        registry._entity_registry = [
            {"entity_id": "sensor.temperature", "friendly_name": "Temperature"},
            {"entity_id": "sensor.humidity", "friendly_name": "Humidity"},
            {"entity_id": "switch.light", "friendly_name": "Light"},
        ]

        registry._pattern_matches = RegistryManager._pattern_matches.__get__(registry)
        registry.search_entities = RegistryManager.search_entities.__get__(registry)

        results = registry.search_entities("temp|humidity")
        assert len(results) == 2
        entity_ids = [r["entity_id"] for r in results]
        assert "sensor.temperature" in entity_ids
        assert "sensor.humidity" in entity_ids

    def test_search_patterns_with_spaces(self):
        """Test patterns with spaces around |."""
        from ha_tools.lib.registry import RegistryManager
        from unittest.mock import MagicMock

        registry = MagicMock(spec=RegistryManager)
        registry._entity_registry = [
            {"entity_id": "sensor.living_room_temp", "friendly_name": "Living Room"},
            {"entity_id": "sensor.bedroom_temp", "friendly_name": "Bedroom"},
        ]

        registry._pattern_matches = RegistryManager._pattern_matches.__get__(registry)
        registry.search_entities = RegistryManager.search_entities.__get__(registry)

        results = registry.search_entities("living | bedroom")
        assert len(results) == 2

    def test_search_empty_patterns_filtered(self):
        """Test that empty patterns are filtered out."""
        from ha_tools.lib.registry import RegistryManager
        from unittest.mock import MagicMock

        registry = MagicMock(spec=RegistryManager)
        registry._entity_registry = [
            {"entity_id": "sensor.temperature", "friendly_name": "Temperature"},
        ]

        registry._pattern_matches = RegistryManager._pattern_matches.__get__(registry)
        registry.search_entities = RegistryManager.search_entities.__get__(registry)

        # Empty patterns between pipes should be ignored
        results = registry.search_entities("|temp|")
        assert len(results) == 1
        assert results[0]["entity_id"] == "sensor.temperature"

    def test_search_all_empty_patterns(self):
        """Test that all-empty patterns return empty list."""
        from ha_tools.lib.registry import RegistryManager
        from unittest.mock import MagicMock

        registry = MagicMock(spec=RegistryManager)
        registry._entity_registry = [
            {"entity_id": "sensor.temperature", "friendly_name": "Temperature"},
        ]

        registry._pattern_matches = RegistryManager._pattern_matches.__get__(registry)
        registry.search_entities = RegistryManager.search_entities.__get__(registry)

        results = registry.search_entities("|||")
        assert len(results) == 0

    def test_search_case_insensitive(self):
        """Test that multi-pattern search is case insensitive."""
        from ha_tools.lib.registry import RegistryManager
        from unittest.mock import MagicMock

        registry = MagicMock(spec=RegistryManager)
        registry._entity_registry = [
            {"entity_id": "sensor.Temperature", "friendly_name": "TEMP Sensor"},
        ]

        registry._pattern_matches = RegistryManager._pattern_matches.__get__(registry)
        registry.search_entities = RegistryManager.search_entities.__get__(registry)

        results = registry.search_entities("TEMP|temperature")
        assert len(results) == 1

    def test_search_no_duplicates(self):
        """Test that entities matching multiple patterns appear only once."""
        from ha_tools.lib.registry import RegistryManager
        from unittest.mock import MagicMock

        registry = MagicMock(spec=RegistryManager)
        registry._entity_registry = [
            {"entity_id": "sensor.temp_humidity", "friendly_name": "Temp and Humidity"},
        ]

        registry._pattern_matches = RegistryManager._pattern_matches.__get__(registry)
        registry.search_entities = RegistryManager.search_entities.__get__(registry)

        # Entity matches both patterns but should only appear once
        results = registry.search_entities("temp|humidity")
        assert len(results) == 1


class TestWildcardSearch:
    """Test wildcard (*) search functionality."""

    def test_wildcard_basic(self):
        """Test basic wildcard matching."""
        from ha_tools.lib.registry import RegistryManager
        from unittest.mock import MagicMock

        registry = MagicMock(spec=RegistryManager)
        registry._entity_registry = [
            {"entity_id": "script.wohnzimmer_saugen", "friendly_name": "Vacuum Living Room"},
            {"entity_id": "script.kueche_saugen", "friendly_name": "Vacuum Kitchen"},
            {"entity_id": "sensor.temperature", "friendly_name": "Temperature"},
        ]

        registry._pattern_matches = RegistryManager._pattern_matches.__get__(registry)
        registry.search_entities = RegistryManager.search_entities.__get__(registry)

        results = registry.search_entities("script.*saugen")
        assert len(results) == 2
        entity_ids = [r["entity_id"] for r in results]
        assert "script.wohnzimmer_saugen" in entity_ids
        assert "script.kueche_saugen" in entity_ids

    def test_wildcard_at_end(self):
        """Test wildcard at end of pattern."""
        from ha_tools.lib.registry import RegistryManager
        from unittest.mock import MagicMock

        registry = MagicMock(spec=RegistryManager)
        registry._entity_registry = [
            {"entity_id": "sensor.temperature_living", "friendly_name": "Temp Living"},
            {"entity_id": "sensor.temperature_bedroom", "friendly_name": "Temp Bedroom"},
            {"entity_id": "sensor.humidity", "friendly_name": "Humidity"},
        ]

        registry._pattern_matches = RegistryManager._pattern_matches.__get__(registry)
        registry.search_entities = RegistryManager.search_entities.__get__(registry)

        results = registry.search_entities("sensor.temperature*")
        assert len(results) == 2

    def test_wildcard_at_start(self):
        """Test wildcard at start of pattern."""
        from ha_tools.lib.registry import RegistryManager
        from unittest.mock import MagicMock

        registry = MagicMock(spec=RegistryManager)
        registry._entity_registry = [
            {"entity_id": "sensor.living_temperature", "friendly_name": "Living Temp"},
            {"entity_id": "sensor.bedroom_temperature", "friendly_name": "Bedroom Temp"},
            {"entity_id": "sensor.humidity", "friendly_name": "Humidity"},
        ]

        registry._pattern_matches = RegistryManager._pattern_matches.__get__(registry)
        registry.search_entities = RegistryManager.search_entities.__get__(registry)

        results = registry.search_entities("*temperature")
        assert len(results) == 2

    def test_wildcard_multiple(self):
        """Test multiple wildcards in pattern."""
        from ha_tools.lib.registry import RegistryManager
        from unittest.mock import MagicMock

        registry = MagicMock(spec=RegistryManager)
        registry._entity_registry = [
            {"entity_id": "sensor.living_room_temperature", "friendly_name": "Living Temp"},
            {"entity_id": "sensor.bedroom_temperature", "friendly_name": "Bedroom Temp"},
            {"entity_id": "switch.living_room_light", "friendly_name": "Living Light"},
        ]

        registry._pattern_matches = RegistryManager._pattern_matches.__get__(registry)
        registry.search_entities = RegistryManager.search_entities.__get__(registry)

        results = registry.search_entities("*living*temp*")
        assert len(results) == 1
        assert results[0]["entity_id"] == "sensor.living_room_temperature"

    def test_wildcard_with_or(self):
        """Test wildcard combined with OR patterns."""
        from ha_tools.lib.registry import RegistryManager
        from unittest.mock import MagicMock

        registry = MagicMock(spec=RegistryManager)
        registry._entity_registry = [
            {"entity_id": "script.wohnzimmer_saugen", "friendly_name": "Vacuum Living"},
            {"entity_id": "script.kueche_kochen", "friendly_name": "Cook Kitchen"},
            {"entity_id": "sensor.temperature", "friendly_name": "Temperature"},
        ]

        registry._pattern_matches = RegistryManager._pattern_matches.__get__(registry)
        registry.search_entities = RegistryManager.search_entities.__get__(registry)

        results = registry.search_entities("script.*saugen|script.*kochen")
        assert len(results) == 2
        entity_ids = [r["entity_id"] for r in results]
        assert "script.wohnzimmer_saugen" in entity_ids
        assert "script.kueche_kochen" in entity_ids

    def test_no_wildcard_still_works(self):
        """Test that patterns without wildcards still work (backward compatibility)."""
        from ha_tools.lib.registry import RegistryManager
        from unittest.mock import MagicMock

        registry = MagicMock(spec=RegistryManager)
        registry._entity_registry = [
            {"entity_id": "sensor.temperature", "friendly_name": "Temperature"},
            {"entity_id": "sensor.humidity", "friendly_name": "Humidity"},
        ]

        registry._pattern_matches = RegistryManager._pattern_matches.__get__(registry)
        registry.search_entities = RegistryManager.search_entities.__get__(registry)

        results = registry.search_entities("temp")
        assert len(results) == 1
        assert results[0]["entity_id"] == "sensor.temperature"

    def test_pattern_matches_helper(self):
        """Test the _pattern_matches helper directly."""
        from ha_tools.lib.registry import RegistryManager
        from unittest.mock import MagicMock

        registry = MagicMock(spec=RegistryManager)
        registry._pattern_matches = RegistryManager._pattern_matches.__get__(registry)

        # Substring match (no wildcard)
        assert registry._pattern_matches("temp", "sensor.temperature")
        assert not registry._pattern_matches("humid", "sensor.temperature")

        # Wildcard matches
        assert registry._pattern_matches("script.*saugen", "script.wohnzimmer_saugen")
        assert registry._pattern_matches("*vacuum*", "robot_vacuum_cleaner")
        assert registry._pattern_matches("sensor.*temp*", "sensor.living_temperature")

        # Wildcard non-matches
        assert not registry._pattern_matches("script.*saugen", "script.wohnzimmer_kochen")
        assert not registry._pattern_matches("sensor.temp*", "switch.temperature")

