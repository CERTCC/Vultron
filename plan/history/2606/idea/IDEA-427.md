---
source: IDEA-427
timestamp: '2026-06-10T14:14:09.356271+00:00'
title: 'FUZZ: Re-implement fuzzer nodes as py_trees simulation stubs'
type: idea
---

## Summary

Re-implement the fuzzer/placeholder BT nodes from the original `vultron/bt/`
simulator as `py_trees`-based probabilistic simulation stubs in
`vultron/demo/fuzzer/`. These nodes are **external-dependency touchpoints**:
named integration points where production logic (system integrations, human
decisions, environmental checks) will eventually replace probabilistic stubs.

`vultron/bt/vul_discovery/fuzzer.py` is intentionally excluded — the
`DiscoverVulnerabilityBt` tree operates upstream of real Vultron (which
starts at `Offer(VulnerabilityReport)`).

## Module Layout

| Target module | Source | Nodes |
|---|---|---|
| `vultron/demo/fuzzer/base.py` | `vultron/bt/base/fuzzer.py` | Probabilistic base types |
| `vultron/demo/fuzzer/embargo.py` | `vultron/bt/embargo_management/fuzzer.py` | ~15 embargo nodes |
| `vultron/demo/fuzzer/messaging.py` | `vultron/bt/messaging/inbound/_behaviors/fuzzer.py` | ~1 messaging node |
| `vultron/demo/fuzzer/report_management/` | `vultron/bt/report_management/fuzzer/` | ~70 nodes in submodules |

## Implementation Issues

- #860 FUZZ-01: Base probabilistic infrastructure (blocks all others)
- #861 FUZZ-02: Embargo management nodes
- #862 FUZZ-03: Report validate + prioritize + messaging inbound
- #863 FUZZ-04: VUL ID + fix develop + close + other-work
- #864 FUZZ-05: Fix deploy + monitor threats + acquire exploit
- #865 FUZZ-06: Publication workflow
- #866 FUZZ-07: Report-to-others workflow
- #867 FUZZ-08 (type:Idea): Wire into demo scenarios (deferred)

**Processed**: 2026-06-10 — Epic #427 updated; implementation tracked in
issues #860, #861, #862, #863, #864, #865, #866. Demo wiring deferred to
issue #867 (type:Idea, blocked by all impl issues).
Docs PR: <https://github.com/CERTCC/Vultron/pull/859>.
Spec: `specs/behavior-tree-integration.yaml` BT-16-001–BT-16-005.
Notes: `notes/bt-integration.md` § *py_trees Fuzzer Node Home*.
