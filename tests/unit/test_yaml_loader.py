"""
Unit tests for ha-tools YAML loader.

Tests Home Assistant custom YAML tag support (!include, !secret, etc.).
"""

import tempfile
from pathlib import Path

import pytest
import yaml

from ha_tools.lib.yaml_loader import (
    HA_YAML_TAGS,
    HAYAMLLoader,
    load_secrets,
    load_yaml,
    load_yaml_file,
)


class TestHAYAMLLoader:
    """Test custom YAML loader functionality."""

    def test_all_ha_tags_registered(self):
        """Test that all HA tags are registered with the loader."""
        expected_tags = [
            "!include",
            "!include_dir_list",
            "!include_dir_merge_list",
            "!include_dir_named",
            "!include_dir_merge_named",
            "!secret",
            "!env_var",
        ]
        assert HA_YAML_TAGS == expected_tags

    def test_stub_mode_include(self):
        """Test !include returns stub in stub mode."""
        content = "automation: !include automations.yaml"
        result = load_yaml(content, expand_includes=False)
        assert result["automation"] == "<!include:automations.yaml>"

    def test_stub_mode_include_dir_list(self):
        """Test !include_dir_list returns stub in stub mode."""
        content = "scene: !include_dir_list scenes/"
        result = load_yaml(content, expand_includes=False)
        assert result["scene"] == "<!include_dir_list:scenes/>"

    def test_stub_mode_include_dir_merge_list(self):
        """Test !include_dir_merge_list returns stub in stub mode."""
        content = "automation: !include_dir_merge_list automations/"
        result = load_yaml(content, expand_includes=False)
        assert result["automation"] == "<!include_dir_merge_list:automations/>"

    def test_stub_mode_include_dir_named(self):
        """Test !include_dir_named returns stub in stub mode."""
        content = "script: !include_dir_named scripts/"
        result = load_yaml(content, expand_includes=False)
        assert result["script"] == "<!include_dir_named:scripts/>"

    def test_stub_mode_include_dir_merge_named(self):
        """Test !include_dir_merge_named returns stub in stub mode."""
        content = "group: !include_dir_merge_named groups/"
        result = load_yaml(content, expand_includes=False)
        assert result["group"] == "<!include_dir_merge_named:groups/>"

    def test_stub_mode_secret(self):
        """Test !secret returns stub in stub mode."""
        content = "password: !secret db_password"
        result = load_yaml(content, expand_includes=False)
        assert result["password"] == "<!secret:db_password>"

    def test_stub_mode_env_var(self):
        """Test !env_var returns stub in stub mode."""
        content = "api_key: !env_var API_KEY"
        result = load_yaml(content, expand_includes=False)
        assert result["api_key"] == "<!env_var:API_KEY>"

    def test_stub_mode_complex_config(self):
        """Test stub mode with complex HA configuration."""
        content = """
homeassistant:
  name: Test Home
  unit_system: metric

automation: !include automations.yaml
script: !include_dir_named scripts/
sensor: !include_dir_merge_list sensors/
api_password: !secret api_password
"""
        result = load_yaml(content, expand_includes=False)

        assert result["homeassistant"]["name"] == "Test Home"
        assert result["automation"] == "<!include:automations.yaml>"
        assert result["script"] == "<!include_dir_named:scripts/>"
        assert result["sensor"] == "<!include_dir_merge_list:sensors/>"
        assert result["api_password"] == "<!secret:api_password>"

    def test_standard_yaml_still_works(self):
        """Test that standard YAML without HA tags still parses correctly."""
        content = """
homeassistant:
  name: Test Home
  latitude: 52.52
  longitude: 13.405

sensor:
  - platform: template
    sensors:
      test_sensor:
        value_template: "{{ 42 }}"
"""
        result = load_yaml(content, expand_includes=False)

        assert result["homeassistant"]["name"] == "Test Home"
        assert result["homeassistant"]["latitude"] == 52.52
        assert len(result["sensor"]) == 1
        assert result["sensor"][0]["platform"] == "template"

    def test_yaml_syntax_error_raises(self):
        """Test that YAML syntax errors are properly raised."""
        content = "invalid: yaml: content: ["

        with pytest.raises(yaml.YAMLError):
            load_yaml(content)


