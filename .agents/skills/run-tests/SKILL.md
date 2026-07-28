---
id: "run-tests"
title: "Run canonical test-suite and capture summary"
description: "Run the repository's canonical pytest command and capture the final summary lines used by CI and automation."
author: "CERTCC / Vultron"
tags:
  - testing
  - ci
shell: "zsh"
commands:
  - "uv run pytest --tb=short 2>&1 | tail -5"
inputs:
  - name: repo_root
    description: "Repository root"
    default: "."
outputs:
  - name: pytest_summary
    description: "The last 5 lines of pytest output (summary and short failure traces)"
---

# Skill: Run Tests

| Suite | Command |
|---|---|
| Unit (default) | `uv run pytest --tb=short 2>&1 \| tail -5` |
| Integration | `uv run pytest -m integration --tb=short 2>&1 \| tail -5` |
| All | `uv run pytest -m "" --tb=short 2>&1 \| tail -5` |

## Constraints

- Run exactly once per validation cycle; do not use `-q` or change output formatting.
- Do not change `tail -5`.
- `filterwarnings = ["error"]` in `pyproject.toml` — warnings are test errors; fix root cause, do not suppress.
- Integration tests are excluded from the default run; use `-m integration` for demo/datalayer validation.
- Treat all failures as branch-owned by default; clean-base proof is required before classifying as pre-existing.
