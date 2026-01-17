"""
Logs command for ha-tools.

Provides runtime log analysis with correlation to entity state changes.
"""

import asyncio
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import typer

from ..config import HaToolsConfig
from ..lib.database import DatabaseManager
from ..lib.output import (
    MarkdownFormatter,
    format_timestamp,
    print_error,
    print_info,
    print_verbose,
    print_verbose_timing,
    print_warning,
)
from ..lib.registry import RegistryManager
from ..lib.rest_api import HomeAssistantAPI
from ..lib.utils import parse_timeframe


def _parse_level_options(level: str | None) -> set[str]:
    """Parse level options string into a set of valid levels."""
    valid_levels = {"error", "warning", "critical", "info", "debug"}

    if not level:
        return {"error", "warning"}  # Default

    options = {opt.strip().lower() for opt in level.split(",")}
    return {opt for opt in options if opt in valid_levels}


def logs_command(
    current: bool = typer.Option(
        False, "--current", "-c", help="Show only current runtime logs"
    ),
    log: str | None = typer.Option(
        None,
        "--log",
        "-l",
        help="Timeframe for log analysis: Nh (hours), Nd (days), Nm (minutes), Nw (weeks)",
    ),
    level: str | None = typer.Option(
        None,
        "--level",
        "-L",
        help="Log levels to include: error, warning, critical, info, debug (comma-separated). Default: error,warning",
    ),
    entity: str | None = typer.Option(
        None, "--entity", "-e", help="Filter logs for specific entity pattern"
    ),
    integration: str | None = typer.Option(
        None, "--integration", "-i", help="Filter logs by integration/component"
    ),
    correlation: bool = typer.Option(
        False, "--correlation", help="Include entity state correlation analysis"
    ),
    format: str | None = typer.Option(
        "markdown", "--format", "-f", help="Output format (markdown, json)"
    ),
) -> None:
    """
    Analyze Home Assistant logs.

    Provides comprehensive log analysis with correlation to entity state changes.
    Uses multiple data sources: API, log files, and database for correlation.

    Examples:
        ha-tools logs --current
        ha-tools logs --log 24h --entity "heizung"
        ha-tools logs --integration "knx" --correlation
    """
    try:
        levels = _parse_level_options(level)
        exit_code = asyncio.run(
            _run_logs_command(
                current,
                log,
                levels,
                entity,
                integration,
                correlation,
                format or "markdown",
            )
        )
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print_error("Log analysis cancelled")
        sys.exit(1)
    except Exception as e:
        print_error(f"Log analysis failed: {e}")
        sys.exit(1)


async def _run_logs_command(
    current: bool,
    log: str | None,
    levels: set[str],
    entity: str | None,
    integration: str | None,
    correlation: bool,
    format: str,
) -> int:
    """Run the logs analysis command."""
    try:
        config = HaToolsConfig.load()
    except Exception as e:
        print_error(f"Configuration error: {e}")
        return 3

    # Parse log timeframe
    log_timeframe = None
    if log:
        log_timeframe = parse_timeframe(log)

    print_info("Analyzing logs...")

    # Initialize database manager - may fail gracefully
    db_manager = DatabaseManager(config.database)
    api_manager = HomeAssistantAPI(config.home_assistant)
    print_verbose("Connecting to Home Assistant API...")

    async with db_manager as db:
        async with api_manager as api:
            print_verbose("Connected to Home Assistant API")
            registry = RegistryManager(config)

            # Check database availability and notify if not connected
            if not db.is_connected():
                print_warning(f"Database unavailable: {db.get_connection_error()}")
                print_info("Using API-only mode (limited functionality)")

            # Load registry for correlation analysis
            if correlation and db.is_connected():
                await registry.load_all_registries(api)

            # Collect logs from different sources
            print_verbose("Collecting logs from sources...")
            start = time.time()
            errors_data = await _collect_errors(
                api,
                db,
                registry,
                current,
                log_timeframe,
                levels,
                entity,
                integration,
                correlation,
            )
            print_verbose_timing("Log collection", (time.time() - start) * 1000)

            # Output results
            await _output_errors(errors_data, format, correlation)

    return 0


