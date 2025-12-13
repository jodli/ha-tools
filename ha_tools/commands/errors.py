"""
Errors command for ha-tools.

Provides runtime error diagnostics with correlation to entity state changes.
"""

import asyncio
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, List
import re

import typer
from rich.console import Console

from ..config import HaToolsConfig
from ..lib.database import DatabaseManager
from ..lib.rest_api import HomeAssistantAPI
from ..lib.registry import RegistryManager
from ..lib.output import MarkdownFormatter, print_error, print_info, format_timestamp, print_verbose, print_verbose_timing
from ..lib.utils import parse_timeframe

console = Console()


def errors_command(
    current: bool = typer.Option(
        False,
        "--current",
        "-c",
        help="Show only current runtime errors"
    ),
    log: Optional[str] = typer.Option(
        None,
        "--log",
        "-l",
        help="Timeframe for log analysis (e.g., 24h, 7d)"
    ),
    entity: Optional[str] = typer.Option(
        None,
        "--entity",
        "-e",
        help="Filter errors for specific entity pattern"
    ),
    integration: Optional[str] = typer.Option(
        None,
        "--integration",
        "-i",
        help="Filter errors by integration/component"
    ),
    correlation: bool = typer.Option(
        False,
        "--correlation",
        help="Include entity state correlation analysis"
    ),
    format: Optional[str] = typer.Option(
        "markdown",
        "--format",
        "-f",
        help="Output format (markdown, json)"
    ),
) -> None:
    """
    Analyze Home Assistant runtime errors.

    Provides comprehensive error analysis with correlation to entity state changes.
    Uses multiple data sources: API, log files, and database for correlation.

    Examples:
        ha-tools errors --current
        ha-tools errors --log 24h --entity "heizung*"
        ha-tools errors --integration "knx" --correlation
    """
    try:
        exit_code = asyncio.run(_run_errors_command(
            current, log, entity, integration, correlation, format
        ))
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print_error("Error analysis cancelled")
        sys.exit(1)
    except Exception as e:
        print_error(f"Error analysis failed: {e}")
        sys.exit(1)


async def _run_errors_command(current: bool, log: Optional[str], entity: Optional[str],
                            integration: Optional[str], correlation: bool,
                            format: str) -> int:
    """Run the errors analysis command."""
    try:
        config = HaToolsConfig.load()
    except Exception as e:
        print_error(f"Configuration error: {e}")
        return 3

    # Parse log timeframe
    log_timeframe = None
    if log:
        log_timeframe = parse_timeframe(log)

    print_info("Analyzing errors...")

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
                print_info(f"⚠️  Database unavailable: {db.get_connection_error()}")
                print_info("ℹ️  Using API-only mode (limited functionality)")

            # Load registry for correlation analysis
            if correlation and db.is_connected():
                await registry.load_all_registries(api)

            # Collect errors from different sources
            print_verbose("Collecting errors from sources...")
            start = time.time()
            errors_data = await _collect_errors(
                api, db, registry, current, log_timeframe, entity, integration, correlation
            )
            print_verbose_timing("Error collection", (time.time() - start) * 1000)

            # Output results
            await _output_errors(errors_data, format, correlation)

    return 0


async def _collect_errors(api: HomeAssistantAPI, db: DatabaseManager,
                         registry: RegistryManager, current: bool,
                         log_timeframe: Optional[datetime], entity: Optional[str],
                         integration: Optional[str], correlation: bool) -> dict:
    """Collect errors from multiple sources."""
    from datetime import timedelta

    errors_data = {
        "api_errors": [],
        "log_errors": [],
        "correlations": []
    }

    # Get current runtime errors from API
    if current:
        try:
            api_errors = await api.get_errors()
            errors_data["api_errors"] = _filter_errors(api_errors, entity, integration)
        except Exception as e:
            print_info(f"Could not fetch API errors: {e}")

        # If API returned no errors, fall back to reading log file for recent errors
        if not errors_data["api_errors"]:
            print_info("API returned no errors, checking log file...")
            # Look at last 1 hour for "current" errors
            recent_timeframe = datetime.now() - timedelta(hours=1)
            log_errors = await _analyze_log_files(
                registry.config.ha_config_path, recent_timeframe, entity, integration
            )
            # Put these in api_errors since they're "current" errors
            errors_data["api_errors"] = log_errors

    # Get historical errors from log files
    if log_timeframe:
        log_errors = await _analyze_log_files(
            registry.config.ha_config_path, log_timeframe, entity, integration
        )
        errors_data["log_errors"] = log_errors

    # Perform correlation analysis if requested
    if correlation and (errors_data["api_errors"] or errors_data["log_errors"]):
        correlations = await _perform_correlation_analysis(
            db, registry, errors_data["api_errors"] + errors_data["log_errors"]
        )
        errors_data["correlations"] = correlations

    return errors_data


def _filter_errors(errors: List[dict], entity: Optional[str], integration: Optional[str]) -> List[dict]:
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


async def _analyze_log_files(ha_config_path: str, since: datetime,
                           entity: Optional[str], integration: Optional[str]) -> List[dict]:
    """Analyze Home Assistant log files for errors."""
    log_errors = []

    # Common log file locations
    log_paths = [
        Path(ha_config_path) / "home-assistant.log",
        Path(ha_config_path) / "config" / "home-assistant.log",
        Path("/var/log/home-assistant.log"),
    ]

    # Also check OS-specific log directories
    import os
    if os.name == "posix":
        log_paths.extend([
            Path("/var/log/home-assistant/home-assistant.log"),
            Path("/var/lib/home-assistant/home-assistant.log"),
        ])

    for log_path in log_paths:
        if not log_path.exists():
            continue

        try:
            print_verbose(f"Analyzing log file: {log_path}")
            file_errors = await _parse_log_file(log_path, since, entity, integration)
            log_errors.extend(file_errors)
            print_verbose(f"Found {len(file_errors)} errors in {log_path}")
        except Exception as e:
            print_info(f"Could not parse log file {log_path}: {e}")

    # Sort by timestamp
    log_errors.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

    return log_errors


