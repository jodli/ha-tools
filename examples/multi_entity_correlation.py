"""Example: align indoor vs outdoor temperature for heating analysis.

Shows multi-entity ``load_states`` with an explicit time window and a pivot into
wide form. ``run()`` returns DataFrames for the integration test.

Run against the real DB:  python examples/multi_entity_correlation.py
"""

from __future__ import annotations

import pandas as pd

import ha_tools

INDOOR = "sensor.kuche_temperatur"
OUTDOOR = "sensor.luftung_aussentemperatur"


def run(start: str = "2026-07-01", end: str = "2026-07-31") -> dict[str, pd.DataFrame]:
    raw = ha_tools.load_states([INDOOR, OUTDOOR], start=start, end=end)
    raw["ts"] = pd.to_datetime(raw["last_updated"])
    raw["value"] = pd.to_numeric(raw["state"], errors="coerce")

    pivot = (
        raw.dropna(subset=["value"])
        .pivot_table(index="ts", columns="entity_id", values="value")
        .sort_index()
    )
    return {"raw": raw, "pivot": pivot}


if __name__ == "__main__":
    result = run()
    print(result["pivot"].head())
