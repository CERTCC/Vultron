---
title: py_trees Ports Adoption — Typed Blackboard Contracts and XML Authoring
status: active
description: >
  Planning analysis for adopting py_trees 2.5.0 typed Ports in vultron/core/behaviors/:
  the concrete wins (typed data contracts, early error detection, isolated node
  testing), the constructor-parameterization vs XML port-remapping impedance
  mismatch, and the staged issue sequence (pilot -> full migration -> XML spike
  -> XML-as-spec idea) derived from planning issue #1558.
related_specs:
  - specs/behavior-tree-node-design.yaml
  - specs/behavior-tree-integration.yaml
related_notes:
  - notes/bt-integration.md
  - notes/bt-pitfalls.md
  - notes/bt-design-patterns.md
relevant_packages:
  - py_trees
  - vultron/core/behaviors
---

# py_trees Ports Adoption

This note records the planning analysis behind GitHub Idea #1558 ("Adopt
py-trees Ports for typed blackboard contracts and XML-based protocol behavior
tree specifications"). It is the durable reference for the implementation
Tasks spawned from that Idea. It captures the current state, what is worth
adopting, what is deferred, the known technical mismatch, and the issue
sequence — so each implementing agent starts from evidence rather than the
Idea's optimistic framing.

## Current state (verified 2026-07-29)

- **Dependency**: `pyproject.toml` already pins `py-trees>=2.5.0`. The Idea's
  "evaluate the upgrade path from the current pin" step is already satisfied —
  no upgrade is required to reach the Ports API.
- **Ports API present, unused**: `py_trees.ports` exposes `BehaviourWithPorts`
  (a `PortsMixin` + `Behaviour` subclass), `PortInformation`,
  `NoDataAvailable`, and a ports registry. A repo-wide search finds **zero**
  references to `input_ports`, `output_ports`, `BehaviourWithPorts`, or
  `PortInformation` in `vultron/`, `specs/`, `notes/`, `docs/`, or `test/`.
- **Node population**: `vultron/core/behaviors/` contains roughly **60 node
  classes** and about **249 `register_key()` call sites**. Every node currently
  subclasses `py_trees.behaviour.Behaviour` (or the DataLayer-aware base classes
  in `helpers.py`) and declares blackboard access imperatively in `setup()` via
  `register_key()`, following the `{noun}_{id_segment}` naming convention
  (BTND-03-005, BTND-03-008).
