---
title: Behavior Tree Composability and Reusability Design Notes
status: active
kind: guidance
description: >
  Vultron's fractal composability principle for behavior trees: using the
  simulator as a blueprint, defining subtrees once and instantiating them per
  use, BT idioms over procedural code, and the reusability anti-pattern
  checklist.
related_specs:
  - specs/bt-composability.yaml
  - specs/behavior-tree-integration.yaml
  - specs/behavior-tree-node-design.yaml
  - specs/configuration.yaml
related_notes:
  - notes/bt-integration.md
  - notes/bt-canonical-reference.md
  - notes/use-case-behavior-trees.md
relevant_packages:
  - py_trees
  - vultron/bt
  - vultron/core/behaviors
---

# Behavior Tree Composability and Reusability Design Notes

Formal requirements: `specs/bt-composability.yaml` (BTC-01 through BTC-04).
The trunk-removed-branches model, the node symbol legend, and how to navigate
`notes/vultron-bt.txt` are in `notes/bt-canonical-reference.md`.

---

## The Fractal Composability Principle

The same compose-and-reuse rule applies at *every depth* of the tree; there is
no depth at which reuse stops being required. `CvdProtocolRoot` is composed of
reusable subtrees (`ReceiveMessagesBt`, `EmbargoManagementBt`, …), each of
those of reusable sub-subtrees (`TerminateEmbargoBt`, `ProposeEmbargoBt`, …),
and so on down:

```text
TerminateEmbargoBt
  ├─ EMinStateNoneOrExited      ← condition leaf
  ├─ ConsiderAbandoningProposed ← subtree
  └─ ConsiderTerminatingActive  ← subtree
```

`TerminateEmbargoBt` is BOTH a standalone behavior that can run by itself AND a
composable child of `EmbargoManagementBt`. That dual role is the fractal
property. A fractal subtree:

- is a complete, meaningful behavior ("engage the case", "validate the
  report");
- can be triggered independently through a use-case entry point;
- can be composed as a child of a larger tree;
- takes **identity and role as constructor parameters**, never hard-coded
  constants.

---

## Using the Simulator as a Reference

Check the simulator before implementing a behavior (it prevents protocol
drift): `notes/vultron-bt.txt` tells you *where* the behavior sits; the
`vultron/bt/` source tells you its children and structure. For a class name,
`grep -rn "TerminateEmbargoBt" vultron/bt/` leads to e.g.
`TerminateEmbargoBt = fallback_node(...)` in
`vultron/bt/embargo_management/behaviors.py`; its children are the structure to
replicate in `vultron/core/behaviors/`.

---

## Define Once, Instantiate per Use

Pre-define each subtree in `vultron/core/behaviors/` (a factory function or
composite class) and have the use case instantiate a fresh instance per
invocation. BT nodes carry per-tick state, so instances are never shared; the
business logic (children, structure, conditions) lives in the behaviors layer,
and the use case only instantiates and invokes. Use cases MUST NOT build trees
inline. A canonical behavior used at several sites is one definition with
several instantiations, so a fix applies once.

---

## BT Idioms Over Procedural Code

Behavior expressed as BT composites is auditable, explainable, composable, and
keeps each node's `update()` simple. Replace `if/else` chains in `update()`
with structure:

- **Preconditions → Sequence**: leading Condition children, then actions.

  ```python
  ConsiderTerminatingActiveEmbargo = sequence_node(
      "ConsiderTerminatingActiveEmbargo", "...",
      EMinStateActiveOrRevise,        # precondition 1
      SufficientCauseToTerminate,     # precondition 2
      OnEmbargoExit, TransitionToExited, EmitET,   # actions
  )
  ```

- **Alternatives → Selector**: a guard that succeeds early, then each
  alternative.

  ```python
  TerminateEmbargoBt = fallback_node(
      "TerminateEmbargoBt", "...",
      EMinStateNoneOrExited,          # guard: already done → succeed
      ConsiderAbandoningProposed,     # alternative 1
      ConsiderTerminatingActive,      # alternative 2
  )
  ```

- **Complex leaf → subtree**: when a simulator `a_` leaf needs non-trivial
  logic, expand it into a Sequence of simple conditions and actions, each
  testable in isolation.

---

## Reusability Anti-Patterns

1. **Hard-coded actor roles or identities** — pass `actor_id`/role as
   constructor parameters so one node serves coordinator, vendor, and finder.
   A factory such as `create_finder_participant_node()` with the role in its
   name and body is the smell.
2. **Demo-specific logic in reusable nodes** — BT nodes MUST NOT import from
   `vultron.demo` or read environment variables; log with the standard
   `logging` module.
3. **One-off subtrees hard-coded to one workflow** — separate generic reusable
   logic (composable) from activity-specific integration (the entry point).
4. **Duplicate subtrees with slight variations** — extract one parameterized
   helper.

### Node Design Rules

- **Parameterization**: nodes take required values as constructor parameters,
  never from global state, environment variables, or implicit context.
- **Blackboard keys**: `{noun}_{id_segment}`, no slashes (see
  `notes/bt-integration.md` § "Design Rules for New Trees").
- **ActorConfig-driven roles**: the local actor's default CVD roles come from
  `ActorConfig` (`vultron/config/actor.py`, outside `vultron/demo/`, so nodes may
  import it), never hard-coded (BTND-04-002, BTND-05-001 through BTND-05-003,
  CFG-07-001 through CFG-07-004).

### Checklist Before Adding a Node or Subtree

- [ ] No hard-coded actor roles or identities
- [ ] No imports from `vultron.demo`, no environment-variable dependencies
- [ ] No singletons — state is parameter-passed or in the DataLayer
- [ ] No duplicate logic — similar operations are parameterized helpers
- [ ] Blackboard keys avoid slashes
- [ ] Composable as a child of a parent tree, and testable in isolation with
  minimal fixtures (test parameter variations and composition; no
  demo-specific fixture data)
