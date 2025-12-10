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
from typer import Context

from . import __version__
from .commands import validate, entities, errors
from .config import HaToolsConfig
from .lib.output import print_error, print_success

# Create the main typer app
app = typer.Typer(
    help="High-performance CLI for AI agents working with Home Assistant configurations",
    rich_markup_mode="rich",
    invoke_without_command=True,
)

@app.callback()
def main(
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
    version: bool = typer.Option(
        False,
        "--version",
        help="Show version and exit",
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
    # Handle version flag
    if version:
        typer.echo(f"ha-tools {__version__}")
        raise typer.Exit()

    # Store global configuration for subcommands
    if config is not None:
        HaToolsConfig.set_config_path(config)

# Import and add commands directly
from .commands.validate import validate_command
from .commands.entities import entities_command
from .commands.errors import errors_command

app.command(name="validate")(validate_command)
app.command(name="entities")(entities_command)
app.command(name="errors")(errors_command)

console = console.Console()


@app.command()
def version() -> None:
    """Show version and exit."""
    typer.echo(f"ha-tools {__version__}")


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
            await db.connect()
            await db.test_connection()
            await db.close()

            # Test REST API connection
            from .lib.rest_api import HomeAssistantAPI
            async with HomeAssistantAPI(config.home_assistant) as api:
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


def main() -> None:
    """Main entry point for the CLI."""
    try:
        app()
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user[/yellow]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    main()