# History Flag Not Returning Data - Implementation Plan

## Overview

When running `uv run ha-tools entities --search "sensor.batteries_forcible_charge" --history 12h`, no history data is returned. Investigation revealed two distinct issues that need to be fixed.

## Current State Analysis

### Issue 1: UX Problem - `--history` flag alone doesn't fetch history

**Location**: `ha_tools/commands/entities.py:216`

```python
if "history" in include_options and history_timeframe:
```

The `--history 12h` flag only sets the *timeframe*, but you also need `--include history` to actually fetch history data. This is confusing and counter-intuitive.

**Expected behavior**: `--history 12h` should automatically enable history fetching.

### Issue 2: Database Schema Mismatch (CRITICAL)

**Location**: `ha_tools/lib/database.py:224-254`

The current queries assume the old Home Assistant database schema where `entity_id` was directly in the `states` table:

```python
query = "SELECT entity_id, state, last_changed, last_updated, attributes FROM states"
```

**Reality**: Since Home Assistant 2022.x (and refined through 2024.8), the schema uses a normalized structure with `states_meta`:

- `states` table contains: `state_id`, `state`, `attributes_id`, `metadata_id`, `last_changed_ts`, `last_updated_ts`
- `states_meta` table contains: `metadata_id`, `entity_id`
- `state_attributes` table contains: `attributes_id`, `shared_attrs` (as JSON)

The query needs to JOIN with `states_meta` to get the `entity_id`.

### Issue 2b: NULL `last_changed_ts` values

**Discovery**: During implementation testing, found that `last_changed_ts` is often NULL when the state value hasn't changed (only `last_updated_ts` is set). The queries need to use `COALESCE(last_changed_ts, last_updated_ts)` for filtering and sorting.

### Issue 3: Silent Error Swallowing

**Location**: `ha_tools/commands/entities.py:223-224`

```python
except Exception:
    pass  # No error handling, just silently fails
```

Database errors (including schema mismatches) are silently swallowed, making debugging impossible.

## Desired End State

After implementation:
1. `uv run ha-tools entities --search "sensor.*" --history 12h` returns history data
2. Database queries work with modern Home Assistant schema (2024.x)
3. Errors are properly logged/reported instead of silently swallowed
4. `--history` flag implicitly enables history fetching without needing `--include history`

### Verification
```bash
# Should return entities with history_count > 0
uv run ha-tools entities --search "sensor.batteries_forcible_charge" --history 12h

# Should output JSON with history records
uv run ha-tools entities --search "sensor.batteries_forcible_charge" --history 12h --format json
```

## What We're NOT Doing

- Not changing statistics queries (separate issue)
- Not adding new history features beyond fixing the existing functionality
- Not refactoring the entire database layer
- Not adding database migration support for multiple schema versions

## Implementation Approach

Fix the issues in priority order: database schema first (blocking), then UX improvement, then error handling.

---

## Phase 1: Fix Database Schema for Modern Home Assistant

### Overview
Update all database query methods to use the normalized schema with `states_meta` JOIN.

### Changes Required:

#### 1. Update SQLite History Query
**File**: `ha_tools/lib/database.py`

Replace `_get_entity_states_sqlite` method (lines 219-254):

```python
async def _get_entity_states_sqlite(self, entity_id: Optional[str],
                                   start_time: Optional[datetime],
                                   end_time: Optional[datetime],
                                   limit: Optional[int]) -> List[Dict[str, Any]]:
    """Get entity states from SQLite database (modern schema with states_meta)."""
    query = """
    SELECT
        sm.entity_id,
        s.state,
        datetime(s.last_changed_ts, 'unixepoch') as last_changed,
        datetime(s.last_updated_ts, 'unixepoch') as last_updated,
        sa.shared_attrs as attributes
    FROM states s
    INNER JOIN states_meta sm ON s.metadata_id = sm.metadata_id
    LEFT JOIN state_attributes sa ON s.attributes_id = sa.attributes_id
    """
    conditions = []
    params = []

    if entity_id:
        if '*' in entity_id:
            entity_id = entity_id.replace('*', '%')
            conditions.append("sm.entity_id LIKE ?")
            params.append(entity_id)
        else:
            conditions.append("sm.entity_id = ?")
            params.append(entity_id)

    if start_time:
        conditions.append("s.last_changed_ts >= ?")
        params.append(start_time.timestamp())

    if end_time:
        conditions.append("s.last_changed_ts <= ?")
        params.append(end_time.timestamp())

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY s.last_changed_ts DESC"

    if limit:
        query += " LIMIT ?"
        params.append(limit)

    return await self.execute_query(query, tuple(params))
```

