---
title: "Received-Side Status Authorization: Two-Gate Design"
status: active
description: >
  Design notes for the two-gate authorization model that governs how a
  CaseActor adopts an inbound participant's reported CaseStatus as canonical
  (StatusAdoptionGate) and whether to execute embargo teardown side-effects (EmbargoTeardownAuthorizationGate).
  Derived from the IDEA-1836 planning session.
related_specs:
  - specs/received-status-handling.yaml
  - specs/behavior-tree-integration.yaml
  - specs/cs-behavior.yaml
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
│   └─ CaseOwnerApprovesStatusUpdate    ← authorization seam (as-built: RequireCaseOwnerApproval;
│                                          RSH-07-004 replaces the shape — see below)
├─ EmitCaseStatusUpdateNode             ← direct ledger write (RSH-04-004, #2857)
├─ TeardownEffectsOrSkip (FailureIsSuccess)
│   └─ TeardownEffects (Sequence)
│       ├─ EmbargoTeardownAuthorizationGate  ← call-out gate (RSH-02-001)
│       └─ ThreatTerminationBranchNode       ← teardown on P/X/A (RSH-03-001)
└─ EmitRMGapNoteNode                    ← NEW: Add(Note,Case) on RM anomaly (RSH-06-004, ADR-0067)
```

### Per-dimension partial accept (RSH-05, ADR-0061)

`FilterParticipantStatusDimensionsNode` replaced the former
`CheckParticipantRMNotClosedNode` guard (now removed). The old guard — and
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
(ISSUE-2256, now implemented). See the **Per-Dimension CaseStatus Adjudication** section for the
`FilterCsEmDimensionNode` / `FilterCsPxaDimensionNode` / `FinalizeCsFilterNode` design.

Two blackboard keys carry the handoff. Both are written on *every* tick (with
`None` when nothing was filtered) and matched by object ID on read, because the
py_trees blackboard is process-global and `BTBridge.execute_with_setup` restores
only `datalayer` and `trigger_activity_factory` between runs:

| Key | Producer | Consumers |
|---|---|---|
| `append_status_dimension_filter` | `FilterParticipantStatusDimensionsNode` | `ResolveAndPersistStatusObjectNode`, `ValidateRMTransitionNode` |
| `ledger_payload_object_override` | `FilterParticipantStatusDimensionsNode` | `CommitCaseLedgerEntryNode` |

`ledger_payload_object_override` is defined in
`vultron/core/behaviors/case/nodes/lifecycle.py` next to its consumer. The
required shape is `{"object_id": <id>, "producer_type": <str>, "fields": {…}}`
(RSH-05-011). Any receive tree may patch the `object` entry of the ledger
payload snapshot; the other receive trees are unaffected because the override is
opt-in and ID-matched.

**Producer contract** (RSH-05-010 through RSH-05-012): every producer MUST (a)
write `None` to the key unconditionally at the start of every tick before any
early return (BT-17-003), (b) include `producer_type` identifying the source
node, and (c) use only wire alias keys recognized by the consumer.

**Consumer validation** (RSH-05-013, RSH-05-014): `CommitCaseLedgerEntryNode`
hard-fails on any unrecognized wire alias in `fields` (data integrity) and
warns on an unrecognized `producer_type` (audit hint, not a commit blocker).

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
{"object_id": status_id, "producer_type": "FilterParticipantStatusDimensionsNode",
 "fields": {"rmState": "VALID", "vfdState": "VFd",
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

#### Independent adjudication cannot see a combination (RSH-05-020)

Each dimension can be individually well-formed and the snapshot still describe a
state no sequence of events could produce: a *ready* or *deployed* fix entails a
report the participant has already accepted, and a deployed fix entails a ready
one. So a final pass evaluates the cross-machine entailments — RM↔VF and RM↔D
(CSB-18-001) and VF↔D (CSB-17-001) — and refuses whichever dimension they
disqualify, carrying the current value forward like any other refusal.

Three properties of that pass are load-bearing:

- **It refuses the dimension that *moved*.** VF↔D constrains a pair, so either
  side can be the offending claim. Refusing the incumbent side carries its value
  straight back — the impossible combination stays recorded and the audit trail
  reports a refusal that changed nothing. A dimension the sender omitted is
  never reported as refused, which keeps the `refused` / `update_fields` split
  above honest. Because the choice is path-specific, the shared evaluator reports
  *candidate* dimensions per rule and the receive path picks; the emit path
  refuses the whole snapshot and needs no choice.
- **It runs on the *effective* state, not the assertion.** This matters for the
  `vf`→`d` chain: a refused or carried-forward `vf` must not license the `d` the
  sender paired it with (#2893). It is *not* a tightening for `rm` — `rm` is
  refused only when the asserted value is not a forward move, so the carried
  value always ranks at or above the asserted one on the RM progress scale, and
  `RM_STATES_CONSISTENT_WITH_FIX` is exactly the top of that scale. Reading the
  effective `rm` can therefore only ever *accept* something the asserted `rm`
  would refuse, never the reverse. Do not cite it as a defence against a
  regressive `rm` licensing a `vf`; no such input exists.
- **Emit and receive share one evaluator.**
  `cross_machine_violations()` in `vultron/core/states/cross_machine_invariants.py`
  composes the three rules; `ValidateTriggerTransitionsNode._validate_entailments`
  and `_adjudicate_cross_machine_entailments` both call it and neither calls the
  individual `violation_*` functions. Before #2906 the receive path composed only
  VF↔D by hand, so an assertion the actor would have refused to *emit* was
  accepted, hash-chained and replicated when it arrived from a peer instead.
  A ratchet test asserts the emit path still delegates.

What this is **not**: it is not a vf→Vf→VF ladder check. Non-adjacent forward
advances stay legal on the received path (CSB-16-001) — a peer may advance
several steps between status messages. An absent dimension (`None`) is likewise
*absent*, not at its initial state (ADR-0075): a non-VENDOR participant has no
vendor path, so no entailment applies through it, and a first observation of a
dimension is accepted when nothing contradicts it.

**The RM↔VF and RM↔D halves are sound, not complete.** Their real constraint is
that the actor passed through `RM.ACCEPTED` at some point — a *history* property
(`rm_em_cs.md` § Fix Ready). A `ParticipantStatus` carries only the current RM
value, so `RM_STATES_CONSISTENT_WITH_FIX` approximates it with the set of states
reachable *from* `ACCEPTED`. `DEFERRED` and `CLOSED` are in that set and are each
also reachable without acceptance (`VALID → DEFERRED`, `INVALID → CLOSED`), so
neither proves it. They stay in anyway: excluding them would refuse a peer that
advances through acceptance and reports fix readiness in one message, which
CSB-16-001 explicitly permits. Narrowing to `{ACCEPTED}` is the only complete
option over one snapshot and costs far more than it catches. A test derives the
set from the RM transition graph so it cannot drift, and a second test pins which
members are ambiguous. Tightening it properly needs RM history (#3015).

**What it guarantees is conditional.** If the participant's *current* state
satisfies the entailments, so does the recorded state. It cannot promise more:
when the incumbent state is already impossible, every carry-forward writes the
offending value back, so no per-dimension refusal can repair it. That case is
logged and left alone rather than reported as the refusal of a claim the sender
never made. Read a log line naming an unrepairable incumbent state as evidence
of a write that bypassed this pass, not of a bad assertion.

The pass also re-evaluates after each refusal instead of sweeping the violation
list once, because a refusal can retire a violation reported alongside it —
refusing `d` for RM↔D clears the D bit, which retires VF↔D too. Acting on the
stale entry would refuse a second dimension for a contradiction that no longer
exists.

The replica-apply path (`ApplyParticipantStatusFromLedgerNode`) is deliberately
out of scope. It applies CaseActor-authored canonical entries the CaseActor
already adjudicated, and is governed by the RM ratchet in RSH-05-007. That is
also the only way an impossible incumbent state is reachable today (#3009).

### CASE_OWNER gospel-bypass rationale

CASE_OWNER is the human decision-maker for the case. Their reported status
updates are authoritative by definition — requiring them to approve their own
updates would be circular. The BT Fallback structure makes this a hard
structural skip: if `CheckIsCaseOwnerNode` succeeds, the approval call-out is
never reached.

For all other senders, `CaseOwnerApprovesStatusUpdate` is the seam that requires
explicit Case Owner authorization before the assertion is adopted as canonical.
A permissive backend (e.g., `AlwaysSucceed`) MAY be configured for
trusted-participant or demo deployments but MUST be explicitly configured
(RSH-07-003, ADR-0076) — and MUST NOT be used to route around a gate that is
blocking (RSH-07-005).

> **Mechanism amended by ADR-0080 (2026-08-31).** The seam is **not** a
> single-tick Evaluator that "performs an Offer/Accept/Reject round-trip and
> waits", and `RequireCaseOwnerApproval` is **not** the default backend to
> implement. RSH-07-004 requires each gate be composed as a
> **conversation-state routing subtree**, and forbids the Evaluator shape: at the
> moment authorization is first needed no answer exists, so an Evaluator asked
> "is this approved?" can only ever answer *no*. That is precisely why
> `RequireCaseOwnerApprovalNode` is a deny-always stub, and why the
> ADR-0046/ADR-0076 model was unreachable by any pathway (CONCERN-2812,
> CONCERN-2809). The node is **deleted rather than completed**.
>
> The gate instead routes on whether authorization has been *recorded*,
> *refused*, *requested-and-outstanding*, or *never requested* — emitting
> `Offer(Proposal)` to the Case Owner and terminating with `SUCCESS` in the last
> case, where `SUCCESS` means *I asked* (ASK-01-002). Authorization is always
> read from the case ledger, never from the outstanding-ask register
> (ASK-02-004). The conservative default posture that ADR-0076 establishes is
> **unchanged**; only its shape is.
>
> See [protocol-asks.md](protocol-asks.md), `specs/protocol-asks.yaml`
> (ASK-01 through ASK-08), and RSH-07-004/RSH-07-005. The replacement work is
> tracked by #2885.

### Direct-write canonicalization pattern (#2857)

When `StatusAdoptionGate` passes, `EmitCaseStatusUpdateNode` writes the
post-adoption `CaseStatus` snapshot directly to the case ledger via an inner
`BTBridge` call to `create_commit_log_entry_tree` (RSH-04-002, RSH-04-003,
RSH-04-004).  The node MUST NOT route through the inbox seam: no
`Add(CaseStatus)` activity is emitted to the CaseActor itself.

Embargo teardown side-effects (previously a downstream result of the inbox
path flowing into `add_case_status_tree`) are now handled inline immediately
after `EmitCaseStatusUpdateNode` via a `FailureIsSuccess`-wrapped
`TeardownEffects` Sequence:

- `EmbargoTeardownAuthorizationGate` — call-out that gates execution
  (RSH-02-001).
- `ThreatTerminationBranchNode` — fires `terminate_embargo_bt` when the
  adopted `CaseStatus` carries P=True, X=True, or A=True (RSH-03-001 to
  RSH-03-003).

The `FailureIsSuccess` wrapper ensures the outer tree still returns SUCCESS
when the authorization gate blocks teardown, mirroring the tolerant
semantics in the use case layer.  This replaced the former inbox-loopback
kludge (`EmitAddCaseStatusToSelfNode`) which required `add_case_status_tree`
to act as an indirect side-effect channel.

---

## Per-Dimension CaseStatus Adjudication (ISSUE-2256, ADR-0061)

**Location**: `add_case_status_tree`, before `GuardedCommitOrSkip`

**Purpose**: accept each EM/PXA dimension independently; carry forward refused
dimensions so a valid EM advance is not discarded alongside a stale PXA value.

Extends the same liberal-accept pattern that ADR-0061 / ISSUE-2235 applied to
`ParticipantStatus` (RM+VFD+PXA) to `CaseStatus` (EM+PXA).

```text
AddCaseStatusToCaseBT (Sequence)
├─ CheckCaseStatusIdempotencyNode       ← precondition guard (CLP-10-009)
├─ FilterCsEmDimensionNode              ← per-dim EM adjudication (RSH-05-018); always SUCCESS
├─ FilterCsPxaDimensionNode             ← per-dim PXA adjudication (RSH-05-019); always SUCCESS
├─ FinalizeCsFilterNode                 ← FAILURE on whole-refusal; publishes filter
├─ GuardedCommitOrSkip                  ← canonical ledger commit (CLP-10-006)
├─ AppendCaseStatusToCaseNode           ← records accepted portion
├─ EmbargoTeardownAuthorizationGate     ← authorization seam (as-built; RSH-07-004)
└─ ThreatTerminationBranchNode          ← fires teardown on CS.P, CS.X, CS.A
```

`ValidateCaseStatusTransitionNode` (the former all-or-nothing guard) has been
removed; per-dimension filter nodes are its replacement.

### Three-node design

`FilterCsEmDimensionNode` runs first: it clears both `BB_CASE_STATUS_DIM_FILTER`
and `BB_LEDGER_PAYLOAD_OBJECT_OVERRIDE` unconditionally (RSH-05-010, BT-17-003),
evaluates the EM transition per the acceptance predicate in RSH-05-018
(`is_valid_em_transition()`), and writes a per-tick accumulator dict to the
blackboard.

`FilterCsPxaDimensionNode` runs second: it reads the accumulator via the
`_BB_CS_FILTER_ACC` input port, evaluates the PXA transition per the acceptance
predicate in RSH-05-019 (`is_monotonic_pxa_forward()`), and writes the
updated accumulator back via `_set_output(_BB_CS_FILTER_ACC_WRITE, acc)` — an
explicit write-back using a dual-alias output port (`_BB_CS_FILTER_ACC_WRITE`)
mapped to the same physical blackboard key (`/{_BB_CS_FILTER_ACC}`). This
satisfies the py_trees constraint that forbids the same logical port name from
appearing in both `input_ports()` and `output_ports()` of the same node (#2706).

`FinalizeCsFilterNode` runs third: it reads the completed accumulator, builds the
`model_copy`-filtered `CaseStatus` (refused dimensions carry current values
forward), and publishes both `BB_CASE_STATUS_DIM_FILTER` (for
`AppendCaseStatusToCaseNode`) and `BB_LEDGER_PAYLOAD_OBJECT_OVERRIDE` (for
`CommitCaseLedgerEntryNode`). Returns FAILURE when every dimension is refused and
no new state is carried (RSH-05-005).

`FinalizeCsFilterNode` is a REJECTION_VALIDATORS member: it MUST appear in
`precondition_guards`, never in `effect_nodes` (CLP-10-009).

### Blackboard keys

| Key | Producer | Consumer |
|---|---|---|
| `cs_dim_filter_accumulator` | `FilterCsEmDimensionNode` (write+clear) | `FilterCsPxaDimensionNode`, `FinalizeCsFilterNode` (read) |
| `append_case_status_dim_filter` | `FilterCsEmDimensionNode` (clear), `FinalizeCsFilterNode` (write) | `AppendCaseStatusToCaseNode` |
| `ledger_payload_object_override` | `FilterCsEmDimensionNode` (clear), `FinalizeCsFilterNode` (write) | `CommitCaseLedgerEntryNode` |

The `ledger_payload_object_override` override fields use camelCase wire aliases
(`emState`, `pxaState`) per RSH-05-012. `FinalizeCsFilterNode` is registered
in `_RECOGNIZED_OVERRIDE_PRODUCERS` per RSH-05-014.

---

## EmbargoTeardownAuthorizationGate + ThreatTerminationBranchNode

**Location**: `add_case_status_tree`, after `AppendCaseStatusToCaseNode`

**Purpose**: decide whether to execute side-effects after a canonical write

```text
AddCaseStatusToCaseBT (Sequence) — effect nodes only
├─ AppendCaseStatusToCaseNode           ← canonical write
├─ EmbargoTeardownAuthorizationGate     ← authorization seam (as-built; RSH-07-004)
└─ ThreatTerminationBranchNode          ← fires teardown on CS.P, CS.X, CS.A
```

### EmbargoTeardownAuthorizationGate

Gates the entire side-effects block, requiring explicit Case Owner authorization
before teardown runs (RSH-07-002, ADR-0076). An implementation MAY configure a
permissive backend (e.g., `AlwaysSucceed` via
`STATUS_AUTHORIZATION_PERMISSIVE`) for trusted or demo deployments (RSH-07-003),
but MUST NOT do so to unblock a gate that is refusing (RSH-07-005).

As built, the seam is an Evaluator call-out whose default backend is
`RequireCaseOwnerApproval`, which returns `FAILURE` unconditionally. Per
ADR-0080 / RSH-07-004 that shape is superseded: the gate becomes a
conversation-state routing subtree, and `RequireCaseOwnerApprovalNode` is
deleted rather than completed. See the amendment note under **StatusAdoptionGate**
above and [protocol-asks.md](protocol-asks.md); tracked by #2885.

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

A `StatusAuthorizationCallOutBundle` covers both gates:

```python
@dataclass(frozen=True)
class StatusAuthorizationCallOutBundle:
    status_adoption_gate_factory: CallOutBackendFactory = ...  # RequireCaseOwnerApproval
    embargo_teardown_authorization_gate_factory: CallOutBackendFactory = ...  # RequireCaseOwnerApproval
```

As built, both fields default to `RequireCaseOwnerApproval` (RSH-07-001,
RSH-07-002, ADR-0076). Under ADR-0080 / RSH-07-004 that default is retired along
with the node: no `CallOutBackendFactory` may return an unconditional `FAILURE`
node as the conservative default, because the conservative posture is expressed
by the routing subtree's branches, not by a backend that always refuses. Demo and
trusted-participant deployments that need automated adoption MUST explicitly
configure a permissive backend — e.g.:

```python
STATUS_AUTHORIZATION_PERMISSIVE = StatusAuthorizationCallOutBundle(
    status_adoption_gate_factory=lambda n: AlwaysSucceed(n),
    embargo_teardown_authorization_gate_factory=lambda n: AlwaysSucceed(n),
)
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
| `ProposeEmbargoLifecycleNode` in `propose_embargo_trigger_bt` (initial proposal) | NO_EMBARGO → PROPOSED | Implemented (#2857) |
| `ProposeEmbargoLifecycleNode` in `propose_embargo_revision_trigger_bt` (revision, with `ValidateEmbargoRevisionStateNode` guard) | ACTIVE → REVISE | Implemented (#2857) |
| `AcceptEmbargoLifecycleNode` (trigger) | PROPOSED → ACTIVE | Implemented (#2857) |
| `RejectEmbargoLifecycleNode` (trigger) | PROPOSED → NO_EMBARGO | Implemented (#2857) |
| `TerminateEmbargoLifecycleNode` (trigger) | ACTIVE/REVISE → EXITED | Implemented (#2857) |
| `RejectProposedEmbargoLifecycleNode` (cascade) | PROPOSED → NO_EMBARGO | Implemented (#2857) |
| `ApplyEmbargoTeardownNode` (sync/announce) | ACTIVE/REVISE → EXITED | Implemented (#2857) |

---

## References

- ADR-0046: `docs/adr/0046-received-status-authorization.md`
- Spec: `specs/received-status-handling.yaml` RSH-01 through RSH-04
- Source Concern: CONCERN-1667
- Source Idea: IDEA-1836
- Superseded approach: `notes/bt-fuzzer-rm-threat.md` (sentinel integration context)
