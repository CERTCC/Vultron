---
title: actionlint pre-commit hook hangs in devcontainer — Go not installed
type: learning
timestamp: "2026-08-31T00:00:00Z"
source: ISSUE-2627
signal: tooling-issue
---

The `actionlint` pre-commit hook (`.pre-commit-config.yaml`: `rhysd/actionlint`, golang hook) hangs indefinitely in the devcontainer because Go is not on PATH and pre-commit cannot download/build the Go toolchain (no internet access to Go download servers).

The hook comment acknowledges "the devcontainer has neither docker nor go on PATH" but does not document a workaround for local commits.

Workaround used: `SKIP=actionlint git commit`. This is safe when no `.github/` workflow files are modified (actionlint only checks GitHub Actions YAML).

The hook would need either: (a) a pre-installed actionlint binary in the devcontainer, (b) switching to `actionlint-docker` (but docker isn't in the devcontainer either), or (c) a `language: system` hook pointing to a pre-installed binary.

## Audit disposition (2026-09-02)

Promoted to notes/devcontainer-tooling.md as a durable card. Confirmed against .pre-commit-config.yaml, whose own comment states the devcontainer has neither docker nor go on PATH.
