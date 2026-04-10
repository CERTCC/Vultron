# Canonical CVD Protocol Behavior Tree Reference

## Purpose

This note documents the **canonical CVD Protocol Behavior Tree** — the
authoritative definition of what Vultron does at the domain level. It
captures the "trunk-removed branches" mental model, provides an annotated
structural overview, maps canonical subtrees to current use cases, and
gives implementation guidance for locating new behaviors before coding them.

**Source**: `vultron-bt.txt` (full tree dump from the simulation engine),
`docs/topics/behavior_logic/` (narrative documentation per subtree),
`vultron/bt/` (simulation implementation, do NOT modify).

---

## The Trunk-Removed Branches Model

The Vultron simulation runs one large `CvdProtocolRoot` tree continuously,
ticking through all branches on every cycle. The prototype cannot do this
— it is event-driven, receiving one ActivityStreams message at a time.

The solution: **remove the trunk, keep the branches**.

Each use case in `vultron/core/use_cases/` corresponds to a named subtree
in the canonical BT. When an external event (HTTP message, trigger API call)
arrives, the dispatcher activates the matching subtree as a py_trees BT.
The branch executes to completion, exactly as it would if the full tree had
ticked down to it.

```text
Canonical tree:          Prototype:
CvdProtocolRoot          (trunk removed)
  ├─ ReceiveMessages ──►  CreateReportReceivedUseCase → __HandleRs_51 subtree
  │    └─ HandleRS  ──►   ValidateReportUseCase       → RMValidateBt_416 subtree
  │    └─ HandleEP  ──►   ProposeEmbargoReceivedUseCase → __HandleEp_135 subtree
  └─ ReportMgmtBt ──►    SvcEngageCaseUseCase         → RMPrioritizeBt_505 subtree
       └─ RmValid        SvcDeferCaseUseCase           → RMPrioritizeBt_505 subtree
            └─ Prioritize
```

**Why this matters**: When adding a cascade (A triggers B), check the
canonical tree. If B is a *child* of A in the canonical tree, B must be a
BT subtree within A's use-case BT — not a procedural call after `bt.run()`
returns. The tree structure IS the documentation. Anything outside the tree
is invisible to analysis and audit.

---

## Node Symbol Legend

The canonical BT uses prefix symbols to identify node types:

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
| `z`    | Fuzzer node (human/external input stub) | replaced by real integration |
| `L->`  | Last child of parent | (same types as above) |

---

## Top-Level Structure

```text
CvdProtocolRoot (Sequence)
├─ Snapshot                     # capture current state
├─ DiscoverVulnerabilityBt      # finder role: find/receive vuln
├─ ReceiveMessagesBt            # process inbound message queue
├─ ReportManagementBt           # RM state machine (non-message-driven)
├─ EmbargoManagementBt          # EM state machine (non-message-driven)
└─ CaseStateBt                  # CS state machine (non-message-driven)
```

The prototype maps these five branches to use cases. The first three
(Snapshot, DiscoverVuln, ReceiveMessages) are reactive; the last two plus
ReportManagementBt are autonomous/trigger behaviors.

---

## Subtree Map: Canonical BT → Use Cases

### Message Receipt: ReceiveMessagesBt (lines 26–410 in vultron-bt.txt)

The canonical tree dispatches on message type inside
`?__HandleMessage_36`. Each message type handler is a subtree:

| Canonical subtree | Message type | Current use case |
|---|---|---|
| `>__HandleRs_51` | RS (Report Submit) | `SubmitReportReceivedUseCase` |
| `>_ProcessRMMessagesBt_37` + `>__HandleRs_51` | RS inbound | `SubmitReportReceivedUseCase` |
| `>_ProcessEMMessagesBt_78` + `>__HandleEp_135` | EP (Embargo Propose) | `ProposeEmbargoReceivedUseCase` |
| `>_ProcessEMMessagesBt_78` + `>__HandleEr_113` | ER (Embargo Revise) | `ReviseEmbargoReceivedUseCase` |
| `>_ProcessEMMessagesBt_78` + `>__HandleEa_148` | EA (Embargo Accept) | `AcceptEmbargoReceivedUseCase` |
| `>_ProcessEMMessagesBt_78` + `>__HandleEt_98` | ET (Embargo Terminate) | `TerminateEmbargoReceivedUseCase` |
| `>_ProcessCSMessagesBt_277` | CV/CF/CD/CP/CX messages | CS-state use cases |

### Report Management State Machine: ReportManagementBt (lines 411–940)

The RM state machine drives autonomous behavior once a report is received.
Sub-trees by RM state:

| Canonical subtree | RM state trigger | Current use case |
|---|---|---|
| `>_RmReceived_414` + `?_RMValidateBt_416` | RM=RECEIVED → validate | `SvcValidateReportUseCase` / `ValidateCaseUseCase` |
| `>__ValidationSequence_425` → `>__ValidateReport_431` | validate → RM.VALID | validate BT (validate_tree.py) |
| `>__InvalidateReport_440` | validate → RM.INVALID | validate BT failure path |
| `>_RmValid_503` + `?_RMPrioritizeBt_505` | RM=VALID → prioritize | `SvcEngageCaseUseCase` / `SvcDeferCaseUseCase` |
| `>__TransitionToRmAccepted_524` | prioritize → RM.ACCEPTED | `SvcEngageCaseUseCase` (engage BT) |
| `>__TransitionToRmDeferred_536` | prioritize → RM.DEFERRED | `SvcDeferCaseUseCase` (defer BT) |
| `?_RMCloseBt_451/549/613` + `>__ReportClosureSequence_453` | RM=VALID/DEFERRED/ACCEPTED → close | `SvcCloseReportUseCase` |

