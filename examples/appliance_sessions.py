"""Example: detect coffee-machine heating sessions from raw power readings.

Mirrors the kaffee_analyse notebook. ``run()`` returns the DataFrames so this
file doubles as an integration test (tests/integration/test_examples.py).

Run against the real DB:  python examples/appliance_sessions.py
"""

from __future__ import annotations

import pandas as pd

import ha_tools

ENTITY = "sensor.kaffeemaschine_leistung"
POWER_THRESHOLD = 100  # Watts above which the machine is actively heating


def run(timeframe: str = "14d") -> dict[str, pd.DataFrame]:
    states = ha_tools.load_states(ENTITY, timeframe=timeframe)
    states = states[states.entity_id == ENTITY].copy()
    states["ts"] = pd.to_datetime(states["last_updated"])
    states["power"] = pd.to_numeric(states["state"], errors="coerce")
    states = states.dropna(subset=["power"]).sort_values("ts")

    active = states[states["power"] >= POWER_THRESHOLD].copy()
    # A gap > 10 minutes starts a new session.
    active["session"] = (active["ts"].diff() > pd.Timedelta(minutes=10)).cumsum()
    sessions = (
        active.groupby("session")["ts"]
        .agg(start="min", end="max")
        .assign(duration_min=lambda d: (d["end"] - d["start"]).dt.total_seconds() / 60)
    )
    return {"states": states, "sessions": sessions}


if __name__ == "__main__":
    result = run()
    print(f"{len(result['sessions'])} heating session(s) detected:")
    print(result["sessions"])
    try:
        import matplotlib.pyplot as plt

        result["states"].set_index("ts")["power"].plot(
            title="Kaffeemaschine Leistung", figsize=(14, 5)
        )
        plt.ylabel("W")
        plt.tight_layout()
        plt.show()
    except ImportError:
        pass
