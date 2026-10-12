---
title: Use Cases, Domain Logic, and Behavior Trees
status: active
kind: guidance
description: >
  Where domain logic belongs: inside the behavior tree, never in a use case's
  execute(). Every use-case tree is a subtree of the canonical CVD tree.
related_specs:
  - specs/code-style.yaml
  - specs/bt-composability.yaml
  - specs/behavior-tree-integration.yaml
  - specs/use-case-organization.yaml
  - specs/case-ledger-processing.yaml
related_notes:
  - notes/bt-integration.md
  - notes/bt-composability.md
  - notes/bt-canonical-reference.md
  - notes/use-case-protocol.md
  - notes/event-driven-control-flow.md
relevant_packages:
  - vultron/core/use_cases
  - vultron/core/behaviors
---

# Use Cases, Domain Logic, and Behavior Trees

The layering itself (adapter → dispatcher → use case → tree → domain model) is
described in `docs/reference/code/hexagonal_architecture.md` § "Use cases and
behavior trees". This note holds the rules for changing it.

---

## Core Principle: The Tree Is the Documentation

If a protocol-observable action — emitting an activity, transitioning RM/EM/CS
state, creating a domain object, cascading to a downstream behavior — is not a
BT node or subtree, analysis, audit, and explainability tools cannot see it. The
enforceable form is BTC-03-001 (and BT-06-001).

### Procedural Glue vs. Domain Logic

A use case's `execute()` MAY contain infrastructure glue only:

- build the tree
- set up the blackboard from the request
- run it with `BTBridge.execute_with_setup()`
- read the result and return the `HandlerResult` or `TriggerResult`

Nothing else domain-significant lives outside the tree, and `execute()` never
writes to the DataLayer, even through a helper (CLP-10-020).

### Anti-Pattern: a cascade after the tree

```python
def execute(self) -> HandlerResult:
    bridge.execute_with_setup(self._dl, bt, bb)
    # WRONG: the validate → engage cascade is invisible to the tree
    if bt.status == Status.SUCCESS:
        SvcEngageCaseUseCase(self._dl, engage_event).execute()
    return HandlerResult.applied()
```

Make the downstream behavior a child subtree of the tree that causes it, so the
cascade runs inside one `execute_with_setup()` call and appears in the tree
structure. Class names here are illustrative.

---

## Every Use-Case Tree Is a Canonical Subtree

A use-case BT is a branch of the canonical CVD protocol BT with the
continuous-tick trunk removed, triggered by an external event instead (BT-06-002).
A use-case tree that diverges from its canonical subtree breaks the link between
the documented process and the implemented one, so a divergence MUST be justified
in an ADR or note.

Before building a new behavior, find where it sits in the canonical tree: see
`notes/bt-canonical-reference.md` for the subtree map and
`notes/bt-integration.md` for the trunk-removed branches model.
