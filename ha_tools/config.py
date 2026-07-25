"""Database connection configuration for ha-tools.

Read from ``~/.ha-tools-config.yaml`` (or ``HA_TOOLS_*`` env vars). Only the
``database`` block is used — the library talks to the recorder DB directly and
does not need a Home Assistant REST token.

Example::

    database:
      url: mysql://user:pass@host:3306/homeassistant
      timeout: 30
"""

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_custom_config_path: Path | None = None


class DatabaseConfig(BaseModel):
    """MariaDB/MySQL connection configuration."""

    url: str = Field(..., description="mysql://user:pass@host:port/database")
    timeout: int = Field(default=30, description="Connection timeout in seconds")

    @field_validator("url")
    @classmethod
    def _validate_url(cls, v: str) -> str:
        if not v.startswith("mysql://"):
            raise ValueError("Database URL must start with mysql://")
        return v


class HaToolsConfig(BaseSettings):
    """Main configuration. Only ``database`` is required."""

    database: DatabaseConfig

    model_config = SettingsConfigDict(
        env_prefix="HA_TOOLS_",
        env_file=".env",
        env_nested_delimiter="__",
        extra="ignore",
    )

    @classmethod
    def set_config_path(cls, path: str | Path) -> None:
        """Override the config file location (used by tests)."""
        global _custom_config_path
        _custom_config_path = Path(path)

    @classmethod
    def get_config_path(cls) -> Path:
        if _custom_config_path is not None:
            return _custom_config_path
        return Path.home() / ".ha-tools-config.yaml"

    @classmethod
    def load(cls) -> "HaToolsConfig":
        """Load config from YAML file, falling back to environment variables."""
        path = cls.get_config_path()
        if path.exists():
            import yaml

            with open(path, encoding="utf-8") as f:
                data: dict[str, Any] = yaml.safe_load(f) or {}
            return cls(**data)
        # env-only (pydantic-settings populates from HA_TOOLS_* / .env)
        return cls()  # type: ignore[call-arg]

    def save(self, path: str | Path | None = None) -> None:
        """Persist config to YAML."""
        import yaml

        target = Path(path) if path else self.get_config_path()
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            yaml.safe_dump(
                self.model_dump(), f, default_flow_style=False, sort_keys=False
            )
