"""
Unit tests for ha-tools configuration management.

Tests configuration loading, validation, and environment variable support.
"""

import os
import tempfile
from pathlib import Path
from typing import Any, Dict
import pytest
import yaml

from ha_tools.config import HaToolsConfig, DatabaseConfig, HomeAssistantConfig


class TestDatabaseConfig:
    """Test DatabaseConfig validation and parsing."""

    def test_valid_sqlite_url(self):
        """Test valid SQLite database URL."""
        config = DatabaseConfig(url="sqlite:///test.db")
        assert config.url == "sqlite:///test.db"
        assert config.pool_size == 10  # Default value
        assert config.timeout == 30  # Default value

    def test_valid_mysql_url(self):
        """Test valid MySQL database URL."""
        config = DatabaseConfig(url="mysql://user:pass@localhost:3306/ha")
        assert config.url == "mysql://user:pass@localhost:3306/ha"

    def test_valid_postgresql_url(self):
        """Test valid PostgreSQL database URL."""
        config = DatabaseConfig(url="postgresql://user:pass@localhost:5432/ha")
        assert config.url == "postgresql://user:pass@localhost:5432/ha"

    def test_invalid_database_url(self):
        """Test validation fails for invalid database URL."""
        with pytest.raises(ValueError, match="Database URL must start with"):
            DatabaseConfig(url="invalid://test.db")

    def test_empty_database_url(self):
        """Test validation fails for empty database URL."""
        with pytest.raises(ValueError, match="Database URL is required"):
            DatabaseConfig(url="")

    def test_custom_config_values(self):
        """Test custom configuration values."""
        config = DatabaseConfig(
            url="sqlite:///test.db",
            pool_size=20,
            timeout=60,
            max_overflow=40
        )
        assert config.pool_size == 20
        assert config.timeout == 60
        assert config.max_overflow == 40


class TestHomeAssistantConfig:
    """Test HomeAssistantConfig validation and parsing."""

    def test_valid_http_url(self):
        """Test valid HTTP URL."""
        config = HomeAssistantConfig(
            url="http://localhost:8123",
            access_token="test_token"
        )
        assert config.url == "http://localhost:8123"
        assert config.access_token == "test_token"
        assert config.timeout == 30  # Default value

    def test_url_normalization(self):
        """Test URL normalization."""
        # Adds http:// prefix
        config = HomeAssistantConfig(
            url="localhost:8123",
            access_token="test_token"
        )
        assert config.url == "http://localhost:8123"

        # Removes trailing slash
        config = HomeAssistantConfig(
            url="https://homeassistant.local:8123/",
            access_token="test_token"
        )
        assert config.url == "https://homeassistant.local:8123"

    def test_invalid_url(self):
        """Test validation fails for invalid URL."""
        with pytest.raises(ValueError, match="Home Assistant URL is required"):
            HomeAssistantConfig(url="", access_token="test_token")

    def test_custom_config_values(self):
        """Test custom configuration values."""
        config = HomeAssistantConfig(
            url="http://localhost:8123",
            access_token="test_token",
            timeout=60
        )
        assert config.timeout == 60


