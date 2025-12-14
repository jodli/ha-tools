# Home Assistant Tools Reference

Quick command reference for the `ha-tools` CLI - optimized for AI agent workflow with hybrid REST API + direct database access.

## Core Commands

### Validation
```bash
ha-tools validate [--syntax-only]
```

### Entity Discovery & Analysis
```bash
ha-tools entities [--search <pattern>] [--include <type>] [--history <timeframe>]
```

### Error Diagnostics
```bash
ha-tools errors [--current] [--log <timeframe>] [--entity <pattern>]
```

## Command Details

### `ha-tools validate`

**Purpose**: Configuration validation for AI agents
**Data Sources**: REST API for runtime, filesystem for syntax

**Usage Examples:**
```bash
ha-tools validate              # Full HA validation (2-3 min)
ha-tools validate --syntax-only  # Quick YAML syntax check (instant)
```

**Expected Output:**
- Success: "✅ Configuration valid"
- Errors: File/line references with specific issues
- Markdown format optimized for AI consumption

### `ha-tools entities`

**Purpose**: Entity discovery with rich data analysis
**Data Sources**: Database (history), filesystem (metadata), REST API (state)

**Include Types:**
- `basic` (default): entity metadata + current state
- `state`: full state with all attributes
- `history`: historical data points and trends
- `relations`: areas, groups, device relationships

**Search Patterns:**
- Substring matching: `temp`, `heizung`, `living`
- Match anywhere in entity ID: `--search "sensor"` matches all sensor entities

**History Timeframes:**
- `Nh` - hours (e.g., `24h`)
- `Nd` - days (e.g., `7d`)
- `Nm` - minutes (e.g., `30m`)
- `Nw` - weeks (e.g., `2w`)
- Long-term: `365d` (via database statistics)

**Usage Examples:**
```bash
# Basic entity discovery
ha-tools entities

# Find temperature sensors (substring matching)
ha-tools entities --search "temp"

# Heating system analysis with history
ha-tools entities --search "heizung" --include history --history 7d

# Current state with full attributes
ha-tools entities --include state --search "temperature"

# Long-term trends (365+ days)
ha-tools entities --include history --history 365d

# Enable verbose output for debugging
ha-tools entities --search "sensor" --verbose
```

**Performance:**
- Entity discovery: 6x faster than REST API alone
- History queries: 10-15x faster than REST API
- Long-term data: Database statistics (not available via REST)

### `ha-tools errors`

**Purpose**: Runtime error diagnosis with correlation analysis
**Data Sources**: REST API (current), filesystem (logs), database (correlation)

**Usage Examples:**
```bash
# Current runtime errors
ha-tools errors --current

# Error history for heating system (substring matching)
ha-tools errors --entity "heizung" --log 24h

# Full error analysis
ha-tools errors --log 7d

# Specific entity error correlation
ha-tools errors --entity "temperature_living" --current

# Verbose output for debugging connectivity
ha-tools errors --current --verbose
```

**Expected Output:**
- Current session errors from HA API
- Historical errors from log files
- Entity correlation with database states
- Structured markdown for AI analysis

## AI Agent Workflow Patterns

### Configuration Changes
```bash
# AI makes changes to config files...

# 1. Quick syntax check
ha-tools validate --syntax-only

# 2. Validate changes
ha-tools validate

# 3. Check affected entities (substring matching)
ha-tools entities --search "modified_area" --include state

# 4. Human reviews and deploys...

# 5. Check for runtime issues
ha-tools errors --current
```

### Debugging Existing Issues
```bash
# User: "Heating automation stopped working"

# 1. Check entity behavior history (use --verbose for timing)
ha-tools entities --search "heizung" --include history --history 24h --verbose

# 2. Look for related errors
ha-tools errors --entity "heizung" --log 24h

# 3. Analyze automation dependencies
ha-tools entities --include relations --search "automation.heating"
```

### Entity Discovery
```bash
# What temperature sensors exist? (substring matching)
ha-tools entities --search "temp"

# How are entities organized?
ha-tools entities --include relations

# What entities are in a specific area?
ha-tools entities --search "living" --include history --history 7d
```

## Performance Architecture

| Operation | Method | Speedup | Use Case |
|-----------|--------|---------|----------|
| Entity discovery | Database + Filesystem | 6x faster | Default |
| History queries | Direct database | 10-15x faster | All history |
| Long-term trends | Statistics database | Exclusive | >10 days |
| Real-time state | REST API | Same | Current state |
| Runtime validation | REST API | Required | Final check |

## Data Sources & Capabilities

### Database Access
- **Fast history queries**: State changes, attribute history
- **Long-term statistics**: 365+ days of aggregated data
- **Bulk operations**: Multiple entities in single query
- **Performance analytics**: Entity activity rankings

### Filesystem Access
- **Entity definitions**: YAML package parsing
- **Package organization**: Directory structure analysis
- **Template dependencies**: Entity reference extraction
- **Configuration drift**: YAML vs runtime comparison

### REST API Fallback
- **Current state**: Real-time entity values
- **Runtime validation**: `/api/config/core/check_config`
- **Error logs**: Current session errors
- **Connection testing**: Availability checks

## Output Format

All commands output **structured markdown**:

```markdown
# Entity: sensor.temperature_living_room

**Package:** `room_living.yaml`
**Current State:** 21.5°C
**Last Changed:** 2 minutes ago

### 24h History Trend
| Time | Value | Change |
|------|-------|--------|
| Now  | 21.5  | +0.2   |
| 1h   | 21.3  | -0.1   |

### Related Entities
- automation.heating_control
- climate.living_room_thermostat
```

## Error Codes

- `0`: Success
- `1`: General error
- `2`: Validation failed
- `3`: Connection error
- `4`: Database access error

## Extension Points

Future commands (not implemented yet):
- `ha-tools packages list|analyze` - Package operations
- `ha-tools template validate <file>` - Template validation
- `ha-tools stats entity <id>` - Advanced statistics

## Configuration

```yaml
# ~/.ha-tools-config.yaml
homeassistant:
  url: "http://homeassistant.local:8123"
  token: "your_long_lived_access_token"

database:
  type: "mariadb"
  host: "localhost"
  database: "homeassistant"
  user: "ha_readonly"  # Always read-only

performance:
  use_database: true
  cache_duration: 300
```