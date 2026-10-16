---
source: CONCERN-4821
timestamp: '2026-10-16T20:21:05.974743+00:00'
title: Occasions that share an entry, wire form and addressee have no distinguisher
  kind MSM-08-002 allows
type: learning
---

## Summary

Two pairs of occasions on one `SEMANTIC_REGISTRY` entry each now show the same row values in the occasion lookup table except the `when` text:

- `suggest-actor-to-case` and `request-invite-actor-to-case` (`OFFER_ACTOR_TO_CASE`): both `Offer(Actor)[target=VulnerabilityCase]` to the CASE_MANAGER, no distinguisher. The CASE_MANAGER tells them apart by whether the sender holds `CVDRole.CASE_OWNER` on the case.
- `announce-embargo` and `announce-embargo-termination` (`ANNOUNCE_EMBARGO_EVENT_TO_CASE`): both `Announce(Event)[context=VulnerabilityCase]` from the CASE_MANAGER to a participant, no distinguisher. The receiver tells them apart by the embargo register status of the named embargo (terminated or in force).

MSM-08-002 allows a distinguisher to be only a field value or a state context (a state machine and its states). Neither the sender's CVD role nor the register status of the object is either kind. So the lookup table's distinguisher column shows "—" for both rows of each pair, and only the prose separates them. #4578 asked for a distinguisher "if the wire form alone does not separate them"; #4818 shipped without one because MSM-08-002 has no kind that fits, and states the separator in each occasion's `notes`.

Why it matters: a reader who receives one of these activities cannot use the lookup table to find which occasion it is, which is the table's job for every other multi-occasion entry with a distinguisher.

## Options

1. Add a distinguisher kind for the sender's CVD role on the case and one for the register status of the named embargo, amending MSM-08-002 (changes what a MUST obliges, so it needs approval), and declare them on the two new occasions.
2. Keep MSM-08-002 as it is and state in MSM-08 that occasions on one entry with the same addressee may share a wire form when the `when` and `notes` name the separator; render the `notes` separator in the lookup table.
3. Leave as is.

Recommendation: option 1 for the sender role, because the role decides the CASE_MANAGER's answer (CM-17-007 versus CM-16-003); decide the register-status case with it.

## Acceptance Criteria

- [ ] AC-1: A recorded decision on how occasions that share an entry, a wire form and an addressee are told apart.
- [ ] AC-2: The two pairs above follow the decision, and `msm-occasions --check` passes.

Governing specs: MSM-08-002, MSM-08-004, MSM-08-007

Where: vultron/semantic_registry/_occasion.py, specs/message-semantics-mapping.yaml MSM-08-002

**Resolved**: 2026-10-16 — implementation tracked in #4852.

Docs PR: <https://github.com/CERTCC/Vultron/pull/4849>.

Spec: `specs/message-semantics-mapping.yaml` (MSM-08-002 amended to add a sender-standing distinguisher; MSM-08-011 added).

Notes: `notes/message-occasion-table.md`.

Finding: the embargo pair already fits MSM-08-002 as a state context on `EmbargoRegisterStatus`; only the actor pair needed a new kind.
