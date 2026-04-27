---
title: Behavior Tree Composability Design Notes
status: active
description: >
  Vultron's fractal composability principle for behavior trees; concrete
  patterns for composing behavioral subtrees.
related_specs:
  - specs/bt-composability.md
related_notes:
  - notes/bt-integration.md
  - notes/bt-reusability.md
relevant_packages:
  - py_trees
  - vultron/bt
  - vultron/core/behaviors
---

# Behavior Tree Composability Design Notes

## Overview

This note explains Vultron's **fractal composability** principle for behavior
trees: what it means in practice, how to use the simulator as a blueprint,
and the concrete patterns agents should follow when implementing behavioral
logic in `vultron/core/behaviors/`.

**Formal requirements**: `specs/bt-composability.md` (BTC-01 through BTC-04).

**See also**:

- `notes/bt-reusability.md` — anti-patterns, parameterization guidelines,
  node design checklist
- `notes/bt-integration.md` — key design decisions, trunk-removed branches
  model, DataLayer integration
- `notes/vultron-bt.txt` — full canonical simulation tree dump
- `vultron/bt/` — simulation source code (read-only reference)

---

## The Fractal Composability Principle

### What "Fractal" Means Here

**Fractal composability** means the same compose-and-reuse rule applies at
*every depth* of the behavior tree — there is no depth at which reuse stops
being required.

At the top level:

```text
CvdProtocolRoot
  ├─ DiscoverVulnerabilityBt    ← reusable subtree
  ├─ ReceiveMessagesBt          ← reusable subtree
  ├─ ReportManagementBt         ← reusable subtree
  └─ EmbargoManagementBt        ← reusable subtree
```

Each of those subtrees is itself composed of reusable sub-subtrees:

```text
EmbargoManagementBt
  ├─ TerminateEmbargoBt         ← reusable subtree
  ├─ ProposeEmbargoBt           ← reusable subtree
  └─ ...
```

And each of *those* is composed of finer-grained pieces:

```text
TerminateEmbargoBt
  ├─ EMinStateNoneOrExited      ← condition leaf
  ├─ ConsiderAbandoningProposed ← subtree
  └─ ConsiderTerminatingActive  ← subtree
```

**The key insight**: `TerminateEmbargoBt` is BOTH a standalone behavior (it
can be instantiated and run by itself) AND a composable child of
`EmbargoManagementBt`. This dual role — standalone entry point and composable
child — is the fractal property.

---

## Clarifying "Trunk-Removed Branches"

### What the Metaphor Does Mean

The **canonical simulation BT** is a single continuously-ticking tree:

```text
CvdProtocolRoot → [ticks on every cycle]
```

The prototype can't replicate this (it receives discrete messages). The
solution is to *remove the trunk* — the continuous-ticking coordinator — and
activate individual branches when triggered by incoming messages.

When a `ProposeEmbargo` activity arrives, the prototype runs
`EmProposeEmbargoReceivedUseCase`, which invokes the `HandleEpBt` subtree.
That subtree is a "branch" of the canonical tree, running to completion and
returning.

### What the Metaphor Does NOT Mean

**Common misreading**: "trunk-removed branches" means go to a fixed depth in
the tree (e.g., the immediate children of `CvdProtocolRoot`) and map each to
one use case.

This is wrong. The extraction point is *the appropriate depth for the
behavior*, which varies:

- `EmbargoManagementBt` (top-level child of root) → a complex multi-behavior
  entry point, probably too coarse for a single use case
- `TerminateEmbargoBt` (child of EmbargoManagementBt) → a coherent, focused
  behavior that maps directly to a reusable subtree
- `ConsiderTerminatingActiveEmbargo` (child of TerminateEmbargoBt) →
  a finer-grained piece that composes into `TerminateEmbargoBt`

**The rule**: Extract at the depth where the behavior is coherent, reusable,
and has a natural protocol trigger — NOT at a uniform depth.

---

