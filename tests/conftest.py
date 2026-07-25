"""Shared test fixtures.

``FakeConnection`` stands in for pymysql so the library's real SQL-building and
DataFrame-shaping code runs hermetically (no live database needed). Fixtures are
plain JSON keyed by query type.
"""

import json
from pathlib import Path
from typing import Any

import pytest

FIXTURE_DIR = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> tuple[list[str], list[tuple]]:
    with open(FIXTURE_DIR / name, encoding="utf-8") as f:
        data = json.load(f)
    return data["columns"], [tuple(row) for row in data["rows"]]


class FakeCursor:
    def __init__(self, conn: "FakeConnection") -> None:
        self._conn = conn
        self.description: list[tuple] | None = None
        self._rows: list[tuple] = []

    def __enter__(self) -> "FakeCursor":
        return self

    def __exit__(self, *exc: Any) -> bool:
        return False

    def execute(self, sql: str, params: tuple = ()) -> None:
        self._conn.executed.append((sql, tuple(params)))
        columns, rows = self._conn.rows_for(sql)
        self.description = [(c,) for c in columns]
        self._rows = rows

    def fetchall(self) -> list[tuple]:
        return list(self._rows)

    def fetchone(self) -> tuple | None:
        return self._rows[0] if self._rows else None


class FakeConnection:
    """A minimal DBAPI-like connection backed by JSON fixtures."""

    def __init__(self) -> None:
        # Every (sql, params) tuple executed through this connection.
        self.executed: list[tuple[str, tuple]] = []

    def cursor(self) -> FakeCursor:
        return FakeCursor(self)

    def close(self) -> None:
        pass

    def rows_for(self, sql: str) -> tuple[list[str], list[tuple]]:
        lowered = sql.lower()
        if "from statistics" in lowered:
            return _load_fixture("statistics.json")
        if "from states" in lowered:
            return _load_fixture("states.json")
        return [], []


@pytest.fixture
def fake_db(monkeypatch: pytest.MonkeyPatch) -> FakeConnection:
    """Point the library's connection seam at a FakeConnection and return it."""
    import ha_tools.db as db

    fake = FakeConnection()
    monkeypatch.setattr(db, "_connection_factory", lambda: fake)
    return fake
