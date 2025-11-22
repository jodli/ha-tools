"""
Integration tests for ha-tools CLI commands.

Tests end-to-end command execution with mocked external dependencies.
"""

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch
import pytest
from typer.testing import CliRunner

from ha_tools.cli import app
from ha_tools.commands.validate import _run_validation
from ha_tools.commands.entities import _run_entities_command
from ha_tools.commands.errors import _run_errors_command


class TestCLIIntegration:
    """Test CLI command integration."""

    def setup_method(self):
        """Set up test runner."""
        self.runner = CliRunner()

    def test_cli_version(self):
        """Test CLI version command."""
        result = self.runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "ha-tools" in result.stdout

    def test_cli_help(self):
        """Test CLI help command."""
        result = self.runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "High-performance CLI" in result.stdout
        assert "validate" in result.stdout
        assert "entities" in result.stdout
        assert "errors" in result.stdout

    def test_validate_command_help(self):
        """Test validate command help."""
        result = self.runner.invoke(app, ["validate", "--help"])
        assert result.exit_code == 0
        assert "--syntax-only" in result.stdout
        assert "--fix" in result.stdout

    def test_entities_command_help(self):
        """Test entities command help."""
        result = self.runner.invoke(app, ["entities", "--help"])
        assert result.exit_code == 0
        assert "--search" in result.stdout
        assert "--include" in result.stdout
        assert "--history" in result.stdout

    def test_errors_command_help(self):
        """Test errors command help."""
        result = self.runner.invoke(app, ["errors", "--help"])
        assert result.exit_code == 0
        assert "--current" in result.stdout
        assert "--log" in result.stdout
        assert "--entity" in result.stdout

    @pytest.mark.asyncio
    async def test_validate_integration_success(self, sample_ha_config: Path, sample_config_file: Path):
        """Test full validation integration with mocked dependencies."""
        # Set up configuration
        import ha_tools.config
        ha_tools.config.HaToolsConfig.set_config_path(sample_config_file)

        with patch('ha_tools.lib.rest_api.HomeAssistantAPI') as mock_api_class:
            # Mock successful API validation
            mock_api = AsyncMock()
            mock_api.validate_config.return_value = {
                "valid": True,
                "errors": [],
                "messages": ["Configuration loaded successfully"]
            }
            mock_api_class.return_value.__aenter__.return_value = mock_api

            # Test syntax-only validation (should work without API)
            result = await _run_validation(syntax_only=True, fix=False)
            assert result == 0

            # Test full validation (should use API)
            result = await _run_validation(syntax_only=False, fix=False)
            assert result == 0

    @pytest.mark.asyncio
    async def test_entities_integration_success(self, test_config, mock_home_assistant_api, mock_database_manager, mock_registry_manager):
        """Test full entities command integration."""
        with patch('ha_tools.commands.entities.DatabaseManager', mock_database_manager.__class__), \
             patch('ha_tools.commands.entities.HomeAssistantAPI', mock_home_assistant_api.__class__), \
             patch('ha_tools.commands.entities.RegistryManager') as mock_registry_class:

            mock_registry_class.return_value = mock_registry_manager

            # Test basic entity discovery
            result = await _run_entities_command(
                search=None,
                include=None,
                history=None,
                limit=100,
                format="markdown"
            )
            assert result == 0

            # Test entity discovery with state
            result = await _run_entities_command(
                search="sensor.*",
                include="state",
                history=None,
                limit=10,
                format="json"
            )
            assert result == 0

    @pytest.mark.asyncio
    async def test_errors_integration_success(self, test_config, mock_home_assistant_api, mock_database_manager, mock_registry_manager, sample_log_file: Path):
        """Test full errors command integration."""
        # Update config to point to sample log
        test_config.ha_config_path = str(sample_log_file.parent)

        with patch('ha_tools.commands.errors.DatabaseManager', mock_database_manager.__class__), \
             patch('ha_tools.commands.errors.HomeAssistantAPI', mock_home_assistant_api.__class__), \
             patch('ha_tools.commands.errors.RegistryManager') as mock_registry_class:

            mock_registry_class.return_value = mock_registry_manager

            # Test current errors
            result = await _run_errors_command(
                current=True,
                log=None,
                entity=None,
                integration=None,
                correlation=False,
                format="markdown"
            )
            assert result == 0

            # Test log analysis
            result = await _run_errors_command(
                current=False,
                log="24h",
                entity="temperature",
                integration=None,
                correlation=True,
                format="json"
            )
            assert result == 0

    def test_setup_command_integration(self, temp_dir: Path):
        """Test setup command integration."""
        # Mock the setup wizard
        with patch('ha_tools.lib.setup_wizard.run_setup') as mock_setup:
            mock_setup.return_value = None

            result = self.runner.invoke(app, ["setup"])
            assert result.exit_code == 0

    def test_test_connection_command_success(self, sample_config_file: Path):
        """Test test-connection command with successful connections."""
        # Set up configuration
        import ha_tools.config
        ha_tools.config.HaToolsConfig.set_config_path(sample_config_file)

        with patch('ha_tools.lib.database.DatabaseManager') as mock_db_class, \
             patch('ha_tools.lib.rest_api.HomeAssistantAPI') as mock_api_class:

            # Mock successful connections
            mock_db = AsyncMock()
            mock_db.test_connection.return_value = None
            mock_db_class.return_value.__aenter__.return_value = mock_db

            mock_api = AsyncMock()
            mock_api.test_connection.return_value = None
            mock_api_class.return_value.__aenter__.return_value = mock_api

            result = self.runner.invoke(app, ["test-connection"])
            assert result.exit_code == 0
            assert "All connections test successful!" in result.stdout

    def test_test_connection_command_failure(self, sample_config_file: Path):
        """Test test-connection command with connection failures."""
        # Set up configuration
        import ha_tools.config
        ha_tools.config.HaToolsConfig.set_config_path(sample_config_file)

        with patch('ha_tools.lib.database.DatabaseManager') as mock_db_class:
            # Mock database connection failure
            mock_db = AsyncMock()
            mock_db.test_connection.side_effect = Exception("Database connection failed")
            mock_db_class.return_value.__aenter__.return_value = mock_db

            result = self.runner.invoke(app, ["test-connection"])
            assert result.exit_code == 1
            assert "Connection test failed" in result.stdout

    @pytest.mark.asyncio
    async def test_error_handling_integration(self, sample_config_file: Path):
        """Test error handling across integrated components."""
        import ha_tools.config
        ha_tools.config.HaToolsConfig.set_config_path(sample_config_file)

        # Test configuration loading error
        with patch('ha_tools.config.HaToolsConfig.load') as mock_load:
            mock_load.side_effect = ValueError("Invalid configuration")

            result = await _run_validation(syntax_only=True, fix=False)
            assert result == 3  # Configuration error

            result = await _run_entities_command(
                search=None, include=None, history=None, limit=None, format="markdown"
            )
            assert result == 3

            result = await _run_errors_command(
                current=False, log=None, entity=None, integration=None,
                correlation=False, format="markdown"
            )
            assert result == 3

    @pytest.mark.asyncio
    async def test_data_flow_integration(self, test_config, mock_home_assistant_api, mock_database_manager, mock_registry_manager):
        """Test data flow between components."""
        # Set up realistic mock data flow
        mock_home_assistant_api.get_states.return_value = [
            {
                "entity_id": "sensor.temperature",
                "state": "20.5",
                "attributes": {"unit_of_measurement": "°C", "friendly_name": "Temperature"}
            }
        ]

        mock_database_manager.get_entity_states.return_value = [
            {
                "entity_id": "sensor.temperature",
                "state": "19.0",
                "last_changed": "2024-01-01T11:00:00+00:00"
            }
        ]

        with patch('ha_tools.commands.entities.DatabaseManager', mock_database_manager.__class__), \
             patch('ha_tools.commands.entities.HomeAssistantAPI', mock_home_assistant_api.__class__), \
             patch('ha_tools.commands.entities.RegistryManager') as mock_registry_class:

            mock_registry_class.return_value = mock_registry_manager

            # Test that data flows correctly through the system
            result = await _run_entities_command(
                search="sensor.*",
                include="state,history",
                history="24h",
                limit=10,
                format="json"
            )
            assert result == 0

            # Verify the mocks were called in the correct order
            mock_registry_manager.load_all_registries.assert_called_once()
            mock_registry_manager.search_entities.assert_called_once_with("sensor.*")

    def test_cli_signal_handling(self):
        """Test CLI handles keyboard interrupts gracefully."""
        with patch('ha_tools.commands.validate._run_validation') as mock_run:
            mock_run.side_effect = KeyboardInterrupt()

            result = self.runner.invoke(app, ["validate"])
            assert result.exit_code == 1  # Keyboard interrupt should result in exit code 1

    def test_cli_unexpected_error_handling(self):
        """Test CLI handles unexpected errors gracefully."""
        with patch('ha_tools.commands.validate._run_validation') as mock_run:
            mock_run.side_effect = Exception("Unexpected error")

            result = self.runner.invoke(app, ["validate"])
            assert result.exit_code == 1  # Unexpected error should result in exit code 1


