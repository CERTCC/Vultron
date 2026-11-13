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
  - "markdownlint-cli2 --fix --config .markdownlint-cli2.yaml <changed .md files>"
  - "./mdlint.sh <changed .md files>  # alternative: wrapper, same exclusions"
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
`markdownlint-cli2`. Prefer invoking the tool directly with the repository's
configuration file (`.markdownlint-cli2.yaml`) so behavior is explicit and
consistent. The repository also includes a legacy wrapper script (`mdlint.sh`)
which is retained as an alternative for environments that rely on it.

## Inputs

- `repo_root` (string, default `.`): repository root where the command should
  be executed.

## Outputs

- `lint_summary` (string): machine- and human-readable summary printed to
  stdout/stderr (exit status indicates success/failure).

## Procedure

1. From the repository root (or `repo_root`), run the linter directly using the
project config on the Markdown files you changed (preferred):

```bash
markdownlint-cli2 --fix --config .markdownlint-cli2.yaml notes/x.md docs/y.md
```

1. The wrapper `./mdlint.sh` is an alternative; pre-commit does not need it
(the hook invokes `markdownlint-cli2` directly). Pass it the same files:
`./mdlint.sh notes/x.md` lints and fixes only those. With no arguments it
lints every Markdown file in the checkout, which is rarely what a task needs.
Both forms skip `.claude/worktrees/` and every `plan/history/` (#6232).

2. Inspect the output. The wrapper attempts to auto-fix problems. If linting
   still reports failures, address them manually and re-run the command.

## Constraints / Rules

- Prefer invoking `markdownlint-cli2` directly with `--config .markdownlint-cli2.yaml`.
- The wrapper `./mdlint.sh` remains available as an alternative for legacy
   environments.
- Do NOT run markdownlint across generated or dependency directories unless
   your configuration deliberately includes them. The repository config file
   contains the canonical ignore patterns.
- Commit any formatting changes produced by the linter before running other
  commit-time checks.

## Examples

```bash
# preferred (direct, uses .markdownlint-cli2.yaml), on the changed files
markdownlint-cli2 --fix --config .markdownlint-cli2.yaml notes/x.md

# alternative (wrapper), same files
./mdlint.sh notes/x.md

# whole checkout (wrapper with no arguments)
./mdlint.sh
```

## Rationale

Centralizing markdown linting through `mdlint.sh` ensures the same config and
exclusions are used by maintainers, CI, and automation. Including this SKILL
makes the capability discoverable by agents and documents the canonical
command for formatting markdown.
