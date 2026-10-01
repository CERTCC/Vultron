---
id: "format-code"
title: "Format code with ruff"
description: "Format Python sources in the repository with ruff and apply its safe lint fixes (pre-commit enforced)."
author: "CERTCC / Vultron"
tags:
  - formatting
  - dev-workflow
shell: "zsh"
commands:
  - "uv run ruff check --fix && uv run ruff format"
inputs:
  - name: repo_root
    description: "Repository root"
    default: "."
outputs:
  - name: formatted_files
    description: "Files fixed or reformatted by ruff (stdout)"
---

# Skill: Format code with ruff

## Purpose

Format Python source files with `ruff format` and apply ruff's safe lint fixes
(import sorting among them). This keeps a consistent code style and avoids
pre-commit failures.

## Inputs

- `repo_root` (string, default `.`): repository root where the command should
  be executed.

## Outputs

- `formatted_files` (string): stdout from ruff listing files fixed or
  reformatted.

## Procedure

1. From the repository root, run:

   ```bash
   uv run ruff check --fix
   uv run ruff format
   ```

2. Inspect the output and stage changes if any files were rewritten.

## Constraints / Rules

- Do not pass paths. Scope is declared in `[tool.ruff]` in `pyproject.toml`
  (IMPLTS-07-021); `ruff format` excludes Markdown there, so fenced Python in
  docs, notes and `plan/history/` is never rewritten.
- Use `markdownlint-cli2` for Markdown.
- Formatting can rewrap a line and strand an inline pragma. `run-linters` runs
  `ruff check`, mypy and pyright after formatting; use it before committing.

## Rationale

One formatter, whose import sorting and lint fixes share one configuration,
keeps the pre-commit hook, the CI `lint-ruff` job and local runs in agreement
(ADR-0094).
