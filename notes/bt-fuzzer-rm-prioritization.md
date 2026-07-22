---
title: "BT Fuzzer Nodes: RM Report Prioritization"
status: active
description: >
  Catalog of fuzzer (stub) BT nodes for the Report Prioritization sub-workflow
  (`RMPrioritizeBt`): priority assessment, severity ranking, and
  prioritization-info sentinel nodes used in simulation.
related_specs:
  - specs/behavior-tree-integration.yaml
related_notes:
  - notes/bt-fuzzer-nodes-report-management.md
  - notes/bt-integration.md
  - notes/bt-canonical-reference.md
  - notes/bt-fuzzer-nodes.md
relevant_packages:
  - vultron/bt/report_management
---

## Report Prioritization

These nodes belong to `RMPrioritizeBt`
(`vultron/bt/report_management/_behaviors/prioritize_report.py`), which
models the process of deciding whether to accept (engage with) or defer
(set aside) a validated vulnerability report.

### `NoNewPrioritizationInfo`

- **Node name**: `NoNewPrioritizationInfo`
- **btz type**: `ProbablySucceed` (p=0.67)
- **Source file**: `report_management/fuzzer/prioritize_report.py`
- **Parent tree**: `RMPrioritizeBt`
- **Semantic function**: Condition — check whether new information has
  arrived that should trigger re-prioritization of the report
- **Input dependency**: Report change detection; metadata timestamp or
  event subscription
- **Notes**: Succeeds more often than not to avoid redundant re-evaluation
- **Automation potential**: **High** — metadata timestamp or case-update event check; fully automatable.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.prioritize.NoNewPrioritizationInfo`
- **Call-out point shape**: ProtocolInternal — reads a change-detection flag written by the upstream
  `NewPrioritizationInfoSentinel` agent (see stub entry below). The external agent seam is at the
  Sentinel (event subscription or polling hook), not at this BT condition check.
  (Category 2 per issue #1199 triage — consumes a flag written by an upstream Sentinel.)
- **Factory-fn placement**:
  `vultron.core.behaviors.report.prioritize_tree.create_prioritize_subtree` —
  ProtocolInternal condition check at the top of `PrioritizeBT` Selector; the retry
  skip-if-no-new-info check belongs here when the full re-prioritization
  loop is implemented (Phase 2)

### `NewPrioritizationInfoSentinel` *(upstream Sentinel stub)*

- **Node name**: `NewPrioritizationInfoSentinel`
- **btz type**: *(not a BT node — upstream agent seam)*
- **Source file**: *(to be determined)*
- **Parent tree**: *(runs independently, outside the BT tick loop)*
- **Semantic function**: Sentinel — monitors the case record for new
  prioritization-relevant events (e.g., updated SSVC scoring data, new
  threat intelligence, CVSS score update) and writes a change-detection
  flag that `NoNewPrioritizationInfo` consumes.
- **Input dependency**: Case management system event stream; metadata
  timestamp comparison or event subscription on prioritization-relevant
  case fields (e.g., SSVC decision points, CVSS scores).
- **Notes**: This is the real call-out point implied by
  `NoNewPrioritizationInfo`. The upstream Sentinel registers with an
  external event source and writes a flag to the BT blackboard / local
  DataLayer; `NoNewPrioritizationInfo` reads that flag each BT tick.
  Implementation tracked in FUZZ-08f.
- **Automation potential**: **High** — event subscription on the case record
  or metadata timestamp comparison; fully automatable.
- **New-arch cross-ref**: `vultron.demo.fuzzer.call_out_point.NewPrioritizationInfoSentinel`
- **Call-out point shape**: Sentinel — registers with a case-event source;
  fires a change-detection signal into the BT blackboard when new
  prioritization-relevant information arrives; no output keys beyond the flag.
- **Factory-fn placement**: FUZZ-08f (planned) — upstream agent seam, not
  placed inside the BT tree; writes a change-detection flag to the blackboard
  key read by `NoNewPrioritizationInfo` at the top of the
  `PrioritizeBT` Selector in
  `vultron.core.behaviors.report.prioritize_tree.create_prioritize_subtree`

### `EnoughPrioritizationInfo`

- **Node name**: `EnoughPrioritizationInfo`
- **btz type**: `UsuallySucceed` (p=0.75)
- **Source file**: `report_management/fuzzer/prioritize_report.py`
- **Parent tree**: `RMPrioritizeBt`
- **Semantic function**: Condition — determine whether there is enough
  context to make an accept/defer decision
- **Input dependency**: Human analyst assessment or automated completeness
  check (e.g., SSVC decision point availability)
- **Notes**: Insufficient info triggers a gathering phase
- **Automation potential**: **Medium** — availability of SSVC decision-point data (e.g., CVSS score, exploitation status) is automatable; the sufficiency judgment for a final accept/defer decision usually involves human analyst review.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.prioritize.EnoughPrioritizationInfo`
- **Call-out point shape**: Evaluator
- **Factory-fn placement**:
  `vultron.core.behaviors.report.prioritize_tree.create_prioritize_subtree` —
  Evaluator condition guard in the `PrioritizeBT` Sequence (Phase 2); gate
  before the info-gathering loop that `GatherPrioritizationInfo` populates

