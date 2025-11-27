"""
Registry loading and management for Home Assistant.

Handles entity, area, and device registries with fallback options.
Provides ID-to-name mapping and metadata extraction.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ..config import HaToolsConfig
from .output import print_warning


class RegistryManager:
    """Manages Home Assistant registry data."""

    def __init__(self, config: HaToolsConfig):
        self.config = config
        self._entity_registry: Optional[List[Dict[str, Any]]] = None
        self._area_registry: Optional[List[Dict[str, Any]]] = None
        self._device_registry: Optional[List[Dict[str, Any]]] = None
        self._entity_id_to_name: Optional[Dict[str, str]] = None
        self._area_id_to_name: Optional[Dict[str, str]] = None

    @property
    def storage_path(self) -> Path:
        """Get the path to Home Assistant storage directory."""
        return Path(self.config.ha_config_path) / ".storage"

    def _load_registry_file(self, filename: str) -> Optional[Dict[str, Any]]:
        """Load a registry file from storage."""
        registry_path = self.storage_path / filename
        try:
            if registry_path.exists():
                with open(registry_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return data.get("data", {})
            else:
                print_warning(f"Registry file not found: {registry_path}")
                return None
        except Exception as e:
            print_warning(f"Failed to load registry {filename}: {e}")
            return None

    async def load_entity_registry(self, fallback_api: Optional[Any] = None) -> List[Dict[str, Any]]:
        """Load entity registry from storage or API fallback."""
        if self._entity_registry is not None:
            return self._entity_registry

        # Try loading from storage first
        registry_data = self._load_registry_file("core.entity_registry")
        if registry_data and "entities" in registry_data:
            self._entity_registry = registry_data["entities"]
        else:
            # Fallback to API
            if fallback_api:
                try:
                    self._entity_registry = await fallback_api.get_entity_registry()
                except Exception as e:
                    print_warning(f"Failed to load entity registry from API: {e}")
                    self._entity_registry = []
            else:
                self._entity_registry = []

        return self._entity_registry

    async def load_area_registry(self, fallback_api: Optional[Any] = None) -> List[Dict[str, Any]]:
        """Load area registry from storage or API fallback."""
        if self._area_registry is not None:
            return self._area_registry

        # Try loading from storage first
        registry_data = self._load_registry_file("core.area_registry")
        if registry_data and "areas" in registry_data:
            self._area_registry = registry_data["areas"]
        else:
            # Fallback to API
            if fallback_api:
                try:
                    self._area_registry = await fallback_api.get_area_registry()
                except Exception as e:
                    print_warning(f"Failed to load area registry from API: {e}")
                    self._area_registry = []
            else:
                self._area_registry = []

        return self._area_registry

    async def load_device_registry(self, fallback_api: Optional[Any] = None) -> List[Dict[str, Any]]:
        """Load device registry from storage or API fallback."""
        if self._device_registry is not None:
            return self._device_registry

        # Try loading from storage first
        registry_data = self._load_registry_file("core.device_registry")
        if registry_data and "devices" in registry_data:
            self._device_registry = registry_data["devices"]
        else:
            # Fallback to API
            if fallback_api:
                try:
                    self._device_registry = await fallback_api.get_device_registry()
                except Exception as e:
                    print_warning(f"Failed to load device registry from API: {e}")
                    self._device_registry = []
            else:
                self._device_registry = []

        return self._device_registry

    async def load_all_registries(self, fallback_api: Optional[Any] = None) -> None:
        """Load all registries."""
        await self.load_entity_registry(fallback_api)
        await self.load_area_registry(fallback_api)
        await self.load_device_registry(fallback_api)

    async def get_entity_name(self, entity_id: str, fallback_api: Optional[Any] = None) -> str:
        """Get friendly name for entity ID."""
        if self._entity_id_to_name is None:
            await self._build_entity_mappings(fallback_api)

        return self._entity_id_to_name.get(entity_id, entity_id)

    async def get_area_name(self, area_id: str, fallback_api: Optional[Any] = None) -> str:
        """Get friendly name for area ID."""
        if self._area_id_to_name is None:
            await self._build_area_mappings(fallback_api)

        return self._area_id_to_name.get(area_id, area_id)

    async def _build_entity_mappings(self, fallback_api: Optional[Any] = None) -> None:
        """Build entity ID to name mappings."""
        self._entity_id_to_name = {}
        entity_registry = await self.load_entity_registry(fallback_api)

        for entity in entity_registry:
            entity_id = entity.get("entity_id")
            if entity_id:  # Only process if entity_id exists
                # Use friendly_name if available, otherwise generate from entity_id
                friendly_name = entity.get("friendly_name")
                if friendly_name:
                    self._entity_id_to_name[entity_id] = friendly_name
                else:
                    # Generate human-readable name from entity_id
                    if "." in entity_id:
                        domain, object_id = entity_id.split(".", 1)
                        name = object_id.replace("_", " ").title()
                        self._entity_id_to_name[entity_id] = name

    async def _build_area_mappings(self, fallback_api: Optional[Any] = None) -> None:
        """Build area ID to name mappings."""
        self._area_id_to_name = {}
        area_registry = await self.load_area_registry(fallback_api)

        for area in area_registry:
            area_id = area.get("area_id")
            if area_id:  # Only process if area_id exists
                name = area.get("name", area_id)
                self._area_id_to_name[area_id] = name

    def get_entities_by_domain(self, domain: str) -> List[Dict[str, Any]]:
        """Get all entities for a specific domain."""
        if not self._entity_registry:
            return []

        return [
            entity for entity in self._entity_registry
            if entity["entity_id"].startswith(f"{domain}.")
        ]

    def get_entities_by_area(self, area_id: str) -> List[Dict[str, Any]]:
        """Get all entities in a specific area."""
        if not self._entity_registry:
            return []

        return [
            entity for entity in self._entity_registry
            if entity.get("area_id") == area_id
        ]

    def get_entities_by_device(self, device_id: str) -> List[Dict[str, Any]]:
        """Get all entities for a specific device."""
        if not self._entity_registry:
            return []

        return [
            entity for entity in self._entity_registry
            if entity.get("device_id") == device_id
        ]

    def get_device_by_area(self, area_id: str) -> List[Dict[str, Any]]:
        """Get all devices in a specific area."""
        if not self._device_registry:
            return []

        return [
            device for device in self._device_registry
            if area_id in device.get("area_id", [])
        ]

    def search_entities(self, pattern: str, search_fields: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Search entities by pattern."""
        if not self._entity_registry:
            return []

        if search_fields is None:
            search_fields = ["entity_id", "friendly_name", "original_name"]

        pattern_lower = pattern.lower().replace("*", "")
        results = []

        for entity in self._entity_registry:
            for field in search_fields:
                value = entity.get(field, "")
                if value and pattern_lower in value.lower():
                    results.append(entity)
                    break

        return results

    def get_entity_metadata(self, entity_id: str) -> Dict[str, Any]:
        """Get comprehensive metadata for an entity."""
        if not self._entity_registry:
            return {}

        for entity in self._entity_registry:
            if entity["entity_id"] == entity_id:
                return entity

        return {}

    def get_area_metadata(self, area_id: str) -> Dict[str, Any]:
        """Get comprehensive metadata for an area."""
        if not self._area_registry:
            return {}

        for area in self._area_registry:
            # Safely check if area has area_id key and compare
            if area.get("area_id") == area_id:
                return area

        return {}

    def get_device_metadata(self, device_id: str) -> Dict[str, Any]:
        """Get comprehensive metadata for a device."""
        if not self._device_registry:
            return {}

        for device in self._device_registry:
            # Safely check if device has device_id key and compare
            if device.get("device_id") == device_id:
                return device

        return {}

    def get_entity_statistics(self) -> Dict[str, Any]:
        """Get statistics about loaded entities."""
        if not self._entity_registry:
            return {}

        domains = {}
        disabled = 0
        hidden = 0

        for entity in self._entity_registry:
            domain = entity["entity_id"].split(".")[0]
            domains[domain] = domains.get(domain, 0) + 1

            if entity.get("disabled_by"):
                disabled += 1
            if entity.get("hidden_by"):
                hidden += 1

        return {
            "total_entities": len(self._entity_registry),
            "domains": domains,
            "disabled_entities": disabled,
            "hidden_entities": hidden,
            "enabled_entities": len(self._entity_registry) - disabled - hidden,
        }

    def get_area_statistics(self) -> Dict[str, Any]:
        """Get statistics about loaded areas."""
        if not self._area_registry:
            return {}

        return {
            "total_areas": len(self._area_registry),
            "area_names": [area.get("name", area["area_id"]) for area in self._area_registry],
        }

    def get_device_statistics(self) -> Dict[str, Any]:
        """Get statistics about loaded devices."""
        if not self._device_registry:
            return {}

        manufacturers = {}
        models = {}

        for device in self._device_registry:
            manufacturer = device.get("manufacturer", "Unknown")
            model = device.get("model", "Unknown")
            manufacturers[manufacturer] = manufacturers.get(manufacturer, 0) + 1
            models[model] = models.get(model, 0) + 1

        return {
            "total_devices": len(self._device_registry),
            "manufacturers": manufacturers,
            "models": models,
        }