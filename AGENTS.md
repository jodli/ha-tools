# Agent Context: ha-tools

`ha-tools` is a **Python library** (not a CLI) that loads Home Assistant
recorder data into pandas DataFrames for Jupyter/notebook analysis. It retrieves
raw rows only — no aggregation.

For live Home Assistant operations (validation, entity search, logs, control),
use the **ha-mcp** MCP server, not this library. This library is for bulk data
access off the MariaDB recorder.

## Public API

```python
from ha_tools import load_states, load_statistics, query

load_states(entity, start=None, end=None, timeframe="24h", limit=None)            # raw states
load_statistics(entity, since=None, start=None, end=None, timeframe=None, limit=None)  # raw stats rows
query(sql, params=None)                                                           # escape hatch
```

`entity` is a string or list; `*` wildcards expand to SQL `LIKE`. Configure the
DB once in `~/.ha-tools-config.yaml` (the `database` block).

## When working in this repo

- **Schema knowledge lives in `ha_tools/db.py`.** `states` joins `states_meta`
  on `s.metadata_id = sm.metadata_id` and `state_attributes` (`shared_attrs` is a
  JSON blob). `statistics` joins `statistics_meta` on `s.metadata_id = m.id`
  (note: `id`, not `metadata_id`) with modern columns `start_ts` / `last_reset_ts`.
- **Connection seam:** `ha_tools.db._connection_factory` — tests override it with
  a `FakeConnection` (see `tests/conftest.py`). Never call real pymysql from tests.
- **Examples are tests:** each `examples/*.py` exposes `run()` and is executed by
  `tests/integration/test_examples.py` against the fake DB. To document a new use
  case, add an example and a matching assertion.
- **Verify:** `uv run pytest` (hermetic), `uv run ruff check .`.

## Operating protocol

1. Read `ha_tools/db.py` before touching SQL.
2. If you change the SQL, update the assertions in `tests/integration/test_examples.py`.
3. Keep `uv run pytest` green.
