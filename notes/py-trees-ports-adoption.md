---
title: py_trees Ports Adoption — Typed Blackboard Contracts and XML Authoring
status: archived
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

## Current state (migration complete — verified 2026-08-24)

- **Dependency**: `pyproject.toml` already pins `py-trees>=2.5.0`. The Idea's
  "evaluate the upgrade path from the current pin" step is already satisfied —
  no upgrade is required to reach the Ports API.
- **Ports API present and in use**: `py_trees.ports` exposes
  `BehaviourWithPorts` (a `PortsMixin` + `Behaviour` subclass),
  `PortInformation`, `NoDataAvailable`, and a ports registry. The pilot (#1808)
  landed `DataLayerConditionWithPorts` and `DataLayerActionWithPorts` in
  `vultron/core/behaviors/helpers.py` and migrated a first tranche of
  `report/nodes/`. The pattern is now the standard base for all new nodes
  (ADR-0044, BTND-03-009 through BTND-03-011).
- **Migration progress**:
  - Part 1/5 (#1883) migrated **41 Type-A nodes** across `case/`, `status/`,
    and `note/` domains — all trivial base-only reparents with no
    domain-specific `register_key()` calls. ✓
  - Part 2/5 (#1884) migrated **36 Type-A nodes** across `report/nodes/` and
    `embargo/nodes/`. **Headroom note**: `report/nodes/deploy_fix.py` is now
    exactly 500 lines (the BTND-07-004 hard limit); split it before the next
    change (see `plan/incoming/learnings/20260821-deploy-fix-line-count-margin.md`).
    ✓ (2026-08-21)
  - Part 3/5 (#1885) migrated **Type-B nodes** (extra READ-only inputs) across
    `sync/`, `sender/`, `embargo/`, `case/`, and `status/` domains — adds
    `input_ports()` + `_domain_port_remappings()` + `get_input()` in
    `initialise()`. Also extracted `SendTerminateEmbargoActivityNode` from
    `lifecycle.py` to restore BTND-07-004, and fixed
    `DataLayerConditionWithPorts`/`DataLayerActionWithPorts.initialise()` to
    catch `NotImplementedError` from py_trees when a blackboard key stores
    explicit `None`. ✓ (2026-08-21)
  - Part 4/5 (#1886) establishes the `output_ports()` + `_set_output()` convention
    (BTND-03-012, BTND-03-013) and migrates **Type-C WRITE-handoff nodes** across
    `sync/`, `case/`, `embargo/`, `report/`, `sender/`, and `status/` domains.
    Nodes with instance-computed (execution-scoped) physical keys are deferred to #1887.
  - Part 5/5 (#1887) migrated **non-DataLayer bare `Behaviour` nodes** that touch
    the blackboard across `inbox/nodes/pipeline.py`, `report/`,
    `status/nodes/append/conditions.py`, and `case/nodes/actor.py`.
    Created `_InboxNodeWithPorts` (parallel to `DataLayerActionWithPorts`) as
    the base for inbox pipeline nodes (IO-02-002).  Execution-scoped output
    ports (BTND-03-013) applied to `EvaluateDefaultRolesNode` and
    `_WriteRolesNode`.  Added architecture ratchet test
    (`test/architecture/test_no_bare_register_key_datalayer_nodes.py`) with a
    51-node audited baseline to prevent new `register_key`-only `DataLayer*`
    leaf nodes.  Composite `Sequence`/`Selector` subclasses are explicitly
    exempt: they are structural orchestrators with no leaf data-flow contract.
    Nodes with no blackboard access (`CheckAutoCaseCreationEnabledNode`,
    `ShouldAdvanceOwnerToAcceptedNode`, `AlwaysSucceed`, `AlwaysFail`,
    `_AlwaysSucceedNode`) are exempt as constructor-parameterized gates.
    ✓ (2026-08-24)
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

### 5. Declare and wire output ports (Type-C nodes — WRITE-handoff)

If the node **writes** a value consumed by a downstream sibling (a "Type-C"
WRITE-handoff node), override `output_ports()` and use `_set_output()`:

```python
@classmethod
def output_ports(cls) -> dict[str, PortInformation]:
    return {
        "fanout_recipients": PortInformation(data_type=object, required=True),
    }

@classmethod
def _domain_port_remappings(cls) -> dict[str, str]:
    return {
        "fanout_recipients": "/fanout_recipients",
        # ... plus any input remappings ...
    }
```

In `update()`, replace `self.blackboard.key = value` with
`self._set_output("key", value)`:

```python
# Before
self.blackboard.fanout_recipients = recipients

# After
self._set_output("fanout_recipients", recipients)
```

Remove the `self.blackboard.register_key(key=..., access=WRITE)` calls from
`setup()` — `setup_ports()` in the base class handles registration for all
declared ports.

**Execution-scoped physical keys** (BTND-03-013): when the physical blackboard
key is computed from a constructor parameter (e.g.
`f"suggested_roles_{report_id.split('/')[-1]}"`), the logical port name in
`output_ports()` uses only the `{noun}` (e.g. `"suggested_roles"`), and the
physical key is wired in the instance `setup()` override — **not** via the
classmethod `_domain_port_remappings()`:

```python
class MyNode(DataLayerActionWithPorts):
    def __init__(self, report_id: str, name=None):
        super().__init__(name=name or self.__class__.__name__)
        _seg = report_id.split("/")[-1]
        self._suggested_roles_key = f"suggested_roles_{_seg}"

    @classmethod
    def output_ports(cls) -> dict[str, PortInformation]:
        return {"suggested_roles": PortInformation(data_type=object, required=True)}

    def setup(self, **kwargs):
        self.setup_ports(
            port_remappings={
                "datalayer": "/datalayer",
                "actor_id": "/actor_id",
                "suggested_roles": f"/{self._suggested_roles_key}",
            }
        )

    def update(self) -> Status:
        ...
        self._set_output("suggested_roles", roles)
        return Status.SUCCESS
```

### 6. Update `update()` for output writes

Replace every `self.blackboard.key = value` for a declared output port with
`self._set_output("key", value)`. Leave `self.blackboard.key` reads
for input ports that are not yet migrated to `get_input()` (but prefer
`get_input()` per BTND-03-011).

### 8. Add isolated-node tests

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

## Exemptions (nodes NOT migrated, with justification)

### Composite nodes (Sequence/Selector subclasses)

`py_trees.composites.Sequence` and `py_trees.composites.Selector` subclasses
throughout `vultron/core/behaviors/` are **structurally exempt**.  Composites
are orchestrators — they have no leaf data-flow contract and own no blackboard
keys.  The typed-Ports contract (BTND-03-009) applies to *leaf* nodes that
read or write data; composites pass control to their children and never touch
the blackboard directly.

### Constructor-parameterized policy gates (no blackboard access)

The following bare `py_trees.behaviour.Behaviour` subclasses have **no
blackboard access** — they make decisions based solely on constructor-injected
values:

- `CheckAutoCaseCreationEnabledNode` (`case/nodes/conditions.py`): reads
  `ActorConfig.auto_create_case` from a constructor-injected object.
- `ShouldAdvanceOwnerToAcceptedNode` (`case/nodes/participant/owner.py`):
  reads a constructor-injected boolean.
- `AlwaysSucceed` / `AlwaysFail` (`call_out/nodes.py`): stateless; always
  return a fixed Status.
- `_AlwaysSucceedNode` (`case/accept_invite_tree.py`): same.

Migrating these to `BehaviourWithPorts` would add no contract value — there
are no ports to declare.

## Finalized conventions (established across parts 1–5)

1. **Type-A nodes** (no domain blackboard keys beyond DataLayer standard):
   pure base-class reparent, no override needed (established by #1883–#1884).

2. **Type-B nodes** (extra READ-only inputs):
   override `input_ports()` + `_domain_port_remappings()` + `get_input()`
   in `initialise()` (established by #1885).

3. **Type-C WRITE-handoff nodes** (static physical key):
   override `output_ports()` + `_domain_port_remappings()` + `_set_output()`
   in `update()` (established by #1886, BTND-03-012).

4. **Type-C execution-scoped physical key** (BTND-03-013):
   declare stable logical port in `output_ports()`, compute physical key in
   `__init__`, wire via instance `setup_ports()` override (not classmethod
   `_domain_port_remappings()`).

5. **Non-DataLayer nodes with blackboard access** (established by #1887):
   extend `BehaviourWithPorts` directly; declare `input_ports()` and/or
   `output_ports()`; call `setup_ports()` in `setup()` with explicit
   `port_remappings` wired to the flat absolute keys.

6. **Inbox pipeline nodes** (`_InboxNodeWithPorts`, #1887):
   parallel to `DataLayerActionWithPorts` for the `inbox_*` key namespace;
   shared output ports for `inbox_outcome_status` and `inbox_failure_reason`;
   `_reject()` uses `_set_output()`; `_domain_port_remappings()` classmethod
   extended by subclasses (IO-02-002).

7. **Read-modify-write same key** (`RehydrateActivityNode`, #1887):
   declare a separate input port alias (e.g. `inbox_activity_in`) for the
   READ path and the normal output port for the WRITE path; both remapped to
   the same absolute key.  Two different client-local names → two access
   levels → same storage slot.

8. **`NotImplementedError` on explicit `None`** (fixed in #1885 and #1887):
   `get_input()` raises `NotImplementedError` when the blackboard key holds
   an explicit `None` value (py_trees quirk).  Optional-or-nullable inputs
   must catch `(NotImplementedError, NoDataAvailable)`.

## Issue sequence

Derived from the #1558 grill-me interview. All Tasks are children of Epic #427.

1. **#1808 — Ports adoption (pattern + pilot)** *(Task, blocked-by #1558)*
   Establish a typed-Ports base class + convention; author the ADR and BTND/BT
   spec amendments; migrate **one** representative subtree
   (e.g. `validate_report` / `prioritize`) end-to-end with tests; document the
   migration recipe. `size:M`.
2. **#1809 — Full node migration** *(Task, blocked-by #1808)*
   Migrate the remaining `vultron/core/behaviors/` nodes to typed Ports,
   following #1808's recipe. `size:L`. Split into five sequential sub-Tasks so
   each part has a reviewable blast radius:
   - **#1883 (1/5) ✓** — trivial base-only reparent: `case`, `status`, `note`.
     Type-A nodes only (no domain `register_key()`), pure base-class swap.
   - **#1884 (2/5)** — trivial base-only reparent: `report`, `embargo`.
   - **#1885 (3/5)** — read-only extra-input nodes: add `input_ports()` and
     replace direct blackboard reads with `get_input()`.
   - **#1886 (4/5)** — WRITE-handoff nodes: establish `output_ports()` and the
     execution-scoped key convention (AC-3's BTND-03-004 property).
   - **#1887 (5/5)** — non-DataLayer nodes, composite exemptions, and
     finalization (including this note's AC-4 completion update).
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

---

## Nodes with Instance-Computed Blackboard Keys

(ISSUE-1885, 2026-08-21; resolved by PR #2530 / #2483, 2026-08-24)

Some nodes compute their blackboard key names dynamically in `__init__` from a
constructor argument (e.g. `report_id`):

```python
_seg = report_id.split("/")[-1] if report_id else "default"
self._participant_case_key = f"participant_case_{_seg}"
```

`input_ports()` is a **classmethod** — it cannot access instance state. During
Part 3/5 (#1885), this meant those nodes could not be migrated to
`DataLayerActionWithPorts` via the standard classmethod pattern.

Additionally, using `DataLayerActionWithPorts` with `self._blackboard_client.register_key(...)`
in `setup()` fails because `_blackboard_client` is typed `Optional` and Pyright
correctly flags `.register_key` on `None`.

Affected nodes identified in Part 3/5 (#1885):

- `PersistOwnerCaseNode`
- `AdvanceOwnerRmToAcceptedNode`
- `RecordOwnerJoinedEventNode`

**Resolved**: cleanup PR #2530 (issue #2483) successfully migrated all three
nodes to `DataLayerActionWithPorts` as part of clearing the `AUDITED_SITES`
backlog. The dynamic-key pattern was handled during that cleanup.
*Source: ISSUE-1885, PR #2530*
