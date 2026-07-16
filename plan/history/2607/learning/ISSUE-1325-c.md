---
title: "Commit ledger entry before writing to outbox"
type: learning
timestamp: 2026-07-13T00:00:00Z
source: ISSUE-1325-c
---

When a BT node both commits a ledger correlation marker and records an outbox
item, the ledger commit must happen first.

If the outbox write happens first and the ledger commit fails, the outbox item
is orphaned — an activity queued for delivery with no corresponding ledger
entry.  On the next invocation, the duplicate-detection guard finds no pending
entry and takes the fresh path, triggering a duplicate offer/invite.

Correct ordering:

1. Build activity via factory (creates the object in the data layer)
2. Commit ledger correlation marker (fails fast if something is wrong)
3. Record outbox item (only reached if the ledger commit succeeded)

**Promoted**: 2026-07-15 — captured in notes/bt-integration.md.
Docs PR: <https://github.com/CERTCC/Vultron/pull/1458>8>8>8>8>.
