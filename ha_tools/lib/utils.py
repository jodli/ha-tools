"""
Shared utility functions for ha-tools.
"""

from datetime import datetime, timedelta


def _parse_timeframe_to_timedelta(timeframe: str) -> timedelta:
    """Parse a timeframe string into a timedelta.

    Args:
        timeframe: String like "24h", "7d", "30m", "2w" (case-insensitive, whitespace-trimmed)

    Returns:
        timedelta representing the duration

    Raises:
        ValueError: If timeframe format is invalid
    """
    timeframe = timeframe.lower().strip()

    try:
        if timeframe.endswith("h"):
            return timedelta(hours=int(timeframe[:-1]))
        elif timeframe.endswith("d"):
            return timedelta(days=int(timeframe[:-1]))
        elif timeframe.endswith("m"):
            return timedelta(minutes=int(timeframe[:-1]))
        elif timeframe.endswith("w"):
            return timedelta(weeks=int(timeframe[:-1]))
        else:
            raise ValueError(
                f"Invalid timeframe format: {timeframe}. Use h (hours), d (days), m (minutes), or w (weeks)."
            )
    except ValueError as e:
        if "Invalid timeframe format" in str(e):
            raise
        raise ValueError(
            f"Invalid timeframe format: {timeframe}. Use h (hours), d (days), m (minutes), or w (weeks)."
        ) from e


def parse_timeframe_to_timedelta(timeframe: str) -> timedelta:
    """Parse a timeframe string into a timedelta.

    Public API - delegates to _parse_timeframe_to_timedelta.

    Args:
        timeframe: String like "24h", "7d", "30m", "2w"

    Returns:
        timedelta representing the duration

    Raises:
        ValueError: If timeframe format is invalid
    """
    return _parse_timeframe_to_timedelta(timeframe)


def parse_timeframe(timeframe: str) -> datetime:
    """
    Parse timeframe string into datetime.

    Supported formats:
        - Nh: N hours ago (e.g., 24h)
        - Nd: N days ago (e.g., 7d)
        - Nm: N minutes ago (e.g., 30m)
        - Nw: N weeks ago (e.g., 2w)

    Args:
        timeframe: String like "24h", "7d", "30m", "2w"

    Returns:
        datetime object representing the start time

    Raises:
        ValueError: If timeframe format is invalid
    """
    delta = _parse_timeframe_to_timedelta(timeframe)
    return datetime.now() - delta


def parse_datetime(date_str: str) -> datetime:
    """Parse a date or datetime string.

    Accepts:
        - YYYY-MM-DD (returns midnight)
        - YYYY-MM-DDTHH:MM:SS

    Args:
        date_str: Date string to parse

    Returns:
        datetime object

    Raises:
        ValueError: If format is invalid
    """
    if not date_str:
        raise ValueError("Empty date string")

    # Try YYYY-MM-DDTHH:MM:SS first
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue

    raise ValueError(
        f"Invalid date format: '{date_str}'. Use YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS."
    )
