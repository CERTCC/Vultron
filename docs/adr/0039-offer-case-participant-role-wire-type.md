---
status: accepted
date: 2026-07-27
---

# Resolve Wire Ambiguity Between OFFER\_CASE\_MANAGER\_ROLE and OFFER\_CASE\_OWNERSHIP\_TRANSFER via Dedicated Object Type

## Context and Problem Statement

`OFFER_CASE_MANAGER_ROLE` and `OFFER_CASE_OWNERSHIP_TRANSFER` both serialize as
`Offer(VulnerabilityCase)` on the wire. They are currently disambiguated only by
the presence of `target=CaseParticipant` in the case-manager-role offer and its
absence in the ownership-transfer offer.

A minimally-conformant or buggy sender that omits the `target` field would have
its case-manager-role offer silently dispatched as an ownership-transfer offer
(or vice versa) with no error surfaced. The `SEMANTIC_REGISTRY` ordering guard
(`_validate_registry_order()`) prevents misrouting within a single implementation
but does not protect against malformed inbound activities from remote peers.

Issue: CONCERN-1674.

## Decision Drivers

- Wire shapes should be self-describing; disambiguation must not depend on
  registry ordering alone.
- The `target` field as a discriminator is semantically odd: the conceptual
  target of a role offer is the Actor receiving the role, not the CaseParticipant
  wrapper record.
- A general-purpose role-offer mechanism (offering any `CVDRole` to any Actor
  in a Case context) is more expressive than a CASE_MANAGER-specific flow.
- Backward compatibility: the existing `OFFER_CASE_MANAGER_ROLE` wire format
  must be deprecated in a traceable way.

## Considered Options

1. **New `as_CaseParticipantRole` object type** — introduce a dedicated wire
   object carrying a `CVDRole` value; wire shape becomes
   `Offer(CaseParticipantRole, target=Actor, context=VulnerabilityCase)`.
2. **Keep `Offer(VulnerabilityCase)`; add `strict=True` to the pattern** —
   enforce the target discriminator at the pattern layer without a type change.
3. **Spec-and-notes documentation only** — record the ordering requirement and
   the target-as-discriminator rationale; no wire format change.

## Decision Outcome

Chosen option: **Option 1 — new `as_CaseParticipantRole` object type**, because:

- It eliminates the structural ambiguity; the wire shape is self-describing
  regardless of registry ordering or sender compliance.
- A general `Offer(CaseParticipantRole, target=Actor, context=VulnerabilityCase)`
  is more semantically correct than targeting a CaseParticipant wrapper, and
  generalises naturally to offering any `CVDRole` (VENDOR, COORDINATOR, etc.)
  rather than only CASE_MANAGER.
- Options 2 and 3 leave the latent misrouting risk in place for external senders.

### Consequences

- Good, because wire shapes for role delegation and ownership transfer are
  structurally distinct and self-describing.
- Good, because the general role-offer mechanism supports future role delegation
  flows beyond CASE_MANAGER.
- Good, because `target=Actor` is semantically correct; the target of a role
  offer is the Actor receiving the role, not the CaseParticipant wrapper.
- Bad, because this is a breaking wire format change for `OFFER_CASE_MANAGER_ROLE`;
  existing devlogs and interop partners must be migrated.
- Bad, because it requires a new `VultronObjectType` enum value, new vocab class,
  updated factory, updated pattern, and new use case + BT handler.

## Validation

- Import-time `_validate_registry_order()` guard confirms no less-specific
  `Offer(VulnerabilityCase)` pattern precedes the new `Offer(CaseParticipantRole)`
  pattern in `SEMANTIC_REGISTRY`.
- Unit tests in `test/test_semantic_activity_patterns.py` assert correct dispatch.
- Demo scenario emits the new wire format and the invariant harness validates it.

## More Information

- Interim protection while the migration is in flight: `SE-08-001` through
  `SE-08-002` mandate registry ordering and required target field until the
  wire type migration is complete.
- `SE-08-003` records the SHOULD preference for dedicated object types over
  target-field discrimination.
- Implementation issue: tracked as a GitHub Task issue blocked by CONCERN-1674.

Generated spec requirements: `specs/semantic-extraction.yaml` SE-08-001,
SE-08-002, SE-08-003.
