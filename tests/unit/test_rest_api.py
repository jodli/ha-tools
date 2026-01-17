"""
Unit tests for ha-tools REST API client.

Tests Home Assistant API authentication, connection handling, and data retrieval.
"""

import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ha_tools.config import HomeAssistantConfig
from ha_tools.lib.rest_api import HomeAssistantAPI


def create_mock_response(status=200, json_data=None, text_data=None):
    """Create a properly mocked async response."""
    mock_response = AsyncMock()
    mock_response.status = status
    if json_data is not None:
        mock_response.json.return_value = json_data
    if text_data is not None:
        mock_response.text.return_value = text_data
    return mock_response


def create_mock_context(mock_response):
    """Create a properly mocked async context manager."""
    mock_context = MagicMock()
    mock_context.__aenter__ = AsyncMock(return_value=mock_response)
    mock_context.__aexit__ = AsyncMock(return_value=None)
    return mock_context


def create_mock_session(mock_response):
    """Create a properly mocked aiohttp session with get/post methods."""
    mock_session = MagicMock()
    mock_session.closed = False
    mock_context = create_mock_context(mock_response)
    mock_session.get = MagicMock(return_value=mock_context)
    mock_session.post = MagicMock(return_value=mock_context)
    mock_session.close = AsyncMock()
    return mock_session


def patch_aiohttp_components():
    """Helper to patch both ClientSession and TCPConnector."""
    return (
        patch("ha_tools.lib.rest_api.ClientSession"),
        patch("ha_tools.lib.rest_api.TCPConnector"),
    )


