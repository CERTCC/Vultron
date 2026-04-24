---
title: Behavior Tree Design Patterns
status: active
description: >
  Idiomatic BT construction patterns from Colledanchise & Ögren; applies to
  simulation and prototype BT implementations.
related_specs:
  - specs/behavior-tree-integration.md
  - specs/behavior-tree-node-design.md
related_notes:
  - notes/bt-composability.md
  - notes/bt-integration.md
  - notes/bt-reusability.md
relevant_packages:
  - py_trees
---

# Behavior Tree Design Patterns

## Overview

This note documents idiomatic BT construction patterns drawn from
*Behavior Trees in Robotics and AI* (Colledanchise & Ögren,
arXiv:1709.00084v6, 2018). These patterns apply to both the simulation BT
engine in `vultron/bt/` and the prototype py_trees implementation in
`vultron/core/behaviors/`.

**Canonical source**: Colledanchise, M. & Ögren, P. (2018). *Behavior Trees
in Robotics and AI: An Introduction*. arXiv:1709.00084v6.
Sections referenced: Chapter "Design Principles" and Chapter "Analysis of
Efficiency, Safety, and Robustness".

**Formal requirements cross-referenced here**:

- `specs/behavior-tree-node-design.md` — `BTND-06-*`
- `specs/behavior-tree-integration.md` — `BT-06-003`, `BT-06-004`

**See also**:

- `notes/bt-integration.md` — Vultron-specific architecture decisions
- `notes/bt-composability.md` — fractal composability and the
  trunk-removed-branches model
- `notes/bt-reusability.md` — anti-patterns and node design checklist

---

## Pattern 1: Implicit Sequences (Goal-first Fallback)

**The dominant pattern in the Vultron simulator.** Use it whenever a
stateful operation should be idempotent and reactive.

### Structure

```text
Fallback
  ├─ GoalAlreadyAchieved   ← condition: return SUCCESS if already done
  └─ Sequence
       ├─ Precondition1    ← guard: must hold before action
       ├─ Precondition2
       └─ Action           ← performs the state transition
```

### How it works

The Fallback first checks whether the goal state is already satisfied.
If so, it returns `SUCCESS` immediately without executing the action.
Only if the goal is *not* yet achieved does it enter the Sequence, which
checks all preconditions before attempting the action.

This makes every stateful node **automatically idempotent**: re-ticking an
already-satisfied goal costs only a cheap condition check.

### Simulator example

```python
# vultron/bt/report_management/_behaviors/validate_report.py

RMValidateBt = fallback_node(
    "RMValidateBt",
    "Validate the report (idempotent).",
    RMinStateValid,        # goal already achieved? → SUCCESS
    _HandleRmI,            # recover from INVALID
    _ValidationSequence,   # attempt validation
    _InvalidateReport,     # fallback: mark invalid
)
```

`RMinStateValid` is the postcondition check. The remaining children execute
only when the report is not yet valid.

### Prototype example (py_trees)

```python
import py_trees

goal_check = ReportAlreadyValid(name="ReportAlreadyValid", dl=dl)
do_validate = py_trees.composites.Sequence(
    name="ValidateSequence", memory=False
)
do_validate.add_children([
    ReportInReceivedOrInvalidState(name="InValidatableState", dl=dl),
    EvaluateCredibility(name="EvaluateCredibility", dl=dl),
    TransitionToValid(name="TransitionToValid", dl=dl),
])

root = py_trees.composites.Selector(name="ValidateReport", memory=False)
root.add_children([goal_check, do_validate])
```

### When to use

- **Always**, for any node whose purpose is to achieve a state transition.
- Whenever the same tree may be ticked multiple times for the same object.
- Whenever the goal may already be satisfied (e.g., deduplication,
  idempotent protocol steps).

### When NOT to use

- Pure condition-check leaves (conditions never return `RUNNING`; they need
  no wrapper).
- One-shot fire-and-forget actions where re-execution is intentional and
  harmless (rare in Vultron).

