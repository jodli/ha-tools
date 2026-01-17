"""
Home Assistant REST API client.

Provides async access to Home Assistant API with authentication and rate limiting.
Used for real-time state and validation when database access isn't sufficient.
"""

import json
from datetime import datetime
from typing import Any

import aiohttp
from aiohttp import ClientSession, ClientTimeout, WSMsgType

from ..config import HomeAssistantConfig
from .output import print_warning


class HomeAssistantAPI:
    """Async Home Assistant REST API client."""

    def __init__(self, config: HomeAssistantConfig):
        self.config = config
        self._session: ClientSession | None = None
        self._base_url = config.url.rstrip("/")
        self._headers = {
            "Authorization": f"Bearer {config.access_token}",
            "Content-Type": "application/json",
        }
        self._timeout = ClientTimeout(total=config.timeout)

        # WebSocket state
        self._ws: Any = None
        self._ws_message_id = 0
        # Build WebSocket URL from HTTP URL
        ws_scheme = "wss://" if self._base_url.startswith("https://") else "ws://"
        http_scheme = "https://" if self._base_url.startswith("https://") else "http://"
        self._ws_url = self._base_url.replace(http_scheme, ws_scheme) + "/api/websocket"

    async def _get_session(self) -> ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = ClientSession(
                headers=self._headers,
                timeout=self._timeout,
                connector=aiohttp.TCPConnector(limit=10, limit_per_host=5),
            )
        return self._session

    async def close(self) -> None:
        """Close the aiohttp session and WebSocket."""
        await self._ws_close()
        if self._session and not self._session.closed:
            await self._session.close()

    async def test_connection(self) -> None:
        """Test API connectivity and authentication."""
        session = await self._get_session()
        async with session.get(f"{self._base_url}/api/") as response:
            if response.status == 200:
                data = await response.json()
                if data.get("message") == "API running.":
                    return
            raise RuntimeError(f"API test failed: HTTP {response.status}")

    async def get_states(self) -> list[dict[str, Any]]:
        """Get all current entity states from Home Assistant."""
        session = await self._get_session()
        async with session.get(f"{self._base_url}/api/states") as response:
            if response.status != 200:
                raise RuntimeError(f"Failed to get states: HTTP {response.status}")
            return await response.json()

    async def get_entity_state(self, entity_id: str) -> dict[str, Any] | None:
        """Get current state for a specific entity."""
        session = await self._get_session()
        async with session.get(f"{self._base_url}/api/states/{entity_id}") as response:
            if response.status == 404:
                return None
            if response.status != 200:
                raise RuntimeError(
                    f"Failed to get entity {entity_id}: HTTP {response.status}"
                )
            return await response.json()

    async def get_entity_history(
        self,
        entity_id: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        minimal_response: bool = True,
    ) -> list[dict[str, Any]]:
        """
        Get historical state data for an entity.

        Note: This is significantly slower than direct database access.
        Use only when database access is not available.
        """
        session = await self._get_session()
        url = f"{self._base_url}/api/history/period/{entity_id}"

        params = {}
        if start_time:
            params["filter_start_time"] = start_time.isoformat()
        if end_time:
            params["filter_end_time"] = end_time.isoformat()
        if minimal_response:
            params["minimal_response"] = "true"

        async with session.get(url, params=params) as response:
            if response.status != 200:
                raise RuntimeError(
                    f"Failed to get history for {entity_id}: HTTP {response.status}"
                )
            return await response.json()

    async def get_config(self) -> dict[str, Any]:
        """Get Home Assistant configuration."""
        session = await self._get_session()
        async with session.get(f"{self._base_url}/api/config") as response:
            if response.status != 200:
                raise RuntimeError(f"Failed to get config: HTTP {response.status}")
            return await response.json()

    async def validate_config(self) -> dict[str, Any]:
        """Validate Home Assistant configuration."""
        session = await self._get_session()
        async with session.post(
            f"{self._base_url}/api/config/core/check_config"
        ) as response:
            if response.status != 200:
                raise RuntimeError(f"Failed to validate config: HTTP {response.status}")
            return await response.json()

    async def get_logs(self, levels: set[str] | None = None) -> list[dict[str, Any]]:
        """
        Get Home Assistant logs from the error log.

        Args:
            levels: Set of log levels to include (error, warning, critical, info, debug).
                    Defaults to {"error", "warning"} if None.

        Tries multiple endpoints:
        1. /api/error_log (standard HA installations)
        2. /api/hassio/core/logs (HA OS/Supervised installations)

        Returns:
            List of log dictionaries with keys: timestamp, level, source, message, context
        """
        if levels is None:
            levels = {"error", "warning"}

        session = await self._get_session()

        # Try standard error_log endpoint first
        try:
            async with session.get(f"{self._base_url}/api/error_log") as response:
                if response.status == 200:
                    log_text = await response.text()
                    logs = self._parse_error_log(log_text, levels)
                    if logs:
                        return logs
        except Exception:
            pass

        # Fall back to Supervisor API for HA OS/Supervised
        try:
            async with session.get(
                f"{self._base_url}/api/hassio/core/logs"
            ) as response:
                if response.status == 200:
                    log_text = await response.text()
                    # Strip ANSI color codes from Supervisor logs
                    log_text = self._strip_ansi_codes(log_text)
                    return self._parse_error_log(log_text, levels)
        except Exception as e:
            print_warning(f"Could not fetch logs: {e}")

        return []

    def _strip_ansi_codes(self, text: str) -> str:
        """Remove ANSI escape codes from text."""
        import re

        ansi_pattern = re.compile(r"\x1b\[[0-9;]*m")
        return ansi_pattern.sub("", text)

    def _parse_error_log(self, log_text: str, levels: set[str]) -> list[dict[str, Any]]:
        """Parse error log text into structured log records."""
        import re
        from datetime import datetime

        logs: list[dict[str, Any]] = []
        current_log: dict[str, Any] | None = None

        for line in log_text.splitlines():
            if not line.strip():
                continue

            # Match log line format: "2024-01-15 10:30:45.123 ERROR (MainThread) [component] Message"
            match = re.match(
                r"(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}(?:\.\d+)?)\s+"
                r"(ERROR|WARNING|CRITICAL|INFO|DEBUG)\s+"
                r"\(([^)]+)\)\s+"
                r"\[([^\]]+)\]\s*"
                r"(.*)",
                line,
            )

            if match:
                # Save previous log if exists
                if current_log:
                    logs.append(current_log)

                timestamp_str, level, thread, source, message = match.groups()
                try:
                    timestamp = datetime.fromisoformat(timestamp_str.replace(" ", "T"))
                except ValueError:
                    timestamp = datetime.now()

                current_log = {
                    "timestamp": timestamp,
                    "level": level,
                    "source": source,
                    "message": message,
                    "context": [],
                }
            elif current_log:
                # Continuation line (traceback, etc.)
                current_log["context"].append(line)

        # Add final log
        if current_log:
            logs.append(current_log)

        # Filter by requested levels (convert to uppercase for comparison)
        upper_levels = {lvl.upper() for lvl in levels}
        logs = [log for log in logs if log["level"] in upper_levels]

        return logs[-50:]  # Return most recent 50 entries

    async def _ws_connect(self) -> bool:
        """
        Connect to WebSocket and authenticate.

        Returns True if connection and auth successful, False otherwise.
        """
        try:
            session = await self._get_session()
            self._ws = await session.ws_connect(self._ws_url)

            # Wait for auth_required message
            msg = await self._ws.receive()
            if msg.type != WSMsgType.TEXT:
                return False

            data = json.loads(msg.data)
            if data.get("type") != "auth_required":
                return False

            # Send auth
            await self._ws.send_json(
                {
                    "type": "auth",
                    "access_token": self.config.access_token,
                }
            )

            # Wait for auth result
            msg = await self._ws.receive()
            if msg.type != WSMsgType.TEXT:
                return False

            data = json.loads(msg.data)
            return data.get("type") == "auth_ok"

        except Exception:
            return False

    async def _ws_send_command(
        self, command_type: str, **kwargs: Any
    ) -> dict[str, Any] | None:
        """Send a WebSocket command and wait for response."""
        if not self._ws or self._ws.closed:
            return None

        self._ws_message_id += 1
        message = {"id": self._ws_message_id, "type": command_type, **kwargs}

        await self._ws.send_json(message)

        # Wait for response with matching ID
        while True:
            msg = await self._ws.receive()
            if msg.type != WSMsgType.TEXT:
                return None

            data = json.loads(msg.data)
            if data.get("id") == self._ws_message_id:
                return data

    async def _ws_close(self) -> None:
        """Close WebSocket connection."""
        if self._ws and not self._ws.closed:
            await self._ws.close()
            self._ws = None

    async def get_system_logs_ws(
        self, levels: set[str] | None = None
    ) -> list[dict[str, Any]]:
        """
        Get system logs via WebSocket system_log/list command.

        This provides the same structured data as Home Assistant's UI,
        including occurrence counts and first/last timestamps.

        Args:
            levels: Set of log levels to include. Defaults to {"error", "warning"}.

        Returns:
            List of log dictionaries with keys: timestamp, level, source,
            source_location, message, context, count, first_occurred
        """
        if levels is None:
            levels = {"error", "warning"}

        upper_levels = {lvl.upper() for lvl in levels}

        # Connect if not already connected
        if not self._ws or self._ws.closed:
            if not await self._ws_connect():
                return []

        response = await self._ws_send_command("system_log/list")
        if not response or not response.get("success"):
            return []

        result = response.get("result", [])

        # Transform to match REST API format with additional fields
        logs = []
        for entry in result:
            level = entry.get("level", "error").upper()
            if level not in upper_levels:
                continue

            # Parse source tuple [filename, line_number]
            source = entry.get("source", ["", 0])
            if isinstance(source, list) and len(source) >= 2:
                source_location = f"{source[0]}:{source[1]}"
            else:
                source_location = str(source)

            # Get most recent message from the message list
            messages = entry.get("message", [])
            message = messages[0] if messages else ""

            # Convert Unix timestamps to datetime
            timestamp = entry.get("timestamp", 0)
            first_occurred = entry.get("first_occurred", timestamp)

            logs.append(
                {
                    "timestamp": datetime.fromtimestamp(timestamp)
                    if timestamp
                    else datetime.now(),
                    "level": level,
                    "source": entry.get("name", ""),
                    "source_location": source_location,
                    "message": message,
                    "context": messages[1:] if len(messages) > 1 else [],
                    "exception": entry.get("exception", ""),
                    "count": entry.get("count", 1),
                    "first_occurred": datetime.fromtimestamp(first_occurred)
                    if first_occurred
                    else None,
                }
            )

        return logs

    async def get_services(self) -> dict[str, Any]:
        """Get all available services."""
        session = await self._get_session()
        async with session.get(f"{self._base_url}/api/services") as response:
            if response.status != 200:
                raise RuntimeError(f"Failed to get services: HTTP {response.status}")
            return await response.json()

    async def get_entity_registry(self) -> list[dict[str, Any]]:
        """Get entity registry data."""
        try:
            session = await self._get_session()
            async with session.get(
                f"{self._base_url}/api/config/registry/entity"
            ) as response:
                if response.status == 200:
                    return await response.json()
        except Exception as e:
            print_warning(f"Could not fetch entity registry via API: {e}")
        return []

    async def get_area_registry(self) -> list[dict[str, Any]]:
        """Get area registry data."""
        try:
            session = await self._get_session()
            async with session.get(
                f"{self._base_url}/api/config/registry/area"
            ) as response:
                if response.status == 200:
                    return await response.json()
        except Exception as e:
            print_warning(f"Could not fetch area registry via API: {e}")
        return []

    async def get_device_registry(self) -> list[dict[str, Any]]:
        """Get device registry data."""
        try:
            session = await self._get_session()
            async with session.get(
                f"{self._base_url}/api/config/registry/device"
            ) as response:
                if response.status == 200:
                    return await response.json()
        except Exception as e:
            print_warning(f"Could not fetch device registry via API: {e}")
        return []

    async def call_service(
        self, domain: str, service: str, service_data: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Call a Home Assistant service."""
        session = await self._get_session()
        url = f"{self._base_url}/api/services/{domain}/{service}"
        data = service_data or {}

        async with session.post(url, json=data) as response:
            if response.status not in [200, 201]:
                raise RuntimeError(
                    f"Failed to call service {domain}.{service}: HTTP {response.status}"
                )
            return await response.json()

    async def reload_core_config(self) -> None:
        """Reload core Home Assistant configuration."""
        await self.call_service("homeassistant", "reload_core_config")

    async def get_integration_info(self) -> dict[str, Any]:
        """Get information about installed integrations."""
        try:
            session = await self._get_session()
            async with session.get(
                f"{self._base_url}/api/config/integrations"
            ) as response:
                if response.status == 200:
                    return await response.json()
        except Exception as e:
            print_warning(f"Could not fetch integration info: {e}")
        return {}

    async def get_statistics(
        self,
        statistic_ids: list[str] | None = None,
        period: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """Get long-term statistics."""
        session = await self._get_session()
        url = f"{self._base_url}/api/history/period/statistics"

        params = {}
        if statistic_ids:
            params["statistic_id"] = ",".join(statistic_ids)
        if period:
            params["period"] = period
        if start_time:
            params["start_time"] = start_time.isoformat()
        if end_time:
            params["end_time"] = end_time.isoformat()

        async with session.get(url, params=params) as response:
            if response.status != 200:
                raise RuntimeError(f"Failed to get statistics: HTTP {response.status}")
            return await response.json()

    def _parse_entity_id(self, entity_id: str) -> tuple[str, str]:
        """Parse entity ID into domain and object_id."""
        if "." not in entity_id:
            raise ValueError(f"Invalid entity ID: {entity_id}")
        domain, object_id = entity_id.split(".", 1)
        return domain, object_id

    async def __aenter__(self) -> "HomeAssistantAPI":
        """Async context manager entry."""
        await self._get_session()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        """Async context manager exit."""
        await self.close()
