---
date: 2025-12-14T13:45:00+01:00
researcher: Claude
git_commit: 409c08d039a69e74ea8904a3a78672b352c76a5a
branch: main
repository: ha-tools
topic: "Add ha-tools history command - Integration Points Research"
tags: [research, codebase, history-command, cli, database, output-formatting]
status: complete
last_updated: 2025-12-14
last_updated_by: Claude
---

# Research: Add ha-tools history command

**Date**: 2025-12-14T13:45:00+01:00
**Researcher**: Claude
**Git Commit**: 409c08d039a69e74ea8904a3a78672b352c76a5a
**Branch**: main
**Repository**: ha-tools

## Research Question

Research integration points for adding a dedicated `ha-tools history <entity_id>` command for deep-diving into single entity state history. The command specification:

```
ha-tools history <entity_id> [options]

Options:
  --timeframe, -t  (default: 24h)   Time range (30m, 2h, 7d, 2w)
  --limit, -l      (default: 100)   Max records to return (-1 for no limit)
  --stats, -s      (default: off)   Include statistics
  --format, -f     (default: markdown)  Output: markdown, json, csv
```

## Summary

The ha-tools codebase has well-established patterns for adding new commands. Key findings:

1. **CLI Registration**: Commands are defined in `commands/` modules and registered via `app.command(name="...")(function)` in `cli.py`
2. **Database Queries**: `get_entity_states()` in `lib/database.py` already supports entity filtering, timeframes, and limits
3. **Timeframe Parsing**: Existing `parse_timeframe()` utility in `lib/utils.py` handles `Nm/Nh/Nd/Nw` formats
4. **Output Formats**: Markdown and JSON patterns exist; CSV needs new implementation
5. **Statistics**: Must be computed Python-side from state records (no SQL aggregation)
6. **Testing**: Comprehensive async test patterns with fixtures in `tests/conftest.py`

## Detailed Findings

### 1. CLI Registration Pattern

**File**: `ha_tools/cli.py`

#### App Creation (lines 23-27)

```python
app = typer.Typer(
    help="High-performance CLI for AI agents working with Home Assistant configurations",
    rich_markup_mode="rich",
    invoke_without_command=True,
)
```

#### Command Registration (lines 79-86)

```python
from .commands.entities import entities_command
from .commands.errors import errors_command
from .commands.validate import validate_command

app.command(name="validate")(validate_command)
app.command(name="entities")(entities_command)
app.command(name="errors")(errors_command)
```

#### Global Verbose Flag (lines 30-67)

The `--verbose` flag is handled globally via callback. Commands access verbose state via:

- `is_verbose()` - Check if verbose mode enabled
- `print_verbose(message)` - Print verbose messages
- `print_verbose_timing(operation, duration_ms)` - Print timing info

**Implementation for history command**:

```python
# In cli.py, add:
from .commands.history import history_command
app.command(name="history")(history_command)
```

### 2. Command Module Structure

**Pattern from**: `ha_tools/commands/entities.py`

#### Standard Command Signature

```python
def history_command(
    entity_id: str = typer.Argument(
        ...,  # Required positional argument
        help="Entity ID to analyze history for"
    ),
    timeframe: str = typer.Option(
        "24h",
        "--timeframe", "-t",
        help="History timeframe: Nm (minutes), Nh (hours), Nd (days), Nw (weeks)"
    ),
    limit: int = typer.Option(
        100,
        "--limit", "-l",
        help="Maximum number of records to return (-1 for no limit)"
    ),
    stats: bool = typer.Option(
        False,
        "--stats", "-s",
        help="Include statistics"
    ),
    format: str = typer.Option(
        "markdown",
        "--format", "-f",
        help="Output format (markdown, json, csv)"
    ),
) -> None:
```

**Key difference**: Use `typer.Argument()` for the required `entity_id` (positional), not `typer.Option()`.

#### Async Wrapper Pattern (entities.py:70-78)

```python
def history_command(...) -> None:
    """Public command function (sync)."""
    try:
        exit_code = asyncio.run(_run_history_command(...))
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print_error("History analysis cancelled")
        sys.exit(1)
    except Exception as e:
        print_error(f"History analysis failed: {e}")
        sys.exit(1)

async def _run_history_command(...) -> int:
    """Private async implementation."""
    # Actual command logic here
    return 0
```

#### Resource Management Pattern (entities.py:81-124)

```python
async def _run_history_command(...) -> int:
    try:
        config = HaToolsConfig.load()
    except Exception as e:
        print_error(f"Configuration error: {e}")
        return 3  # Configuration error exit code

    async with DatabaseManager(config.database) as db:
        async with HomeAssistantAPI(config.home_assistant) as api:
            # Command logic with database and API access
            pass

    return 0
```

### 3. Database Query Methods

**File**: `ha_tools/lib/database.py`

#### get_entity_states() Method (lines 198-202)

