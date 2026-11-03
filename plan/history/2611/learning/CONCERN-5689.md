---
source: CONCERN-5689
timestamp: '2026-11-03T16:42:06.795153+00:00'
title: A repeat assertion is suppressed on its effect, not on a clock window
type: learning
---

Theme: theme:protocol-correctness — a repeat assertion is suppressed or admitted
on its effect, so the decision comes out the same whatever order two threads
reach it and whatever the clock says.

> **Updated 2026-11-03.** This issue was filed while #5591 was still being
> fixed, and two of its three arguments have since been answered by the fix
> that landed (PR #5659). The corrected reasoning is below; the superseded
> claims are named so nobody re-derives them. The remaining question is real
> but smaller than first written, and no longer urgent.

## What #5659 settled

A participant keeps an in-memory pending-assertion store so a near-term repeat
of an assertion whose round-trip has not come back is suppressed
(SYNC-11-001, SYNC-11-002), and it decides by time: an entry suppresses while
it is `pending` and inside a configured window, and a timeout lifts the
suppression so a lost assertion can be made again (SYNC-11-005).

This issue originally argued that deciding by time cost three things. Two are
now paid:

**"It puts a clock on a read path" — fixed.** Every lookup
(`is_suppressed`, `pending_for_subject`, `clear_activity`) now takes the
deciding instant as a required `at` keyword from the caller, which already
holds the instant of the act under decision. The lookup reads no clock and
expiry stays live on it.

**"The timeout needs an evaluator, and every placement is wrong somewhere" —
withdrawn as stated.** The original text claimed that marking an overdue entry
on the lookup "re-creates the clock read" and that no fourth placement existed.
That was wrong: marking on the lookup against a *caller-supplied* instant is
the fourth placement, and it is what shipped. The three dead ends the text
described are still dead ends — marking on a lookup that reads its own clock,
marking only on a write or an explicit sweep (which left `expire_timed_out()`
with no production caller and would have let a lone unanswered ask suppress its
own repeat forever), and sweeping per delivery on an unordered thread.

## What still stands

**The window is a second answer to a question already answered.** SYNC-11-004
forbids the CASE_MANAGER from using the store at all, because the single
authoritative writer's own idempotency check already rejects a duplicate
commit. ID-04-002 and ID-04-004 already require a state-changing handler to
check existing state and be idempotent. The store sits in front of that as an
optimization, and exists as a separate mechanism only because duplicate
detection is keyed on the activity id (ID-02-001) while a repeat of the same
ask can carry a new one.

So the question is narrower than first written, and it is about mechanism
duplication rather than reproducibility:

Should the repeat decision read the effect instead of a window? A repeat is
skipped when it is identical to the outstanding assertion, or when its effect
would be no change to the case, whichever activity id it carries. Otherwise it
is admitted, and the authoritative writer decides as it already must. If that
is the rule, SYNC-11's window and its timeout have no work left to do. If it is
not the rule, the reason is worth writing down, because two mechanisms
answering one question is what invites the next agent to ask again.

## What has to be settled before work items can be written

- Whether "no change in effect" is computable at the three decision sites —
  `triggers/_base.py` and `behaviors/embargo/nodes/terminate.py` via
  `suppressed_repeat_reason()`, and `use_cases/received/_pending_refusal.py`
  via `pending_for_subject()` — without reaching into the authoritative store
  from a participant that only holds a replica (CLP-07-013).
- Whether an effect-based decision still needs the store at all, or whether it
  collapses into the idempotency chain and SYNC-11 loses its window.
- What a repeat means to the protocol: a retry after a loss, and a participant
  genuinely asking a second time, are the same bytes with different intent. A
  rule that skips the second one silently is a liveness bug wearing
  idempotency's clothes. This is the trap in the effect-based direction and the
  reason it is a Concern rather than a Task.
- ASK-04-007's shared outstanding-ask lifecycle faces the same decision at its
  own call sites (#5649, #5650, #5651, #5652), but it now has a worked pattern
  to follow rather than an open question: the instant comes from the act being
  decided. ASK-05-001's MUST — an overdue ask is expired at the next entry into
  the tree, with no prior reaping pass — is satisfied by that pattern.

## Context

Raised by the maintainer while reviewing #5591. #5659 kept the timeout and
removed the clock read; it did not answer this question and must not be read as
having answered it. Its reviewer flagged that this issue's text had fallen
behind the code and deliberately left it alone rather than edit toward an
answer, which is why this update is a correction rather than a closure.

Governing specs: SYNC-11-001, SYNC-11-002, SYNC-11-004, SYNC-11-005,
ID-02-001, ID-04-002, ID-04-004, ASK-04-007, ASK-05-001

**Resolved**: 2026-11-03 — implementation tracked in #5720. The decision on a repeat moves to its effect at the CASE_MANAGER (EP-09-032 for same-end-time embargo proposals; ID-04-004 and CM-13-005 already cover the other suppressed repeats). The participant window stays as a traffic saver, because a replica cannot see its own assertion's effect until the round trip returns (CLP-07-013).

Docs PR: <https://github.com/CERTCC/Vultron/pull/5725>.

Spec: `specs/embargo-policy.yaml` (EP-09-032); `specs/sync-ledger-replication.yaml` (SYNC-11-001, SYNC-11-006 rationale).

Notes: `notes/protocol-asks.md`.
