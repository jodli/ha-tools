"""
ha-tools - High-performance CLI for AI agents working with Home Assistant configurations.

A lightweight, fast CLI tool that replaces heavy MCP implementations with a hybrid
REST API + direct database access approach for optimal performance.
"""

__version__ = "0.1.0"
__author__ = "Home Assistant Tools"
__description__ = (
    "High-performance CLI for AI agents working with Home Assistant configurations"
)

# Import configuration for convenience
from .config import HaToolsConfig

__all__ = ["HaToolsConfig", "__version__"]
