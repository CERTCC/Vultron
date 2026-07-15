---
title: FastAPIIngressAdapter.rehydrate() must not re-read from DataLayer for inline objects
type: learning
timestamp: 2026-07-15T18:26:00Z
source: ISSUE-1324
---

## Root Cause

When `FastAPIIngressAdapter.rehydrate(activity)` called `rehydrate(activity.id_, dl)`,
it re-read the activity from the DataLayer. The DataLayer's `_dehydrate_data` collapses
any inline `object_` dict to its bare ID string on write. On read, `_rehydrate_fields`
tries to expand that string via `dl.read(entry.id_)`.

For `Announce(CaseLedgerEntry)`, `CheckLedgerEntryAlreadyStoredNode` requires that only
`PersistReceivedLogEntryNode` stores the entry. So `_store_nested_inbox_object` correctly
skips storing the CaseLedgerEntry. But this means `dl.read(entry.id_)` returns None during
rehydration, so `object_` stays as a bare string.

`find_matching_semantics()` then sees `Announce` + `object_=string` + `strict=False`
and matches `AnnounceVulnerabilityCasePattern` (earlier in the registry than
`AnnounceLogEntryPattern`). The activity is dispatched as `announce_vulnerability_case`,
the BT for log-entry processing never runs, and `PersistReceivedLogEntryNode` is never
called. The CI invariant harness times out waiting for contiguous ledger coverage.

## Fix

Two-part fix:

1. `_store_nested_inbox_object` now writes the re-parsed specific-type object back onto
   `activity.object_` (mutates in-place via `cast(Any, activity).object_ = typed_nested`).
   This gives the in-memory activity a fully-typed CaseLedgerEntry before the BT pipeline
   begins.

2. `FastAPIIngressAdapter.rehydrate()` now calls `rehydrate(activity, dl)` (passing the
   in-memory object) instead of `rehydrate(activity.id_, dl)` (going through DataLayer).
   The in-memory activity already has the typed CaseLedgerEntry on `object_`, so
   `find_matching_semantics` correctly identifies `ANNOUNCE_CASE_LEDGER_ENTRY`.

## Key Invariant

`_store_nested_inbox_object` serves TWO purposes:

1. Preserves domain-specific fields of inline objects (case_id, log_index, etc.) by
   re-parsing with the specific vocabulary class via `_reparse_as_specific_type`.
2. Stores the result in DataLayer for rehydration of the REPLAY path
   (StoredActivityIngressAdapter reads by activity ID after bootstrap).

For CaseLedgerEntry, purpose (2) is suppressed because pre-storage breaks the
`CheckLedgerEntryAlreadyStoredNode` idempotency gate. Purpose (1) is preserved via
the in-memory mutation.

The replay path (deferred activities via StoredActivityIngressAdapter) would still fail
if a CaseLedgerEntry Announce is deferred, because the entry is not in DataLayer when
replayed. In practice, Announce(CaseLedgerEntry) is only deferred if the case isn't
known yet — a race condition that doesn't occur in the current demos. A follow-up issue
should track this edge case.
