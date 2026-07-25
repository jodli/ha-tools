# CLAUDE.md

## Overview

`ha-tools` is a small Python **library** that loads Home Assistant recorder data
(MariaDB) into pandas DataFrames for analysis in Jupyter notebooks. It retrieves
raw rows only — all calculation happens in the notebook. Live HA operations
(validation, search, logs, control) are handled by the ha-mcp MCP server; this
library exists purely for bulk data access.

## Public API

- `ha_tools.load_states(entity, start, end, timeframe, limit)` — raw state history.
- `ha_tools.load_statistics(entity, since, start, end, timeframe, limit)` — raw long-term stats rows.
- `ha_tools.query(sql, params)` — low-level escape hatch.

## Development

```bash
uv run pytest                 # hermetic tests via FakeConnection (no live DB)
uv run ruff check . && uv run ruff format .
```

## Key files

- `ha_tools/db.py` — SQL + DataFrame construction; the recorder schema knowledge
  lives here. `_connection_factory` is the test seam.
- `ha_tools/config.py` — reads `~/.ha-tools-config.yaml` (`database` block).
- `ha_tools/utils.py` — timeframe / datetime parsing.
- `examples/` — runnable usage demos that double as the integration suite.
- `tests/conftest.py` — `FakeConnection` + JSON fixtures under `tests/fixtures/`.

## Schema notes

- `states` ⟕ `states_meta` on `metadata_id = metadata_id`; `state_attributes.shared_attrs` is a JSON blob.
- `statistics` ⟕ `statistics_meta` on `metadata_id = id`; modern columns are `start_ts` / `last_reset_ts` (not `start` / `last_reset`).
- Timestamps are unix floats (`*_ts`); selected via `FROM_UNIXTIME` → naive UTC datetimes.
