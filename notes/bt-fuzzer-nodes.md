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
- **Automation potential**: High / Medium / Low / N/A (see below)

**Automation potential categories:**

- **High** — fully automatable via API calls, metadata queries, or
  policy-rule evaluation
- **Medium** — partially automatable with data feeds or policy templates,
  but human oversight or judgment still needed for edge cases
- **Low** — inherently human-driven; automation limited to notifications
  or task triggers
- **N/A** — terminal placeholder nodes with no real decision logic

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
