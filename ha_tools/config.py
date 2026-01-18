"""
Configuration management for ha-tools.

Uses Pydantic for type-safe configuration management with environment variable support.
"""

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Module-level variable for custom config path
_custom_config_path: Path | None = None


class DatabaseConfig(BaseModel):
    """Database connection configuration."""

    url: str = Field(
        ...,
        description="Database URL (e.g., mysql://user:pass@host/db, postgresql://..., sqlite:///path)",
    )
    pool_size: int = Field(default=10, description="Connection pool size")
    max_overflow: int = Field(default=20, description="Maximum connection overflow")
    timeout: int = Field(default=30, description="Connection timeout in seconds")

    @field_validator("url")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        """Validate database URL format."""
        if not v:
            raise ValueError("Database URL is required")

        # Basic URL format validation
        if not any(
            prefix in v for prefix in ["mysql://", "postgresql://", "sqlite:///"]
        ):
            raise ValueError(
                "Database URL must start with mysql://, postgresql://, or sqlite:///"
            )
        return v


class HomeAssistantConfig(BaseModel):
    """Home Assistant REST API configuration."""

    url: str = Field(
        ..., description="Home Assistant URL (e.g., http://localhost:8123)"
    )
    access_token: str = Field(..., description="Long-lived access token")
    timeout: int = Field(default=30, description="API request timeout in seconds")

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Validate Home Assistant URL format."""
        if not v:
            raise ValueError("Home Assistant URL is required")

        # Normalize URL
        if not v.startswith(("http://", "https://")):
            v = f"http://{v}"

        # Remove trailing slash
        v = v.rstrip("/")

        return v


class HaToolsConfig(BaseSettings):
    """Main configuration for ha-tools."""

    home_assistant: HomeAssistantConfig = Field(
        ..., description="Home Assistant configuration"
    )
    database: DatabaseConfig = Field(..., description="Database configuration")
    ha_config_path: str = Field(
        default="/config", description="Path to Home Assistant configuration directory"
    )
    output_format: str = Field(
        default="markdown", description="Output format (markdown only, csv for history)"
    )
    verbose: bool = Field(default=False, description="Enable verbose logging")

    model_config = SettingsConfigDict(
        env_prefix="HA_TOOLS_", env_file=".env", env_nested_delimiter="__"
    )

    @classmethod
    def set_config_path(cls, path: str | Path) -> None:
        """Set custom configuration file path."""
        global _custom_config_path
        _custom_config_path = Path(path)

    @classmethod
    def get_config_path(cls) -> Path:
        """Get the configuration file path."""
        global _custom_config_path
        if _custom_config_path:
            return _custom_config_path

        # Default to ~/.ha-tools-config.yaml
        return Path.home() / ".ha-tools-config.yaml"

    @classmethod
    def load(cls) -> "HaToolsConfig":
        """Load configuration from file and environment variables."""
        config_path = cls.get_config_path()

        if config_path.exists():
            try:
                import yaml

                with open(config_path, encoding="utf-8") as f:
                    config_data = yaml.safe_load(f) or {}
                return cls(**config_data)
            except Exception as e:
                raise ValueError(
                    f"Failed to load config from {config_path}: {e}"
                ) from e
        else:
            # Try to load from environment variables only
            # pydantic-settings will populate required fields from env vars at runtime
            try:
                return cls()  # type: ignore[call-arg]
            except Exception as e:
                raise ValueError(
                    f"No configuration file found at {config_path} and "
                    f"environment variables incomplete: {e}"
                ) from e

    def save(self, path: str | Path | None = None) -> None:
        """Save configuration to file."""
        import yaml

        save_path = Path(path) if path else self.get_config_path()

        # Create parent directory if needed
        save_path.parent.mkdir(parents=True, exist_ok=True)

        # Convert to dict, excluding private attributes
        config_dict = self.model_dump(exclude_none=True)

        with open(save_path, "w", encoding="utf-8") as f:
            yaml.dump(config_dict, f, default_flow_style=False, indent=2)

    def validate_access(self) -> None:
        """Validate that we can access Home Assistant resources."""
        # Check Home Assistant config directory
        ha_path = Path(self.ha_config_path)
        if not ha_path.exists():
            raise ValueError(f"Home Assistant config directory not found: {ha_path}")

        # Check for essential files
        required_files = ["configuration.yaml"]
        for file_name in required_files:
            file_path = ha_path / file_name
            if not file_path.exists():
                raise ValueError(f"Required Home Assistant file not found: {file_path}")

    def to_dict(self) -> dict[str, Any]:
        """Convert configuration to dictionary for API usage."""
        return self.model_dump()


# Version information
__version__ = "0.1.0"
