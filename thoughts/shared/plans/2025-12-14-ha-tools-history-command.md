# ha-tools history command Implementation Plan

## Overview

Add a dedicated `ha-tools history <entity_id>` command for deep-diving into single entity state history. This command provides detailed historical state analysis with optional statistics and multiple output formats.

## Current State Analysis

The ha-tools codebase has well-established patterns for CLI commands:
- Commands are registered in `cli.py` via `app.command(name="...")(function)`
- Command modules in `commands/` follow sync wrapper + async implementation pattern
- Database queries use `DatabaseManager.get_entity_states()` with timeframe filtering
- Output formatting uses `MarkdownFormatter` for markdown, `json.dumps` for JSON

### Key Discoveries:
- `get_entity_states()` already supports single entity filtering, timeframes, and limits (`lib/database.py:198-202`)
- `parse_timeframe()` handles `Nm/Nh/Nd/Nw` formats (`lib/utils.py:8-47`)
- Existing commands use `typer.Option()` only; history needs `typer.Argument()` for required entity_id
- CSV output is new - no existing pattern to follow
- Statistics must be computed Python-side from state records

## Desired End State

After implementation:
1. `ha-tools history sensor.temperature` returns last 24h of state history in markdown
2. `ha-tools history sensor.temperature --timeframe 7d --stats` includes min/max/avg for numeric entities
3. `ha-tools history switch.light --stats` shows state change counts for non-numeric entities
4. `ha-tools history sensor.temperature --format csv` outputs CSV with dynamic attribute columns
5. `ha-tools history sensor.temperature --format json` outputs JSON array with optional stats metadata
6. Verbose mode shows query timing and record counts

### Verification:
```bash
# Basic usage
uv run ha-tools history sensor.temperature

# With options
uv run ha-tools history sensor.temperature --timeframe 7d --limit 50 --stats --verbose

# Different formats
uv run ha-tools history sensor.temperature --format json
uv run ha-tools history sensor.temperature --format csv
```

## What We're NOT Doing

- No REST API fallback - history command is database-only (design decision)
- No wildcard entity matching - single entity only (use `entities --search` for discovery)
- No graph/chart output - text formats only
- No real-time streaming - snapshot queries only
- No attribute filtering - all attributes included in CSV

## Implementation Approach

Single-phase implementation following existing command patterns. The history command is self-contained and doesn't require changes to shared libraries.

## Phase 1: Implement history command

### Overview
Create the complete history command with all features in one phase.

### Changes Required:

#### 1. Create command module
**File**: `ha_tools/commands/history.py` (new file)

