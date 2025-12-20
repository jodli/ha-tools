"""
History command for ha-tools.

Provides detailed state history analysis for a single entity.
"""

import asyncio
import csv
import io
import json
import sys
from typing import Any

import typer

from ..config import HaToolsConfig
from ..lib.database import DatabaseManager
from ..lib.output import (
    MarkdownFormatter,
    format_timestamp,
    is_verbose,
    print_error,
    print_verbose,
    print_verbose_timing,
    print_warning,
)
from ..lib.utils import parse_timeframe

# Default Home Assistant attributes to exclude from CSV output
# These are system attributes that rarely change or contain useful data for analysis
HA_DEFAULT_ATTRIBUTES = {
    "friendly_name",
    "icon",
    "entity_picture",
    "assumed_state",
    "unit_of_measurement",
    "attribution",
    "device_class",
    "supported_features",
}


def history_command(
    entity_id: str = typer.Argument(
        ..., help="Entity ID to analyze history for (e.g., sensor.temperature)"
    ),
    timeframe: str = typer.Option(
        "24h",
        "--timeframe",
        "-t",
        help="History timeframe: Nm (minutes), Nh (hours), Nd (days), Nw (weeks)",
    ),
    limit: int = typer.Option(
        100,
        "--limit",
        "-l",
        help="Maximum number of records to return (-1 for no limit)",
    ),
    stats: bool = typer.Option(
        False,
        "--stats",
        "-s",
        help="Include statistics (min/max/avg for numeric, state counts for non-numeric)",
    ),
    format: str = typer.Option(
        "markdown", "--format", "-f", help="Output format (markdown, json, csv)"
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
        exit_code = asyncio.run(
            _run_history_command(entity_id, timeframe, limit, stats, format)
        )
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print_error("History analysis cancelled")
        sys.exit(1)
    except Exception as e:
        print_error(f"History analysis failed: {e}")
        sys.exit(1)


async def _run_history_command(
    entity_id: str, timeframe: str, limit: int, stats: bool, format: str
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
        result = await db.get_entity_states(
            entity_id=entity_id,
            start_time=start_time,
            limit=query_limit,
            include_stats=is_verbose(),
        )

        states: list[dict[str, Any]]
        if is_verbose() and isinstance(result, tuple):
            states, query_stats = result
            print_verbose_timing("History query", query_stats.get("query_time_ms", 0))
            print_verbose(
                f"Total records for entity: {query_stats.get('total_records', 0):,}"
            )
            print_verbose(
                f"Records in timeframe: {query_stats.get('filtered_count', 0):,}"
            )
        elif isinstance(result, list):
            states = result
        else:
            states = result[0]  # Extract list from tuple

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


def _compute_statistics(states: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute statistics from state records.

    For numeric states: min, max, avg
    For non-numeric states: state change counts
    """
    numeric_values = []
    state_counts: dict[str, int] = {}

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
    states: list[dict[str, Any]],
    format: str,
    entity_id: str,
    timeframe: str,
    stats_data: dict[str, Any] | None,
) -> None:
    """Output results in the specified format."""
    if format == "json":
        _output_json_format(states, entity_id, timeframe, stats_data)
    elif format == "csv":
        _output_csv_format(states)
    else:  # markdown (default)
        _output_markdown_format(states, entity_id, timeframe, stats_data)


def _output_markdown_format(
    states: list[dict[str, Any]],
    entity_id: str,
    timeframe: str,
    stats_data: dict[str, Any] | None,
) -> None:
    """Output states in markdown format."""
    formatter = MarkdownFormatter(title=f"History: {entity_id}")

    # Summary section
    summary_lines = [
        f"Found **{len(states)}** state changes in the last **{timeframe}**"
    ]
    formatter.add_section("Summary", "\n".join(summary_lines))

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
                stats_data["state_counts"].items(), key=lambda x: x[1], reverse=True
            ):
                pct = (count / stats_data["total_records"]) * 100
                stats_lines.append(f"- `{state_val}`: {count} ({pct:.1f}%)")

        formatter.add_section("Statistics", "\n".join(stats_lines))

    # State history table
    headers = ["Timestamp", "State", "Changed"]
    rows = []
    for state in states[:50]:  # Limit table rows for readability
        rows.append(
            [
                format_timestamp(state.get("last_updated")),
                state.get("state", "N/A"),
                format_timestamp(state.get("last_changed")),
            ]
        )

    formatter.add_table(headers, rows, "State History")

    if len(states) > 50:
        formatter.add_section(
            "",
            f"*... and {len(states) - 50} more records (use --format csv for full data)*",
        )

    print(formatter.format())


def _output_json_format(
    states: list[dict[str, Any]],
    entity_id: str,
    timeframe: str,
    stats_data: dict[str, Any] | None,
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

    from ..lib.output import output_json

    print(output_json(output))


def _output_csv_format(states: list[dict[str, Any]]) -> None:
    """Output states in CSV format with dynamic attribute columns."""
    if not states:
        return

    # Collect all attribute keys from all states
    all_attr_keys: set[str] = set()
    parsed_attrs: list[dict[str, Any]] = []

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
        # Exclude default HA attributes - only include entity-specific attributes
        all_attr_keys.update(k for k in attrs.keys() if k not in HA_DEFAULT_ATTRIBUTES)

    # Sort attribute keys for consistent column order
    attr_keys = sorted(all_attr_keys)

    # Build CSV
    output = io.StringIO()
    headers = ["timestamp", "state", "last_changed"] + [f"attr_{k}" for k in attr_keys]

    writer = csv.writer(output)
    writer.writerow(headers)

    for state, attrs in zip(states, parsed_attrs, strict=False):
        row = [
            state.get("last_updated", ""),
            state.get("state", ""),
            state.get("last_changed", ""),
        ]
        # Add attribute values in order
        for key in attr_keys:
            value = attrs.get(key, "")
            # Convert complex types to JSON strings
            if isinstance(value, dict | list):
                value = json.dumps(value)
            row.append(value)
        writer.writerow(row)

    print(output.getvalue(), end="")
