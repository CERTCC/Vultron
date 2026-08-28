---
title: 1140 non-protocol-kind MUST requirements still lack verification fields
type: learning
timestamp: "2026-08-25T00:00:00Z"
source: ISSUE-2467
signal: concern
---

ISSUE-2467 backfilled `verification:` for all 749 protocol-kind MUST requirements,
satisfying AC-3. However, 1140 MUST requirements of other kinds still lack
`verification:` fields:

- `project`: 915 requirements
- `process`: 156 requirements
- `architecture`: 69 requirements

These produce 1140 `MUST_WITHOUT_VERIFICATION` advisory warnings from
`spec-lint`. None were in scope for ISSUE-2467, but the backlog remains large
and is the majority of the original 1910-warning total from CONCERN-2382.

Follow-up: consider a separate task or Epic to backfill non-protocol-kind
requirements — especially `architecture` (69) and `process` (156) which are
less numerous than `project` (915) and may be more actionable in a single pass.

**Promoted**: 2026-08-27 — archived (already in specs/notes/AGENTS.md or tracked as GitHub issue). Docs PR: <pending>.