class TestExpandIncludesMode:
    """Test expand includes mode (full resolution)."""

    def test_expand_include_single_file(self, temp_dir: Path):
        """Test !include expands single file."""
        # Create included file
        included_file = temp_dir / "automations.yaml"
        included_file.write_text("- alias: Test Automation\n  trigger: []")

        # Create main config
        main_content = "automation: !include automations.yaml"

        result = load_yaml(main_content, config_path=temp_dir, expand_includes=True)

        assert isinstance(result["automation"], list)
        assert result["automation"][0]["alias"] == "Test Automation"

    def test_expand_include_dir_list(self, temp_dir: Path):
        """Test !include_dir_list expands directory as list."""
        # Create directory with files
        scenes_dir = temp_dir / "scenes"
        scenes_dir.mkdir()
        (scenes_dir / "scene1.yaml").write_text("name: Scene 1")
        (scenes_dir / "scene2.yaml").write_text("name: Scene 2")

        main_content = "scene: !include_dir_list scenes/"

        result = load_yaml(main_content, config_path=temp_dir, expand_includes=True)

        assert isinstance(result["scene"], list)
        assert len(result["scene"]) == 2

    def test_expand_include_dir_merge_list(self, temp_dir: Path):
        """Test !include_dir_merge_list merges lists from directory."""
        # Create directory with list files
        automations_dir = temp_dir / "automations"
        automations_dir.mkdir()
        (automations_dir / "auto1.yaml").write_text("- alias: Auto 1\n- alias: Auto 2")
        (automations_dir / "auto2.yaml").write_text("- alias: Auto 3")

        main_content = "automation: !include_dir_merge_list automations/"

        result = load_yaml(main_content, config_path=temp_dir, expand_includes=True)

        assert isinstance(result["automation"], list)
        assert len(result["automation"]) == 3

    def test_expand_include_dir_named(self, temp_dir: Path):
        """Test !include_dir_named includes as dict with filename keys."""
        # Create directory with files
        scripts_dir = temp_dir / "scripts"
        scripts_dir.mkdir()
        (scripts_dir / "morning.yaml").write_text("sequence: []")
        (scripts_dir / "evening.yaml").write_text("sequence: []")

        main_content = "script: !include_dir_named scripts/"

        result = load_yaml(main_content, config_path=temp_dir, expand_includes=True)

        assert isinstance(result["script"], dict)
        assert "morning" in result["script"]
        assert "evening" in result["script"]

    def test_expand_secret(self, temp_dir: Path):
        """Test !secret expands from secrets dict."""
        secrets = {"db_password": "supersecret123"}

        content = "password: !secret db_password"
        result = load_yaml(
            content, config_path=temp_dir, expand_includes=True, secrets=secrets
        )

        assert result["password"] == "supersecret123"

    def test_expand_secret_not_found_raises(self, temp_dir: Path):
        """Test !secret raises error when secret not found."""
        secrets = {}

        content = "password: !secret missing_secret"

        with pytest.raises(yaml.YAMLError, match="Secret 'missing_secret' not found"):
            load_yaml(
                content, config_path=temp_dir, expand_includes=True, secrets=secrets
            )

    def test_expand_env_var(self, temp_dir: Path, monkeypatch):
        """Test !env_var expands environment variable."""
        monkeypatch.setenv("TEST_API_KEY", "test_key_value")

        content = "api_key: !env_var TEST_API_KEY"
        result = load_yaml(content, config_path=temp_dir, expand_includes=True)

        assert result["api_key"] == "test_key_value"

    def test_expand_env_var_not_set_raises(self, temp_dir: Path):
        """Test !env_var raises error when env var not set."""
        content = "api_key: !env_var NONEXISTENT_VAR_12345"

        with pytest.raises(yaml.YAMLError, match="Environment variable.*not set"):
            load_yaml(content, config_path=temp_dir, expand_includes=True)

    def test_include_file_not_found_raises(self, temp_dir: Path):
        """Test !include raises error when file not found."""
        content = "automation: !include nonexistent.yaml"

        with pytest.raises(yaml.YAMLError, match="Include file not found"):
            load_yaml(content, config_path=temp_dir, expand_includes=True)

    def test_include_dir_not_found_raises(self, temp_dir: Path):
        """Test !include_dir_* raises error when directory not found."""
        content = "scene: !include_dir_list nonexistent/"

        with pytest.raises(yaml.YAMLError, match="Include directory not found"):
            load_yaml(content, config_path=temp_dir, expand_includes=True)