```python
"""
History command for ha-tools.

Provides detailed state history analysis for a single entity.
"""

import asyncio
import csv
import io
import json
import sys
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import typer

from ..config import HaToolsConfig
from ..lib.database import DatabaseManager
from ..lib.output import (
    MarkdownFormatter,
    print_error,
    print_info,
    print_warning,
    print_verbose,
    print_verbose_timing,
    is_verbose,
    format_timestamp,
)
from ..lib.utils import parse_timeframe


def history_command(
    entity_id: str = typer.Argument(
        ...,
        help="Entity ID to analyze history for (e.g., sensor.temperature)"
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
        help="Include statistics (min/max/avg for numeric, state counts for non-numeric)"
    ),
    format: str = typer.Option(
        "markdown",
        "--format", "-f",
        help="Output format (markdown, json, csv)"
    ),
) -> None:
    """
    Analyze state history for a single entity.

    Provides detailed historical state data with optional statistics.
    Uses direct database access for fast queries.

    Examples:
        ha-tools history sensor.temperature
        ha-tools history sensor.temperature --timeframe 7d --stats
        ha-tools history switch.light --format csv --limit -1
    """
    try:
        exit_code = asyncio.run(_run_history_command(entity_id, timeframe, limit, stats, format))
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print_error("History analysis cancelled")
        sys.exit(1)
    except Exception as e:
        print_error(f"History analysis failed: {e}")
        sys.exit(1)


async def _run_history_command(
    entity_id: str,
    timeframe: str,
    limit: int,
    stats: bool,
    format: str
) -> int:
    """Run the history command."""
    # Load configuration
    try:
        config = HaToolsConfig.load()
    except Exception as e:
        print_error(f"Configuration error: {e}")
        return 3

    # Parse timeframe
    try:
        start_time = parse_timeframe(timeframe)
    except ValueError as e:
        print_error(f"Invalid timeframe: {e}")
        return 2

    # Validate format
    if format not in ("markdown", "json", "csv"):
        print_error(f"Invalid format '{format}'. Use: markdown, json, csv")
        return 2

    # Handle limit=-1 as no limit
    query_limit = None if limit == -1 else limit

    print_verbose(f"Fetching history for {entity_id}...")

    async with DatabaseManager(config.database) as db:
        if not db.is_connected():
            print_error(f"Database unavailable: {db.get_connection_error()}")
            return 4

        # Query states with stats in verbose mode
        start_query = time.time()
        result = await db.get_entity_states(
            entity_id=entity_id,
            start_time=start_time,
            limit=query_limit,
            include_stats=is_verbose()
        )

        if is_verbose() and isinstance(result, tuple):
            states, query_stats = result
            print_verbose_timing("History query", query_stats.get("query_time_ms", 0))
            print_verbose(f"Total records for entity: {query_stats.get('total_records', 0):,}")
            print_verbose(f"Records in timeframe: {query_stats.get('filtered_count', 0):,}")
        else:
            states = result

        # Handle empty results
        if not states:
            print_warning(f"No history found for {entity_id} in the last {timeframe}")
            return 0

        # Compute statistics if requested
        stats_data = None
        if stats:
            stats_data = _compute_statistics(states)

        # Output results
        _output_results(states, format, entity_id, timeframe, stats_data)

    return 0


def _compute_statistics(states: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute statistics from state records.

    For numeric states: min, max, avg
    For non-numeric states: state change counts
    """
    numeric_values = []
    state_counts: Dict[str, int] = {}

    for state in states:
        state_value = state.get("state", "")

        # Count all states
        state_counts[state_value] = state_counts.get(state_value, 0) + 1

        # Try to parse as numeric
        try:
            if state_value not in ("unknown", "unavailable", ""):
                numeric_values.append(float(state_value))
        except (ValueError, TypeError):
            pass

    result = {
        "total_records": len(states),
        "unique_states": len(state_counts),
        "state_counts": state_counts,
    }

    if numeric_values:
        result["numeric"] = True
        result["min"] = min(numeric_values)
        result["max"] = max(numeric_values)
        result["avg"] = sum(numeric_values) / len(numeric_values)
        result["numeric_count"] = len(numeric_values)
    else:
        result["numeric"] = False

    return result


def _output_results(
    states: List[Dict[str, Any]],
    format: str,
    entity_id: str,
    timeframe: str,
    stats_data: Optional[Dict[str, Any]]
) -> None:
    """Output results in the specified format."""
    if format == "json":
        _output_json_format(states, entity_id, timeframe, stats_data)
    elif format == "csv":
        _output_csv_format(states)
    else:  # markdown (default)
        _output_markdown_format(states, entity_id, timeframe, stats_data)


def _output_markdown_format(
    states: List[Dict[str, Any]],
    entity_id: str,
    timeframe: str,
    stats_data: Optional[Dict[str, Any]]
) -> None:
    """Output states in markdown format."""
    formatter = MarkdownFormatter(title=f"History: {entity_id}")

    # Summary section
    summary_lines = [
        f"Found **{len(states)}** state changes in the last **{timeframe}**"
    ]
    formatter.add_section("📊 Summary", "\n".join(summary_lines))

    # Statistics section (if requested)
    if stats_data:
        stats_lines = []
        if stats_data.get("numeric"):
            stats_lines.append(f"**Min:** {stats_data['min']:.2f}")
            stats_lines.append(f"**Max:** {stats_data['max']:.2f}")
            stats_lines.append(f"**Average:** {stats_data['avg']:.2f}")
            stats_lines.append(f"**Samples:** {stats_data['numeric_count']}")
        else:
            stats_lines.append("**State Distribution:**")
            for state_val, count in sorted(
                stats_data["state_counts"].items(),
                key=lambda x: x[1],
                reverse=True
            ):
                pct = (count / stats_data["total_records"]) * 100
                stats_lines.append(f"- `{state_val}`: {count} ({pct:.1f}%)")

        formatter.add_section("📈 Statistics", "\n".join(stats_lines))

    # State history table
    headers = ["Timestamp", "State", "Changed"]
    rows = []
    for state in states[:50]:  # Limit table rows for readability
        rows.append([
            format_timestamp(state.get("last_updated")),
            state.get("state", "N/A"),
            format_timestamp(state.get("last_changed")),
        ])

    formatter.add_table(headers, rows, "State History")

    if len(states) > 50:
        formatter.add_section("", f"*... and {len(states) - 50} more records (use --format csv for full data)*")

    print(formatter.format())


def _output_json_format(
    states: List[Dict[str, Any]],
    entity_id: str,
    timeframe: str,
    stats_data: Optional[Dict[str, Any]]
) -> None:
    """Output states in JSON format."""
    output = {
        "entity_id": entity_id,
        "timeframe": timeframe,
        "count": len(states),
        "states": states,
    }

    if stats_data:
        output["statistics"] = stats_data

    print(json.dumps(output, indent=2, default=str))


def _output_csv_format(states: List[Dict[str, Any]]) -> None:
    """Output states in CSV format with dynamic attribute columns."""
    if not states:
        return

    # Collect all attribute keys from all states
    all_attr_keys: set[str] = set()
    parsed_attrs: List[Dict[str, Any]] = []

    for state in states:
        attrs_raw = state.get("attributes", "{}")
        if isinstance(attrs_raw, str):
            try:
                attrs = json.loads(attrs_raw)
            except json.JSONDecodeError:
                attrs = {}
        else:
            attrs = attrs_raw or {}
        parsed_attrs.append(attrs)
        all_attr_keys.update(attrs.keys())

    # Sort attribute keys for consistent column order
    attr_keys = sorted(all_attr_keys)

    # Build CSV
    output = io.StringIO()
    headers = ["timestamp", "state", "last_changed"] + [f"attr_{k}" for k in attr_keys]

    writer = csv.writer(output)
    writer.writerow(headers)

    for state, attrs in zip(states, parsed_attrs):
        row = [
            state.get("last_updated", ""),
            state.get("state", ""),
            state.get("last_changed", ""),
        ]
        # Add attribute values in order
        for key in attr_keys:
            value = attrs.get(key, "")
            # Convert complex types to JSON strings
            if isinstance(value, (dict, list)):
                value = json.dumps(value)
            row.append(value)
        writer.writerow(row)

    print(output.getvalue(), end="")
```