class TestHomeAssistantAPI:
    """Test HomeAssistantAPI connection and data retrieval."""

    def test_api_initialization(self):
        """Test API client initialization."""
        config = HomeAssistantConfig(
            url="http://localhost:8123", access_token="test_token_123", timeout=60
        )
        api = HomeAssistantAPI(config)

        assert api._base_url == "http://localhost:8123"
        assert api._headers["Authorization"] == "Bearer test_token_123"
        assert api._headers["Content-Type"] == "application/json"
        assert api._timeout.total == 60

    def test_url_normalization(self):
        """Test URL normalization during initialization."""
        config = HomeAssistantConfig(
            url="https://homeassistant.local:8123/", access_token="test_token"
        )
        api = HomeAssistantAPI(config)

        assert (
            api._base_url == "https://homeassistant.local:8123"
        )  # Trailing slash removed

    @pytest.mark.asyncio
    async def test_get_session_creation(self):
        """Test session creation and caching."""
        config = HomeAssistantConfig(
            url="http://localhost:8123", access_token="test_token"
        )
        api = HomeAssistantAPI(config)

        with (
            patch("ha_tools.lib.rest_api.ClientSession") as mock_session_class,
            patch("aiohttp.TCPConnector") as mock_connector_class,
        ):
            mock_session = AsyncMock()
            mock_session.closed = False
            mock_session_class.return_value = mock_session
            mock_connector_class.return_value = MagicMock()

            # First call should create session
            session1 = await api._get_session()
            mock_session_class.assert_called_once()
            mock_connector_class.assert_called_once()

            # Second call should reuse session
            session2 = await api._get_session()
            assert session1 is session2
            assert mock_session_class.call_count == 1

    @pytest.mark.asyncio
    async def test_get_session_closed_recreation(self):
        """Test session recreation when existing session is closed."""
        config = HomeAssistantConfig(
            url="http://localhost:8123", access_token="test_token"
        )
        api = HomeAssistantAPI(config)

        with (
            patch("ha_tools.lib.rest_api.ClientSession") as mock_session_class,
            patch("aiohttp.TCPConnector") as mock_connector_class,
        ):
            mock_session1 = AsyncMock()
            mock_session1.closed = False
            mock_session2 = AsyncMock()
            mock_session2.closed = False
            mock_session_class.side_effect = [mock_session1, mock_session2]
            mock_connector_class.return_value = MagicMock()

            # First call creates session1
            session = await api._get_session()
            assert session is mock_session1
            assert mock_session_class.call_count == 1

            # Simulate session being closed externally
            mock_session1.closed = True

            # Second call should detect closed session and create new one
            session = await api._get_session()
            assert session is mock_session2
            assert mock_session_class.call_count == 2

    @pytest.mark.asyncio
    async def test_close_session(self):
        """Test session cleanup."""
        config = HomeAssistantConfig(
            url="http://localhost:8123", access_token="test_token"
        )
        api = HomeAssistantAPI(config)

        with (
            patch("ha_tools.lib.rest_api.ClientSession") as mock_session_class,
            patch("aiohttp.TCPConnector"),
        ):
            mock_session = AsyncMock()
            mock_session.closed = False
            mock_session_class.return_value = mock_session

            # Create session
            await api._get_session()

            # Close session
            await api.close()
            mock_session.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_session_when_none(self):
        """Test closing when no session exists."""
        config = HomeAssistantConfig(
            url="http://localhost:8123", access_token="test_token"
        )
        api = HomeAssistantAPI(config)

        # Should not raise error
        await api.close()

    @pytest.mark.asyncio
    async def test_close_session_when_already_closed(self):
        """Test closing when session is already closed."""
        config = HomeAssistantConfig(
            url="http://localhost:8123", access_token="test_token"
        )
        api_client = HomeAssistantAPI(config)

        with (
            patch("ha_tools.lib.rest_api.ClientSession") as mock_session_class,
            patch("aiohttp.TCPConnector"),
        ):
            mock_session = AsyncMock()
            mock_session.closed = True
            mock_session_class.return_value = mock_session

            await api_client._get_session()
            await api_client.close()

            # Should not attempt to close already closed session
            mock_session.close.assert_not_called()

    @pytest.mark.asyncio
    async def test_test_connection_success(self):
        """Test successful API connection test."""
        config = HomeAssistantConfig(
            url="http://localhost:8123", access_token="test_token"
        )
        api = HomeAssistantAPI(config)

        with (
            patch("ha_tools.lib.rest_api.ClientSession") as mock_session_class,
            patch("aiohttp.TCPConnector") as mock_connector_class,
        ):
            mock_response = create_mock_response(
                status=200, json_data={"message": "API running."}
            )
            mock_session = create_mock_session(mock_response)

            mock_session_class.return_value = mock_session
            mock_connector_class.return_value = MagicMock()

            # Should not raise exception
            await api.test_connection()

    @pytest.mark.asyncio
    async def test_test_connection_failure_invalid_response(self):
        """Test API connection test with invalid response."""
        config = HomeAssistantConfig(
            url="http://localhost:8123", access_token="test_token"
        )
        api = HomeAssistantAPI(config)

        with (
            patch("ha_tools.lib.rest_api.ClientSession") as mock_session_class,
            patch("aiohttp.TCPConnector") as mock_connector_class,
        ):
            mock_response = create_mock_response(status=500)
            mock_session = create_mock_session(mock_response)
            mock_session_class.return_value = mock_session
            mock_connector_class.return_value = MagicMock()

            with pytest.raises(RuntimeError, match="API test failed: HTTP 500"):
                await api.test_connection()

    @pytest.mark.asyncio
    async def test_test_connection_failure_wrong_message(self):
        """Test API connection test with wrong response message."""
        config = HomeAssistantConfig(
            url="http://localhost:8123", access_token="test_token"
        )
        api = HomeAssistantAPI(config)

        with (
            patch("ha_tools.lib.rest_api.ClientSession") as mock_session_class,
            patch("aiohttp.TCPConnector") as mock_connector_class,
        ):
            mock_response = create_mock_response(
                status=200, json_data={"message": "Wrong message"}
            )
            mock_session = create_mock_session(mock_response)
            mock_session_class.return_value = mock_session
            mock_connector_class.return_value = MagicMock()

            with pytest.raises(RuntimeError, match="API test failed: HTTP 200"):
                await api.test_connection()

    @pytest.mark.asyncio
    async def test_get_states_success(self):
        """Test successful states retrieval."""
        config = HomeAssistantConfig(
            url="http://localhost:8123", access_token="test_token"
        )
        api = HomeAssistantAPI(config)

        sample_states = [
            {
                "entity_id": "sensor.temperature",
                "state": "20.5",
                "attributes": {"unit_of_measurement": "°C"},
                "last_changed": "2024-01-01T12:00:00+00:00",
                "last_updated": "2024-01-01T12:00:00+00:00",
            },
            {
                "entity_id": "switch.light",
                "state": "on",
                "attributes": {"friendly_name": "Living Room Light"},
                "last_changed": "2024-01-01T11:30:00+00:00",
                "last_updated": "2024-01-01T11:30:00+00:00",
            },
        ]

        with (
            patch("ha_tools.lib.rest_api.ClientSession") as mock_session_class,
            patch("aiohttp.TCPConnector") as mock_connector_class,
        ):
            mock_response = create_mock_response(status=200, json_data=sample_states)
            mock_session = create_mock_session(mock_response)
            mock_session_class.return_value = mock_session
            mock_connector_class.return_value = MagicMock()

            states = await api.get_states()
            assert len(states) == 2
            assert states[0]["entity_id"] == "sensor.temperature"
            assert states[1]["entity_id"] == "switch.light"

    @pytest.mark.asyncio
    async def test_get_states_failure(self):
        """Test states retrieval failure."""
        config = HomeAssistantConfig(
            url="http://localhost:8123", access_token="test_token"
        )
        api = HomeAssistantAPI(config)

        with (
            patch("ha_tools.lib.rest_api.ClientSession") as mock_session_class,
            patch("aiohttp.TCPConnector") as mock_connector_class,
        ):
            mock_response = create_mock_response(status=401)
            mock_session = create_mock_session(mock_response)
            mock_session_class.return_value = mock_session
            mock_connector_class.return_value = MagicMock()

            with pytest.raises(RuntimeError, match="Failed to get states: HTTP 401"):
                await api.get_states()

    @pytest.mark.asyncio
    async def test_get_entity_state_success(self):
        """Test successful single entity state retrieval."""
        config = HomeAssistantConfig(
            url="http://localhost:8123", access_token="test_token"
        )
        api = HomeAssistantAPI(config)

        entity_state = {
            "entity_id": "sensor.temperature",
            "state": "20.5",
            "attributes": {"unit_of_measurement": "°C"},
            "last_changed": "2024-01-01T12:00:00+00:00",
            "last_updated": "2024-01-01T12:00:00+00:00",
        }

        with (
            patch("ha_tools.lib.rest_api.ClientSession") as mock_session_class,
            patch("aiohttp.TCPConnector") as mock_connector_class,
        ):
            mock_response = create_mock_response(status=200, json_data=entity_state)
            mock_session = create_mock_session(mock_response)
            mock_session_class.return_value = mock_session
            mock_connector_class.return_value = MagicMock()

            state = await api.get_entity_state("sensor.temperature")
            assert state is not None
            assert state["entity_id"] == "sensor.temperature"
            assert state["state"] == "20.5"

    @pytest.mark.asyncio
    async def test_get_entity_state_not_found(self):
        """Test entity state retrieval when entity not found."""
        config = HomeAssistantConfig(
            url="http://localhost:8123", access_token="test_token"
        )
        api = HomeAssistantAPI(config)

        with (
            patch("ha_tools.lib.rest_api.ClientSession") as mock_session_class,
            patch("aiohttp.TCPConnector") as mock_connector_class,
        ):
            mock_response = create_mock_response(status=404)
            mock_session = create_mock_session(mock_response)
            mock_session_class.return_value = mock_session
            mock_connector_class.return_value = MagicMock()

            state = await api.get_entity_state("sensor.nonexistent")
            assert state is None

    @pytest.mark.asyncio
    async def test_get_entity_state_failure(self):
        """Test entity state retrieval failure."""
        config = HomeAssistantConfig(
            url="http://localhost:8123", access_token="test_token"
        )
        api = HomeAssistantAPI(config)

        with (
            patch("ha_tools.lib.rest_api.ClientSession") as mock_session_class,
            patch("aiohttp.TCPConnector") as mock_connector_class,
        ):
            mock_response = create_mock_response(status=500)
            mock_session = create_mock_session(mock_response)
            mock_session_class.return_value = mock_session
            mock_connector_class.return_value = MagicMock()

            with pytest.raises(
                RuntimeError, match="Failed to get entity sensor.temperature: HTTP 500"
            ):
                await api.get_entity_state("sensor.temperature")

    @pytest.mark.asyncio
    async def test_get_entity_history_success(self):
        """Test successful entity history retrieval."""
        config = HomeAssistantConfig(
            url="http://localhost:8123", access_token="test_token"
        )
        api = HomeAssistantAPI(config)

        history_data = [
            [
                {
                    "entity_id": "sensor.temperature",
                    "state": "20.0",
                    "last_changed": "2024-01-01T11:00:00+00:00",
                    "last_updated": "2024-01-01T11:00:00+00:00",
                },
                {
                    "entity_id": "sensor.temperature",
                    "state": "20.5",
                    "last_changed": "2024-01-01T12:00:00+00:00",
                    "last_updated": "2024-01-01T12:00:00+00:00",
                },
            ]
        ]

        with (
            patch("ha_tools.lib.rest_api.ClientSession") as mock_session_class,
            patch("aiohttp.TCPConnector") as mock_connector_class,
        ):
            mock_response = create_mock_response(status=200, json_data=history_data)
            mock_session = create_mock_session(mock_response)
            mock_session_class.return_value = mock_session
            mock_connector_class.return_value = MagicMock()

            history = await api.get_entity_history("sensor.temperature")
            assert len(history) == 1
            assert len(history[0]) == 2
            assert history[0][0]["state"] == "20.0"
            assert history[0][1]["state"] == "20.5"

    @pytest.mark.asyncio
    async def test_get_entity_history_with_time_range(self):
        """Test entity history retrieval with time range parameters."""
        config = HomeAssistantConfig(
            url="http://localhost:8123", access_token="test_token"
        )
        api = HomeAssistantAPI(config)

        start_time = datetime(2024, 1, 1, 10, 0, 0)
        end_time = datetime(2024, 1, 1, 14, 0, 0)

        with (
            patch("ha_tools.lib.rest_api.ClientSession") as mock_session_class,
            patch("aiohttp.TCPConnector") as mock_connector_class,
        ):
            mock_response = create_mock_response(status=200, json_data=[])
            mock_session = create_mock_session(mock_response)
            mock_session_class.return_value = mock_session
            mock_connector_class.return_value = MagicMock()

            await api.get_entity_history(
                "sensor.temperature",
                start_time=start_time,
                end_time=end_time,
                minimal_response=False,
            )

            # Verify correct parameters were passed
            mock_session.get.assert_called_once()
            call_args = mock_session.get.call_args
            assert "filter_start_time" in call_args[1]["params"]
            assert "filter_end_time" in call_args[1]["params"]
            # When minimal_response=False, the param is not included (only "true" is set)
            assert "minimal_response" not in call_args[1]["params"]

    @pytest.mark.asyncio
    async def test_get_entity_history_default_parameters(self):
        """Test entity history retrieval with default parameters."""
        config = HomeAssistantConfig(
            url="http://localhost:8123", access_token="test_token"
        )
        api = HomeAssistantAPI(config)

        with (
            patch("ha_tools.lib.rest_api.ClientSession") as mock_session_class,
            patch("aiohttp.TCPConnector") as mock_connector_class,
        ):
            mock_response = create_mock_response(status=200, json_data=[])
            mock_session = create_mock_session(mock_response)
            mock_session_class.return_value = mock_session
            mock_connector_class.return_value = MagicMock()

            await api.get_entity_history("sensor.temperature")

            # Verify default minimal_response parameter
            call_args = mock_session.get.call_args
            assert call_args[1]["params"]["minimal_response"] == "true"

    @pytest.mark.asyncio
    async def test_get_entity_history_failure(self):
        """Test entity history retrieval failure."""
        config = HomeAssistantConfig(
            url="http://localhost:8123", access_token="test_token"
        )
        api = HomeAssistantAPI(config)

        with (
            patch("ha_tools.lib.rest_api.ClientSession") as mock_session_class,
            patch("aiohttp.TCPConnector") as mock_connector_class,
        ):
            mock_response = create_mock_response(status=500)
            mock_session = create_mock_session(mock_response)
            mock_session_class.return_value = mock_session
            mock_connector_class.return_value = MagicMock()

            with pytest.raises(
                RuntimeError,
                match="Failed to get history for sensor.temperature: HTTP 500",
            ):
                await api.get_entity_history("sensor.temperature")

    @pytest.mark.asyncio
    async def test_api_url_construction(self):
        """Test correct API URL construction."""
        config = HomeAssistantConfig(
            url="http://localhost:8123", access_token="test_token"
        )
        api = HomeAssistantAPI(config)

        with (
            patch("ha_tools.lib.rest_api.ClientSession") as mock_session_class,
            patch("aiohttp.TCPConnector") as mock_connector_class,
        ):
            mock_response = create_mock_response(status=200, json_data=[])
            mock_session = create_mock_session(mock_response)
            mock_session_class.return_value = mock_session
            mock_connector_class.return_value = MagicMock()

            await api.get_states()
            mock_session.get.assert_called_with("http://localhost:8123/api/states")

            await api.get_entity_state("sensor.test")
            mock_session.get.assert_called_with(
                "http://localhost:8123/api/states/sensor.test"
            )

            await api.get_entity_history("sensor.test")
            mock_session.get.assert_called_with(
                "http://localhost:8123/api/history/period/sensor.test",
                params=mock_session.get.call_args[1]["params"],
            )

    @pytest.mark.asyncio
    async def test_authentication_headers(self):
        """Test that authentication headers are correctly included."""
        config = HomeAssistantConfig(
            url="http://localhost:8123", access_token="test_token_12345"
        )
        api = HomeAssistantAPI(config)

        with (
            patch("ha_tools.lib.rest_api.ClientSession") as mock_session_class,
            patch("aiohttp.TCPConnector") as mock_connector_class,
        ):
            mock_response = create_mock_response(status=200, json_data=[])
            mock_session = create_mock_session(mock_response)
            mock_session_class.return_value = mock_session
            mock_connector_class.return_value = MagicMock()

            await api.get_states()

            # Verify session was created with correct headers
            mock_session_class.assert_called_once()
            call_kwargs = mock_session_class.call_args[1]
            assert "Authorization" in call_kwargs["headers"]
            assert call_kwargs["headers"]["Authorization"] == "Bearer test_token_12345"
            assert call_kwargs["headers"]["Content-Type"] == "application/json"

    @pytest.mark.asyncio
    async def test_timeout_configuration(self):
        """Test that timeout is correctly configured."""
        config = HomeAssistantConfig(
            url="http://localhost:8123", access_token="test_token", timeout=45
        )
        api = HomeAssistantAPI(config)

        with (
            patch("ha_tools.lib.rest_api.ClientSession") as mock_session_class,
            patch("aiohttp.TCPConnector"),
        ):
            mock_session = AsyncMock()
            mock_session_class.return_value = mock_session

            await api._get_session()

            # Verify timeout was configured
            call_kwargs = mock_session_class.call_args[1]
            assert "timeout" in call_kwargs
            assert call_kwargs["timeout"].total == 45

    @pytest.mark.asyncio
    async def test_connection_pool_configuration(self):
        """Test that connection pool limits are configured."""
        config = HomeAssistantConfig(
            url="http://localhost:8123", access_token="test_token"
        )
        api = HomeAssistantAPI(config)

        with (
            patch("ha_tools.lib.rest_api.ClientSession") as mock_session_class,
            patch("aiohttp.TCPConnector") as mock_connector_class,
        ):
            mock_session = AsyncMock()
            mock_session.closed = False
            mock_connector = MagicMock()
            mock_session_class.return_value = mock_session
            mock_connector_class.return_value = mock_connector

            await api._get_session()

            # Verify TCPConnector was created with correct pool limits
            mock_connector_class.assert_called_once_with(limit=10, limit_per_host=5)

            # Verify connector was passed to ClientSession
            call_kwargs = mock_session_class.call_args[1]
            assert "connector" in call_kwargs
            assert call_kwargs["connector"] is mock_connector


