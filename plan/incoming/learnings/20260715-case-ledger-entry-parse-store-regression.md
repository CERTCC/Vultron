---
title: "CaseLedgerEntry parse-time store causes CheckLedgerEntryAlreadyStored false positive"
type: learning
timestamp: "2026-07-15T17:45:00Z"
source: "PR #1447 / ISSUE-1324"
---

## Observation

`_store_nested_inbox_object` in `_inbox.py` pre-stores the inline `object_`
of every Announce activity into the DataLayer BEFORE the BT runs.  For
`Announce(CaseLedgerEntry)`, this made `CheckLedgerEntryAlreadyStoredNode`
fire SUCCESS on first delivery, skipping `LogEntryEventEffects` entirely.

Symptom: `ApplyInviteAcceptFromLedger` never ran → vendor2 not added as
participant → FVV demo participant count stayed at 3.

## Fix

Added guard in `_store_nested_inbox_object` to skip objects whose `type_`
field equals `"CaseLedgerEntry"`.  `PersistReceivedLogEntryNode` is the
canonical writer; rehydration doesn't need it in DataLayer because
`object_` is already typed from the wire parser.

## Lesson

When introducing new DataLayer-existence checks as BT gates, verify that
the adapter layer doesn't pre-store objects that would trigger the gate
prematurely.  Pre-parse storage is for rehydration of string-ID references,
NOT for domain state management.
