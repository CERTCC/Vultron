---
id: "load-specs"
title: "Load targeted specs as LLM-optimized JSON"
description: "Map the spec corpus with `spec-dump --index`, then load only the topics, groups, or IDs a task needs (plus cross-cutting constraints). Run this at the start of any implementation or design task."
author: "CERTCC / Vultron"
tags:
  - specs
  - requirements
  - agent-context
shell: "zsh"
commands:
  - "PYTHONPATH= uv run spec-dump --index"
  - "PYTHONPATH= uv run spec-dump --cross-cutting --slim"
inputs:
  - name: repo_root
    description: "Repository root where the command should be executed"
    default: "."
outputs:
  - name: spec_index
    description: "Plain-text map: one line per topic, one indented line per group, with requirement counts"
  - name: specs_json
    description: "Compact JSON with the selected requirements, edges, and topic metadata"
---

# Skill: Load Specs

The full dump is ~2.5 MB (~600k tokens) and does not fit in context. Load
in two steps:

```bash
# 1. Map (~30 KB): topics and groups with requirement counts
PYTHONPATH= uv run spec-dump --index

# 2. Load what the task touches, plus the cross-cutting constraints
PYTHONPATH= uv run spec-dump --topic CM --group EP-04 --cross-cutting --slim
```

Do **not** read raw `specs/*.yaml` files — the export resolves inheritance
and flattens group nesting.

## Flags

| Flag | Effect |
|---|---|
| `--index` | Plain-text map instead of JSON. Other flags narrow it. |
| `--topic A,B` | Select topics (spec files). |
| `--group A-01,B-02` | Select groups. |
| `--ids X,Y` | Select requirement IDs. |
| `--deps` | Add transitive dependencies of the selection. |
| `--cross-cutting` | Add the cross-cutting topics (see below). |
| `--kind`, `--tag`, `--scope`, `--priority` | Narrow the selection. `--kind`/`--tag` take comma lists; all tags must match. |
| `--slim` | Keep only `id`, `priority`, `statement`, `note` per requirement. |

Selectors (`--topic`, `--group`, `--ids`, `--cross-cutting`) combine as a
union. An unknown value exits with code 2 and names the value. A run with
no filters prints the full dump (for `spec-audit`) with a size warning on
stderr.

## Cross-cutting constraints

Always add `--cross-cutting`, whatever the primary topic. The list of topics
is `CROSS_CUTTING_TOPICS` in `vultron/metadata/specs/llm_export.py`. Refer to
the flag; do not copy the list into other files.

Use `--slim` to scan. Load a requirement without `--slim` when you need its
`rationale`, `verification`, or `relationships`. See
[REFERENCE.md](REFERENCE.md) for field definitions.

## Checking a selection

`PYTHONPATH= uv run spec-backstop --manifest <file>` checks a Spec manifest
against the branch diff and lists the governing groups it missed. See
`deepen-context` § "Backstop".
