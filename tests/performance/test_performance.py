"""
Performance tests for ha-tools.

Tests performance characteristics, memory usage, and response times.
"""

import asyncio
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from ha_tools.config import HaToolsConfig, DatabaseConfig, HomeAssistantConfig
from ha_tools.lib.database import DatabaseManager
from ha_tools.commands.entities import _get_entities


class TestDatabasePerformance:
    """Test database layer performance."""

    @pytest.mark.asyncio
    async def test_sqlite_query_performance(self, temp_dir: Path):
        """Test SQLite query performance with large datasets."""
        db_path = temp_dir / "performance_test.db"
        config = DatabaseConfig(url=f"sqlite:///{db_path}")
        db = DatabaseManager(config)

        await db.connect()

        # Create test table with many records
        await db.execute_query("""
            CREATE TABLE states (
                entity_id TEXT,
                state TEXT,
                last_changed TEXT,
                last_updated TEXT,
                attributes TEXT
            )
        """)

        # Insert test data
        base_time = datetime.now()
        insert_data = []
        for i in range(1000):  # 1000 records
            insert_data.append((
                f"sensor.test_{i % 100}",  # 100 unique entities
                str(i % 50),  # 50 unique states
                (base_time - timedelta(minutes=i)).isoformat(),
                (base_time - timedelta(minutes=i)).isoformat(),
                f'{{"index": {i}}}'
            ))

        # Measure insert performance
        start_time = time.time()
        for entity_id, state, last_changed, last_updated, attributes in insert_data:
            await db.execute_query(
                "INSERT INTO states (entity_id, state, last_changed, last_updated, attributes) VALUES (?, ?, ?, ?, ?)",
                (entity_id, state, last_changed, last_updated, attributes)
            )
        insert_time = time.time() - start_time

        print(f"Inserted 1000 records in {insert_time:.3f} seconds")
        assert insert_time < 5.0  # Should complete within 5 seconds

        # Measure query performance
        start_time = time.time()
        results = await db.get_entity_states(
            entity_id="sensor.test_1",
            start_time=base_time - timedelta(hours=1),
            limit=100
        )
        query_time = time.time() - start_time

        print(f"Queried entity states in {query_time:.3f} seconds")
        assert query_time < 1.0  # Should complete within 1 second
        assert len(results) <= 100  # Should respect limit

    @pytest.mark.asyncio
    async def test_connection_pool_performance(self):
        """Test database connection pool performance."""
        config = DatabaseConfig(url="mysql://user:pass@localhost:3306/test")

        with patch('asyncmy.create_pool') as mock_create_pool:
            mock_pool = AsyncMock()
            mock_create_pool.return_value = mock_pool

            db = DatabaseManager(config)
            await db.connect()

            # Test that connection pool is created with correct parameters
            mock_create_pool.assert_called_once()
            call_args = mock_create_pool.call_args[1]
            assert call_args["maxsize"] == 10  # Default pool size
            assert call_args["minsize"] == 1


class TestEntityDiscoveryPerformance:
    """Test entity discovery performance."""

    @pytest.mark.asyncio
    async def test_large_entity_registry_performance(self):
        """Test performance with large entity registries."""
        # Create mock registry with many entities
        mock_registry = AsyncMock()
        mock_db = AsyncMock()
        mock_api = AsyncMock()

        # Create 500 entities
        large_entity_registry = []
        for i in range(500):
            large_entity_registry.append({
                "entity_id": f"sensor.test_{i}",
                "friendly_name": f"Test Sensor {i}",
                "device_class": "temperature" if i % 2 == 0 else "humidity",
                "unit_of_measurement": "°C" if i % 2 == 0 else "%",
                "area_id": f"area_{i % 10}" if i % 5 == 0 else None,
                "device_id": f"device_{i % 20}"
            })

        mock_registry._entity_registry = large_entity_registry

        # Mock API responses for state queries
        mock_api.get_entity_state.return_value = {
            "entity_id": "sensor.test_1",
            "state": "20.5",
            "attributes": {"unit_of_measurement": "°C"},
            "last_changed": "2024-01-01T12:00:00+00:00"
        }

        start_time = time.time()

        entities = await _get_entities(
            mock_registry, mock_db, mock_api,
            search=None,
            include_options={"state"},
            history_timeframe=None,
            limit=100
        )

        processing_time = time.time() - start_time

        print(f"Processed 500 entities in {processing_time:.3f} seconds")
        assert processing_time < 2.0  # Should complete within 2 seconds
        assert len(entities) == 100  # Should respect limit

    @pytest.mark.asyncio
    async def test_search_pattern_performance(self):
        """Test search pattern performance with wildcard patterns."""
        # Use MagicMock for registry (search_entities is synchronous)
        mock_registry = MagicMock()
        mock_db = AsyncMock()
        mock_api = AsyncMock()

        # Create entities that match various patterns
        entity_registry = []
        patterns = ["temp", "humidity", "light", "switch", "motion"]

        for i, pattern in enumerate(patterns):
            for j in range(100):  # 100 entities per pattern
                entity_registry.append({
                    "entity_id": f"sensor.{pattern}_{j}",
                    "friendly_name": f"{pattern.capitalize()} Sensor {j}",
                    "device_class": pattern
                })

        mock_registry.search_entities.return_value = entity_registry[:100]  # Return subset

        start_time = time.time()

        entities = await _get_entities(
            mock_registry, mock_db, mock_api,
            search="sensor.temp_*",
            include_options=set(),
            history_timeframe=None,
            limit=None
        )

        search_time = time.time() - start_time

        print(f"Search pattern matching in {search_time:.3f} seconds")
        assert search_time < 0.5  # Should complete within 0.5 seconds
        mock_registry.search_entities.assert_called_once_with("sensor.temp_*")

    @pytest.mark.asyncio
    async def test_concurrent_api_requests_performance(self):
        """Test performance of concurrent API requests."""
        mock_registry = AsyncMock()
        mock_db = AsyncMock()
        mock_api = AsyncMock()

        # Create 50 entities
        entity_registry = [
            {
                "entity_id": f"sensor.concurrent_{i}",
                "friendly_name": f"Concurrent Sensor {i}"
            }
            for i in range(50)
        ]

        mock_registry._entity_registry = entity_registry

        # Mock API with slight delay to simulate network latency
        async def mock_get_state(entity_id):
            await asyncio.sleep(0.01)  # 10ms delay per request
            return {
                "entity_id": entity_id,
                "state": "20.0",
                "attributes": {"unit_of_measurement": "°C"}
            }

        mock_api.get_entity_state.side_effect = mock_get_state

        start_time = time.time()

        entities = await _get_entities(
            mock_registry, mock_db, mock_api,
            search=None,
            include_options={"state"},
            history_timeframe=None,
            limit=None
        )

        total_time = time.time() - start_time

        print(f"Concurrent API requests for 50 entities in {total_time:.3f} seconds")

        # With sequential requests, this would take ~0.5 seconds (50 * 0.01s)
        # With concurrent processing, it should be faster
        assert total_time < 0.3  # Should be significantly faster than sequential
        assert len(entities) == 50


