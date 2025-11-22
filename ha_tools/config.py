"""
Configuration management for ha-tools.

Uses Pydantic for type-safe configuration management with environment variable support.
"""

import os
from pathlib import Path
from typing import Any, Dict, Optional, Union

from pydantic import BaseModel, Field, validator
from pydantic_settings import BaseSettings


class DatabaseConfig(BaseModel):
    """Database connection configuration."""

    url: str = Field(
        ...,
        description="Database URL (e.g., mysql://user:pass@host/db, postgresql://..., sqlite:///path)"
    )
    pool_size: int = Field(default=10, description="Connection pool size")
    max_overflow: int = Field(default=20, description="Maximum connection overflow")
    timeout: int = Field(default=30, description="Connection timeout in seconds")

    @validator("url")
    def validate_database_url(cls, v: str) -> str:
        """Validate database URL format."""
        if not v:
            raise ValueError("Database URL is required")

        # Basic URL format validation
        if not any(prefix in v for prefix in ["mysql://", "postgresql://", "sqlite:///"]):
            raise ValueError(
                "Database URL must start with mysql://, postgresql://, or sqlite:///"
            )
        return v


class HomeAssistantConfig(BaseModel):
    """Home Assistant REST API configuration."""

    url: str = Field(
        ...,
        description="Home Assistant URL (e.g., http://localhost:8123)"
    )
    access_token: str = Field(
        ...,
        description="Long-lived access token"
    )
    timeout: int = Field(default=30, description="API request timeout in seconds")

    @validator("url")
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

    home_assistant: HomeAssistantConfig = Field(..., description="Home Assistant configuration")
    database: DatabaseConfig = Field(..., description="Database configuration")
    ha_config_path: str = Field(
        default="/config",
        description="Path to Home Assistant configuration directory"
    )
    output_format: str = Field(
        default="markdown",
        description="Output format (markdown, json, table)"
    )
    verbose: bool = Field(default=False, description="Enable verbose logging")

    # Custom settings path
    _config_path: Optional[Path] = None

    class Config:
        env_prefix = "HA_TOOLS_"
        env_file = ".env"
        env_nested_delimiter = "__"

    @classmethod
    def set_config_path(cls, path: Union[str, Path]) -> None:
        """Set custom configuration file path."""
        cls._config_path = Path(path)

    @classmethod
    def get_config_path(cls) -> Path:
        """Get the configuration file path."""
        if cls._config_path:
            return cls._config_path

        # Default to ~/.ha-tools-config.yaml
        return Path.home() / ".ha-tools-config.yaml"

    @classmethod
    def load(cls) -> "HaToolsConfig":
        """Load configuration from file and environment variables."""
        config_path = cls.get_config_path()

        if config_path.exists():
            try:
                import yaml
                with open(config_path, "r", encoding="utf-8") as f:
                    config_data = yaml.safe_load(f) or {}
                return cls(**config_data)
            except Exception as e:
                raise ValueError(f"Failed to load config from {config_path}: {e}")
        else:
            # Try to load from environment variables only
            try:
                return cls()
            except Exception as e:
                raise ValueError(
                    f"No configuration file found at {config_path} and "
                    f"environment variables incomplete: {e}"
                )

    def save(self, path: Optional[Union[str, Path]] = None) -> None:
        """Save configuration to file."""
        import yaml

        save_path = Path(path) if path else self.get_config_path()

        # Create parent directory if needed
        save_path.parent.mkdir(parents=True, exist_ok=True)

        # Convert to dict, excluding private attributes
        config_dict = self.dict(exclude_none=True)

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

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary for API usage."""
        return self.dict()


# Version information
__version__ = "0.1.0"