## Using the Simulator as a Reference

### Two Sources, Two Purposes

| Source | Purpose |
|---|---|
| `notes/vultron-bt.txt` | Navigate to the right location in the tree |
| `vultron/bt/` source code | Read the node's children and structure |

### Navigating `vultron-bt.txt`

The tree dump uses node names with a numeric suffix:

```text
|-> ?_TerminateEmbargoBt_217
|   |-> c_EMinStateNoneOrExited_218
|   |-> >_ConsiderAbandoningProposedEmbargo_219
|   L-> >_ConsiderTerminatingActiveEmbargo_201
```

Strip the underscore-number suffix to get the class name:
`TerminateEmbargoBt_217` → `TerminateEmbargoBt`.

The prefix character indicates node type:

| Prefix | Node type |
|---|---|
| `>` | Sequence (AND — all children must succeed) |
| `?` | Fallback/Selector (OR — first success wins) |
| `c` | Condition leaf |
| `a` | Action leaf |
| `!` | Decorator |
| `l` | Loop decorator |
| `^` | Invert decorator |
| `z` | Fuzzer/stub leaf |

### Finding the Class in `vultron/bt/`

Once you have a class name (e.g., `TerminateEmbargoBt`), search the source:

```bash
grep -rn "TerminateEmbargoBt" vultron/bt/ --include="*.py"
```

This gives:

```text
vultron/bt/embargo_management/behaviors.py:217:TerminateEmbargoBt = fallback_node(
```

Read the `fallback_node(...)` call to see its children — those are the
structures to replicate in `vultron/core/behaviors/`.

---

## The Class-Define, Instance-Invoke Pattern

### Why Separate Definition from Invocation

The simulator creates fresh instances at every tick because BT nodes carry
per-tick state. The prototype does the same: each time a use case needs the
behavior, it instantiates a fresh instance of the pre-defined class.

```python
# In vultron/core/behaviors/embargo/terminate.py:
class TerminateEmbargoBt(py_trees.composites.Selector):
    """Terminate the embargo if sufficient cause exists.
    
    Corresponds to TerminateEmbargoBt in vultron/bt/embargo_management/behaviors.py.
    
    Children:
      1. EMinStateNoneOrExited  — guard: already done, succeed early
      2. ConsiderAbandoningProposed — if in Proposed state with cause
      3. ConsiderTerminatingActive  — if in Active/Revise with cause
    """
    
    def __init__(self, case_id: str, dl: DataLayer) -> None:
        super().__init__(name="TerminateEmbargoBt", memory=False)
        self.add_children([
            EMinStateNoneOrExited(case_id=case_id, dl=dl),
            ConsiderAbandoningProposed(case_id=case_id, dl=dl),
            ConsiderTerminatingActive(case_id=case_id, dl=dl),
        ])
```

```python
# In vultron/core/use_cases/embargo/teardown_received.py:
class EmbargoTeardownReceivedUseCase:
    def __init__(self, dl: DataLayer, request: EmTeardownReceivedEvent) -> None:
        self._dl = dl
        self._request = request

    def execute(self) -> None:
        bb = setup_blackboard(self._request)
        
        # Instantiate the pre-defined class — fresh instance per invocation
        bt = TerminateEmbargoBt(
            case_id=self._request.case_id,
            dl=self._dl,
        )
        bridge.execute_with_setup(self._dl, bt, bb)
```

**Key**: The business logic (children, structure, conditions) lives in
`TerminateEmbargoBt`. The use case only instantiates and invokes.

---

## BT Idioms Over Procedural Code

### Why This Matters

Behavioral logic expressed as BT composites is:

- **Auditable**: anyone who can read the tree structure can understand the
  protocol behavior without reading implementation code
- **Explainable**: the tree visualizes the decision logic
- **Composable**: subtrees can be reused without understanding internals
- **Cyclomatic-complexity-friendly**: each node does one thing; complex
  if/else chains in `update()` are replaced by tree structure

