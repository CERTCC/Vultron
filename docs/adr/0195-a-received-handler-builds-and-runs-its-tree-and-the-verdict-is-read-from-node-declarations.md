---
status: proposed
date: 2026-11-13
created: 2026-11-13
updated: 2026-11-13
revision: 1
deciders: Allen D. Householder
consulted: Vultron maintainers
informed: Vultron implementers
stakeholder_type: [project-contributor]
---

# A Received Handler Builds and Runs Its Tree, and the Verdict Is Read From Node Declarations

## Context and Problem Statement

A received use case runs one behavior tree per delivery (CLP-10-005).
The tree's root status says only whether it succeeded, and a handler must report more than that: a benign no-op is `SKIPPED`, a refused assertion is `REFUSED`, and a programming error is neither (HP-01-003, HP-01-014).

Each handler used to wire the bridge, resolve the receiving actor, run the tree, and then pick its reading of the result from a set of per-guard helpers.
A guard that detects a repeat already said so on itself, through `ReportsIdempotentRepeat`, and the refusal stage already read that declaration generically.
The handlers did not: each one had to remember which of nine wrappers its tree needed.
A handler that picked the wrong wrapper, or none, reported a harmless redelivery as `REFUSED`.
"Succeeded but changed nothing" was read the same way, by hand, in a few handlers.

**Where is a received delivery's verdict decided, and from what?**

## Decision Drivers

- The tree carries the protocol logic, so a verdict should come from what the tree's nodes recorded, not from Python a handler adds around the run.
- A new guard should get the right verdict without every handler that uses it learning about it.
- Tree tests should check a tree's verdict without importing a use case.
- The order of the readings matters: a door's answer comes first, then a repeat or a no-op, then the general refusal.

## Considered Options

- One runner beside the received tree that reads node declarations
- Keep the per-guard wrappers in each handler
- Have every tree end in a node that writes the verdict to the blackboard

## Decision Outcome

Chosen option: "One runner beside the received tree that reads node declarations", because it reads the declarations the guards already make, keeps every reading in one place, and leaves the tree as the only place a protocol decision is made.

A received use case only builds its tree and hands it to the runner.
The runner wires the bridge and the ports, runs the tree once as the receiving actor (BT-17-005), and reads the verdict from node status, declared flags and failure reasons only.
Nothing in the runner reads or writes the DataLayer before or after the run.
A verdict that needs a fact the tree did not record gets a node that records it, not code in the runner.

Two node declarations carry the non-default verdicts:

- A guard whose failure is an idempotent repeat declares it (`ReportsIdempotentRepeat`), and the runner reports `SKIPPED` when such a guard is on the failure chain.
- A node whose success means the run had nothing to change declares it (`ReportsNoChange`), and the runner reports `SKIPPED` instead of `APPLIED`.

A handler that owes a reading no declaration expresses passes an optional reader.
The reader receives only the finished run: the tree, the bridge's result and the handler's label.
It gets no DataLayer, no port and no request.

The readings keep one order: the doors and the sender sequence stage, then the handler's reader, then a declared no-change or repeat, then the general refusal.
The reader comes before the declarations so that a handler reading that names its own answer for a run wins.
A reader returns no answer for any run it does not read, and the declarations then decide.

### Consequences

- Good, because a guard that declares a repeat is reported `SKIPPED` in every tree it joins, with no handler change.
- Good, because a handler's `execute()` shrinks to building a tree and running it.
- Good, because tree tests read verdicts through `core/behaviors` alone.
- Bad, because a few readings that read the DataLayer around the run stay in the use cases until each gets a node or a door of its own.
- Neutral, because the reader is a deliberate escape hatch: a reading that recurs across handlers should become a node declaration.

## Validation

- Tree tests in `test/core/behaviors/case/test_received_run.py` check each reading and its order without importing a use case.
- `test/architecture/test_received_side_actor_id.py` checks that no received use case calls the bridge's `execute_with_setup` and that the runner runs the tree as the resolved receiver.
- The single-tree ratchet in `test/architecture/test_single_bt_execution_received_side.py` counts a call of the runner as the delivery's one tree run.

## Pros and Cons of the Options

### One runner beside the received tree that reads node declarations

- Good, because it reuses the declaration the refusal stage already reads.
- Good, because the reading order is written once.
- Bad, because a handler-specific reading needs a reader, which a careless one could grow into logic that belongs in the tree.

### Keep the per-guard wrappers in each handler

- Good, because nothing moves.
- Bad, because each handler must pick the right wrapper, and a wrong pick misreports a redelivery as a refusal.
- Bad, because a new repeat guard needs a new wrapper and an edit to every handler that uses it.

### Have every tree end in a node that writes the verdict to the blackboard

- Good, because the verdict would be a tree output.
- Bad, because a node at the end of the tree does not run when an earlier node fails, which is exactly when the verdict matters most.
- Bad, because it duplicates what the nodes already declare on themselves.

## More Information

The use case's side of the rule, and the refusals that still read the DataLayer around the run, are tracked in issue #6394, which adds the testable requirements and the architecture test.