#### 2. Register command in CLI
**File**: `ha_tools/cli.py`

Add import after line 82:
```python
from .commands.history import history_command
```

Add registration after line 86:
```python
app.command(name="history")(history_command)
```

#### 3. Create unit tests
**File**: `tests/unit/test_history_command.py` (new file)

```python
"""Unit tests for the history command."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from io import StringIO

from ha_tools.commands.history import (
    _run_history_command,
    _compute_statistics,
    _output_csv_format,
    _output_json_format,
    _output_markdown_format,
)


class TestComputeStatistics:
    """Tests for _compute_statistics function."""

    def test_numeric_states(self):
        """Test statistics for numeric states."""
        states = [
            {"state": "20.0"},
            {"state": "21.5"},
            {"state": "19.0"},
            {"state": "22.0"},
        ]

        stats = _compute_statistics(states)

        assert stats["numeric"] is True
        assert stats["min"] == 19.0
        assert stats["max"] == 22.0
        assert stats["avg"] == 20.625
        assert stats["numeric_count"] == 4
        assert stats["total_records"] == 4

    def test_non_numeric_states(self):
        """Test statistics for non-numeric states."""
        states = [
            {"state": "on"},
            {"state": "off"},
            {"state": "on"},
            {"state": "on"},
        ]

        stats = _compute_statistics(states)

        assert stats["numeric"] is False
        assert stats["state_counts"] == {"on": 3, "off": 1}
        assert stats["total_records"] == 4
        assert stats["unique_states"] == 2

    def test_mixed_states_with_unavailable(self):
        """Test that unavailable/unknown states are counted but not in numeric stats."""
        states = [
            {"state": "20.0"},
            {"state": "unavailable"},
            {"state": "21.0"},
            {"state": "unknown"},
        ]

        stats = _compute_statistics(states)

        assert stats["numeric"] is True
        assert stats["numeric_count"] == 2
        assert stats["total_records"] == 4
        assert "unavailable" in stats["state_counts"]


class TestOutputFormats:
    """Tests for output formatting functions."""

    def test_csv_output_with_attributes(self, capsys):
        """Test CSV output includes dynamic attribute columns."""
        states = [
            {
                "last_updated": "2024-01-01T12:00:00",
                "state": "20.0",
                "last_changed": "2024-01-01T12:00:00",
                "attributes": '{"unit_of_measurement": "°C", "friendly_name": "Temp"}'
            },
            {
                "last_updated": "2024-01-01T13:00:00",
                "state": "21.0",
                "last_changed": "2024-01-01T13:00:00",
                "attributes": '{"unit_of_measurement": "°C"}'
            },
        ]

        _output_csv_format(states)

        captured = capsys.readouterr()
        lines = captured.out.strip().split("\n")

        # Check headers include attribute columns
        headers = lines[0].split(",")
        assert "timestamp" in headers
        assert "state" in headers
        assert "attr_unit_of_measurement" in headers
        assert "attr_friendly_name" in headers

    def test_json_output_structure(self, capsys):
        """Test JSON output has correct structure."""
        states = [{"state": "20.0", "last_updated": "2024-01-01T12:00:00"}]
        stats_data = {"numeric": True, "min": 20.0, "max": 20.0, "avg": 20.0}

        _output_json_format(states, "sensor.test", "24h", stats_data)

        captured = capsys.readouterr()
        output = json.loads(captured.out)

        assert output["entity_id"] == "sensor.test"
        assert output["timeframe"] == "24h"
        assert output["count"] == 1
        assert "states" in output
        assert "statistics" in output


@pytest.mark.asyncio
class TestRunHistoryCommand:
    """Tests for _run_history_command."""

    async def test_database_unavailable(self):
        """Test handling when database is unavailable."""
        mock_db = AsyncMock()
        mock_db.is_connected = MagicMock(return_value=False)
        mock_db.get_connection_error = MagicMock(return_value=Exception("Connection failed"))

        with patch('ha_tools.commands.history.HaToolsConfig') as mock_config_class:
            mock_config = MagicMock()
            mock_config_class.load.return_value = mock_config

            with patch('ha_tools.commands.history.DatabaseManager') as mock_db_class:
                mock_db_class.return_value.__aenter__ = AsyncMock(return_value=mock_db)
                mock_db_class.return_value.__aexit__ = AsyncMock(return_value=None)

                result = await _run_history_command(
                    entity_id="sensor.test",
                    timeframe="24h",
                    limit=100,
                    stats=False,
                    format="markdown"
                )

                assert result == 4  # Database error exit code

    async def test_empty_results(self):
        """Test handling of empty results."""
        mock_db = AsyncMock()
        mock_db.is_connected = MagicMock(return_value=True)
        mock_db.get_entity_states.return_value = []

        with patch('ha_tools.commands.history.HaToolsConfig') as mock_config_class:
            mock_config = MagicMock()
            mock_config_class.load.return_value = mock_config

            with patch('ha_tools.commands.history.DatabaseManager') as mock_db_class:
                mock_db_class.return_value.__aenter__ = AsyncMock(return_value=mock_db)
                mock_db_class.return_value.__aexit__ = AsyncMock(return_value=None)

                result = await _run_history_command(
                    entity_id="sensor.nonexistent",
                    timeframe="24h",
                    limit=100,
                    stats=False,
                    format="markdown"
                )

                # Empty result is valid - should return 0
                assert result == 0

    async def test_invalid_format(self):
        """Test handling of invalid format."""
        with patch('ha_tools.commands.history.HaToolsConfig') as mock_config_class:
            mock_config = MagicMock()
            mock_config_class.load.return_value = mock_config

            result = await _run_history_command(
                entity_id="sensor.test",
                timeframe="24h",
                limit=100,
                stats=False,
                format="invalid"
            )

            assert result == 2  # Validation error exit code

    async def test_invalid_timeframe(self):
        """Test handling of invalid timeframe."""
        with patch('ha_tools.commands.history.HaToolsConfig') as mock_config_class:
            mock_config = MagicMock()
            mock_config_class.load.return_value = mock_config

            result = await _run_history_command(
                entity_id="sensor.test",
                timeframe="invalid",
                limit=100,
                stats=False,
                format="markdown"
            )

            assert result == 2  # Validation error exit code
```

