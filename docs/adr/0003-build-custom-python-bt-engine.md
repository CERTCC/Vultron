---
status: accepted
date: 2023-10-23
created: 2023-10-23
updated: 2023-10-23
revision: 1
amended: "2026-10-09"
deciders: adh
partially_superseded_by: 0008-use-py-trees-for-handler-bt-integration.md
stakeholder_type: [project-contributor]
---
# Build our own Behavior Tree engine in Python

## Context and Problem Statement

We need a Behavior Tree engine to support our Behavior Tree Agent implementation.

## Decision Drivers

- Need to support stochastic behaviors
- Team is most familiar with Python
- Need to support quick prototyping and experimentation

## Considered Options

- BehaviorTree.CPP
- py_trees
- Build our own

## Decision Outcome

Chosen option: "Build our own", because

- It's a good opportunity to learn about Behavior Trees
- py_trees is closely tied to robot operating system (ROS), so it might not be a good fit for our use case
- BehaviorTree.CPP is written in C++, so it would be difficult to integrate with the rest of our Python codebase

This decision can/should be revisited if

- the complexity of building our own Behavior Tree engine becomes too high
- we discover that existing Behavior Tree engines already support features that would be difficult for us to build

In order to mitigate the risk of building our own Behavior Tree engine, we will maintain a modular design
that allows us to swap out our engine for an existing engine if necessary.

### Consequences

Good, because:

- Provides an opportunity to learn more about Behavior Trees
- We can build it in Python, so it should be easy to integrate with the rest of our codebase
- We can build it in a way that supports stochastic behaviors
- We can customize it to our needs

Neutral, because:

- We might discover that we need features that are already supported by existing Behavior Tree engines
- We might find that other Behavior Tree engines are better suited to our needs

Bad, because:

- We have to build and maintain our own Behavior Tree engine
- It's another dependency we have to own and maintain

## Pros and Cons of the Options

### BehaviorTree.CPP

Good, because:

- It's a mature, well-tested Behavior Tree engine

Bad, because:

- It's written in C++, so it would be difficult to integrate with the rest of our Python codebase

### py_trees

Good, because:

- It's written in Python, so it should be easy to integrate with the rest of our codebase
- It seems to be a mature, well-tested Behavior Tree engine

Neutral-to-bad, because:

- It's closely tied to robot operating system (ROS), so it might not be a good fit for our use case

## Amendment — 2026-10-09

The decision stands for the legacy simulator only.
The custom engine in `vultron/bt/` still runs the legacy protocol simulator, the vultrabot demos, and the tests under `test/bt/`.

ADR-0008 chose `py_trees` for handler behavior-tree execution, and kept this engine for the simulator.
ADR-0044 later adopted typed blackboard ports for the `py_trees` nodes under `vultron/core/behaviors/`.
The rules that new code must follow are specified elsewhere, not in this record: BT-02-001 requires handler trees to use a standard library, BT-02-002 freezes `vultron/bt/`, and BT-16-001 places the `py_trees` fuzzer nodes under `vultron/demo/fuzzer/`.

The ROS concern in the original reasoning did not hold: `py_trees` runs without ROS.

- Source: #4391

## More Information

- [BehaviorTree.CPP](https://www.behaviortree.dev/) [GitHub](https://github.com/BehaviorTree/BehaviorTree.CPP)
- [py_trees](https://py-trees.readthedocs.io/en/devel/) [GitHub](https://github.com/splintered-reality/py_trees)
