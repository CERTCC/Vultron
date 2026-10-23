---
source: ISSUE-1298
timestamp: '2026-07-10T14:19:19.095905+00:00'
title: 'impl: suggest_actor_tree ADR-0026 redesign'
type: implementation
---

## Issue #1298 — redesign suggest_actor_tree.py (ADR-0026/CM-16)

Rewrote the actor-suggestion BT factories and use cases so `Offer(Actor, Case)`
routes through the CaseActor inbox per ADR-0026/CM-16 rather than directly to
the Case Owner inbox (the pre-ADR-0021 anti-pattern).

**Key changes:**

- New `MessageSemantics`: `OFFER_ACTOR_TO_CASE`, `ACCEPT_ACTOR_RECOMMENDATION`,
  `REJECT_ACTOR_RECOMMENDATION`
- New wire activities: `_OfferCaseParticipantActivity`,
  `_AcceptCaseParticipantOfferActivity`, `_RejectCaseParticipantOfferActivity`
- New factory functions: `offer_case_participant_activity`,
  `accept_case_participant_offer_activity`, `reject_case_participant_offer_activity`
- `EmitOfferCaseParticipantToOwnerNode` resolves case owner from DataLayer and
  passes `to=[owner_id]` — fixes missing `to:` field for outbox delivery
- `recommended_id` threaded through Accept/Reject nodes and adapter so wire
  messages carry the correct actor URI (not the recommendation activity URI)
- `OfferActorToCaseReceivedUseCase` extracts `recommended_id` from
  `CaseParticipant.attributed_to` (not `object_id` which has `#participant` suffix)
- Legacy pre-ADR-0026 use cases kept as drop+warn stubs for old participants
- `suggest_actor_demo.py` updated to ADR-0026 three-step protocol

**Verification:** 4435 unit tests pass (21 new); Black, flake8, mypy, pyright clean.

PR: <https://github.com/CERTCC/Vultron/pull/1320>
