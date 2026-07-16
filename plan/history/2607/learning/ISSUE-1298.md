---
title: OFFER_ACTOR_TO_CASE registry pattern must match inbound wire format, not outbound emit format
type: learning
timestamp: '2026-07-10T18:00:00Z'
source: ISSUE-1298
---

OFFER_ACTOR_TO_CASE was initially mapped to OfferActorToCasePattern
(Offer(CaseParticipant, Case)) — the outbound DM format that CaseActor sends to
Case Owner — instead of SuggestActorToCasePattern (Offer(Actor, Case)) — the
actual inbound format that Finder sends to CaseActor inbox.

The distinction matters: the registry pattern must match the *inbound* wire
format, not the format the handler emits outbound.

OfferActorToCasePattern is still needed in `_instances.py` as a nested-object
template for AcceptActorRecommendationPattern and
RejectActorRecommendationPattern (which wrap Offer(CaseParticipant)).

**Promoted**: 2026-07-15 — captured in notes/activitystreams-semantics.md.
Docs PR: <https://github.com/CERTCC/Vultron/pull/1458>8>8>8>8>.
