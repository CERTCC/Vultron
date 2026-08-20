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

## Amendment — `strict=True` for `target_` (CONCERN-2322)

CONCERN-2322 surfaced a second structural gap: even with Option 1 chosen,
`ActivityPattern._match_activity_field` always treats the `target_` field as
permissive (`strict=False`), meaning a bare URI string in `target` would match
any typed target constraint. For the deprecated `Offer(VulnerabilityCase,
target=CaseParticipant)` format this meant registry ordering was the **sole**
protection against misrouting when `_rehydrate_fields` had not yet resolved
the target.

The amendment decision (CONCERN-2322) is:

- **`strict=True` on `ActivityPattern` MUST also gate `target_` matching**:
  when `strict=True`, a bare string in the `target` field must NOT match a
  typed target constraint. This is implemented by passing `self.strict` to the
  `target_` field pair in `_match_activity_field` instead of the hardcoded
  `False`.
- **`OFFER_CASE_MANAGER_ROLE` is removed** (not merely deprecated): the
  backward-compat wire format was never emitted by any supported actor
  implementation; retaining it as a fallback-only registry entry was a source
  of registry-ordering fragility. Removed by CONCERN-2322.
- **`ACCEPT_CASE_PARTICIPANT_ROLE` and `REJECT_CASE_PARTICIPANT_ROLE`** are
  added to complete the three-way role-offer flow for the canonical wire format.

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

- `SE-08-001` through `SE-08-002` mandate registry ordering and required target
  field for any pattern that discriminates by target.
- `SE-08-003` records the SHOULD preference for dedicated object types over
  target-field discrimination.
- `SE-08-004` mandates `strict=True` on patterns that use `target_` as the
  sole discriminator (amended by CONCERN-2322).
- `SE-08-005` records the removal of the `OFFER_CASE_MANAGER_ROLE` backward-compat
  format (CONCERN-2322).
- Implementation issues: tracked as GitHub Task issues blocked by CONCERN-2322.

Generated spec requirements: `specs/semantic-extraction.yaml` SE-08-001,
SE-08-002, SE-08-003, SE-08-004, SE-08-005.
