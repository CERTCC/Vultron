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

# Skill: Load Specs

```bash
PYTHONPATH= uv run spec-dump
```

Do **not** read raw `specs/*.yaml` files directly — the JSON export resolves inheritance and flattens group nesting. See [REFERENCE.md](REFERENCE.md) for the full output structure and field definitions.

## Output structure

Three top-level arrays: `topics`, `requirements`, `edges`.

## Cross-cutting constraints

Always check requirements from these spec files regardless of primary topic:

- `ARCH` — architecture layer rules
- `CS` — code style
- `TB` — testability
- `HP` — handler protocol
- `SL` — structured logging
- `EH` — error handling
