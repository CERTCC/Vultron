---
id: "load-specs"
title: "Load all specs as LLM-optimized JSON"
description: "Export all project specifications as flat, inheritance-resolved JSON for coding agents. Run this at the start of any implementation or design task."
author: "CERTCC / Vultron"
tags:
  - specs
  - requirements
  - agent-context
shell: "zsh"
commands:
  - "uv run spec-dump"
inputs:
  - name: repo_root
    description: "Repository root where the command should be executed"
    default: "."
outputs:
  - name: specs_json
    description: "Compact JSON with all requirements, edges, and file metadata"
---

# Skill: Load All Specs as LLM-Optimized JSON

## Purpose

Export all project specifications as a flat, inheritance-resolved JSON
structure optimized for coding agents. This is the **required** way to load
specs before any implementation or design task.

**Do not read raw `specs/*.yaml` files directly.** Those files are for
authoring and linting only. The JSON export resolves inheritance, flattens
group nesting, and provides a consistent structure for agent consumption.

## Procedure

From the repository root, run:

```bash
uv run spec-dump
```

This produces compact JSON on stdout. Capture or pipe it as needed.

## Output Structure

The JSON has three top-level arrays:

```json
{
  "files": [...],
  "requirements": [...],
  "edges": [...]
}
```

### `files`

One entry per spec file. Fields: `id`, `title`, `version`, `kind`, `scope`.

### `requirements`

One entry per requirement (statement or behavioral). Key fields:

| Field | Meaning |
|---|---|
| `id` | Unique requirement ID (e.g. `ARCH-01-001`) |
| `file_id` | Parent spec file ID (e.g. `ARCH`) |
| `group_id` | Group within the file (e.g. `ARCH-01`) |
| `group_title` | Human-readable group name |
| `priority` | `MUST`, `SHOULD`, or `MAY` |
| `statement` | The normative requirement text |
| `kind` | `implementation`, `behavioral`, `documentation`, `testing` |
| `scope` | List: `prototype`, `production`, or both |
| `tags` | Optional topic labels |
| `type` | `statement` or `behavioral` |
| `relationships` | Inline list of `{type, target, note}` edges from this spec |
| `testable` | `true` if the requirement has a verification path |
| `rationale` | Optional explanatory text |
| `verification` | Optional verification criteria |

Behavioral specs additionally have: `preconditions`, `steps`, `postconditions`.

### `edges`

Centralized list of all relationships across all files:

```json
{"from": "ARCH-01-001", "type": "depends_on", "to": "CS-01-001", "note": "..."}
```

Edge types include: `depends_on`, `relates_to`, `implements`, `contradicts`.

## Cross-Cutting Constraints

When implementing any feature, always pay attention to requirements from
these cross-cutting spec files regardless of the primary topic:

- `ARCH` — architecture layer rules (no cross-layer imports, etc.)
- `CS` — code style conventions
- `TB` — testability requirements (coverage, test structure)
- `HP` — handler protocol
- `SL` — structured logging
- `EH` — error handling

These apply to all code changes even when working on a specific feature area.

## Examples

```bash
# Full dump (default — always prefer this)
uv run spec-dump

# Write to file for reference
uv run spec-dump > /tmp/specs.json

# Count requirements
uv run spec-dump | python -c "import json,sys; r=json.load(sys.stdin); print(len(r['requirements']))"

# Filter MUST requirements in Python after loading
uv run spec-dump | python -c "
import json, sys
data = json.load(sys.stdin)
musts = [r for r in data['requirements'] if r['priority'] == 'MUST']
print(f'{len(musts)} MUST requirements')
"
```

## Rationale

The `specs/*.yaml` source files use an authoring-optimized format with
inheritance (kind/scope inherited from file→group→spec), optional rationale,
and group nesting. This structure is good for authors but burdens coding agents
with mental inheritance resolution and navigation of nested structures.

The LLM JSON export:

1. Resolves all inheritance so every requirement has explicit `kind` and `scope`
2. Flattens group nesting so requirements are a simple array
3. Centralizes edges for graph-based dependency planning
4. Omits empty/null fields to minimize token usage
5. Uses readable field names (no abbreviations)

Running this export ensures agents always see the complete, consistent,
authoritative requirement set rather than a subset from browsing individual
files.
