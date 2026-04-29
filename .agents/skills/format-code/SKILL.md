---
id: "format-code"
title: "Format code with Black"
description: "Format Python sources in the repository using Black (pre-commit enforced)."
author: "CERTCC / Vultron"
tags:
  - formatting
  - dev-workflow
shell: "zsh"
commands:
  - "uv run black vultron/ test/ && uv run flake8 vultron/ test/"
inputs:
  - name: repo_root
    description: "Repository root"
    default: "."
outputs:
  - name: formatted_files
    description: "Files modified by Black (stdout)"
---

# Skill: Format code with Black

## Purpose

Format Python source files in the repository using Black. This ensures a
consistent code style and avoids pre-commit failures.

## Inputs

- `repo_root` (string, default `.`): repository root where the command should
  be executed.

## Outputs

- `formatted_files` (string): stdout from Black listing files reformatted.

## Procedure

1. From the repository root, run Black and flake8 on the `vultron/` and
   `test/` directories:

```bash
uv run black vultron/ test/ && uv run flake8 vultron/ test/
```

1. Inspect the output and stage changes if any files were reformatted.

## Constraints / Rules

- Do NOT run Black on markdown files; use `markdownlint-cli2` for markdown.
- Run Black before staging changes for commit; pre-commit hooks assume code is
  formatted.

## Examples

```bash
cd "$REPO_ROOT"
uv run black vultron/ test/ && uv run flake8 vultron/ test/
```

## Rationale

Using Black guarantees consistent formatting across the codebase and prevents
pre-commit failures during CI and developer commits.
