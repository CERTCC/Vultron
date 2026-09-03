---
status: accepted-provisional
date: 2026-08-26
deciders: Allen D. Householder
consulted: []
informed: []
---

# Split Per-Participant VFD Tracking into Separate Vendor-Path and Deployer-Path Sub-Machines

## Context and Problem Statement

The `CS_vfd` sub-machine couples vendor-awareness (`v→V`), fix-readiness
(`f→F`), and fix-deployment (`d→D`) transitions into a single 4-state chain
(`vfd → Vfd → VFd → VFD`) for all participants regardless of their CVD role.
This creates a semantic mismatch: `V` and `F` transitions are only meaningful for
VENDOR participants (who develop and supply fixes), while `D` transitions are only
meaningful for DEPLOYER participants (who apply fixes in their own environments).

For a DEPLOYER-only participant the `vfd` field could never advance past `vfd`
through normal V/F transitions, requiring a workaround: the `CS_vfd.vfd` null
element doubled as both "initial state" and "not applicable". This workaround
was addressed at the guard layer (CSB-15-004 causal gate, PR #2593) but left the
data-model ambiguity in place. See CONCERN-2595 for the full context.

## Decision Drivers

- The `CS_vfd.vfd` "null element" was overloaded: it meant both "vendor unaware,
  fix not ready, not deployed" (initial state for VENDORs) and "not applicable"
  (for DEPLOYER-only and non-VFD participants).
- BT guards compensated for data-model ambiguity rather than preventing
  structurally impossible states.
- A participant's permitted transitions should be derivable from its role without
  runtime guards.

## Considered Options

- **Direction 1** — keep `CS_vfd` monolithic; enforce via guards only
- **Direction 2** — add a role predicate to `ParticipantStatus` to gate VFD
  sub-field access at runtime
- **Direction 3a** — split at the per-participant level into two nullable fields:
  `vf: VfDimension | None` (vendor path, 3 states) and `d: DDimension | None`
  (deployer path, 2 states); structural `None` for inapplicable roles
- **Direction 3b** — split `CS_vfd` into a compound type with optional V/F and
  optional D parts at the case-aggregate level

## Decision Outcome

Chosen option: **Direction 3a** — split at the per-participant level with two
nullable fields on `ParticipantStatus`.

Rationale: the split retires the overloaded `CS_vfd.vfd` null element, which
had meant both "initial state" and "not applicable". A DEPLOYER-only
participant's vendor path is now the absent `vf` field (`None`) rather than a
value that has to be interpreted by role; likewise a VENDOR-only participant's
deployer path is the absent `d` field. Direction 1 leaves the ambiguity intact.
Direction 2 adds runtime
predicates without removing the ambiguous field. Direction 3b changes the
case-aggregate CS model, which is orthogonal and unnecessary — the compound
`CS_vfd` (4 states) at the case level is unchanged.

The implementation is sequenced as three additive+removable tasks:

- #2662 — Add `CS_vf`, `CS_d`, `VfDimension`, `DDimension` (additive)
- #2663 — Migrate `ParticipantStatus.vfd` to `vf`/`d` fields
- #2664 — Remove `CS_vfd`, `VfdDimension`, and retired guard nodes

Status is `accepted-provisional` because implementation is not yet complete;
the spec changes and dimension-split direction are validated, but the final
shape may be refined during #2663.

### Consequences

- Good, because the two dimensions are independently nullable: a participant's
  vendor path and deployer path are separate fields rather than positions in a
  single overloaded chain, so each can be present or absent on its own.
- Good, because `ParticipantStatus` construction *auto-seeds* the applicable
  dimension for a VENDOR or DEPLOYER role
  (`_enforce_role_dimension_invariant`), so a role-consistent object never has
  to be assembled by hand.
- Neutral, because the split does **not** by itself make an inapplicable
  dimension unrepresentable: the model seeds but does not reject a stray `vf`
  on a non-VENDOR (or `d` on a non-DEPLOYER). Role *authorization* stays at the
  guard layer, enforced against the acting participant's authoritative
  `case_roles` — see [Validation](#validation) for why a construction-time
  raise is deliberately avoided.
- Good, because the case-level `CS_vfd` 4-state enum and `cs_invariants.py`
  history validity logic are unchanged — the split is per-participant only.
- Bad, because migration of all `ParticipantStatus.vfd_state` call sites (#2663)
  is a large mechanical change requiring careful review.
- Neutral, because the compound CS state (VFD × PXA, 32 members) is unaffected;
  `CSB-17-001` remains valid.

## Validation

The role-dimension invariant is enforced at the *guard* layer, not at
construction. The `model_validator` on `ParticipantStatus`
(`_enforce_role_dimension_invariant`, `mode="before"`) only auto-seeds the
applicable dimension for VENDOR/DEPLOYER roles; it deliberately does **not**
raise on a stray dimension. Enforcement lives where the acting participant's
*authoritative* `case_roles` are known:

- **Trigger / emit path** (fail-closed): `ValidateTriggerTransitionsNode`
  (`_check_vf_role`) and the `CheckVendorRoleNode` / `CheckDeployerRoleNode` /
  `CheckNotSoleObserverVfdNode` guards on the add-participant-status trigger
  tree refuse the whole write when a role is missing (BTND-10-001, CSB-15-001,
  CSB-15-002, CM-25-005).
- **Receive path** (partial-accept): `_adjudicate_vf` / `_adjudicate_d`
  (`_adjudication.py`) refuse just the offending dimension against the
  authoritative roles and carry the current value forward (RSH-05-001/002).

A construction-time raise is deliberately **not** added: the wire→core
extractor (`vultron/wire/as2/extractor/_builders.py`) builds a
`ParticipantStatus` from the sender's *untrusted, self-reported* `cvd_role`, so
a hard raise there would convert receive-path per-dimension partial-accept into
whole-object rejection — violating the emit/receive Postel asymmetry documented
in `notes/domain-validation.md`. See issue #2860.

Validated by unit tests in `test/core/models/test_participant_status_shape.py`
(`TestRoleDimensionInvariant` — auto-seed behaviour and that a stray dimension
is *not* rejected by the model), `test/core/behaviors/case/nodes/test_vfd_role_guards.py`
(trigger-path refusal), and
`test/core/behaviors/status/test_partial_accept_participant_status.py`
(receive-path refusal/acceptance).

## More Information

- Planning learning: `plan/history/2608/learning/CONCERN-2595.md`
- Follow-on concern (fine-grained vendor-deployer dependency tracking): #2665
- Immediate workaround (guard layer): PR #2593, CONCERN-2595

Generated spec requirements: `specs/cs-behavior.yaml` CSB-15-001, CSB-15-002,
CSB-15-004, CSB-16-001.
