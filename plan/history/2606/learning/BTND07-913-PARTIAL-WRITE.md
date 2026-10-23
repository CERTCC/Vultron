---
source: BTND07-913-PARTIAL-WRITE
timestamp: '2026-06-22T19:34:54.720387+00:00'
title: memory=False Sequence partial-write semantics in BT
type: learning
---

A `Sequence(memory=False)` node re-runs ALL children on each tick, even if
a previous tick made it through child N. This means idempotency must be
explicitly guaranteed at every leaf that writes state. If any leaf is not
idempotent, use `Sequence(memory=True)` instead, and document why. For
blackboard writes in particular, always clean up after a Sequence returns
SUCCESS or FAILURE to avoid stale keys on the next tick.

**Promoted**: 2026-06-22 — captured in `notes/bt-integration.md`
(`memory=False` Partial-Write Semantics section).
Docs PR: <https://github.com/CERTCC/Vultron/pull/1112>.
