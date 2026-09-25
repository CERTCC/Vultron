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
  - ".github/scripts/mkdocs-build-strict.sh"
  - "uv run docs-withheld"
  - "uv run docs-links"
  - "uv run docs-legacy-urls"
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

Validate that documentation builds cleanly without real warnings or broken links using
`mkdocs build --strict`. This ensures the documentation site is correct before
committing changes to `docs/` directory files.

When the `docs/` directory is modified, `mkdocs build --strict` MUST pass with
zero real warnings before code is staged for commit. CI enforces the same
constraint: both `docs-build-check.yml` and `deploy_site.yml` run a plain
`mkdocs build --strict` (DOCBW-03-009). CI suppresses **nothing**, so a warning
this script forgives below still fails CI; the suppression list exists only for
the griffe false positives, which are absent from the current build.

**Note**: This skill automatically suppresses false-positive warnings from griffe
that result from Python decorators being misinterpreted as bibliography citations
(e.g., `@dataclass`, `@main.command`, `@prefix`). Real documentation errors are
still reported and must be fixed.

## Inputs

- `repo_root` (string, default `.`): repository root where the command should
  be executed.

## Outputs

- `build_status` (string): machine- and human-readable summary printed to
  stdout/stderr (exit status indicates success/failure). A successful build
  prints "Successfully built docs!" and exits with code 0. A build with
  real warnings exits with code 1 and prints the warning count.

## Procedure

1. From the repository root, run the build script:

```bash
.github/scripts/mkdocs-build-strict.sh
```

1. Inspect the output. Any broken links, missing anchors, or other real issues
   are printed as `WARNING` lines to stdout. False-positive warnings from griffe
   decorators are automatically suppressed.

2. Fix all reported real issues in the `docs/` files and re-run the command until
   it exits with code 0.

3. Check the publication axis against the site the previous step just built:

```bash
PYTHONPATH='' uv run docs-withheld
PYTHONPATH='' uv run docs-legacy-urls
```

   `docs-withheld` fails when an artifact the project declared withheld
   produced files in `site/` (DOCBW-03-005). `docs-legacy-urls` fails when a
   URL an earlier publish served no longer resolves as a page or a redirect
   (DOCBW-03-008). The fix for a moved page is a `redirect_maps` entry in
   `mkdocs.yml`. A page withdrawn on purpose gets a declaration in
   `vultron/metadata/docs/withheld.py` instead. Both checks read the built tree,
   so they only mean anything after step 1 succeeded. Both the pull-request
   workflow and `deploy_site.yml` run them through the
   `check-site-publication` action, so a failure here is a failure that would
   have blocked the deploy.

1. Check the reference axis against the same build:

```bash
PYTHONPATH='' uv run docs-links
```

   This resolves every internal `href`/`src` on every page in `site/` and
   fails on any that points at a file the build did not produce, printing each
   as `<page>: <reference>` (DOCBW-03-007). It covers what `--strict` cannot:
   links printed by `markdown-exec` blocks, links to withheld pages, and pages
   nothing links to. Both workflows run it, unconditionally, through the same
   `check-site-publication` action.

1. Stage changes only after all four commands exit cleanly with zero code.

## Constraints / Rules

- Run the build script only when files in `docs/` are modified.
- All documentation MUST build cleanly; no real warnings are acceptable in strict mode.
- Common real issues to watch for:
  - Broken anchor links: `#section-name` references that do not exist in the
    target file (including auto-generated anchors from headings)
  - Missing files: links to documentation files that have been deleted or moved
  - Invalid markdown: syntax errors that prevent proper parsing
- Validate links using `markdownlint-cli2` BEFORE running the build script
  to catch markdown syntax issues early.
- Run `docs-withheld`, `docs-legacy-urls` and `docs-links` AFTER the build
  script, never before: they read `site/`, and they fail rather than pass when
  that directory is absent or empty.

## Examples

```bash
# Build docs in strict mode (required when docs/ changes)
.github/scripts/mkdocs-build-strict.sh
```

## Rationale

Validating documentation builds during development prevents broken links and
build failures from reaching CI. The `--strict` flag treats warnings as errors,
ensuring high quality documentation. This skill provides a discoverable,
reproducible invocation matching CI behavior, reducing surprise failures and
improving documentation quality. The script suppresses false-positive griffe
warnings while maintaining strict validation of real documentation issues.

## False-Positive Warnings Suppressed

The script automatically suppresses the following false-positive warnings:

- `Inline reference to unknown key petterogren7535` — YouTube handle
- `Inline reference to unknown key main` — `@main.command` decorator
- `Inline reference to unknown key v4` — GitHub Actions version reference
- `Inline reference to unknown key dataclass` — Python decorator
- `Inline reference to unknown key prefix` — Common word in code
- `Inline reference to unknown key base` — Common word in code
- `[mkdocs-print-site]` plugin ordering warning — Version-specific false positive

These occur when griffe's docstring parser encounters Python decorators and
misinterprets them as bibliography citations. They are harmless and do not
indicate documentation problems.

## Related Skills

- `.agents/skills/format-markdown/SKILL.md` — Lint markdown in docs/ files
