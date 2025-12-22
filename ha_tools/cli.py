#!/usr/bin/env python3
"""
Home Assistant Tools - High-performance CLI for AI agents

A lightweight, fast CLI tool for working with Home Assistant configurations.
Uses hybrid REST API + database access for optimal performance.
"""

import asyncio
import sys

import typer
from typer import Context

from . import __version__
from .commands.entities import entities_command
from .commands.history import history_command
from .commands.logs import logs_command
from .commands.validate import validate_command
from .config import HaToolsConfig
from .lib.output import console, print_error, print_success, set_verbose

# Create the main typer app
app = typer.Typer(
    help="High-performance CLI for AI agents working with Home Assistant configurations",
    rich_markup_mode="rich",
    invoke_without_command=True,
)


@app.callback(invoke_without_command=True)
def callback(
    ctx: Context,
    config: str | None = typer.Option(
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
        ha-tools logs --current --log 24h
    """
    # Handle version flag
    if version:
        typer.echo(f"ha-tools {__version__}")
        raise typer.Exit()

    # Enable verbose output if requested
    set_verbose(verbose)

    # Store global configuration for subcommands
    if config is not None:
        HaToolsConfig.set_config_path(config)

    # Show help if no command provided
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit()


# Register command functions
app.command(name="validate")(validate_command)
app.command(name="entities")(entities_command)
app.command(name="logs")(logs_command)
app.command(name="history")(history_command)


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
        raise typer.Exit(1) from None


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
            raise typer.Exit(1) from None

    try:
        asyncio.run(_test())
    except KeyboardInterrupt:
        print_error("Connection test cancelled")
        raise typer.Exit(1) from None


def cli_main() -> None:
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
    cli_main()