class TestCircularIncludeDetection:
    """Test circular include detection."""

    def test_circular_include_detected(self, temp_dir: Path):
        """Test that circular includes are detected and raise error."""
        # Create circular include: a.yaml -> b.yaml -> a.yaml
        (temp_dir / "a.yaml").write_text("include_b: !include b.yaml")
        (temp_dir / "b.yaml").write_text("include_a: !include a.yaml")

        with pytest.raises(yaml.YAMLError, match="Circular include detected"):
            load_yaml_file(temp_dir / "a.yaml", expand_includes=True)

    def test_self_include_detected(self, temp_dir: Path):
        """Test that self-includes are detected."""
        (temp_dir / "self.yaml").write_text("self_ref: !include self.yaml")

        with pytest.raises(yaml.YAMLError, match="Circular include detected"):
            load_yaml_file(temp_dir / "self.yaml", expand_includes=True)


class TestLoadSecrets:
    """Test secrets loading functionality."""

    def test_load_secrets_from_file(self, temp_dir: Path):
        """Test loading secrets from secrets.yaml."""
        secrets_file = temp_dir / "secrets.yaml"
        secrets_file.write_text("db_password: secret123\napi_key: key456")

        secrets = load_secrets(temp_dir)

        assert secrets["db_password"] == "secret123"
        assert secrets["api_key"] == "key456"

    def test_load_secrets_file_not_found(self, temp_dir: Path):
        """Test loading secrets when file doesn't exist returns empty dict."""
        secrets = load_secrets(temp_dir)
        assert secrets == {}

    def test_load_secrets_invalid_yaml(self, temp_dir: Path):
        """Test loading secrets with invalid YAML returns empty dict."""
        secrets_file = temp_dir / "secrets.yaml"
        secrets_file.write_text("invalid: yaml: [")

        secrets = load_secrets(temp_dir)
        assert secrets == {}

    def test_load_secrets_non_dict(self, temp_dir: Path):
        """Test loading secrets with non-dict content returns empty dict."""
        secrets_file = temp_dir / "secrets.yaml"
        secrets_file.write_text("- item1\n- item2")

        secrets = load_secrets(temp_dir)
        assert secrets == {}


class TestLoadYamlFile:
    """Test load_yaml_file convenience function."""

    def test_load_yaml_file_success(self, temp_dir: Path):
        """Test loading YAML file successfully."""
        yaml_file = temp_dir / "config.yaml"
        yaml_file.write_text("homeassistant:\n  name: Test")

        result = load_yaml_file(yaml_file)

        assert result["homeassistant"]["name"] == "Test"

    def test_load_yaml_file_with_ha_tags(self, temp_dir: Path):
        """Test loading YAML file with HA tags in stub mode."""
        yaml_file = temp_dir / "config.yaml"
        yaml_file.write_text("automation: !include automations.yaml")

        result = load_yaml_file(yaml_file, expand_includes=False)

        assert result["automation"] == "<!include:automations.yaml>"

    def test_load_yaml_file_not_found(self, temp_dir: Path):
        """Test loading non-existent file raises error."""
        yaml_file = temp_dir / "nonexistent.yaml"

        with pytest.raises(FileNotFoundError):
            load_yaml_file(yaml_file)
