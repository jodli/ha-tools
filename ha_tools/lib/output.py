"""
Output formatting utilities for ha-tools.

Provides structured markdown output optimized for AI consumption with progressive disclosure.
"""

import json
from datetime import datetime
from typing import Any

from rich.console import Console

console = Console()

# Verbose output state
_verbose_enabled = False


def set_verbose(enabled: bool) -> None:
    """Enable or disable verbose output."""
    global _verbose_enabled
    _verbose_enabled = enabled


def is_verbose() -> bool:
    """Check if verbose output is enabled."""
    return _verbose_enabled


def print_verbose(message: str) -> None:
    """Print a message only when verbose mode is enabled."""
    if _verbose_enabled:
        console.print(f"[dim]  {message}[/dim]")


def print_verbose_timing(operation: str, duration_ms: float) -> None:
    """Print timing information in verbose mode."""
    if _verbose_enabled:
        console.print(f"[dim]  {operation}: {duration_ms:.1f}ms[/dim]")


def print_success(message: str) -> None:
    """Print a success message."""
    console.print(f"[green]✓ {message}[/green]")


def print_error(message: str) -> None:
    """Print an error message."""
    console.print(f"[red]✗ {message}[/red]")


def print_warning(message: str) -> None:
    """Print a warning message."""
    console.print(f"[yellow]⚠ {message}[/yellow]")


def print_info(message: str) -> None:
    """Print an info message."""
    console.print(f"[blue]ℹ {message}[/blue]")


class MarkdownFormatter:
    """Format output as structured markdown optimized for AI consumption."""

    def __init__(self, title: str | None = None):
        self.title = title
        self.sections: list[str] = []

    def add_section(self, title: str, content: str, level: int = 2) -> None:
        """Add a markdown section."""
        header = "#" * level + f" {title}"
        self.sections.append(f"{header}\n{content}")

    def add_table(
        self, headers: list[str], rows: list[list[str]], title: str | None = None
    ) -> None:
        """Add a markdown table."""
        if not rows:
            return

        if title:
            self.sections.append(f"### {title}")

        # Create table
        table_content = []
        table_content.append("| " + " | ".join(headers) + " |")
        table_content.append("| " + " | ".join(["---"] * len(headers)) + " |")

        for row in rows:
            # Ensure row has same number of columns as headers
            while len(row) < len(headers):
                row.append("")
            table_content.append("| " + " | ".join(str(cell) for cell in row) + " |")

        self.sections.append("\n".join(table_content))

    def add_code_block(
        self, code: str, language: str | None = None, title: str | None = None
    ) -> None:
        """Add a code block."""
        if title:
            self.sections.append(f"### {title}")

        lang = language or ""
        self.sections.append(f"```{lang}\n{code}\n```")

    def add_list(
        self, items: list[str], ordered: bool = False, title: str | None = None
    ) -> None:
        """Add a list."""
        if title:
            self.sections.append(f"### {title}")

        if ordered:
            for i, item in enumerate(items, 1):
                self.sections.append(f"{i}. {item}")
        else:
            for item in items:
                self.sections.append(f"- {item}")

    def add_collapsible(self, summary: str, content: str) -> None:
        """Add a collapsible section (HTML details tag)."""
        self.sections.append(
            f"<details>\n<summary>{summary}</summary>\n\n{content}\n</details>"
        )

    def format(self) -> str:
        """Return the complete markdown content."""
        content = []

        if self.title:
            content.append(f"# {self.title}")

        content.extend(self.sections)
        return "\n\n".join(content)


def format_timestamp(timestamp: str | datetime | None) -> str:
    """Format timestamp for display."""
    if not timestamp:
        return "Never"

    dt: datetime
    if isinstance(timestamp, str):
        try:
            dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except ValueError:
            return timestamp
    else:
        dt = timestamp

    return dt.strftime("%Y-%m-%d %H:%M:%S")


def output_json(data: Any, pretty: bool = True) -> str:
    """Output data as JSON."""
    if pretty:
        return json.dumps(data, indent=2, default=str)
    return json.dumps(data, default=str)
