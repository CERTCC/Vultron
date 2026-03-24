---
id: "format-markdown"
title: "Format Markdown with markdownlint-cli2"
description: "Run markdownlint-cli2 consistently using the repository's wrapper script to lint and auto-fix markdown files." 
author: "CERTCC / Vultron"
tags:
  - markdown
  - linting
  - dev-workflow
shell: "zsh"
commands:
  - "./mdlint.sh"
  - "markdownlint-cli2 --fix --config .markdownlint-cli2.yaml \"**/*.md\" \"#.venv/**\" \"#.git/**\" \"#node_modules/**\" \"#wip_notes/**\""
inputs:
  - name: repo_root
    description: "Repository root where the command will be executed"
    default: "."
outputs:
  - name: lint_summary
    description: "Exit status and any remaining lint failures printed to stdout/stderr"
---

# Skill: Format Markdown with markdownlint-cli2

## Purpose

Ensure consistent markdown formatting and linting across the repository using
`markdownlint-cli2`. The project provides a small wrapper script (`mdlint.sh`)
that runs `markdownlint-cli2 --fix` with the canonical config and excludes
local development artefacts; this SKILL documents and standardizes that usage.

## Inputs

- `repo_root` (string, default `.`): repository root where the command should
  be executed.

## Outputs

- `lint_summary` (string): machine- and human-readable summary printed to
  stdout/stderr (exit status indicates success/failure).

## Procedure

1. From the repository root (or `repo_root`), run the wrapper script which
   invokes `markdownlint-cli2` with the project's config and excludes:

```bash
./mdlint.sh
```

2. If you prefer to run the linter directly (the wrapper is the recommended
   approach), use this explicit command (note quoting/escaping for zsh):

```bash
markdownlint-cli2 --fix --config .markdownlint-cli2.yaml "**/*.md" "#.venv/**" "#.git/**" "#node_modules/**" "#wip_notes/**"
```

3. Inspect the output. The wrapper attempts to auto-fix problems. If linting
   still reports failures, address them manually and re-run the command.

## Constraints / Rules

- Use the wrapper `./mdlint.sh` to ensure the same exclusions and `--fix`
  behavior across environments.
- Do NOT run markdownlint across generated or dependency directories
  (e.g., `.venv`, `node_modules`, `.git`, `wip_notes`). The wrapper already
  excludes these patterns.
- Commit any formatting changes produced by the linter before running other
  commit-time checks.

## Examples

```bash
# recommended (uses wrapper with repo exclusions)
./mdlint.sh

# direct invocation (equivalent)
markdownlint-cli2 --fix --config .markdownlint-cli2.yaml "**/*.md" "#.venv/**" "#.git/**" "#node_modules/**" "#wip_notes/**"
```

## Rationale

Centralizing markdown linting through `mdlint.sh` ensures the same config and
exclusions are used by maintainers, CI, and automation. Including this SKILL
makes the capability discoverable by agents and documents the canonical
command for formatting markdown.

