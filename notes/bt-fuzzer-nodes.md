---
title: "Vultron BT Fuzzer Nodes: Call-Out Points"
status: active
description: >
  Index and background for fuzzer (stub) BT nodes in the Vultron BT
  simulation. Fuzzer nodes are call-out points cataloged by domain area
  in per-topic sub-files.
related_specs:
  - specs/behavior-tree-integration.yaml
related_notes:
  - notes/bt-integration.md
  - notes/coordination-agents.md
  - notes/bt-fuzzer-nodes-vul-discovery.md
  - notes/bt-fuzzer-nodes-embargo.md
  - notes/bt-fuzzer-nodes-report-management.md
  - notes/bt-fuzzer-nodes-messaging.md
relevant_packages:
  - vultron/bt/report_management
  - vultron/bt/embargo_management
  - vultron/bt/messaging
  - vultron/bt/vul_discovery
---

# Vultron BT Fuzzer Nodes: Call-Out Points

## Background and Purpose

This document is the **index** for the fuzzer node catalog. Fuzzer nodes are
stub implementations created with the `vultron.bt.base.factory.fuzzer`
factory function. Each one wraps a probabilistic base type from
`vultron.bt.base.fuzzer` (e.g., `AlwaysSucceed`, `UsuallyFail`,
`ProbablySucceed`) to stand in for real-world logic that has not yet been
implemented.

Every fuzzer node is a **call-out point** — a location in the protocol
simulation where the BT cannot proceed automatically. One of the following
is required to determine the outcome:

- **External data source**: e.g., threat intelligence feeds, exploit
  databases, vulnerability registries, contact directories
- **State of the world**: e.g., whether a fix has been deployed, whether a
  threat has materialized, whether a timer has elapsed
- **Human judgment**: e.g., analyst decisions on report validity, embargo
  terms, publication priorities, effort thresholds
- **Decision-support input from another agent**: e.g., automated scoring
  systems (CVSS, SSVC), policy engines, orchestration services

### Entry Format

Each fuzzer node entry in the sub-files has these fields:

- **Node name**: The Python identifier used in the BT
- **btz type**: The probabilistic base type from `vultron.bt.base.fuzzer`
  and its approximate success probability in the simulation
- **Source file**: Path relative to `vultron/bt/`
- **Parent tree**: The named BT sub-tree this node participates in
- **Semantic function**: What this node represents in the CVD process
- **Input dependency**: The kind of real-world input needed to replace it
- **Notes**: Any implementation guidance from the source code comments
- **Automation potential**: High / Medium / Low / TerminalPlaceholder (see below)
- **New-arch cross-ref**: The corresponding `vultron.demo.fuzzer.*` class
  in the py_trees-based prototype (added in FUZZ-08a / PR #1179); N/A for
  simulation-only nodes not ported to the new architecture
- **Call-out point shape**: Evaluator, Retriever, Sentinel, Composer, or
  ProtocolInternal — per the agent shape taxonomy in
  `docs/adr/0024-coordination-agent-taxonomy.md` (added in FUZZ-08a / PR
  #1179; reclassified in issue #1188). Use `ProtocolInternal` only for
  nodes that are terminal placeholders or structural composites with no
  external input or output seam. See BT-18-005: shape MUST be determined
  by the ADR-0024 seam-structure decision tree, independently of automation
  potential.
- **Factory-fn placement**: The module-qualified `vultron.core.behaviors.*`
  factory function that hosts (or should host) this call-out point node in
  the prototype BT, with ordering hints indicating where in the tree the node
  is inserted (e.g., guard vs effect, and which composite it belongs to).
  Use `FUTURE: vultron.core.behaviors.<module>.create_<name>_tree` (with
  a reference to the tracking issue) for nodes whose target factory function
  does not yet exist. N/A for nodes that map to no prototype factory
  function (e.g., simulation-only nodes).

**Automation potential categories:**

- **High** — fully automatable via API calls, metadata queries, or
  policy-rule evaluation
- **Medium** — partially automatable with data feeds or policy templates,
  but human oversight or judgment still needed for edge cases
- **Low** — inherently human-driven; automation limited to notifications
  or task triggers
- **TerminalPlaceholder** — terminal placeholder node with no real decision
  logic (e.g., `AlwaysSucceed` fallback leaf); no external dependency exists

**Call-out point shape values (per ADR-0024):**

- **Sentinel** — binary condition monitor; no output keys; signals
  `SUCCESS`/`FAILURE` only
- **Evaluator** — reads situation context; writes a structured
  recommendation; `SUCCESS` = recommendation available
- **Retriever** — reads a query; writes structured facts from an external
  source; `SUCCESS` = facts retrieved
- **Composer** — reads composition context; writes a generated artifact;
  `SUCCESS` = artifact ready
- **ProtocolInternal** — node resolves entirely within the protocol
  implementation; no external input, output, or monitoring seam exists.
  Use this value only for terminal placeholders and structural composites
  that have no call-out point. Do NOT use `ProtocolInternal` because a
  node's automation potential is High — those nodes have an external seam
  and belong to one of the four shapes above (BT-18-005).

### Fuzzer Base Types (Quick Reference)

| btz type | Success probability |
|---|---|
| `AlwaysSucceed` | 1.00 |
| `AlmostCertainlySucceed` | 0.93 |
| `AlmostAlwaysSucceed` | 0.90 |
| `UsuallySucceed` | 0.75 |
| `OftenSucceed` / `LikelySucceed` | 0.70 |
| `ProbablySucceed` | 0.67 |
| `UniformSucceedFail` / `RandomSucceedFail` | 0.50 |
| `SuccessOrRunning` | 0.50 (never fails; returns SUCCESS or RUNNING) |
| `ProbablyFail` | 0.33 |
| `OftenFail` | 0.30 |
| `UsuallyFail` | 0.25 |
| `AlmostAlwaysFail` / `RarelySucceed` | 0.10 |
| `AlmostCertainlyFail` | 0.07 |
| `OneInTwenty` | 0.05 |
| `OneInOneHundred` | 0.01 |
| `OneInTwoHundred` | 0.005 |
| `AlwaysFail` | 0.00 |

---

## Sub-Files by Domain Area

| File | Domain | BT Module |
|---|---|---|
| `notes/bt-fuzzer-nodes-vul-discovery.md` | Vulnerability Discovery | `vultron/bt/vul_discovery/` |
| `notes/bt-fuzzer-nodes-embargo.md` | Embargo Management | `vultron/bt/embargo_management/` |
| `notes/bt-fuzzer-nodes-report-management.md` | Report Management (validation, prioritization, ID, fix, exploit, threat, publication, reporting, closure) | `vultron/bt/report_management/` |
| `notes/bt-fuzzer-nodes-messaging.md` | Inbound Message Handling | `vultron/bt/messaging/` |

---