#### 4. Update CLAUDE.md documentation
**File**: `CLAUDE.md`

Add to the "Development Commands" section under entity discovery examples:

```markdown
# History analysis examples
uv run ha-tools history sensor.temperature                     # Last 24h in markdown
uv run ha-tools history sensor.temperature --timeframe 7d      # Last 7 days
uv run ha-tools history sensor.temperature --stats             # With min/max/avg
uv run ha-tools history switch.light --stats                   # State change counts
uv run ha-tools history sensor.temperature --format json       # JSON output
uv run ha-tools history sensor.temperature --format csv -l -1  # Full CSV export
```

### Success Criteria:

#### Automated Verification:
- [ ] All existing tests pass: `uv run pytest`
- [ ] New unit tests pass: `uv run pytest tests/unit/test_history_command.py -v`
- [ ] Type checking passes (if configured)
- [ ] Command help works: `uv run ha-tools history --help`

#### Manual Verification:
- [ ] `uv run ha-tools history sensor.temperature` returns markdown output
- [ ] `uv run ha-tools history sensor.temperature --stats` shows statistics
- [ ] `uv run ha-tools history sensor.temperature --format json` returns valid JSON
- [ ] `uv run ha-tools history sensor.temperature --format csv` returns valid CSV with attribute columns
- [ ] `uv run ha-tools history sensor.temperature --verbose` shows timing info
- [ ] `uv run ha-tools history nonexistent.entity` shows warning and exits 0
- [ ] Database unavailable scenario shows error and exits 4

---

## Testing Strategy

### Unit Tests:
- Statistics computation for numeric states
- Statistics computation for non-numeric states
- CSV output with dynamic attributes
- JSON output structure
- Error handling (invalid format, invalid timeframe, database unavailable)
- Empty result handling

### Integration Tests (future):
- Full command execution with real database
- CLI argument parsing via typer

### Manual Testing Steps:
1. Run `uv run ha-tools history sensor.<your_entity>` with a real entity
2. Verify CSV export opens correctly in spreadsheet application
3. Verify JSON output is valid and parseable
4. Test with entity that has many attributes to verify dynamic columns work

## Performance Considerations

- Uses existing optimized `get_entity_states()` query with index-friendly filtering
- Limit defaults to 100 records to avoid memory issues
- CSV output streams to stdout (no large in-memory strings for unlimited queries)
- Markdown output caps table at 50 rows for readability

## References

- Original research: `thoughts/shared/research/2025-12-14-ha-tools-history-command.md`
- Entities command pattern: `ha_tools/commands/entities.py`
- Database query method: `ha_tools/lib/database.py:198-302`
- Output formatting: `ha_tools/lib/output.py:68-137`
