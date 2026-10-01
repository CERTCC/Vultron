---
id: "run-linters"
title: "Run repository linters"
description: "Run the canonical set of linters used by maintainers: ruff (lint and format), mypy, and pyright."
author: "CERTCC / Vultron"
tags:
  - linting
  - ci
  - dev-workflow
shell: "zsh"
commands:
  - "G=.agents/skills/shared/run-if-changed.sh; uv run ruff check --fix && uv run ruff format && uv run ruff check && \"$G\" mypy vultron/ test/ .mypy.ini uv.lock -- uv run mypy && \"$G\" pyright vultron/ test/ pyrightconfig.json uv.lock -- uv run pyright"
inputs:
  - name: repo_root
    description: "Repository root where the command will be executed"
    default: "."
outputs:
  - name: lint_summary
    description: "Exit status and summary output from the linters"
---

# Skill: Run Linters

ruff runs directly: a whole-tree pass takes about a second, so a fingerprint
lookup would cost a real share of the work it saves (ADR-0094). mypy and pyright
are routed through the shared `run-if-changed.sh` guard, which skips a tool when
its inputs (the `vultron/`+`test/` sources, that tool's config file, and
`uv.lock`) are unchanged since its last successful run.

```bash
uv run ruff check --fix
uv run ruff format
uv run ruff check
G=.agents/skills/shared/run-if-changed.sh
"$G" mypy    vultron/ test/ .mypy.ini          uv.lock -- uv run mypy
"$G" pyright vultron/ test/ pyrightconfig.json uv.lock -- uv run pyright
```

## Constraints

- Never pass paths to ruff. Scope is declared in `[tool.ruff]` in
  `pyproject.toml` (IMPLTS-07-021), so a bare `ruff check` covers exactly what CI
  and the pre-commit hook cover.
- The second `ruff check` runs after `ruff format` because the formatter can
  rewrap a line and move an inline `# noqa` off the line it suppresses.
- Run mypy and pyright **after** formatting for the same reason: a wrapped line
  can strand a `# type: ignore[...]` or `# pyright: ignore[...]` on the wrong
  line (see `notes/codebase-structure-fastapi-patterns.md`).
- C901 enforces the complexity gate (`max-complexity = 10`); a function over
  CC=10 is a hard failure (IMPLTS-07-008).
- RUF100 reports an unused `# noqa`. When your change fixes a baselined finding,
  delete its `# noqa: RULE  # ruff-baseline #N` marker (IMPLTS-07-020).
- All tools must exit 0 before staging.
- A `... inputs unchanged since last success — skipping` line is the guard
  reusing a prior pass, not a failure. On failure the guard records nothing, so
  the next run re-executes the tool.
