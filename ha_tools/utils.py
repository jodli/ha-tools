"""Time-window helpers shared across the library."""

import re
from datetime import datetime, timedelta

_TIMEFRAME_RE = re.compile(r"^(\d+)\s*([mhdw])$", re.IGNORECASE)
_DATETIME_FORMATS = ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d")


def parse_timeframe_to_timedelta(timeframe: str) -> timedelta:
    """Parse a relative duration like ``"30m"``, ``"24h"``, ``"14d"``, ``"2w"``."""
    match = _TIMEFRAME_RE.match(timeframe.strip())
    if not match:
        raise ValueError(
            f"Invalid timeframe {timeframe!r}; expected e.g. 30m, 24h, 14d, 2w"
        )
    value = int(match.group(1))
    unit = match.group(2).lower()
    if unit == "m":
        return timedelta(minutes=value)
    if unit == "h":
        return timedelta(hours=value)
    if unit == "d":
        return timedelta(days=value)
    return timedelta(weeks=value)


def parse_datetime(value: str | datetime) -> datetime:
    """Parse a date or datetime string (``YYYY-MM-DD`` or ISO)."""
    if isinstance(value, datetime):
        return value
    text = value.strip()
    for fmt in _DATETIME_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"Could not parse datetime {value!r}") from exc
