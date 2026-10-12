---
title: Case State Model Notes
status: active
kind: guidance
description: >
  Rules for working with the CVD case state: where the CS rules live and the
  legacy reference model's status, which dimensions are per-participant versus
  per-case, role-gated VF/D writes, the two v→V drive paths, the d→D causal
  gate, append-only status history, the invite-path RM entry point, and why
  the compound CS enum stays.
related_specs:
  - specs/architecture.yaml (ARCH-12-002)
  - specs/case-management.yaml
  - specs/cs-behavior.yaml
  - specs/em-behavior.yaml
  - specs/received-status-handling.yaml
  - specs/rm-behavior.yaml
related_notes:
  - notes/activitystreams-semantics.md
  - notes/message-type-reference.md
  - notes/protocol-event-cascades.md
  - notes/received-status-authorization.md
  - notes/domain-validation.md
  - notes/case-joining.md
  - notes/embargo-lifecycle.md
  - notes/status-dimension-objects.md
  - notes/lifecycle-staged-types.md
relevant_packages:
  - transitions
  - vultron/bt/embargo_management
  - vultron/bt/report_management
  - vultron/core/case_states
---

# Case State Model Notes

The model itself (six dimensions, 32 states, 58 transitions) is documented in
`docs/topics/process_models/cs/` and `docs/reference/case_states/`; the
participant-agnostic versus participant-specific split in
`docs/topics/process_models/model_interactions/index.md`. This note holds the
rules for changing the code that implements it.

## Where the CS Rules Live (ADR-0060)

- **Enums**: `vultron/core/states/cs.py`. The 32-member `CS` enum makes the
  impossible combinations (`vF`, `fD`) unrepresentable; the split sub-machine
  enums are `CS_vf`, `CS_d`, `CS_pxa` (ADR-0075).
- **Invariants**: `vultron/core/states/cs_invariants.py` (CSB-17). New code
  MUST use it and MUST NOT import `vultron/core/case_states/validations.py`.
  `vultron/core/case_states/` is a reference model and the test oracle for the
  invariants, not a protocol path.
- **Cross-dimension combinations**: call `composite_state_violations()` (or,
  on the emit path, `participant_transition_violations()`), never the
  individual predicates; ratchet tests enforce this (CSB-17-001, RSH-05-020).
  After ADR-0075 `*fD*` is representable, so the check is a runtime one.
- **Transitions delegate to the dimension machines** (`VfDimension`,
  `DDimension`, `PxaDimension`); only the two ephemeral rules are compound-level
  logic. Do not re-derive monotonicity at the compound level, or the two drift.
- **History validity is causal replay.** Use `is_valid_cs_history_prefix()` for
  live cases; `is_valid_cs_history()` requires all six events.
- **Ephemeral states**: the six `vP` states must next take `V`, and the six
  `pX` states must next take `P` (`required_next_cs_events()`, CSB-17-003).

The legacy module stays until two importers migrate: `cs.py` still uses
`case_states.validations.ensure_valid_state`, and
`vultron/core/use_cases/query/action_rules.py` (the `actors_get_action_rules`
endpoint) still uses `case_states.patterns.potential_actions`.

## Participant-Specific vs. Participant-Agnostic State

Mixing these up produces wrong case state.

| Dimension | Scope | Where tracked |
|---|---|---|
| RM | Per participant | `ParticipantStatus.rm` |
| VF (vendor path) | Per participant, VENDOR only | `ParticipantStatus.vf` |
| D (deployer path) | Per participant, DEPLOYER only | `ParticipantStatus.d` |
| EM | Per case | Derived from the embargo register (ADR-0122) |
| PXA | Per case | `CaseStatus.pxa_state` |

- An RM or VF/D transition updates the **sending actor's** `CaseParticipant`;
  a PXA transition updates the shared `CaseStatus`.
- EM is never set on a status: it is derived from the case's embargo register
  and stamped onto `current_status`; `append_case_status(em_state=...)` is
  refused (ADR-0122).

### Role-gated VF and D writes

