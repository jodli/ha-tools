# ha-tools

> Load Home Assistant recorder data into pandas for Jupyter analysis

`ha-tools` is a small Python **library** that reads raw state history and
long-term statistics from the Home Assistant recorder database directly into
pandas DataFrames — for analysis, feasibility, and amortisation work in
notebooks. It only **retrieves**; it never aggregates or computes, so you keep
full control of the maths.

Live Home Assistant operations (config validation, entity search, logs, control)
are handled by the **ha-mcp** MCP server. This library exists purely for bulk
data access off the recorder DB.

## Install

```bash
uv pip install -e /home/jodli/repos/ha-tools
```

Configure the database connection once in `~/.ha-tools-config.yaml` (never paste
credentials into a notebook):

```yaml
database:
  url: mysql://user:pass@host:3306/homeassistant
  timeout: 30
```

## Usage

```python
from ha_tools import load_states, load_statistics, query

# Raw state-change history (supports wildcards and lists)
df = load_states("sensor.kaffeemaschine_leistung", timeframe="14d")
df = load_states("sensor.*_leistung", timeframe="7d")
df = load_states(
    ["sensor.kuche_temperatur", "sensor.luftung_aussentemperatur"],
    start="2026-01-01",
    end="2026-03-01",
)

# Raw long-term-statistics rows (running totals — you difference them)
stats = load_statistics("sensor.erdgeschoss_energieverbrauch_total", since="2025-01-01")

# Low-level escape hatch for custom SQL
custom = query("SELECT FROM_UNIXTIME(start_ts) ts, sum FROM statistics s "
               "JOIN statistics_meta m ON s.metadata_id = m.id WHERE m.statistic_id = %s",
               ("sensor.x",))
```

- `load_states` → `entity_id, state, last_changed, last_updated, attributes`
  (`attributes` is a parsed dict; use `pd.json_normalize(df["attributes"])` to expand).
- `load_statistics` → `statistic_id, start, mean, min, max, sum, state, last_reset, unit_of_measurement`.
- `*` wildcards expand to SQL `LIKE`; pass a list for multiple entities.
- Time windows: `timeframe="14d"` (`Nm`/`Nh`/`Nd`/`Nw`), or `start`/`end` ISO dates.

## Examples

`examples/` are runnable scripts that double as the integration test suite:

- `appliance_sessions.py` — power-threshold session detection from raw states
- `energy_statistics.py` — daily consumption + cost from raw statistics
- `multi_entity_correlation.py` — aligning several entities over a window

Run one against the real DB: `python examples/energy_statistics.py`.

## Development

```bash
uv sync --all-extras            # install dev deps
uv run pytest                   # hermetic tests (FakeConnection — no live DB)
uv run ruff check . && uv run ruff format .
```

## License

MIT — see [LICENSE](LICENSE).
