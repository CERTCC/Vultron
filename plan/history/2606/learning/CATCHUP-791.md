---
source: CATCHUP-791
timestamp: '2026-06-22T19:35:03.615379+00:00'
title: Catchup replay must not double-apply already-integrated entries
type: learning
---

When replaying a remote actor's JSONL catchup stream, always check
`CheckLogEntryAlreadyStored` before the guarded-commit node. Without this
guard, re-running a catchup for an actor that is already partially synced
re-inserts duplicate `CaseLedgerEntry` records, which breaks hash-chain
validation for all entries after the first duplicate.

**Promoted**: 2026-06-22 — archive only (already covered in the
catchup/replay use-case docs).
Docs PR: <https://github.com/CERTCC/Vultron/pull/1112>.
