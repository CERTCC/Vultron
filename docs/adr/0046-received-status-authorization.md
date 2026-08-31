---
status: accepted-provisional
date: 2026-07-30
updated: 2026-08-11
deciders: Allen D. Householder
consulted: Claude Sonnet 4.6
informed: []
---

# Two-Gate Authorization Model for Received-Side CaseStatus Canonicalization

## Context and Problem Statement

When a CaseActor receives an `Add(ParticipantStatus)` activity, it records
the participant's claimed state ("X said FOO"). But a separate question
follows: should the CaseActor treat that claimed state as canonical for the
whole case, and if so, should it execute side effects (embargo teardown)?

The pre-existing `PublicDisclosureBranchNode` in `add_participant_status_tree`
conflated these concerns: it gated teardown on (CS.P AND CASE_OWNER sender),
covering neither CS.X nor CS.A, and it ran before the CaseStatus was written
as canonical. The authorization and side-effect logic belonged in the wrong tree.

A production threat-monitoring architecture makes this gap acute: an external
sentinel actor (not necessarily a CASE_OWNER) posts `Add(ParticipantStatus)`
with PXA transitions; the CaseActor must decide independently whether to adopt
the claim and whether to trigger embargo teardown.

## Decision Drivers

- CaseStatus canonicalization and side-effect execution are distinct decisions
  requiring distinct authorization hooks
- CASE_OWNER reports are authoritative ("gospel") and should bypass approval;
  non-owner reports should pass through a configurable approval seam
- Embargo teardown must fire on CS.P, CS.X, and CS.A — not only CS.P
- The ADR-0025 call-out injection pattern should extend naturally to both
  authorization seams
- The `add_case_status_tree` pipeline is the correct place to trigger
  side-effects, because it is the authoritative writer of canonical case state

## Considered Options

1. **Single seam** — one call-out in `add_participant_status_tree` that covers
   both authorization and side-effects
2. **Two-seam model** — separate guards: one in `add_participant_status_tree`
   for status adoption, one in `add_case_status_tree` for side-effects
3. **No guard — always adopt, always fire teardown** — simplest, but no
   hook for future human-in-the-loop or policy-engine integration

## Decision Outcome

Chosen option: **Two-seam model** (option 2), because it respects the
single-responsibility principle across the two trees, preserves the
existing CASE_MANAGER-only gate on `add_case_status_tree`, and provides
independent extension points for authorization and side-effect policy.

The self-addressed `Add(CaseStatus)` pattern threads the two gates together
without coupling the trees directly: when StatusAdoptionGate passes, the CaseActor emits
`Add(CaseStatus)` to itself as CASE_MANAGER, which routes through
`add_case_status_tree` naturally and triggers EmbargoTeardownAuthorizationGate.

### Consequences

- Good: each gate has a single responsibility and a named call-out point
- Good: CASE_OWNER bypass is a hard structural skip (BT Fallback), not a
  policy decision that could be misconfigured
- Good: side-effects (teardown) only execute after canonical state is written,
  preserving write-before-side-effect ordering
- Good: both seams default to `RequireCaseOwnerApproval`, making the
  conservative posture the out-of-the-box behavior; permissive behavior
  (e.g., `AlwaysSucceed` for trusted-participant or demo deployments) requires
  explicit operator configuration (RSH-07-003, ADR-0076)
- Neutral: two new call-out fields add bundle surface area; addressed by a
  single `StatusAuthorizationCallOutBundle` (StatusAdoptionGate and EmbargoTeardownAuthorizationGate)
- Bad: the self-addressed `Add(CaseStatus)` introduces an internal loopback;
  implementations must ensure the CASE_MANAGER role check on
  `add_case_status_tree` is satisfied by the CaseActor's own identity

