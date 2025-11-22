# Home Assistant Tools CLI Design

## Overview

`ha-tools` is a lightweight CLI for AI agents working with Home Assistant configurations. Designed to replace heavy MCP implementations with fast, targeted operations using hybrid REST API + direct database access.

**Target Use**: AI agents need to validate changes, discover entities, and diagnose runtime errors efficiently.

## Installation & Setup

```bash
# Install the tool
pip install ha-tools

# Configure Home Assistant connection
ha-tools setup

# Test connection
ha-tools test-connection
```

## Core Commands

### `ha-tools validate [--syntax-only]`

Validate Home Assistant configuration.

**Approach:**
- **Default**: Full semantic validation via HA REST API
- **`--syntax-only`**: Fast local YAML syntax checking

**Examples:**
```bash
ha-tools validate              # Full HA validation (slow but complete)
ha-tools validate --syntax-only  # Quick syntax check (fast)
```

### `ha-tools entities [--search <pattern>] [--include <type>] [--history <timeframe>]`

Discover and analyze entities with hybrid data sources.

**Data Sources:**
- **Database**: Fast history queries, long-term statistics, performance data
- **Filesystem**: Entity definitions, package organization, template dependencies
- **REST API**: Real-time current state as fallback

**Include Types:**
- `basic` (default): entity metadata and current state
- `state`: full current state with all attributes
- `history`: historical data points and trends
- `relations`: areas, groups, device relationships

**History Timeframes:**
- Relative: `24h`, `7d`, `30d`
- Samples: `last:10`, `samples:50`

**Examples:**
```bash
# Discover all entities with metadata
ha-tools entities

# Find temperature sensors with current values
ha-tools entities --search "temp_*" --include state

# Analyze heating system behavior over time
ha-tools entities --search "heizung*" --include history --history 7d

# Long-term trends (365+ days via database statistics)
ha-tools entities --include history --history 365d
```

### `ha-tools errors [--current] [--log <timeframe>] [--entity <pattern>]`

Diagnose runtime errors using multiple sources.

**Data Sources:**
- **REST API**: Current session errors (`/api/error_log`)
- **Filesystem**: Persistent log file parsing (`/config/home-assistant.log`)
- **Database**: Error correlation with entity states and events

**Examples:**
```bash
# Current runtime errors
ha-tools errors --current

# Error history for specific entities
ha-tools errors --entity "heizung*" --log 24h

# Full error analysis
ha-tools errors --log 7d
```

## Output Format

All commands output **structured markdown** optimized for AI agent consumption:

- Tables for entity listings and comparisons
- Code blocks for error messages and configuration snippets
- Headers for logical organization
- Human-readable for review purposes

## Performance Architecture

**Hybrid Strategy for Speed:**

| Operation | Method | Speed | When to Use |
|-----------|--------|-------|-------------|
| Entity discovery | Database + Filesystem | 6x faster | Default |
| History queries | Database | 10-15x faster | All history |
| Long-term trends | Database statistics | Exclusive capability | >10 days |
| Real-time state | REST API | Tie | Current state only |
| Runtime validation | REST API | Required | Final check |

## Configuration

```yaml
# ~/.ha-tools-config.yaml
homeassistant:
  url: "http://homeassistant.local:8123"
  token: "your_long_lived_access_token"

database:
  type: "mariadb"  # mariadb, postgresql, sqlite
  host: "localhost"
  database: "homeassistant"
  user: "ha_readonly"  # Always use read-only access

performance:
  use_database: true
  cache_duration: 300  # 5 minutes

output:
  format: "markdown"
  colors: true
```

## AI Agent Workflow

### Typical Configuration Changes

```bash
# 1. AI makes changes to config files

# 2. Quick syntax validation
ha-tools validate --syntax-only

# 3. Check affected entities
ha-tools entities --search "modified_area*" --include state

# 4. Full validation if syntax OK
ha-tools validate

# 5. Human reviews and deploys manually
# 6. Check for runtime issues
ha-tools errors --current
```

### Debugging Existing Issues

```bash
# User: "Heating automation stopped working"

# Check entity behavior history
ha-tools entities --search "heizung*" --include history --history 24h

# Look for related errors
ha-tools errors --entity "heizung*" --log 24h

# Analyze automation dependencies
ha-tools entities --include relations --search "automation.heating*"
```

## Extension Points

The simple 3-command architecture can be extended later:

- **Package operations**: `ha-tools packages list|analyze`
- **Template validation**: `ha-tools template validate <file>`
- **Advanced analytics**: `ha-tools stats entity <id>`

## Error Handling

- **Syntax errors**: File and line numbers with context
- **Connection issues**: Clear troubleshooting steps
- **Database access**: Graceful fallback to REST API
- **Entity not found**: Suggestions for similar names

## Exit Codes

- `0`: Success
- `1`: General error
- `2`: Validation failed
- `3`: Connection error
- `4`: Database access error