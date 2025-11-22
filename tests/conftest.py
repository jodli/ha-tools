"""
Test configuration and fixtures for ha-tools.

Provides common fixtures for testing CLI commands, database connections,
and Home Assistant API interactions.
"""

import asyncio
import tempfile
from pathlib import Path
from typing import Any, Dict, Generator, Optional
from unittest.mock import AsyncMock, MagicMock
import pytest
import yaml

from ha_tools.config import HaToolsConfig, DatabaseConfig, HomeAssistantConfig


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield Path(tmp_dir)


@pytest.fixture
def sample_ha_config(temp_dir: Path) -> Path:
    """Create a sample Home Assistant configuration."""
    config_dir = temp_dir / "config"
    config_dir.mkdir()

    # Main configuration file
    main_config = {
        "homeassistant": {
            "name": "Test Home",
            "latitude": 52.0,
            "longitude": 13.0,
            "elevation": 34,
            "unit_system": "metric",
            "time_zone": "Europe/Berlin",
        },
        "sensor": [
            {
                "platform": "template",
                "sensors": {
                    "test_temperature": {
                        "friendly_name": "Test Temperature",
                        "unit_of_measurement": "°C",
                        "value_template": "{{ 20.0 }}"
                    }
                }
            }
        ]
    }

    config_file = config_dir / "configuration.yaml"
    with open(config_file, "w") as f:
        yaml.dump(main_config, f)

    # Packages directory
    packages_dir = config_dir / "packages"
    packages_dir.mkdir()

    # Sample package
    package_config = {
        "script": {
            "test_script": {
                "alias": "Test Script",
                "sequence": [{"delay": "00:01:00"}]
            }
        }
    }

    package_file = packages_dir / "test_package.yaml"
    with open(package_file, "w") as f:
        yaml.dump(package_config, f)

    return config_dir


@pytest.fixture
def sample_config_file(temp_dir: Path) -> Path:
    """Create a sample ha-tools configuration file."""
    config_data = {
        "home_assistant": {
            "url": "http://localhost:8123",
            "access_token": "test_token_12345",
            "timeout": 30
        },
        "database": {
            "url": "sqlite:///test.db",
            "pool_size": 5,
            "timeout": 10
        },
        "ha_config_path": str(temp_dir / "config"),
        "output_format": "markdown",
        "verbose": False
    }

    config_file = temp_dir / ".ha-tools-config.yaml"
    with open(config_file, "w") as f:
        yaml.dump(config_data, f)

    return config_file


@pytest.fixture
def test_config(sample_config_file: Path) -> HaToolsConfig:
    """Create a test HaToolsConfig instance."""
    HaToolsConfig.set_config_path(sample_config_file)
    return HaToolsConfig.load()


@pytest.fixture
def mock_home_assistant_api():
    """Create a mock Home Assistant API client."""
    api = AsyncMock()

    # Mock common API responses
    api.test_connection.return_value = None
    api.get_states.return_value = [
        {
            "entity_id": "sensor.test_temperature",
            "state": "20.0",
            "attributes": {
                "friendly_name": "Test Temperature",
                "unit_of_measurement": "°C",
                "device_class": "temperature"
            },
            "last_changed": "2024-01-01T12:00:00+00:00",
            "last_updated": "2024-01-01T12:00:00+00:00"
        },
        {
            "entity_id": "switch.test_switch",
            "state": "off",
            "attributes": {
                "friendly_name": "Test Switch"
            },
            "last_changed": "2024-01-01T11:30:00+00:00",
            "last_updated": "2024-01-01T11:30:00+00:00"
        }
    ]

    api.get_entity_state.return_value = {
        "entity_id": "sensor.test_temperature",
        "state": "20.0",
        "attributes": {
            "friendly_name": "Test Temperature",
            "unit_of_measurement": "°C"
        },
        "last_changed": "2024-01-01T12:00:00+00:00",
        "last_updated": "2024-01-01T12:00:00+00:00"
    }

    api.get_errors.return_value = []
    api.validate_config.return_value = {"valid": True, "errors": [], "messages": []}

    return api