async def _parse_log_file(log_path: Path, since: datetime,
                         entity: Optional[str], integration: Optional[str]) -> List[dict]:
    """Parse a single log file for errors."""
    errors = []

    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except Exception:
        return []

    current_error = None
    error_patterns = [
        r"ERROR",
        r"Exception",
        r"Failed",
        r"Error in",
        r"Traceback",
    ]

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

        # Check if this line contains an error
        is_error_line = any(pattern in line for pattern in error_patterns)

        if is_error_line:
            # Start a new error entry
            if current_error:
                errors.append(current_error)

            current_error = {
                "timestamp": timestamp or datetime.now(),
                "message": line,
                "source": str(log_path),
                "context": []
            }
        elif current_error:
            # Continue current error context
            current_error["context"].append(line)

            # End error if we hit a new log entry with timestamp
            if timestamp and not any(pattern in line for pattern in error_patterns):
                errors.append(current_error)
                current_error = None

    # Add the last error if we're still in one
    if current_error:
        errors.append(current_error)

    # Apply filters
    if entity or integration:
        errors = _filter_errors(errors, entity, integration)

    return errors


async def _perform_correlation_analysis(db: DatabaseManager, registry: RegistryManager,
                                     errors: List[dict]) -> List[dict]:
    """Correlate errors with entity state changes."""
    correlations = []

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

                state_changes = await db.get_entity_states(
                    entity_id, start_time, end_time, 10
                )

                if len(state_changes) > 1:  # More than just the current state
                    correlations.append({
                        "error_timestamp": error_time,
                        "error_message": error_text[:100] + "...",
                        "entity_id": entity_id,
                        "entity_name": await registry.get_entity_name(entity_id),
                        "state_changes": state_changes,
                        "correlation_strength": _calculate_correlation_strength(
                            error_time, state_changes
                        )
                    })
            except Exception:
                continue

    # Sort by correlation strength
    correlations.sort(key=lambda x: x.get("correlation_strength", 0), reverse=True)

    return correlations[:10]  # Return top 10 correlations


def _extract_entity_references(text: str) -> List[str]:
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


def _calculate_correlation_strength(error_time: datetime, state_changes: List[dict]) -> float:
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


async def _output_errors(errors_data: dict, format: str, correlation: bool) -> None:
    """Output errors analysis in specified format."""
    if format == "json":
        import json
        print(json.dumps(errors_data, indent=2, default=str))
    else:  # markdown
        _output_markdown_format(errors_data, correlation)


def _output_markdown_format(errors_data: dict, correlation: bool) -> None:
    """Output errors analysis in markdown format."""
    formatter = MarkdownFormatter(title="Error Analysis Results")

    # Summary
    total_errors = len(errors_data["api_errors"]) + len(errors_data["log_errors"])

    formatter.add_section(
        "📊 Summary",
        f"Total errors found: **{total_errors}**\n"
        f"- Current runtime errors: {len(errors_data['api_errors'])}\n"
        f"- Log file errors: {len(errors_data['log_errors'])}\n"
        f"- Correlations found: {len(errors_data['correlations'])}"
    )

    # Current runtime errors
    if errors_data["api_errors"]:
        formatter.add_section("🚨 Current Runtime Errors", "")
        for i, error in enumerate(errors_data["api_errors"][:10], 1):
            timestamp = format_timestamp(error.get("timestamp"))
            source = error.get("source", "Unknown")
            message = error.get("message", "No message")
            context = error.get("context", [])
            context_str = "\n".join(context[:5]) if context else ""

            formatter.add_section(
                f"Error {i} - {timestamp}",
                f"**Source:** `{source}`\n"
                f"**Message:** {message}\n"
                + (f"**Context:**\n```\n{context_str}\n```" if context_str else "")
            )
        if len(errors_data["api_errors"]) > 10:
            formatter.add_section("", f"... and {len(errors_data['api_errors']) - 10} more errors")

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
                f"**Context:** {' | '.join(error.get('context', [])[:3])}"
            )
        if len(errors_data["log_errors"]) > 15:
            formatter.add_section("", f"... and {len(errors_data['log_errors']) - 15} more errors")

    # Correlation analysis
    if correlation and errors_data["correlations"]:
        formatter.add_section("🔗 Correlation Analysis", "")
        for corr in errors_data["correlations"]:
            strength = corr.get("correlation_strength", 0)
            strength_emoji = "🔴" if strength > 2.0 else "🟡" if strength > 1.0 else "🟢"

            formatter.add_section(
                f"{strength_emoji} Entity: {corr.get('entity_name', 'Unknown')}",
                f"**Error Time:** {format_timestamp(corr['error_timestamp'])}\n"
                f"**Entity ID:** `{corr['entity_id']}`\n"
                f"**Correlation Strength:** {strength:.1f}/3.0\n"
                f"**Error:** {corr['error_message']}\n"
                f"**State Changes:** {len(corr['state_changes'])} states around error time"
            )

    if not any([errors_data["api_errors"], errors_data["log_errors"]]):
        formatter.add_section("✅ No Errors Found", "Great! No errors detected in the specified timeframe.")

    print(formatter.format())