**Critical**: In the canonical tree, `?_RMValidateBt_416` and
`?_RMPrioritizeBt_505` are parent→child. The validate subtree runs, then
the prioritize subtree runs as the next step in the same RM sequence. This
means **the validate→prioritize (engage/defer) cascade MUST be expressed as
a BT subtree**, not as a procedural call after validation succeeds.

### Embargo Management State Machine: EmbargoManagementBt (lines 940+)

| Canonical subtree | Trigger | Current use case |
|---|---|---|
| `?_EMProposeBt` | EM=NONE → propose | `SvcProposeEmbargoUseCase` |
| `?_EMEvalBt` | EM=PROPOSED → evaluate | embargo evaluation BT |
| `?_EMRevise` | EM=ACTIVE → revise | `SvcReviseEmbargoUseCase` |
| `?_EMTerminateBt` | EM=ACTIVE → terminate | `SvcTerminateEmbargoUseCase` |

---

## The Prioritize Subtree in Detail

The validate → engage/defer cascade is one of the most commonly
misimplemented patterns. The canonical structure is:

```text
?_RMPrioritizeBt_505 (Selector)
├─ >__ConsiderGatheringMorePrioritizationInfo_506
│    └─ skip if already DEFERRED or ACCEPTED
├─ >__DecideIfFurtherActionNeeded_515 (Sequence)
│    ├─ check RM in VALID/DEFERRED/ACCEPTED
│    ├─ a_EvaluatePriority_520          ← fuzzer: SSVC or other evaluator
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

`a_EvaluatePriority_520` is a fuzzer node — a stub for real-world
prioritization logic. In the prototype this becomes the
**priority-check node** described in IDEA-26041004: a node that returns
SUCCESS (engage), FAILURE (defer), or RUNNING (evaluation pending). The
default implementation returns SUCCESS to preserve current demo behavior.

This subtree MUST be a child of the validate BT (or its parent), not a
procedural function called after `bt.run()` returns.

---

## How to Locate a New Behavior in the Canonical Tree

When implementing a new cascade, state transition, or downstream behavior:

1. **Find the canonical subtree path** in `vultron-bt.txt`. Use the node
   names (e.g., `?_RMPrioritizeBt_505`) to locate the right section.
2. **Check whether it is a child of the triggering subtree** in the
   canonical tree. If yes → it MUST be a BT subtree, not procedural code.
3. **Identify any fuzzer nodes** (`z_` prefix) in the path. These are
   integration points where real logic (human, AI, external system) must
   replace the stub. In the prototype, implement as a leaf node that can
   be replaced without changing the tree structure.
4. **Implement as a shared subtree factory** (e.g.,
   `create_prioritize_subtree()`) so the same subtree can be instantiated
   anywhere the canonical tree reuses it.
5. **Document divergence**: if the prototype diverges from the canonical
   structure (e.g., skips a branch that requires human input), add a
   comment explaining why and file a tech debt item.

---

## Key Fuzzer Nodes: Future Integration Points

Fuzzer nodes in the canonical BT represent the planned extension points for
the Vultron system. Each one is a location where real-world logic will
eventually replace the simulation stub. See `notes/bt-fuzzer-nodes.md`
for the full inventory.

Highest-priority fuzzer nodes for the prototype:

| Node | Location | Real-world replacement |
|---|---|---|
| `a_EvaluatePriority_520` | RMPrioritizeBt | SSVC evaluator, policy engine, or simple default |
| `z_EvaluateReportCredibility_429` | RMValidateBt | Report credibility check (reporter trust, content check) |
| `z_EvaluateReportValidity_430` | RMValidateBt | Technical validity assessment |
| `z_EnoughPrioritizationInfo_511` | RMPrioritizeBt | Data sufficiency check before prioritization |

---

## Anti-Pattern Reference

### DO NOT: post-BT procedural cascade

```python
# BAD — the engage/defer decision is invisible outside the BT
def execute(self) -> None:
    result = bridge.execute_with_setup(validate_tree, actor_id=...)
    if result.status == Status.SUCCESS:
        SvcEngageCaseUseCase(self._dl, ...).execute()  # ← ANTI-PATTERN
```

This pattern was used in `_auto_engage()` in `received/case.py` and
`triggers/report.py` (D5-7-BTFIX-1). It violates BT-06-006.

### DO: cascade as BT subtree

```python
# GOOD — engage/defer is a child subtree of the validate tree
def create_validate_and_prioritize_tree(report_id, offer_id):
    validate_subtree = create_validate_report_subtree(report_id, offer_id)
    prioritize_subtree = create_prioritize_subtree(report_id)
    root = py_trees.composites.Sequence(
        name="ValidateAndPrioritize",
        memory=False,
        children=[validate_subtree, prioritize_subtree],
    )
    return root
```

The full behavior — validate then prioritize (engage or defer) — is visible
by reading the tree. No domain logic lives in `execute()`.

---

## Related

- `vultron-bt.txt` — full canonical BT dump from the simulation
- `docs/topics/behavior_logic/` — narrative documentation per subtree
- `vultron/bt/` — simulation implementation (read-only reference)
- `notes/bt-integration.md` — py_trees integration design decisions
- `notes/use-case-behavior-trees.md` — use case + BT layering model
- `notes/protocol-event-cascades.md` — cascade gap analysis
- `notes/bt-fuzzer-nodes.md` — fuzzer node inventory (integration points)
- `specs/behavior-tree-integration.md` — BT requirements (BT-06-005,
  BT-06-006)
