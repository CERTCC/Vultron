---
source: NOTES-coordination-agents--call-out-point-abstraction-layer
timestamp: '2026-09-17T17:13:37.985134+00:00'
title: Call-Out Point Abstraction Layer
type: note
---

**Archived:** 2026-09-17
**Reason:** (a,b) factory-injection/bundle design delivered; documented in call-out-configuration.md
**Superseded by:** vultron/core/behaviors/call_out/; notes/call-out-configuration.md

---

## Call-Out Point Abstraction Layer

> **Provisional design — formed in sand**: The pattern described here
> reflects the intent after the #867 planning session. It will be validated
> by #1151 (one exemplar per agent shape) and may be refined as the
> shape-based implementation issues (FUZZ-08d through FUZZ-08g) work through
> the full 93-node inventory. See ADR-0025 for the full decision record.

### Core concept: fuzzer as adapter

Every fuzzer node in `vultron/demo/fuzzer/` is a **call-out point adapter**
— a probabilistic stand-in for logic that has not yet been implemented. The
goal of the abstraction layer is to make the adapter *swappable* at tree
construction time, so that real implementations can replace the fuzzer
incrementally (node by node, scenario by scenario) without changing the BT
tree structure.

### Factory-based injection

The mechanism is **factory-based injection**, consistent with how BT trees
are already constructed elsewhere in the codebase:

- Each call-out point is expressed as a **backend factory**: a callable
  that produces a `py_trees.behaviour.Behaviour` node honouring the
  call-out point's blackboard contract.
- The fuzzer factory is the default for each call-out point.
- Tree-building functions that contain call-out points accept the factory
  (or a mapping of factories) as a parameter, with the fuzzer as the
  default. Swapping is a construction-time operation.

### Blackboard contracts

Every call-out point has a **blackboard contract**:

- **Input keys**: blackboard keys the node reads before dispatching
- **Output keys + types**: blackboard keys the node writes on `SUCCESS`
- **Signal**: `SUCCESS` or `FAILURE` to the tree

The fuzzer backend MUST honour the same contract as a real backend: on
`SUCCESS`, it writes synthetic data to the declared output keys. This ensures
downstream nodes are unaffected by the fuzzer-vs-real swap.

Blackboard contract requirements are specified in
`specs/behavior-tree-integration.yaml` BT-18-001 through BT-18-004.

### Shape base classes

Each of the five capability shapes (Evaluator, Retriever, Sentinel, Composer, Actuator)
defines a **lifecycle pattern** for how the node reads input, dispatches, and
writes output. Concrete call-out point nodes subclass the appropriate shape
base class. The shape base class is NOT a generic reusable class; it
documents the lifecycle pattern and defines the hook points for subclasses.

Note: Sentinel has **no call-out point base class** — it operates exclusively
on the call-in surface and has no BT node. The base classes below are for the
four shapes that appear at call-out points.

- **Evaluator**: reads situation context from the blackboard; writes a
  structured recommendation to a declared output key; `SUCCESS` = answer
  available, `FAILURE` = cannot evaluate
- **Retriever**: reads a query from the blackboard; writes structured facts
  to a declared output key (including boolean/binary results — see ADR-0024
  § "Boolean external queries are Retrievers, not Sentinels"); `SUCCESS` =
  facts retrieved, `FAILURE` = not found or unavailable
- **Composer**: reads composition context from the blackboard; writes a
  generated artifact to a declared output key; `SUCCESS` = artifact ready,
  `FAILURE` = generation failed
- **Actuator**: reads trigger context from the blackboard; invokes an external
  system; no output keys written; `SUCCESS` = side effect confirmed, `FAILURE`
  = side effect failed

### Implementation chain

```text
#1150 — Update catalog: add cross-refs (vultron/bt/ → demo/fuzzer/) +
         capability-shape classification per node [DONE]

#1151 — Design exemplar: one call-out point per shape [DONE]
         Delivered:
         - CallOutBackendFactory type alias (vultron.core.behaviors.call_out_point)
         - Five shape mixin classes (vultron.demo.fuzzer.call_out_point):
             EvaluatorCallOutPoint, RetrieverCallOutPoint, ComposerCallOutPoint,
             ActuatorCallOutPoint, SentinelCallOutPoint
         - Exemplar nodes (with blackboard contract docstrings + output_keys):
             EvaluateReportCredibility (Evaluator) — validate.py
             GatherValidationInfo (Retriever) — validate.py
             OnAccept / OnDefer (Actuator) — prioritize.py
             PrepareReport (Composer) — publication.py
             NewValidationInfoSentinel (Sentinel) — call_out_point.py (illustrative)
         - Factory injection into:
             create_validate_report_tree (credibility_factory, validity_factory,
               gather_info_factory [Phase 2 reserved])
             create_prioritize_subtree (on_accept_factory, on_defer_factory)
             create_publication_tree (prepare_report_factory) [new Phase 1 stub]
         - ADR-0025 advanced from proposed → accepted

#1152 — Wire demo BTs: audit BTs for implicit policy nodes; externalize
         as call-out points with deterministic (AlwaysSucceed/AlwaysFail)
         backends; add one randomized demo

FUZZ-08a-quart (#1266) — Reclassify remaining 17 Sentinel-labeled nodes
                           (likely all become Retriever or ProtocolInternal)

FUZZ-08d — All Evaluator-shaped call-out points (cross-domain)
         Prototype instance landed in #1330 (issue #1299):
           EvaluateDefaultRolesNode (Evaluator, CM-16-003) —
             vultron/core/behaviors/case/nodes/actor.py
             Writes suggested_roles=[CVDRole.VENDOR] to blackboard;
             call-out point for actor role assignment in the
             Offer(Actor, Case) received-side BT.
FUZZ-08e — All Retriever-shaped call-out points (cross-domain)
FUZZ-08f (#1175) — All Sentinel-shaped call-out points (cross-domain)
                   [scope likely zero after FUZZ-08a-quart]
FUZZ-08g — All Composer-shaped call-out points (cross-domain)
(FUZZ-08h covers Actuator per the revised 5-shape taxonomy)

Domain sweep audits — verify completeness per domain after shape rollout
```

---