class TestErrorLogParsing:
    """Test error log parsing functionality."""

    def test_parse_error_log_basic(self):
        """Test parsing basic error log format."""
        log_text = """2024-01-15 10:30:45.123 ERROR (MainThread) [homeassistant.core] Error doing job
Traceback (most recent call last):
  File "test.py", line 1
ValueError: test error
2024-01-15 10:31:00.456 ERROR (MainThread) [custom_component] Another error"""

        config = HomeAssistantConfig(
            url="http://localhost:8123", access_token="test_token"
        )
        api = HomeAssistantAPI(config)
        errors = api._parse_error_log(log_text, {"error", "warning"})

        assert len(errors) == 2
        assert errors[0]["source"] == "homeassistant.core"
        assert errors[0]["message"] == "Error doing job"
        assert len(errors[0]["context"]) == 3  # Traceback lines
        assert errors[1]["source"] == "custom_component"

    def test_parse_error_log_empty(self):
        """Test parsing empty log."""
        config = HomeAssistantConfig(
            url="http://localhost:8123", access_token="test_token"
        )
        api = HomeAssistantAPI(config)
        errors = api._parse_error_log("", {"error", "warning"})
        assert errors == []

    def test_parse_error_log_filters_warnings(self):
        """Test that WARNING level is filtered out when not in levels set."""
        log_text = """2024-01-15 10:30:45 WARNING (MainThread) [test] Warning message
2024-01-15 10:30:46 ERROR (MainThread) [test] Error message"""

        config = HomeAssistantConfig(
            url="http://localhost:8123", access_token="test_token"
        )
        api = HomeAssistantAPI(config)
        # Only request error level - warnings should be filtered
        errors = api._parse_error_log(log_text, {"error"})

        assert len(errors) == 1
        assert errors[0]["level"] == "ERROR"

    def test_parse_error_log_critical_included(self):
        """Test that CRITICAL level is included when in levels set."""
        log_text = (
            """2024-01-15 10:30:45 CRITICAL (MainThread) [test] Critical message"""
        )

        config = HomeAssistantConfig(
            url="http://localhost:8123", access_token="test_token"
        )
        api = HomeAssistantAPI(config)
        errors = api._parse_error_log(log_text, {"error", "critical"})

        assert len(errors) == 1
        assert errors[0]["level"] == "CRITICAL"
        assert errors[0]["message"] == "Critical message"

    def test_parse_error_log_timestamp_parsing(self):
        """Test correct timestamp parsing."""
        log_text = """2024-01-15 10:30:45.123 ERROR (MainThread) [test] Test message"""

        config = HomeAssistantConfig(
            url="http://localhost:8123", access_token="test_token"
        )
        api = HomeAssistantAPI(config)
        errors = api._parse_error_log(log_text, {"error"})

        assert len(errors) == 1
        assert errors[0]["timestamp"].year == 2024
        assert errors[0]["timestamp"].month == 1
        assert errors[0]["timestamp"].day == 15
        assert errors[0]["timestamp"].hour == 10
        assert errors[0]["timestamp"].minute == 30
        assert errors[0]["timestamp"].second == 45

    def test_parse_error_log_multiline_traceback(self):
        """Test parsing errors with multiline tracebacks."""
        log_text = """2024-01-15 10:30:45.123 ERROR (MainThread) [homeassistant.core] Error in setup
Traceback (most recent call last):
  File "/config/custom_components/test/__init__.py", line 42, in async_setup
    await do_something()
  File "/config/custom_components/test/sensor.py", line 100, in do_something
    return data["missing_key"]
KeyError: 'missing_key'"""

        config = HomeAssistantConfig(
            url="http://localhost:8123", access_token="test_token"
        )
        api = HomeAssistantAPI(config)
        errors = api._parse_error_log(log_text, {"error"})

        assert len(errors) == 1
        assert errors[0]["source"] == "homeassistant.core"
        assert len(errors[0]["context"]) == 6  # 6 traceback lines
        assert "KeyError" in errors[0]["context"][-1]

    def test_parse_error_log_limits_to_50(self):
        """Test that parsing limits results to 50 most recent errors."""
        # Create 60 errors
        log_lines = []
        for i in range(60):
            log_lines.append(
                f"2024-01-15 10:{i:02d}:00 ERROR (MainThread) [test] Error {i}"
            )

        log_text = "\n".join(log_lines)

        config = HomeAssistantConfig(
            url="http://localhost:8123", access_token="test_token"
        )
        api = HomeAssistantAPI(config)
        errors = api._parse_error_log(log_text, {"error"})

        assert len(errors) == 50
        # Should keep the most recent (last) 50
        assert errors[0]["message"] == "Error 10"  # First of last 50
        assert errors[-1]["message"] == "Error 59"  # Last error

    def test_parse_error_log_without_milliseconds(self):
        """Test parsing logs without millisecond precision."""
        log_text = """2024-01-15 10:30:45 ERROR (MainThread) [test] No milliseconds"""

        config = HomeAssistantConfig(
            url="http://localhost:8123", access_token="test_token"
        )
        api = HomeAssistantAPI(config)
        errors = api._parse_error_log(log_text, {"error"})

        assert len(errors) == 1
        assert errors[0]["message"] == "No milliseconds"

    @pytest.mark.asyncio
    async def test_get_logs_integration(self):
        """Test get_logs() properly parses text response."""
        config = HomeAssistantConfig(
            url="http://localhost:8123", access_token="test_token"
        )
        api = HomeAssistantAPI(config)

        log_text = """2024-01-15 10:30:45.123 ERROR (MainThread) [test.component] Test error message
Additional context line"""

        with (
            patch("ha_tools.lib.rest_api.ClientSession") as mock_session_class,
            patch("aiohttp.TCPConnector") as mock_connector_class,
        ):
            mock_response = create_mock_response(status=200, text_data=log_text)
            mock_session = create_mock_session(mock_response)
            mock_session_class.return_value = mock_session
            mock_connector_class.return_value = MagicMock()

            logs = await api.get_logs({"error", "warning"})

            assert len(logs) == 1
            assert logs[0]["source"] == "test.component"
            assert logs[0]["message"] == "Test error message"
            assert len(logs[0]["context"]) == 1

    @pytest.mark.asyncio
    async def test_get_logs_empty_response(self):
        """Test get_logs() handles empty response."""
        config = HomeAssistantConfig(
            url="http://localhost:8123", access_token="test_token"
        )
        api = HomeAssistantAPI(config)

        with (
            patch("ha_tools.lib.rest_api.ClientSession") as mock_session_class,
            patch("aiohttp.TCPConnector") as mock_connector_class,
        ):
            mock_response = create_mock_response(status=200, text_data="")
            mock_session = create_mock_session(mock_response)
            mock_session_class.return_value = mock_session
            mock_connector_class.return_value = MagicMock()

            logs = await api.get_logs({"error", "warning"})

            assert logs == []

    @pytest.mark.asyncio
    async def test_get_logs_api_failure(self):
        """Test get_logs() handles API failure gracefully."""
        config = HomeAssistantConfig(
            url="http://localhost:8123", access_token="test_token"
        )
        api = HomeAssistantAPI(config)

        with (
            patch("ha_tools.lib.rest_api.ClientSession") as mock_session_class,
            patch("aiohttp.TCPConnector") as mock_connector_class,
            patch("ha_tools.lib.rest_api.print_warning"),
        ):
            mock_response = create_mock_response(
                status=500, text_data="Internal Server Error"
            )
            mock_session = create_mock_session(mock_response)
            mock_session_class.return_value = mock_session
            mock_connector_class.return_value = MagicMock()

            logs = await api.get_logs({"error", "warning"})

            assert logs == []


