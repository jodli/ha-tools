"""
Output formatting utilities for ha-tools.

Provides structured markdown output optimized for AI consumption with progressive disclosure.
"""

import json
from datetime import datetime
from typing import Any

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress
from rich.table import Table

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


class RichOutput:
    """Rich console output utilities."""

    @staticmethod
    def create_table(title: str, headers: list[str], rows: list[list[str]]) -> Table:
        """Create a rich table."""
        table = Table(title=title, box=box.ROUNDED)
        for header in headers:
            table.add_column(header)

        for row in rows:
            # Pad row to match header count
            while len(row) < len(headers):
                row.append("")
            table.add_row(*row)

        return table

    @staticmethod
    def create_panel(
        content: str, title: str | None = None, style: str = "blue"
    ) -> Panel:
        """Create a rich panel."""
        return Panel(content, title=title, border_style=style)

    @staticmethod
    def create_progress() -> Progress:
        """Create a progress bar."""
        return Progress()


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


def format_duration(seconds: float | None) -> str:
    """Format duration in human-readable format."""
    if not seconds:
        return "N/A"

    if seconds < 1:
        return f"{seconds * 1000:.0f}ms"
    elif seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}m {secs}s"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}h {minutes}m"


def format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable format."""
    if size_bytes < 1024:
        return f"{size_bytes}B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f}KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f}MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f}GB"


def output_json(data: Any, pretty: bool = True) -> str:
    """Output data as JSON."""
    if pretty:
        return json.dumps(data, indent=2, default=str)
    return json.dumps(data, default=str)


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """Truncate text to specified length."""
    if len(text) <= max_length:
        return text
    return text[: max_length - len(suffix)] + suffix
