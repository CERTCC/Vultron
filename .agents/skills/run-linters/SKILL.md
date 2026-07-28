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
  - "uv run black vultron/ test/ && uv run flake8 vultron/ test/ && uv run mypy && uv run pyright"
inputs:
  - name: repo_root
    description: "Repository root where the command will be executed"
    default: "."
outputs:
  - name: lint_summary
    description: "Exit status and summary output from the linters"
---

# Skill: Run Linters

```bash
uv run black vultron/ test/ && uv run flake8 vultron/ test/ && uv run mypy && uv run pyright
```

## Constraints

- Run `black` first — formatting errors cause spurious `flake8` failures.
- `flake8` enforces a CC gate (`max-complexity = 10` in `.flake8`); functions exceeding CC=10 are a hard failure (IMPLTS-07-008).
- All four tools must exit 0 before staging.