**Formal requirement**: `BTND-06-001`

---

## Pattern 2: Explicit Success Conditions

**Improves readability** by making the success condition of each action
explicit in the tree rather than buried in the action's implementation.

### Structure

```text
Sequence
  ├─ Fallback
  │    ├─ DoorIsUnlocked   ← condition: skip action if already done
  │    └─ UnlockDoor       ← action
  ├─ Fallback
  │    ├─ DoorIsOpen
  │    └─ OpenDoor
  └─ PassThroughDoor
```

Each action is paired with its success condition via a Fallback. If the
condition is already satisfied the action is skipped; if the condition is not
satisfied the action is attempted.

### How it differs from Pattern 1

Pattern 1 puts the *goal* check at the *root* of the Fallback (one check
for the whole composite operation). Pattern 2 puts an *intermediate*
condition check before each individual action in the Sequence.

Patterns 1 and 2 are often combined: the outer Fallback provides
goal-first idempotency; the inner pairs provide per-step idempotency.

### When to use

- When individual steps in a Sequence can independently be already
  complete (e.g., a multi-step initialization that may have partially
  succeeded on a previous tick).
- When the action implementation does not handle the "already done" case
  internally and you want to make that invariant explicit in the tree.
- As a stepping stone before refactoring to Pattern 1.

### When NOT to use

- When the action is already naturally idempotent (returns `SUCCESS`
  immediately if its postcondition holds).
- When the precondition and success condition are identical (merge into
  Pattern 1 instead).

**Formal requirement**: `BTND-06-002`

---

## Pattern 3: PPA (Postcondition–Precondition–Action)

**The fundamental unit cell of idiomatic BT design** from
Colledanchise & Ögren. Every stateful leaf-level operation should have this
shape.

### Structure

```text
Fallback                          ← PPA root
  ├─ Postcondition   (C)          ← goal check: already achieved?
  └─ Sequence
       ├─ Precondition1  (C_1)    ← guard: required before action
       ├─ Precondition2  (C_2)
       └─ Action          (A)     ← achieves postcondition C
```

Formally: `Fallback(C, Sequence(C_1, …, C_n, A))` where `A` achieves `C`
when all `C_i` hold.

### Relationship to Pattern 1

Pattern 1 is the implicit-sequence application of PPA at the *composite*
level. PPA names the structure explicitly and makes it the unit for
back-chaining (Pattern 4).

### Vultron usage

Every BT node that performs a protocol state transition (RM, EM, CS state
machine update, emitting an AS2 activity) SHOULD follow PPA structure:

```python
# Postcondition: RM is already VALID → SUCCESS
# Precondition:  RM is in RECEIVED or INVALID
# Action:        transition RM to VALID, emit RV

validate_ppa = fallback_node(
    "ValidatePPA",
    "PPA: RM → VALID",
    RMinStateValid,                       # postcondition
    sequence_node(
        "_DoValidate",
        "Preconditions + action",
        RMinStateReceivedOrInvalid,       # precondition
        EvaluateReportValidity,           # action step 1
        q_rm_to_V,                        # action step 2: transition
        EmitRV,                           # action step 3: notify
    ),
)
```

### When to use

- For every node that performs a meaningful state transition in the
  protocol state machines (RM, EM, CS).
- When designing new subtrees from scratch — start with PPA as the
  template and expand from there.

**Formal requirement**: `BTND-06-003`

---

## Pattern 4: Back-chaining

**A systematic method for constructing deliberative, goal-directed BTs.**
Back-chaining produces the implicit sequence pattern recursively.

### Algorithm (from Colledanchise & Ögren)

1. Start with a single goal condition `C` (a Condition leaf).
2. Find a PPA `Fallback(C, Sequence(C_1, …, C_n, A))` whose postcondition
   is `C`.
3. Replace the standalone `C` leaf with the full PPA.
4. Repeat: for any precondition `C_i` that may fail, find a PPA whose
   postcondition is `C_i` and substitute it in.
