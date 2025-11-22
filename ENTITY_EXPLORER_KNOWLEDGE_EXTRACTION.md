# Entity Explorer Knowledge Extraction

This document captures the key knowledge, patterns, and implementation details from the `entity_explorer.py` script for reuse in CLI tools.

## Overview

The entity_explorer.py script is a sophisticated Home Assistant entity analysis tool that loads entity and area registries, categorizes entities by domain and area, and provides multiple search and filtering mechanisms. It serves as an excellent reference for building HA registry analysis tools.

## 1. Data Loading Patterns

### Registry File Locations
```python
# Entity registry location
registry_path = config_path / ".storage" / "core.entity_registry"

# Area registry location
area_path = config_path / ".storage" / "core.area_registry"
```

### Registry Loading Functions
```python
def load_entity_registry(config_path: Path) -> Optional[Dict]:
    """Load and parse the entity registry file."""
    registry_path = config_path / ".storage" / "core.entity_registry"

    if not registry_path.exists():
        print(f"Error: Entity registry not found at {registry_path}")
        return None

    try:
        with open(registry_path, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error reading entity registry: {e}")
        return None

def load_area_registry(config_path: Path) -> Dict[str, str]:
    """Load area names from area registry."""
    area_path = config_path / ".storage" / "core.area_registry"
    area_names = {}

    if area_path.exists():
        try:
            with open(area_path, "r") as f:
                area_data = json.load(f)
                for area in area_data.get("data", {}).get("areas", []):
                    area_names[area["id"]] = area["name"]
        except Exception as e:
            print(f"Warning: Could not load area names: {e}")

    return area_names
```

**Key Patterns:**
- **Graceful error handling**: Registry files may not exist, handle gracefully
- **Path validation**: Always check file existence before loading
- **Data extraction**: Use safe `.get()` methods with defaults for nested JSON structures
- **ID-to-name mapping**: Create lookup dictionaries for efficient area name resolution

## 2. Entity Categorization Logic

### Entity Filtering Strategy
```python
# Skip disabled/hidden entities
if entity.get("disabled_by") or entity.get("hidden_by"):
    continue
```

### Display Name Resolution
```python
def get_entity_display_name(entity: Dict) -> str:
    """Get the best display name for an entity."""
    if entity.get("name"):
        return entity["name"]
    elif entity.get("original_name"):
        return entity["original_name"]
    else:
        # Extract from entity_id
        return entity["entity_id"].split(".")[-1].replace("_", " ").title()
```

**Key Logic:**
1. Priority order: `name` → `original_name` → derived from `entity_id`
2. Fallback transformation: domain_name_entity_name → "Entity Name" (title case)

### Domain Classification System
```python
# Domains that are commonly used in automations
key_domains = {
    "climate", "switch", "light", "fan", "cover", "lock", "camera",
    "person", "device_tracker", "binary_sensor", "sensor",
    "media_player", "scene", "script", "input_boolean",
    "input_select", "input_number",
}
```

### Multi-dimensional Categorization
```python
def categorize_entities(entities: List[Dict], area_names: Dict[str, str]) -> Dict:
    """Categorize entities by domain and area."""
    by_domain = defaultdict(list)
    by_area = defaultdict(list)
    automation_relevant = defaultdict(list)

    for entity in entities:
        # Filtering logic...

        entity_info = {
            "entity_id": entity_id,
            "name": display_name,
            "area": area_name,
            "device_class": device_class,
            "platform": entity.get("platform"),
            "unit": entity.get("unit_of_measurement"),
        }

        # Multi-category assignment
        by_domain[domain].append(entity_info)
        by_area[area_name].append(entity_info)

        # Smart automation relevance filtering
        if domain in key_domains:
            automation_relevant[domain].append(entity_info)
        elif domain == "sensor" and device_class in [
            "temperature", "humidity", "motion", "door", "window"
        ]:
            automation_relevant["sensor"].append(entity_info)
        # ... more filtering logic
```

