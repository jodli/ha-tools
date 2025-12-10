"""
Unit tests for ha-tools validate command.

Tests YAML validation, configuration checking, and error reporting.
"""

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml

from ha_tools.commands.validate import (
    _generate_semantic_report,
    _generate_syntax_report,
    _run_full_validation,
    _run_syntax_validation,
    _run_validation,
    _validate_yaml_file,
)
from ha_tools.lib.output import MarkdownFormatter


class TestValidateCommand:
    """Test validate command functionality."""

    @pytest.mark.asyncio
    async def test_run_validation_syntax_only(self, test_config):
        """Test validation with syntax-only mode."""
        with patch("ha_tools.commands.validate._run_syntax_validation") as mock_syntax:
            mock_syntax.return_value = 0  # Success

            result = await _run_validation(syntax_only=True)
            assert result == 0
            mock_syntax.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_validation_full(self, test_config):
        """Test full validation mode."""
        with patch("ha_tools.commands.validate._run_full_validation") as mock_full:
            mock_full.return_value = 0  # Success

            result = await _run_validation(syntax_only=False)
            assert result == 0
            mock_full.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_syntax_validation_success(self, sample_ha_config: Path):
        """Test successful syntax validation."""
        # Create valid config
        config = MagicMock()
        config.ha_config_path = str(sample_ha_config)

        formatter = MarkdownFormatter()
        result = await _run_syntax_validation(config, formatter)

        assert result == 0  # Success

    @pytest.mark.asyncio
    async def test_run_syntax_validation_with_errors(self, temp_dir: Path):
        """Test syntax validation with YAML errors."""
        # Create invalid config file
        invalid_config = temp_dir / "config"
        invalid_config.mkdir()

        config_file = invalid_config / "configuration.yaml"
        with open(config_file, "w") as f:
            f.write("invalid: yaml: content: [")

        config = MagicMock()
        config.ha_config_path = str(invalid_config)

        formatter = MarkdownFormatter()
        result = await _run_syntax_validation(config, formatter)

        assert result == 2  # Validation errors exit code

    @pytest.mark.asyncio
    async def test_run_full_validation_syntax_errors(self, sample_ha_config: Path):
        """Test full validation that stops on syntax errors."""
        config = MagicMock()
        config.ha_config_path = str(sample_ha_config)

        with patch("ha_tools.commands.validate._run_syntax_validation") as mock_syntax:
            # Mock syntax validation failure
            mock_syntax.return_value = 2  # Syntax errors

            formatter = MarkdownFormatter()
            result = await _run_full_validation(config, formatter)

            assert result == 2  # Should return syntax error code

    @pytest.mark.asyncio
    async def test_validate_yaml_file_success(self, temp_dir: Path):
        """Test successful YAML file validation."""
        # Create valid YAML file
        yaml_file = temp_dir / "valid.yaml"
        valid_content = {
            "homeassistant": {"name": "Test Home", "unit_system": "metric"}
        }

        with open(yaml_file, "w") as f:
            yaml.dump(valid_content, f)

        errors, warnings = await _validate_yaml_file(yaml_file)

        assert len(errors) == 0
        assert len(warnings) == 0

    @pytest.mark.asyncio
    async def test_validate_yaml_file_not_found(self, temp_dir: Path):
        """Test YAML file validation when file doesn't exist."""
        missing_file = temp_dir / "missing.yaml"

        errors, warnings = await _validate_yaml_file(missing_file)

        assert len(errors) == 0
        assert len(warnings) == 1
        assert "File not found" in warnings[0]

    @pytest.mark.asyncio
    async def test_validate_yaml_file_syntax_error(self, temp_dir: Path):
        """Test YAML file validation with syntax error."""
        # Create invalid YAML file
        yaml_file = temp_dir / "invalid.yaml"
        with open(yaml_file, "w") as f:
            f.write("invalid: yaml: content: [")  # Invalid YAML

        errors, warnings = await _validate_yaml_file(yaml_file)

        assert len(errors) == 1
        assert "YAML syntax error" in errors[0]
        assert len(warnings) == 0

    @pytest.mark.asyncio
    async def test_validate_yaml_file_read_error(self, temp_dir: Path):
        """Test YAML file validation with file read error."""
        # Create file but mock open to raise error
        yaml_file = temp_dir / "error.yaml"
        yaml_file.touch()  # Create empty file

        with patch("builtins.open", side_effect=PermissionError("Permission denied")):
            errors, warnings = await _validate_yaml_file(yaml_file)

            assert len(errors) == 1
            assert "Error validating" in errors[0]
            assert len(warnings) == 0

    def test_generate_syntax_report_success(self):
        """Test syntax report generation for successful validation."""
        formatter = MarkdownFormatter()
        errors = []
        warnings = []

        _generate_syntax_report(formatter, errors, warnings)

        output = formatter.format()
        assert "✅ Syntax Validation" in output
        assert "All YAML files passed syntax validation!" in output

    def test_generate_syntax_report_with_errors(self):
        """Test syntax report generation with validation errors."""
        formatter = MarkdownFormatter()
        errors = ["YAML syntax error in file1.yaml"]
        warnings = ["File not found: file2.yaml"]

        _generate_syntax_report(formatter, errors, warnings)

        output = formatter.format()
        assert "❌ Syntax Errors" in output
        assert "⚠️ Warnings" in output
        assert "📊 Summary" in output
        assert "Status: **FAILED**" in output
        assert "Errors: 1" in output
        assert "Warnings: 1" in output

    def test_generate_syntax_report_with_warnings_only(self):
        """Test syntax report generation with warnings only."""
        formatter = MarkdownFormatter()
        errors = []
        warnings = ["File not found: optional_file.yaml"]

        _generate_syntax_report(formatter, errors, warnings)

        output = formatter.format()
        assert "Status: **PASSED**" in output  # Warnings don't cause failure
        assert "Errors: 0" in output
        assert "Warnings: 1" in output

    def test_generate_semantic_report_valid(self):
        """Test semantic report generation for valid configuration."""
        formatter = MarkdownFormatter()
        validation_result = {
            "valid": True,
            "errors": [],
            "messages": ["Configuration loaded successfully"],
        }

        _generate_semantic_report(formatter, validation_result)

        output = formatter.format()
        assert "🔍 Semantic Validation" in output
        assert "✅ Configuration Valid" in output
        assert "Home Assistant configuration is valid!" in output

    def test_generate_semantic_report_invalid(self):
        """Test semantic report generation for invalid configuration."""
        formatter = MarkdownFormatter()
        validation_result = {
            "valid": False,
            "errors": [
                "Component 'unknown_platform' not found",
                "Invalid integration configuration",
            ],
            "messages": ["Configuration has errors"],
        }

        _generate_semantic_report(formatter, validation_result)

        output = formatter.format()
        assert "❌ Configuration Invalid" in output
        assert "Component 'unknown_platform' not found" in output
        assert "Invalid integration configuration" in output

    def test_generate_semantic_report_with_messages(self):
        """Test semantic report generation with additional messages."""
        formatter = MarkdownFormatter()
        validation_result = {
            "valid": True,
            "errors": [],
            "messages": [
                "Component 'sensor' loaded",
                "Component 'switch' loaded",
                "3 automations loaded",
            ],
        }

        _generate_semantic_report(formatter, validation_result)

        output = formatter.format()
        assert "📝 Messages" in output
        assert "Component 'sensor' loaded" in output
        assert "Component 'switch' loaded" in output

    @pytest.mark.asyncio
    async def test_syntax_validation_package_files(self, temp_dir: Path):
        """Test syntax validation includes package files."""
        config_dir = temp_dir / "config"
        config_dir.mkdir()

        # Create main config
        main_config = config_dir / "configuration.yaml"
        with open(main_config, "w") as f:
            f.write("homeassistant:\n  name: Test")

        # Create packages directory with valid package
        packages_dir = config_dir / "packages"
        packages_dir.mkdir()

        package_file = packages_dir / "test_package.yaml"
        with open(package_file, "w") as f:
            f.write(
                "sensor:\n  - platform: template\n    sensors:\n      test:\n        value_template: 'ok'"
            )

        config = MagicMock()
        config.ha_config_path = str(config_dir)

        formatter = MarkdownFormatter()
        result = await _run_syntax_validation(config, formatter)

        assert result == 0

    @pytest.mark.asyncio
    async def test_syntax_validation_template_files(self, temp_dir: Path):
        """Test syntax validation includes template files."""
        config_dir = temp_dir / "config"
        config_dir.mkdir()

        # Create main config
        main_config = config_dir / "configuration.yaml"
        with open(main_config, "w") as f:
            f.write("homeassistant:\n  name: Test")

        # Create templates directory with valid template
        templates_dir = config_dir / "templates"
        templates_dir.mkdir()

        template_file = templates_dir / "test_template.yaml"
        with open(template_file, "w") as f:
            f.write(
                "test_template:\n  value_template: '{{ now().strftime(\"%H:%M\") }}'"
            )

        config = MagicMock()
        config.ha_config_path = str(config_dir)

        formatter = MarkdownFormatter()
        result = await _run_syntax_validation(
            config,
            formatter,
        )

        assert result == 0

    @pytest.mark.asyncio
    async def test_syntax_validation_missing_directories(self, temp_dir: Path):
        """Test syntax validation handles missing packages/templates directories."""
        config_dir = temp_dir / "config"
        config_dir.mkdir()

        # Create main config only
        main_config = config_dir / "configuration.yaml"
        with open(main_config, "w") as f:
            f.write("homeassistant:\n  name: Test")

        # Don't create packages or templates directories

        config = MagicMock()
        config.ha_config_path = str(config_dir)

        formatter = MarkdownFormatter()
        result = await _run_syntax_validation(
            config,
            formatter,
        )

        assert result == 0  # Should succeed with just main config

    @pytest.mark.asyncio
    async def test_syntax_validation_invalid_package_file(self, temp_dir: Path):
        """Test syntax validation with invalid package file."""
        config_dir = temp_dir / "config"
        config_dir.mkdir()

        # Create main config
        main_config = config_dir / "configuration.yaml"
        with open(main_config, "w") as f:
            f.write("homeassistant:\n  name: Test")

        # Create packages directory with invalid package
        packages_dir = config_dir / "packages"
        packages_dir.mkdir()

        invalid_package = packages_dir / "invalid_package.yaml"
        with open(invalid_package, "w") as f:
            f.write("invalid: yaml: content: [")  # Invalid YAML

        config = MagicMock()
        config.ha_config_path = str(config_dir)

        formatter = MarkdownFormatter()
        result = await _run_syntax_validation(
            config,
            formatter,
        )

        assert result == 2  # Validation errors

        output = formatter.format()
        assert "invalid_package.yaml" in output