```python
async def get_entity_states(
    self,
    entity_id: Optional[str] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    limit: Optional[int] = None,
    include_stats: bool = False
) -> List[Dict[str, Any]] | tuple[List[Dict[str, Any]], Dict[str, Any]]:
```

**Parameters**:

- `entity_id`: Entity ID to filter (required)
- `start_time`: Start of timeframe (datetime object)
- `end_time`: End of timeframe (datetime object)
- `limit`: Maximum records to return (-1 or None for no limit)
- `include_stats`: Return tuple with query stats (total_records, filtered_count, query_time_ms)

**Return Value**:

- Default: `List[Dict[str, Any]]` with keys: `entity_id`, `state`, `last_changed`, `last_updated`, `attributes`
- With `include_stats=True`: `tuple[List[Dict], Dict]` where stats dict contains performance metrics

**Usage for history command**:

```python
# Parse timeframe to datetime
start_time = parse_timeframe(timeframe)  # e.g., "24h" -> datetime 24h ago

# Query states
result = await db.get_entity_states(
    entity_id=entity_id,
    start_time=start_time,
    limit=limit,
    include_stats=is_verbose()
)

# Handle return type
if isinstance(result, tuple):
    states, stats = result
else:
    states = result
```

### 4. Timeframe Parsing

**File**: `ha_tools/lib/utils.py` (lines 8-47)

```python
def parse_timeframe(timeframe: str) -> datetime:
    """
    Supported formats:
        - Nm: N minutes ago (e.g., 30m)
        - Nh: N hours ago (e.g., 24h)
        - Nd: N days ago (e.g., 7d)
        - Nw: N weeks ago (e.g., 2w)
    """
```

**Import pattern**:

```python
from ..lib.utils import parse_timeframe
```

**Already used in**: `entities.py:21`, `errors.py:23`

### 5. Output Formatting Patterns

**File**: `ha_tools/lib/output.py`

#### MarkdownFormatter Class (lines 68-137)

```python
formatter = MarkdownFormatter(title="Entity History")

# Add summary section
formatter.add_section(
    "Summary",
    f"Found **{len(states)}** state changes for `{entity_id}` in the last {timeframe}"
)

# Add table
headers = ["Timestamp", "State", "Changed"]
rows = [[s["last_updated"], s["state"], s["last_changed"]] for s in states]
formatter.add_table(headers, rows, "State History")

# Add statistics section (if --stats)
if stats:
    formatter.add_section("Statistics", f"Min: {min_val}, Max: {max_val}, Avg: {avg_val:.2f}")

# Output
print(formatter.format())
```

#### JSON Output Pattern (entities.py:273-275)

```python
if format == "json":
    print(json.dumps(data, indent=2, default=str))
```

#### CSV Output (NEW - needs implementation)

```python
import csv
import io

def _output_csv_format(states: List[Dict], include_attrs: bool = False) -> None:
    """Output states in CSV format."""
    output = io.StringIO()

    # Base headers
    headers = ["timestamp", "state"]

    # Optionally flatten attributes
    if include_attrs and states:
        # Get unique attribute keys from first record
        attrs = json.loads(states[0].get("attributes", "{}"))
        attr_keys = sorted(attrs.keys())
        headers.extend(attr_keys)

    writer = csv.writer(output)
    writer.writerow(headers)

    for state in states:
        row = [state["last_updated"], state["state"]]
        if include_attrs:
            attrs = json.loads(state.get("attributes", "{}"))
            row.extend(attrs.get(k, "") for k in attr_keys)
        writer.writerow(row)

    print(output.getvalue())
```

#### Format Routing Pattern

```python
async def _output_results(states, format, entity_id, stats_data):
    if format == "json":
        _output_json_format(states, entity_id, stats_data)
    elif format == "csv":
        _output_csv_format(states)
    else:  # markdown (default)
        _output_markdown_format(states, entity_id, stats_data)
```

### 6. Statistics Computation

**Note**: Statistics must be computed Python-side from state records.

```python
def compute_statistics(states: List[Dict]) -> Dict[str, Any]:
    """Compute min/max/avg from state records."""
    numeric_values = []

    for state in states:
        try:
            value = float(state["state"])
            numeric_values.append(value)
        except (ValueError, TypeError):
            continue  # Skip non-numeric states

    if not numeric_values:
        return {"error": "No numeric values found"}

    return {
        "min": min(numeric_values),
        "max": max(numeric_values),
        "avg": sum(numeric_values) / len(numeric_values),
        "count": len(numeric_values),
        "total_records": len(states)
    }
```

### 7. Error Handling and Exit Codes