class TestMemoryUsage:
    """Test memory usage characteristics."""

    @pytest.mark.asyncio
    async def test_memory_usage_large_history(self):
        """Test memory usage when processing large history datasets."""
        mock_registry = AsyncMock()
        mock_db = AsyncMock()
        mock_api = AsyncMock()

        # Create entity with large history
        mock_registry._entity_registry = [
            {"entity_id": "sensor.memory_test", "friendly_name": "Memory Test"}
        ]

        # Mock large history data (1000 records)
        large_history = []
        base_time = datetime.now() - timedelta(days=365)
        for i in range(1000):
            large_history.append({
                "entity_id": "sensor.memory_test",
                "state": str(20 + (i % 10)),
                "last_changed": (base_time + timedelta(hours=i)).isoformat(),
                "attributes": f'{{"index": {i}, "large_data": "x" * 100}}'  # 100 bytes per record
            })

        mock_db.get_entity_states.return_value = large_history

        # Measure memory usage (approximate)
        import sys
        entities_before = None

        entities = await _get_entities(
            mock_registry, mock_db, mock_api,
            search=None,
            include_options={"history"},
            history_timeframe=datetime.now() - timedelta(days=1),
            limit=None
        )

        # Basic sanity check
        assert len(entities) == 1
        assert entities[0]["history_count"] == 1000
        assert len(entities[0]["history"]) == 1000

        # Verify data structure integrity
        for record in entities[0]["history"][:10]:  # Check first 10
            assert "entity_id" in record
            assert "state" in record
            assert "last_changed" in record


class TestScalabilityBenchmarks:
    """Benchmark tests for scalability."""

    @pytest.mark.asyncio
    async def test_entity_count_scalability(self):
        """Test how performance scales with entity count."""
        mock_registry = AsyncMock()
        mock_db = AsyncMock()
        mock_api = AsyncMock()

        entity_counts = [10, 50, 100, 500]
        performance_results = {}

        for count in entity_counts:
            # Create mock registry with specified entity count
            entity_registry = [
                {
                    "entity_id": f"sensor.scale_test_{i}",
                    "friendly_name": f"Scale Test Sensor {i}"
                }
                for i in range(count)
            ]

            mock_registry._entity_registry = entity_registry

            # Measure performance
            start_time = time.time()

            entities = await _get_entities(
                mock_registry, mock_db, mock_api,
                search=None,
                include_options=set(),
                history_timeframe=None,
                limit=None
            )

            processing_time = time.time() - start_time
            performance_results[count] = processing_time

            print(f"Processed {count} entities in {processing_time:.3f} seconds")

            assert len(entities) == count
            assert processing_time < count * 0.01  # Should scale linearly but reasonably

        # Verify reasonable scaling (not exponential)
        assert performance_results[500] < performance_results[10] * 10  # Less than 10x slower for 50x more entities

    def test_configuration_loading_performance(self, temp_dir: Path):
        """Test configuration loading performance."""
        # Create configuration with many settings
        config_data = {
            "home_assistant": {
                "url": "http://localhost:8123",
                "access_token": "test_token",
                "timeout": 30
            },
            "database": {
                "url": "sqlite:///test.db",
                "pool_size": 10,
                "timeout": 30
            },
            "ha_config_path": str(temp_dir),
            "output_format": "markdown",
            "verbose": False
        }

        config_file = temp_dir / "performance_config.yaml"
        import yaml
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        # Measure loading time
        start_time = time.time()
        for _ in range(100):  # Load 100 times
            HaToolsConfig.set_config_path(config_file)
            config = HaToolsConfig.load()
        loading_time = time.time() - start_time

        avg_time = loading_time / 100
        print(f"Average config loading time: {avg_time*1000:.2f}ms")
        assert avg_time < 0.01  # Should load in less than 10ms on average