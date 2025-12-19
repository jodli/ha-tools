"""
Database connection layer for Home Assistant data.

Provides async database access for MariaDB/MySQL.
Optimized for fast history queries with connection pooling.

Note: SQLite and PostgreSQL support removed - contributions welcome!
See GitHub issues for implementation details.
"""

from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

from ..config import DatabaseConfig


class DatabaseManager:
    """Async database manager for Home Assistant data (MariaDB only)."""

    def __init__(self, config: DatabaseConfig):
        self.config = config
        self._connection_pool: Any = None
        self._database_type = self._detect_database_type(config.url)
        self._connection_error: Exception | None = None

    def _detect_database_type(self, url: str) -> str:
        """Detect database type from URL."""
        if url.startswith("mysql://"):
            return "mysql"
        elif url.startswith("sqlite://"):
            raise ValueError(
                "SQLite support not yet implemented. "
                "See https://github.com/jodli/ha-tools/issues for details."
            )
        elif url.startswith("postgresql://"):
            raise ValueError(
                "PostgreSQL support not yet implemented. "
                "See https://github.com/jodli/ha-tools/issues for details."
            )
        else:
            raise ValueError(f"Unsupported database type: {url}")

    async def connect(self) -> None:
        """Establish database connection pool."""
        try:
            if self._database_type == "mysql":
                await self._connect_mysql()
        except Exception as e:
            # Store the connection error for later handling
            self._connection_error = e
            # Don't raise the exception - allow graceful fallback
            pass

    async def _connect_mysql(self) -> None:
        """Connect to MySQL/MariaDB database."""
        import asyncmy

        # Parse connection URL
        url_parts = self._parse_mysql_url()

        # Create connection pool
        self._connection_pool = await asyncmy.create_pool(
            host=url_parts["host"],
            port=url_parts["port"],
            user=url_parts["user"],
            password=url_parts["password"],
            database=url_parts["database"],
            minsize=1,
            maxsize=self.config.pool_size,
            connect_timeout=self.config.timeout,
        )

    def _parse_mysql_url(self) -> dict[str, str | int]:
        """Parse MySQL connection URL."""
        # Format: mysql://user:pass@host:port/database
        import re

        pattern = r"mysql://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)"
        match = re.match(pattern, self.config.url)
        if not match:
            raise ValueError(f"Invalid MySQL URL format: {self.config.url}")

        return {
            "user": match.group(1),
            "password": match.group(2),
            "host": match.group(3),
            "port": int(match.group(4)),
            "database": match.group(5),
        }

    @asynccontextmanager
    async def get_connection(self) -> Any:
        """Get a database connection from the pool."""
        if self._database_type == "mysql":
            async with self._connection_pool.acquire() as conn:
                yield conn
        else:
            yield None

    def is_connected(self) -> bool:
        """Check if database connection is available."""
        return self._connection_pool is not None and self._connection_error is None

    def get_connection_error(self) -> Exception | None:
        """Get the connection error if any."""
        return self._connection_error

    async def test_connection(self) -> None:
        """Test database connectivity."""
        if not self.is_connected():
            raise self._connection_error or Exception("Database not connected")

        async with self.get_connection() as conn:
            if self._database_type == "mysql":
                await conn.ping()

    async def execute_query(
        self, query: str, params: tuple[Any, ...] | None = None
    ) -> list[dict[str, Any]]:
        """Execute a query and return results as list of dictionaries."""
        if not self.is_connected():
            # Return empty result when database is not available
            return []

        async with self.get_connection() as conn:
            if self._database_type == "mysql":
                async with conn.cursor() as cursor:
                    await cursor.execute(query, params)
                    columns = [desc[0] for desc in cursor.description]
                    rows = await cursor.fetchall()
                    return [dict(zip(columns, row, strict=False)) for row in rows]
        return []

    async def get_entity_states(
        self,
        entity_id: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int | None = None,
        include_stats: bool = False,
    ) -> list[dict[str, Any]] | tuple[list[dict[str, Any]], dict[str, Any]]:
        """
        Get entity state history from database.

        This is the core method for fast history queries, achieving 10-15x
        performance improvement over REST API.

        If include_stats=True, returns (results, stats_dict) where stats_dict contains:
        - total_records: Total state records for this entity (unfiltered)
        - query_time_ms: Time taken for the query
        """
        if not self.is_connected():
            # Return empty result when database is not available
            if include_stats:
                return [], {"total_records": 0, "query_time_ms": 0}
            return []

        if self._database_type == "mysql":
            return await self._get_entity_states_mysql(
                entity_id, start_time, end_time, limit, include_stats
            )

        # Default case for unsupported database types
        if include_stats:
            return [], {"total_records": 0, "query_time_ms": 0}
        return []

    async def _get_entity_states_mysql(
        self,
        entity_id: str | None,
        start_time: datetime | None,
        end_time: datetime | None,
        limit: int | None,
        include_stats: bool = False,
    ) -> list[dict[str, Any]] | tuple[list[dict[str, Any]], dict[str, Any]]:
        """Get entity states from MySQL database (modern schema with states_meta)."""
        import time as time_module

        start_query_time = time_module.time()

        # When include_stats=True, add:
        # - COUNT(*) OVER() for filtered count (records matching time filter, before LIMIT)
        # - Subquery for total records (all records for this entity, explains slow queries)
        if include_stats and entity_id and "*" not in entity_id:
            count_select = """, COUNT(*) OVER() as _filtered_count,
                (SELECT COUNT(*) FROM states s2
                 INNER JOIN states_meta sm2 ON s2.metadata_id = sm2.metadata_id
                 WHERE sm2.entity_id = sm.entity_id) as _total_records"""
        else:
            count_select = ""

        query = f"""
        SELECT
            sm.entity_id,
            s.state,
            FROM_UNIXTIME(COALESCE(s.last_changed_ts, s.last_updated_ts)) as last_changed,
            FROM_UNIXTIME(s.last_updated_ts) as last_updated,
            sa.shared_attrs as attributes{count_select}
        FROM states s
        INNER JOIN states_meta sm ON s.metadata_id = sm.metadata_id
        LEFT JOIN state_attributes sa ON s.attributes_id = sa.attributes_id
        """
        conditions: list[str] = []
        params: list[str | float | int] = []

        if entity_id:
            if "*" in entity_id:
                entity_id = entity_id.replace("*", "%")
                conditions.append("sm.entity_id LIKE %s")
                params.append(entity_id)
            else:
                conditions.append("sm.entity_id = %s")
                params.append(entity_id)

        if start_time:
            # Use last_updated_ts directly - it's always set and allows index usage
            # (COALESCE prevents index usage, causing full table scans)
            conditions.append("s.last_updated_ts >= %s")
            params.append(start_time.timestamp())

        if end_time:
            conditions.append("s.last_updated_ts <= %s")
            params.append(end_time.timestamp())

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY s.last_updated_ts DESC"

        if limit:
            query += " LIMIT %s"
            params.append(limit)

        results = await self.execute_query(query, tuple(params))
        query_time_ms = (time_module.time() - start_query_time) * 1000

        if include_stats:
            stats = {
                "total_records": results[0].get("_total_records", 0) if results else 0,
                "filtered_count": results[0].get("_filtered_count", 0)
                if results
                else 0,
                "query_time_ms": query_time_ms,
            }
            # Remove stats fields from results
            for row in results:
                row.pop("_total_records", None)
                row.pop("_filtered_count", None)
            return results, stats

        return results

    async def get_entity_statistics(
        self,
        entity_id: str | None = None,
        statistic_type: str | None = None,
        period: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get long-term statistics data from database."""
        if not self.is_connected():
            # Return empty result when database is not available
            return []

        if self._database_type == "mysql":
            return await self._get_statistics_mysql(entity_id, statistic_type, period)
        return []

    async def _get_statistics_mysql(
        self, entity_id: str | None, statistic_type: str | None, period: str | None
    ) -> list[dict[str, Any]]:
        """Get statistics from MySQL database."""
        query = """
        SELECT s.statistic_id, s.metadata_id, s.start, s.mean, s.min, s.max,
               s.last_reset, s.state, s.sum, m.statistic_id, m.unit_of_measurement
        FROM statistics s
        JOIN statistics_meta m ON s.metadata_id = m.metadata_id
        """
        conditions = []
        params = []

        if entity_id:
            conditions.append("m.statistic_id LIKE %s")
            params.append(entity_id.replace("*", "%"))

        if statistic_type:
            conditions.append("m.statistic_id LIKE %s")
            params.append(f"%{statistic_type}%")

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY start DESC LIMIT 1000"

        return await self.execute_query(query, tuple(params))

    async def close(self) -> None:
        """Close database connections."""
        if self._connection_pool:
            close_method = getattr(self._connection_pool, "close", None)
            if close_method:
                try:
                    # Try async close first
                    await close_method()
                except TypeError:
                    # If close() is not async, call it directly
                    close_method()

    async def __aenter__(self) -> "DatabaseManager":
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        """Async context manager exit."""
        await self.close()