`ParticipantStatus` auto-seeds `vf` for a VENDOR and `d` for a DEPLOYER, but
does **not** raise on a stray dimension. Role authorization is enforced at the
guard layer against the participant's authoritative `case_roles`:

- **Trigger / emit path** (fail-closed): `ValidateTriggerTransitionsNode` and
  the role guards on the add-participant-status trigger tree (BTND-10-001,
  CSB-15-001/002).
- **Receive path** (partial accept, offending dimension carried forward):
  `vultron/core/behaviors/status/nodes/_adjudication.py` (RSH-05-001/002).

Do not move the check into the model. The extractor builds a
`ParticipantStatus` from the sender's untrusted self-reported role, so a
construction-time raise would turn the receive path's partial accept into
whole-object rejection (ADR-0075; `notes/domain-validation.md`).

### `v→V` has two authorized drive paths

The vendor may self-report `v→V`, and the party that delivered the report to
the vendor (or invited it) may assert `v→V` on its behalf, because awareness
means having received the information. `f→F` and `d→D` are self-reports only.
The on-behalf path is the add-on-behalf-status trigger, which permits only
`v→V` for a vendor (`vultron/core/use_cases/triggers/request_bodies.py`). The
dispute edge cases are an open question in protocol spec §12.4.1
(`docs/reference/vultron-spec/_oq-v-to-V.md`).

### DEPLOYER `d→D` needs some vendor at VF (CSB-15-004)

A DEPLOYER may advance `d→D` only when at least one VENDOR in the case is at
`CS_vf.VF`. `CheckSomeVendorAtVFNode` enforces it on both the direct and
on-behalf trigger trees. The gate is deliberately case-wide, not per vendor
(Concern #2665).

## Status Lists Are Append-Only History

- `VulnerabilityCase.case_status` and `CaseParticipant.participant_status` are
  append-only lists. The current entry is the one with the latest `updated`
  timestamp; items may arrive out of order. Use `current_status`, never list
  indexing.
- A status update carrying a future timestamp is an error.
- The CASE_MANAGER's trusted timestamp for a state-changing event is its
  `CaseLedgerEntry` commit, not an edit to the object's own timestamp, which
  would break the append-only history (CM-02-009).

## Invite-Path Participants Enter at RM.RECEIVED

An invitee's participant record is created inert at `RM.RECEIVED` when the
CASE_MANAGER sends the stub Invite (CM-11-006), and the stub `Accept` moves no
RM state (CM-11-001). Accepting a stub agrees to join and to the embargo; it is
not a judgement of a case the actor has not seen, so recording `RM.VALID` or
`RM.ACCEPTED` there is wrong. RM then advances only on the participant's own
reply to the full-case Invite and its `Join`/`Ignore`. This applies to
post-initialization invitees, not the participants created during case
initialization (CM-12, CM-13). Full flow: [case-joining.md](case-joining.md).

## Case-Level Action Rules Aggregate Across Participants

A case-level rule (CASE_MANAGER or case owner perspective) MUST aggregate over
all relevant participants: for example, an `EMBARGO_END` trigger MUST NOT fire
because one vendor reached `FIX_READY` while others have not. Participant-level
rules evaluate one participant's state.

## CS Representation: Keep the Compound Enum

Do not introduce a `CaseState(BaseModel)`. `CS` is already
`CompoundState(CS_vf, CS_d, CS_pxa)`; core code consumes the split enums
(ADR-0075), the monolithic enum serves the legacy `vultron/bt/` simulator, and
the ADR-0036 dimension objects already give a structured per-dimension view. A
second structure would duplicate that surface. Likewise, explicit transition
constructors stay rejected until the ADR-0033 reopen bar is met (see
[lifecycle-staged-types.md](lifecycle-staged-types.md)).

## A Replica Applies the Ledger, It Does Not Re-Derive (CM-23-016)

A participant's replica is `case(t0)` plus the ledger entries that followed.
It applies the transitions the ledger records and never re-derives one by
walking the RM table: the table governs what the CASE_MANAGER may commit, not
what a replica may infer.
