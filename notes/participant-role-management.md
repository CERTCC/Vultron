---
title: Participant Role Management Design Notes
status: active
description: >
  Design decisions and implementation guidance for the VultronParticipant and
  CaseParticipant role-management API (add_role, remove_role, has_role, roles
  property). Source: IDEA-26050401.
related_specs:
  - specs/participant-role-management.yaml
relevant_packages:
  - vultron/core/models/participant.py
  - vultron/wire/as2/vocab/objects/case_participant.py
  - vultron/core/use_cases/query/action_rules.py
  - vultron/core/predicates/participants.py
  - vultron/core/behaviors/case/nodes/on_behalf_guards.py
  - vultron/core/use_cases/triggers/case/add_on_behalf_status.py
  - test/core/models/test_participant.py
---

# Participant Role Management Design Notes

## Decision Table

| Question | Decision | Rationale |
|---|---|---|
| Where do new tests go? | New `test/core/models/test_participant.py` | Mirrors source layout; keeps `test_base.py` focused on the base model contract |
| Should core code read `case_roles` directly? | No — use `roles` property | Decouples callers from storage field; allows future representation changes |
| What does the `roles` property return? | `list[CVDRole]` | Keeps callers working with domain types; `.value` extraction stays at call sites |
| Should `CaseParticipant` match the `VultronParticipant` interface? | Yes — full parity | Callers should not need to know which class they hold to manage roles |
| Should wire-layer `model_validator` role inits use `add_role()`? | Yes | Routes all role mutations through the single invariant-check point |
| Should an architecture test enforce the no-direct-mutation rule? | Yes, with ≤1 s budget | Machine-checkable enforcement; targeted scan stays fast |
| Should an architecture test enforce the no-direct-read rule (`getattr(*, "case_roles")`)? | Yes — `test_no_getattr_case_roles_read_in_core()` added in PR #1443 | Complements the mutation ratchet; enforces PRM-01-003 |

---

## Participant Lookup: Two Patterns, Chosen by Context

`actor_participant_index` is the authoritative fast path. Two lookup patterns
exist and they are not interchangeable:

- **RM state mutation** (`update_participant_rm_state`): MUST use
  `actor_participant_index → dl.read()` exclusively (CM-19-003). Never read
  inline objects from `case_participants`; they may be stale snapshots (#2233).
- **BT-level resolution** (`FindParticipantByActorIdNode`): check
  `actor_participant_index` first, then fall back to a `case_participants` scan
  for bootstrap compatibility. Fail only on index↔scan *contradictions*, never
  on a cache miss.

## RM Terminal Guard Must Run Before the Same-State Shortcut

Evaluate `RM.CLOSED` terminal rules *before* the `current == new` no-op check.
Ordering them the other way silently permits a transition out of a terminal
state whenever the target happens to equal the current state.

## Assertion Authority and On-Behalf Exceptions (PRM-06)

Participant status is self-declaratory by default (PRM-06-001, ADR-0084). Two
narrow on-behalf exceptions exist:

- **v→V** (`CS_vf.Vf`): a Case Manager or Case Owner MAY assert vendor awareness
  on behalf of a notified-but-not-joined vendor (PRM-06-003).
- **d→D** (`CS_d.D`): the same asserting actors MAY assert deployer deployment
  under externally-evidenced exceptional circumstances (PRM-06-004).
- **f→F** (`CS_vf.VF`) is always Vendor-only and cannot be asserted on behalf
  of another actor (PRM-06-005).

The **Vendor-implies-V invariant** (PRM-06-002): a participant holding
`CVDRole.VENDOR` cannot assert `CS_vf.vf` (vendor-unaware) — a vendor that
has joined a case is by definition aware of it. Enforced by
`vendor_vf_invariant_ok` in `vultron/core/predicates/participants.py`.

Implementation: `SvcAddOnBehalfStatusUseCase` in
`vultron/core/use_cases/triggers/case/add_on_behalf_status.py`; BT guards
in `vultron/core/behaviors/case/nodes/on_behalf_guards.py`.
