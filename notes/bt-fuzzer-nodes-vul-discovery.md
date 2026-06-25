---
title: "BT Fuzzer Nodes: Vulnerability Discovery"
status: active
description: >
  Catalog of fuzzer (stub) BT nodes for the Vulnerability Discovery workflow in
  the Vultron BT simulation.
related_specs:
  - specs/behavior-tree-integration.yaml
related_notes:
  - notes/bt-integration.md
  - notes/bt-fuzzer-nodes.md
relevant_packages:
  - vultron/bt/vul_discovery
---

# BT Fuzzer Nodes: Vulnerability Discovery

These are the stub nodes for `DiscoverVulnerabilityBt`
(`vultron/bt/vul_discovery/behaviors.py`). See
`notes/bt-fuzzer-nodes.md` for background on what fuzzer nodes are and
the full catalog index.

**Fuzzer base types quick reference:**

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

## Vulnerability Discovery

These nodes belong to the `DiscoverVulnerabilityBt` fallback tree
(`vultron/bt/vul_discovery/behaviors.py`), which is one of the four top-level
branches of `CvdProtocolRoot`. The tree models the process by which a
participant with the FINDER role searches for and discovers a new vulnerability.

Note that the `DiscoverVulnerabilityBt` is only needed for the simulation,
and would not be part of a real Vultron implementation. The actual Vultron
system would start with creating and submitting vulnerability reports, which
is essentially the "output" of the discovery process.

### `HaveDiscoveryPriority`

- **Node name**: `HaveDiscoveryPriority`
- **btz type**: `AlwaysSucceed` (p=1.00)
- **Source file**: `vul_discovery/fuzzer.py`
- **Parent tree**: `FindVulnerabilities` (within `DiscoverVulnerabilityBt`)
- **Semantic function**: Condition check — has the participant decided to
  prioritize vulnerability discovery as a current goal?
- **Input dependency**: Organizational priority setting; could be driven by
  human tasking, scheduled policy, or an automated work-queue query
- **Notes**: Always succeeds in simulation to keep the discovery loop active
- **Automation potential**: **High** — static role/capability configuration check; can be fully automated as a lookup against the participant's role metadata or organizational task queue.
- **New-arch cross-ref**: N/A — simulation-only BT not ported to new architecture
- **Call-out point shape**: N/A

### `DiscoverVulnerability`

- **Node name**: `DiscoverVulnerability`
- **btz type**: `ProbablySucceed` (p=0.67)
- **Source file**: `vul_discovery/fuzzer.py`
- **Parent tree**: `FindVulnerabilities` (within `DiscoverVulnerabilityBt`)
- **Semantic function**: Action — execute a vulnerability discovery activity,
  such as fuzzing, code audit, pentesting, or research
- **Input dependency**: Results from a vulnerability research tool, a
  researcher's findings, or an automated scanning system
- **Notes**: Succeeds often enough to drive simulation throughput while still
  modeling that discovery is not guaranteed on every cycle
- **Automation potential**: **Low** — inherently a human or tool-driven research activity (fuzzing, code audit, pentesting); results must be fed in from an external research pipeline.
- **New-arch cross-ref**: N/A — simulation-only BT not ported to new architecture
- **Call-out point shape**: N/A

### `NoVulFound`

- **Node name**: `NoVulFound`
- **btz type**: `AlwaysSucceed` (p=1.00)
- **Source file**: `vul_discovery/fuzzer.py`
- **Parent tree**: `DiscoverVulnerabilityBt`
- **Semantic function**: Fallback leaf — acknowledge that no vulnerability
  was discovered in this tick; keep the overall BT from failing
- **Input dependency**: None (terminal success placeholder); no external
  input needed once we confirm discovery came up empty
- **Notes**: Ensures the discovery branch always succeeds so the top-level
  sequence can continue to other work
- **Automation potential**: **N/A** — terminal success placeholder; no real decision logic required.
- **New-arch cross-ref**: N/A — simulation-only BT not ported to new architecture
- **Call-out point shape**: N/A

---
