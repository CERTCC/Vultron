---
title: "Issue #2495 AC-3 names ADR-0069 but correct ADR is ADR-0077"
type: learning
timestamp: "2026-08-26T19:55:00Z"
source: ISSUE-2495
signal: process-issue
---

Issue #2495 AC-3 states: "Document references ADR-[0069] for the rationale
behind the companion-doc boundary decision."

ADR-0069 on `main` is "Adopt certcc.github.io/Vultron as the Initial Vultron
Vocabulary Namespace Host" — the namespace URI decision, completely unrelated
to ledger replication.

The correct ADR is **ADR-0077** — "Scope Ledger Replication Mechanics to a
Companion Spec; Single-Hub Fan-Out Is Normative." This was confirmed by:

- `notes/sync-ledger-replication.md` § "Document Boundary": explicitly
  references ADR-0077, not ADR-0069.
- `docs/adr/index.md` line 149: ADR-0077 is the companion-spec boundary ADR.
- `docs/reference/draft-vultron-spec.md` §7.2 forward reference: "See ADR-0077."

This is a stale issue body — the issue was written when ADR-0077 was planned
as ADR-0069 (a number-collision artefact; the plan/history learning
`20260822-adr-number-is-a-claim-on-a-shared-sequence.md` documents this
collision). When ADR-0077 actually landed, the issue body was not updated.

The companion doc at PR #2703 references ADR-0077 correctly. The issue body
discrepancy was noted in the PR description.
