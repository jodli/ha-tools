"""
Custom YAML loader with Home Assistant tag support.

Home Assistant uses custom YAML tags that standard PyYAML cannot parse:
- !include, !include_dir_list, !include_dir_merge_list
- !include_dir_named, !include_dir_merge_named
- !secret, !env_var

This module provides a custom loader that can handle these tags in two modes:
1. Stub mode (default): Returns placeholder values for fast syntax validation
2. Expand mode: Fully resolves includes and secrets for thorough validation
"""

from pathlib import Path
from typing import Any

import yaml

# All Home Assistant custom YAML tags
HA_YAML_TAGS = [
    "!include",
    "!include_dir_list",
    "!include_dir_merge_list",
    "!include_dir_named",
    "!include_dir_merge_named",
    "!secret",
    "!env_var",
]


class HAYAMLLoader(yaml.SafeLoader):
    """Custom YAML loader with Home Assistant tag support.

    This loader can operate in two modes:
    - Stub mode (expand_includes=False): Returns placeholder strings for HA tags.
      Fast and doesn't require file access. Good for syntax validation.
    - Expand mode (expand_includes=True): Fully resolves includes and secrets.
      Slower but validates that all referenced files exist.
    """

    def __init__(
        self,
        stream: Any,
        config_path: Path | None = None,
        secrets: dict[str, str] | None = None,
        expand_includes: bool = False,
    ):
        """Initialize the loader.

        Args:
            stream: The YAML content to parse
            config_path: Base path for resolving relative includes
            secrets: Dictionary of secrets (from secrets.yaml)
            expand_includes: If True, fully expand includes. If False, use stubs.
        """
        super().__init__(stream)
        self.config_path = config_path or Path.cwd()
        self.secrets = secrets or {}
        self.expand_includes = expand_includes
        self._include_stack: list[Path] = []  # Track includes for cycle detection


def _construct_stub(loader: HAYAMLLoader, tag: str, node: yaml.Node) -> str:
    """Return a stub value for any HA tag (used when not expanding)."""
    value = loader.construct_scalar(node)
    return f"<{tag}:{value}>"


def _construct_include(loader: HAYAMLLoader, node: yaml.Node) -> Any:
    """Handle !include tag."""
    relative_path = loader.construct_scalar(node)

    if not loader.expand_includes:
        return f"<!include:{relative_path}>"

    include_path = loader.config_path / relative_path
    return _load_yaml_file(loader, include_path)


def _construct_include_dir_list(loader: HAYAMLLoader, node: yaml.Node) -> Any:
    """Handle !include_dir_list tag - includes directory as list."""
    relative_path = loader.construct_scalar(node)

    if not loader.expand_includes:
        return f"<!include_dir_list:{relative_path}>"

    dir_path = loader.config_path / relative_path
    return _load_yaml_directory_as_list(loader, dir_path, merge=False)


def _construct_include_dir_merge_list(loader: HAYAMLLoader, node: yaml.Node) -> Any:
    """Handle !include_dir_merge_list tag - merges files into single list."""
    relative_path = loader.construct_scalar(node)

    if not loader.expand_includes:
        return f"<!include_dir_merge_list:{relative_path}>"

    dir_path = loader.config_path / relative_path
    return _load_yaml_directory_as_list(loader, dir_path, merge=True)


def _construct_include_dir_named(loader: HAYAMLLoader, node: yaml.Node) -> Any:
    """Handle !include_dir_named tag - includes as dict (filename = key)."""
    relative_path = loader.construct_scalar(node)

    if not loader.expand_includes:
        return f"<!include_dir_named:{relative_path}>"

    dir_path = loader.config_path / relative_path
    return _load_yaml_directory_as_dict(loader, dir_path, merge=False)


def _construct_include_dir_merge_named(loader: HAYAMLLoader, node: yaml.Node) -> Any:
    """Handle !include_dir_merge_named tag - merges dicts from files."""
    relative_path = loader.construct_scalar(node)

    if not loader.expand_includes:
        return f"<!include_dir_merge_named:{relative_path}>"

    dir_path = loader.config_path / relative_path
    return _load_yaml_directory_as_dict(loader, dir_path, merge=True)


def _construct_secret(loader: HAYAMLLoader, node: yaml.Node) -> Any:
    """Handle !secret tag."""
    secret_key = loader.construct_scalar(node)

    if not loader.expand_includes:
        return f"<!secret:{secret_key}>"

    if secret_key not in loader.secrets:
        raise yaml.YAMLError(f"Secret '{secret_key}' not found in secrets.yaml")
    return loader.secrets[secret_key]


def _construct_env_var(loader: HAYAMLLoader, node: yaml.Node) -> Any:
    """Handle !env_var tag."""
    env_var = loader.construct_scalar(node)

    if not loader.expand_includes:
        return f"<!env_var:{env_var}>"

    import os

    value = os.environ.get(env_var)
    if value is None:
        raise yaml.YAMLError(f"Environment variable '{env_var}' not set")
    return value