class TestEndToEndWorkflows:
    """Test end-to-end workflows that mirror real usage."""

    @pytest.mark.asyncio
    async def test_configuration_change_workflow(self, sample_ha_config: Path, sample_config_file: Path):
        """Test typical workflow after configuration changes."""
        import ha_tools.config
        ha_tools.config.HaToolsConfig.set_config_path(sample_config_file)

        with patch('ha_tools.lib.rest_api.HomeAssistantAPI') as mock_api_class:
            # Mock API responses
            mock_api = AsyncMock()
            mock_api.validate_config.return_value = {
                "valid": True,
                "errors": [],
                "messages": []
            }
            mock_api_class.return_value.__aenter__.return_value = mock_api

            # Step 1: Quick syntax validation
            result = await _run_validation(syntax_only=True, fix=False)
            assert result == 0

            # Step 2: Check affected entities
            # (This would normally involve searching for entities related to changes)
            # For integration test, just verify entities command works
            with patch('ha_tools.commands.entities.DatabaseManager') as mock_db_class, \
                 patch('ha_tools.commands.entities.RegistryManager') as mock_registry_class:

                mock_db = AsyncMock()
                mock_db_class.return_value.__aenter__.return_value = mock_db
                mock_registry_class.return_value = MagicMock()

                entities_result = await _run_entities_command(
                    search=None, include=None, history=None, limit=10, format="markdown"
                )
                assert entities_result == 0

            # Step 3: Full validation
            result = await _run_validation(syntax_only=False, fix=False)
            assert result == 0

    @pytest.mark.asyncio
    async def test_debugging_workflow(self, test_config, mock_home_assistant_api, mock_database_manager, mock_registry_manager, sample_log_file: Path):
        """Test typical debugging workflow for issues."""
        # Update config to point to sample log
        test_config.ha_config_path = str(sample_log_file.parent)

        with patch('ha_tools.commands.errors.DatabaseManager', mock_database_manager.__class__), \
             patch('ha_tools.commands.entities.HomeAssistantAPI', mock_home_assistant_api.__class__), \
             patch('ha_tools.commands.entities.RegistryManager') as mock_registry_class, \
             patch('ha_tools.commands.errors.RegistryManager') as mock_error_registry_class:

            mock_registry_class.return_value = mock_registry_manager
            mock_error_registry_class.return_value = mock_registry_manager

            # User reports: "Heating automation stopped working"

            # Step 1: Check entity behavior history
            entities_result = await _run_entities_command(
                search="heizung*",
                include="history",
                history="24h",
                limit=20,
                format="markdown"
            )
            assert entities_result == 0

            # Step 2: Look for related errors
            errors_result = await _run_errors_command(
                current=False,
                log="24h",
                entity="heizung*",
                integration=None,
                correlation=True,
                format="markdown"
            )
            assert errors_result == 0

            # Step 3: Analyze automation dependencies
            entities_result = await _run_entities_command(
                search="automation.heating*",
                include="relations",
                history=None,
                limit=10,
                format="markdown"
            )
            assert entities_result == 0