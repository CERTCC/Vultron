---
source: CONCERN-5793
timestamp: '2026-11-11T20:20:44.665299+00:00'
title: A full-case Invite with no replica waits at the inbox
type: learning
---

Theme: theme:protocol-correctness — settles whether the full-case Invite reaches a receiver that holds no replica, so its path declaration and the inbox's defer set agree.

## Summary
`InviteActorToFullCaseReceivedBT` declares the no-case path, because CM-11-032 is a MUST about a receiver that holds no replica: "A receiver MUST refuse a full-case Invite whose sender is not the CASE_MANAGER on its replica or, with no replica, its stub-Invite trust anchor (PCR-03-004)." Three tests in `test/core/use_cases/received/actor/test_full_case_invite.py` drive exactly that receiver.

HP-01-041, also a MUST, says a tree declares the no-case path **only** for a message type the inbox delivers without its case being known. `MessageSemantics.INVITE_ACTOR_TO_FULL_CASE` is in neither `CASE_BOOTSTRAP_SEMANTICS` nor `CASE_PRECEDING_SEMANTICS` (`vultron/core/models/events/case_context.py`), so `is_deferral_exempt` is false for it and the inbox's defer check holds the delivery until the case is known.

## Surface Symptom vs. Underlying Problem
The surface reading is a stale declaration: drop the no-case path and the two MUSTs agree. That would make CM-11-032's second clause and the three tests that cover it dead, and the tests would keep passing while asserting a refusal that comes from the path stage rather than from the trust anchor — a vacuous assertion of the kind `notes/testing-pitfalls.md` warns about.

The underlying problem is that two requirements disagree about when a full-case Invite can arrive. CM-11-010 queues it after the Announce, so in the ordinary flow the replica exists. CM-11-032 nonetheless specifies the no-replica receiver, and the stub Invite's trust anchor exists to serve it. Either the semantic belongs in `CASE_PRECEDING_SEMANTICS` (it precedes its case by design, like the stub Invite), or CM-11-032's second clause should say that a receiver with no replica defers rather than judges, and the anchor path belongs to the stub Invite and `Announce(VulnerabilityCase)` alone.

What is correct and should stay: the trust anchor itself (PCR-03-004), and the declaration as it stands, which preserves today's behaviour either way.

## Category
Specification consistency.

## Severity
Low. Nothing misbehaves today: the declaration admits the no-replica receiver, and the inbox would hold such a delivery anyway, so the two readings differ only in which door turns it away.

## Evidence
- CM-11-032 (MUST) names the no-replica receiver.
- HP-01-041 (MUST) restricts the no-case declaration to types the inbox does not defer.
- `CASE_PRECEDING_SEMANTICS` holds `INVITE_ACTOR_TO_CASE` only.
- `test/core/behaviors/test_declared_received_paths.py` pins the declaration, so whichever way this is settled, the pin records it.

## Impact if Ignored
A later reader takes the declaration as a counter-example to HP-01-041 and copies it, and the three tests keep passing for a reason no requirement states.

## Suggested Action
Decide which requirement moves. If the semantic is deferral-exempt, add it to `CASE_PRECEDING_SEMANTICS` with the reason and keep the declaration. If it is not, amend CM-11-032 to say a no-replica receiver defers, drop the no-case path from the declaration, and rewrite the three tests to cover the anchor through the stub Invite and `Announce(VulnerabilityCase)` instead.

**Resolved**: 2026-11-11 — implementation tracked in #6309. The full-case Invite is case-scoped: a receiver with no replica holds it at the inbox until the Announce's replay, and never judges it without the replica.
Docs PR: https://github.com/CERTCC/Vultron/pull/6308.
Spec: `specs/case-management.yaml`.
Notes: `notes/case-joining.md`.