### Precondition Pattern (Sequence)

When a behavior requires preconditions to be true before acting:

```python
# ❌ Procedural
def update(self) -> Status:
    if not self.is_em_active():
        return Status.FAILURE
    if not self.has_sufficient_cause():
        return Status.FAILURE
    self.transition_to_exited()
    self.emit_et()
    return Status.SUCCESS

# ✅ BT Sequence (preconditions as leading Condition children)
ConsiderTerminatingActiveEmbargo = sequence_node(
    "ConsiderTerminatingActiveEmbargo",
    "...",
    EMinStateActiveOrRevise,        # ← precondition 1
    SufficientCauseToTerminate,     # ← precondition 2
    OnEmbargoExit,                  # ← action
    TransitionToExited,             # ← action
    EmitET,                         # ← action
)
```

The Sequence version is readable as: "If active/revise AND sufficient cause,
then exit and emit."

### Fallback Pattern (Try-or-Else)

When a behavior has alternatives (try A, else B):

```python
# ❌ Procedural
def update(self) -> Status:
    if self.already_exited():
        return Status.SUCCESS      # early-out
    if self.in_proposed():
        return self.abandon()
    if self.in_active():
        return self.terminate()
    return Status.FAILURE

# ✅ BT Selector (alternatives as children)
TerminateEmbargoBt = fallback_node(
    "TerminateEmbargoBt",
    "...",
    EMinStateNoneOrExited,          # ← guard: already done → succeed
    ConsiderAbandoningProposed,     # ← alternative 1
    ConsiderTerminatingActive,      # ← alternative 2
)
```

The Selector version is readable as: "Succeed if already exited; otherwise
try abandoning proposal; otherwise try terminating active embargo."

### Expanding Complex Leaf Nodes

When a simulator leaf node (`a_` prefix) requires non-trivial logic to
implement, replace it with a subtree:

```text
# Simulator: a_PerformValidation (single leaf)

# Prototype: expand into subtree
PerformValidationBt = sequence_node(
    "PerformValidation",
    ...,
    CheckReportHasContent,         # ← condition
    CheckReportNotDuplicate,       # ← condition
    RecordValidationResult,        # ← action
    EmitRVMessage,                 # ← action
)
```

This keeps each child node simple and testable in isolation.

---

## Decision Table

| Design question | Decision | Rationale |
|---|---|---|
| Simulator lookup mandatory? | Yes — MUST check before implementing | Prevents protocol drift |
| Navigation: txt vs code? | Both — txt for position, code for structure | One-to-one class mapping |
| Structures pre-defined before use? | Yes — MUST pre-define in core/behaviors/ | Business logic stays in behaviors layer |
| Use-case inline tree construction? | MUST NOT | Use cases are dispatch glue, not logic |
| BT idioms vs procedural if/else? | BT idioms MUST be used | Auditability, composability |
| Extraction depth? | Appropriate depth for the behavior | Fractal — no fixed rule |
| Multi-site canonical behaviors? | One class, multiple instantiations | DRY; fixes apply once |
| "Trunkless branch" misreading? | NOT depth-X slicing; any depth is valid | Fractal property |
| Leaf nodes with complex logic? | Expand to subtree using BT idioms | Cyclomatic complexity, auditability |

---

## Related Reading

- `specs/bt-composability.md` — formal BTC-01 through BTC-04 requirements
- `notes/bt-reusability.md` — anti-patterns and node design checklist
- `notes/bt-integration.md` — design decisions, trunk-removed branches model
- `notes/vultron-bt.txt` — canonical simulation BT structure (full dump)
- `vultron/bt/embargo_management/behaviors.py` — TerminateEmbargoBt,
  EmbargoManagementBt (canonical reference for embargo behaviors)
- `vultron/bt/report_management/_behaviors/` — RMValidateBt, RMPrioritizeBt,
  RMCloseBt, RMDoWorkBt (canonical reference for report behaviors)
