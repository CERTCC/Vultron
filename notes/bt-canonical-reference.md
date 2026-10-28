---
title: Canonical CVD Protocol Behavior Tree Reference
status: active
kind: guidance
description: >
  How to use the canonical CVD Protocol Behavior Tree when building py_trees
  use-case trees: the trunk-removed-branches model and what it does not mean,
  node symbol legend, subtree map to current use cases, the Prioritize subtree,
  how to locate a new behavior, and the BT-IDM-01/02/03 anti-patterns.
related_specs:
  - specs/behavior-tree-integration.yaml
  - specs/behavior-tree-node-design.yaml
  - specs/bt-composability.yaml
  - specs/event-driven-control-flow.yaml
  - specs/message-semantics-mapping.yaml
  - specs/protocol-asks.yaml
related_notes:
  - notes/bt-integration.md
  - notes/bt-composability.md
  - notes/bt-pitfalls.md
  - notes/bt-design-patterns.md
  - notes/protocol-asks.md
  - notes/call-out-configuration.md
  - notes/use-case-behavior-trees.md
relevant_packages:
  - vultron/bt
  - vultron/core/behaviors
  - vultron/core/use_cases
---

# Canonical CVD Protocol Behavior Tree Reference

The **canonical CVD Protocol Behavior Tree** is the domain-level definition of
what Vultron does. Sources: `notes/vultron-bt.txt` (full tree dump from the
simulation engine), `docs/topics/behavior_logic/` (narrative per subtree), and
`vultron/bt/` (simulation implementation; frozen by BT-02-002, do NOT modify).

The simulation builds its nodes through the factory functions in
`vultron.bt.base.factory` (ADR-0004). That governs only the legacy engine; it is
a reading aid, not a rule for the `py_trees` nodes under
`vultron/core/behaviors/`, which the BTND requirements govern.

## The Trunk-Removed Branches Model

The simulation ticks one large `CvdProtocolRoot` tree continuously. The
prototype is event-driven and receives one ActivityStreams message at a time,
so it **removes the trunk and keeps the branches**: each use case in
`vultron/core/use_cases/` corresponds to a named subtree of the canonical BT,
and when an event (inbound activity, trigger call) arrives, the dispatcher runs
the matching subtree as a py_trees BT to completion, exactly as if the full tree
had ticked down to it.

**Why it matters**: when adding a cascade (A triggers B), check the canonical
tree. If B is a *child* of A there, B MUST be a BT subtree within A's use-case
tree, not a procedural call after the tree returns (BT-06-006). Anything outside
the tree is invisible to analysis and audit.

**What it does NOT mean**: it is not "map each child of `CvdProtocolRoot` (or
any fixed depth) to one use case". Extract at the depth where the behavior is
coherent, reusable, and has a natural protocol trigger. `EmbargoManagementBt`
is too coarse for one use case; `TerminateEmbargoBt` (its child) is a focused,
reusable behavior; `ConsiderTerminatingActiveEmbargo` (its child) is a
finer-grained piece composed into it. See `notes/bt-composability.md`.

### Node Symbol Legend

| Symbol | Node type | py_trees equivalent |
|--------|-----------|---------------------|
| `+--`  | Root sequence | `py_trees.composites.Sequence` |
| `>`    | Sequence (all children must succeed) | `py_trees.composites.Sequence` |
| `?`    | Selector (first success wins) | `py_trees.composites.Selector` |
| `l`    | While/loop | custom repeat decorator |
| `^`    | Inverter | `py_trees.decorators.Inverter` |
| `!`    | Action (emit message) | action leaf node |
| `a`    | Action (state transition) | action leaf node |
| `c`    | Condition check | condition leaf node |
| `z`    | Fuzzer node (human/external input stub) | call-out point |
| no prefix | Fuzzer subclass (e.g. `OnAccept_525`) | call-out point |
| `L->`  | Last child of parent | (same types as above) |

Strip the numeric suffix to get the simulator name
(`?_TerminateEmbargoBt_209` → `TerminateEmbargoBt`), then
`grep -rn "TerminateEmbargoBt" vultron/bt/` to read its children.

### Top-Level Structure

