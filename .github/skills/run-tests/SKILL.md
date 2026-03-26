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

# Skill: Run canonical test-suite and capture summary

## Purpose

Run the repository's canonical test command exactly as maintainers and CI do,
then capture the last five lines of output. This is the canonical validation
step used across the project and by automation.

## Inputs

- `repo_root` (string, default `.`): repository root where the command should
  be executed.

## Outputs

- `pytest_summary` (string): the last five lines produced by the test command,
  intended for quick inspection and automated parsing.

## Procedure

1. From the repository root, run the full test-suite exactly once and capture
   the last five lines of output:

```bash
uv run pytest --tb=short 2>&1 | tail -5
```

2. Read the five-line summary for pass/fail status and short failure traces.

## Constraints / Rules

- Run the exact command above and only once per validation cycle.
- Do NOT re-run pytest to extract counts; do not use `-q` or otherwise change
  pytest output formatting.
- Do NOT change the `tail` window (it must be `tail -5`).
- pytest is configured with `filterwarnings = ["error"]` in `pyproject.toml`;
  warnings are treated as test errors. Do NOT suppress or ignore warnings
  without fixing their root cause.

## Examples

```bash
cd "$REPO_ROOT"
uv run pytest --tb=short 2>&1 | tail -5
```

## Rationale

Using a single, canonical command keeps CI output consistent and makes
automated tooling and skills (like Copilot skills) reliable.

