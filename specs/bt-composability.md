# Behavior Tree Composability Specification

## Overview

Requirements for implementing Vultron's behavioral logic as composable,
reusable BT structures using the simulator as the canonical blueprint.

These requirements address the *workflow* of BT composition: how to use the
simulator reference, where structures must live, when to use BT composite
idioms instead of procedural code, and the fractal composability principle
that applies at every depth.

**Source**: IDEA-26041703 (BT composability as core design principle).

**Cross-references**:

- `specs/behavior-tree-integration.md` BT-06-001 through BT-06-006 — when
  to use BTs, protocol-significant behavior, cascade rules
- `specs/behavior-tree-node-design.md` BTND-01 through BTND-05 — node
  parameterization, composability, module ownership
- `notes/bt-composability.md` — implementation guidance, examples, and
  the fractal pattern in depth

---

## Simulator Reference Workflow

- `BTC-01-001` Before implementing any BT node or subtree in
  `vultron/core/behaviors/`, a developer MUST search `notes/vultron-bt.txt`
  to locate the corresponding node in the canonical simulation tree.
  - **How**: Search for the behavior name in the tree dump (e.g.,
    `TerminateEmbargoBt`, `RMValidateBt`). If a matching named node exists,
    it MUST be used as the structural template for the prototype
    implementation.
  - **Rationale**: The canonical tree is the normative definition of Vultron's
    domain behavior. Implementing without consulting it risks inventing
    structures that contradict the protocol design.
  - `BTC-01-001 refines BT-06-002`

- `BTC-01-002` After locating a node in `notes/vultron-bt.txt`, a developer
  MUST examine the corresponding class in `vultron/bt/` to understand the
  node's children, structure, and composites.
  - **Navigation rule**: Node names in `vultron-bt.txt` are runtime instance
    names with an underscore-separated numeric suffix (e.g.,
    `TerminateEmbargoBt_217`). The class name is the prefix before the
    underscore-number suffix (e.g., `TerminateEmbargoBt`). Find that class in
    `vultron/bt/` to read its structure.
  - `BTC-01-002 refines BT-06-002`

- `BTC-01-003` If a corresponding simulator class does NOT exist for the
  behavior being implemented, the developer MUST document the divergence
  with a brief rationale comment before proceeding.
  - `BTC-01-003 refines BT-06-002`

---

## BT Structure Pre-Definition

- `BTC-02-001` All BT composite structures used by use cases in
  `vultron/core/use_cases/` MUST be pre-defined as named classes or
  factory composites in `vultron/core/behaviors/` before use.
  - **Rationale**: Business logic lives in `core/behaviors/`. If use cases
    construct trees ad-hoc, the business logic migrates into use cases and
    becomes invisible to analysis of the behavior layer.
  - `BTC-02-001 refines BT-06-001`

- `BTC-02-002` Use cases MUST NOT construct ad-hoc BT composite trees inline.
  Inline construction means calling `py_trees.composites.Sequence(children=[
  NodeA(), NodeB(), ...])` or equivalent directly inside a use case's
  `execute()` method.
  - **Permitted**: infrastructure glue — instantiating a pre-defined class
    (`bt = DefinedBtClass(**params)`), calling the bridge, and reading
    results. See BT-06-001 for the full permitted list.
  - `BTC-02-002 refines BTC-02-001`

- `BTC-02-003` Use cases MUST follow the instantiate-then-invoke pattern when
  using BTs:

  ```python
  # ✅ Correct: instantiate pre-defined class, then invoke via bridge
  bt = TerminateEmbargoBt(embargo_id=embargo_id, case_id=case_id)
  bridge.execute_with_setup(self._dl, bt, bb)

  # ❌ Wrong: ad-hoc inline tree construction
  bt = py_trees.composites.Selector(
      name="TerminateEmbargo",
      children=[
          EMinStateNoneOrExited(),
          ConsiderTerminatingEmbargo(),
      ],
  )
  bridge.execute_with_setup(self._dl, bt, bb)
  ```

  - `BTC-02-003 refines BTC-02-002`

---

## BT Idioms Over Procedural Code

- `BTC-03-001` Behavioral logic that belongs inside a BT MUST be expressed
  using BT composite idioms (Sequence, Selector/Fallback, Decorator) rather
  than procedural `if`/`else` chains.
  - **Rationale**: BT idioms make logic auditable, extractable, and
    explainable by anyone who can read the tree structure, without reading
    implementation code. Procedural logic inside `update()` is opaque.
  - `BTC-03-001 refines BT-06-001`

- `BTC-03-002` Precondition-then-action logic MUST be modeled as a Sequence
  where leading children are Condition nodes and trailing children are Action
  nodes.
  - **Pattern**: `Sequence([CondA, CondB, ActionC])` — succeeds only if
    CondA and CondB succeed, then executes ActionC.
  - `BTC-03-002 refines BTC-03-001`

