#!/usr/bin/env python3
"""
Home Assistant Tools - High-performance CLI for AI agents

A lightweight, fast CLI tool for working with Home Assistant configurations.
Uses hybrid REST API + database access for optimal performance.
"""

import asyncio
import sys
from typing import Optional

import typer
from rich import console

from . import __version__
from .commands import validate, entities, errors
from .config import HaToolsConfig
from .lib.output import print_error, print_success

# Create the main typer app
app = typer.Typer(
    name="ha-tools",
    help="High-performance CLI for AI agents working with Home Assistant configurations",
    no_args_is_help=True,
    rich_markup_mode="rich",
)

# Add subcommands
app.add_typer(validate.app, name="validate", help="Validate Home Assistant configuration")
app.add_typer(entities.app, name="entities", help="Discover and analyze entities")
app.add_typer(errors.app, name="errors", help="Analyze runtime errors")

console = console.Console()


def version_callback(value: bool) -> None:
    """Print version information and exit."""
    if value:
        typer.echo(f"ha-tools {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        "-v",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit",
    ),
    config: Optional[str] = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to configuration file (default: ~/.ha-tools-config.yaml)",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        help="Enable verbose output",
    ),
) -> None:
    """
    High-performance CLI for AI agents working with Home Assistant configurations.

    This tool uses a hybrid approach with REST API + direct database access for
    optimal performance when analyzing Home Assistant configurations.

    Examples:
        ha-tools validate --syntax-only
        ha-tools entities --search "temp_*" --include history
        ha-tools errors --current --log 24h
    """
    # Store global configuration for subcommands
    if config:
        HaToolsConfig.set_config_path(config)


@app.command()
def setup() -> None:
    """Interactive setup wizard for ha-tools configuration."""
    from .lib.setup_wizard import run_setup

    try:
        asyncio.run(run_setup())
        print_success("✓ Configuration setup completed successfully!")
    except Exception as e:
        print_error(f"Setup failed: {e}")
        raise typer.Exit(1)


@app.command()
def test_connection() -> None:
    """Test connection to Home Assistant and database."""
    async def _test() -> None:
        try:
            config = HaToolsConfig.load()

            # Test database connection
            from .lib.database import DatabaseManager
            db = DatabaseManager(config.database)
            await db.test_connection()

            # Test REST API connection
            from .lib.rest_api import HomeAssistantAPI
            api = HomeAssistantAPI(config.home_assistant)
            await api.test_connection()

            print_success("✓ All connections test successful!")

        except Exception as e:
            print_error(f"Connection test failed: {e}")
            raise typer.Exit(1)

    try:
        asyncio.run(_test())
    except KeyboardInterrupt:
        print_error("Connection test cancelled")
        raise typer.Exit(1)


if __name__ == "__main__":
    try:
        app()
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user[/yellow]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)