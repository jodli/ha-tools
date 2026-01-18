"""
Integration tests for ha-tools CLI commands.

Tests end-to-end command execution with mocked external dependencies.
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from ha_tools.cli import app
from ha_tools.commands.entities import _run_entities_command
from ha_tools.commands.logs import _run_logs_command
from ha_tools.commands.validate import _run_validation


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
        assert "logs" in result.stdout

    def test_validate_command_help(self):
        """Test validate command help."""
        result = self.runner.invoke(app, ["validate", "--help"])
        assert result.exit_code == 0
        assert "--syntax-only" in result.stdout
        assert "--expand-includes" in result.stdout

    def test_entities_command_help(self):
        """Test entities command help."""
        result = self.runner.invoke(app, ["entities", "--help"])
        assert result.exit_code == 0
        assert "--search" in result.stdout
        assert "--include" in result.stdout
        assert "--history" in result.stdout

    def test_logs_command_help(self):
        """Test logs command help."""
        result = self.runner.invoke(app, ["logs", "--help"])
        assert result.exit_code == 0
        assert "--current" in result.stdout
        assert "--log" in result.stdout
        assert "--entity" in result.stdout
        assert "--level" in result.stdout

    @pytest.mark.asyncio
    async def test_validate_integration_success(
        self, sample_ha_config: Path, sample_config_file: Path
    ):
        """Test full validation integration with mocked dependencies."""
        # Set up configuration
        import ha_tools.config

        ha_tools.config.HaToolsConfig.set_config_path(sample_config_file)

        with patch("ha_tools.commands.validate.HomeAssistantAPI") as mock_api_class:
            # Mock successful API validation
            mock_api = AsyncMock()
            mock_api.validate_config.return_value = {
                "valid": True,
                "errors": [],
                "messages": ["Configuration loaded successfully"],
            }
            mock_api_class.return_value.__aenter__.return_value = mock_api

            # Test syntax-only validation (should work without API)
            result = await _run_validation(syntax_only=True, expand_includes=False)
            assert result == 0

            # Test full validation (should use API)
            result = await _run_validation(syntax_only=False, expand_includes=False)
            assert result == 0

    @pytest.mark.asyncio
    async def test_entities_integration_success(
        self,
        test_config,
        mock_home_assistant_api,
        mock_database_manager,
        mock_registry_manager,
    ):
        """Test full entities command integration."""
        with (
            patch("ha_tools.commands.entities.DatabaseManager") as mock_db_class,
            patch("ha_tools.commands.entities.HomeAssistantAPI") as mock_api_class,
            patch("ha_tools.commands.entities.RegistryManager") as mock_registry_class,
        ):
            # Setup async context manager mocks
            mock_db_class.return_value.__aenter__ = AsyncMock(
                return_value=mock_database_manager
            )
            mock_db_class.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_api_class.return_value.__aenter__ = AsyncMock(
                return_value=mock_home_assistant_api
            )
            mock_api_class.return_value.__aexit__ = AsyncMock(return_value=None)

            mock_registry_class.return_value = mock_registry_manager

            # Test basic entity discovery
            result = await _run_entities_command(
                search=None, include=None, history=None, limit=100
            )
            assert result == 0

            # Test entity discovery with state
            result = await _run_entities_command(
                search="sensor.*",
                include="state",
                history=None,
                limit=10,
            )
            assert result == 0

    @pytest.mark.asyncio
    async def test_logs_integration_success(
        self,
        test_config,
        mock_home_assistant_api,
        mock_database_manager,
        mock_registry_manager,
        sample_log_file: Path,
    ):
        """Test full logs command integration."""
        # Update config to point to sample log
        test_config.ha_config_path = str(sample_log_file.parent)

        with (
            patch("ha_tools.commands.logs.DatabaseManager") as mock_db_class,
            patch("ha_tools.commands.logs.HomeAssistantAPI") as mock_api_class,
            patch("ha_tools.commands.logs.RegistryManager") as mock_registry_class,
        ):
            # Setup async context manager mocks with properly configured fixtures
            mock_db_class.return_value.__aenter__ = AsyncMock(
                return_value=mock_database_manager
            )
            mock_db_class.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_api_class.return_value.__aenter__ = AsyncMock(
                return_value=mock_home_assistant_api
            )
            mock_api_class.return_value.__aexit__ = AsyncMock(return_value=None)

            mock_registry_class.return_value = mock_registry_manager

            # Test current logs
            result = await _run_logs_command(
                current=True,
                log=None,
                levels={"error", "warning"},
                entity=None,
                integration=None,
                correlation=False,
            )
            assert result == 0

            # Test log analysis
            result = await _run_logs_command(
                current=False,
                log="24h",
                levels={"error", "warning"},
                entity="temperature",
                integration=None,
                correlation=True,
            )
            assert result == 0

    def test_setup_command_integration(self, temp_dir: Path):
        """Test setup command integration."""
        # Mock the setup wizard
        with patch("ha_tools.lib.setup_wizard.run_setup") as mock_setup:
            mock_setup.return_value = None

            result = self.runner.invoke(app, ["setup"])
            assert result.exit_code == 0

    def test_test_connection_command_success(self, sample_config_file: Path):
        """Test test-connection command with successful connections."""
        # Set up configuration
        import ha_tools.config

        ha_tools.config.HaToolsConfig.set_config_path(sample_config_file)

        with (
            patch("ha_tools.lib.database.DatabaseManager") as mock_db_class,
            patch("ha_tools.lib.rest_api.HomeAssistantAPI") as mock_api_class,
        ):
            # Mock successful connections
            mock_db = AsyncMock()
            mock_db.connect = AsyncMock()
            mock_db.test_connection = AsyncMock()
            mock_db.close = AsyncMock()
            mock_db_class.return_value = mock_db

            mock_api = AsyncMock()
            mock_api.test_connection = AsyncMock()
            mock_api_class.return_value = mock_api

            result = self.runner.invoke(app, ["test-connection"])
            assert result.exit_code == 0
            assert "All connections test successful!" in result.output

    def test_test_connection_command_failure(self, sample_config_file: Path):
        """Test test-connection command with connection failures."""
        # Set up configuration
        import ha_tools.config

        ha_tools.config.HaToolsConfig.set_config_path(sample_config_file)

        with patch("ha_tools.lib.database.DatabaseManager") as mock_db_class:
            # Mock database connection failure
            mock_db = AsyncMock()
            mock_db.test_connection.side_effect = Exception(
                "Database connection failed"
            )
            mock_db_class.return_value.__aenter__.return_value = mock_db

            result = self.runner.invoke(app, ["test-connection"])
            assert result.exit_code == 1
            assert "Connection test failed" in result.output

    @pytest.mark.asyncio
    async def test_error_handling_integration(self, sample_config_file: Path):
        """Test error handling across integrated components."""
        import ha_tools.config

        ha_tools.config.HaToolsConfig.set_config_path(sample_config_file)

        # Test configuration loading error
        with patch("ha_tools.config.HaToolsConfig.load") as mock_load:
            mock_load.side_effect = ValueError("Invalid configuration")

            result = await _run_validation(syntax_only=True, expand_includes=False)
            assert result == 3  # Configuration error

            result = await _run_entities_command(
                search=None, include=None, history=None, limit=None
            )
            assert result == 3

            result = await _run_logs_command(
                current=False,
                log=None,
                levels={"error", "warning"},
                entity=None,
                integration=None,
                correlation=False,
            )
            assert result == 3

    @pytest.mark.asyncio
    async def test_data_flow_integration(
        self,
        test_config,
        mock_home_assistant_api,
        mock_database_manager,
        mock_registry_manager,
    ):
        """Test data flow between components."""
        # Set up realistic mock data flow
        mock_home_assistant_api.get_states.return_value = [
            {
                "entity_id": "sensor.temperature",
                "state": "20.5",
                "attributes": {
                    "unit_of_measurement": "°C",
                    "friendly_name": "Temperature",
                },
            }
        ]

        mock_database_manager.get_entity_states.return_value = [
            {
                "entity_id": "sensor.temperature",
                "state": "19.0",
                "last_changed": "2024-01-01T11:00:00+00:00",
            }
        ]

        with (
            patch("ha_tools.commands.entities.DatabaseManager") as mock_db_class,
            patch("ha_tools.commands.entities.HomeAssistantAPI") as mock_api_class,
            patch("ha_tools.commands.entities.RegistryManager") as mock_registry_class,
        ):
            # Setup async context manager mocks
            mock_db_class.return_value.__aenter__ = AsyncMock(
                return_value=mock_database_manager
            )
            mock_db_class.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_api_class.return_value.__aenter__ = AsyncMock(
                return_value=mock_home_assistant_api
            )
            mock_api_class.return_value.__aexit__ = AsyncMock(return_value=None)

            mock_registry_class.return_value = mock_registry_manager

            # Test that data flows correctly through the system
            result = await _run_entities_command(
                search="sensor.*",
                include="state,history",
                history="24h",
                limit=10,
            )
            assert result == 0

            # Verify the mocks were called in the correct order
            mock_registry_manager.load_all_registries.assert_called_once()
            mock_registry_manager.search_entities.assert_called_once_with("sensor.*")

    def test_cli_signal_handling(self):
        """Test CLI handles keyboard interrupts gracefully."""
        with patch("ha_tools.commands.validate._run_validation") as mock_run:
            mock_run.side_effect = KeyboardInterrupt()

            result = self.runner.invoke(app, ["validate"])
            assert (
                result.exit_code == 1
            )  # Keyboard interrupt should result in exit code 1

    def test_cli_unexpected_error_handling(self):
        """Test CLI handles unexpected errors gracefully."""
        with patch("ha_tools.commands.validate._run_validation") as mock_run:
            mock_run.side_effect = Exception("Unexpected error")

            result = self.runner.invoke(app, ["validate"])
            assert (
                result.exit_code == 1
            )  # Unexpected error should result in exit code 1


class TestEndToEndWorkflows:
    """Test end-to-end workflows that mirror real usage."""

    @pytest.mark.asyncio
    async def test_configuration_change_workflow(
        self, sample_ha_config: Path, sample_config_file: Path
    ):
        """Test typical workflow after configuration changes."""
        import ha_tools.config

        ha_tools.config.HaToolsConfig.set_config_path(sample_config_file)

        # Patch where HomeAssistantAPI is used (in validate module)
        with patch("ha_tools.commands.validate.HomeAssistantAPI") as mock_api_class:
            # Mock API responses
            mock_api = AsyncMock()
            mock_api.validate_config.return_value = {
                "valid": True,
                "errors": [],
                "messages": [],
            }
            mock_api_class.return_value.__aenter__.return_value = mock_api
            mock_api_class.return_value.__aexit__.return_value = None

            # Step 1: Quick syntax validation
            result = await _run_validation(syntax_only=True, expand_includes=False)
            assert result == 0

            # Step 2: Check affected entities
            # (This would normally involve searching for entities related to changes)
            # For integration test, just verify entities command works
            with (
                patch("ha_tools.commands.entities.DatabaseManager") as mock_db_class,
                patch(
                    "ha_tools.commands.entities.RegistryManager"
                ) as mock_registry_class,
            ):
                mock_db = AsyncMock()
                # Mock sync methods to avoid unawaited coroutines
                mock_db.is_connected = MagicMock(return_value=True)
                mock_db.get_connection_error = MagicMock(return_value=None)
                mock_db_class.return_value.__aenter__ = AsyncMock(return_value=mock_db)
                mock_db_class.return_value.__aexit__ = AsyncMock(return_value=None)

                # Create a mock registry with async support
                mock_registry = AsyncMock()
                mock_registry.load_all_registries = AsyncMock(return_value=None)
                mock_registry._entity_registry = []
                mock_registry.search_entities = MagicMock(return_value=[])
                mock_registry_class.return_value = mock_registry

                entities_result = await _run_entities_command(
                    search=None, include=None, history=None, limit=10
                )
                assert entities_result == 0

            # Step 3: Full validation
            result = await _run_validation(syntax_only=False, expand_includes=False)
            assert result == 0

    @pytest.mark.asyncio
    async def test_debugging_workflow(
        self,
        test_config,
        mock_home_assistant_api,
        mock_database_manager,
        mock_registry_manager,
        sample_log_file: Path,
    ):
        """Test typical debugging workflow for issues."""
        # Update config to point to sample log
        test_config.ha_config_path = str(sample_log_file.parent)

        with (
            patch("ha_tools.commands.logs.DatabaseManager") as mock_logs_db_class,
            patch(
                "ha_tools.commands.entities.DatabaseManager"
            ) as mock_entities_db_class,
            patch(
                "ha_tools.commands.entities.HomeAssistantAPI"
            ) as mock_entities_api_class,
            patch("ha_tools.commands.logs.HomeAssistantAPI") as mock_logs_api_class,
            patch("ha_tools.commands.entities.RegistryManager") as mock_registry_class,
            patch("ha_tools.commands.logs.RegistryManager") as mock_logs_registry_class,
        ):
            # Setup database mocks with sync methods properly mocked
            mock_logs_db_class.return_value.__aenter__ = AsyncMock(
                return_value=mock_database_manager
            )
            mock_logs_db_class.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_entities_db_class.return_value.__aenter__ = AsyncMock(
                return_value=mock_database_manager
            )
            mock_entities_db_class.return_value.__aexit__ = AsyncMock(return_value=None)

            # Setup API mocks
            mock_entities_api_class.return_value.__aenter__ = AsyncMock(
                return_value=mock_home_assistant_api
            )
            mock_entities_api_class.return_value.__aexit__ = AsyncMock(
                return_value=None
            )
            mock_logs_api_class.return_value.__aenter__ = AsyncMock(
                return_value=mock_home_assistant_api
            )
            mock_logs_api_class.return_value.__aexit__ = AsyncMock(return_value=None)

            mock_registry_class.return_value = mock_registry_manager
            mock_logs_registry_class.return_value = mock_registry_manager

            # User reports: "Heating automation stopped working"

            # Step 1: Check entity behavior history
            entities_result = await _run_entities_command(
                search="heizung*",
                include="history",
                history="24h",
                limit=20,
            )
            assert entities_result == 0

            # Step 2: Look for related logs
            logs_result = await _run_logs_command(
                current=False,
                log="24h",
                levels={"error", "warning"},
                entity="heizung*",
                integration=None,
                correlation=True,
            )
            assert logs_result == 0

            # Step 3: Analyze automation dependencies
            entities_result = await _run_entities_command(
                search="automation.heating*",
                include="relations",
                history=None,
                limit=10,
            )
            assert entities_result == 0
