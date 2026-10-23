---
source: IDEA-867
timestamp: '2026-06-25T17:01:33.294362+00:00'
title: 'FUZZ-08: Wire fuzzer nodes into demo scenarios (planning)'
type: idea
---

## Original umbrella summary

Umbrella planning issue for wiring the ported `vultron/demo/fuzzer/` nodes into
demo scenarios as **call-out points** — named integration seams where the BT
calls out to an external party (initially the fuzzer, later real implementations
or coordination agents).

FUZZ-01 through FUZZ-07 (#860–#866) are complete. This umbrella tracked the
follow-on work of exposing those nodes as swappable abstractions and wiring
them into demo scenarios.

## Planning session outcome (2026-06-25)

Gap analysis and issue review session. #1150, #1151, and #1152 were revised
with clearer scope. Six new issues were created.

**Docs PR**: #1172 — ADR-0025 (call-out point abstraction layer design),
BT-18 spec group (blackboard contract requirements), coordination-agents.md
abstraction section.

**Key design decisions:**

- Call-out point nodes use **factory-based injection** (consistent with
  existing BT factory pattern): each tree builder accepts the backend factory
  as a parameter with the fuzzer as the default.
- Each call-out point has a **blackboard contract**: declared input keys and
  output keys (with types); fuzzer backends MUST write synthetic
  type-conformant output to the same keys as real backends.
- The four agent shapes (Sentinel, Evaluator, Retriever, Composer from
  ADR-0024) each define a lifecycle pattern for their nodes.
- Implementation is **shape-based** (not domain-based): one issue per shape
  covers all nodes of that shape across all domains, ensuring DRY base classes
  and consistent patterns.
- The design is **provisional** ("formed in sand"): ADR-0025 status is
  `proposed` and is expected to be refined during exemplar implementation
  (#1151) before the shape rollout begins.

**Revised implementation issues:**

- #1150 — Update catalog: add new-arch cross-refs (vultron/bt/ → demo/fuzzer/)
  - call-out point shape annotations + terminology alignment
- #1151 — Design: shape base classes + one exemplar per shape + blackboard
  contract documentation (provisional)
- #1152 — Demo wiring: audit BTs for implicit policy nodes, externalize as
  call-out points with deterministic backends, add one randomised demo

**New implementation issues:**

- #1173 (FUZZ-08d): All Evaluator-shaped call-out points (cross-domain)
- #1174 (FUZZ-08e): All Retriever-shaped call-out points (cross-domain)
- #1175 (FUZZ-08f): All Sentinel-shaped call-out points (cross-domain)
- #1176 (FUZZ-08g): All Composer-shaped call-out points (cross-domain)
- #1177 (FUZZ-08h): Domain sweep audit (breadcrumb — blocked by 08d–08g)
- #1178: Fully-fuzzed protocol simulation scenario (under #1093 Demo Scenarios)

**Processed**: 2026-06-25 — implementation tracked in #1150, #1151, #1152,
\#1173, #1174, #1175, #1176, #1177, #1178.
Docs PR: <https://github.com/CERTCC/Vultron/pull/1172>.
