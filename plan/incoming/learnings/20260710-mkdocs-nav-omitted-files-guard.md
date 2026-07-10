---
title: Enabling mkdocs nav.omitted_files requires declaring intentional omissions first
type: learning
timestamp: 2026-07-10
source: ISSUE-1304
---

While adding a `validation.nav.omitted_files: warn` regression guard to catch
un-navved docs pages (#1304), two non-obvious facts surfaced:

- **`exclude_docs` does NOT satisfy the nav-omission validator.** Pages under
  `docs/developer/` are excluded from the published build via `exclude_docs`,
  but the nav validator still flagged them as "not included in the nav." They
  had to *also* be listed in `not_in_nav` (`developer/**/*.md`) for the guard
  not to flood. Same for `agents/*.md`, `reference/inbox_handler.md`, and
  `reference/code/hexagonal_architecture.md` — all intentional omissions must
  be enumerated in `not_in_nav` before turning the guard on.
- **`mkdocs.dev.yml` REPLACES `not_in_nav`, it does not merge.** The dev
  overlay (`INHERIT: mkdocs.yml`) sets its own `not_in_nav: | developer/**`,
  which fully overrides the base list rather than extending it. MkDocs cannot
  append to list-based nav config via inheritance. CI runs the dev config
  non-strict, so the inherited `validation` block only warns there — but be
  aware the two configs have divergent omission lists.

Also: CI's `docs-build-check.yml` runs plain `uv run mkdocs build` (non-strict)
for both configs, so `omitted_files: warn` never *fails* CI — it fails only the
local `mkdocs-build-strict.sh` wrapper. The wrapper itself counts known
false-positive warnings (griffe decorator/bib misreads: `dataclass`, `prefix`,
`base`, print-site) and exits 0 if only those remain; genuine pre-existing
warnings (`markdown_exec` code-block execution errors, `context`/`pytest` bib
keys) make it exit non-zero even on clean `main`, so don't treat a red strict
wrapper as a regression without a clean-base comparison.
