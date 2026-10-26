---
title: "BT-14-001's FAILURE for a held-back ledger send, combined with CLP-07-015, lets one broken old entry stop every later commit in a case"
type: learning
timestamp: "2026-10-26T22:30:00Z"
source: ISSUE-5120
signal: spec-ambiguity
---

**Trigger.** You are deciding what a CASE_MANAGER send node returns when
SYNC-03-009 holds back an entry it cannot verify, or you are reading
`SendLogEntryToEachNode` (`vultron/core/behaviors/sync/nodes/fanout.py`), which
backfills admitted, paused peers before it sends a new entry.

**Claim.** BT-14-001 says a fan-out MUST return FAILURE when "outbox enqueueing
fails"; it does not say whether a deliberate hold-back is such a failure. Read
as one, it meets CLP-07-015, which says an act commits whole. A held-back
fan-out backfill then refuses the commit. Because the peer keeps its pause, it
also refuses every later commit in the case until the entry is repaired. The
SYNC-03-009 rationale expects later fan-outs to go on ("the replica sends one
`Reject` per later fan-out"). `learn` must settle whether a hold-back of an
*old* entry, during a fan-out of a *new* one, fails the fan-out (fail-stop) or
only stalls that peer (skip it, ERROR, SUCCESS). The answer belongs in
SYNC-03-009 or BT-14-001.

**Evidence.** PR #5248 (ISSUE-5120) builds the fail-stop reading, which is AC-3
as written, and is held as a draft on this question. See its "Held" section and
the pre-push finding `phase8-one-peer-holdback-stalls-fanout-0`.

**How to apply.** Until it is settled, follow whatever the PR #5248 decision
records. Do not add another send path that returns FAILURE on a hold-back inside
an act without checking what that does to the act.
