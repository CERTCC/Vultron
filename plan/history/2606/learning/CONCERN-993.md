---
source: CONCERN-993
timestamp: '2026-06-16T15:42:17.193330+00:00'
title: Case ledger genesis hash provides no case-specific origin binding
type: learning
---

## Summary

`GENESIS_HASH = "0" * 64` is a hardcoded constant with no case-specific entropy.
Every case ledger starts identically, providing no cryptographic origin-binding
and enabling several integrity and availability weaknesses.

## Category

Security / Integrity

## Severity

Medium (research prototype risk; would be High for production deployments)

## Evidence

`vultron/core/models/case_ledger.py:72`:

```python
GENESIS_HASH: str = "0" * 64
```

This constant is used as the `prev_log_hash` default on the first entry of **every**
case ledger across all cases and all deployments. `tail_hash == GENESIS_HASH` is also
used as the sentinel for an empty/new ledger in `CaseLedger.tail_hash`,
`sync_helpers.py`, and the sync replay paths.

## Impact if Ignored

1. **No cryptographic origin-binding**: There is no cryptographic proof of who started
   a ledger, when, or for which specific case. Trust in the chain's starting point is
   entirely delegated to DataLayer `case_id` field integrity — a compromised DataLayer
   can silently substitute entries.
2. **Truncated ledger indistinguishable from new ledger**: A ledger with all entries
   stripped by an attacker with DataLayer access is indistinguishable from a
   legitimately new empty ledger (`tail_hash == GENESIS_HASH` in both cases). Without
   an out-of-band record of the expected chain start, silent truncation cannot be
   detected.
3. **Sync DoS amplification via well-known constant**: `from_hash=GENESIS_HASH` in
   `RejectSync` / backfill requests triggers a full ledger retransmission. Because the
   constant is universally known and applies to every case, an attacker can force full
   retransmission of any case ledger without needing any case-specific knowledge.
4. **No anchoring to case lifecycle**: The ledger start has no cryptographic tie to case
   creation metadata (creator, timestamp, actor IDs), so ledger provenance cannot be
   independently verified by a third party or an auditor.

## Resolution

Per-case genesis hash derived as
`SHA-256(case_id + "|" + created_at.isoformat() + "|" + case_actor_id)`.
Non-spoofability relies on `case_id` being a UUIDv4 (122 bits entropy).
No extra salt needed. Global `GENESIS_HASH` constant to be removed entirely.

**Resolved**: 2026-06-16 — implementation tracked in #995.
Docs PR: [#994](https://github.com/CERTCC/Vultron/pull/994).
Spec: `specs/case-ledger-processing.yaml` (CLP-08-001 through CLP-08-006).