class TestHaToolsConfig:
    """Test HaToolsConfig loading and management."""

    def test_load_from_file(self, sample_config_file: Path):
        """Test loading configuration from file."""
        HaToolsConfig.set_config_path(sample_config_file)
        config = HaToolsConfig.load()

        assert config.home_assistant.url == "http://localhost:8123"
        assert config.home_assistant.access_token == "test_token_12345"
        assert config.database.url == "sqlite:///test.db"
        assert config.ha_config_path.endswith("config")
        assert config.output_format == "markdown"
        assert config.verbose is False

    def test_load_missing_file(self):
        """Test loading configuration when file doesn't exist."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            missing_file = Path(tmp_dir) / "missing.yaml"
            HaToolsConfig.set_config_path(missing_file)

            with pytest.raises(ValueError, match="No configuration file found"):
                HaToolsConfig.load()

    def test_load_invalid_yaml(self, temp_dir: Path):
        """Test loading configuration from invalid YAML file."""
        invalid_file = temp_dir / "invalid.yaml"
        with open(invalid_file, "w") as f:
            f.write("invalid: yaml: content: [")  # Invalid YAML

        HaToolsConfig.set_config_path(invalid_file)

        with pytest.raises(ValueError, match="Failed to load config"):
            HaToolsConfig.load()

    def test_environment_variable_support(self):
        """Test configuration loading from environment variables."""
        env_vars = {
            "HA_TOOLS_HOME_ASSISTANT__URL": "http://env.local:8123",
            "HA_TOOLS_HOME_ASSISTANT__ACCESS_TOKEN": "env_token",
            "HA_TOOLS_DATABASE__URL": "postgresql://env_user:env_pass@localhost/env_db",
            "HA_TOOLS_OUTPUT_FORMAT": "json",
            "HA_TOOLS_VERBOSE": "true"
        }

        # Temporarily set environment variables
        original_env = {}
        for key, value in env_vars.items():
            original_env[key] = os.environ.get(key)
            os.environ[key] = value

        try:
            # Clear any existing config file path
            HaToolsConfig._config_path = None

            with tempfile.TemporaryDirectory() as tmp_dir:
                # Create a non-existent config file to force env-only loading
                non_existent = Path(tmp_dir) / "non_existent.yaml"
                HaToolsConfig.set_config_path(non_existent)

                config = HaToolsConfig()

                assert config.home_assistant.url == "http://env.local:8123"
                assert config.home_assistant.access_token == "env_token"
                assert config.database.url == "postgresql://env_user:env_pass@localhost/env_db"
                assert config.output_format == "json"
                assert config.verbose is True

        finally:
            # Restore original environment
            for key, original_value in original_env.items():
                if original_value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = original_value

    def test_save_configuration(self, temp_dir: Path):
        """Test saving configuration to file."""
        config_file = temp_dir / "test_save.yaml"

        config = HaToolsConfig(
            home_assistant=HomeAssistantConfig(
                url="https://ha.local:8123",
                access_token="save_token"
            ),
            database=DatabaseConfig(url="sqlite:///save.db"),
            ha_config_path="/config/path",
            output_format="table",
            verbose=True
        )

        config.save(config_file)

        # Verify file was created and contains correct data
        assert config_file.exists()

        with open(config_file, "r") as f:
            saved_data = yaml.safe_load(f)

        assert saved_data["home_assistant"]["url"] == "https://ha.local:8123"
        assert saved_data["home_assistant"]["access_token"] == "save_token"
        assert saved_data["database"]["url"] == "sqlite:///save.db"
        assert saved_data["output_format"] == "table"
        assert saved_data["verbose"] is True

    def test_validate_access_success(self, sample_ha_config: Path):
        """Test successful access validation."""
        config = HaToolsConfig(
            home_assistant=HomeAssistantConfig(
                url="http://localhost:8123",
                access_token="test_token"
            ),
            database=DatabaseConfig(url="sqlite:///test.db"),
            ha_config_path=str(sample_ha_config)
        )

        # Should not raise an exception
        config.validate_access()

    def test_validate_access_missing_config_dir(self):
        """Test access validation with missing config directory."""
        config = HaToolsConfig(
            home_assistant=HomeAssistantConfig(
                url="http://localhost:8123",
                access_token="test_token"
            ),
            database=DatabaseConfig(url="sqlite:///test.db"),
            ha_config_path="/non/existent/path"
        )

        with pytest.raises(ValueError, match="Home Assistant config directory not found"):
            config.validate_access()

    def test_validate_access_missing_config_file(self, temp_dir: Path):
        """Test access validation with missing configuration.yaml file."""
        empty_config_dir = temp_dir / "empty_config"
        empty_config_dir.mkdir()

        config = HaToolsConfig(
            home_assistant=HomeAssistantConfig(
                url="http://localhost:8123",
                access_token="test_token"
            ),
            database=DatabaseConfig(url="sqlite:///test.db"),
            ha_config_path=str(empty_config_dir)
        )

        with pytest.raises(ValueError, match="Required Home Assistant file not found"):
            config.validate_access()

    def test_to_dict(self, test_config: HaToolsConfig):
        """Test converting configuration to dictionary."""
        config_dict = test_config.to_dict()

        assert isinstance(config_dict, dict)
        assert "home_assistant" in config_dict
        assert "database" in config_dict
        assert config_dict["home_assistant"]["url"] == "http://localhost:8123"
        assert config_dict["database"]["url"] == "sqlite:///test.db"

    def test_custom_config_path(self, temp_dir: Path):
        """Test using custom configuration file path."""
        custom_path = temp_dir / "custom_config.yaml"
        config_data = {
            "home_assistant": {
                "url": "http://custom.local:8123",
                "access_token": "custom_token"
            },
            "database": {"url": "sqlite:///custom.db"}
        }

        with open(custom_path, "w") as f:
            yaml.dump(config_data, f)

        HaToolsConfig.set_config_path(custom_path)
        config = HaToolsConfig.load()

        assert config.home_assistant.url == "http://custom.local:8123"
        assert config.home_assistant.access_token == "custom_token"

    def test_partial_config_with_env_vars(self):
        """Test partial configuration file supplemented with environment variables."""
        env_vars = {
            "HA_TOOLS_HOME_ASSISTANT__ACCESS_TOKEN": "env_token",
            "HA_TOOLS_DATABASE__URL": "postgresql://env_user:env_pass@localhost/env_db"
        }

        # Temporarily set environment variables
        original_env = {}
        for key, value in env_vars.items():
            original_env[key] = os.environ.get(key)
            os.environ[key] = value

        try:
            with tempfile.TemporaryDirectory() as tmp_dir:
                partial_config_file = Path(tmp_dir) / "partial.yaml"
                partial_config = {
                    "home_assistant": {
                        "url": "http://localhost:8123"
                        # Missing access_token - should come from env
                    },
                    "output_format": "json"
                }

                with open(partial_config_file, "w") as f:
                    yaml.dump(partial_config, f)

                HaToolsConfig.set_config_path(partial_config_file)
                config = HaToolsConfig.load()

                assert config.home_assistant.url == "http://localhost:8123"
                assert config.home_assistant.access_token == "env_token"
                assert config.database.url == "postgresql://env_user:env_pass@localhost/env_db"
                assert config.output_format == "json"

        finally:
            # Restore original environment
            for key, original_value in original_env.items():
                if original_value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = original_value