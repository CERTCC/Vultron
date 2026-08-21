---
source: CONCERN-2106
timestamp: '2026-08-21T20:34:33.273396+00:00'
title: Ledger replication scope — RFC vs companion spec
type: learning
---

## Outcome

Resolved concern #2106: decided that ledger replication mechanics belong in an
external-facing companion document, not in the main Vultron protocol RFC.

## Decision

- The main RFC (`docs/reference/draft-vultron-spec.md`) will resolve Open
  Question #2 with a scoping note and a forward reference to the companion doc.
- A new external-facing companion document
  (`docs/reference/draft-vultron-replication-spec.md`) will cover replication
  mechanics in RFC style, suitable for external reviewers.
- The single-hub / single-writer + fan-out model is **normative** for the
  Hosting capability set.
- Distributed consensus (Raft-style multi-node CaseActor cluster) is a future
  extension, explicitly out of scope for the current spec.
- ADR-0069 (`docs/adr/0069-ledger-replication-companion-spec.md`) will document
  the boundary decision and the rationale.

## Notes file updated

`notes/sync-ledger-replication.md` — added "Document Boundary" section
explaining the split between the internal SYNC spec and the forthcoming
companion document; notes the companion must stay consistent with
`specs/sync-ledger-replication.yaml`.

## Docs PR

<https://github.com/CERTCC/Vultron/pull/2493>

## Implementation Issues

- #2494 (size:M) — resolve OQ#2 in RFC, write ADR-0069, confirm single-hub normative
- #2495 (size:L) — write companion ledger replication spec document
