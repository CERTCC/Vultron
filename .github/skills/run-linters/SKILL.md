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
  - "uv run black vultron/ test/ && uv run flake8 --exit-zero vultron/ test/ && uv run mypy && uv run pyright"
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

## Inputs

- `repo_root` (string, default `.`): repository root where the command should
  be executed.

## Outputs

- `lint_summary` (string): the combined stdout/stderr from the lint commands; the
  exit status indicates whether any linters failed.

## Procedure

1. From the repository root (or `repo_root`), run the combined linters:

```bash
uv run black vultron/ test/ && uv run flake8 --exit-zero vultron/ test/ && uv run mypy && uv run pyright
```

2. Inspect each tool's output. `black` will reformat files in-place. `flake8`
   runs with `--exit-zero` here (to collect issues without failing the whole
   command chain); you may want to run `uv run flake8 vultron/ test/` separately
   during development to see non-zero exit behavior.

3. Address issues reported by each tool and repeat until the suite is clean.

## Constraints / Rules

- Run `black` first to ensure formatting does not generate spurious lint
  failures.
- `flake8` is invoked with `--exit-zero` in this combined command to allow
  collection of issues across all linters; CI may run `flake8` without
  `--exit-zero` to fail the build on lint errors.
- `mypy` and `pyright` are both included to provide complementary type
  checking; teams may prefer one over the other, but including both helps
  surface different classes of type issues.

## Examples

```bash
# Run the combined linters (recommended for local pre-commit checks)
uv run black vultron/ test/ && uv run flake8 --exit-zero vultron/ test/ && uv run mypy && uv run pyright
```

## Rationale

Grouping linters into a single skill provides a reproducible developer
workflow and makes it easier for agents and automation to invoke the same set
of checks maintainers use. Including both `mypy` and `pyright` gives
coverage from two type-checking tools that can catch different issues.

