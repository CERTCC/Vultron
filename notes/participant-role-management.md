---
title: Participant Role Management Design Notes
status: active
kind: guidance
description: >
  Design decisions and implementation guidance for the CaseParticipant
  role-management API (roles property, add_role/remove_role), participant
  lookup, the RM terminal-guard ordering, on-behalf assertion authority
  (PRM-06), and the retired Finder role.
related_specs:
  - specs/participant-role-management.yaml
  - specs/case-management.yaml
related_notes:
  - notes/case-joining.md
  - notes/demo-ci-diagnostics.md
relevant_packages:
  - vultron/core/models/case_participant.py
  - vultron/wire/as2/vocab/objects/case_participant.py
  - vultron/core/use_cases/query/action_rules.py
  - vultron/core/predicates/participants.py
  - vultron/core/behaviors/case/nodes/on_behalf_guards.py
  - vultron/core/use_cases/triggers/case/add_on_behalf_status.py
  - test/core/models/test_participant.py
---

# Participant Role Management Design Notes

## Read and Mutate Roles Through the API (PRM-01)

Core code reads roles via the `roles` property (`list[CVDRole]`) and mutates
them only via `add_role()` / `remove_role()`, including in model validators, so
every mutation passes the one invariant check and callers stay decoupled from
the `case_roles` storage field. `test/architecture/test_participant_case_roles.py`
fails on a direct `case_roles` read or mutation in core.

## Participant Lookup: Two Patterns, Chosen by Context

`actor_participant_index` is the authoritative fast path. Two lookup patterns
exist and they are not interchangeable:

- **RM state mutation** (`update_participant_rm_state`): MUST use
  `actor_participant_index → dl.read()` exclusively (CM-19-003). Never read
  inline objects from `case_participants`; they may be stale snapshots.
- **BT-level resolution** (`FindParticipantByActorIdNode`): check
  `actor_participant_index` first, then fall back to a `case_participants` scan
  for bootstrap compatibility. Fail only on index↔scan *contradictions*, never
  on a cache miss.

## RM Terminal Guard Must Run Before the Same-State Shortcut

Evaluate `RM.CLOSED` terminal rules *before* the `current == new` no-op check.
Ordering them the other way silently permits a transition out of a terminal
state whenever the target happens to equal the current state.

## Assertion Authority and On-Behalf Exceptions (PRM-06)

Participant status is self-declaratory by default (PRM-06-001, ADR-0121). Two
narrow on-behalf exceptions exist:

- **v→V** (`CS_vf.Vf`): a Case Manager or Case Owner MAY assert vendor awareness
  on behalf of a vendor participant whose notification is evidenced — typically
  an inert invitee that has not yet replied to its stub Invite (PRM-06-003).
- **d→D** (`CS_d.D`): the same asserting actors MAY assert deployer deployment
  under externally-evidenced exceptional circumstances (PRM-06-004). The
  RM↔D entailment still applies, so it succeeds only for a deployer whose RM
  state is consistent with deployment.
- **f→F** (`CS_vf.VF`) is always Vendor-only and cannot be asserted on behalf
  of another actor (PRM-06-005).

The two on-behalf exceptions target an **existing** participant only. An
on-behalf assertion for an actor that is not a participant is refused before
any write and never creates one (PRM-06-006, ADR-0121): a status update is
never a way into a case — joining is the Invite flow
([case-joining.md](case-joining.md), ADR-0114).
`CheckOnBehalfTargetIsParticipantNode` enforces this as the second guard of the
on-behalf tree, ahead of the only write: it refuses, naming the target, when
the target is not in `actor_participant_index` or lacks the asserted
dimension's role (`VENDOR` for `v→V`, `DEPLOYER` for `d→D`). The tree has no
node that creates or attaches a participant.

The **Vendor-implies-V invariant** (PRM-06-002): a participant holding
`CVDRole.VENDOR` cannot assert `CS_vf.vf` (vendor-unaware) — a vendor that
has joined a case is by definition aware of it. Enforced by
`vendor_vf_invariant_ok` in `vultron/core/predicates/participants.py`.

Implementation: `SvcAddOnBehalfStatusUseCase` in
`vultron/core/use_cases/triggers/case/add_on_behalf_status.py`; BT guards
in `vultron/core/behaviors/case/nodes/on_behalf_guards.py`.

## The Finder Role Is Retired (ADR-0078)

No protocol state machine treats a Finder differently from a Reporter, so an
actor that finds a vulnerability and reports it holds `CVDRole.REPORTER`. Who
discovered it is metadata: record it in the report content or case notes.

`CVDRole.FINDER` and the `FinderParticipant` / `FinderReporterParticipant`
subclasses are gone (#2677). Every boundary role parse goes through
`parse_role()` in `vultron/enums/roles.py`, which refuses the retired wire
value `"finder"` (any case) with the ADR-0078 reason listed in
`RETIRED_ROLE_VALUES`. It is refused, never aliased to `reporter`, so stored
data or a peer still carrying it fails validation rather than being silently
rewritten.
