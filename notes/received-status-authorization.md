---
title: "Received-Side Status Authorization: Two-Seam Design"
status: active
description: >
  Design notes for the two-seam authorization model that governs how a
  CaseActor adopts an inbound participant's reported CaseStatus as canonical
  (Seam 1) and whether to execute embargo teardown side-effects (Seam 2).
  Derived from the IDEA-1836 planning session.
related_specs:
  - specs/received-status-handling.yaml
  - specs/behavior-tree-integration.yaml
related_notes:
  - notes/bt-integration.md
  - notes/call-out-configuration.md
  - notes/bt-fuzzer-rm-threat.md
relevant_packages:
  - vultron/core/behaviors/status
  - vultron/core/use_cases/received
---

# Received-Side Status Authorization: Two-Seam Design

## Background

When a CaseActor receives an `Add(ParticipantStatus)` activity it faces two
separate questions:

1. **Adoption**: should the CaseActor treat the participant's claimed CaseStatus
   as canonical for the whole case?
2. **Side-effects**: if the status is canonical, should the CaseActor execute
   embargo teardown (or other side-effects)?

These are independent authorization decisions. The original
`PublicDisclosureBranchNode` conflated both in `add_participant_status_tree`,
ran before the canonical write, and covered only CS.P with a CASE_OWNER-only
gate. ADR-0046 formalizes the two-seam separation.

---

## Sentinel Integration Pattern

In production, threat monitoring is **event-driven**, not polling:

1. A **sentinel actor** (or any informed participant) monitors threat feeds and
   detects a signal (exploit published, attack observed, public disclosure).
2. The sentinel posts `Add(ParticipantStatus, CaseParticipant)` to the CaseActor,
   carrying the appropriate PXA state change (e.g., X=True for exploit, A=True
   for attacks).
3. The CaseActor's received-side BT processes the activity and decides whether
   to adopt the claim and act on it.

