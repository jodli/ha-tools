"""Config loading/saving."""

import textwrap

import pytest
from pydantic import ValidationError

from ha_tools.config import DatabaseConfig, HaToolsConfig


def _write(path, text):
    path.write_text(textwrap.dedent(text), encoding="utf-8")
    return path


def test_load_database_block_and_ignores_extras(tmp_path, monkeypatch):
    cfg_path = _write(
        tmp_path / "c.yaml",
        """
        database:
          url: mysql://u:p@h:3306/ha
          timeout: 5
        home_assistant:
          url: http://x
          access_token: secret
        ha_config_path: /config
        output_format: markdown
        """,
    )
    monkeypatch.setattr("ha_tools.config._custom_config_path", cfg_path)

    cfg = HaToolsConfig.load()
    assert cfg.database.url == "mysql://u:p@h:3306/ha"
    assert cfg.database.timeout == 5


def test_save_roundtrip(tmp_path, monkeypatch):
    cfg_path = tmp_path / "c.yaml"
    monkeypatch.setattr("ha_tools.config._custom_config_path", cfg_path)

    HaToolsConfig(database=DatabaseConfig(url="mysql://u:p@h:3306/ha")).save()
    cfg = HaToolsConfig.load()
    assert cfg.database.url == "mysql://u:p@h:3306/ha"


def test_invalid_database_url_rejected():
    with pytest.raises(ValidationError):
        DatabaseConfig(url="postgres://x")