#### 2. Update MySQL History Query
**File**: `ha_tools/lib/database.py`

Replace `_get_entity_states_mysql` method (lines 256-294):

```python
async def _get_entity_states_mysql(self, entity_id: Optional[str],
                                 start_time: Optional[datetime],
                                 end_time: Optional[datetime],
                                 limit: Optional[int]) -> List[Dict[str, Any]]:
    """Get entity states from MySQL database (modern schema with states_meta)."""
    query = """
    SELECT
        sm.entity_id,
        s.state,
        FROM_UNIXTIME(s.last_changed_ts) as last_changed,
        FROM_UNIXTIME(s.last_updated_ts) as last_updated,
        sa.shared_attrs as attributes
    FROM states s
    INNER JOIN states_meta sm ON s.metadata_id = sm.metadata_id
    LEFT JOIN state_attributes sa ON s.attributes_id = sa.attributes_id
    """
    conditions = []
    params = []

    if entity_id:
        if '*' in entity_id:
            entity_id = entity_id.replace('*', '%')
            conditions.append("sm.entity_id LIKE %s")
            params.append(entity_id)
        else:
            conditions.append("sm.entity_id = %s")
            params.append(entity_id)

    if start_time:
        conditions.append("s.last_changed_ts >= %s")
        params.append(start_time.timestamp())

    if end_time:
        conditions.append("s.last_changed_ts <= %s")
        params.append(end_time.timestamp())

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY s.last_changed_ts DESC"

    if limit:
        query += " LIMIT %s"
        params.append(limit)

    return await self.execute_query(query, tuple(params))
```

#### 3. Update PostgreSQL History Query
**File**: `ha_tools/lib/database.py`

Replace `_get_entity_states_postgresql` method (lines 296-334):

```python
async def _get_entity_states_postgresql(self, entity_id: Optional[str],
                                      start_time: Optional[datetime],
                                      end_time: Optional[datetime],
                                      limit: Optional[int]) -> List[Dict[str, Any]]:
    """Get entity states from PostgreSQL database (modern schema with states_meta)."""
    query = """
    SELECT
        sm.entity_id,
        s.state,
        to_timestamp(s.last_changed_ts) as last_changed,
        to_timestamp(s.last_updated_ts) as last_updated,
        sa.shared_attrs as attributes
    FROM states s
    INNER JOIN states_meta sm ON s.metadata_id = sm.metadata_id
    LEFT JOIN state_attributes sa ON s.attributes_id = sa.attributes_id
    """
    conditions = []
    params = []
    param_idx = 1

    if entity_id:
        if '*' in entity_id:
            entity_id = entity_id.replace('*', '%')
            conditions.append(f"sm.entity_id LIKE ${param_idx}")
            params.append(entity_id)
            param_idx += 1
        else:
            conditions.append(f"sm.entity_id = ${param_idx}")
            params.append(entity_id)
            param_idx += 1

    if start_time:
        conditions.append(f"s.last_changed_ts >= ${param_idx}")
        params.append(start_time.timestamp())
        param_idx += 1

    if end_time:
        conditions.append(f"s.last_changed_ts <= ${param_idx}")
        params.append(end_time.timestamp())
        param_idx += 1

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY s.last_changed_ts DESC"

    if limit:
        query += f" LIMIT ${param_idx}"
        params.append(limit)

    return await self.execute_query(query, tuple(params))
```

### Success Criteria:

