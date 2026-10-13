---
source: NOTES-case-ledger-authority--commit-authorization-and-coverage-clp-09-epic-788-retrospective
timestamp: '2026-10-12T19:32:52.891804+00:00'
title: 'Commit Authorization and Coverage (CLP-09, Epic #788 retrospective)'
type: note
---

**Archived:** 2026-10-12
**Reason:** retrospective; the three gaps are recorded in CLP-09-001/003/004 rationale
**Superseded by:** specs/case-ledger-processing.yaml CLP-09; vultron/core/behaviors/case/AGENTS.md

---

## Commit Authorization and Coverage (CLP-09, Epic #788 retrospective)

Three gaps surfaced late in Epic #788 that CLP-09 now makes explicit, because
the prior framing (BT-10-004's single line, "CASE_MANAGER MUST enforce
case-level authorization") was not specific enough to prevent them from
accumulating call site by call site.

The three gaps are now recorded in the `rationale` of CLP-09-001 (authorization
was a convention, not a gate), CLP-09-003 (commit coverage had no structural
check) and CLP-09-004 (dual-invocation use cases need per-invocation
authorization). The guarded-commit composition itself is shown at the top of
`vultron/core/behaviors/case/AGENTS.md`.

---
