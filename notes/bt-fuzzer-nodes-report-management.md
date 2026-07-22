---
title: "BT Fuzzer Nodes: Report Management (Index)"
status: active
description: >
  Index of per-RM-sub-workflow fuzzer-node catalogs; includes the fuzzer base-type
  probability table and cross-cutting production-collapse designs for four simulator
  subtree groups (issue #1200). Individual per-workflow catalogs are split into
  focused files listed below.
related_specs:
  - specs/behavior-tree-integration.yaml
related_notes:
  - notes/bt-integration.md
  - notes/bt-canonical-reference.md
  - notes/bt-fuzzer-nodes.md
  - notes/coordination-agents.md
  - notes/bt-fuzzer-rm-validation.md
  - notes/bt-fuzzer-rm-prioritization.md
  - notes/bt-fuzzer-rm-id-assignment.md
  - notes/bt-fuzzer-rm-fix.md
  - notes/bt-fuzzer-rm-exploit.md
  - notes/bt-fuzzer-rm-threat.md
  - notes/bt-fuzzer-rm-publication.md
  - notes/bt-fuzzer-rm-reporting.md
  - notes/bt-fuzzer-rm-closure.md
relevant_packages:
  - vultron/bt/report_management
---

# BT Fuzzer Nodes: Report Management

These are the stub nodes for report management BT sub-trees:
`ValidateReportBt`, `PrioritizeReportBt`, `AssignVulIdBt`, `DevelopFixBt`,
`DeployFixBt`, `MonitorThreatsBt`, `AcquireExploitBt`, `PublicationBt`,
`ReportToOthersBt`, `CloseReportBt`, and `OtherWorkBt` (all sourced from
`vultron/bt/report_management/fuzzer/`). See `notes/bt-fuzzer-nodes.md`
for background on what fuzzer nodes are and the full catalog index.

**Fuzzer base types quick reference:**

| btz type | Success probability |
|---|---|
| `AlwaysSucceed` | 1.00 |
| `AlmostCertainlySucceed` | 0.93 |
| `AlmostAlwaysSucceed` | 0.90 |
| `UsuallySucceed` | 0.75 |
| `OftenSucceed` / `LikelySucceed` | 0.70 |
| `ProbablySucceed` | 0.67 |
| `UniformSucceedFail` / `RandomSucceedFail` | 0.50 |
| `SuccessOrRunning` | 0.50 (never fails; returns SUCCESS or RUNNING) |
| `ProbablyFail` | 0.33 |
| `OftenFail` | 0.30 |
| `UsuallyFail` | 0.25 |
| `AlmostAlwaysFail` / `RarelySucceed` | 0.10 |
| `AlmostCertainlyFail` | 0.07 |
| `OneInTwenty` | 0.05 |
| `OneInOneHundred` | 0.01 |
| `OneInTwoHundred` | 0.005 |
| `AlwaysFail` | 0.00 |

---

## Per-Workflow Catalogs

Each RM sub-workflow's fuzzer-node catalog is in a focused file:

| Sub-workflow | File |
|---|---|
| Report Validation (`RMValidateBt`) | [bt-fuzzer-rm-validation.md](bt-fuzzer-rm-validation.md) |
| Report Prioritization (`RMPrioritizeBt`) | [bt-fuzzer-rm-prioritization.md](bt-fuzzer-rm-prioritization.md) |
| Vulnerability ID Assignment (`AssignVulIdBt`) | [bt-fuzzer-rm-id-assignment.md](bt-fuzzer-rm-id-assignment.md) |
| Fix Development + Deployment (`DevelopFixBt` / `DeployFixBt`) | [bt-fuzzer-rm-fix.md](bt-fuzzer-rm-fix.md) |
| Exploit Acquisition (`AcquireExploitBt`) | [bt-fuzzer-rm-exploit.md](bt-fuzzer-rm-exploit.md) |
| Threat Monitoring (`MonitorThreatsBt`) | [bt-fuzzer-rm-threat.md](bt-fuzzer-rm-threat.md) |
| Publication (`PublicationBt`) | [bt-fuzzer-rm-publication.md](bt-fuzzer-rm-publication.md) |
| Reporting to Other Parties (`ReportToOthersBt`) | [bt-fuzzer-rm-reporting.md](bt-fuzzer-rm-reporting.md) |
| Report Closure + Other Work (`CloseReportBt` / `RMDoWorkBt`) | [bt-fuzzer-rm-closure.md](bt-fuzzer-rm-closure.md) |

---

## Production Collapse Designs

The sections below document how groups of simulator fuzzer nodes are expected
to **collapse** in the production BT architecture. Each group of simulator
leaves maps to a smaller set of production call-out points. These designs are
**provisional** — they represent the best understanding at planning time
(issue #1200) and are subject to revision when the corresponding
implementation issues are worked.

Cross-references: each affected simulator-node entry above has a
"see Production Collapse" note pointing here. The implementation issues listed
in each section are what to work when it is time to build the production
subtrees.

---

### Production Collapse 1: Exploit-strategy subtree → EvaluateExploitStrategy

**Simulator nodes involved**: `HaveExploit`, `ExploitPrioritySet`,
`EvaluateExploitPriority`, `ExploitDeferred`, `ExploitDesired`
(see [bt-fuzzer-rm-exploit.md](bt-fuzzer-rm-exploit.md))

**Implemented by**: issue #1309 (PR #1566)

#### Production shape

The five-node simulator sequence is replaced by two independently-swappable
call-out points (ADR-0027 Option 2):

1. **`HaveExploit`** (Retriever) — early-exit guard; queries whether a working
   exploit already exists. Survives as a separate seam for independent swapability.
2. **`EvaluateExploitStrategy`** (Evaluator) — receives case context and returns
   a structured `ExploitStrategyDecision` record.

The three ProtocolInternal nodes (`ExploitPrioritySet`, `ExploitDeferred`,
`ExploitDesired`) are eliminated as separate BT leaves — their decisions become
internal reads on the Evaluator's output record.

**Output schema** (Pydantic BaseModel, implemented in
`vultron.core.behaviors.report.acquire_exploit_strategy_tree`):

```python
class ExploitStrategyDecision(BaseModel):
    have_exploit: bool = False  # whether a working exploit is already available
    acquire: bool = False       # decision: pursue exploit acquisition
    rationale: str = ""         # reasoning for the decision
```

**Factory function**:
`vultron.core.behaviors.report.acquire_exploit_strategy_tree.create_acquire_exploit_strategy_tree`

**Spec requirements**: BT-20-001 (see `specs/behavior-tree-integration.yaml`)

---

### Production Collapse 2: Publication-intent subtree → Evaluator + per-artifact arms

**Simulator nodes involved**: `PublicationIntentsSet`, `PrioritizePublicationIntents`,
`NoPublishExploit`, `ExploitReady`, `PrepareExploit`, `ReprioritizeExploit`,
`NoPublishFix`, `PrepareFix`, `ReprioritizeFix`, `NoPublishReport`,
`PrepareReport`, `ReprioritizeReport`
(see [bt-fuzzer-rm-publication.md](bt-fuzzer-rm-publication.md))

**Implemented by**: issue #1310

#### Production shape

The `PublicationIntentsSet` flag check and `NoPublish*` bypass leaves are
**ProtocolInternal structural artifacts** of the simulator representation —
they do not survive as call-out points. In production:

1. **`PrioritizePublicationIntents`** (already an Evaluator) returns a
   structured `PublicationIntentDecision` record: `{publish_exploit: bool,
   publish_fix: bool, publish_report: bool, rationale: str}`. The
   `PublicationIntentsSet` flag check disappears — the BT queries the intent
   record directly via `ShouldPublishX` gate nodes.

2. For each intended artifact: one **Composer** subtree
   (`PrepareExploit` / `PrepareFix` / `PrepareReport`) drafts and stages the
   artifact.

3. For each prepared artifact: one **Actuator** (`Publish`) submits to the
   external advisory platform.

The `NoPublish*` bypass leaves and `ReprioritizeX` Evaluators disappear — the
intent record from step 1 drives which arms execute. The removed `NoPublishX`
leaves are replaced by positively-named `ShouldPublishX` gate nodes
(BTND-08-001) that read the intent record; each arm's `Inverter(ShouldPublishX)`
skip branch provides the graceful no-op that `NoPublishX` used to.

**BT structure** (lean: three named arms — exploit arm, fix arm, report arm):

```text
PublicationBT (Sequence)
├── PrioritizePublicationIntents (Evaluator)       — writes PublicationIntentDecision
├── ExploitPublicationArm (Selector)
│   ├── Sequence(ShouldPublishExploit, PrepareExploit, Publish)
│   └── Inverter(ShouldPublishExploit)             — SUCCESS no-op if not intended
├── FixPublicationArm (Selector)                   — same shape, publish_fix gate
└── ReportPublicationArm (Selector)                — same shape, publish_report gate
```

The per-arm `Publish` Actuator is kept as a single leaf here; expanding it into
a draft-review-submit pipeline is Production Collapse 4 (ADR-0030 / BT-20-004).

**Factory function**:
`vultron.core.behaviors.report.publication_tree.create_publication_tree`

**Output schema**: `PublicationIntentDecision(publish_exploit, publish_fix,
publish_report, rationale)` (Pydantic BaseModel) in
`vultron/core/behaviors/report/publication_tree.py`

**Spec requirements**: BT-20-002 (see
`specs/behavior-tree-integration.yaml`) and ADR-0028

---

### Production Collapse 3: Notification loop → suggest-actor-to-case protocol

**Simulator nodes involved**: `HaveReportToOthersCapability`, `AllPartiesKnown`,
`IdentifyVendors`, `IdentifyCoordinators`, `IdentifyOthers`,
`NotificationsComplete`, `ChooseRecipient`, `RemoveRecipient`,
`RecipientEffortExceeded`, `TotalEffortLimitMet`, `PolicyCompatible`,
`FindContact`, `RcptNotInQrmS`, `SetRcptQrmR`, `MoreVendors`,
`MoreCoordinators`, `MoreOthers`, `InjectParticipant`, `InjectVendor`,
`InjectCoordinator`, `InjectOther`
(see [bt-fuzzer-rm-reporting.md](bt-fuzzer-rm-reporting.md))

**Implemented by**: issue #1311 (PR see ADR-0029)

#### Production shape

The **outer loop structure survives** — `create_report_to_others_tree` builds a
BT that asks "should we notify additional parties?" and iterates through
identified parties grouped by role. What changes is **what happens at the end
of each iteration**: instead of `InjectParticipant` (a direct case-management
write), the BT writes the appropriate `CVDRole` to the blackboard and calls
the `suggest-actor-to-case` trigger, which initiates the full
`RecommendActor → Invite → Accept → Record` cascade automatically.

Tree structure::

    ReportToOthersBT (Sequence, memory=False)
    ├── AllPartiesKnown            (Evaluator factory)
    ├── TotalEffortLimitMet        (Evaluator factory)
    ├── VendorSubLoop              (Selector — skip-or-execute, BTND-08-001)
    │   ├── Inverter(MoreVendors)
    │   └── Sequence(MoreVendors, WriteVendorRoles, SuggestVendor)
    ├── CoordinatorSubLoop         (Selector)
    │   ├── Inverter(MoreCoordinators)
    │   └── Sequence(MoreCoordinators, WriteCoordinatorRoles, SuggestCoordinator)
    └── OtherSubLoop               (Selector)
        ├── Inverter(MoreOthers)
        └── Sequence(MoreOthers, WriteOtherRoles, SuggestOther)

**Nodes that survive** (as call-out points or ProtocolInternal):

- `AllPartiesKnown` — Evaluator factory (outer guard)
- `TotalEffortLimitMet` — Evaluator factory (outer effort-limit guard)
- `MoreVendors`, `MoreCoordinators`, `MoreOthers` — factory-backed
  ProtocolInternal iteration guards; each appears in both the skip arm
  (Inverter) and execute arm (Sequence) of its sub-loop (BTND-08-001)

**Nodes that collapse**:

- `HaveReportToOthersCapability`, `NotificationsComplete`, `ChooseRecipient`,
  `FindContact`, `RcptNotInQrmS`, `RecipientEffortExceeded`, `PolicyCompatible`,
  `RemoveRecipient`, `SetRcptQrmR` — eliminated from the outer loop; per-
  recipient effort gating and RM-state writes are now managed by the
  `suggest-actor-to-case` cascade (SetRcptQrmR is handled by AcceptInviteToCase)
- `InjectParticipant`, `InjectVendor`, `InjectCoordinator`, `InjectOther` —
  replaced by the `WriteXRoles` + `suggest_*_factory` pair in each sub-loop.
  `InjectVendor`/`InjectCoordinator`/`InjectOther` remain in the demo layer
  as the **default fuzzer backends** for `suggest_vendor_factory`,
  `suggest_coordinator_factory`, and `suggest_other_factory` respectively.

**New ProtocolInternal node**:

- `_WriteRolesNode` — writes `suggested_roles_{case_id_segment}` = [CVDRole.X]
  to the blackboard before the trigger fires, so the downstream CaseActor
  receive path carries the correct role when forwarding
  `Offer(CaseParticipant)` to the Case Owner (BTND-03-004, AC-2).

**Factory function**:
`vultron.core.behaviors.report.create_report_to_others_tree`
(module: `vultron/core/behaviors/report/report_to_others_tree.py`)

**Spec requirements**: BT-20-003 — see `specs/behavior-tree-integration.yaml`

---

### Production Collapse 4: Publish leaf → draft-review-submit pipeline

**Simulator nodes involved**: `Publish`
(see [bt-fuzzer-rm-publication.md](bt-fuzzer-rm-publication.md); also see
Production Collapse 2 for the per-artifact preparation context)

**Implemented by**: issue #1312 (`task/1607-signal-taxonomy` branch, 2026-07-22, ADR-0030 accepted)

#### Production shape

The single `Publish` simulator leaf expands into a **multi-step pipeline**
with its own call-out points. This acknowledges that advisory publication in
production involves drafting, review/approval, and submission — not a single
atomic action.

**Core pipeline** (lean: Composer → Evaluator → Actuator):

```text
PublishArtifactBT (Sequence)
├── DraftAdvisoryArtifact (Composer)    — draft CSAF/CVE JSON/advisory from case data
├── ReviewAdvisoryDraft (Evaluator)     — review/approve the draft (human or automated QA)
├── [optional] ReviseAdvisoryDraft (Composer) — revise based on review feedback
└── SubmitAdvisoryArtifact (Actuator)   — submit finalized artifact to advisory platform
```

**Open design question (deferred)**: Whether the review phase should include
a "broadcast draft to case participants for comment" step was explicitly
deferred in issue #1312 to a follow-on issue. The pipeline functions without
it — the default `ReviewAdvisoryDraft` Evaluator is an auto-approve
`AlwaysSucceed` stub (AC-3, ADR-0030). When the follow-on issue is addressed,
the participant-comment broadcast would involve emitting an outbound Activity
(a protocol-visible action) and optionally waiting for participant responses
— resembling the `Accept/Reject` question pattern used elsewhere.

**Impact on existing `Publish` Actuator nodes**: Each per-artifact arm in
Production Collapse 2 (`ExploitReady → Publish`, `PrepareFix → Publish`,
`PrepareReport → Publish`) has its own `Publish` Actuator. In production,
those Actuators are each replaced by this full `PublishArtifactBT` subtree.

**Implemented factory function**:
`vultron.core.behaviors.report.publish_artifact_tree.create_publish_artifact_tree`
(called from `create_publication_tree` per arm via `_make_artifact_arm`)

**Spec requirements**: BT-20-004 (see `specs/behavior-tree-integration.yaml`)

---

## Sentinel Stubs Must Be Synced When the Upstream Issue Closes

(ISSUE-1177, 2026-07-14)

A catalog entry with `New-arch cross-ref: *(to be implemented — see FUZZ-08x)*`
where the referenced issue is now **closed** is a gap — the stub was never
promoted.

When FUZZ-08f (Sentinel shape, issue #1175) closed, three catalog entries
here carried `*(to be implemented — see FUZZ-08f)*`:

- `NewValidationInfoSentinel` — was implemented; cross-ref updated.
- `NewPrioritizationInfoSentinel` — left unimplemented.
- `NewDeploymentInfoSentinel` — left unimplemented.

Only the first was added; the other two remained as unimplemented stubs with
no matching class in `call_out_point.py`.

**Pattern to apply** during domain-sweep audits (FUZZ-08h style):

1. Grep catalog entries for `*(to be implemented — see FUZZ-08x)*`.
2. Check if the referenced issue is closed.
3. If closed but the class is absent from `call_out_point.py`, it is a gap —
   add the class and update the catalog cross-ref line.

The domain-sweep audit is the right checkpoint for this; catching it there
prevents gaps from persisting across multiple closed issues.

---
