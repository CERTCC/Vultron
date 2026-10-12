---
stakeholder_type: [project-contributor]
---

# BT fuzzer node catalog

Fuzzer nodes are stub behavior tree nodes in the `vultron/bt/` protocol simulation.
Each one is built with the `vultron.bt.base.factory.fuzzer` factory and wraps a probabilistic base type from `vultron.bt.base.fuzzer` (such as `AlwaysSucceed` or `UsuallyFail`) in place of real-world logic.

Every fuzzer node is a **call-out point**: a place where the tree cannot decide the outcome by itself.
Deciding it takes one of the following:

- **External data**, such as threat intelligence feeds, exploit databases, vulnerability registries, or contact directories.
- **State of the world**, such as whether a fix is deployed, a threat has materialized, or a timer has elapsed.
- **Human judgment**, such as an analyst's decision on report validity, embargo terms, or publication priority.
- **Input from another agent**, such as a scoring system (CVSS, SSVC), a policy engine, or an orchestration service.

The `vultron.demo.fuzzer` package ports these stubs to the py_trees prototype, where `vultron.core.behaviors` factories accept them as call-out backends.

---

## Catalog pages

| Page | Simulator tree | Simulator module |
|---|---|---|
| [Vulnerability discovery](vul-discovery.md) | `DiscoverVulnerabilityBt` | `vultron/bt/vul_discovery/` |
| [Embargo management](embargo.md) | `EmbargoManagementBt` | `vultron/bt/embargo_management/` |
| [Report validation](rm-validation.md) | `RMValidateBt` | `vultron/bt/report_management/` |
| [Report prioritization](rm-prioritization.md) | `RMPrioritizeBt` | `vultron/bt/report_management/` |
| [Vulnerability ID assignment](rm-id-assignment.md) | `AssignVulID` | `vultron/bt/report_management/` |
| [Fix development and deployment](rm-fix.md) | `DevelopFix`, `Deployment` | `vultron/bt/report_management/` |
| [Exploit acquisition](rm-exploit.md) | `AcquireExploit` | `vultron/bt/report_management/` |
| [Threat monitoring](rm-threat.md) | `MonitorThreats` | `vultron/bt/report_management/` |
| [Publication](rm-publication.md) | `Publication` | `vultron/bt/report_management/` |
| [Report closure and other work](rm-closure.md) | `RMCloseBt`, `RMDoWorkBt` | `vultron/bt/report_management/` |

The simulator's report-to-others and inbound-message error-handling trees have no catalog page: production has no counterpart for either (ADR-0047, ADR-0049).

---

## Entry format

Each node entry has these fields:

- **Node name**: the Python identifier used in the BT.
- **btz type**: the base type from `vultron.bt.base.fuzzer` and its success probability (see [Base types](#base-types)).
- **Source file**: the path relative to `vultron/bt/`, unless written in full.
- **Parent tree**: the named BT sub-tree the node participates in.
- **Semantic function**: what the node represents in the CVD process.
- **Input dependency**: the kind of real-world input needed to replace it.
- **Notes**: implementation guidance from the source code comments.
- **Automation potential**: one of the [automation potential](#automation-potential) values.
- **New-arch cross-ref**: the matching `vultron.demo.fuzzer.*` class, or N/A for simulation-only nodes.
- **Call-out point shape**: one of the [call-out point shapes](#call-out-point-shapes).
- **Factory-fn placement**: the `vultron.core.behaviors.*` factory that hosts the node and where in the tree it sits, or why no factory hosts it.

---

## Automation potential

- **High**: fully automatable through API calls, metadata queries, or policy-rule evaluation.
- **Medium**: partly automatable with data feeds or policy templates, but edge cases still need human oversight.
- **Low**: inherently human-driven; automation is limited to notifications or task triggers.
- **TerminalPlaceholder**: a placeholder leaf with no decision logic and no external dependency, such as an `AlwaysSucceed` fallback.

---

## Call-out point shapes

Shapes follow ADR-0024 as amended by ADR-0097, and BT-18-013 lists them normatively.
The shape comes from the seam structure, not from the automation potential (BT-18-005).

- **Evaluator**: reads situation context and writes a structured recommendation; `SUCCESS` means a recommendation is available.
- **Retriever**: reads a query and writes structured facts from an external source; `SUCCESS` means the facts were retrieved.
  A synchronous yes-or-no query is a Retriever whose fact is the `SUCCESS` or `FAILURE` result itself, with no output keys (BT-18-006).
- **Composer**: reads composition context and writes a generated artifact; `SUCCESS` means the artifact is ready.
- **Actuator**: receives a trigger and context and invokes an external system for a side effect, such as a notification, a state write, or an API call.
  It returns `SUCCESS` when the side effect is confirmed and writes no content artifact to the blackboard.
- **ProtocolInternal**: the node resolves entirely inside the protocol implementation, with no external input, output, or monitoring seam.
  Use it only for terminal placeholders and structural composites, never because a node is highly automatable (BT-18-005).

Sentinel is not a call-out shape: it is a call-in pattern with no call-out node to classify (ADR-0097).
A few entries still read `Sentinel`; #3424 tracks reclassifying them.

---

## Base types

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
