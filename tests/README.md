# Testing for ha-tools

This project uses modern Python testing with `uv` and `pytest`.

## Quick Start

```bash
# Install dependencies
uv sync

# Run all tests
uv run pytest tests/ -v

# Run specific test suites
uv run pytest tests/unit/ -v          # Unit tests only
uv run pytest tests/integration/ -v   # Integration tests only
uv run pytest tests/performance/ -v   # Performance tests only
uv run pytest tests/unit/ tests/integration/ -v -m "not slow"  # Skip slow tests

# Run tests with coverage
uv run pytest tests/ --cov=ha_tools --cov-report=term-missing --cov-report=html
```

## Test Structure

```
tests/
├── conftest.py              # Shared test fixtures and configuration
├── unit/                    # Unit tests for individual components
│   ├── test_config.py       # Configuration management tests
│   ├── test_database.py     # Database layer tests
│   ├── test_rest_api.py     # Home Assistant API client tests
│   ├── test_validate_command.py
│   ├── test_entities_command.py
│   └── test_errors_command.py
├── integration/             # End-to-end integration tests
│   └── test_cli_integration.py
├── performance/             # Performance and scalability tests
│   └── test_performance.py
└── fixtures/                # Test data and sample files
```

## Running Tests with uvx

For one-off execution without installing dependencies:

```bash
# Run the tool directly
uvx --from . ha-tools --help

# Test connection
uvx --from . ha-tools test-connection

# Run validation
uvx --from . ha-tools validate --syntax-only

# Discover entities
uvx --from . ha-tools entities --search "sensor.*"

# Check for errors
uvx --from . ha-tools errors --current
```

## Test Categories

### Unit Tests (`tests/unit/`)
- Test individual functions and classes in isolation
- Use mocks to avoid external dependencies
- Fast execution, suitable for TDD
- Coverage of core logic, edge cases, and error conditions

### Integration Tests (`tests/integration/`)
- Test component interactions and workflows
- End-to-end command execution
- Realistic usage scenarios
- Configuration loading and CLI integration

### Performance Tests (`tests/performance/`)
- Benchmark query performance
- Test scalability with large datasets
- Memory usage verification
- Concurrent operation testing

## Mocking Strategy

The tests use comprehensive mocking to avoid external dependencies:

- **Home Assistant API**: Mocked `aiohttp` responses
- **Database**: Mocked async connections and query results
- **File System**: Temporary files and directories for config files
- **Registry Data**: Sample entity/area/device registries

## Test Fixtures

Key fixtures in `conftest.py`:

- `temp_dir`: Temporary directory for test files
- `sample_ha_config`: Sample Home Assistant configuration
- `sample_config_file`: Sample ha-tools configuration
- `test_config`: Loaded configuration instance
- `mock_home_assistant_api`: Mocked API client with sample responses
- `mock_database_manager`: Mocked database manager
- `mock_registry_manager`: Mocked entity/area/device registry

## Coverage

Current test coverage:

- **Configuration Management**: ✅ Complete
- **Database Layer**: ✅ Complete (SQLite, MySQL, PostgreSQL)
- **REST API Client**: ✅ Complete
- **CLI Commands**: ✅ Complete (validate, entities, errors)
- **Integration**: ✅ End-to-end workflows
- **Performance**: ✅ Scalability benchmarks

## Development Workflow

```bash
# Set up development environment
uv sync

# During development - quick tests
uv run pytest tests/unit/ tests/integration/ -v -m "not slow"

# Before committing - run full suite with coverage
uv run pytest tests/ --cov=ha_tools --cov-report=term-missing

# Check code quality
uv run ruff check ha_tools/ tests/
uv run ruff format ha_tools/ tests/
uv run mypy ha_tools/
```

## CI/CD Integration

```bash
# In CI/CD pipelines
uv sync --frozen
uv run pytest tests/ --cov=ha_tools --cov-report=term-missing
uv run ruff check ha_tools/ tests/
uv run mypy ha_tools/
```

## Adding Tests

1. **Unit Tests**: Add to `tests/unit/test_<module>.py`
2. **Integration Tests**: Add to `tests/integration/`
3. **Fixtures**: Add common test data to `conftest.py`
4. **Performance**: Add benchmarks to `tests/performance/`

Use `pytest.mark.asyncio` for async tests and `pytest.mark.slow` for performance tests.