5. Iterate until all leaf conditions are either trivially satisfied or
   correspond to irreducible primitive actions.

### Result

The resulting tree:

- First checks whether the goal is already achieved.
- If not, checks whether all preconditions for the primary action hold.
- For each failing precondition, recursively attempts to achieve it.
- Is fully reactive: if any intermediate state is undone, the tree
  automatically retries the corresponding sub-goal.

### When to use

- When designing a multi-step workflow where each step has its own
  preconditions (e.g., negotiate embargo requires active case, active case
  requires validated report, validated report requires received report).
- When you want the tree to automatically recover from partial progress or
  external interference.

### When NOT to use

- When steps are strictly one-shot and should not auto-retry on failure.
- When preconditions can never be achieved by the agent (human-in-the-loop
  decisions, external approvals) — model these as terminal Failure leaves
  instead of back-chain targets.

**Formal requirement**: `BTND-06-004`

---

## Pattern 5: Safety via Sequence (Guard Nodes)

**Use a Sequence with a safety condition as its first child to prevent
execution when the system is in an unsafe state.**

### Structure

```text
Sequence
  ├─ SafetyCondition     ← returns FAILURE if unsafe → whole Sequence fails
  └─ MainBehavior        ← only executes if safety condition passes
```

### How it works

The Sequence short-circuits: `MainBehavior` is never reached if
`SafetyCondition` returns `FAILURE`. This is the BT equivalent of a
precondition guard on a dangerous or irreversible operation.

### Hysteresis variant

To avoid chattering (rapidly switching between safe/unsafe states),
pair the safety check with a hysteresis condition that requires a more
conservative threshold to re-enter the safe state:

```text
Sequence
  ├─ BatteryAbove20Percent    ← entry guard: below 20% → recharge
  └─ MainTask

# With hysteresis:
Fallback
  ├─ BatteryAbove100Percent   ← exit guard: keep charging until 100%
  └─ Sequence
       ├─ BatteryAbove20Percent
       └─ MainTask
```

### Vultron application

Safety guards appear throughout the simulator wherever state machine
preconditions must hold before a protocol action is taken:

```python
# Only propose embargo if not already in an active embargo
_MaybePropose = sequence_node(
    "MaybePropose",
    "Propose embargo only if none is active.",
    EMinStateNoneOrExited,   # ← safety / precondition guard
    SelectEmbargoOfferTerms,
    q_em_to_P,
    EmitEP,
)
```

### When to use

- **Always** before any irreversible protocol action (e.g., state
  transitions that cannot be undone, emitting disclosure activities,
  expiring an embargo).
- When an action should only run in a specific bounded state range (add
  both entry and exit hysteresis conditions to prevent chattering).
- As the first child of any Sequence in a multi-party protocol context,
  where external events may change state between ticks.

**Formal requirement**: `BTND-06-005`

---

## Pattern 6: Memory Nodes

**Use memory (non-reactive) composites only in fully deterministic,
non-reactive environments.**

### What memory nodes do

A `Sequence(memory=True)` or `Fallback(memory=True)` remembers which child
succeeded last and resumes from that child on the next tick, rather than
re-evaluating from the first child every time.

This **disables reactivity**: once a child has succeeded and is "remembered",
it will not be re-checked even if the world state changes.

### When it is appropriate

Colledanchise & Ögren limit memory nodes to environments that are:

1. **Fully predictable in space and time** — no external actor can undo
   a sub-behavior's outcome.
2. **Closed-loop is unnecessary** — the agent does not need to react to
   unexpected state changes mid-execution.
3. **Human-supervised** — the execution environment is controlled (e.g.,
   an industrial robot line where operators pause the system before making
   changes).

### Why memory nodes are almost never appropriate in Vultron

Vultron operates in a **multi-party, adversarial, open world**:

- Another party may withdraw a proposal, change embargo terms, or disclose
  while a handler is executing.
- The very purpose of protocol state machines (RM, EM, CS) is to track
  reactive transitions driven by external messages.