```text
CvdProtocolRoot (Sequence)
├─ Snapshot                     # capture current state
├─ DiscoverVulnerabilityBt      # finder role: find/receive vul
├─ ReceiveMessagesBt            # process inbound message queue
├─ ReportManagementBt           # RM state machine (non-message-driven)
└─ EmbargoManagementBt          # EM state machine (non-message-driven)
```

`ReceiveMessagesBt` maps to received-side use cases; `ReportManagementBt` and
`EmbargoManagementBt` map to trigger use cases. `DiscoverVulnerabilityBt` is
upstream of Vultron, which starts at `Offer(VulnerabilityReport)`.

### Subtree Map: Canonical BT → Use Cases

#### Message Receipt: ReceiveMessagesBt (`vultron-bt.txt` lines 26–410)

| Canonical subtree | Message type | Current use case |
|---|---|---|
| `>_ProcessRMMessagesBt_37` + `>__HandleRs_51` | RS (report submit) | `SubmitReportReceivedUseCase` |
| `>_ProcessEMMessagesBt_78` + `>__HandleEp_135` | EP (embargo propose) | `InviteToEmbargoOnCaseReceivedUseCase` |
| `>_ProcessEMMessagesBt_78` + `>__HandleEv_161` | EV (embargo revise) | `InviteToEmbargoOnCaseReceivedUseCase` (revision Invite) |
| `>_ProcessEMMessagesBt_78` + `>__HandleEa_148` / `>__HandleEc_191` | EA / EC (accept) | `ActivateEmbargoOnCaseReceivedUseCase` (the Case Owner's decision, MSM-02-002/005) |
| `>_ProcessEMMessagesBt_78` + `>__HandleEr_113` / `>__HandleEj_183` | ER / EJ (reject) | `RejectEmbargoProposalOnCaseReceivedUseCase`; ER also the CASE_MANAGER's abandonment via `RejectInviteToEmbargoOnCaseReceivedUseCase` (MSM-02-004/006) |
| `>_ProcessEMMessagesBt_78` + `>__HandleEt_98` | ET (embargo terminate) | `RemoveEmbargoEventFromCaseReceivedUseCase` |
| `>_ProcessCSMessagesBt_277` | CV/CF/CD/CP/CX messages | CS-state use cases |

A Participant's `Accept`/`Reject(Invite(Event))` is its own consent (PEC), handled by
`AcceptInviteToEmbargoOnCaseReceivedUseCase` and
`RejectInviteToEmbargoOnCaseReceivedUseCase`; it has no canonical subtree, because
the canonical tree models the case's view of the embargo, not PEC (MSM-02-010).

#### Report Management State Machine: ReportManagementBt (lines 411–1414)

| Canonical subtree | RM state trigger | Current use case |
|---|---|---|
| `>_RmReceived_414` + `?_RMValidateBt_416` | RM=RECEIVED → validate | `SvcValidateReportUseCase` (`report/validate_tree.py`) |
| `>__InvalidateReport_440` | validate → RM.INVALID | `SvcInvalidateReportUseCase` |
| `>_RmValid_503` + `?_RMPrioritizeBt_505` | RM=VALID → prioritize | `SvcEngageCaseUseCase` / `SvcDeferCaseUseCase` |
| `?_RMCloseBt_451/549/613` | RM=VALID/DEFERRED/ACCEPTED → close | `SvcLeaveCaseUseCase` (`leave-case`, once a case holds the report); `SvcRejectReportUseCase` before one does |

`?_RMValidateBt_416` and `?_RMPrioritizeBt_505` run in sequence in the same RM
branch, so **the validate→prioritize (engage/defer) cascade MUST be a BT
subtree**, never a procedural call after validation succeeds.

#### Embargo Management State Machine: EmbargoManagementBt (line 1415)

| Canonical subtree | EM state | Current use case |
|---|---|---|
| `>_EmNone_1430` | NONE → propose | `SvcProposeEmbargoUseCase` |
| `>_EmProposed_1480` | PROPOSED → accept/reject | `SvcAcceptEmbargoUseCase` / `SvcRejectEmbargoUseCase` |
| `>_EmActive_1618` | ACTIVE → revise/terminate | `SvcProposeEmbargoRevisionUseCase` / `SvcTerminateEmbargoUseCase` |
| `>_EmRevise_1734` | REVISE → accept/reject/terminate | as above |

### The Prioritize Subtree in Detail

```text
?_RMPrioritizeBt_505 (Selector)
├─ >__ConsiderGatheringMorePrioritizationInfo_506
│    └─ skip if already DEFERRED or ACCEPTED
├─ >__DecideIfFurtherActionNeeded_515 (Sequence)
│    ├─ check RM in VALID/DEFERRED/ACCEPTED
│    ├─ a_EvaluatePriority_520          ← SSVC or other evaluator
│    ├─ c_PriorityNotDefer_521          ← condition: should we engage?
│    └─ ?__EnsureRmAccepted_522
│         └─ >__TransitionToRmAccepted_524
│              ├─ OnAccept_525
│              ├─ transition RM → ACCEPTED
│              └─ !_Emit_RA_533         ← emit RA message
└─ ?__EnsureRmDeferred_534
     └─ >__TransitionToRmDeferred_536
          ├─ OnDefer_537
          ├─ transition RM → DEFERRED
          └─ !_Emit_RD_545              ← emit RD message
```

`a_EvaluatePriority_520` becomes the priority call-out point
(`EvaluateCasePriority`): SUCCESS engages, FAILURE defers, and the default
returns SUCCESS. It MUST NOT return RUNNING for "evaluation pending"
(EDF-04-002, ASK-01-003; `BTBridge.execute_tree` cannot host it). A judgment a
local capability can answer is a call-out point answered within the tick; one
that needs another actor's decision is a protocol ask, so the node emits the ask
and terminates (`notes/protocol-asks.md`, ADR-0080).

### How to Locate a New Behavior in the Canonical Tree

1. **Find the canonical subtree path** in `vultron-bt.txt` by node name (e.g.
   `?_RMPrioritizeBt_505`).
2. **Check whether it is a child of the triggering subtree.** If yes, it MUST
   be a BT subtree, not procedural code.
3. **Identify fuzzer nodes** (`z_` prefix or no prefix) on the path. Each is a
   call-out point: implement it as a leaf whose backend can be swapped without
   changing the tree (`notes/call-out-configuration.md`; catalog in
   `docs/developer/reference/bt-fuzzer/index.md`).
4. **Implement as a shared subtree factory** (e.g.
   `create_prioritize_subtree()`) so every place the canonical tree reuses it
   instantiates the same subtree.
5. **Document divergence**: if the prototype skips or reshapes a branch, say why
   in a comment and file an issue.

### Anti-Pattern Reference

#### DO NOT: post-BT procedural cascade

Calling a use case from `execute()` after the tree succeeds (e.g. running
`SvcEngageCaseUseCase` once validation returns SUCCESS) violates BT-06-006.
Compose the cascade as a child subtree (validate subtree, then
`create_prioritize_subtree`, under one Sequence) so the whole behavior is
visible by reading the tree.

#### BT-IDM-01: BT node calling a use case

A BT node's `update()` MUST NOT instantiate or call a use case. Use cases
*create* BTs; a node calling one builds a BT→UseCase→BT chain that cannot be
audited or preempted. Model the multi-step workflow as a child subtree of the
current tree (BT-06-001, BT-06-006).

#### BT-IDM-02: BT node importing from use-case modules

BT nodes in `vultron/core/behaviors/` MUST NOT import from
`vultron/core/use_cases/`; the dependency runs `use_cases/ → behaviors/` only.
A helper needed by both layers moves to a shared module (e.g.
`vultron/core/use_cases/_helpers` or a domain-model method).

#### BT-IDM-03: God BT nodes

A leaf node's `update()` SHOULD NOT exceed ~20–30 lines of logic; complexity
belongs in tree *structure*. Smell signals:

- more than 3–4 responsibilities (read, validate, create, persist, broadcast)
- multiple `dl.save()` calls in one `update()`
- boolean constructor parameters (`advance_to_accepted=True`) that silently
  activate optional branches
- internal `if/else` chains that should be `Sequence`/`Selector` children

Fix: decompose into a named subtree of single-responsibility leaves; the
subtree factory becomes the visible documentation of the workflow (BTND-02-001;
`notes/bt-design-patterns.md`).
