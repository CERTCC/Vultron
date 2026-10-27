---
title: "BT-14-001 does not say a fan-out's held-back catch-up is skipped, not failed, which #5120 decided so one broken old entry cannot stop every later commit"
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
fan-out catch-up to a let-back-in, paused peer then refuses the commit. Because
the peer keeps its pause, it also refuses every later commit in the case. The
user decided on #5120 that the fan-out skips that peer, sends the new entry to
everyone else and succeeds, while every other hold-back still fails its node.
`learn` should write that exception into SYNC-03-009 or BT-14-001, where it
now lives only in code, a note and the issue. The join backfill and the
admission backfill node recur the same way and still fail, as decided: while a
broken old entry exists, every later Accept of an Invite to the case is refused
whole, so no one new can join. The spec text should say so too.

**Evidence.** PR #5248 (ISSUE-5120): the decision in its "AC-3 amended" section
and on #5120 (comment 6443457746); the pre-push finding
`phase8-one-peer-holdback-stalls-fanout-0`.

**How to apply.** Before a new send path returns FAILURE on a hold-back inside
an act, check whether the same hold-back recurs on every later act, as a kept
pause makes it recur. If it does, skip the stalled peer instead.
