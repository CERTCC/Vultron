---
source: ISSUE-666
timestamp: '2026-06-08T13:41:01.238075+00:00'
title: Notes frontmatter and docs-build warning constraints
type: learning
---

## 2026-06-02 ISSUE-666 — Notes frontmatter and docs-build warning constraints

- `notes/*.md` frontmatter currently enforces `superseded_by` as a single
  non-empty string (not a YAML list), so split-note migrations should point
  `superseded_by` at one canonical successor and list sibling files in
  `related_notes` or body text.
- `.github/scripts/mkdocs-build-strict.sh` suppresses several known griffe
  false positives but still treats unknown-key warnings like `context` and
  `pytest` as real build failures.

**Promoted**: 2026-06-08 — captured in `AGENTS.md`, `notes/codebase-structure.md`, and `notes/domain-model-separation.md`.
Docs PR: <https://github.com/CERTCC/Vultron/pull/818>.
