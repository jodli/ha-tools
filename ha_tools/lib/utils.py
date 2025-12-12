"""
Shared utility functions for ha-tools.
"""

from datetime import datetime, timedelta


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
    timeframe = timeframe.lower().strip()

    try:
        if timeframe.endswith("h"):
            hours = int(timeframe[:-1])
            return datetime.now() - timedelta(hours=hours)
        elif timeframe.endswith("d"):
            days = int(timeframe[:-1])
            return datetime.now() - timedelta(days=days)
        elif timeframe.endswith("m"):
            minutes = int(timeframe[:-1])
            return datetime.now() - timedelta(minutes=minutes)
        elif timeframe.endswith("w"):
            weeks = int(timeframe[:-1])
            return datetime.now() - timedelta(weeks=weeks)
        else:
            raise ValueError(f"Invalid timeframe format: {timeframe}. Use h (hours), d (days), m (minutes), or w (weeks).")
    except ValueError as e:
        if "Invalid timeframe format" in str(e):
            raise
        raise ValueError(f"Invalid timeframe format: {timeframe}. Use h (hours), d (days), m (minutes), or w (weeks).") from e
