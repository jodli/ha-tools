# ha-tools

High-performance CLI tool for AI agents working with Home Assistant configurations.

## Overview

`ha-tools` is a lightweight, fast CLI tool designed specifically for AI agents to work with Home Assistant configurations. It uses a hybrid approach combining REST API access with direct database queries for optimal performance.

## Features

- **3-Command Design**: Simple, focused interface
  - `ha-tools validate` - Configuration validation
  - `ha-tools entities` - Entity discovery and analysis
  - `ha-tools errors` - Runtime error diagnostics

- **Performance Optimized**:
  - 10-15x faster history queries via direct database access
  - 6x faster entity discovery than REST API alone
  - Structured markdown output optimized for AI consumption

- **Multi-Database Support**: MariaDB, PostgreSQL, SQLite
- **Async Architecture**: High-performance concurrent operations
- **Rich Terminal Output**: Beautiful, informative displays with progress indicators

## Quick Start

### Installation

```bash
# Using uv (recommended)
uv run ha-tools setup
```

### Setup

```bash
# Interactive setup wizard
uv run ha-tools setup

# Test connections
uv run ha-tools test-connection
```

### Usage

```bash
# Quick syntax validation
uv run ha-tools validate --syntax-only

# Full validation (2-3 minutes)
uv run ha-tools validate

# Entity discovery
uv run ha-tools entities

# Search entities with history (substring matching)
uv run ha-tools entities --search "temp" --include history --history 24h

# Error analysis
uv run ha-tools errors --current

# Historical error analysis with correlation
uv run ha-tools errors --log 24h --correlation

# Enable verbose output for debugging
uv run ha-tools entities --verbose
```

## Timeframe Formats

All timeframe options (`--history`, `--log`) support:
- `Nh` - hours (e.g., `24h`)
- `Nd` - days (e.g., `7d`)
- `Nm` - minutes (e.g., `30m`)
- `Nw` - weeks (e.g., `2w`)

## Architecture

### Hybrid Data Source Strategy

1. **Database (Primary)**: 10-15x faster for history queries and long-term statistics
2. **Filesystem (Secondary)**: YAML parsing, package organization, template dependencies
3. **REST API (Fallback)**: Real-time state, validation, and when database isn't available

### Command Structure

- **Validate**: Syntax checking + semantic validation via Home Assistant API
- **Entities**: Search (substring matching), filter, and analyze entities with optional historical data
- **Errors**: Multi-source error analysis with correlation to entity state changes

## Performance Targets

- Entity discovery: **6x faster** than REST API alone
- History queries: **10-15x faster** than REST API
- Full validation: **2-3 minutes** (acceptable for comprehensive checks)
- Long-term trends: **Exclusive capability** via database statistics (>365 days)

## Configuration

Configuration is stored in `~/.ha-tools-config.yaml`:

```yaml
home_assistant:
  url: "http://localhost:8123"
  access_token: "your_long_lived_token_here"
  timeout: 30

database:
  url: "sqlite:////config/home-assistant_v2.db"
  pool_size: 10
  max_overflow: 20
  timeout: 30

ha_config_path: "/config"
output_format: "markdown"
```

## Global Options

- `--verbose` / `-v`: Enable detailed output showing timing, API calls, and intermediate steps
- `--limit` / `-l`: Maximum entities to return (default: 100)

## Development

### Project Structure

```
ha_tools/
├── cli.py              # Main entry point
├── config.py           # Configuration management
├── commands/           # Command implementations
│   ├── validate.py     # Configuration validation
│   ├── entities.py     # Entity discovery
│   └── errors.py       # Error diagnostics
└── lib/               # Core libraries
    ├── database.py     # Database connection layer
    ├── rest_api.py     # Home Assistant API client
    ├── registry.py     # Registry management
    └── output.py       # Output formatting
```

### Running in Development

```bash
# Install development dependencies
uv run ha-tools setup

# Test with uvx
uv run ha-tools entities --search "sensor.*"
```

## AI Agent Integration

This tool is specifically designed for AI agents with:

- **Structured Markdown Output**: Optimized for LLM consumption with progressive disclosure
- **Comprehensive Exit Codes**: Clear success/failure indicators for automation
- **Rich Metadata**: Entity relationships, device information, and correlation analysis
- **Fast Operations**: Optimized for quick iteration and analysis

## License

MIT License - see LICENSE file for details.

## Contributing

Contributions welcome! Please see CONTRIBUTING.md for guidelines.