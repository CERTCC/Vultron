---
id: "run-linters"
title: "Run repository linters"
description: "Run the canonical set of linters used by maintainers: ruff (lint and format) and mypy."
author: "CERTCC / Vultron"
tags:
  - linting
  - ci
  - dev-workflow
shell: "zsh"
commands:
  - "G=.agents/skills/shared/run-if-changed.sh; uv run ruff check --fix && uv run ruff format && uv run ruff check && \"$G\" mypy vultron/ test/ .mypy.ini uv.lock -- uv run mypy"
inputs:
  - name: repo_root
    description: "Repository root where the command will be executed"
    default: "."
outputs:
  - name: lint_summary
    description: "Exit status and summary output from the linters"
---

# Skill: Run Linters

The linter step is ruff and mypy (PAD-18-026). ruff runs directly: a whole-tree
pass takes about a second, so a fingerprint lookup would cost a real share of
the work it saves (ADR-0094). mypy is routed through the shared
`run-if-changed.sh` guard, which skips it when its inputs (the
`vultron/`+`test/` sources, `.mypy.ini`, and `uv.lock`) are unchanged since its
last successful run.

```bash
uv run ruff check --fix
uv run ruff format
uv run ruff check
G=.agents/skills/shared/run-if-changed.sh
"$G" mypy vultron/ test/ .mypy.ini uv.lock -- uv run mypy
```

**pyright is CI's, not this skill's** (PAD-18-027). It took a median of two
minutes in each local step and enough memory to starve a parallel test run,
while CI's `lint-pyright` job answers in 81–149 s and the required `CI gate`
refuses a merge until it is green. Do not add it back here or to any other
local gate.

## Constraints

- Never pass paths to ruff. Scope is declared in `[tool.ruff]` in
  `pyproject.toml` (IMPLTS-07-021), so a bare `ruff check` covers exactly what CI
  and the pre-commit hook cover.
- The second `ruff check` runs after `ruff format` because the formatter can
  rewrap a line and move an inline `# noqa` off the line it suppresses.
- Run mypy **after** formatting for the same reason: a wrapped line can strand
  a `# type: ignore[...]` on the wrong line (see
  `notes/codebase-structure.md`). The same hazard applies to a
  `# pyright: ignore[...]`, which CI's pyright job reports.
- C901 enforces the complexity gate (`max-complexity = 10`); a function over
  CC=10 is a hard failure (IMPLTS-07-008).
- RUF100 reports an unused `# noqa`. When your change fixes a baselined finding,
  delete its `# noqa: RULE  # ruff-baseline #N` marker (IMPLTS-07-020).
- All tools must exit 0 before staging.
- A `... inputs unchanged since last success — skipping` line is the guard
  reusing a prior pass, not a failure. On failure the guard records nothing, so
  the next run re-executes the tool.