@pytest.fixture
def mock_database_manager():
    """Create a mock database manager."""
    db = AsyncMock()

    # Mock common database responses
    db.test_connection.return_value = None

    db.get_entity_states.return_value = [
        {
            "entity_id": "sensor.test_temperature",
            "state": "20.0",
            "last_changed": "2024-01-01T12:00:00+00:00",
            "last_updated": "2024-01-01T12:00:00+00:00",
            "attributes": '{"friendly_name": "Test Temperature", "unit_of_measurement": "°C"}'
        }
    ]

    db.get_entity_statistics.return_value = [
        {
            "statistic_id": "sensor.test_temperature_mean",
            "mean": 19.5,
            "min": 18.0,
            "max": 21.0,
            "start": "2024-01-01T00:00:00+00:00"
        }
    ]

    return db


@pytest.fixture
def mock_registry_manager():
    """Create a mock registry manager."""
    registry = AsyncMock()

    # Mock registry data
    registry._entity_registry = [
        {
            "entity_id": "sensor.test_temperature",
            "friendly_name": "Test Temperature",
            "device_class": "temperature",
            "unit_of_measurement": "°C",
            "area_id": "area_1",
            "device_id": "device_1"
        },
        {
            "entity_id": "switch.test_switch",
            "friendly_name": "Test Switch",
            "disabled_by": None,
            "hidden_by": None
        }
    ]

    registry._area_registry = {
        "area_1": {
            "area_id": "area_1",
            "name": "Test Area"
        }
    }

    registry._device_registry = {
        "device_1": {
            "device_id": "device_1",
            "name": "Test Device",
            "manufacturer": "Test Manufacturer",
            "model": "Test Model"
        }
    }

    registry.search_entities.return_value = registry._entity_registry
    registry.get_area_name.return_value = "Test Area"
    registry.get_entity_name.return_value = "Test Temperature"
    registry.get_device_metadata.return_value = {
        "name": "Test Device",
        "manufacturer": "Test Manufacturer",
        "model": "Test Model"
    }

    return registry


@pytest.fixture
def sample_log_file(temp_dir: Path) -> Path:
    """Create a sample Home Assistant log file."""
    log_content = """
2024-01-01 12:00:00.123 INFOMainThreadhomeassistant.bootstrapHome Assistant initialized
2024-01-01 12:01:00.456 ERRORMainThreadhomeassistant.components.sensorError in sensor.test_temperature
2024-01-01 12:01:00.457 ERRORMainThreadTraceback (most recent call last):
File "/config/sensor.py", line 42, in update_state
    temperature = self.get_temperature()
File "/config/sensor.py", line 25, in get_temperature
    return self.api.call("/temperature")
ValueError: Failed to get temperature from API
2024-01-01 12:02:00.789 WARNINGMainThreadhomeassistant.components.switchSwitch test_switch unavailable
2024-01-01 12:03:00.012 ERRORMainThreadhomeassistant.coreError executing service automation.turn_on
Failed to call service automation.turn_on on entity automation.heating_control
Entity not found: automation.heating_control
"""

    log_file = temp_dir / "home-assistant.log"
    with open(log_file, "w") as f:
        f.write(log_content.strip())

    return log_file


@pytest.fixture
async def async_loop():
    """Create an event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# Test data constants
SAMPLE_ENTITY_REGISTRY = {
    "sensor.test_temperature": {
        "entity_id": "sensor.test_temperature",
        "friendly_name": "Test Temperature",
        "device_class": "temperature",
        "unit_of_measurement": "°C",
        "area_id": "area_1"
    }
}

SAMPLE_AREA_REGISTRY = {
    "area_1": {
        "area_id": "area_1",
        "name": "Living Room"
    }
}

SAMPLE_DEVICE_REGISTRY = {
    "device_1": {
        "device_id": "device_1",
        "name": "Weather Station",
        "manufacturer": "Test Corp",
        "model": "WS-1000"
    }
}

SAMPLE_STATES = [
    {
        "entity_id": "sensor.test_temperature",
        "state": "20.5",
        "attributes": {"friendly_name": "Test Temperature"},
        "last_changed": "2024-01-01T12:00:00+00:00",
        "last_updated": "2024-01-01T12:00:00+00:00"
    }
]

SAMPLE_ERROR_LOG = [
    {
        "timestamp": "2024-01-01T12:01:00",
        "message": "Error in sensor.test_temperature: Failed to get temperature",
        "source": "/config/home-assistant.log",
        "context": ["Traceback...", "ValueError: Failed to get temperature"]
    }
]