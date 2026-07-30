---
status: accepted
date: 2026-07-29
deciders:
  - vultron maintainers
consulted:
  - project stakeholders
informed:
  - contributors
---

# Adopt py_trees Typed Ports for BT Node Blackboard Contracts

## Context and Problem Statement

ADR-0008 established `py_trees` as the BT library for prototype handler
execution in `vultron/core/behaviors/`. The current convention for declaring
a node's blackboard dependencies is imperative: each node calls
`register_key()` in `setup()` and reads keys via direct attribute access on
`self.blackboard` in `initialise()`. This approach works, but has two
weaknesses:

1. **Hidden data contracts**: the keys a node reads or writes are scattered
   across `setup()`, `initialise()`, and `update()` — there is no single,
   machine-readable declaration.
2. **Late error detection**: a misspelled key or a missing required input
   surfaces as a mid-tick `KeyError` or a silent `None`, not at setup time.

`py_trees >= 2.5.0` (already pinned in `pyproject.toml`) provides a typed
Ports API (`BehaviourWithPorts`, `PortInformation`, `setup_ports()`,
`get_input()`) that addresses both weaknesses.

## Decision Drivers

- Explicit, readable data-flow contracts at the class level (one method per
  direction: `input_ports()` / `output_ports()`).
- Structured early error detection: `NoDataAvailable` on a missing required
  input surfaces in `initialise()` (at the start of the first tick) rather than
  silently mid-tick as a `KeyError`.
- Easier isolated unit tests: a node can be exercised by wiring its ports to
  known blackboard keys without scaffolding a full tree.
- No dependency upgrade: `py_trees >= 2.5.0` is already installed.
- Compatibility with the existing `BTBridge` flat-key convention: port
  remappings (`{"datalayer": "/datalayer", "actor_id": "/actor_id"}`) bridge
  the Ports namespace to the keys `BTBridge.setup_tree()` writes.

## Considered Options

1. Keep the imperative `register_key` / direct-attribute convention.
2. Adopt `BehaviourWithPorts` as base for all `vultron/core/behaviors/` nodes.
3. Adopt `BehaviourWithPorts` for new nodes only; keep legacy nodes unchanged.

## Decision Outcome

**Option 2 — adopt `BehaviourWithPorts` as the standard base for all nodes
in `vultron/core/behaviors/`**, piloted on the `validate_report` subtree.

The pilot validates the migration recipe before the full sweep (Issue #1809).

### Consequences

**Good:**

- `input_ports()` / `output_ports()` are the single source of truth for
  each node's blackboard contract — readable without tracing `update()`.
- `NoDataAvailable` on a missing required input surfaces when `get_input()` is
  called in `initialise()` — at the start of the first tick, not during `setup()`.
- Isolated node tests can call `setup_ports()` + `get_input()` directly
  without running a full tree.
- `DataLayerConditionWithPorts` and `DataLayerActionWithPorts` in
  `helpers.py` encapsulate the standard port remappings and `_require_*`
  guard helpers, so subclasses need only declare domain-specific ports.

**Known consequence (not a blocker):**

- The py_trees XML parser instantiates nodes via port remapping only and
  has no mechanism for passing constructor arguments (factories, case IDs).
  Vultron nodes are **heavily constructor-parameterized** (BTND-01-001), so
  XML-based tree authoring is not yet feasible. This tension is documented
  in `notes/py-trees-ports-adoption.md` and is the subject of the XML
  feasibility spike (Issue #1810).

### Implementation pattern

```python
class CheckRMStateValid(DataLayerConditionWithPorts):
    @classmethod
    def input_ports(cls) -> dict[str, PortInformation]:
        # Inherit datalayer + actor_id from base class defaults.
        # Override only to add domain-specific ports.
        return super().input_ports()

    @classmethod
    def output_ports(cls) -> dict[str, PortInformation]:
        return {}

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        # ... domain logic using self.datalayer and self.actor_id
```

`DataLayerConditionWithPorts.setup()` calls `setup_ports()` with the
standard BTBridge remappings; `initialise()` calls `get_input()` to
populate `self.datalayer` and `self.actor_id`.

## More Information

- `notes/py-trees-ports-adoption.md` — full migration recipe and issue
  sequence.
- `specs/behavior-tree-node-design.yaml` BTND-03-009 through BTND-03-011 —
  normative requirements for typed port declarations.
- `vultron/core/behaviors/helpers.py` — `DataLayerConditionWithPorts` and
  `DataLayerActionWithPorts` base classes.
- Pilot subtree: `vultron/core/behaviors/report/nodes/` (`CheckRMStateValid`,
  `CheckRMStateReceivedOrInvalid`, `EnsureEmbargoExists`,
  `TransitionRMtoValid`).
- Related ADRs: ADR-0008 (py_trees adoption), ADR-0025 (call-out point
  abstraction).
- Follow-on: Issue #1809 (full migration), Issue #1810 (XML spike).
