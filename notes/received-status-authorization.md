---
title: "Received-Side Status Authorization: Two-Seam Design"
status: active
description: >
  Design notes for the two-gate authorization model that governs how a
  CaseActor adopts an inbound participant's reported CaseStatus as canonical
  (StatusAdoptionGate) and whether to execute embargo teardown side-effects (EmbargoTeardownAuthorizationGate).
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

# Received-Side Status Authorization: Two-Gate Design

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

## StatusAdoptionGate

**Location**: `add_participant_status_tree`, after `AppendParticipantStatusNode`

**Purpose**: decide whether to canonicalize the participant's reported CaseStatus

```text
AddParticipantStatusBT (Sequence)
├─ VerifySenderIsParticipantNode        ← unchanged
├─ FilterParticipantStatusDimensionsNode ← per-dimension adjudication (RSH-05)
├─ GuardedCommitOrSkip                  ← unchanged (CLP-10-006)
├─ AppendParticipantStatusNode          ← records the accepted portion
├─ StatusAdoptionGate (Fallback)         ← NEW
│   ├─ CheckIsCaseOwnerNode             ← hard bypass: CASE_OWNER = gospel
│   └─ CaseOwnerApprovesStatusUpdate    ← Evaluator call-out (AlwaysSucceed)
├─ EmitAddCaseStatusToSelfNode          ← NEW: triggers canonicalization
└─ AutoCloseIfCaseManager               ← unchanged
```

### Per-dimension partial accept (RSH-05, ADR-0061)

`FilterParticipantStatusDimensionsNode` replaced the former
`CheckParticipantRMNotClosedNode` guard. The old guard — and
`ValidateRMTransitionNode` inside the append subtree — refused a whole
`ParticipantStatus` snapshot when its `rm` dimension was unacceptable, which
discarded the accepted `vfd`/`pxa` values *and* aborted this Sequence before
the StatusAdoptionGate emit, silently skipping embargo teardown (ISSUE-2235).

The guard now adjudicates `rm`, `vfd` and `pxa` independently and publishes a
*filtered* `ParticipantStatus` in which each refused dimension carries the
participant's current value forward. It is read-only with respect to the
DataLayer (CLP-10-006), so it can run before `GuardedCommitOrSkip` and the
canonical entry snapshots the accepted portion rather than the raw claim.

`em` is deliberately **not** adjudicated here — embargo state belongs to EmbargoTeardownAuthorizationGate
(ISSUE-2256).

Two blackboard keys carry the handoff. Both are written on *every* tick (with
`None` when nothing was filtered) and matched by object ID on read, because the
py_trees blackboard is process-global and `BTBridge.execute_with_setup` restores
only `datalayer` and `trigger_activity_factory` between runs:

| Key | Producer | Consumers |
|---|---|---|
| `append_status_dimension_filter` | `FilterParticipantStatusDimensionsNode` | `ResolveAndPersistStatusObjectNode`, `ValidateRMTransitionNode` |
| `ledger_payload_object_override` | `FilterParticipantStatusDimensionsNode` | `CommitCaseLedgerEntryNode` |

`ledger_payload_object_override` is defined in
`vultron/core/behaviors/case/nodes/lifecycle.py` next to its consumer and is
deliberately generic (`{"object_id", "fields"}`): any receive tree may patch the
`object` entry of the ledger payload snapshot, and the other receive trees are
unaffected because the override is opt-in and ID-matched.

It carries a **field patch, not a replacement object** (RSH-05-009). The
snapshot's `object` is the sender's wire-shaped `ParticipantStatus` — flat
`rmState`/`vfdState`, nested `caseStatus`, plus `@context`, `emConsentState` and
`cvdRole` — and every replica plus the case-ledger invariant harness read it in
that shape. A guard in `vultron.core` cannot rebuild that object: core has zero
`from vultron.wire` imports (ADR-0009, ADR-0017), so dumping the core model
would emit nested `rm`/`vfd` dimension objects and drop every field the guard
never adjudicated. Naming only the adjudicated fields, keyed by wire alias, and
merging them onto the existing snapshot makes shape preservation structural
rather than something the guard has to remember:

```python
{"object_id": status_id, "fields": {"rmState": "VALID", "vfdState": "VFd",
                                    "caseStatus": {"pxaState": "Pxa", ...}}}
```

`CommitCaseLedgerEntryNode._resolve_payload_object_override` merges one level
deep, so patching `caseStatus.pxaState` keeps that nested object's own `id`; it
leaves a `caseStatus` that is still a bare reference string alone, and it drops
the stale snake_case twin of any patched alias so a consumer preferring
`rm_state` cannot read the value the receiver just refused.

`ValidateRMTransitionNode` keeps its all-or-nothing RM semantics when the
append subtree is used standalone. It only relaxes when the blackboard says
`rm` was refused upstream and carried forward — a narrower change than
reordering its terminal-`CLOSED` and equality checks would have been.

