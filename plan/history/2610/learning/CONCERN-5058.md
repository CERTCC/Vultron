---
source: CONCERN-5058
timestamp: '2026-10-21T19:30:22.866541+00:00'
title: 'VultronReplicationState join-backfill fields are write-only after #5032'
type: learning
---

## Summary

Since #5032 removed the dispatcher's join-backfill gate, nothing reads the three join-backfill fields of `VultronReplicationState` (`join_backfill_target_index`, `join_backfill_last_sent_index`, `join_backfill_complete`) as a decision input.

- `BackfillCanonicalLedgerToInviteeNode` writes them and reads back only what it has just written in the same call.
- The duplicate-Accept guard (`CheckInviteeNotAlreadyParticipantNode`) checks only that a state exists, not these fields.
- Their only other reader is the model's own consistency validator.

The join backfill commits with its Accept in one act (CLP-07-015), so the fields no longer record progress that anything resumes.

## Question

Should the fields be retired? This is a stored-schema change: a renamed or removed stored field refuses its old key through `RetiredFieldsRecord` (#4128). If not, what reader should they serve?

Governing specs: CLP-07-015, SYNC-04-001

Where: vultron/core/models/replication_state.py

**Resolved**: 2026-10-21 — implementation tracked in #5074.

Docs PR: <https://github.com/CERTCC/Vultron/pull/5077>.

Spec: `specs/case-management.yaml` (CM-17-012).
