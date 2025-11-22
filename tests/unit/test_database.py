"""
Simplified database tests for ha-tools.

Tests only the core business logic, not external library mechanics.
"""

import pytest
from ha_tools.config import DatabaseConfig
from ha_tools.lib.database import DatabaseManager


class TestDatabaseManagerCore:
    """Test core database business logic only."""

    def test_detect_database_types(self):
        """Test database type detection from URLs."""
        config = DatabaseConfig(url="sqlite:///test.db")
        db = DatabaseManager(config)
        assert db._database_type == "sqlite"

        config = DatabaseConfig(url="mysql://user:pass@localhost:3306/db")
        db = DatabaseManager(config)
        assert db._database_type == "mysql"

        config = DatabaseConfig(url="postgresql://user:pass@localhost:5432/db")
        db = DatabaseManager(config)
        assert db._database_type == "postgresql"

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
        config = DatabaseConfig(url="mysql://user@host")  # Missing password and database
        db = DatabaseManager(config)

        with pytest.raises(ValueError, match="Invalid MySQL URL format"):
            db._parse_mysql_url()

    def test_parse_postgresql_url(self):
        """Test PostgreSQL URL parsing."""
        config = DatabaseConfig(url="postgresql://user:password@localhost:5432/database")
        db = DatabaseManager(config)

        parsed = db._parse_postgresql_url()
        assert parsed["user"] == "user"
        assert parsed["password"] == "password"
        assert parsed["host"] == "localhost"
        assert parsed["port"] == 5432
        assert parsed["database"] == "database"

    def test_parse_postgresql_url_invalid(self):
        """Test invalid PostgreSQL URL parsing."""
        config = DatabaseConfig(url="postgresql://user@host")  # Missing password and database
        db = DatabaseManager(config)

        with pytest.raises(ValueError, match="Invalid PostgreSQL URL format"):
            db._parse_postgresql_url()

    def test_custom_config_values(self):
        """Test custom database configuration values."""
        config = DatabaseConfig(
            url="sqlite:///test.db",
            pool_size=20,
            timeout=60,
            max_overflow=40
        )
        db = DatabaseManager(config)

        assert db.config.pool_size == 20
        assert db.config.timeout == 60
        assert db.config.max_overflow == 40

    def test_database_url_formats(self):
        """Test various database URL formats are detected correctly."""
        test_cases = [
            ("sqlite:///test.db", "sqlite"),
            ("sqlite:///path/to/test.db", "sqlite"),
            ("mysql://user:pass@host:3306/db", "mysql"),
            ("postgresql://user:pass@host:5432/db", "postgresql"),
        ]

        for url, expected_type in test_cases:
            config = DatabaseConfig(url=url)
            db = DatabaseManager(config)
            assert db._database_type == expected_type