**Key Patterns:**
- **Standardized entity structure**: Consistent dictionary format for all entity views
- **Multiple categorization axes**: Domain, area, and automation relevance
- **Smart filtering**: Device class-based relevance determination
- **Comprehensive data capture**: Include all relevant metadata fields

## 3. Search and Filtering Algorithms

### Multi-field Search Implementation
```python
def search_entities(categorized: Dict, query: str):
    """Search for entities matching a query."""
    matches = []
    query_lower = query.lower()

    for domain_entities in categorized["by_domain"].values():
        for entity in domain_entities:
            if (
                query_lower in entity["entity_id"].lower()
                or query_lower in entity["name"].lower()
                or (
                    entity.get("device_class")
                    and query_lower in entity["device_class"].lower()
                )
            ):
                matches.append(entity)
```

**Search Fields:**
- Entity ID (exact and partial matching)
- Display name (case-insensitive)
- Device class (for sensors/binary_sensors)

### Domain-based Filtering
```python
domains_to_show = (
    [domain_filter] if domain_filter else sorted(categorized["by_domain"].keys())
)

for domain in domains_to_show:
    if domain not in categorized["by_domain"]:
        print(f"Domain '{domain}' not found")
        continue
    # Process domain...
```

### Area-based Filtering
```python
areas_to_show = (
    [area_filter] if area_filter else sorted(categorized["by_area"].keys())
)

# Additional grouping within areas
by_domain_in_area = defaultdict(list)
for entity in entities:
    domain = entity["entity_id"].split(".")[0]
    by_domain_in_area[domain].append(entity)
```

**Key Patterns:**
- **Flexible filtering**: Support single-item or all-items display
- **Validation**: Check for existence before processing filters
- **Hierarchical grouping**: Support nested categorization (area → domain)
- **Case-insensitive search**: User-friendly search behavior

## 4. Output Formatting and Display Patterns

### Consistent Entity Display Format
```python
def format_entity_display(entity: Dict) -> str:
    """Standardized entity display formatting."""
    area_str = f" | {entity['area']}" if entity["area"] != "No Area" else ""
    unit_str = f" [{entity['unit']}]" if entity.get("unit") else ""
    device_class_str = (
        f" ({entity['device_class']})" if entity.get("device_class") else ""
    )

    return f"{entity['entity_id']}{device_class_str}{unit_str}{area_str}"
```

**Output Format Examples:**
- `light.living_room_main | Living Room`
- `sensor.temperature (temperature) [°C] | Kitchen`
- `switch.outdoor_lights | Garden`

### Summary Statistics Pattern
```python
def print_summary(categorized: Dict):
    """Print a summary of available entities."""
    # Overall stats
    total_entities = sum(
        len(entities) for entities in categorized["by_domain"].values()
    )
    total_domains = len(categorized["by_domain"])
    total_areas = len(categorized["by_area"])

    print("📊 OVERVIEW:")
    print(f"   Total Entities: {total_entities}")
    print(f"   Domains: {total_domains}")
    print(f"   Areas: {total_areas}")
```

### Truncated Display for Overview
```python
# Show a few examples
for entity in entities[:3]:
    area_str = f" ({entity['area']})" if entity["area"] != "No Area" else ""
    unit_str = f" [{entity['unit']}]" if entity.get("unit") else ""
    print(f"     • {entity['entity_id']}{area_str}{unit_str}")

if len(entities) > 3:
    print(f"     ... and {len(entities) - 3} more")
```

**Key Patterns:**
- **Consistent visual hierarchy**: Use headers, indentation, and separators
- **Conditional information display**: Only show non-empty fields
- **Smart truncation**: Show examples + count for large lists
- **Visual indicators**: Use emojis and formatting for better readability
- **Alphabetical sorting**: Consistent ordering for predictability

## 5. Configuration and Argument Handling

