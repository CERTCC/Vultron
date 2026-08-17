---
title: "Introduced a generic ledger payload_snapshot override seam rather than a status-specific one"
type: learning
timestamp: "2026-08-12T00:00:00Z"
source: ISSUE-2235-ledger-payload
signal: design-question
---

ISSUE-2235 required the canonical `CaseLedgerEntry` to snapshot the *accepted*
portion of an inbound `ParticipantStatus`, not the raw assertion. `CommitCaseLedgerEntryNode`
builds `payload_snapshot` from the activity, so something had to let a preceding
guard substitute the `object` entry. Two shapes were available:

1. A status-specific hook on `CommitCaseLedgerEntryNode` (e.g. read
   `append_status_dimension_filter` directly).
2. A **generic** override key, `ledger_payload_object_override`, carrying
   `{"object_id", "object"}`, which any receive tree may publish.

Option 2 was chosen and the key is defined in
`vultron/core/behaviors/case/nodes/lifecycle.py` next to its consumer, not next
to its (currently sole) producer — so the import direction stays status → case,
matching the pre-existing edge, and no cycle is introduced.

This was a decision beyond what the issue asked for. Rationale: the same need
recurs for every seam that adjudicates before committing (Seam 2 `em`,
ISSUE-2256, is the immediate next case), and a per-concern hook on the commit
node would accumulate one branch per concern inside the single writer of the
hash chain.

The risk it accepts: the commit node — the one place that must be trustworthy,
since its output is hash-chained and replicated to every participant — now has an
opt-in path by which an upstream node can rewrite what gets committed. It is
mitigated by being ID-matched (the override is ignored unless it names the object
being committed) and by logging the substitution at INFO. Anything wired to
produce this key is effectively asserting canonical content and should be
reviewed with that in mind.

**Promoted**: 2026-08-17 — captured in GitHub #2326 (Concern: ledger_payload_object_override seam).
Docs PR: <https://github.com/CERTCC/Vultron/pull/2330>0>0>0>0>0>0>0>0>0>.
