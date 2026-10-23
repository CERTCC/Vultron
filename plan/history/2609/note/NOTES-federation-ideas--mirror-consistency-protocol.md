---
source: NOTES-federation-ideas--mirror-consistency-protocol
timestamp: '2026-09-17T17:25:20.947419+00:00'
title: Mirror Consistency Protocol
type: note
---

**Archived:** 2026-09-17
**Reason:** (a,b) delivered (single-instance); cross-instance nuance kept as a pointer in-file
**Superseded by:** specs/sync-ledger-replication.yaml; notes/participant-case-replica.md

---

## 9. Mirror Consistency Protocol

- **Push by default**: CaseActor DMs all relevant Journal activities to
  participants as they occur, with `journalSeq` and `journalPrev` fields
  enabling immediate local ordering.
- **Non-repudiation**; Because each Journal entry contains `JournalPrev`
  (hash of previous entry) and is signed by CaseActor, participants can
  verify the integrity and authenticity of the Journal stream as it arrives.
- **Gap detection**: participants track received sequence numbers (provided
  by `journalSeq`) and detect gaps (e.g., received seq 1,2,3,5 → seq 4 is missing → trigger pull
  reconciliation).
- **Pull reconciliation**: participants can fetch the CaseActor's `/outbox` (AS2
  `OrderedCollection`, paginated) to resync at any time. This is the fallback,
  not the primary path. CaseActor will need to enforce that only active
  participants can fetch the Journal.