### Argument Parser Structure
```python
def main():
    parser = argparse.ArgumentParser(
        description="Explore Home Assistant Entity Registry"
    )
    parser.add_argument(
        "--config", "-c", default="config", help="Path to HA config directory"
    )
    parser.add_argument(
        "--domain", "-d", help="Show only entities from specific domain"
    )
    parser.add_argument("--area", "-a", help="Show only entities from specific area")
    parser.add_argument(
        "--search", "-s", help="Search entities by name/id/device_class"
    )
    parser.add_argument(
        "--full", "-f", action="store_true", help="Show full detailed output"
    )

    args = parser.parse_args()
```

### Path Validation Pattern
```python
config_path = Path(args.config)
if not config_path.exists():
    print(f"Error: Config directory not found: {config_path}")
    return 1
```

### Output Mode Selection Logic
```python
# Show output based on arguments
if args.search:
    search_entities(categorized, args.search)
elif args.domain:
    print_detailed_by_domain(categorized, args.domain)
elif args.area:
    print_by_area(categorized, args.area)
elif args.full:
    print_summary(categorized)
    print_detailed_by_domain(categorized)
    print_by_area(categorized)
else:
    print_summary(categorized)
```

**Key Patterns:**
- **Mutually exclusive options**: Only one primary action at a time
- **Path validation**: Early validation with clear error messages
- **Default behavior**: Sensible default (summary view)
- **Progressive disclosure**: Basic overview by default, detailed view on demand

## 6. Reusable Data Structures

### Standardized Entity Information Structure
```python
entity_info = {
    "entity_id": str,           # "light.living_room_main"
    "name": str,               # "Living Room Main Light"
    "area": str,               # "Living Room" or "No Area"
    "device_class": str,       # "temperature", "motion", None
    "platform": str,           # "knx", "mqtt", "zha"
    "unit": str,               # "°C", "kWh", None
}
```

### Categorized Data Structure
```python
categorized_data = {
    "by_domain": {
        "light": [entity_info, ...],
        "sensor": [entity_info, ...],
        # ... other domains
    },
    "by_area": {
        "Living Room": [entity_info, ...],
        "Kitchen": [entity_info, ...],
        # ... other areas
    },
    "automation_relevant": {
        "light": [entity_info, ...],
        "switch": [entity_info, ...],
        # ... filtered relevant domains
    }
}
```

### Area Name Mapping
```python
area_names = {
    "area_id_123": "Living Room",
    "area_id_456": "Kitchen",
    # ... ID to name mappings
}
```

## 7. Key Implementation Insights

### Performance Considerations
- **Single-pass categorization**: All categorization done in one loop
- **Lazy evaluation**: Only compute and display what's needed
- **Efficient lookups**: Use dictionaries for O(1) area name resolution

### Error Handling Patterns
- **Graceful degradation**: Continue with partial data if registries fail to load
- **User-friendly errors**: Clear error messages with file paths
- **Warning vs Error**: Use warnings for non-critical issues

### Extensibility Design
- **Modular functions**: Each major operation is a separate function
- **Data-driven**: Domain lists and filters can be easily modified
- **Flexible output**: Different display modes for different use cases

## 8. Recommended Reuse Patterns for HA-TOOLS

### Core Functions to Adapt
1. **Registry Loading**: `load_entity_registry()`, `load_area_registry()`
2. **Entity Processing**: `get_entity_display_name()`, `categorize_entities()`
3. **Search/Filter**: `search_entities()`, domain/area filtering logic
4. **Display Formatting**: Entity display formatting, summary statistics

### Data Structures to Reuse
1. **Standard entity info dict**: Consistent metadata structure
2. **Multi-dimensional categorization**: Domain/area/relevance views
3. **Area name mapping**: ID-to-name lookup pattern

### CLI Patterns to Adopt
1. **Argument structure**: Path + filter + display mode options
2. **Output mode selection**: Mutually exclusive primary actions
3. **Progressive disclosure**: Summary → detailed view hierarchy

This extraction provides a solid foundation for building similar entity analysis functionality in the ha-tools CLI while maintaining consistency with established patterns.