Two things the guard tracks that are easy to conflate:

- **An omitted `caseStatus` is not a refusal.** A status that says nothing about
  `pxa`/`em` has the receiver's own `case_status` carried forward; persisting the
  assertion verbatim would blank both dimensions, which is silent data loss, not
  adjudication. So the guard returns two different sets: `refused` names the
  dimensions whose asserted value was rejected, while the `model_copy` update
  also covers dimensions nobody asserted. If carrying `case_status` forward is
  the *only* thing the update does, nothing new was learned and the status is
  refused in full (RSH-05-005).
- **A blocked dimension is not always a rewritten one.** `RM.CLOSED` restated by
  a participant already at `RM.CLOSED` is refused by the terminal-state rule, but
  the recorded value matches the assertion, so nothing was discarded. The
  operator-facing WARNING distinguishes `rewrote dimension(s) …` from `blocked
  dimension(s) … with no change to the asserted value`; calling the latter a
  refusal would misdescribe the audit trail.

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

When `StatusAdoptionGate` passes, `EmitAddCaseStatusToSelfNode` emits
`Add(CaseStatus, VulnerabilityCase)` addressed to the CaseActor itself (acting
as CASE_MANAGER). This activity is routed through
`AddCaseStatusToCaseReceivedUseCase` → `add_case_status_tree`, where the
CASE_MANAGER-only gate passes naturally because the CaseActor is the sender.

This pattern decouples the two gates: `add_participant_status_tree` does not
know or care about teardown; `add_case_status_tree` does not know whether the
canonical write came from an external message or an internal self-emit.

---

## EmbargoTeardownAuthorizationGate + ThreatTerminationBranchNode

**Location**: `add_case_status_tree`, after `AppendCaseStatusToCaseNode`

**Purpose**: decide whether to execute side-effects after a canonical write

```text
AddCaseStatusToCaseBT (Sequence)
├─ CheckCaseStatusIdempotencyNode       ← unchanged
├─ ValidateCaseStatusTransitionNode     ← unchanged
├─ AppendCaseStatusToCaseNode           ← unchanged (canonical write)
├─ EmbargoTeardownAuthorizationGate (Evaluator)         ← NEW call-out (AlwaysSucceed default)
└─ ThreatTerminationBranchNode          ← NEW: fires teardown on CS.P, CS.X, CS.A
```

### EmbargoTeardownAuthorizationGate

An Evaluator call-out that gates the entire side-effects block. Default:
`AlwaysSucceed`. A production implementation can replace this with a policy
check (e.g., require CASE_OWNER confirmation before executing teardown even
when the canonical write was authorized).

Note: the self-addressed `Add(CaseStatus)` path arrives with the CaseActor as
sender (CASE_MANAGER role). This means even when `EmbargoTeardownAuthorizationGate` requires
CASE_OWNER approval, the CaseActor has already obtained that approval via
StatusAdoptionGate before emitting the self-message. The two gates compose correctly.

### ThreatTerminationBranchNode

Replaces `PublicDisclosureBranchNode` (which is removed from
`add_participant_status_tree`). Fires `terminate_embargo_bt` when the canonical
CaseStatus carries any of:

- **CS.P** — public awareness (previously covered)
- **CS.X** — exploit public (newly covered)
- **CS.A** — attacks observed (newly covered)

The CASE_OWNER sender gate that was part of `PublicDisclosureBranchNode`
is dropped: authorization already occurred at StatusAdoptionGate. By the time
`ThreatTerminationBranchNode` runs, the canonical state write has been
authorized.

---

## Call-Out Bundle

A new `StatusAuthorizationCallOutBundle` covers both gates:

```python
@dataclass(frozen=True)
class StatusAuthorizationCallOutBundle:
    status_adoption_gate_factory: CallOutBackendFactory = ...  # AlwaysSucceed
    embargo_teardown_authorization_gate_factory: CallOutBackendFactory = ...   # AlwaysSucceed
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

The inbox gate (StatusAdoptionGate → EmbargoTeardownAuthorizationGate) exists for evaluating **external participant
suggestions**, not for the CaseActor recording its own authoritative state
changes. `EmitAddCaseStatusToSelfNode` is a recognized kludge; a follow-on
issue will refactor the inbound path to use direct ledger writes as well
(blocked by the `EmitCaseStatusUpdateNode` impl issue).

### BT nodes in scope for the emit invariant

| Node / Tree | EM transition | Covered by `EmitCaseStatusUpdateNode`? |
|---|---|---|
| `ProposeEmbargoLifecycleNode` in `propose_embargo_trigger_bt` (initial proposal) | NO_EMBARGO → PROPOSED | Pending (ISSUE-2175) |
| `ProposeEmbargoLifecycleNode` in `propose_embargo_revision_trigger_bt` (revision, with `ValidateEmbargoRevisionStateNode` guard) | ACTIVE → REVISE | Pending (ISSUE-2175) |
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
