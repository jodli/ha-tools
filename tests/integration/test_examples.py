"""Integration test: the example scripts run end-to-end against the mock DB.

The examples in ``examples/`` are both the library's usage documentation and
its integration suite. Each is loaded by path and its ``run()`` executed under
the ``fake_db`` fixture; we assert both the resulting DataFrames and the SQL the
library emitted.
"""

import importlib.util
from pathlib import Path

EXAMPLES_DIR = Path(__file__).resolve().parents[2] / "examples"


def _load_example(name: str):
    path = EXAMPLES_DIR / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"example_{name}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_appliance_sessions(fake_db):
    mod = _load_example("appliance_sessions")
    out = mod.run()
    assert {"states", "sessions"} <= set(out)
    assert len(out["states"]) > 0
    assert len(out["sessions"]) >= 1
    assert "FROM states s" in fake_db.executed[-1][0]


def test_energy_statistics(fake_db):
    mod = _load_example("energy_statistics")
    out = mod.run()
    assert len(out["statistics"]) > 0
    assert len(out["daily"]) >= 1
    assert "statistics_meta m ON s.metadata_id = m.id" in fake_db.executed[-1][0]


def test_multi_entity_correlation(fake_db):
    mod = _load_example("multi_entity_correlation")
    out = mod.run()
    assert len(out["pivot"]) > 0
    sql, _ = fake_db.executed[-1]
    assert " OR " in sql  # multi-entity OR clause
