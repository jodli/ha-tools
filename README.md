# HAT - Home Assistant Tools

> High-performance CLI for AI agents working with Home Assistant

**HAT** gives AI agents fast, reliable access to Home Assistant - validation, entity discovery, history analysis, and error diagnostics. Built for speed with direct database access (10-15x faster than REST API).

## Quick Start

```bash
# Setup
uv run ha-tools setup

# Validate config
uv run ha-tools validate --syntax-only   # Quick syntax check
uv run ha-tools validate                  # Full validation

# Explore entities (supports * wildcard and | for OR)
uv run ha-tools entities --search "temp"
uv run ha-tools entities --search "temp|humidity"
uv run ha-tools entities --search "script.*saugen"
uv run ha-tools entities --include history --history 24h

# Analyze history
uv run ha-tools history sensor.temperature --stats

# Check errors
uv run ha-tools errors --current
```

## Commands

| Command | Purpose |
|---------|---------|
| `validate` | Configuration syntax & semantic validation |
| `entities` | Entity discovery, search, and state analysis |
| `history` | Single entity history with stats and export |
| `errors` | Runtime error diagnostics |

## Key Features

- **Fast**: Direct database access for history queries (MariaDB, PostgreSQL, SQLite)
- **AI-Optimized**: Structured markdown output, clear exit codes
- **Flexible**: Timeframes like `24h`, `7d`, `30m`, `2w`

## Configuration

Config lives at `~/.ha-tools-config.yaml`:

```yaml
home_assistant:
  url: "http://localhost:8123"
  access_token: "your_token"

database:
  url: "sqlite:////config/home-assistant_v2.db"

ha_config_path: "/config"
```

## License

MIT - see [LICENSE](LICENSE)