- Single-shot BT execution (one message → one tree run) already provides
  transaction semantics without needing memory.

**Default**: Use `memory=False` for all composites unless you can
explicitly justify a closed-loop, externally-controlled context.

```python
# Correct: non-memory Sequence — re-evaluates all children each tick
py_trees.composites.Sequence(name="MySeq", memory=False)

# Use with caution: memory Sequence — skips already-succeeded children
py_trees.composites.Sequence(name="MySeq", memory=True)
```

**Formal requirement**: `BTND-06-006`

---

## Pattern 7: Granularity (Leaf vs. Subtree)

**Deciding when to represent a behavior as a single leaf action versus
decomposing it into a subtree of conditions and finer-grained actions.**

### Guideline: use a leaf when

- The sub-parts of the behavior are **always used together** in exactly
  this combination — decomposing adds no reuse value.
- The operation is **atomic from the protocol's perspective**: it either
  fully succeeds or fully fails, with no intermediate states that matter.
- **Reactivity within the operation is not needed**: no external event can
  invalidate a half-completed step.

Example: `q_rm_to_V` (transition RM state to VALID) is a leaf. It is a
single atomic state update; there is no sub-step worth exposing.

### Guideline: use a subtree when

- Sub-parts are **reusable in other combinations** elsewhere in the tree.
- **Reactivity matters**: an external event mid-execution should be able
  to interrupt and redirect the behavior.
- The operation involves **multiple distinguishable intermediate states**
  (e.g., check-then-act, acquire-then-use-then-release).
- **Auditability**: making the internal steps visible in the tree aids
  reasoning, debugging, and testing.

Example: `RMValidateBt` (validate a report) is a subtree. Credibility
evaluation, validity evaluation, and state transition are separate concerns
that may each need to be retried, and the intermediate RM states
(RECEIVED → INVALID → VALID) are protocol-observable.

### The BT-06-004 rule

`specs/behavior-tree-integration.md` BT-06-004 states: "Any node that
contains complicated business logic is a candidate for refactoring into its
own sub-tree." Apply this rule proactively: if an `update()` method is
doing more than one logical check or one state update, it is probably a
subtree in disguise.

### Vultron-specific guidance

- **State-machine condition checks** (is RM in state X?) are always leaves.
- **State-machine transitions** (RM → X) are always leaves.
- **Message emission** (EmitRV, EmitEP) are always leaves.
- **Composed workflows** (validate report, propose embargo, accept
  invitation) are always subtrees.
- **Human-in-the-loop decisions** (evaluate credibility, accept embargo
  terms) are leaves backed by fuzzer nodes in simulation and by domain
  logic / DataLayer queries in the prototype.

**Formal requirement**: `BTND-06-007`

---

## Pattern Interaction Summary

| Pattern | Keyword | Strength | Primary use in Vultron |
|---|---|---|---|
| Implicit Sequences | Goal-first Fallback | SHOULD | All stateful BT nodes |
| Explicit Success Conditions | Per-step condition pair | SHOULD | Multi-step inits |
| PPA | Postcondition–Precondition–Action | SHOULD | Every state transition |
| Back-chaining | Recursive PPA expansion | MAY | Multi-step deliberative trees |
| Safety via Sequence | Guard node first | SHOULD | Before irreversible actions |
| Memory Nodes | Non-reactive composites | MAY (with caution) | Closed-loop only |
| Granularity | Leaf vs subtree | SHOULD | All new node design |

The three SHOULD patterns (Implicit Sequences, PPA, Safety) are not
alternatives — they compose together. A typical Vultron BT node looks like:

```text
Fallback                             ← Pattern 1 (goal-first)
  ├─ GoalCondition                   ← postcondition of PPA
  └─ Sequence                        ← Pattern 3 (PPA body) + Pattern 5
       ├─ SafetyGuard                ← Pattern 5 (guard)
       ├─ PreconditionCheck          ← PPA precondition
       └─ Action                     ← PPA action
```
