---
source: CONCERN-1674
timestamp: '2026-07-27T19:06:07.129461+00:00'
title: Wire ambiguity between OFFER_CASE_OWNERSHIP_TRANSFER and OFFER_CASE_MANAGER_ROLE
type: learning
---

## Summary

Both `OFFER_CASE_OWNERSHIP_TRANSFER` and `OFFER_CASE_MANAGER_ROLE` serialize as
`Offer(VulnerabilityCase)` on the wire. They are disambiguated only by the presence
or absence of `target=CaseParticipant`, plus `SEMANTIC_REGISTRY` dispatch ordering.
A sender that omits the target field by mistake would cause the wrong handler to fire
silently.

## Category

Protocol correctness / wire encoding

## Severity

Medium — latent correctness risk currently papered over by registry ordering.

## Evidence

`vultron/wire/as2/extractor/_instances.py` — `OfferCaseOwnershipTransferActivityPattern`
(`activity_=OFFER, object_=VULNERABILITY_CASE`, no target) vs
`OfferCaseManagerRolePattern` (`activity_=OFFER, object_=VULNERABILITY_CASE,
target_=CASE_PARTICIPANT`). `vultron/semantic_registry/actor.py` — ordering dependency
between the two entries.

## Impact if Ignored

A minimally-conformant or buggy sender omitting the target field would have its
case-manager-role offer silently dispatched as an ownership-transfer offer (or vice
versa) with no error surfaced.

## Resolution (2026-07-27)

Two interim protections documented and spec-encoded:

1. Registry ordering guard (`_validate_registry_order()`) — SE-07-001
2. Required `target` field on `_OfferCaseManagerRoleActivity` — SE-07-002

Structural fix tracked in #1726: introduce `as_CaseParticipantRole` wire object type
and `OFFER_CASE_PARTICIPANT_ROLE` semantic with
`Offer(CaseParticipantRole, target=Actor, context=VulnerabilityCase)` wire shape,
replacing the current `Offer(VulnerabilityCase, target=CaseParticipant)` format.

ADR-0039 records the evaluated alternatives and decision rationale.
SE-07-003 records the SHOULD preference for dedicated object types.

**Docs PR**: <https://github.com/CERTCC/Vultron/pull/1727>
**Spec**: `specs/semantic-extraction.yaml` SE-07-001, SE-07-002, SE-07-003.
**Notes**: `notes/activitystreams-state-update.md` § "Target-Field Discriminators".
