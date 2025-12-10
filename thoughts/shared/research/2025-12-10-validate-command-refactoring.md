---
date: 2025-12-10T12:00:00+01:00
researcher: Claude
git_commit: 09bbd35d7bcd8cb5f8f828f838667c5c5f70d74d
branch: main
repository: ha-tools
topic: "Validate Command Refactoring - Integration Points Analysis"
tags: [research, codebase, validate, yaml, home-assistant]
status: complete
last_updated: 2025-12-10
last_updated_by: Claude
---

# Research: Validate Command Refactoring

**Date**: 2025-12-10T12:00:00+01:00
**Researcher**: Claude
**Git Commit**: 09bbd35d7bcd8cb5f8f828f838667c5c5f70d74d
**Branch**: main
**Repository**: ha-tools

## Research Question

Analyze the validate command to identify:
1. Why `--syntax-only` doesn't work with Home Assistant's custom YAML includes
2. Whether `--fix` command makes sense (conclusion: remove it)
3. How to properly distinguish between "local yaml parsing" and "full validation via Home Assistant API"

## Summary

The current validate command has three main issues:

1. **`--syntax-only` uses `yaml.safe_load()`** which cannot parse HA's custom YAML tags (`!include`, `!secret`, etc.) - files with these tags will fail validation
2. **`--fix` only fixes trivial issues** (trailing whitespace, final newlines) - not useful enough to justify the complexity
3. **The distinction between local/API validation isn't clear** in the current implementation and documentation

### Key Findings

| Aspect | Current State | Required State |
|--------|--------------|----------------|
| YAML Parsing | `yaml.safe_load()` | Custom loader with HA tag support |
| `--fix` flag | Fixes whitespace only | Should be removed |
| Local validation | Basic syntax check | Full HA YAML expansion |
| API validation | Works correctly | Keep as-is |

## Detailed Findings

### 1. Current Implementation Analysis

**Location:** `ha_tools/commands/validate.py`

**Current `--syntax-only` flow:**
```python
# Line 189 - Uses standard PyYAML
yaml.safe_load(content)
```

This fails on any file containing:
- `!include automations.yaml`
- `!include_dir_merge_list automations/`
- `!secret api_password`
- Any other HA custom tag

**Current `--fix` implementation (`validate.py:196-216`):**
- Removes trailing whitespace
- Adds final newline if missing
- That's it - no semantic fixes

### 2. Home Assistant Custom YAML Tags

HA uses these custom YAML constructors:

| Tag | Purpose | Example |
|-----|---------|---------|
| `!include` | Include single file | `automation: !include automations.yaml` |
| `!include_dir_list` | Include directory as list | `scene: !include_dir_list scenes/` |
| `!include_dir_merge_list` | Merge files into single list | `automation: !include_dir_merge_list automations/` |
| `!include_dir_named` | Include as dict (filename = key) | `script: !include_dir_named scripts/` |
| `!include_dir_merge_named` | Merge dicts from files | `group: !include_dir_merge_named groups/` |
| `!secret` | Reference from secrets.yaml | `password: !secret db_password` |
| `!env_var` | Environment variable (Core only) | `key: !env_var API_KEY` |

### 3. What's Needed for Proper Local Validation

**Option A: Custom YAML Loader (Recommended)**

Create `ha_tools/lib/yaml_loader.py`:

```python
import yaml
from pathlib import Path
from typing import Any, Dict, List, Optional

class HAYAMLLoader(yaml.SafeLoader):
    """Custom YAML loader with Home Assistant tag support."""
    
    def __init__(self, stream, config_path: Path, secrets: Optional[Dict[str, str]] = None):
        super().__init__(stream)
        self.config_path = config_path
        self.secrets = secrets or {}

def construct_include(loader: HAYAMLLoader, node: yaml.Node) -> Any:
    """Handle !include tag."""
    path = loader.config_path / loader.construct_scalar(node)
    with open(path) as f:
        return yaml.load(f, Loader=lambda s: HAYAMLLoader(s, path.parent, loader.secrets))

def construct_include_dir_list(loader: HAYAMLLoader, node: yaml.Node) -> List[Any]:
    """Handle !include_dir_list tag."""
    dir_path = loader.config_path / loader.construct_scalar(node)
    result = []
    for yaml_file in sorted(dir_path.glob("*.yaml")):
        with open(yaml_file) as f:
            content = yaml.load(f, Loader=lambda s: HAYAMLLoader(s, yaml_file.parent, loader.secrets))
            if content is not None:
                result.append(content)
    return result

def construct_include_dir_merge_list(loader: HAYAMLLoader, node: yaml.Node) -> List[Any]:
    """Handle !include_dir_merge_list tag."""
    dir_path = loader.config_path / loader.construct_scalar(node)
    result = []
    for yaml_file in sorted(dir_path.glob("*.yaml")):
        with open(yaml_file) as f:
            content = yaml.load(f, Loader=lambda s: HAYAMLLoader(s, yaml_file.parent, loader.secrets))
            if isinstance(content, list):
                result.extend(content)
    return result

def construct_secret(loader: HAYAMLLoader, node: yaml.Node) -> str:
    """Handle !secret tag."""
    key = loader.construct_scalar(node)
    if key not in loader.secrets:
        raise ValueError(f"Secret '{key}' not found in secrets.yaml")
    return loader.secrets[key]

# Register constructors
HAYAMLLoader.add_constructor('!include', construct_include)
HAYAMLLoader.add_constructor('!include_dir_list', construct_include_dir_list)
HAYAMLLoader.add_constructor('!include_dir_merge_list', construct_include_dir_merge_list)
HAYAMLLoader.add_constructor('!include_dir_named', construct_include_dir_named)
HAYAMLLoader.add_constructor('!include_dir_merge_named', construct_include_dir_merge_named)
HAYAMLLoader.add_constructor('!secret', construct_secret)
```

**Option B: Stub-based Validation (Simpler)**

Instead of fully expanding includes, just register constructors that return placeholder values:

```python
def construct_stub(loader, node):
    """Return a stub value for any HA tag."""
    return f"<{node.tag}:{loader.construct_scalar(node)}>"

for tag in ['!include', '!include_dir_list', '!include_dir_merge_list', 
            '!include_dir_named', '!include_dir_merge_named', '!secret', '!env_var']:
    yaml.SafeLoader.add_constructor(tag, construct_stub)
```

This allows syntax validation without file resolution - good for quick checks.

### 4. API Validation Endpoint

**Endpoint:** `POST /api/config/core/check_config`

**Response format:**
```json
{
    "valid": true/false,
    "errors": ["error message 1", ...],
    "messages": ["info message 1", ...]
}
```

**Performance:** 2-3 minutes for full validation (loads all integrations)

**What API validates:**
- Integration/component configuration
- Template syntax in runtime context
- Automation/script definitions
- Cross-component dependencies

**What API does NOT validate:**
- YAML syntax (must be valid before calling)
- File structure issues

### 5. Recommended Command Structure

**Remove `--fix` flag entirely.**

**Rename/clarify modes:**

```
ha-tools validate                    # Full validation (syntax + API)
ha-tools validate --syntax-only      # Local YAML parsing only (fast)
ha-tools validate --api-only         # Skip syntax, just call API (if already validated)
```

**Proposed implementation:**

```python
def validate_command(
    syntax_only: bool = typer.Option(
        False, "--syntax-only", "-s",
        help="Only perform local YAML syntax validation (fast, no API call)"
    ),
    api_only: bool = typer.Option(
        False, "--api-only", "-a", 
        help="Skip syntax validation, only call Home Assistant API"
    ),
    expand_includes: bool = typer.Option(
        False, "--expand-includes", "-e",
        help="Fully expand !include directives during syntax validation"
    ),
) -> None:
    """
    Validate Home Assistant configuration.
    
    By default, performs both local syntax validation and full API validation.
    
    Examples:
        ha-tools validate                    # Full validation
        ha-tools validate --syntax-only      # Quick local check
        ha-tools validate --api-only         # API only (skip syntax)
    """
```