**Convention** (documented but not in a central constant, let's refactor this to a central constant!):

- `0`: Success
- `1`: General error (KeyboardInterrupt, unexpected exceptions)
- `2`: Validation errors
- `3`: Configuration/connection error
- `4`: Database error (mentioned in docs, rarely used)

**Pattern**:

```python
async def _run_history_command(...) -> int:
    try:
        config = HaToolsConfig.load()
    except Exception as e:
        print_error(f"Configuration error: {e}")
        return 3

    # Check entity exists
    async with DatabaseManager(config.database) as db:
        if not db.is_connected():
            print_error(f"Database unavailable: {db.get_connection_error()}")
            return 4

        states = await db.get_entity_states(entity_id, start_time, limit=limit)

        if not states:
            print_warning(f"No history found for {entity_id}")
            # Still return 0 - empty result is valid

    return 0
```

### 8. Verbose Mode Integration

**Access pattern** (from `lib/output.py`):

```python
from ..lib.output import (
    print_verbose,
    print_verbose_timing,
    is_verbose
)

# Usage in command
print_verbose(f"Fetching history for {entity_id}...")
start = time.time()
states = await db.get_entity_states(...)
print_verbose_timing("History query", (time.time() - start) * 1000)

# Conditional stats in verbose mode
result = await db.get_entity_states(
    entity_id, start_time, limit=limit,
    include_stats=is_verbose()
)
```

### 9. Test Patterns

**File structure**:

```
tests/
├── conftest.py                  # Shared fixtures
├── unit/
│   └── test_history_command.py  # NEW: Unit tests
└── integration/
    └── test_cli_integration.py  # Add history workflow tests
```

#### Test Fixture Pattern (conftest.py)

```python
@pytest.fixture
def mock_database_manager():
    db = AsyncMock()
    db.is_connected = MagicMock(return_value=True)
    db.get_entity_states.return_value = [
        {
            "entity_id": "sensor.temperature",
            "state": "20.0",
            "last_changed": "2024-01-01T12:00:00+00:00",
            "last_updated": "2024-01-01T12:00:00+00:00",
            "attributes": '{"unit_of_measurement": "°C"}'
        }
    ]
    return db
```

#### Async Test Pattern

```python
@pytest.mark.asyncio
async def test_run_history_command_success(mock_database_manager):
    with patch('ha_tools.commands.history.DatabaseManager') as mock_db_class:
        mock_db_class.return_value.__aenter__ = AsyncMock(return_value=mock_database_manager)
        mock_db_class.return_value.__aexit__ = AsyncMock(return_value=None)

        result = await _run_history_command(
            entity_id="sensor.temperature",
            timeframe="24h",
            limit=100,
            stats=False,
            format="markdown"
        )

        assert result == 0
```

## Code References

| File                            | Line    | Description                    |
| ------------------------------- | ------- | ------------------------------ |
| `ha_tools/cli.py`               | 23-27   | Typer app creation             |
| `ha_tools/cli.py`               | 30-67   | Global callback with --verbose |
| `ha_tools/cli.py`               | 79-86   | Command registration pattern   |
| `ha_tools/commands/entities.py` | 26-57   | Command function signature     |
| `ha_tools/commands/entities.py` | 70-78   | Async wrapper pattern          |
| `ha_tools/commands/entities.py` | 81-124  | Resource management pattern    |
| `ha_tools/lib/database.py`      | 198-202 | get_entity_states() signature  |
| `ha_tools/lib/database.py`      | 245-284 | SQLite query structure         |
| `ha_tools/lib/utils.py`         | 8-47    | parse_timeframe() function     |
| `ha_tools/lib/output.py`        | 68-137  | MarkdownFormatter class        |
| `ha_tools/lib/output.py`        | 36-45   | Verbose output functions       |
| `tests/conftest.py`             | 160-192 | Mock database fixture          |

## Architecture Insights

### Design Patterns Used

1. **Sync/Async Wrapper**: Public typer functions are sync, wrap async implementation with `asyncio.run()`
2. **Context Manager Resources**: Database and API clients use `async with` for cleanup
3. **Graceful Degradation**: Database unavailable falls back to API-only mode
4. **Progressive Disclosure**: Markdown output shows summary first, then details
5. **Module-Level State**: Verbose flag stored in `output.py` module global

### Key Implementation Decisions

1. **Use Argument for entity_id**: Unlike existing commands that use only Options, history needs a required positional argument
2. **CSV Output is New**: Must implement from scratch; no existing pattern
3. **Statistics are Python-side**: No SQL aggregation; filter numeric states and compute
4. **No Table Format**: Spec excludes table format; only markdown, json, csv

## Implementation Checklist

- [ ] Create `ha_tools/commands/history.py` with command function
- [ ] Register command in `ha_tools/cli.py`
- [ ] Implement `_run_history_command()` async function
- [ ] Add `_output_markdown_format()` with summary and state list
- [ ] Add `_output_json_format()` with optional stats metadata
- [ ] Add `_output_csv_format()` with flattened attributes
- [ ] Add `compute_statistics()` helper for --stats flag
- [ ] Create `tests/unit/test_history_command.py`
- [ ] Add history workflow to integration tests
- [ ] Update CLAUDE.md with history command examples

## Open Questions

1. **Attribute Handling in CSV**: Should all attributes be flattened, or only common ones?
2. **Empty Result Handling**: Return exit 0 with message, or exit 1?
3. **Statistics for Non-Numeric**: What to show when entity has non-numeric states?
