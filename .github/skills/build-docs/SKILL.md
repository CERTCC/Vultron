---
id: "build-docs"
title: "Build docs with mkdocs in strict mode"
description: "Run mkdocs build with strict validation to ensure documentation builds cleanly and all links are valid."
author: "CERTCC / Vultron"
tags:
  - documentation
  - mkdocs
  - ci
  - dev-workflow
shell: "zsh"
commands:
  - "uv run mkdocs build --strict"
inputs:
  - name: repo_root
    description: "Repository root where the command will be executed"
    default: "."
outputs:
  - name: build_status
    description: "Exit status and summary from mkdocs build (zero exit code means success)"
---

# Skill: Build Docs with mkdocs in Strict Mode

## Purpose

Validate that documentation builds cleanly without warnings or broken links using
`mkdocs build --strict`. This ensures the documentation site is correct before
committing changes to `docs/` directory files.

When the `docs/` directory is modified, `mkdocs build --strict` MUST pass with
zero warnings before code is staged for commit. This mirrors the CI pipeline
which enforces the same constraint.

## Inputs

- `repo_root` (string, default `.`): repository root where the command should
  be executed.

## Outputs

- `build_status` (string): machine- and human-readable summary printed to
  stdout/stderr (exit status indicates success/failure). A successful build
  prints "Successfully built docs!" and exits with code 0. A build with
  warnings exits with code 1 and prints "Aborted with N warnings in strict
  mode!".

## Procedure

1. From the repository root, run the mkdocs build in strict mode:

```bash
uv run mkdocs build --strict
```

2. Inspect the output. Any broken links, missing anchors, or other issues are
   printed as `INFO` lines to stdout. In strict mode, even warnings cause the
   build to fail (exit code 1).

3. Fix all reported issues in the `docs/` files and re-run the command until
   it exits with code 0.

4. Stage changes only after the build exits cleanly with zero code.

## Constraints / Rules

- Run `mkdocs build --strict` only when files in `docs/` are modified.
- All documentation MUST build cleanly; no warnings are acceptable in strict mode.
- Common issues:
  - Broken anchor links: `#section-name` references that do not exist in the
    target file (including auto-generated anchors from headings)
  - Missing files: links to documentation files that have been deleted or moved
  - Invalid markdown: syntax errors that prevent proper parsing
- Validate links using `markdownlint-cli2` BEFORE running `mkdocs build --strict`
  to catch markdown syntax issues early.

## Examples

```bash
# Build docs in strict mode (required when docs/ changes)
uv run mkdocs build --strict
```

## Rationale

Validating documentation builds during development prevents broken links and
build failures from reaching CI. The `--strict` flag treats warnings as errors,
ensuring high quality documentation. This skill provides a discoverable,
reproducible invocation matching CI behavior, reducing surprise failures and
improving documentation quality.

## Related Skills

- `.github/skills/format-markdown/SKILL.md` — Lint markdown in docs/ files