## Code References

- `ha_tools/commands/validate.py:189` - Current `yaml.safe_load()` usage
- `ha_tools/commands/validate.py:196-216` - Current `--fix` implementation
- `ha_tools/lib/rest_api.py:109-115` - API `validate_config()` method
- `ha_tools/config.py:120` - Config file loading (also uses `safe_load`)
- `tests/unit/test_validate_command.py` - Existing test coverage

## Architecture Insights

### Current Validation Flow

```
validate_command()
    │
    ├── syntax_only=True
    │   └── _run_syntax_validation()
    │       └── _validate_yaml_file() × N files
    │           └── yaml.safe_load() ← FAILS on HA tags
    │
    └── syntax_only=False (full)
        ├── _run_syntax_validation() ← runs first
        │   └── returns early if errors
        └── _run_full_validation()
            └── api.validate_config()
                └── POST /api/config/core/check_config
```

### Proposed Validation Flow

```
validate_command()
    │
    ├── syntax_only=True
    │   └── _run_syntax_validation()
    │       └── _validate_yaml_file() × N files
    │           └── ha_yaml_loader.load() ← NEW: supports HA tags
    │               ├── expand_includes=True: full resolution
    │               └── expand_includes=False: stub values
    │
    └── Full validation
        ├── _run_syntax_validation()
        │   └── returns early if errors
        └── _run_api_validation()
            └── api.validate_config()
```

## Implementation Plan

### Phase 1: Remove `--fix` flag
- Delete `--fix` option from `validate_command()`
- Remove `fix` parameter from `_run_validation()`, `_run_syntax_validation()`, `_validate_yaml_file()`
- Remove fix logic from `_validate_yaml_file()`
- Update `_generate_syntax_report()` to remove fixes_applied handling
- Update tests

### Phase 2: Create custom YAML loader
- Create `ha_tools/lib/yaml_loader.py`
- Implement stub-based constructors for all HA tags
- Add option for full include expansion
- Add secrets.yaml loading

### Phase 3: Update validate command
- Replace `yaml.safe_load()` with custom loader
- Add `--expand-includes` flag for full resolution
- Consider adding `--api-only` flag
- Update documentation

### Phase 4: Update tests
- Add tests for HA YAML tags
- Add tests for include expansion
- Add tests for secrets handling

## Open Questions

1. **Should we fully expand includes or use stubs?**
   - Full expansion: More thorough but slower, needs file access
   - Stubs: Faster, validates syntax without file resolution
   - Recommendation: Default to stubs, `--expand-includes` for full resolution

2. **What about secrets.yaml validation?**
   - Should we validate that all referenced secrets exist?
   - Should we warn about unused secrets?

3. **How to handle circular includes?**
   - Need to track include stack to detect cycles
   - Should probably error out with clear message

4. **Should we validate included files exist?**
   - Even with stubs, we could check that referenced files/directories exist
   - Would catch typos in include paths

## Related Research

- `ENTITY_EXPLORER_KNOWLEDGE_EXTRACTION.md` - Registry loading patterns
- `HA_TOOLS_REFERENCE.md` - API endpoint documentation

## Sources

- [Home Assistant Splitting Configuration](https://www.home-assistant.io/docs/configuration/splitting_configuration/)
- [Home Assistant Secrets](https://www.home-assistant.io/docs/configuration/secrets/)
- [Home Assistant YAML Syntax](https://www.home-assistant.io/docs/configuration/yaml/)
- [HA Core YAML Loader](https://github.com/home-assistant/core/blob/dev/homeassistant/util/yaml/loader.py)
