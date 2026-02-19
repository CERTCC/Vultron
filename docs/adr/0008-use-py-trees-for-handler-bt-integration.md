---
status: accepted
date: 2026-02-19
deciders:
  - vultron maintainers
consulted:
  - project stakeholders
informed:
  - contributors
---

# Use py_trees for Behavior Tree Execution in Handler Integration

## Context and Problem Statement

ADR-0002 establishes that Vultron models CVD processes as behavior trees (BTs),
and ADR-0007 introduces a behavior dispatcher between inbox handling and
behavior execution. The `vultron/bt/` module implements a custom BT engine
tailored to Vultron's simulation needs. As the prototype API v2 handlers
evolve, complex workflows (e.g., report validation) require structured
orchestration beyond procedural code.

The question is: which BT library should be used for handler-level BT
execution in the prototype API?

## Decision Drivers

- Need a mature BT library with standard semantics (Sequence, Fallback,
  Condition, Action)
- Must support blackboard state management for multi-node data passing
- Visualization and debugging support is highly desirable
- The `vultron/bt/` custom engine is optimized for simulation; it should not
  be modified or reused for API handler execution
- Must be compatible with Python 3.12+ and FastAPI's synchronous handler model

## Considered Options

- Use the existing `vultron/bt/` custom engine for handler BT execution
- Introduce `py_trees` (v2.2.0+) as the handler-level BT library
- Implement ad-hoc procedural logic in handlers without a BT library

## Decision Outcome

Chosen option: "Introduce `py_trees` as the handler-level BT library."

Justification:

- `py_trees` provides standard BT semantics, blackboard state management,
  and tree visualization — all needed for handler-level execution.
- Reusing `vultron/bt/` would couple simulation internals to the API runtime
  and risk breaking existing simulation code.
- Procedural logic in handlers is workable for simple cases but grows
  unwieldy for complex, multi-step workflows; BTs provide structured
  composition.
- `py_trees` is a mature, well-tested library used in robotics and AI; it
  aligns with the BT literature referenced in ADR-0002.

### Consequences

- Good:
  - Standard BT semantics (SUCCESS/FAILURE/RUNNING) align with spec
    requirements
  - Built-in blackboard management simplifies inter-node state passing
  - `py_trees.display` utilities provide tree visualization for debugging
  - Clean separation: `vultron/bt/` remains the simulation engine;
    `vultron/behaviors/` uses `py_trees` for API handler execution
  - Proof-of-concept validated in Phase BT-1: P99 execution time < 1ms
- Bad / Tradeoffs:
  - Adds an external dependency (`py_trees ^2.2.0`)
  - Introduces a bridge layer (`vultron/behaviors/bridge.py`) to adapt
    `py_trees` execution context to Vultron's DataLayer and handler protocol
  - Blackboard key naming constraints (no slashes; use simplified keys)

## Validation

- Phase BT-1 proof-of-concept: `validate_report` handler refactored to use
  `py_trees` BT execution via `BTBridge`
- 78 BT tests passing in `test/behaviors/`
- Performance baseline: P50=0.44ms, P95=0.69ms, P99=0.84ms (well within
  100ms target)
- All 456 existing tests continue to pass (no regressions)

## More Information

- `vultron/behaviors/bridge.py`: `BTBridge` adapter class
- `vultron/behaviors/helpers.py`: DataLayer-aware base node classes
- `vultron/behaviors/report/`: Report validation BT implementation
- `specs/behavior-tree-integration.md`: BT integration requirements
- Related ADRs: ADR-0002 (BT rationale), ADR-0003 (custom engine retained
  for simulation), ADR-0007 (dispatcher architecture)
