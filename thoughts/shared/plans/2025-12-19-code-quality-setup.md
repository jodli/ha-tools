# Code Quality Setup Implementation Plan

## Overview

Add code quality automation to ha-tools via pre-commit hooks. Fix existing linting and type errors to establish a clean baseline.

## Current State Analysis

- **Tools configured**: ruff, mypy, black, pytest in `pyproject.toml`
- **Issues**: 308 ruff errors (274 auto-fixable), 84 mypy errors
- **Problems**: Deprecated ruff config format, no automation, black redundant with ruff
- **Missing**: `.pre-commit-config.yaml`, CI/CD

### Key Files:
- `pyproject.toml:65-83` - Ruff config (deprecated format)
- `pyproject.toml:85-93` - Mypy config (strict, keep as-is)
- `pyproject.toml:38-46` - Dev dependencies

## Desired End State

- Pre-commit hooks run ruff (lint + format) and mypy on every commit
- Zero ruff errors, zero mypy errors
- Clean `uv run ruff check ha_tools/` and `uv run mypy ha_tools/` output

## What We're NOT Doing

- GitHub Actions CI (can add later if needed)
- Relaxing mypy strictness
- Adding new ruff rules beyond current selection

---

## Phase 1: Fix Ruff Config & Remove Black

### Overview
Update ruff config to non-deprecated format and remove redundant black dependency.

### Changes Required:

#### 1. Update `pyproject.toml` - Ruff config
**File**: `pyproject.toml`

Replace lines 65-83 with:

```toml
[tool.ruff]
target-version = "py311"
line-length = 88

[tool.ruff.lint]
select = [
    "E",  # pycodestyle errors
    "W",  # pycodestyle warnings
    "F",  # pyflakes
    "I",  # isort
    "B",  # flake8-bugbear
    "C4", # flake8-comprehensions
    "UP", # pyupgrade
]
ignore = [
    "E501",  # line too long, handled by formatter
    "B008",  # do not perform function calls in argument defaults
]

[tool.ruff.lint.per-file-ignores]
"__init__.py" = ["F401"]

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
```

#### 2. Remove black from dev dependencies
**File**: `pyproject.toml`

Remove line 42 (`"black>=23.10.0",`) and delete the entire `[tool.black]` section (lines 60-63).

### Success Criteria:

#### Automated Verification:
- [x] `uv run ruff check ha_tools/` runs without deprecation warnings
- [x] `uv run ruff format --check ha_tools/` works

---

## Phase 2: Add Pre-commit Hooks

### Overview
Create pre-commit configuration with ruff and mypy hooks.

### Changes Required:

#### 1. Create `.pre-commit-config.yaml`
**File**: `.pre-commit-config.yaml`

```yaml
repos:
  # Ruff linting and formatting
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.8.4
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  # Type checking
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.13.0
    hooks:
      - id: mypy
        additional_dependencies:
          - types-PyYAML
          - pydantic>=2.5.0
        args: [--config-file=pyproject.toml]

  # Standard safety hooks
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
      - id: debug-statements
```

#### 2. Add pre-commit to dev dependencies
**File**: `pyproject.toml`

Add `"pre-commit>=3.6.0",` to the dev dependencies list.

### Success Criteria:

#### Automated Verification:
- [x] `uv sync --dev` installs pre-commit
- [x] `uv run pre-commit install` succeeds
- [x] `uv run pre-commit run --all-files` runs (will fail on existing issues, that's expected)

---

## Phase 3: Auto-fix Ruff Issues

### Overview
Run ruff auto-fix to eliminate 274 fixable issues instantly.

### Commands:
```bash
uv run ruff check --fix ha_tools/
uv run ruff format ha_tools/
```

### Success Criteria:

#### Automated Verification:
- [x] `uv run ruff check ha_tools/` shows 0 errors
- [x] `uv run ruff format --check ha_tools/` shows no changes needed

---

## Phase 4: Fix Mypy Errors

### Overview
Fix 84 mypy errors step by step, keeping strict settings.

### Sub-phases:

#### 4a. Add missing import overrides
**File**: `pyproject.toml`

Add after line 93:

```toml
[[tool.mypy.overrides]]
module = ["asyncmy.*", "asyncpg.*"]
ignore_missing_imports = true
```

#### 4b. Fix type errors file by file

Work through files in order of complexity (fewest errors first):
1. `ha_tools/cli.py` - Console type issue
2. `ha_tools/config.py` - Pydantic config
3. `ha_tools/lib/*.py` - Library modules
4. `ha_tools/commands/*.py` - Command modules

### Success Criteria:

#### Automated Verification:
- [x] `uv run mypy ha_tools/` shows 0 errors

---

## Phase 5: Final Verification

### Commands:
```bash
uv run pre-commit run --all-files
uv run pytest
```

### Success Criteria:

#### Automated Verification:
- [x] Pre-commit passes on all files
- [x] All tests pass (235 tests)
- [x] Clean commit possible

---

## References

- Research: `thoughts/shared/research/2025-12-19-code-quality-setup.md`
- Ruff docs: https://docs.astral.sh/ruff/
- Pre-commit docs: https://pre-commit.com/