async def _collect_errors(
    api: HomeAssistantAPI,
    db: DatabaseManager,
    registry: RegistryManager,
    current: bool,
    log_timeframe: datetime | None,
    levels: set[str],
    entity: str | None,
    integration: str | None,
    correlation: bool,
) -> dict[str, Any]:
    """Collect errors from multiple sources."""
    errors_data: dict[str, list[dict[str, Any]]] = {
        "api_errors": [],
        "log_errors": [],
        "correlations": [],
    }

    # Get current runtime logs - try sources in order of preference
    if current:
        errors_data["api_errors"] = await _fetch_current_logs(
            api, entity, integration, levels, registry.config.ha_config_path
        )

    # Get historical logs from log files
    if log_timeframe:
        log_entries = await _analyze_log_files(
            registry.config.ha_config_path, log_timeframe, levels, entity, integration
        )
        errors_data["log_errors"] = log_entries

    # Perform correlation analysis if requested
    if correlation and (errors_data["api_errors"] or errors_data["log_errors"]):
        correlations = await _perform_correlation_analysis(
            db, registry, errors_data["api_errors"] + errors_data["log_errors"]
        )
        errors_data["correlations"] = correlations

    return errors_data


async def _fetch_current_logs(
    api: HomeAssistantAPI,
    entity: str | None,
    integration: str | None,
    levels: set[str],
    ha_config_path: str,
) -> list[dict[str, Any]]:
    """Fetch current logs from WebSocket, REST API, or log files (in order of preference)."""
    # Try WebSocket first (preferred - matches HA UI)
    print_verbose("Attempting WebSocket for system logs...")
    try:
        ws_logs = await api.get_system_logs_ws(levels)
        if ws_logs:
            print_verbose(f"Got {len(ws_logs)} logs via WebSocket")
            return _filter_errors(ws_logs, entity, integration)
    except Exception as e:
        print_verbose(f"WebSocket failed: {e}")

    # Fall back to REST API
    print_verbose("Trying REST API for logs...")
    try:
        api_logs = await api.get_logs(levels)
        if api_logs:
            return _filter_errors(api_logs, entity, integration)
    except Exception as e:
        print_warning(f"Could not fetch API logs: {e}")

    # Final fallback: read log file for recent logs
    print_verbose("API returned no logs, checking log file...")
    recent_timeframe = datetime.now() - timedelta(hours=1)
    return await _analyze_log_files(
        ha_config_path, recent_timeframe, levels, entity, integration
    )


def _filter_errors(
    errors: list[dict[str, Any]], entity: str | None, integration: str | None
) -> list[dict[str, Any]]:
    """Filter errors based on entity and integration criteria."""
    if not errors:
        return []

    filtered = []

    for error in errors:
        # Entity filter
        if entity:
            error_text = str(error).lower()
            entity_pattern = entity.lower().replace("*", "")
            if entity_pattern not in error_text:
                continue

        # Integration filter
        if integration:
            error_text = str(error).lower()
            integration_pattern = integration.lower()
            if integration_pattern not in error_text:
                continue

        filtered.append(error)

    return filtered


async def _analyze_log_files(
    ha_config_path: str,
    since: datetime,
    levels: set[str],
    entity: str | None,
    integration: str | None,
) -> list[dict[str, Any]]:
    """Analyze Home Assistant log files for log entries."""
    log_entries = []

    # Common log file locations
    log_paths = [
        Path(ha_config_path) / "home-assistant.log",
        Path(ha_config_path) / "config" / "home-assistant.log",
        Path("/var/log/home-assistant.log"),
    ]

    # Also check OS-specific log directories
    import os

    if os.name == "posix":
        log_paths.extend(
            [
                Path("/var/log/home-assistant/home-assistant.log"),
                Path("/var/lib/home-assistant/home-assistant.log"),
            ]
        )

    for log_path in log_paths:
        if not log_path.exists():
            continue

        try:
            print_verbose(f"Analyzing log file: {log_path}")
            file_entries = await _parse_log_file(
                log_path, since, levels, entity, integration
            )
            log_entries.extend(file_entries)
            print_verbose(f"Found {len(file_entries)} log entries in {log_path}")
        except Exception as e:
            print_warning(f"Could not parse log file {log_path}: {e}")

    # Sort by timestamp
    log_entries.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

    return log_entries


