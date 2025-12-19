---
date: 2025-12-19T10:30:00+01:00
researcher: Claude
git_commit: 93529ced5ad9303bcbf475b3f10c78431d5f2e71
branch: main
repository: ha-tools
topic: "Code Quality Checks: Linting, Type Checking, Pre-commit Hooks"
tags: [research, codebase, code-quality, linting, type-checking, pre-commit]
status: complete
last_updated: 2025-12-19
last_updated_by: Claude
---

# Research: Code Quality Checks for ha-tools

**Date**: 2025-12-19T10:30:00+01:00
**Researcher**: Claude
**Git Commit**: 93529ced5ad9303bcbf475b3f10c78431d5f2e71
**Branch**: main
**Repository**: ha-tools

## Research Question
How to add code quality checks (linting, type checking, etc.) to the ha-tools repository?

## Summary

Good news: The repo **already has** quality tools configured in `pyproject.toml` (ruff, mypy, black, pytest). What's missing is:
1. **Automation** - no pre-commit hooks or CI/CD
2. **Fixing existing issues** - 308 ruff issues, 84 mypy errors
3. **Config updates** - ruff config uses deprecated format

## Current State

### Tools Already Configured (`pyproject.toml`)

| Tool   | Version   | Purpose            | Status                           |
| ------ | --------- | ------------------ | -------------------------------- |
| ruff   | >=0.1.6   | Linting + imports  | Configured, deprecated syntax    |
| mypy   | >=1.7.0   | Type checking      | Configured, strict settings      |
| black  | >=23.10.0 | Code formatting    | Configured (redundant with ruff) |
| pytest | >=7.4.0   | Testing + coverage | Configured                       |

### Current Issues

**Ruff Linting (308 issues, 274 auto-fixable)**:
- Missing newlines at end of files (W292)
- Unused imports (F401)
- Type annotation modernization (UP045, UP006) - `Optional[T]` → `T | None`
- Import sorting needed (I001)
- Missing `from` in exception chains (B904)

**Mypy Type Errors (84 errors)**:
- Missing library stubs for `asyncmy`, `asyncpg`
- Pydantic config issues in `config.py`
- Missing type annotations throughout
- None handling issues

### What's Missing

- `.pre-commit-config.yaml` - no pre-commit hooks
- `.github/workflows/` - no CI/CD
- No automation to run checks

## Recommended Implementation

### 1. Simplify: Remove Black (Use Ruff Only)

Modern best practice (2025) is to use **Ruff for both linting AND formatting**. It's a drop-in replacement for Black and 30x faster.

```diff
# In pyproject.toml [project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "pytest-asyncio>=0.23.0",
    "pytest-cov>=4.1.0",
-   "black>=23.10.0",
    "ruff>=0.1.6",
    "mypy>=1.7.0",
    "types-PyYAML",
]
```

### 2. Fix Ruff Config (Deprecated Format)

Move linting settings to `[tool.ruff.lint]`:

```toml
[tool.ruff]
target-version = "py311"
line-length = 88

[tool.ruff.lint]
select = ["E", "W", "F", "I", "B", "C4", "UP"]
ignore = ["E501"]

[tool.ruff.lint.per-file-ignores]
"__init__.py" = ["F401"]

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
```

### 3. Add Pre-commit Hooks

Create `.pre-commit-config.yaml`:

```yaml
repos:
  # Keep uv.lock in sync
  - repo: https://github.com/astral-sh/uv-pre-commit
    rev: 0.9.18
    hooks:
      - id: uv-lock

  # Ruff linting and formatting
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.14.10
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

### 4. Fix Existing Issues

**Quick wins (auto-fix):**
```bash
uv run ruff check --fix ha_tools/
uv run ruff format ha_tools/
```

**Manual fixes needed:**
1. Add type stubs for database libraries:
   ```toml
   # In pyproject.toml
   [tool.mypy]
   [[tool.mypy.overrides]]
   module = ["asyncmy.*", "asyncpg.*"]
   ignore_missing_imports = true
   ```

2. Fix pydantic config in `ha_tools/config.py`
3. Add missing type annotations

### 5. Optional: Add GitHub Actions CI

Create `.github/workflows/ci.yml`:

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v4
      - run: uv sync --dev
      - run: uv run ruff check ha_tools/
      - run: uv run ruff format --check ha_tools/

  type-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v4
      - run: uv sync --dev
      - run: uv run mypy ha_tools/

  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v4
      - run: uv sync --dev
      - run: uv run pytest
```

## Implementation Priority

| Priority | Task | Effort | Impact |
|----------|------|--------|--------|
| 1 | Fix ruff config format | 5 min | Fixes deprecation warnings |
| 2 | Auto-fix ruff issues | 1 min | -274 issues instantly |
| 3 | Add pre-commit config | 10 min | Prevents future issues |
| 4 | Remove black dependency | 2 min | Simplifies toolchain |
| 5 | Fix mypy issues | 30-60 min | Full type safety |
| 6 | Add GitHub Actions | 15 min | CI automation |

## Code References

- `pyproject.toml:60-83` - Current ruff config (deprecated format)
- `pyproject.toml:85-93` - Current mypy config
- `pyproject.toml:38-46` - Dev dependencies
- `ha_tools/config.py` - Pydantic config issues
- `ha_tools/lib/database.py` - Most mypy errors

## Open Questions

1. Do you want GitHub Actions CI, or is pre-commit enough?
2. Should mypy be strict (current) or relaxed initially?
3. Any specific ruff rules to add/ignore?
