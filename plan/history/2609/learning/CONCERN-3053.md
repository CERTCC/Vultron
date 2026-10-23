---
source: CONCERN-3053
timestamp: '2026-09-17T17:14:26.125092+00:00'
title: Freshness/tail-hash helpers ignore disposition, contradicting CLP-04-003 recorded-only
  chain semantics
type: learning
---

## Concern

`CaseLedger` keeps two views and is explicit about which one the hash chain uses
(`vultron/core/models/case_ledger.py`):

- `entries` — the full audit log, recorded and rejected.
- `recorded_entries` — the `disposition == "recorded"` projection, "used for hash-chain computation and canonical state reconstruction. Per CLP-04-001, CLP-04-003."
- `tail_hash` — "Hash of the last *recorded* entry ... **Rejected entries do not advance the tail**."
- `next_index` — `len(self._entries)`, i.e. a `log_index` is consumed by **every** appended entry, rejections included.

Two helpers in `vultron/core/sync_helpers.py` did not follow those semantics:

1. `_reconstruct_tail_hash` collected all local `CaseLedgerEntry` objects for the case, sorted by `log_index`, and returned `entries[-1].entry_hash` — with no disposition filter. If the last stored entry was a rejection, this returned a hash that was not the chain tail.
2. `is_ledger_fresh_for_case` walked all local entries and required both `curr.log_index == prev.log_index + 1` and `curr.prev_log_hash == prev.entry_hash`. Neither holds across a rejection: the rejection consumes an index but does not advance the chain, so the next recorded entry's `prev_log_hash` points past it.

CLP-04-003 requires replicated hash chains and replay state to be computed over recorded entries only, so the helpers were the ones out of step.

## Design question (resolved)

The design question — whether the freshness gate and tail reconstruction should operate on the recorded projection or the full audit log — was resolved as: **the ledger must contain only canonical accepted entries**. Rejection outcomes belong in structured logs, not ledger entries. The `disposition`, `reason_code`, and `reason_detail` fields were removed from `HashChainLedgerRecord`, `CaseLedgerEntry`, and `as_CaseLedgerEntry`. The AGENTS.md guidance recommending `disposition="rejected"` for emit-side correlation markers was removed; emit-side dedup uses `PendingAssertionStore` instead.

**Resolved**: 2026-09-17 — implementation in PR #3330 (this PR closes the concern by removing the problematic fields and documenting the canonical-entries-only invariant as CLP-04-007).

Docs PR: <https://github.com/CERTCC/Vultron/pull/3330>