The simulation `MonitorThreats` polling BT (FUZZ-D / issue #1250) is superseded
by this pattern for production. The four simulation nodes
(`MonitorAttacks`, `MonitorExploits`, `MonitorPublicReports`, `NoThreatsFound`)
remain valid as fuzzer stubs for the sentinel actor's internal logic — they are
not wired into the CaseActor's received-side pipeline.

---

## Seam 1 — StatusUpdateGuard

**Location**: `add_participant_status_tree`, after `AppendParticipantStatusNode`

**Purpose**: decide whether to canonicalize the participant's reported CaseStatus

```text
AddParticipantStatusBT (Sequence)
├─ VerifySenderIsParticipantNode        ← unchanged
├─ CheckParticipantRMNotClosedNode      ← unchanged
├─ GuardedCommitOrSkip                  ← unchanged (CLP-10-006)
├─ AppendParticipantStatusNode          ← records "X said FOO" (unchanged)
├─ StatusUpdateGuard (Fallback)         ← NEW
│   ├─ CheckIsCaseOwnerNode             ← hard bypass: CASE_OWNER = gospel
│   └─ CaseOwnerApprovesStatusUpdate    ← Evaluator call-out (AlwaysSucceed)
├─ EmitAddCaseStatusToSelfNode          ← NEW: triggers canonicalization
└─ AutoCloseIfCaseManager               ← unchanged
```

### CASE_OWNER gospel-bypass rationale

CASE_OWNER is the human decision-maker for the case. Their reported status
updates are authoritative by definition — requiring them to approve their own
updates would be circular. The BT Fallback structure makes this a hard
structural skip: if `CheckIsCaseOwnerNode` succeeds, the approval call-out is
never reached.

For all other senders, the `CaseOwnerApprovesStatusUpdate` Evaluator call-out
provides the hook. In the prototype it defaults to `AlwaysSucceed` (all status
updates are adopted automatically). A production implementation can replace
this with a real policy engine or human-in-the-loop step.

### Self-addressed `Add(CaseStatus)` pattern

When `StatusUpdateGuard` passes, `EmitAddCaseStatusToSelfNode` emits
`Add(CaseStatus, VulnerabilityCase)` addressed to the CaseActor itself (acting
as CASE_MANAGER). This activity is routed through
`AddCaseStatusToCaseReceivedUseCase` → `add_case_status_tree`, where the
CASE_MANAGER-only gate passes naturally because the CaseActor is the sender.

This pattern decouples the two seams: `add_participant_status_tree` does not
know or care about teardown; `add_case_status_tree` does not know whether the
canonical write came from an external message or an internal self-emit.

---

## Seam 2 — SideEffectsGuard + ThreatTerminationBranchNode

**Location**: `add_case_status_tree`, after `AppendCaseStatusToCaseNode`

**Purpose**: decide whether to execute side-effects after a canonical write

```text
AddCaseStatusToCaseBT (Sequence)
├─ CheckCaseStatusIdempotencyNode       ← unchanged
├─ ValidateCaseStatusTransitionNode     ← unchanged
├─ AppendCaseStatusToCaseNode           ← unchanged (canonical write)
├─ SideEffectsGuard (Evaluator)         ← NEW call-out (AlwaysSucceed default)
└─ ThreatTerminationBranchNode          ← NEW: fires teardown on CS.P, CS.X, CS.A
```

### SideEffectsGuard

An Evaluator call-out that gates the entire side-effects block. Default:
`AlwaysSucceed`. A production implementation can replace this with a policy
check (e.g., require CASE_OWNER confirmation before executing teardown even
when the canonical write was authorized).

Note: the self-addressed `Add(CaseStatus)` path arrives with the CaseActor as
sender (CASE_MANAGER role). This means even when `SideEffectsGuard` requires
CASE_OWNER approval, the CaseActor has already obtained that approval via
Seam 1 before emitting the self-message. The two seams compose correctly.

### ThreatTerminationBranchNode

Replaces `PublicDisclosureBranchNode` (which is removed from
`add_participant_status_tree`). Fires `terminate_embargo_bt` when the canonical
CaseStatus carries any of:

- **CS.P** — public awareness (previously covered)
- **CS.X** — exploit public (newly covered)
- **CS.A** — attacks observed (newly covered)

The CASE_OWNER sender gate that was part of `PublicDisclosureBranchNode`
is dropped: authorization already occurred at Seam 1. By the time
`ThreatTerminationBranchNode` runs, the canonical state write has been
authorized.

---

## Call-Out Bundle

A new `StatusAuthorizationCallOutBundle` covers both seams:

```python
@dataclass(frozen=True)
class StatusAuthorizationCallOutBundle:
    status_update_guard_factory: CallOutBackendFactory = ...  # AlwaysSucceed
    side_effects_guard_factory: CallOutBackendFactory = ...   # AlwaysSucceed
```

Placed in `vultron/core/behaviors/call_out/bundles/status_authorization.py`
(core-owned, per ADR-0025 / module layout in `notes/call-out-configuration.md`).

---

## Migration from PublicDisclosureBranchNode

| Before | After |
|---|---|
| `PublicDisclosureBranchNode` in `add_participant_status_tree` | Removed |
| Gates: CS.P AND CASE_OWNER sender | N/A |
| Runs before canonical write | N/A |
| `ThreatTerminationBranchNode` in `add_case_status_tree` | Added |
| Gates: CS.P OR CS.X OR CS.A (no sender gate) | Correct tree, post-write |

---

## CaseStatus Emission Authority (RSH-04)

### The invariant

CaseStatus is the **only protocol channel** for communicating EM and PXA
state changes to participant replicas. This means:

1. **Only the CaseActor (CASE_MANAGER) emits `Add(CaseStatus)` directly.**
   All other participants embed a suggested `CaseStatus` inside
   `Add(ParticipantStatus)` and let the two-seam model decide whether to
   adopt it (RSH-04-001).

2. **Every CaseActor-side EM or PXA state mutation MUST be followed by a
   canonical `CaseStatus` ledger write** (RSH-04-002, RSH-04-003). Without
   it, all participant replicas remain stale until the next round-trip.

### The emit mechanism

A shared BT node, `EmitCaseStatusUpdateNode`, performs the canonical write:

1. Reads the updated `CaseStatus` from the case record (post-mutation state).
2. Appends it to `case.case_statuses` and persists.
3. Commits a `CaseLedgerEntry` (the authoritative ledger record).
4. The `Announce(CaseLedgerEntry)` broadcast that syncs participants to
   the new state is handled by the existing announce mechanism downstream.

This node is wired **after** every EM lifecycle node in each BT tree factory
(Propose, Accept, Reject, Terminate, and cascade variants such as
`RejectProposedEmbargoLifecycleNode` and `ApplyEmbargoTeardownNode`).

### Causality (important)

The correct causal order is:

```text
CaseActor mutates EM/PXA state
  → writes CaseStatus to ledger (authoritative)
  → Announce(CaseLedgerEntry) syncs participants
```

**Not** the inbox-loopback pattern that `EmitAddCaseStatusToSelfNode`
currently uses:

```text
[kludge] EmitAddCaseStatusToSelf → inbox → add_case_status_tree → writes ledger
```

The inbox seam (Seam 1 → Seam 2) exists for evaluating **external participant
suggestions**, not for the CaseActor recording its own authoritative state
changes. `EmitAddCaseStatusToSelfNode` is a recognized kludge; a follow-on
issue will refactor the inbound path to use direct ledger writes as well
(blocked by the `EmitCaseStatusUpdateNode` impl issue).

### BT nodes in scope for the emit invariant

| Node / Tree | EM transition | Covered by `EmitCaseStatusUpdateNode`? |
|---|---|---|
| `ProposeEmbargoLifecycleNode` (trigger) | NO_EMBARGO → PROPOSED or ACTIVE → REVISE | Pending (ISSUE-1667 child) |
| `AcceptEmbargoLifecycleNode` (trigger) | PROPOSED → ACTIVE | Pending |
| `RejectEmbargoLifecycleNode` (trigger) | PROPOSED → NO_EMBARGO | Pending |
| `TerminateEmbargoLifecycleNode` (trigger) | ACTIVE/REVISE → EXITED | Pending |
| `RejectProposedEmbargoLifecycleNode` (cascade) | PROPOSED → NO_EMBARGO | Pending |
| `ApplyEmbargoTeardownNode` (sync/announce) | ACTIVE/REVISE → EXITED | Pending |

---

## References

- ADR-0046: `docs/adr/0046-received-status-authorization.md`
- Spec: `specs/received-status-handling.yaml` RSH-01 through RSH-04
- Source Concern: CONCERN-1667
- Source Idea: IDEA-1836
- Superseded approach: `notes/bt-fuzzer-rm-threat.md` (sentinel integration context)
