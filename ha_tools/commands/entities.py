"""
Entities command for ha-tools.

Provides entity discovery and analysis with multi-source data aggregation.
"""

import asyncio
import sys
import time
from datetime import datetime
from typing import Optional, List

import typer
from rich.console import Console

from ..config import HaToolsConfig
from ..lib.database import DatabaseManager
from ..lib.rest_api import HomeAssistantAPI
from ..lib.registry import RegistryManager
from ..lib.output import MarkdownFormatter, print_error, print_info, format_timestamp, print_verbose, print_verbose_timing
from ..lib.utils import parse_timeframe

console = Console()


def entities_command(
    search: Optional[str] = typer.Option(
        None,
        "--search",
        "-s",
        help="Search pattern (supports wildcards like temp_*)"
    ),
    include: Optional[str] = typer.Option(
        None,
        "--include",
        "-i",
        help="Include additional data (state, history, relations)"
    ),
    history: Optional[str] = typer.Option(
        None,
        "--history",
        "-h",
        help="History timeframe (e.g., 24h, 7d, 1m) - requires database access"
    ),
    limit: Optional[int] = typer.Option(
        100,
        "--limit",
        "-l",
        help="Maximum number of entities to return"
    ),
    format: Optional[str] = typer.Option(
        "markdown",
        "--format",
        "-f",
        help="Output format (markdown, json, table)"
    ),
) -> None:
    """
    Discover and analyze Home Assistant entities.

    Provides fast entity discovery with optional state, history, and relationship data.
    Uses database access for 10-15x faster history queries.

    Examples:
        ha-tools entities
        ha-tools entities --search "temp_*" --include history --history 24h
        ha-tools entities --include state,relations
        ha-tools entities --search "sensor.*" --format json
    """
    try:
        exit_code = asyncio.run(_run_entities_command(search, include, history, limit, format))
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print_error("Entity discovery cancelled")
        sys.exit(1)
    except Exception as e:
        print_error(f"Entity discovery failed: {e}")
        sys.exit(1)


async def _run_entities_command(search: Optional[str], include: Optional[str],
                              history: Optional[str], limit: Optional[int],
                              format: str) -> int:
    """Run the entities discovery command."""
    try:
        config = HaToolsConfig.load()
    except Exception as e:
        print_error(f"Configuration error: {e}")
        return 3

    # Parse include options
    include_options = _parse_include_options(include)

    # Parse history timeframe
    history_timeframe = None
    if history:
        history_timeframe = parse_timeframe(history)
        # Auto-include history when --history is specified
        include_options = include_options | {"history"}

    print_info("Discovering entities...")

    async with DatabaseManager(config.database) as db:
        async with HomeAssistantAPI(config.home_assistant) as api:
            registry = RegistryManager(config)

            # Load registry data
            print_verbose("Loading entity registries...")
            start = time.time()
            await registry.load_all_registries(api)
            print_verbose_timing("Registry load", (time.time() - start) * 1000)

            # Get entities
            print_verbose("Discovering entities...")
            start = time.time()
            entities_data = await _get_entities(
                registry, db, api, search, include_options, history_timeframe, limit
            )
            print_verbose_timing("Entity discovery", (time.time() - start) * 1000)

            # Format and output results
            await _output_results(entities_data, format, include_options)

    return 0


def _parse_include_options(include: Optional[str]) -> set[str]:
    """Parse include options string."""
    if not include:
        return set()

    options = set(opt.strip().lower() for opt in include.split(","))
    valid_options = {"state", "history", "relations", "metadata"}

    # Filter for valid options
    return {opt for opt in options if opt in valid_options}


