"""
Interactive setup wizard for ha-tools configuration.

Guides users through setting up Home Assistant and database connections.
"""

from pathlib import Path

import yaml
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Confirm, Prompt

from ..config import DatabaseConfig, HaToolsConfig, HomeAssistantConfig
from .output import print_error, print_success, print_warning

console = Console()


async def run_setup() -> None:
    """Run the interactive setup wizard."""
    console.print("[bold blue]Home Assistant Tools Setup Wizard[/bold blue]")
    console.print(
        "This wizard will help you configure ha-tools for your Home Assistant instance.\n"
    )

    # Check if config already exists
    config_path = HaToolsConfig.get_config_path()
    if config_path.exists():
        console.print(
            f"[yellow]⚠ Configuration file already exists at {config_path}[/yellow]"
        )
        if not Confirm.ask("Do you want to overwrite it?"):
            return

    # Get Home Assistant configuration
    ha_config = await _setup_home_assistant()

    # Get database configuration
    db_config = await _setup_database()

    # Get additional settings
    ha_config_path = Prompt.ask(
        "Home Assistant configuration directory", default="/config"
    )

    # Create configuration
    config = HaToolsConfig(
        home_assistant=ha_config, database=db_config, ha_config_path=ha_config_path
    )

    # Validate configuration
    try:
        await _validate_config(config)
    except Exception as e:
        print_error(f"Configuration validation failed: {e}")
        if not Confirm.ask("Do you want to save anyway?"):
            return

    # Save configuration
    config.save()
    print_success(f"Configuration saved to {config_path}")

    # Test connections
    if Confirm.ask("Test connections now?"):
        await _test_connections(config)


async def _setup_home_assistant() -> HomeAssistantConfig:
    """Setup Home Assistant configuration."""
    console.print("\n[bold]Home Assistant Configuration[/bold]")

    while True:
        url = Prompt.ask("Home Assistant URL", default="http://localhost:8123")

        token = Prompt.ask("Long-lived access token", password=True)

        config = HomeAssistantConfig(url=url, access_token=token)

        # Test connection
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Testing Home Assistant connection...", total=None)

            try:
                from .rest_api import HomeAssistantAPI

                api = HomeAssistantAPI(config)
                await api.test_connection()
                progress.update(task, description="✓ Connection successful")
                print_success("Home Assistant connection verified")
                break
            except Exception as e:
                progress.update(task, description="✗ Connection failed")
                print_error(f"Home Assistant connection failed: {e}")

                if not Confirm.ask("Try again?"):
                    break

    return config


async def _setup_database() -> DatabaseConfig:
    """Setup database configuration."""
    console.print("\n[bold]Database Configuration[/bold]")

    # Help text about database setup
    console.print("[dim]Home Assistant uses a database to store historical data.[/dim]")
    console.print("[dim]Check your configuration.yaml for database settings.[/dim]\n")

    # Offer preset options
    console.print("Common database types:")
    console.print("1. SQLite (default, embedded)")
    console.print("2. MySQL/MariaDB")
    console.print("3. PostgreSQL")

    db_type = Prompt.ask("Select database type", choices=["1", "2", "3"], default="1")

    url = None
    if db_type == "1":
        # SQLite
        db_path = Prompt.ask(
            "SQLite database file path", default="/config/home-assistant_v2.db"
        )
        url = f"sqlite:///{db_path}"
    elif db_type == "2":
        # MySQL/MariaDB
        host = Prompt.ask("MySQL/MariaDB host", default="localhost")
        port = Prompt.ask("Port", default="3306")
        database = Prompt.ask("Database name", default="homeassistant")
        username = Prompt.ask("Username")
        password = Prompt.ask("Password", password=True)
        url = f"mysql://{username}:{password}@{host}:{port}/{database}"
    elif db_type == "3":
        # PostgreSQL
        host = Prompt.ask("PostgreSQL host", default="localhost")
        port = Prompt.ask("Port", default="5432")
        database = Prompt.ask("Database name", default="homeassistant")
        username = Prompt.ask("Username")
        password = Prompt.ask("Password", password=True)
        url = f"postgresql://{username}:{password}@{host}:{port}/{database}"

    # Test connection
    assert url is not None  # All branches above set url
    config = DatabaseConfig(url=url)
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Testing database connection...", total=None)

        try:
            from .database import DatabaseManager

            db = DatabaseManager(config)
            await db.test_connection()
            progress.update(task, description="✓ Connection successful")
            print_success("Database connection verified")
        except Exception as e:
            progress.update(task, description="✗ Connection failed")
            print_error(f"Database connection failed: {e}")
            print_warning(
                "You can continue setup and fix the database connection later"
            )

    return config


async def _validate_config(config: HaToolsConfig) -> None:
    """Validate the configuration."""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        # Validate Home Assistant config directory
        task = progress.add_task(
            "Validating Home Assistant configuration...", total=None
        )
        config.validate_access()
        progress.update(task, description="✓ Home Assistant configuration accessible")

        # Check for essential files
        ha_path = Path(config.ha_config_path)
        required_files = ["configuration.yaml"]
        for file_name in required_files:
            file_path = ha_path / file_name
            if not file_path.exists():
                raise ValueError(f"Required file not found: {file_path}")

        print_success("Configuration validation passed")


async def _test_connections(config: HaToolsConfig) -> None:
    """Test all configured connections."""
    console.print("\n[bold]Testing Connections[/bold]")

    # Test database
    try:
        from .database import DatabaseManager

        db = DatabaseManager(config.database)
        await db.test_connection()
        print_success("✓ Database connection successful")
    except Exception as e:
        print_error(f"✗ Database connection failed: {e}")

    # Test Home Assistant API
    try:
        from .rest_api import HomeAssistantAPI

        api = HomeAssistantAPI(config.home_assistant)
        await api.test_connection()
        print_success("✓ Home Assistant API connection successful")
    except Exception as e:
        print_error(f"✗ Home Assistant API connection failed: {e}")

    # Test registry access
    try:
        storage_path = Path(config.ha_config_path) / ".storage"
        if storage_path.exists():
            print_success("✓ Home Assistant storage directory accessible")
        else:
            print_warning("⚠ Home Assistant storage directory not found")
    except Exception as e:
        print_error(f"✗ Storage directory access failed: {e}")


def show_config_example() -> None:
    """Show example configuration file."""
    example = {
        "home_assistant": {
            "url": "http://localhost:8123",
            "access_token": "your_long_lived_token_here",
            "timeout": 30,
        },
        "database": {
            "url": "sqlite:////config/home-assistant_v2.db",
            "pool_size": 10,
            "max_overflow": 20,
            "timeout": 30,
        },
        "ha_config_path": "/config",
        "output_format": "markdown",
        "verbose": False,
    }

    console.print("\n[bold]Example Configuration File[/bold]")
    console.print("[dim]~/.ha-tools-config.yaml[/dim]:\n")
    console.print(yaml.dump(example, default_flow_style=False))
