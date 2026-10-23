---
source: SYNC-902-MISMATCH-TEST-SEAM
timestamp: '2026-06-22T19:33:10.718856+00:00'
title: Mismatch assertions need dispatch-level injection, not post_actor_inbox
type: learning
---

For predecessor-mismatch coverage (#902), injecting `Announce(CaseLogEntry)`
through `post_actor_inbox` can mask mismatch behavior because nested object
persistence can make `CheckLogEntryAlreadyStored` short-circuit before hash
validation. A stable test seam is `handle_inbox_item(...)` with a typed
activity object, then normal outbox-driven replay from the CaseActor.

**Promoted**: 2026-06-22 — captured in `test/AGENTS.md` (SYNC Replication
Test Patterns section, Predecessor-Mismatch Test Seam).
Docs PR: <https://github.com/CERTCC/Vultron/pull/1112>.
