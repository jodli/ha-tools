"""
Common utilities for ha-tools commands.

Shared functionality and helper functions.
"""

from rich.progress import Progress, SpinnerColumn, TextColumn


def create_progress() -> Progress:
    """Create a standardized progress bar."""
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
    )
