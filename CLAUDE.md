# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

This is the `ha-tools` Python CLI - a lightweight, high-performance tool designed specifically for AI agents working with Home Assistant configurations. The project uses a hybrid REST API + direct database access approach to replace heavy MCP implementations with fast, targeted operations.

## Core Architecture

**3-Command Design**:

- `ha-tools validate [--syntax-only]` - Configuration validation
- `ha-tools entities [--search <pattern>] [--include <type>] [--history <timeframe>] [--verbose]` - Entity discovery and analysis
- `ha-tools errors [--current] [--log <timeframe>] [--entity <pattern>]` - Runtime error diagnostics

**Performance Strategy**:

- Database access: 10-15x faster for history queries
- Filesystem access: Package organization and YAML parsing
- REST API fallback: Real-time state and validation

## Development Commands

```bash
# Setup with uv (modern Python package management)
uv run ha-tools setup

# Run validation
uv run ha-tools validate --syntax-only  # Quick syntax check
uv run ha-tools validate               # Full validation (2-3 min)

# Entity discovery examples (supports * wildcard and | for OR)
uv run ha-tools entities                                       # Overview
uv run ha-tools entities --search "temp"                       # Substring match
uv run ha-tools entities --search "temp|humidity"              # Multiple patterns (OR)
uv run ha-tools entities --search "script.*saugen"             # Wildcard (* = any chars)
uv run ha-tools entities --search "sensor.temp*|*humidity"     # Wildcards + OR combined
uv run ha-tools entities --include history --history 7d        # With historical data
uv run ha-tools entities --include state --search "sensor"     # Full state details
uv run ha-tools entities --verbose                             # Show timing and debug info

# Timeframe formats: Nh (hours), Nd (days), Nm (minutes), Nw (weeks)
uv run ha-tools entities --history 30m                         # Last 30 minutes
uv run ha-tools entities --history 2w                          # Last 2 weeks

# History analysis examples
uv run ha-tools history sensor.temperature                     # Last 24h in markdown
uv run ha-tools history sensor.temperature --timeframe 7d      # Last 7 days
uv run ha-tools history sensor.temperature --stats             # With min/max/avg
uv run ha-tools history switch.light --stats                   # State change counts
uv run ha-tools history sensor.temperature --format json       # JSON output
uv run ha-tools history sensor.temperature --format csv -l -1  # Full CSV export

# Error diagnostics
uv run ha-tools errors --current                              # Current runtime errors
uv run ha-tools errors --log 24h --entity "heizung"           # Entity-specific errors (substring match)
```

## Implementation Structure

```
ha_tools/
├── pyproject.toml      # Modern Python project configuration
├── cli.py              # Main entry point and argument parsing
├── commands/
│   ├── __init__.py
│   ├── validate.py     # Configuration validation logic
│   ├── entities.py     # Entity discovery and analysis
│   └── errors.py       # Error diagnostics
├── lib/
│   ├── __init__.py
│   ├── database.py     # Async database connection and queries
│   ├── registry.py     # Entity/area registry loading
│   ├── rest_api.py     # Async Home Assistant REST API client
│   └── output.py       # Markdown formatting utilities
└── config.py           # Configuration management with pydantic
```

### Tech Stack

- **uv**: Modern Python package management and execution
- **pyproject.toml**: Standard Python project configuration
- **asyncio**: Async database and API operations for performance
- **pydantic**: Type-safe configuration management
- **rich**: Terminal formatting and progress indicators
- **typer**: Modern CLI framework with automatic help generation

## Key Patterns

### Data Source Hierarchy

1. **Database** (Primary): History, statistics, bulk operations
2. **Filesystem** (Secondary): YAML parsing, package analysis
3. **REST API** (Fallback): Real-time state, validation

### Configuration Management

- Location: `~/.ha-tools-config.yaml`
- Database: Read-only access to MariaDB (SQLite/PostgreSQL support planned, see GitHub issues)
- Home Assistant: URL + long-lived access token
- Modern async/await patterns for database and API operations
- Type hints throughout the codebase

### Output Format

All commands output structured markdown optimized for AI consumption:

- Progressive disclosure (summary → detailed views)
- Tables for entity listings
- Code blocks for errors and configuration
- Performance metrics and troubleshooting guidance

### Registry Loading Patterns

Use the established patterns from `ENTITY_EXPLORER_KNOWLEDGE_EXTRACTION.md`:

- Entity registry: `.storage/core.entity_registry`
- Area registry: `.storage/core.area_registry`
- Graceful error handling with fallbacks

## AI Agent Workflow Integration

### Configuration Changes

```bash
# 1. Quick syntax check
uv run ha-tools validate --syntax-only

# 2. Check affected entities (substring matching)
uv run ha-tools entities --search "modified_area" --include state

# 3. Full validation
uv run ha-tools validate

# 4. Check for runtime issues
uv run ha-tools errors --current
```

### Debugging Existing Issues

```bash
# Analyze entity behavior (use --verbose for timing details)
uv run ha-tools entities --search "heizung" --include history --history 24h --verbose

# Correlate with errors
uv run ha-tools errors --log 24h --entity "heizung"

# Check automation dependencies
uv run ha-tools entities --include relations --search "automation.heating"
```

## Error Handling

- Exit codes: 0 (success), 1 (general), 2 (validation), 3 (connection), 4 (database)
- Graceful degradation: Database unavailable → REST API fallback
- User-friendly error messages with troubleshooting steps

## Extension Points

The modular architecture supports future extensions:

- Package operations: `ha-tools packages list|analyze`
- Template validation: `ha-tools template validate <file>`
- Advanced analytics: `ha-tools stats entity <id>`