async def _get_entities(registry: RegistryManager, db: DatabaseManager,
                       api: HomeAssistantAPI, search: Optional[str],
                       include_options: set[str], history_timeframe: Optional[datetime],
                       limit: Optional[int]) -> List[dict]:
    """Get entities data based on search criteria."""
    entities_data = []

    # Get entities from registry
    if search:
        # Search in registry
        registry_entities = registry.search_entities(search)
    else:
        # Get all entities
        registry_entities = registry._entity_registry or []

    # Apply limit
    if limit:
        registry_entities = registry_entities[:limit]

    print_info(f"Processing {len(registry_entities)} entities...")

    # Build basic entity data first
    for entity in registry_entities:
        entity_id = entity["entity_id"]
        entity_data = {
            "entity_id": entity_id,
            "friendly_name": entity.get("friendly_name"),
            "domain": entity_id.split(".")[0],
            "device_class": entity.get("device_class"),
            "unit_of_measurement": entity.get("unit_of_measurement"),
            "area_id": entity.get("area_id"),
            "device_id": entity.get("device_id"),
            "disabled_by": entity.get("disabled_by"),
            "hidden_by": entity.get("hidden_by"),
        }
        entities_data.append(entity_data)

    # If we need state data, fetch it concurrently
    if "state" in include_options and entities_data:
        print_verbose(f"Fetching state for {len(entities_data)} entities...")
        state_start = time.time()

        async def get_entity_state(entity_data):
            try:
                state = await api.get_entity_state(entity_data["entity_id"])
                if state:
                    entity_data["current_state"] = state.get("state")
                    entity_data["last_changed"] = state.get("last_changed")
                    entity_data["last_updated"] = state.get("last_updated")
                    entity_data["attributes"] = state.get("attributes", {})
            except Exception:
                pass  # Skip state if unavailable
            return entity_data

        # Use semaphore to limit concurrent requests (avoid overwhelming Home Assistant)
        semaphore = asyncio.Semaphore(10)  # Limit to 10 concurrent requests

        async def get_with_semaphore(entity_data):
            async with semaphore:
                return await get_entity_state(entity_data)

        # Process all entities concurrently
        tasks = [get_with_semaphore(entity) for entity in entities_data]
        entities_data = await asyncio.gather(*tasks)
        print_verbose_timing("State fetching", (time.time() - state_start) * 1000)

    # Handle history and relations (these can remain sequential as they're less common)
    if "history" in include_options and history_timeframe:
        print_verbose(f"Querying history for {len(entities_data)} entities...")

    for entity_data in entities_data:
        # History fetching (if needed)
        if "history" in include_options and history_timeframe:
            try:
                history_records = await db.get_entity_states(
                    entity_data["entity_id"], history_timeframe, None, 10
                )
                entity_data["history"] = history_records
                entity_data["history_count"] = len(history_records)
            except Exception as e:
                # Log the error but continue processing other entities
                entity_data["history"] = []
                entity_data["history_count"] = 0
                entity_data["history_error"] = str(e)

        # Relations (if needed)
        if "relations" in include_options:
            relations = {}
            if entity_data.get("area_id"):
                # get_area_name might be async in some implementations
                area_name = registry.get_area_name(entity_data["area_id"])
                if hasattr(area_name, '__await__'):
                    area_name = await area_name
                relations["area"] = {
                    "id": entity_data["area_id"],
                    "name": area_name
                }

            if entity_data.get("device_id"):
                device_info = registry.get_device_metadata(entity_data["device_id"])
                # Handle case where get_device_metadata might be async (from mocks)
                if hasattr(device_info, '__await__'):
                    device_info = await device_info
                relations["device"] = {
                    "id": entity_data["device_id"],
                    "name": device_info.get("name", "Unknown"),
                    "manufacturer": device_info.get("manufacturer"),
                    "model": device_info.get("model"),
                }
            entity_data["relations"] = relations

        if "metadata" in include_options:
            # Find the original entity data
            for entity in registry_entities:
                if entity["entity_id"] == entity_data["entity_id"]:
                    entity_data["full_metadata"] = entity
                    break

    return entities_data


