"""Sync MariaDB access for the Home Assistant recorder → pandas DataFrames.

All functions retrieve raw rows only — no aggregation happens here. The
connection is opened per call from ``~/.ha-tools-config.yaml``; tests override
the :data:`_connection_factory` seam to feed a :class:`FakeConnection`.
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from datetime import datetime
from typing import Any

import pandas as pd

from .config import HaToolsConfig
from .utils import parse_datetime, parse_timeframe_to_timedelta

# --- connection seam (override in tests) -------------------------------------
_connection_factory: Any = None
"""If set, ``_get_connection`` returns its result instead of a real connection."""


def _get_connection() -> Any:
    if _connection_factory is not None:
        return _connection_factory()
    return connect()


def connect() -> Any:
    """Open a ``pymysql`` connection from the configured database URL."""
    import pymysql

    cfg = HaToolsConfig.load()
    return pymysql.connect(
        **_parse_mysql_url(cfg.database.url),
        connect_timeout=cfg.database.timeout,
    )


def _parse_mysql_url(url: str) -> dict[str, Any]:
    """Parse ``mysql://user:pass@host:port/database`` into pymysql kwargs."""
    match = re.match(r"mysql://([^:]+):([^@]*)@([^:]+):(\d+)/(.+)", url)
    if not match:
        raise ValueError(f"Invalid MySQL URL: {url}")
    return {
        "user": match.group(1),
        "password": match.group(2),
        "host": match.group(3),
        "port": int(match.group(4)),
        "database": match.group(5),
    }


def _fetch(sql: str, params: Sequence[Any]) -> tuple[list[str], list[tuple]]:
    """Execute a SELECT and return (column names, rows)."""
    conn = _get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, tuple(params))
            columns = [desc[0] for desc in cur.description] if cur.description else []
            rows = cur.fetchall()
        return columns, list(rows)
    finally:
        conn.close()


def _resolve_window(
    start: str | datetime | None = None,
    end: str | datetime | None = None,
    timeframe: str | None = None,
    *,
    default_timeframe: str | None = "24h",
) -> tuple[datetime | None, datetime | None]:
    """Resolve (start, end) datetimes following the documented precedence."""
    start_dt = parse_datetime(start) if start else None
    end_dt = parse_datetime(end) if end else None

    delta = parse_timeframe_to_timedelta(timeframe) if timeframe else None
    if delta is not None:
        if start_dt is not None and end_dt is None:
            end_dt = start_dt + delta
        elif end_dt is not None and start_dt is None:
            start_dt = end_dt - delta
        elif start_dt is None and end_dt is None:
            now = datetime.now()
            start_dt, end_dt = now - delta, now

    if start_dt is None and end_dt is None and default_timeframe is not None:
        delta = parse_timeframe_to_timedelta(default_timeframe)
        now = datetime.now()
        start_dt, end_dt = now - delta, now

    return start_dt, end_dt


def _pattern_clause(patterns: Sequence[str], column: str) -> tuple[str, list[Any]]:
    """Build a WHERE fragment matching entity ids; ``*`` becomes SQL ``LIKE``."""
    conditions: list[str] = []
    params: list[str] = []
    for pattern in patterns:
        if "*" in pattern:
            conditions.append(f"{column} LIKE %s")
            params.append(pattern.replace("*", "%"))
        else:
            conditions.append(f"{column} = %s")
            params.append(pattern)
    return "(" + " OR ".join(conditions) + ")", params


def _as_patterns(entity: str | Sequence[str]) -> list[str]:
    return [entity] if isinstance(entity, str) else list(entity)


def _parse_attributes(value: Any) -> Any:
    if value is None:
        return {}
    if isinstance(value, dict | list):
        return value
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return {}


def load_states(
    entity: str | Sequence[str],
    start: str | datetime | None = None,
    end: str | datetime | None = None,
    timeframe: str | None = None,
    limit: int | None = None,
) -> pd.DataFrame:
    """Load raw state-change history for one or more entities (supports ``*``).

    Returns a long DataFrame: ``entity_id, state, last_changed, last_updated,
    attributes`` (ascending by time; ``attributes`` is a parsed dict column).
    """
    patterns = _as_patterns(entity)
    entity_sql, params = _pattern_clause(patterns, "sm.entity_id")
    start_dt, end_dt = _resolve_window(start, end, timeframe)

    conditions = [entity_sql]
    if start_dt is not None:
        conditions.append("s.last_updated_ts >= %s")
        params.append(start_dt.timestamp())
    if end_dt is not None:
        conditions.append("s.last_updated_ts <= %s")
        params.append(end_dt.timestamp())

    sql = f"""
    SELECT
        sm.entity_id,
        s.state,
        FROM_UNIXTIME(COALESCE(s.last_changed_ts, s.last_updated_ts)) AS last_changed,
        FROM_UNIXTIME(s.last_updated_ts) AS last_updated,
        sa.shared_attrs AS attributes
    FROM states s
    INNER JOIN states_meta sm ON s.metadata_id = sm.metadata_id
    LEFT JOIN state_attributes sa ON s.attributes_id = sa.attributes_id
    WHERE {" AND ".join(conditions)}
    ORDER BY s.last_updated_ts ASC
    """
    if limit:
        sql += " LIMIT %s"
        params.append(limit)

    columns, rows = _fetch(sql, params)
    df = pd.DataFrame(rows, columns=columns)
    if "attributes" in df.columns and len(df) > 0:
        df["attributes"] = df["attributes"].apply(_parse_attributes)
    return df


def load_statistics(
    entity: str | Sequence[str],
    since: str | datetime | None = None,
    start: str | datetime | None = None,
    end: str | datetime | None = None,
    timeframe: str | None = None,
    limit: int | None = None,
) -> pd.DataFrame:
    """Load raw long-term-statistics rows (no aggregation by the library).

    Returns ``statistic_id, start, mean, min, max, sum, state, last_reset,
    unit_of_measurement`` (ascending by ``start``). ``since`` is an alias for
    ``start``; with no bounds given, all rows are returned.
    """
    patterns = _as_patterns(entity)
    entity_sql, params = _pattern_clause(patterns, "m.statistic_id")
    start_dt, end_dt = _resolve_window(
        start or since, end, timeframe, default_timeframe=None
    )

    conditions = [entity_sql]
    if start_dt is not None:
        conditions.append("s.start_ts >= %s")
        params.append(start_dt.timestamp())
    if end_dt is not None:
        conditions.append("s.start_ts <= %s")
        params.append(end_dt.timestamp())

    sql = f"""
    SELECT
        m.statistic_id,
        FROM_UNIXTIME(s.start_ts) AS start,
        s.mean, s.min, s.max, s.sum, s.state,
        FROM_UNIXTIME(s.last_reset_ts) AS last_reset,
        m.unit_of_measurement
    FROM statistics s
    JOIN statistics_meta m ON s.metadata_id = m.id
    WHERE {" AND ".join(conditions)}
    ORDER BY s.start_ts ASC
    """
    if limit:
        sql += " LIMIT %s"
        params.append(limit)

    columns, rows = _fetch(sql, params)
    return pd.DataFrame(rows, columns=columns)


def query(sql: str, params: Sequence[Any] | None = None) -> pd.DataFrame:
    """Low-level escape hatch: run arbitrary SQL and return a DataFrame."""
    columns, rows = _fetch(sql, params or [])
    return pd.DataFrame(rows, columns=columns)
