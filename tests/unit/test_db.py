"""Unit tests for SQL construction and DataFrame shaping."""

import pandas as pd

import ha_tools

STATES_COLS = ["entity_id", "state", "last_changed", "last_updated", "attributes"]
STATS_COLS = [
    "statistic_id",
    "start",
    "mean",
    "min",
    "max",
    "sum",
    "state",
    "last_reset",
    "unit_of_measurement",
]


def test_load_states_columns_and_attributes(fake_db):
    df = ha_tools.load_states("sensor.kaffeemaschine_leistung", timeframe="14d")
    assert list(df.columns) == STATES_COLS
    assert len(df) > 0
    assert isinstance(df["attributes"].iloc[0], dict)
    assert df["attributes"].iloc[0].get("unit_of_measurement") == "W"


def test_load_states_sql_uses_recorder_schema(fake_db):
    ha_tools.load_states("sensor.x", timeframe="1d")
    sql = fake_db.executed[-1][0]
    assert "FROM states s" in sql
    assert "states_meta sm ON s.metadata_id = sm.metadata_id" in sql
    assert "state_attributes sa ON s.attributes_id = sa.attributes_id" in sql
    assert "FROM_UNIXTIME(COALESCE(s.last_changed_ts, s.last_updated_ts))" in sql
    assert "ORDER BY s.last_updated_ts ASC" in sql


def test_load_states_wildcard(fake_db):
    ha_tools.load_states("sensor.*_leistung", timeframe="1d")
    sql, params = fake_db.executed[-1]
    assert "sm.entity_id LIKE %s" in sql
    assert "sensor.%_leistung" in params  # '*' expanded to SQL '%'


def test_load_states_multi_entity_uses_or(fake_db):
    ha_tools.load_states(["sensor.a", "sensor.b"], timeframe="1d")
    sql, params = fake_db.executed[-1]
    assert " OR " in sql
    assert "sensor.a" in params and "sensor.b" in params


def test_load_states_window_bounds(fake_db):
    ha_tools.load_states("sensor.x", start="2026-01-01", end="2026-02-01")
    sql, params = fake_db.executed[-1]
    assert "s.last_updated_ts >= %s" in sql
    assert "s.last_updated_ts <= %s" in sql
    assert len(params) == 3  # entity + start + end


def test_load_states_default_window_is_relative(fake_db):
    ha_tools.load_states("sensor.x")
    sql, params = fake_db.executed[-1]
    assert "s.last_updated_ts >= %s" in sql
    assert "s.last_updated_ts <= %s" in sql  # default 24h → bounded


def test_load_statistics_columns_and_fixed_join(fake_db):
    df = ha_tools.load_statistics(
        "sensor.erdgeschoss_energieverbrauch_total", since="2025-01-01"
    )
    assert list(df.columns) == STATS_COLS
    assert len(df) > 0
    sql, params = fake_db.executed[-1]
    assert "statistics_meta m ON s.metadata_id = m.id" in sql  # the bug fix
    assert "FROM_UNIXTIME(s.start_ts)" in sql
    assert "FROM_UNIXTIME(s.last_reset_ts)" in sql
    assert "ORDER BY s.start_ts ASC" in sql
    assert len(params) == 2  # entity + start (since); open-ended end


def test_load_statistics_no_default_window(fake_db):
    ha_tools.load_statistics("sensor.x")
    sql, _ = fake_db.executed[-1]
    assert "start_ts >=" not in sql  # no bounds → no time filter
    assert "start_ts <=" not in sql


def test_query_returns_dataframe(fake_db):
    df = ha_tools.query("SELECT 1 AS one")
    assert isinstance(df, pd.DataFrame)
