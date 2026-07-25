"""ha-tools: load Home Assistant recorder data into pandas for Jupyter analysis.

The library only retrieves raw rows from the HA recorder database; all
calculation/aggregation is left to the notebook. Configure the database
connection once in ``~/.ha-tools-config.yaml`` (never paste credentials into a
notebook).

    from ha_tools import load_states, load_statistics
    df = load_states("sensor.kaffeemaschine_leistung", timeframe="14d")
"""

from .config import DatabaseConfig, HaToolsConfig
from .db import connect, load_states, load_statistics, query

__all__ = [
    "load_states",
    "load_statistics",
    "query",
    "connect",
    "HaToolsConfig",
    "DatabaseConfig",
]

__version__ = "0.2.0"
