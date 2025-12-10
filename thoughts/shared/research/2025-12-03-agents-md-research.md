---
date: 2025-12-03T22:51:42+01:00
researcher: Antigravity
git_commit: unknown
branch: unknown
repository: ha-tools
topic: "Context Engineering for AGENTS.md"
tags: [research, context-engineering, agents, ha-tools]
status: complete
last_updated: 2025-12-03
last_updated_by: Antigravity
---

# Research: Context Engineering for AGENTS.md

**Date**: 2025-12-03T22:51:42+01:00
**Researcher**: Antigravity
**Repository**: ha-tools

## Research Question
"Take a look at @[CLAUDE.md] and the other markdown files in this repo and come up with a good AGENTS.md file we can use for context engineering in this repo."

## Summary
The `ha-tools` repository is explicitly designed *for* AI agents. The existing markdown files (`CLAUDE.md`, `HATOOLS_CLI.md`, `HA_TOOLS_REFERENCE.md`) contain scattered instructions and workflows for agents. The `AGENTS.md` file should consolidate these into a single "System Prompt" or "Context" file that an agent can read to understand its role, capabilities, and standard operating procedures when working in this environment.

## Detailed Findings

### 1. The "Agent" Concept
- **Finding**: The codebase does not contain internal "agent" classes (confirmed via `grep`).
- **Insight**: "Agent" refers to the LLM/AI user of the CLI. The CLI is the interface for the agent to interact with Home Assistant.

### 2. Core Capabilities (`ha-tools`)
- **Validate**: `ha-tools validate` (full) and `--syntax-only` (fast).
- **Entities**: `ha-tools entities` for discovery, search, and history.
- **Errors**: `ha-tools errors` for diagnostics.
- **Reference**: `CLAUDE.md` (lines 13-15), `HATOOLS_CLI.md` (lines 24-91).

### 3. Standard Workflows
Two primary workflows are repeated across multiple files:
1.  **Configuration Changes**:
    - Syntax check -> Check affected entities -> Full validation -> Check runtime errors.
    - Source: `CLAUDE.md` (lines 111-125), `HATOOLS_CLI.md` (lines 139-156).
2.  **Debugging**:
    - Check entity history -> Correlate with errors -> Check dependencies.
    - Source: `CLAUDE.md` (lines 127-138), `HATOOLS_CLI.md` (lines 158-171).

### 4. Performance Strategy
- Agents should prioritize **Database** (history) and **Filesystem** (static analysis) over **REST API** (slow, fallback).
- Source: `CLAUDE.md` (lines 78-82), `README.md` (lines 71-75).

### 5. Output Format
- Tools output "structured markdown optimized for AI consumption".
- Agents should expect tables, code blocks, and progressive disclosure.

## Proposed AGENTS.md Structure
The file should serve as a "Context Injection" for an AI session.

1.  **Role Definition**: "You are an expert Home Assistant Administrator Agent."
2.  **Tooling**: Introduction to `ha-tools` and its 3-command philosophy.
3.  **Operational Protocols** (The Workflows):
    - Protocol: Making Configuration Changes
    - Protocol: Debugging & Diagnostics
4.  **Best Practices**:
    - "Always validate syntax before full validation."
    - "Use database history for trends."
5.  **Emergency Procedures**: What to do if tools fail (fallback to manual checks).

## Code References
- `CLAUDE.md`: Primary source of agent instructions.
- `HATOOLS_CLI.md`: Detailed command usage.
- `ENTITY_EXPLORER_KNOWLEDGE_EXTRACTION.md`: Deep dive into data structures (useful for advanced understanding).

## Architecture Insights
The repo follows a "Tool-First" architecture for agents. Instead of the agent writing complex Python scripts to analyze HA, it delegates to the high-performance CLI. `AGENTS.md` should reinforce this delegation pattern.