- **XML parser**: `py_trees.parsers.behaviour_tree_xml` exists but is documented
  as **experimental** ("the parser is experimental and its API may change
  between releases"). It instantiates only classes registered in a
  `PortsMixin`/`BehaviourWithPorts` node registry and wires data flow through
  **port remapping** (`{key}` -> absolute blackboard path), plus `<SubTree>`
  templates with namespace scoping.

## What is worth adopting (the "usable things")

Typed Ports deliver three concrete wins independent of any XML story:

1. **Explicit data contracts** — `input_ports()` / `output_ports()` become a
   node's declared data-flow API, readable without tracing `update()`. This is
   a stronger, typed form of the existing BTND-03-003 "document your keys in the
   docstring" SHOULD.
2. **Structured early error detection** — typed writes, `NoDataAvailable` on a
   missing required input, and misconfigured remappings surface at setup time
   rather than as a mid-tick `KeyError`. This directly hardens the class of bugs
   catalogued in `notes/bt-pitfalls.md` (§ "py_trees `blackboard.get()` Raises
   KeyError for Unwritten READ Keys", § "Decomposed BT Leaf Must Return FAILURE
   for Missing Blackboard Keys").
3. **Easier isolated unit testing** — a single node can be exercised by wiring
   its ports to known blackboard keys and ticking once, reducing tree-scaffolding
   boilerplate (complements `BTTestScenario`).

## What is deferred (out of scope for the Ports adoption work)

- **XML tree authoring** and **XML-as-specification artifacts** are **not** part
  of the Ports adoption Tasks. They depend on resolving the mismatch below and
  are tracked as a separate Idea (see sequence). The Ports adoption is justified
  entirely by the three wins above.

## The impedance mismatch (the reason XML is a spike, not a Task)

Vultron BT nodes are **heavily constructor-parameterized** by mandate:
BTND-01-001 requires actor identities, CVD roles, case IDs, and factory
callables to be **constructor parameters**, and BTND-01-002 forbids reading them
from ambient context. The py_trees XML parser, by contrast, instantiates nodes
from the registry and injects data only through **blackboard port remapping** —
it has no general mechanism for passing arbitrary constructor arguments
(factories, case IDs) to a node at XML-parse time.

Consequences to resolve before any XML authoring is attempted:

- Constructor-injected values (call-out backend factories per ADR-0025,
  `case_id`, role parameters) do not have an obvious XML representation.
- Adopting XML port-remapping would push node inputs from constructor args
  toward blackboard ports — in tension with BTND-01-001. Whether that tension
  is acceptable, and for which node categories, is exactly what the spike must
  determine.
- The parser is experimental; committing protocol-specification artifacts to an
  API that "may change between releases" is a risk that needs explicit
  evaluation.

## ADR / spec determination

Adopting Ports is an **evaluated architectural choice** (Ports vs. the current
imperative `register_key` convention) that also generates **recurring testable
requirements** (every migrated node must declare typed ports). Per
`notes/specs-vs-adrs.md`, that dual signal calls for **both** an ADR and spec
amendments — to be authored **within the Ports adoption Task**, validated by the
pilot subtree, not pre-committed here:

- **ADR** (extends ADR-0008 "Use py_trees for … Handler Integration"): records
  the decision to adopt typed Ports, the alternatives (keep imperative
  `register_key`; adopt Ports base class), and the constructor-parameterization
  vs. remapping tension as a known consequence.
- **`specs/behavior-tree-node-design.yaml`** (BTND-03 family): amend the
  blackboard-contract requirements to express typed port declarations, and
  reconcile with the `{noun}_{id_segment}` naming and BTND-01 constructor rules.
- **`specs/behavior-tree-integration.yaml`**: update where it describes the
  blackboard/bridge contract if Ports change the bridge's setup path.

## Migration recipe (established by #1808)

Follow these steps when migrating any `DataLayerCondition` / `DataLayerAction`
node to typed Ports (required for all new nodes; follow-on sweep in #1809).

### 1. Change the base class

```python
# Before
class MyNode(DataLayerCondition):
    ...

# After
class MyNode(DataLayerConditionWithPorts):
    ...
```

Use `DataLayerConditionWithPorts` for condition (read-only) nodes and
`DataLayerActionWithPorts` for action (mutating) nodes.

### 2. Add `input_ports()` and `output_ports()`

Declare every blackboard key the node uses. The base classes already declare
`datalayer`, `actor_id`, and (for actions) `trigger_activity_factory`.
Override `input_ports()` to **add** domain-specific ports; call
`super().input_ports()` first if you want to extend rather than replace:

```python
@classmethod
def input_ports(cls) -> dict[str, PortInformation]:
    ports = super().input_ports()          # inherit base ports
    ports["report_id"] = PortInformation(data_type=str, required=True)
    return ports

@classmethod
def output_ports(cls) -> dict[str, PortInformation]:
    return {}                              # or declare output ports here
```

If the node has **no** domain-specific ports beyond the base class defaults,
omit `input_ports()` and `output_ports()` entirely — the base class
definitions are abstract but already implemented.

### 3. Remove `setup()` overrides that only call `register_key()`

The base class `setup()` calls `setup_ports()` with the standard BTBridge
remappings. Only override `setup()` if you need to register **additional**
domain-specific ports:

```python
def setup(self, **kwargs: Any) -> None:
    super().setup(**kwargs)          # registers datalayer, actor_id
    # register additional domain ports here if needed
```

### 4. Update `initialise()` to use `get_input()`

```python
# Before
def initialise(self) -> None:
    self.datalayer = self.blackboard.datalayer
    self.actor_id = self.blackboard.actor_id

# After — base class initialise() already does this; only override if
# you need to read additional domain ports:
def initialise(self) -> None:
    super().initialise()             # sets self.datalayer, self.actor_id
    self.report_id = self.get_input("report_id")
```

### 5. Leave `update()` unchanged

The `update()` logic itself does not change — it still uses `self.datalayer`,
`self.actor_id`, and the `_require_*` guard helpers.

### 6. Add isolated-node tests

Add at least two tests per migrated node:

- **Happy path**: wire required ports, tick once, assert SUCCESS.
- **Missing required port**: call `setup_ports()` without the required port
  written to the blackboard; assert `NoDataAvailable` is raised at setup time.

Use the `BTTestScenario` harness from `test/core/behaviors/bt_harness.py` for
the happy-path test.  For the isolated-port test, call `setup_ports()` and
`get_input()` directly:

```python
from py_trees.ports import NoDataAvailable
import pytest

def test_missing_required_port():
    node = CheckRMStateValid(report_id="https://example.org/reports/1")
    node.setup_ports()   # no remappings → default keys; blackboard is empty
    with pytest.raises(NoDataAvailable):
        node.get_input("datalayer")
```

## Issue sequence

Derived from the #1558 grill-me interview. All Tasks are children of Epic #427.

1. **#1808 — Ports adoption (pattern + pilot)** *(Task, blocked-by #1558)*
   Establish a typed-Ports base class + convention; author the ADR and BTND/BT
   spec amendments; migrate **one** representative subtree
   (e.g. `validate_report` / `prioritize`) end-to-end with tests; document the
   migration recipe. `size:M`.
2. **#1809 — Full node migration** *(Task, blocked-by #1808)*
   Migrate the remaining `vultron/core/behaviors/` nodes to typed Ports,
   following #1808's recipe. `size:L`.
3. **#1810 — XML feasibility spike** *(Task, blocked-by #1809)*
   Assess whether protocol BTs can be authored/exported as BehaviorTree XML
   given the constructor-vs-remapping mismatch and the experimental parser.
   **Deliverable is a learning artifact**: detailed commentary appended to the
   XML planning Idea (#1811) — feasibility verdict, the mismatch analysis,
   parser-risk assessment. Throwaway proof-of-concept code is allowed but the
   spike is **not** gated on merging production code. `size:S`.
4. **#1811 — XML-as-specification Idea** *(Idea, blocked-by #1809 and #1810)*
   Captures XML tree authoring and XML-as-spec artifacts, to be planned later
   via `plan-issue` once the spike's findings are in.

Blocker graph: `#1558 -> #1808 -> #1809 -> {#1810, #1811}` and
`#1810 -> #1811`.
