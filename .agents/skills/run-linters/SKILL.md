---
id: "run-linters"
title: "Run repository linters"
description: "Run the canonical set of linters used by maintainers: Black, flake8, mypy, and pyright."
author: "CERTCC / Vultron"
tags:
  - linting
  - ci
  - dev-workflow
shell: "zsh"
commands:
  - "G=.agents/skills/shared/run-if-changed.sh; \"$G\" black vultron/ test/ pyproject.toml uv.lock -- uv run black vultron/ test/ && \"$G\" flake8 vultron/ test/ .flake8 uv.lock -- uv run flake8 vultron/ test/ && \"$G\" mypy vultron/ test/ .mypy.ini uv.lock -- uv run mypy && \"$G\" pyright vultron/ test/ pyrightconfig.json uv.lock -- uv run pyright"
inputs:
  - name: repo_root
    description: "Repository root where the command will be executed"
    default: "."
outputs:
  - name: lint_summary
    description: "Exit status and summary output from the linters"
---

# Skill: Run Linters

Each tool is routed through the shared `run-if-changed.sh` guard, which skips a
tool when its inputs (the `vultron/`+`test/` sources, that tool's config file,
and `uv.lock`) are unchanged since its last successful run. So back-to-back
lint passes — and the flake8 pre-commit hook — reuse work instead of repeating
it, while any edit to a relevant file forces a fresh run.

```bash
G=.agents/skills/shared/run-if-changed.sh
"$G" black   vultron/ test/ pyproject.toml     uv.lock -- uv run black  vultron/ test/
"$G" flake8  vultron/ test/ .flake8            uv.lock -- uv run flake8 vultron/ test/
"$G" mypy    vultron/ test/ .mypy.ini          uv.lock -- uv run mypy
"$G" pyright vultron/ test/ pyrightconfig.json uv.lock -- uv run pyright
```

## Constraints

- Run `black` first — formatting errors cause spurious `flake8` failures.
- `flake8` enforces a CC gate (`max-complexity = 10` in `.flake8`); functions exceeding CC=10 are a hard failure (IMPLTS-07-008).
- All four tools must exit 0 before staging.
- A `... inputs unchanged since last success — skipping` line is the guard
  reusing a prior pass, not a failure. On failure the guard records nothing, so
  the next run re-executes the tool.
