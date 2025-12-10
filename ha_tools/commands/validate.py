"""
Validate command for ha-tools.

Provides configuration validation with syntax-only and full validation modes.
"""

import asyncio
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from ..config import HaToolsConfig
from ..lib.database import DatabaseManager
from ..lib.output import MarkdownFormatter, print_error, print_info, print_success
from ..lib.rest_api import HomeAssistantAPI
from .common import create_progress

console = Console()


def validate_command(
    syntax_only: bool = typer.Option(
        False,
        "--syntax-only",
        "-s",
        help="Only perform syntax validation (fast, local-only)",
    ),
) -> None:
    """
    Validate Home Assistant configuration.

    Performs syntax-only validation (local YAML parsing) or full validation
    via Home Assistant API.

    Examples:
        ha-tools validate --syntax-only
        ha-tools validate
    """
    try:
        # Run async validation
        exit_code = asyncio.run(_run_validation(syntax_only))
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print_error("Validation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print_error(f"Validation failed: {e}")
        sys.exit(1)


async def _run_validation(syntax_only: bool) -> int:
    """Run the validation process."""
    try:
        config = HaToolsConfig.load()
    except Exception as e:
        print_error(f"Configuration error: {e}")
        return 3  # Configuration error

    formatter = MarkdownFormatter(title="Configuration Validation")

    if syntax_only:
        return await _run_syntax_validation(config, formatter)
    else:
        return await _run_full_validation(config, formatter)


async def _run_syntax_validation(
    config: HaToolsConfig, formatter: MarkdownFormatter
) -> int:
    """Run syntax-only validation."""
    print_info("Running syntax validation...")
    errors = []
    warnings = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Validating YAML files...", total=None)

        # Validate main configuration
        main_errors, main_warnings = await _validate_yaml_file(
            Path(config.ha_config_path) / "configuration.yaml"
        )
        errors.extend(main_errors)
        warnings.extend(main_warnings)

        # Validate package files
        packages_path = Path(config.ha_config_path) / "packages"
        if packages_path.exists():
            for package_file in packages_path.glob("*.yaml"):
                pkg_errors, pkg_warnings = await _validate_yaml_file(package_file)
                errors.extend(pkg_errors)
                warnings.extend(pkg_warnings)

        # Validate templates
        templates_path = Path(config.ha_config_path) / "templates"
        if templates_path.exists():
            for template_file in templates_path.glob("*.yaml"):
                tpl_errors, tpl_warnings = await _validate_yaml_file(template_file)
                errors.extend(tpl_errors)
                warnings.extend(tpl_warnings)

        progress.update(task, description="✓ Syntax validation complete")

    # Generate report
    _generate_syntax_report(formatter, errors, warnings)

    console.print(formatter.format())

    # Return exit code based on results
    if errors:
        return 2  # Validation errors found
    elif warnings:
        return 0  # Success, but with warnings
    else:
        return 0  # Success


async def _run_full_validation(
    config: HaToolsConfig, formatter: MarkdownFormatter
) -> int:
    """Run full validation including Home Assistant API."""
    print_info("Running full validation...")

    # First run syntax validation
    syntax_exit_code = await _run_syntax_validation(config, formatter)
    if syntax_exit_code == 2:
        return 2  # Don't continue if syntax errors

    # Then run semantic validation via Home Assistant
    try:
        async with HomeAssistantAPI(config.home_assistant) as api:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task(
                    "Performing Home Assistant validation...", total=None
                )

                validation_result = await api.validate_config()
                progress.update(task, description="✓ Validation complete")

            _generate_semantic_report(formatter, validation_result)

    except Exception as e:
        print_error(f"Failed to connect to Home Assistant: {e}")
        return 3  # Connection error

    console.print(formatter.format())

    return 0  # Success


async def _validate_yaml_file(file_path: Path) -> tuple[list[str], list[str]]:
    """Validate a single YAML file."""
    errors = []
    warnings = []

    if not file_path.exists():
        warnings.append(f"File not found: {file_path}")
        return errors, warnings

    try:
        import yaml

        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Try to parse YAML
        yaml.safe_load(content)

    except yaml.YAMLError as e:
        errors.append(f"YAML syntax error in {file_path}: {e}")
    except Exception as e:
        errors.append(f"Error validating {file_path}: {e}")

    return errors, warnings


def _generate_syntax_report(
    formatter: MarkdownFormatter,
    errors: list[str],
    warnings: list[str],
) -> None:
    """Generate syntax validation report."""
    if errors:
        formatter.add_section("❌ Syntax Errors", "")
        formatter.add_list(errors)
        formatter.add_section("", "")

    if warnings:
        formatter.add_section("⚠️ Warnings", "")
        formatter.add_list(warnings)
        formatter.add_section("", "")

    # Summary
    total_issues = len(errors) + len(warnings)
    if total_issues == 0:
        formatter.add_section(
            "✅ Syntax Validation", "All YAML files passed syntax validation!"
        )
    else:
        status = "FAILED" if errors else "PASSED"
        formatter.add_section(
            "📊 Summary",
            f"Status: **{status}**\nErrors: {len(errors)}\nWarnings: {len(warnings)}",
        )


def _generate_semantic_report(
    formatter: MarkdownFormatter, validation_result: dict
) -> None:
    """Generate semantic validation report."""
    formatter.add_section("🔍 Semantic Validation", "")

    if validation_result.get("valid", True):
        formatter.add_section(
            "✅ Configuration Valid", "Home Assistant configuration is valid!"
        )
    else:
        formatter.add_section("❌ Configuration Invalid", "")
        errors = validation_result.get("errors", [])
        if errors:
            formatter.add_list(errors)

    # Add any additional information from validation result
    if "messages" in validation_result:
        formatter.add_section("📝 Messages", "")
        formatter.add_list(validation_result["messages"])