async def _output_results(entities_data: List[dict], format: str,
                         include_options: set[str]) -> None:
    """Output entities data in specified format."""
    if format == "json":
        import json
        print(json.dumps(entities_data, indent=2, default=str))
    elif format == "table":
        _output_table_format(entities_data, include_options)
    else:  # markdown (default)
        _output_markdown_format(entities_data, include_options)


def _output_table_format(entities_data: List[dict], include_options: set[str]) -> None:
    """Output entities in table format."""
    if not entities_data:
        print("No entities found.")
        return

    # Prepare headers
    headers = ["Entity ID", "Friendly Name", "Domain", "State"]
    if "history" in include_options:
        headers.append("History Count")

    # Prepare rows
    rows = []
    for entity in entities_data:
        row = [
            entity["entity_id"],
            entity["friendly_name"] or "N/A",
            entity["domain"],
            entity.get("current_state", "N/A"),
        ]
        if "history" in include_options:
            row.append(str(entity.get("history_count", 0)))
        rows.append(row)

    # Use rich table for formatting
    from rich.console import Console
    from rich.table import Table

    console = Console()
    table = Table(title="Home Assistant Entities")
    for header in headers:
        table.add_column(header)

    for row in rows:
        table.add_row(*row)

    console.print(table)


def _output_markdown_format(entities_data: List[dict], include_options: set[str]) -> None:
    """Output entities in markdown format."""
    formatter = MarkdownFormatter(title="Entity Discovery Results")

    if not entities_data:
        formatter.add_section("No Entities Found", "No entities matched your search criteria.")
        print(formatter.format())
        return

    # Summary
    formatter.add_section(
        "📊 Summary",
        f"Found **{len(entities_data)}** entities"
        f"{' with history data' if 'history' in include_options else ''}"
        f"{' with current state' if 'state' in include_options else ''}"
        f"{' with relations' if 'relations' in include_options else ''}"
    )

    # Entity table
    headers = ["Entity ID", "Friendly Name", "Domain", "Device Class", "Unit"]
    if "state" in include_options:
        headers.append("Current State")
    if "history" in include_options:
        headers.append("History Count")

    rows = []
    for entity in entities_data:
        row = [
            entity["entity_id"],
            entity["friendly_name"] or "N/A",
            entity["domain"],
            entity.get("device_class") or "N/A",
            entity.get("unit_of_measurement") or "N/A",
        ]
        if "state" in include_options:
            row.append(entity.get("current_state", "N/A"))
        if "history" in include_options:
            row.append(str(entity.get("history_count", 0)))
        rows.append(row)

    formatter.add_table(headers, rows, "Entity Overview")

    # Detailed sections if requested
    if include_options:
        formatter.add_section("🔍 Detailed Information", "")

        for entity in entities_data[:10]:  # Limit detailed output to first 10
            entity_id = entity["entity_id"]
            details = []

            # Basic metadata
            details.append(f"**Domain:** {entity['domain']}")
            if entity.get("disabled_by"):
                details.append(f"**Disabled:** {entity['disabled_by']}")
            if entity.get("hidden_by"):
                details.append(f"**Hidden:** {entity['hidden_by']}")

            # State information
            if "state" in include_options and "current_state" in entity:
                details.append(f"**Current State:** {entity['current_state']}")
                if entity.get("last_changed"):
                    details.append(f"**Last Changed:** {format_timestamp(entity['last_changed'])}")

            # History information
            if "history" in include_options and "history_count" in entity:
                details.append(f"**History Records:** {entity['history_count']}")

            # Relations
            if "relations" in include_options and "relations" in entity:
                relations = entity["relations"]
                if "area" in relations:
                    details.append(f"**Area:** {relations['area']['name']}")
                if "device" in relations:
                    device = relations["device"]
                    details.append(f"**Device:** {device['name']} ({device.get('manufacturer', 'Unknown')})")

            formatter.add_section(entity_id, "\n".join(details))

        if len(entities_data) > 10:
            formatter.add_section("", f"... and {len(entities_data) - 10} more entities")

    print(formatter.format())