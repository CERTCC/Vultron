---
source: ISSUE-1325
timestamp: '2026-07-13T20:28:42.996903+00:00'
title: ADR-0026 AC-6 and AC-7 duplicate recommendation handling
type: implementation
---

## Issue #1325 — impl: ADR-0026 duplicate recommendation handling — AC-6 (pending decision) and AC-7 (actor already participant / invite in-flight)

Implemented duplicate detection for the CaseActor-routed suggest-actor workflow:

- AC-6: second Offer(Actor, Case) while first Offer(CaseParticipant) is pending → Note DM to Case Owner, no second Offer
- AC-7a: Invite in-flight → auto-accept to second recommender, no duplicate Invite
- AC-7b: actor already participant → auto-accept to second recommender

Key design decisions:

- ProtocolPair.request_found + is_pending() disambiguates "pending" from "fresh" pairs
- Local correlation markers use disposition="rejected" to bypass canonical-payload validation for non-canonical event types (offer_case_participant, invite_actor_to_case)
- Ledger commit before outbox write to prevent orphaned outbox items
- Fail-fast on missing Case Owner (ADR-0032)

PR: <https://github.com/CERTCC/Vultron/pull/1398>
