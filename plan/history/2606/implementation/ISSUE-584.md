---
source: ISSUE-584
timestamp: '2026-06-01T18:04:49.839559+00:00'
title: Rename linkchecker.yml to docs-build-check.yml with narrowed triggers
type: implementation
---

## Issue #584 — Implement docs-build-check.yml: narrowed triggers and conditional link-check step

Renamed `.github/workflows/linkchecker.yml` to
`.github/workflows/docs-build-check.yml` and rewrote its content to
implement DOCBW-01 through DOCBW-05 (`specs/docs-build-workflow.yaml`).

**Changes made:**

- Renamed workflow file; updated `name:` to `Docs Build and Link Check`
- Narrowed `pull_request` trigger paths: removed `**/*.md`, added `docs/**`,
  `overrides/**`, `references.bib`, `mkdocs.yml`, `pyproject.toml`, `uv.lock`,
  the workflow file, and specific root markdown files included via
  `{% include-markdown %}` in docs pages
- Added `Check if docs/ changed` filter step that sets `docs_changed` output:
  always `true` on `workflow_dispatch`, uses `git diff --name-only` against PR
  base for PRs
- `Build Site` step runs unconditionally on every trigger
- `Check links` step gated on `steps.filter.outputs.docs_changed == 'true'`
- Used `env:` variable for `github.base_ref` in git diff to prevent shell
  injection
- `fetch-depth: 0` on checkout for correct three-dot diff

PR: [#646](https://github.com/CERTCC/Vultron/pull/646)