#### Automated Verification:
- [x] Unit tests pass: `uv run pytest tests/unit/`
- [x] Integration tests pass: `uv run pytest tests/integration/`

#### Manual Verification:
- [x] `uv run ha-tools entities --search "sensor.batteries_forcible_charge" --include history --history 12h` returns history data with `history_count > 0`
- [x] Query works against production Home Assistant database

**Implementation Note**: After completing this phase and all automated verification passes, pause here for manual confirmation that the database queries work against your production Home Assistant.

**Note**: Additional fix required - `last_changed_ts` is often NULL, so queries must use `COALESCE(last_changed_ts, last_updated_ts)` for filtering.

---

## Phase 2: Improve UX - Auto-enable History with `--history` Flag

### Overview
Make `--history` flag automatically enable history fetching, so users don't need both `--history` and `--include history`.

### Changes Required:

#### 1. Auto-add "history" to include_options when history flag is used
**File**: `ha_tools/commands/entities.py`

After line 95 (after parsing `history_timeframe`), add:

```python
# Parse history timeframe
history_timeframe = None
if history:
    history_timeframe = _parse_timeframe(history)
    # Auto-include history when --history is specified
    if "history" not in include_options:
        include_options = include_options | {"history"}
```

Note: This needs to happen after `include_options` is parsed, so the change should be:

**Replace lines 89-95**:
```python
# Parse include options
include_options = _parse_include_options(include)

# Parse history timeframe
history_timeframe = None
if history:
    history_timeframe = _parse_timeframe(history)
    # Auto-include history when --history is specified
    include_options = include_options | {"history"}
```

### Success Criteria:

#### Automated Verification:
- [x] Unit tests pass: `uv run pytest tests/unit/`
- [x] Integration tests pass: `uv run pytest tests/integration/`

#### Manual Verification:
- [x] `uv run ha-tools entities --search "sensor.*" --history 12h` works (without `--include history`)
- [x] `uv run ha-tools entities --search "sensor.*" --include history --history 12h` still works (backwards compatible)

---

## Phase 3: Improve Error Handling

### Overview
Replace silent `pass` statements with proper error logging to aid debugging.

### Changes Required:

#### 1. Add proper error handling for history fetching
**File**: `ha_tools/commands/entities.py`

Replace lines 216-224:

```python
# History fetching (if needed)
if "history" in include_options and history_timeframe:
    try:
        history_records = await db.get_entity_states(
            entity_data["entity_id"], history_timeframe, None, 10
        )
        entity_data["history"] = history_records
        entity_data["history_count"] = len(history_records)
    except Exception as e:
        # Log the error but continue processing other entities
        entity_data["history"] = []
        entity_data["history_count"] = 0
        entity_data["history_error"] = str(e)
```

#### 2. Add database connection status to output (optional enhancement)
**File**: `ha_tools/commands/entities.py`

In `_run_entities_command`, after database context manager enters, add check:

```python
async with DatabaseManager(config.database) as db:
    if not db.is_connected():
        print_info("Database not available - history features will be limited")
```

### Success Criteria:

#### Automated Verification:
- [x] Unit tests pass: `uv run pytest tests/unit/`

#### Manual Verification:
- [ ] Database errors are visible in output rather than silently swallowed
- [ ] Command still completes even when database has issues

---

## Testing Strategy

### Unit Tests:
- Mock database queries to test new schema structure
- Test `--history` auto-enabling `include history`
- Test error handling paths

### Integration Tests:
- Test against actual Home Assistant database with modern schema
- Verify history data is returned correctly

### Manual Testing Steps:
1. Run `uv run ha-tools entities --search "sensor.batteries_forcible_charge" --history 12h`
2. Verify `history_count` is greater than 0
3. Run with `--format json` to inspect actual history records
4. Test with different timeframes (1h, 24h, 7d)

## References

- [Home Assistant Database Documentation](https://www.home-assistant.io/docs/backend/database)
- [Home Assistant States Schema](https://data.home-assistant.io/docs/states/)
- [Database Schema Changes 2024.8](https://github.com/home-assistant/core/issues/123358)
