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

# Skill: Run repository linters

## Purpose

Run the project's canonical linters in a single, discoverable skill. This
combines code formatting (Black), Python linting (flake8), type checking
(mypy), and static type checking with Pyright into a single, reproducible
invocation for maintainers and automation.

All four tools **MUST** pass cleanly (zero exit code) before code is staged
for commit. This mirrors the CI pipeline (`python-app.yml`) which runs each
linter as a separate parallel job and only proceeds to build if every check
passes.

## Inputs

- `repo_root` (string, default `.`): repository root where the command should
  be executed.

## Outputs

- `lint_summary` (string): the combined stdout/stderr from the lint commands;
  the exit status indicates whether any linters failed.

## Procedure

1. From the repository root (or `repo_root`), run the combined linters:

```bash
uv run black vultron/ test/ && uv run flake8 vultron/ test/ && uv run mypy && uv run pyright
```

2. Inspect each tool's output. `black` will reformat files in-place. `flake8`,
   `mypy`, and `pyright` will print diagnostics. Fix all reported issues and
   repeat until the suite is clean.

3. Stage only after all four tools exit with code 0.

## Constraints / Rules

- Run `black` first — formatting errors cause spurious `flake8` failures.
- `flake8` MUST be run **without** `--exit-zero`; a non-zero exit means the
  commit is not ready.
- `mypy` and `pyright` are both required; they surface complementary classes
  of type errors.
- Do **not** commit code that produces warnings or errors from any of the four
  tools.

## Examples

```bash
# Run all linters (required before every commit)
uv run black vultron/ test/ && uv run flake8 vultron/ test/ && uv run mypy && uv run pyright
```

## Rationale

Grouping linters into a single skill provides a reproducible developer
workflow and makes it easier for agents and automation to invoke the same set
of checks maintainers use. All four linters are also enforced by CI, so
running them locally before committing avoids CI failures and preserves the
known-clean codebase baseline.