- `BTC-03-003` Try-A-or-else-B fallback logic MUST be modeled as a Selector
  (Fallback) composite with A and B as children.
  - **Pattern**: `Selector([TryA, TryB])` — tries TryA; if it fails, tries
    TryB.
  - `BTC-03-003 refines BTC-03-001`

- `BTC-03-004` When a leaf node in the canonical simulator BT requires complex
  implementation logic, that logic SHOULD be expanded into a subtree using BT
  composite idioms rather than procedural code in a single `update()` method.
  - **Guidance**: A leaf node's `update()` longer than ~10 lines is a signal
    to consider expansion. Replace the leaf with a Sequence or Selector
    subtree whose children each do one focused thing.
  - `BTC-03-004 refines BT-06-004`

---

## Fractal Composability

- `BTC-04-001` The compose-and-reuse principle MUST apply at every depth
  level of the behavior tree — from single-purpose leaf nodes up to
  use-case entry trees.
  - **Fractal implication**: A subtree that itself composes smaller subtrees
    follows the same principle as those smaller subtrees. There is no depth
    at which reuse stops being required.
  - `BTC-04-001 refines BTND-02-002`

- `BTC-04-002` When the canonical simulation tree shows the same named
  behavior appearing at two or more locations, that behavior MUST be
  implemented as a single reusable class in `vultron/core/behaviors/`,
  instantiated separately at each use site.
  - **Example**: `TerminateEmbargoBt` appears as a child of both
    `EmbargoManagementBt` and other subtrees in the canonical tree. The
    prototype MUST have one `TerminateEmbargoBt` class instantiated where
    needed — NOT duplicated logic per call site.
  - `BTC-04-002 refines BTND-02-001`

- `BTC-04-003` The "trunk-removed branches" model means extracting reusable
  subtrees at *the appropriate depth for the behavior*, not uniformly at the
  top level.
  - A behavior that is a subtree of a subtree in the canonical tree SHOULD
    be implemented as a composable subtree that can be added as a child to
    its parent tree. The extraction depth is determined by the canonical tree
    structure, not by a fixed rule.
  - `BTC-04-003 refines BT-06-002`

- `BTC-04-004` Every pre-defined BT class in `vultron/core/behaviors/` SHOULD
  be usable both as a standalone use-case entry point AND as a composable
  child of a larger BT.
  - **Constraint**: A subtree that can only be used one way (e.g., only as a
    use-case entry, never as a child) is a candidate for interface review.
  - `BTC-04-004 refines BTND-02-002`

---

## Verification

### BTC-01-001, BTC-01-002

- Code review: New BT subtree classes in `vultron/core/behaviors/` include
  a reference to their canonical simulator counterpart in a docstring or
  comment (e.g., `# Corresponds to TerminateEmbargoBt in vultron/bt/`).
- Code review: No new BT structure exists in `vultron/core/behaviors/` that
  has a clear canonical counterpart in `vultron/bt/` but was implemented
  differently without documented justification.

### BTC-02-001, BTC-02-002, BTC-02-003

- Code review: No `py_trees.composites.*` constructor call appears inside
  a use-case `execute()` method; all BT construction is delegated to classes
  in `vultron/core/behaviors/`.
- Unit test: Each `execute()` method in `vultron/core/use_cases/` that uses
  a BT instantiates a named class from `vultron.core.behaviors` before
  passing it to the bridge.

### BTC-03-001, BTC-03-002, BTC-03-003

- Code review: BT node `update()` methods contain only: state reads from
  DataLayer or blackboard, the single action of the node, and a return of
  SUCCESS or FAILURE. Multi-branch conditional logic in `update()` is
  flagged for extraction to a subtree.
- Code review: Precondition checks are leading Condition children in a
  Sequence, not `if/else` guards inside `update()`.

### BTC-04-002

- Code review: Any behavior named in `notes/vultron-bt.txt` at two or more
  structural locations is implemented as a single class in
  `vultron/core/behaviors/`.
- Code review: No two classes in `vultron/core/behaviors/` have
  functionally identical `update()` bodies that differ only by a parameter
  that should have been made a constructor argument.

### BTC-04-004

- Unit test: Each pre-defined BT class in `vultron/core/behaviors/` can be
  added as a child to a `py_trees.composites.Sequence` in a test without
  error.
- Unit test: Each use-case entry-point tree can also be constructed and
  ticked standalone in isolation without a parent tree.

---

## Related

- **Design notes**: `notes/bt-composability.md` — fractal pattern in depth,
  "trunkless branch" clarification, simulator navigation guide, and BT idiom
  examples
- **BT node design**: `specs/behavior-tree-node-design.md` BTND-01 through
  BTND-05 — parameterization, module ownership, blackboard contracts
- **BT execution model**: `specs/behavior-tree-integration.md` BT-06-001
  through BT-06-006 — when BTs are required, cascade rules
- **Event-driven cascade model**: `specs/event-driven-control-flow.md` —
  cascade chain and BT-as-cascade-mechanism requirements
- **Canonical tree reference**: `notes/vultron-bt.txt`,
  `vultron/bt/behaviors.py` (simulator source)
