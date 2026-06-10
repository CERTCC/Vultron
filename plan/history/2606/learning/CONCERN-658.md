---
source: CONCERN-658
timestamp: '2026-06-02T17:02:37.905184+00:00'
title: Split notes/architecture-ports-and-adapters.md monolith into focused sub-files
type: learning
---

## Summary

`notes/architecture-ports-and-adapters.md` grew to 926+ lines (~40 sections)
covering the hexagonal overview, layer rules, port taxonomy, inbound/outbound
patterns, per-adapter details, DataLayer scope boundaries, and more. Agents
accumulated new content here even when a more targeted per-port or per-adapter
notes file would have been more appropriate.

## Category

- Technical debt

## Severity

medium

## Evidence

- `notes/architecture-ports-and-adapters.md` (869–926 lines, ~40 sections)

## Impact if Ignored

The file continues to grow as a monolith. Agents miss relevant sections or
add per-adapter content to the wrong place. Cross-references become harder
to maintain. Discoverability degrades as the table of concerns grows.

## Resolution

**Resolved**: 2026-06-02 — implementation tracked in
[#666](https://github.com/CERTCC/Vultron/issues/666).

The implementation issue (#666) covers a 3-way split into:

- `notes/architecture-hexagonal.md` — overview, layer model, Rules 1–9,
  design constraints, review checklist
- `notes/architecture-ports.md` — port taxonomy, dispatch/emit terminology,
  use-case-as-port design note
- `notes/architecture-adapters.md` — per-adapter details, delivery invariants,
  ASGI emitter patterns, driven ports, ratchet test

All cross-references (AGENTS.md, vultron/core/ports/ docstrings,
vultron/adapters/\_\_init\_\_.py, docs/adr/\*.md, docs/reference/codebase/,
specs/vocabulary-model.yaml, notes/asgi-emitter.md) will be updated, and
the original file marked `status: superseded` with `superseded_by` pointing
at the three new files. notes/README.md will be updated with Load-when
descriptions for all three new files.

No docs-only PR opened (the split itself is the implementation work, tracked
in #666).
