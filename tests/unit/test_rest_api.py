"""
Unit tests for ha-tools REST API client.

Tests Home Assistant API authentication, connection handling, and data retrieval.
"""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
import aiohttp

from ha_tools.config import HomeAssistantConfig
from ha_tools.lib.rest_api import HomeAssistantAPI


class TestHomeAssistantAPI:
    """Test HomeAssistantAPI connection and data retrieval."""

    def test_api_initialization(self):
        """Test API client initialization."""
        config = HomeAssistantConfig(
            url="http://localhost:8123",
            access_token="test_token_123",
            timeout=60
        )
        api = HomeAssistantAPI(config)

        assert api._base_url == "http://localhost:8123"
        assert api._headers["Authorization"] == "Bearer test_token_123"
        assert api._headers["Content-Type"] == "application/json"
        assert api._timeout.total == 60

    def test_url_normalization(self):
        """Test URL normalization during initialization."""
        config = HomeAssistantConfig(
            url="https://homeassistant.local:8123/",
            access_token="test_token"
        )
        api = HomeAssistantAPI(config)

        assert api._base_url == "https://homeassistant.local:8123"  # Trailing slash removed

    @pytest.mark.asyncio
    async def test_get_session_creation(self):
        """Test session creation and caching."""
        config = HomeAssistantConfig(
            url="http://localhost:8123",
            access_token="test_token"
        )
        api = HomeAssistantAPI(config)

        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_session.closed = False
            mock_session_class.return_value = mock_session

            # First call should create session
            session1 = await api._get_session()
            mock_session_class.assert_called_once()

            # Second call should reuse session
            session2 = await api._get_session()
            assert session1 is session2
            assert mock_session_class.call_count == 1

    @pytest.mark.asyncio
    async def test_get_session_closed_recreation(self):
        """Test session recreation when existing session is closed."""
        config = HomeAssistantConfig(
            url="http://localhost:8123",
            access_token="test_token"
        )
        api = HomeAssistantAPI(config)

        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session1 = AsyncMock()
            mock_session1.closed = True
            mock_session2 = AsyncMock()
            mock_session2.closed = False
            mock_session_class.side_effect = [mock_session1, mock_session2]

            # First call with closed session should create new one
            session1 = await api._get_session()
            assert session1 is mock_session2

    @pytest.mark.asyncio
    async def test_close_session(self):
        """Test session cleanup."""
        config = HomeAssistantConfig(
            url="http://localhost:8123",
            access_token="test_token"
        )
        api = HomeAssistantAPI(config)

        with patch('aiohttp.ClientSession') as mock_session_class:
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
            url="http://localhost:8123",
            access_token="test_token"
        )
        api = HomeAssistantAPI(config)

        # Should not raise error
        await api.close()

    @pytest.mark.asyncio
    async def test_close_session_when_already_closed(self):
        """Test closing when session is already closed."""
        config = HomeAssistantConfig(
            url="http://localhost:8123",
            access_token="test_token"
        )
        api = HomeAssistantConfig(url="http://localhost:8123", access_token="test_token")
        api_client = HomeAssistantAPI(config)

        with patch('aiohttp.ClientSession') as mock_session_class:
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
            url="http://localhost:8123",
            access_token="test_token"
        )
        api = HomeAssistantAPI(config)

        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json.return_value = {"message": "API running."}
            mock_session.get.return_value.__aenter__.return_value = mock_response
            mock_session_class.return_value = mock_session

            # Should not raise exception
            await api.test_connection()

    @pytest.mark.asyncio
    async def test_test_connection_failure_invalid_response(self):
        """Test API connection test with invalid response."""
        config = HomeAssistantConfig(
            url="http://localhost:8123",
            access_token="test_token"
        )
        api = HomeAssistantAPI(config)

        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_response = AsyncMock()
            mock_response.status = 500
            mock_session.get.return_value.__aenter__.return_value = mock_response
            mock_session_class.return_value = mock_session

            with pytest.raises(RuntimeError, match="API test failed: HTTP 500"):
                await api.test_connection()

    @pytest.mark.asyncio
    async def test_test_connection_failure_wrong_message(self):
        """Test API connection test with wrong response message."""
        config = HomeAssistantConfig(
            url="http://localhost:8123",
            access_token="test_token"
        )
        api = HomeAssistantAPI(config)

        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json.return_value = {"message": "Wrong message"}
            mock_session.get.return_value.__aenter__.return_value = mock_response
            mock_session_class.return_value = mock_session

            with pytest.raises(RuntimeError, match="API test failed: HTTP 200"):
                await api.test_connection()

    @pytest.mark.asyncio
    async def test_get_states_success(self):
        """Test successful states retrieval."""
        config = HomeAssistantConfig(
            url="http://localhost:8123",
            access_token="test_token"
        )
        api = HomeAssistantAPI(config)

        sample_states = [
            {
                "entity_id": "sensor.temperature",
                "state": "20.5",
                "attributes": {"unit_of_measurement": "°C"},
                "last_changed": "2024-01-01T12:00:00+00:00",
                "last_updated": "2024-01-01T12:00:00+00:00"
            },
            {
                "entity_id": "switch.light",
                "state": "on",
                "attributes": {"friendly_name": "Living Room Light"},
                "last_changed": "2024-01-01T11:30:00+00:00",
                "last_updated": "2024-01-01T11:30:00+00:00"
            }
        ]

        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json.return_value = sample_states
            mock_session.get.return_value.__aenter__.return_value = mock_response
            mock_session_class.return_value = mock_session

            states = await api.get_states()
            assert len(states) == 2
            assert states[0]["entity_id"] == "sensor.temperature"
            assert states[1]["entity_id"] == "switch.light"

    @pytest.mark.asyncio
    async def test_get_states_failure(self):
        """Test states retrieval failure."""
        config = HomeAssistantConfig(
            url="http://localhost:8123",
            access_token="test_token"
        )
        api = HomeAssistantAPI(config)

        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_response = AsyncMock()
            mock_response.status = 401
            mock_session.get.return_value.__aenter__.return_value = mock_response
            mock_session_class.return_value = mock_session

            with pytest.raises(RuntimeError, match="Failed to get states: HTTP 401"):
                await api.get_states()

    @pytest.mark.asyncio
    async def test_get_entity_state_success(self):
        """Test successful single entity state retrieval."""
        config = HomeAssistantConfig(
            url="http://localhost:8123",
            access_token="test_token"
        )
        api = HomeAssistantAPI(config)

        entity_state = {
            "entity_id": "sensor.temperature",
            "state": "20.5",
            "attributes": {"unit_of_measurement": "°C"},
            "last_changed": "2024-01-01T12:00:00+00:00",
            "last_updated": "2024-01-01T12:00:00+00:00"
        }

        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json.return_value = entity_state
            mock_session.get.return_value.__aenter__.return_value = mock_response
            mock_session_class.return_value = mock_session

            state = await api.get_entity_state("sensor.temperature")
            assert state is not None
            assert state["entity_id"] == "sensor.temperature"
            assert state["state"] == "20.5"

    @pytest.mark.asyncio
    async def test_get_entity_state_not_found(self):
        """Test entity state retrieval when entity not found."""
        config = HomeAssistantConfig(
            url="http://localhost:8123",
            access_token="test_token"
        )
        api = HomeAssistantAPI(config)

        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_response = AsyncMock()
            mock_response.status = 404
            mock_session.get.return_value.__aenter__.return_value = mock_response
            mock_session_class.return_value = mock_session

            state = await api.get_entity_state("sensor.nonexistent")
            assert state is None

    @pytest.mark.asyncio
    async def test_get_entity_state_failure(self):
        """Test entity state retrieval failure."""
        config = HomeAssistantConfig(
            url="http://localhost:8123",
            access_token="test_token"
        )
        api = HomeAssistantAPI(config)

        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_response = AsyncMock()
            mock_response.status = 500
            mock_session.get.return_value.__aenter__.return_value = mock_response
            mock_session_class.return_value = mock_session

            with pytest.raises(RuntimeError, match="Failed to get entity sensor.temperature: HTTP 500"):
                await api.get_entity_state("sensor.temperature")

    @pytest.mark.asyncio
    async def test_get_entity_history_success(self):
        """Test successful entity history retrieval."""
        config = HomeAssistantConfig(
            url="http://localhost:8123",
            access_token="test_token"
        )
        api = HomeAssistantAPI(config)

        history_data = [
            [
                {
                    "entity_id": "sensor.temperature",
                    "state": "20.0",
                    "last_changed": "2024-01-01T11:00:00+00:00",
                    "last_updated": "2024-01-01T11:00:00+00:00"
                },
                {
                    "entity_id": "sensor.temperature",
                    "state": "20.5",
                    "last_changed": "2024-01-01T12:00:00+00:00",
                    "last_updated": "2024-01-01T12:00:00+00:00"
                }
            ]
        ]

        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json.return_value = history_data
            mock_session.get.return_value.__aenter__.return_value = mock_response
            mock_session_class.return_value = mock_session

            history = await api.get_entity_history("sensor.temperature")
            assert len(history) == 1
            assert len(history[0]) == 2
            assert history[0][0]["state"] == "20.0"
            assert history[0][1]["state"] == "20.5"

    @pytest.mark.asyncio
    async def test_get_entity_history_with_time_range(self):
        """Test entity history retrieval with time range parameters."""
        config = HomeAssistantConfig(
            url="http://localhost:8123",
            access_token="test_token"
        )
        api = HomeAssistantAPI(config)

        start_time = datetime(2024, 1, 1, 10, 0, 0)
        end_time = datetime(2024, 1, 1, 14, 0, 0)

        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json.return_value = []
            mock_session.get.return_value.__aenter__.return_value = mock_response
            mock_session_class.return_value = mock_session

            await api.get_entity_history(
                "sensor.temperature",
                start_time=start_time,
                end_time=end_time,
                minimal_response=False
            )

            # Verify correct parameters were passed
            mock_session.get.assert_called_once()
            call_args = mock_session.get.call_args
            assert "filter_start_time" in call_args[1]["params"]
            assert "filter_end_time" in call_args[1]["params"]
            assert call_args[1]["params"]["minimal_response"] == "false"

    @pytest.mark.asyncio
    async def test_get_entity_history_default_parameters(self):
        """Test entity history retrieval with default parameters."""
        config = HomeAssistantConfig(
            url="http://localhost:8123",
            access_token="test_token"
        )
        api = HomeAssistantAPI(config)

        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json.return_value = []
            mock_session.get.return_value.__aenter__.return_value = mock_response
            mock_session_class.return_value = mock_session

            await api.get_entity_history("sensor.temperature")

            # Verify default minimal_response parameter
            call_args = mock_session.get.call_args
            assert call_args[1]["params"]["minimal_response"] == "true"

    @pytest.mark.asyncio
    async def test_get_entity_history_failure(self):
        """Test entity history retrieval failure."""
        config = HomeAssistantConfig(
            url="http://localhost:8123",
            access_token="test_token"
        )
        api = HomeAssistantAPI(config)

        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_response = AsyncMock()
            mock_response.status = 500
            mock_session.get.return_value.__aenter__.return_value = mock_response
            mock_session_class.return_value = mock_session

            with pytest.raises(RuntimeError, match="Failed to get history for sensor.temperature: HTTP 500"):
                await api.get_entity_history("sensor.temperature")

    @pytest.mark.asyncio
    async def test_api_url_construction(self):
        """Test correct API URL construction."""
        config = HomeAssistantConfig(
            url="http://localhost:8123",
            access_token="test_token"
        )
        api = HomeAssistantAPI(config)

        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json.return_value = []
            mock_session.get.return_value.__aenter__.return_value = mock_response
            mock_session_class.return_value = mock_session

            await api.get_states()
            mock_session.get.assert_called_with("http://localhost:8123/api/states")

            await api.get_entity_state("sensor.test")
            mock_session.get.assert_called_with("http://localhost:8123/api/states/sensor.test")

            await api.get_entity_history("sensor.test")
            mock_session.get.assert_called_with("http://localhost:8123/api/history/period/sensor.test", params=mock_session.get.call_args[1]["params"])

    @pytest.mark.asyncio
    async def test_authentication_headers(self):
        """Test that authentication headers are correctly included."""
        config = HomeAssistantConfig(
            url="http://localhost:8123",
            access_token="test_token_12345"
        )
        api = HomeAssistantAPI(config)

        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json.return_value = []
            mock_session.get.return_value.__aenter__.return_value = mock_response
            mock_session_class.return_value = mock_session

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
            url="http://localhost:8123",
            access_token="test_token",
            timeout=45
        )
        api = HomeAssistantAPI(config)

        with patch('aiohttp.ClientSession') as mock_session_class:
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
            url="http://localhost:8123",
            access_token="test_token"
        )
        api = HomeAssistantAPI(config)

        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_session_class.return_value = mock_session

            await api._get_session()

            # Verify connection pool configuration
            call_kwargs = mock_session_class.call_args[1]
            assert "connector" in call_kwargs
            connector = call_kwargs["connector"]
            assert isinstance(connector, aiohttp.TCPConnector)
            assert connector._limit == 10
            assert connector._limit_per_host == 5