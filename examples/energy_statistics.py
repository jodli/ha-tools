"""Example: daily energy consumption + cost from raw long-term statistics.

Mirrors pv_amortisation.ipynb, but via the library — no hand-written SQL and no
hardcoded credentials. ``run()`` returns DataFrames for the integration test.

Run against the real DB:  python examples/energy_statistics.py
"""

from __future__ import annotations

import pandas as pd

import ha_tools

ENTITY = "sensor.erdgeschoss_energieverbrauch_total"
STROMPREIS = 0.29  # EUR/kWh Netzbezug


def run(since: str = "2025-01-01") -> dict[str, pd.DataFrame]:
    stats = ha_tools.load_statistics(ENTITY, since=since)
    stats = stats[stats.statistic_id == ENTITY].copy()
    stats["day"] = pd.to_datetime(stats["start"]).dt.date

    # The statistics table stores a running total; differencing the last reading
    # per day gives that day's consumption.
    daily = stats.groupby("day")["sum"].last().diff().dropna().rename("kwh").to_frame()
    daily["cost_eur"] = daily["kwh"] * STROMPREIS
    return {"statistics": stats, "daily": daily}


if __name__ == "__main__":
    result = run()
    print(result["daily"])