### `GatherPrioritizationInfo`

- **Node name**: `GatherPrioritizationInfo`
- **btz type**: `AlmostAlwaysSucceed` (p=0.90)
- **Source file**: `report_management/fuzzer/prioritize_report.py`
- **Parent tree**: `RMPrioritizeBt`
- **Semantic function**: Action — collect additional context needed to
  support a prioritization decision (e.g., severity scores, asset
  inventory, threat landscape data)
- **Input dependency**: Human analyst research, CVSS/SSVC scoring tools,
  asset management systems, threat intelligence feeds
- **Notes**: Succeeds almost always in simulation to keep the workflow
  progressing
- **Automation potential**: **Medium** — fetching CVSS scores, EPSS scores, NVD data, and asset inventory is fully automatable via APIs; analyst interpretation and gap-filling still requires human involvement.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.prioritize.GatherPrioritizationInfo`
- **Call-out point shape**: Retriever
- **Factory-fn placement**:
  `vultron.core.behaviors.report.prioritize_tree.create_prioritize_subtree` —
  Retriever action node in the info-gathering Sequence (Phase 2), triggered
  when `EnoughPrioritizationInfo` returns FAILURE

### `OnDefer`

- **Node name**: `OnDefer`
- **btz type**: `AlwaysSucceed` (p=1.00)
- **Source file**: `report_management/fuzzer/prioritize_report.py`
- **Parent tree**: `RMPrioritizeBt`
- **Semantic function**: Action — execute site-specific tasks when a report
  is deferred (e.g., notify stakeholders, schedule a follow-up, update
  case status)
- **Input dependency**: Integration hook; notification APIs, task scheduling
  services, case management system updates
- **Notes**: Always succeeds in simulation; must be idempotent in production
- **Automation potential**: **High** — stakeholder notifications, follow-up scheduling, and state updates are all automatable via integration APIs.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.prioritize.OnDefer`
- **Call-out point shape**: Actuator — fires integration hooks on report deferral; invokes notification APIs, task-scheduling services, and case-management state writes. There is no content artifact placed on the blackboard; the side effects in external systems are the seam.
- **Factory-fn placement**:
  `vultron.core.behaviors.report.prioritize_tree.create_prioritize_subtree` —
  Actuator effect node appended to `DeferCaseTriggerBT` Sequence (in
  `create_defer_case_tree`), after `TransitionParticipantRMtoDeferred` and
  the sender-side subtree

### `OnAccept`

- **Node name**: `OnAccept`
- **btz type**: `AlwaysSucceed` (p=1.00)
- **Source file**: `report_management/fuzzer/prioritize_report.py`
- **Parent tree**: `RMPrioritizeBt`
- **Semantic function**: Action — execute site-specific tasks when a report
  is accepted (e.g., notify stakeholders, initialize case workflow, assign
  to a team)
- **Input dependency**: Integration hook; notification APIs, workflow
  initialization, case management system updates
- **Notes**: Always succeeds in simulation; must be idempotent in production
- **Automation potential**: **High** — stakeholder notifications, workflow initialization, and state updates are all automatable via integration APIs.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.prioritize.OnAccept`
- **Call-out point shape**: Actuator — fires integration hooks on report acceptance; invokes notification APIs, workflow-initialization services, and case-management state writes. There is no content artifact placed on the blackboard; the side effects in external systems are the seam.
- **Factory-fn placement**:
  `vultron.core.behaviors.report.prioritize_tree.create_prioritize_subtree` —
  Actuator effect node appended to `EngageCaseTriggerBT` Sequence (in
  `create_engage_case_tree`), after `TransitionParticipantRMtoAccepted` and
  the sender-side subtree

---