> **Amended by ADR-0080 (2026-08-31).** Both gates become **conversation-state
> routing subtrees** rather than single-tick Evaluator call-outs (RSH-07-004).
> The two-gate division of responsibility, the CASE_OWNER structural bypass, and
> the write-before-side-effect ordering are all unchanged; what changes is that a
> gate awaiting the Case Owner emits an ask and terminates successfully instead of
> answering the authorization question inline. See ADR-0080 and
> `notes/protocol-asks.md`.
>
> One consequence of the original design is worth reading in that light: because
> the gate sits *after* `AppendParticipantStatusNode`, the participant's claim is
> already recorded while adoption is pending. That is exactly the legitimate
> not-yet state ASK-02-005 requires an ask to leave behind, so this tree needed no
> new intermediate state to become askable.

## Gate Definitions

### StatusAdoptionGate (`add_participant_status_tree`)

Positioned after `AppendParticipantStatusNode` (which records the participant's
claim), before any canonicalization.

```text
StatusAdoptionGate (Fallback)
├─ CheckIsCaseOwnerNode            ← hard bypass: CASE_OWNER = gospel
└─ CaseOwnerApprovesStatusUpdate   ← Evaluator call-out (RequireCaseOwnerApproval default)
```

If the gate passes, `EmitAddCaseStatusToSelfNode` emits a self-addressed
`Add(CaseStatus)` to the CaseActor (as CASE_MANAGER).

### EmbargoTeardownAuthorizationGate + ThreatTerminationBranchNode (`add_case_status_tree`)

Positioned after `AppendCaseStatusToCaseNode`.

```text
EmbargoTeardownAuthorizationGate (Evaluator call-out, RequireCaseOwnerApproval default)
ThreatTerminationBranchNode    ← fires teardown on CS.P OR CS.X OR CS.A
```

`ThreatTerminationBranchNode` replaces and extends `PublicDisclosureBranchNode`,
which is removed from `add_participant_status_tree`.

## Validation

- Architecture boundary test (`test_core_no_demo_imports.py`) must continue to
  pass after new call-out bundles are added
- Unit tests: StatusAdoptionGate bypassed when sender is CASE_OWNER
- Unit tests: CaseOwnerApprovesStatusUpdate (AlwaysSucceed) passes for non-owner
- Unit tests: ThreatTerminationBranchNode fires teardown on CS.P, CS.X, CS.A
- Unit tests: CS states outside {P, X, A} do not trigger teardown
- Regression: CS.P path unaffected after migration of PublicDisclosureBranchNode

## Outbound Emit Invariant

The two-seam model governs **inbound** participant suggestions. A parallel
invariant applies to the CaseActor's **own** EM and PXA state mutations:

> Every CaseActor-side EM or PXA state change MUST be followed by a canonical
> `CaseStatus` ledger write. `CaseStatus` is the only protocol channel for
> communicating EM and PXA state to participant replicas.

The correct causal order is:

```text
CaseActor mutates EM/PXA state
  → writes CaseStatus to case.case_statuses + CaseLedgerEntry (authoritative)
  → Announce(CaseLedgerEntry) syncs participants
```

A shared `EmitCaseStatusUpdateNode` (direct write, not inbox-routed) is wired
after every EM lifecycle BT node. This is **not** a new seam decision — it
carves a limited exception to ADR-0021's inbox-routing rule: the CaseActor's
own outbound EM/PXA state change emissions write directly to the ledger rather
than routing through the inbox seam. The existing `EmitAddCaseStatusToSelfNode` (inbox-loopback path)
is a kludge that will be refactored once `EmitCaseStatusUpdateNode` is in place.

### CaseStatus Emission Authority (RSH-04)

Only the CaseActor (acting as CASE_MANAGER) emits `Add(CaseStatus)` directly.
All other participants embed a suggested `CaseStatus` inside
`Add(ParticipantStatus)`; the two-seam model decides whether to adopt it.

See `specs/received-status-handling.yaml` RSH-04-001 through RSH-04-004 and
`notes/received-status-authorization.md` § "CaseStatus Emission Authority".

---

## More Information

Design ratified in IDEA-1836 planning session (2026-07-30).
Status is `accepted-provisional` — the inbound two-seam design is implemented;
the outbound emit invariant (`EmitCaseStatusUpdateNode`) is pending
(CONCERN-1667 implementation child issue).

Generated spec requirements: `specs/received-status-handling.yaml` RSH-01
through RSH-04.