class TestValidateWithHATags:
    """Test validate command with Home Assistant YAML tags."""

    @pytest.mark.asyncio
    async def test_validate_file_with_include_stub_mode(self, temp_dir: Path):
        """Test validation passes for file with !include in stub mode."""
        yaml_file = temp_dir / "config.yaml"
        yaml_file.write_text(
            "automation: !include automations.yaml\nsensor: !secret api_key"
        )

        errors, warnings = await _validate_yaml_file(yaml_file, expand_includes=False)

        assert len(errors) == 0
        assert len(warnings) == 0

    @pytest.mark.asyncio
    async def test_validate_file_with_all_ha_tags(self, temp_dir: Path):
        """Test validation passes for file with all HA tags in stub mode."""
        yaml_file = temp_dir / "config.yaml"
        content = """
homeassistant:
  name: Test

automation: !include automations.yaml
scene: !include_dir_list scenes/
sensor: !include_dir_merge_list sensors/
script: !include_dir_named scripts/
group: !include_dir_merge_named groups/
password: !secret db_password
api_key: !env_var API_KEY
"""
        yaml_file.write_text(content)

        errors, warnings = await _validate_yaml_file(yaml_file, expand_includes=False)

        assert len(errors) == 0
        assert len(warnings) == 0

    @pytest.mark.asyncio
    async def test_validate_file_with_include_expand_mode(self, temp_dir: Path):
        """Test validation with expand mode resolves includes."""
        # Create included file
        included_file = temp_dir / "automations.yaml"
        included_file.write_text("- alias: Test\n  trigger: []")

        # Create main config
        yaml_file = temp_dir / "config.yaml"
        yaml_file.write_text("automation: !include automations.yaml")

        errors, warnings = await _validate_yaml_file(yaml_file, expand_includes=True)

        assert len(errors) == 0
        assert len(warnings) == 0

    @pytest.mark.asyncio
    async def test_validate_file_expand_mode_missing_include(self, temp_dir: Path):
        """Test validation with expand mode fails when include file missing."""
        yaml_file = temp_dir / "config.yaml"
        yaml_file.write_text("automation: !include nonexistent.yaml")

        errors, warnings = await _validate_yaml_file(yaml_file, expand_includes=True)

        assert len(errors) == 1
        assert "Include file not found" in errors[0] or "nonexistent.yaml" in errors[0]

    @pytest.mark.asyncio
    async def test_syntax_validation_with_ha_tags(self, temp_dir: Path):
        """Test full syntax validation with HA tags in config."""
        config_dir = temp_dir / "config"
        config_dir.mkdir()

        # Create main config with HA tags
        main_config = config_dir / "configuration.yaml"
        main_config.write_text("""
homeassistant:
  name: Test

automation: !include automations.yaml
password: !secret db_password
""")

        config = MagicMock()
        config.ha_config_path = str(config_dir)

        formatter = MarkdownFormatter()
        result = await _run_syntax_validation(config, formatter, expand_includes=False)

        assert result == 0  # Success - HA tags handled in stub mode

    @pytest.mark.asyncio
    async def test_run_validation_passes_expand_includes(self, test_config):
        """Test that _run_validation passes expand_includes parameter."""
        with patch("ha_tools.commands.validate._run_syntax_validation") as mock_syntax:
            mock_syntax.return_value = 0

            await _run_validation(syntax_only=True, expand_includes=True)

            # Check that expand_includes was passed
            mock_syntax.assert_called_once()
            call_kwargs = mock_syntax.call_args
            # The third positional arg or expand_includes kwarg should be True
            assert (
                call_kwargs[0][2] is True
                or call_kwargs.kwargs.get("expand_includes") is True
            )
