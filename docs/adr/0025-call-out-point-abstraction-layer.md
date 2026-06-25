---
status: proposed
date: 2026-06-25
deciders: [adh]
---

# Call-Out Point Abstraction Layer: Factory-Based Injection with Typed Backends

## Context and Problem Statement

Vultron's Behavior Trees contain **call-out points** — nodes where the
protocol cannot proceed autonomously and must request input from an external
party (see ADR-0024 for the taxonomy of agent shapes). After FUZZ-01 through
FUZZ-07 (#860–#866), each call-out point has a probabilistic fuzzer node as
its stand-in. The fuzzer is not a permanent implementation: it is an adapter
that will be replaced over time by real data lookups, policy evaluations, or
coordination agents.

Before those replacements can happen, the call-out points must be expressed
as proper injection seams: the BT tree must be built so that the fuzzer is
the *default* backend, not the *only* option. Without an abstraction layer,
swapping any call-out point requires finding and editing the concrete node
class instead of injecting a different factory — and with roughly 93 call-out
point nodes across all domains, the maintenance burden is unacceptable.

The design question is: **What mechanism makes each call-out point backend
swappable while remaining consistent with the existing py_trees Behaviour
pattern, factory-function conventions, and blackboard contract model?**

> **Design status — formed in sand, not concrete**: This ADR captures the
> forward-looking intent after one planning session. The design will be
> exercised in #1151 (one exemplar per agent shape) and is expected to
> converge after two or three concrete implementations across different
> domain areas. Implementers working on the shape-based follow-on issues
> (FUZZ-08d through FUZZ-08g) SHOULD refine this ADR if the pattern proves
> incorrect or incomplete. The ADR status will advance from `proposed` to
> `accepted` once the exemplars validate the approach.

## Decision Drivers

- Must be consistent with the existing BT factory-function pattern
  (tree composition functions, not ad-hoc node instantiation)
- Must allow individual call-out points to be swapped without changing the
  calling tree structure (incremental replacement)
- Must maintain the same blackboard contract whether the backend is a fuzzer
  or a real implementation — downstream nodes must be unaffected by the swap
- Must keep simulation artifacts (`vultron/demo/fuzzer/`) out of
  `vultron/core/behaviors/` (BT-16-001)
- Must be compatible with the four agent shapes from ADR-0024 (Sentinel,
  Evaluator, Retriever, Composer), each of which has different input/output
  semantics
- Must support partial replacement: a scenario can use real implementations
  for some call-out points and fuzzer backends for others in the same run

## Considered Options

1. **No abstraction** — leave fuzzer nodes as concrete hardcoded classes;
   require code edits to swap backends
2. **Node-level strategy injection** — define a
   `CallOutPointBehaviour(Behaviour)` base class with an injected `backend`
   callable; require subclassing per call-out point
3. **Per-tree parameter injection** — each tree-building function has named
   parameters for its call-out point factories (`eval_validity=make_fuzzer`,
   `eval_priority=make_fuzzer`, …); swapping is explicit but verbose
4. **Registry-based injection** — a `CallOutRegistry` maps call-out point
   names to factory callables; tree builders accept one `registry` argument;
   mirrors the `USE_CASE_MAP`/`SEMANTIC_REGISTRY` pattern
5. **Factory-protocol injection** — each call-out point is a typed callable
   Protocol (`CallOutFactory = Callable[[str], Behaviour]`); individual
   tree builders accept a mapping or single typed factory per call-out point;
   swapping is done at construction time

## Decision Outcome

Chosen option: **factory-protocol injection (Option 5)**, refined by
borrowing the registry-consolidation idea from Option 4 for tree builders
that have multiple call-out points.

The concrete form:

1. Each call-out point type is defined by its **blackboard contract**: a
   declared set of input keys (read before the node runs), output keys
   (written to on SUCCESS), and types for each. The contract is documented
   in the node's docstring and — for nodes that produce data — in
   `specs/behavior-tree-integration.yaml` under BT-17.

2. A call-out point **backend factory** is a callable with a defined
   signature:

   ```python
   # Minimal form: factory produces a Behaviour with a known blackboard contract
   CallOutBackendFactory = Callable[[str], py_trees.behaviour.Behaviour]
   ```

   The factory is responsible for producing a node that honours the
   call-out point's blackboard contract.

3. The **fuzzer backend factory** is the default for each call-out point.
   It produces a probabilistic `WeightedBehavior` subclass that writes
   synthetic data to the required output keys (where applicable), matching
   the contract that a real backend would satisfy.

4. Tree-building functions that contain call-out points accept the factory
   (or a mapping of factories) as a parameter with the fuzzer factory as
   the default. This is the canonical swap mechanism.

5. The four agent shapes (Evaluator, Retriever, Sentinel, Composer from
   ADR-0024) each define a **lifecycle pattern** — how the node reads
   input from the blackboard, dispatches to the backend, and writes output
   back. Concrete call-out point nodes subclass the appropriate shape base
   class and declare their specific I/O keys and types. The shape base
   class is NOT reusable generically; it documents the lifecycle pattern and
   defines the hook points.

### Consequences

- Good, because it is consistent with the existing BT factory pattern and
  does not require a new base-class hierarchy to be invented from scratch
- Good, because individual call-out points can be swapped independently;
  a scenario can mix fuzzer and real backends node by node
- Good, because fuzzer backends maintain the same blackboard contract as
  real backends, making swap transparent to downstream nodes
- Good, because the shape base classes document the lifecycle pattern for
  each agent shape, making the code self-explanatory
- Neutral, because tree builders gain new parameters (one per call-out
  point or a single registry mapping); this is a small API surface increase
- Bad/uncertain, because the exact factory signature (positional args,
  configuration struct, or keyword-only) is not yet fully specified — this
  must be settled during the exemplar implementation in #1151
- Bad/uncertain, because the blackboard output contract for data-producing
  nodes (Evaluators, Retrievers, Composers) requires explicit declaration
  per node — this is documentation work that must be done alongside
  implementation

## Pros and Cons of the Options

### Option 1: No abstraction

- Bad, because swapping any backend requires editing the concrete class
- Bad, because fuzzer logic is permanently coupled to the call-out point
- Bad, because 93 nodes would each need to be touched individually

### Option 2: Node-level strategy injection

- Good, because each node clearly shows its injectable backend
- Neutral, because subclassing is familiar to py_trees users
- Bad, because it requires refactoring all 93 existing fuzzer nodes
- Bad, because the injected callable type varies per node (each has a
  different I/O contract); a single `Callable` type alias doesn't express this

### Option 3: Per-tree parameter injection

- Good, because explicit parameter names make dependencies visible
- Bad, because tree builders accumulate many parameters (some BT trees have
  5–10 call-out points each), making signatures unwieldy
- Bad, because adding a new call-out point requires changing the tree
  builder's signature and all call sites

### Option 4: Registry-based injection

- Good, because it mirrors the existing `USE_CASE_MAP` dispatch table pattern
- Good, because a single `registry` argument keeps tree builder signatures
  small regardless of the number of call-out points
- Neutral, because registry lookup introduces a name-coupling risk (typo in
  the registry key silently uses the wrong backend or raises at runtime)
- Good, partially adopted: the registry idea is used for tree builders that
  contain multiple call-out points (keeps signature clean)

### Option 5: Factory-protocol injection (chosen)

- Good, because it is consistent with existing factory-function conventions
- Good, because typed callable Protocols make the contract explicit
- Good, because swapping is a construction-time operation, not a runtime
  configuration dependency
- Neutral, because the exact factory Protocol signature must be finalized
  during exemplar implementation — it cannot be fully specified without
  working through concrete cases

## Validation

- #1151 implements one exemplar per agent shape; each exemplar must
  demonstrate the factory-based swap (fuzzer default → real backend).
- Shape-based implementation issues (FUZZ-08d through FUZZ-08g) apply the
  pattern to all 93 nodes. If the exemplar pattern requires revision for any
  shape, this ADR must be updated before the corresponding shape issue
  begins.
- `specs/behavior-tree-integration.yaml` BT-18 captures the blackboard
  contract requirements that every call-out point implementation must satisfy.

## More Information

- ADR-0024: Coordination Agent Taxonomy (call-out point concept and the four
  agent shapes)
- `notes/coordination-agents.md`: design notes for coordination agents
  including the two integration surfaces (call-in vs. call-out)
- `notes/bt-fuzzer-nodes.md` and sub-files: per-node catalog with automation
  potential ratings and agent-shape classifications (completed by #1150)
- Implementation chain: #1150 (catalog update) → #1151 (exemplars) →
  #1152 (demo scenario wiring) → FUZZ-08d–08g (shape rollout)

Generated spec requirements: `specs/behavior-tree-integration.yaml`
BT-18-001 through BT-18-004.