class TestHomeAssistantAPIWebSocket:
    """Tests for HomeAssistantAPI WebSocket methods."""

    @pytest.fixture
    def mock_config(self):
        """Create mock Home Assistant config."""
        config = MagicMock()
        config.url = "http://homeassistant.local:8123"
        config.access_token = "test_token"
        config.timeout = 30
        return config

    @pytest.fixture
    def api_client(self, mock_config):
        """Create API client instance."""
        return HomeAssistantAPI(mock_config)

    @pytest.fixture
    def mock_ws_response(self, api_client):
        """
        Factory fixture to set up mock WebSocket with a given response.

        Usage:
            mock_ws_response({"id": 1, "success": True, "result": [...]})
        """

        def _setup(response_data: dict):
            api_client._ws = AsyncMock()
            api_client._ws.closed = False
            api_client._ws.send_json = AsyncMock()

            mock_msg = MagicMock()
            mock_msg.type = 1  # WSMsgType.TEXT
            mock_msg.data = json.dumps(response_data)
            api_client._ws.receive = AsyncMock(return_value=mock_msg)
            return api_client

        return _setup

    def test_websocket_url_http(self, api_client):
        """Test WebSocket URL construction from HTTP."""
        assert api_client._ws_url == "ws://homeassistant.local:8123/api/websocket"

    def test_websocket_url_https(self, mock_config):
        """Test WebSocket URL construction from HTTPS."""
        mock_config.url = "https://homeassistant.local:8123"
        api = HomeAssistantAPI(mock_config)
        assert api._ws_url == "wss://homeassistant.local:8123/api/websocket"

    @pytest.mark.asyncio
    async def test_get_system_logs_ws_success(self, api_client, mock_ws_response):
        """Test successful system log retrieval via WebSocket."""
        mock_ws_response(
            {
                "id": 1,
                "type": "result",
                "success": True,
                "result": [
                    {
                        "name": "homeassistant.components.sensor.helpers",
                        "message": ["sensor.test rendered invalid timestamp"],
                        "level": "ERROR",
                        "source": ["components/sensor/helpers.py", 23],
                        "timestamp": 1736715000.123,
                        "exception": "",
                        "count": 7,
                        "first_occurred": 1736712600.456,
                    }
                ],
            }
        )

        logs = await api_client.get_system_logs_ws({"error"})

        assert len(logs) == 1
        assert logs[0]["source"] == "homeassistant.components.sensor.helpers"
        assert logs[0]["source_location"] == "components/sensor/helpers.py:23"
        assert logs[0]["count"] == 7
        assert logs[0]["level"] == "ERROR"

    @pytest.mark.asyncio
    async def test_get_system_logs_ws_level_filter(self, api_client, mock_ws_response):
        """Test that logs are filtered by level."""
        mock_ws_response(
            {
                "id": 1,
                "type": "result",
                "success": True,
                "result": [
                    {
                        "name": "test",
                        "message": ["error"],
                        "level": "ERROR",
                        "source": ["a.py", 1],
                        "timestamp": 1,
                        "exception": "",
                        "count": 1,
                        "first_occurred": 1,
                    },
                    {
                        "name": "test",
                        "message": ["warning"],
                        "level": "WARNING",
                        "source": ["b.py", 2],
                        "timestamp": 2,
                        "exception": "",
                        "count": 1,
                        "first_occurred": 2,
                    },
                    {
                        "name": "test",
                        "message": ["info"],
                        "level": "INFO",
                        "source": ["c.py", 3],
                        "timestamp": 3,
                        "exception": "",
                        "count": 1,
                        "first_occurred": 3,
                    },
                ],
            }
        )

        logs = await api_client.get_system_logs_ws({"error"})
        assert len(logs) == 1
        assert logs[0]["level"] == "ERROR"

    @pytest.mark.asyncio
    async def test_get_system_logs_ws_empty_response(
        self, api_client, mock_ws_response
    ):
        """Test handling empty response."""
        mock_ws_response({"id": 1, "type": "result", "success": True, "result": []})

        logs = await api_client.get_system_logs_ws()
        assert logs == []

    @pytest.mark.asyncio
    async def test_get_system_logs_ws_connection_failure(self, api_client):
        """Test graceful handling when WebSocket connection fails."""
        # No WebSocket connected
        api_client._ws = None
        # Mock _ws_connect to fail
        api_client._ws_connect = AsyncMock(return_value=False)

        logs = await api_client.get_system_logs_ws()
        assert logs == []

    @pytest.mark.asyncio
    async def test_ws_connect_auth_invalid(self, api_client):
        """Test handling of auth_invalid response."""
        # Mock WebSocket that returns auth_required then auth_invalid
        mock_ws = AsyncMock()
        mock_ws.closed = False

        auth_required_msg = MagicMock()
        auth_required_msg.type = 1  # WSMsgType.TEXT
        auth_required_msg.data = json.dumps(
            {"type": "auth_required", "ha_version": "2024.1.0"}
        )

        auth_invalid_msg = MagicMock()
        auth_invalid_msg.type = 1  # WSMsgType.TEXT
        auth_invalid_msg.data = json.dumps(
            {"type": "auth_invalid", "message": "Invalid access token"}
        )

        mock_ws.receive = AsyncMock(side_effect=[auth_required_msg, auth_invalid_msg])
        mock_ws.send_json = AsyncMock()

        # Mock session to return our mock WebSocket
        mock_session = AsyncMock()
        mock_session.ws_connect = AsyncMock(return_value=mock_ws)
        api_client._session = mock_session

        result = await api_client._ws_connect()
        assert result is False

    @pytest.mark.asyncio
    async def test_get_system_logs_ws_with_exception(
        self, api_client, mock_ws_response
    ):
        """Test parsing logs that include exception tracebacks."""
        mock_ws_response(
            {
                "id": 1,
                "type": "result",
                "success": True,
                "result": [
                    {
                        "name": "homeassistant.core",
                        "message": ["Uncaught exception in main loop"],
                        "level": "ERROR",
                        "source": ["homeassistant/core.py", 145],
                        "timestamp": 1736715000.0,
                        "exception": 'Traceback (most recent call last):\n  File "core.py", line 145\nValueError: test',
                        "count": 1,
                        "first_occurred": 1736715000.0,
                    }
                ],
            }
        )

        logs = await api_client.get_system_logs_ws({"error"})

        assert len(logs) == 1
        assert (
            logs[0]["exception"]
            == 'Traceback (most recent call last):\n  File "core.py", line 145\nValueError: test'
        )

    @pytest.mark.asyncio
    async def test_get_system_logs_ws_multiple_messages(
        self, api_client, mock_ws_response
    ):
        """Test parsing logs with multiple message variations (up to 5 stored by HA)."""
        mock_ws_response(
            {
                "id": 1,
                "type": "result",
                "success": True,
                "result": [
                    {
                        "name": "homeassistant.components.sensor",
                        "message": [
                            "sensor.temp1 unavailable",
                            "sensor.temp2 unavailable",
                            "sensor.temp3 unavailable",
                        ],
                        "level": "WARNING",
                        "source": ["components/sensor/__init__.py", 50],
                        "timestamp": 1736715000.0,
                        "exception": "",
                        "count": 3,
                        "first_occurred": 1736712000.0,
                    }
                ],
            }
        )

        logs = await api_client.get_system_logs_ws({"warning"})

        assert len(logs) == 1
        # First message is the most recent
        assert logs[0]["message"] == "sensor.temp1 unavailable"
        # Additional messages stored as context
        assert logs[0]["context"] == [
            "sensor.temp2 unavailable",
            "sensor.temp3 unavailable",
        ]

    @pytest.mark.asyncio
    async def test_get_system_logs_ws_command_error(self, api_client, mock_ws_response):
        """Test graceful handling when command fails (e.g., non-admin token)."""
        mock_ws_response(
            {
                "id": 1,
                "type": "result",
                "success": False,
                "error": {"code": "unauthorized", "message": "Unauthorized"},
            }
        )

        logs = await api_client.get_system_logs_ws({"error"})
        assert logs == []
