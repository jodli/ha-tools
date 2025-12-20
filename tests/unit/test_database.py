"""
Simplified database tests for ha-tools.

Tests only the core business logic, not external library mechanics.
"""

import pytest

from ha_tools.config import DatabaseConfig
from ha_tools.lib.database import DatabaseManager


class TestDatabaseManagerCore:
    """Test core database business logic only."""

    def test_detect_mysql_database_type(self):
        """Test MySQL database type detection from URL."""
        config = DatabaseConfig(url="mysql://user:pass@localhost:3306/db")
        db = DatabaseManager(config)
        assert db._database_type == "mysql"

    def test_sqlite_raises_not_implemented(self):
        """Test that SQLite URLs raise ValueError (not yet implemented)."""
        config = DatabaseConfig(url="sqlite:///test.db")
        with pytest.raises(ValueError, match="SQLite support not yet implemented"):
            DatabaseManager(config)

    def test_postgresql_raises_not_implemented(self):
        """Test that PostgreSQL URLs raise ValueError (not yet implemented)."""
        config = DatabaseConfig(url="postgresql://user:pass@localhost:5432/db")
        with pytest.raises(ValueError, match="PostgreSQL support not yet implemented"):
            DatabaseManager(config)

    def test_invalid_database_url(self):
        """Test that invalid database URLs are rejected."""
        with pytest.raises(ValueError, match="Database URL must start with"):
            DatabaseConfig(url="invalid://test")

    def test_parse_mysql_url(self):
        """Test MySQL URL parsing."""
        config = DatabaseConfig(url="mysql://user:password@localhost:3306/database")
        db = DatabaseManager(config)

        parsed = db._parse_mysql_url()
        assert parsed["user"] == "user"
        assert parsed["password"] == "password"
        assert parsed["host"] == "localhost"
        assert parsed["port"] == 3306
        assert parsed["database"] == "database"

    def test_parse_mysql_url_invalid(self):
        """Test invalid MySQL URL parsing."""
        config = DatabaseConfig(
            url="mysql://user@host"
        )  # Missing password and database
        db = DatabaseManager(config)

        with pytest.raises(ValueError, match="Invalid MySQL URL format"):
            db._parse_mysql_url()

    def test_custom_config_values(self):
        """Test custom database configuration values."""
        config = DatabaseConfig(
            url="mysql://user:pass@localhost:3306/db",
            pool_size=20,
            timeout=60,
            max_overflow=40,
        )
        db = DatabaseManager(config)

        assert db.config.pool_size == 20
        assert db.config.timeout == 60
        assert db.config.max_overflow == 40