async def _parse_log_file(
    log_path: Path,
    since: datetime,
    levels: set[str],
    entity: str | None,
    integration: str | None,
) -> list[dict[str, Any]]:
    """Parse a single log file for log entries matching requested levels."""
    entries: list[dict[str, Any]] = []

    try:
        with open(log_path, encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except Exception:
        return []

    # Build regex pattern for requested levels
    upper_levels = {lvl.upper() for lvl in levels}
    level_pattern = "|".join(upper_levels)

    # Additional patterns for error-like entries (only when "error" level is requested)
    extra_patterns: list[str] = []
    if "error" in levels:
        extra_patterns = ["Exception", "Failed", "Error in", "Traceback"]

    current_entry: dict[str, Any] | None = None

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Extract timestamp (common formats)
        timestamp_match = re.search(r"(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2})", line)
        timestamp = None
        if timestamp_match:
            try:
                timestamp_str = timestamp_match.group(1).replace(" ", "T")
                timestamp = datetime.fromisoformat(timestamp_str)
            except ValueError:
                pass

        # Skip old entries
        if timestamp and timestamp < since:
            continue

        # Check if this line matches a requested level
        level_match = (
            re.search(rf"\b({level_pattern})\b", line) if level_pattern else None
        )
        is_extra_pattern = any(pattern in line for pattern in extra_patterns)

        if level_match or is_extra_pattern:
            # Start a new entry
            if current_entry:
                entries.append(current_entry)

            matched_level = level_match.group(1) if level_match else "ERROR"
            current_entry = {
                "timestamp": timestamp or datetime.now(),
                "level": matched_level,
                "message": line,
                "source": str(log_path),
                "context": [],
            }
        elif current_entry:
            # Continue current entry context
            current_entry["context"].append(line)

            # End entry if we hit a new log line with timestamp
            if timestamp and not level_match and not is_extra_pattern:
                entries.append(current_entry)
                current_entry = None

    # Add the last entry if we're still in one
    if current_entry:
        entries.append(current_entry)

    # Apply filters
    if entity or integration:
        entries = _filter_errors(entries, entity, integration)

    return entries


async def _perform_correlation_analysis(
    db: DatabaseManager, registry: RegistryManager, errors: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Correlate errors with entity state changes."""
    correlations: list[dict[str, Any]] = []

    if not errors:
        return correlations

    print_info("Performing correlation analysis...")

    for error in errors[:20]:  # Limit to avoid too many DB queries
        error_time = error.get("timestamp")
        if not error_time:
            continue

        # Look for entity references in error message
        error_text = error.get("message", "")
        entity_references = _extract_entity_references(error_text)

        if not entity_references:
            continue

        # Check state changes around error time
        for entity_id in entity_references:
            print_verbose(f"Correlating error with entity: {entity_id}")
            try:
                # Get state changes 5 minutes before and after error
                start_time = error_time - timedelta(minutes=5)
                end_time = error_time + timedelta(minutes=5)

                state_changes_result = await db.get_entity_states(
                    entity_id, start_time, end_time, 10
                )
                # Handle both tuple (with stats) and list return types
                state_changes: list[dict[str, Any]] = (
                    state_changes_result[0]
                    if isinstance(state_changes_result, tuple)
                    else state_changes_result
                )

                if len(state_changes) > 1:  # More than just the current state
                    correlations.append(
                        {
                            "error_timestamp": error_time,
                            "error_message": error_text[:100] + "...",
                            "entity_id": entity_id,
                            "entity_name": await registry.get_entity_name(entity_id),
                            "state_changes": state_changes,
                            "correlation_strength": _calculate_correlation_strength(
                                error_time, state_changes
                            ),
                        }
                    )
            except Exception:
                continue

    # Sort by correlation strength
    correlations.sort(key=lambda x: x.get("correlation_strength", 0), reverse=True)

    return correlations[:10]  # Return top 10 correlations


def _extract_entity_references(text: str) -> list[str]:
    """Extract entity IDs from error text."""
    # Common patterns for entity IDs
    patterns = [
        r"[a-zA-Z0-9_]+\.[a-zA-Z0-9_]+",  # domain.entity_id
        r"entity\s+([a-zA-Z0-9_]+\.[a-zA-Z0-9_]+)",  # entity domain.entity_id
        r"sensor\.[a-zA-Z0-9_]+",  # sensor.*
        r"switch\.[a-zA-Z0-9_]+",  # switch.*
        r"light\.[a-zA-Z0-9_]+",  # light.*
    ]

    entities = []
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        entities.extend(matches)

    # Filter for valid-looking entity IDs
    valid_entities = []
    for entity in entities:
        if "." in entity and len(entity) > 3:
            valid_entities.append(entity.lower())

    return list(set(valid_entities))  # Remove duplicates


def _calculate_correlation_strength(
    error_time: datetime, state_changes: list[dict[str, Any]]
) -> float:
    """Calculate correlation strength between error and state changes."""
    if not state_changes:
        return 0.0

    strength = 0.0
    for change in state_changes:
        change_time = change.get("last_changed")
        if not change_time:
            continue

        try:
            if isinstance(change_time, str):
                change_time = datetime.fromisoformat(change_time.replace("Z", "+00:00"))
        except ValueError:
            continue

        # Calculate time difference
        time_diff = abs((error_time - change_time).total_seconds())

        # Stronger correlation for closer timing
        if time_diff < 60:  # Within 1 minute
            strength += 1.0
        elif time_diff < 300:  # Within 5 minutes
            strength += 0.5
        elif time_diff < 600:  # Within 10 minutes
            strength += 0.2

    return min(strength, 3.0)  # Cap at 3.0


async def _output_errors(
    errors_data: dict[str, Any], format: str, correlation: bool
) -> None:
    """Output errors analysis in specified format."""
    if format == "json":
        from ..lib.output import output_json

        print(output_json(errors_data))
    else:  # markdown
        _output_markdown_format(errors_data, correlation)


def _output_markdown_format(errors_data: dict[str, Any], correlation: bool) -> None:
    """Output errors analysis in markdown format."""
    formatter = MarkdownFormatter(title="Error Analysis Results")

    # Summary
    total_errors = len(errors_data["api_errors"]) + len(errors_data["log_errors"])

    formatter.add_section(
        "📊 Summary",
        f"Total errors found: **{total_errors}**\n"
        f"- Current runtime errors: {len(errors_data['api_errors'])}\n"
        f"- Log file errors: {len(errors_data['log_errors'])}\n"
        f"- Correlations found: {len(errors_data['correlations'])}",
    )

    # Current runtime errors
    if errors_data["api_errors"]:
        formatter.add_section("🚨 Current Runtime Errors", "")
        for i, error in enumerate(errors_data["api_errors"][:10], 1):
            timestamp = format_timestamp(error.get("timestamp"))
            source = error.get("source", "Unknown")
            source_location = error.get(
                "source_location", ""
            )  # File:line from WebSocket
            message = error.get("message", "No message")
            context = error.get("context", [])
            context_str = "\n".join(context[:5]) if context else ""

            # Build error content
            content_parts = [f"**Logger:** `{source}`"]
            if source_location:
                content_parts.append(f"**Source:** `{source_location}`")
            content_parts.append(f"**Message:** {message}")

            # Add occurrence info from WebSocket (only shown when count > 1)
            count = error.get("count", 1)
            if count > 1:
                content_parts.append(f"**Occurrences:** {count} times")
                first_occurred = error.get("first_occurred")
                if first_occurred:
                    content_parts.append(
                        f"**First occurred:** {format_timestamp(first_occurred)}"
                    )

            if context_str:
                content_parts.append(f"**Context:**\n```\n{context_str}\n```")

            formatter.add_section(
                f"Error {i} - {timestamp}",
                "\n".join(content_parts),
            )
        if len(errors_data["api_errors"]) > 10:
            formatter.add_section(
                "", f"... and {len(errors_data['api_errors']) - 10} more errors"
            )

    # Log file errors
    if errors_data["log_errors"]:
        formatter.add_section("📋 Log File Errors", "")
        for i, error in enumerate(errors_data["log_errors"][:15], 1):
            timestamp = format_timestamp(error.get("timestamp"))
            source = error.get("source", "Unknown")
            message = error.get("message", "No message")[:100]
            formatter.add_section(
                f"Error {i} - {timestamp}",
                f"**Source:** {source}\n"
                f"**Message:** {message}\n"
                f"**Context:** {' | '.join(error.get('context', [])[:3])}",
            )
        if len(errors_data["log_errors"]) > 15:
            formatter.add_section(
                "", f"... and {len(errors_data['log_errors']) - 15} more errors"
            )

    # Correlation analysis
    if correlation and errors_data["correlations"]:
        formatter.add_section("🔗 Correlation Analysis", "")
        for corr in errors_data["correlations"]:
            strength = corr.get("correlation_strength", 0)
            strength_emoji = (
                "🔴" if strength > 2.0 else "🟡" if strength > 1.0 else "🟢"
            )

            formatter.add_section(
                f"{strength_emoji} Entity: {corr.get('entity_name', 'Unknown')}",
                f"**Error Time:** {format_timestamp(corr['error_timestamp'])}\n"
                f"**Entity ID:** `{corr['entity_id']}`\n"
                f"**Correlation Strength:** {strength:.1f}/3.0\n"
                f"**Error:** {corr['error_message']}\n"
                f"**State Changes:** {len(corr['state_changes'])} states around error time",
            )

    if not any([errors_data["api_errors"], errors_data["log_errors"]]):
        formatter.add_section(
            "✅ No Errors Found",
            "Great! No errors detected in the specified timeframe.",
        )

    print(formatter.format())