def _load_yaml_file(loader: HAYAMLLoader, file_path: Path) -> Any:
    """Load and parse a YAML file with cycle detection."""
    resolved_path = file_path.resolve()

    # Check for circular includes
    if resolved_path in loader._include_stack:
        cycle = (
            " -> ".join(str(p) for p in loader._include_stack) + f" -> {resolved_path}"
        )
        raise yaml.YAMLError(f"Circular include detected: {cycle}")

    if not file_path.exists():
        raise yaml.YAMLError(f"Include file not found: {file_path}")

    loader._include_stack.append(resolved_path)
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Create a new loader for the included file
        new_loader = HAYAMLLoader(
            content,
            config_path=file_path.parent,
            secrets=loader.secrets,
            expand_includes=loader.expand_includes,
        )
        new_loader._include_stack = loader._include_stack

        return yaml.load(content, Loader=lambda s: new_loader)
    finally:
        loader._include_stack.pop()


def _load_yaml_directory_as_list(
    loader: HAYAMLLoader, dir_path: Path, merge: bool
) -> list[Any]:
    """Load all YAML files from a directory as a list."""
    if not dir_path.exists():
        raise yaml.YAMLError(f"Include directory not found: {dir_path}")

    result: list[Any] = []
    for yaml_file in sorted(dir_path.glob("*.yaml")):
        content = _load_yaml_file(loader, yaml_file)
        if content is not None:
            if merge and isinstance(content, list):
                result.extend(content)
            else:
                result.append(content)
    return result


def _load_yaml_directory_as_dict(
    loader: HAYAMLLoader, dir_path: Path, merge: bool
) -> dict[str, Any]:
    """Load all YAML files from a directory as a dict."""
    if not dir_path.exists():
        raise yaml.YAMLError(f"Include directory not found: {dir_path}")

    result: dict[str, Any] = {}
    for yaml_file in sorted(dir_path.glob("*.yaml")):
        content = _load_yaml_file(loader, yaml_file)
        if content is not None:
            if merge and isinstance(content, dict):
                result.update(content)
            else:
                # Use filename without extension as key
                key = yaml_file.stem
                result[key] = content
    return result


def load_secrets(config_path: Path) -> dict[str, str]:
    """Load secrets from secrets.yaml file.

    Args:
        config_path: Path to the Home Assistant config directory

    Returns:
        Dictionary of secret key -> value mappings
    """
    secrets_file = config_path / "secrets.yaml"
    if not secrets_file.exists():
        return {}

    try:
        with open(secrets_file, "r", encoding="utf-8") as f:
            content = yaml.safe_load(f)
            return content if isinstance(content, dict) else {}
    except yaml.YAMLError:
        return {}


def load_yaml(
    content: str,
    config_path: Path | None = None,
    expand_includes: bool = False,
    secrets: dict[str, str] | None = None,
) -> Any:
    """Load YAML content with Home Assistant tag support.

    Args:
        content: YAML content as string
        config_path: Base path for resolving includes (defaults to cwd)
        expand_includes: If True, fully expand includes. If False, use stubs.
        secrets: Pre-loaded secrets dict. If None and expand_includes=True,
                 secrets will be loaded from config_path/secrets.yaml

    Returns:
        Parsed YAML content
    """
    path = config_path or Path.cwd()

    # Load secrets if expanding and not provided
    if expand_includes and secrets is None:
        secrets = load_secrets(path)

    loader = HAYAMLLoader(
        content,
        config_path=path,
        secrets=secrets or {},
        expand_includes=expand_includes,
    )

    return yaml.load(content, Loader=lambda s: loader)


def load_yaml_file(
    file_path: Path,
    expand_includes: bool = False,
    secrets: dict[str, str] | None = None,
) -> Any:
    """Load a YAML file with Home Assistant tag support.

    Args:
        file_path: Path to the YAML file
        expand_includes: If True, fully expand includes. If False, use stubs.
        secrets: Pre-loaded secrets dict

    Returns:
        Parsed YAML content
    """
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    return load_yaml(
        content,
        config_path=file_path.parent,
        expand_includes=expand_includes,
        secrets=secrets,
    )


# Register all constructors
HAYAMLLoader.add_constructor("!include", _construct_include)
HAYAMLLoader.add_constructor("!include_dir_list", _construct_include_dir_list)
HAYAMLLoader.add_constructor(
    "!include_dir_merge_list", _construct_include_dir_merge_list
)
HAYAMLLoader.add_constructor("!include_dir_named", _construct_include_dir_named)
HAYAMLLoader.add_constructor(
    "!include_dir_merge_named", _construct_include_dir_merge_named
)
HAYAMLLoader.add_constructor("!secret", _construct_secret)
HAYAMLLoader.add_constructor("!env_var", _construct_env_var)
