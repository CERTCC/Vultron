---
stakeholder_type: [project-contributor]
---

# Report prioritization fuzzer nodes

These stub nodes belong to `RMPrioritizeBt` (`vultron/bt/report_management/_behaviors/prioritize_report.py`), the sub-tree that decides whether to accept (engage) or defer a valid report.

See the [fuzzer node index](index.md) for the entry format, the automation-potential and call-out shape values, and the base-type probabilities.

## `NoNewPrioritizationInfo`

- **Node name**: `NoNewPrioritizationInfo`
- **btz type**: `ProbablySucceed` (p=0.67)
- **Source file**: `report_management/fuzzer/prioritize_report.py`
- **Parent tree**: `RMPrioritizeBt`
- **Semantic function**: Condition — check whether new information has arrived that should trigger re-prioritization of the report
- **Input dependency**: Report change detection; metadata timestamp or event subscription
- **Notes**: Succeeds more often than not to avoid redundant re-evaluation
- **Automation potential**: **High** — metadata timestamp or case-update event check; fully automatable.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.prioritize.NoNewPrioritizationInfo`
- **Call-out point shape**: ProtocolInternal — reads a change-detection flag written by the upstream `NewPrioritizationInfoSentinel` (see the next entry).
  The external seam is at that upstream writer, not at this BT condition check.
- **Factory-fn placement**: `vultron.core.behaviors.report.prioritize_tree.create_prioritize_subtree` — ProtocolInternal condition check at the top of `PrioritizeBT` Selector; not wired yet: it belongs here once the re-prioritization loop exists

## `NewPrioritizationInfoSentinel` *(upstream Sentinel stub)*

- **Node name**: `NewPrioritizationInfoSentinel`
- **btz type**: *(not a BT node — upstream agent seam)*
- **Source file**: *(to be determined)*
- **Parent tree**: *(runs independently, outside the BT tick loop)*
- **Semantic function**: Sentinel — monitors the case record for new prioritization-relevant events (e.g., updated SSVC scoring data, new threat intelligence, CVSS score update) and writes a change-detection flag that `NoNewPrioritizationInfo` consumes.
- **Input dependency**: Case management system event stream; metadata timestamp comparison or event subscription on prioritization-relevant case fields (e.g., SSVC decision points, CVSS scores).
- **Notes**: This is the real seam implied by `NoNewPrioritizationInfo`.
  The writer registers with an external event source and writes a flag to the BT blackboard or local DataLayer; `NoNewPrioritizationInfo` reads that flag each tick.
- **Automation potential**: **High** — event subscription on the case record or metadata timestamp comparison; fully automatable.
- **New-arch cross-ref**: `vultron.demo.fuzzer.call_out_point.NewPrioritizationInfoSentinel`
- **Call-out point shape**: Sentinel — pending reclassification: Sentinel is no longer a call-out shape (ADR-0097, BT-18-013), and #3424 tracks reclassifying this entry.
- **Factory-fn placement**: Not placed inside the BT tree; writes the change-detection flag read by `NoNewPrioritizationInfo` at the top of the `PrioritizeBT` Selector in `vultron.core.behaviors.report.prioritize_tree.create_prioritize_subtree`

## `EnoughPrioritizationInfo`

- **Node name**: `EnoughPrioritizationInfo`
- **btz type**: `UsuallySucceed` (p=0.75)
- **Source file**: `report_management/fuzzer/prioritize_report.py`
- **Parent tree**: `RMPrioritizeBt`
- **Semantic function**: Condition — determine whether there is enough context to make an accept/defer decision
- **Input dependency**: Human analyst assessment or automated completeness check (e.g., SSVC decision point availability)
- **Notes**: Insufficient info triggers a gathering phase
- **Automation potential**: **Medium** — availability of SSVC decision-point data (e.g., CVSS score, exploitation status) is automatable; the sufficiency judgment for a final accept/defer decision usually involves human analyst review.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.prioritize.EnoughPrioritizationInfo`
- **Call-out point shape**: Evaluator
- **Factory-fn placement**: `vultron.core.behaviors.report.prioritize_tree.create_prioritize_subtree` — Evaluator condition guard in the `PrioritizeBT` Sequence (not wired yet); gate before the info-gathering loop that `GatherPrioritizationInfo` populates

## `GatherPrioritizationInfo`

- **Node name**: `GatherPrioritizationInfo`
- **btz type**: `AlmostAlwaysSucceed` (p=0.90)
- **Source file**: `report_management/fuzzer/prioritize_report.py`
- **Parent tree**: `RMPrioritizeBt`
- **Semantic function**: Action — collect additional context needed to support a prioritization decision (e.g., severity scores, asset inventory, threat landscape data)
- **Input dependency**: Human analyst research, CVSS/SSVC scoring tools, asset management systems, threat intelligence feeds
- **Notes**: Succeeds almost always in simulation to keep the workflow progressing
- **Automation potential**: **Medium** — fetching CVSS scores, EPSS scores, NVD data, and asset inventory is fully automatable via APIs; analyst interpretation and gap-filling still requires human involvement.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.prioritize.GatherPrioritizationInfo`
- **Call-out point shape**: Retriever
- **Factory-fn placement**: `vultron.core.behaviors.report.prioritize_tree.create_prioritize_subtree` — Retriever action node in the info-gathering Sequence (not wired yet), triggered when `EnoughPrioritizationInfo` returns FAILURE

## `OnDefer`

- **Node name**: `OnDefer`
- **btz type**: `AlwaysSucceed` (p=1.00)
- **Source file**: `report_management/fuzzer/prioritize_report.py`
- **Parent tree**: `RMPrioritizeBt`
- **Semantic function**: Action — execute site-specific tasks when a report is deferred (e.g., notify stakeholders, schedule a follow-up, update case status)
- **Input dependency**: Integration hook; notification APIs, task scheduling services, case management system updates
- **Notes**: Always succeeds in simulation; must be idempotent in production
- **Automation potential**: **High** — stakeholder notifications, follow-up scheduling, and state updates are all automatable via integration APIs.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.prioritize.OnDefer`
- **Call-out point shape**: Actuator — fires integration hooks on report deferral; invokes notification APIs, task-scheduling services, and case-management state writes.
  There is no content artifact placed on the blackboard; the side effects in external systems are the seam.
- **Factory-fn placement**: `vultron.core.behaviors.report.prioritize_tree.create_prioritize_subtree` — Actuator effect node appended to `DeferCaseTriggerBT` Sequence (in `create_defer_case_tree`), after `TransitionParticipantRMtoDeferred` and the sender-side subtree

## `OnAccept`

- **Node name**: `OnAccept`
- **btz type**: `AlwaysSucceed` (p=1.00)
- **Source file**: `report_management/fuzzer/prioritize_report.py`
- **Parent tree**: `RMPrioritizeBt`
- **Semantic function**: Action — execute site-specific tasks when a report is accepted (e.g., notify stakeholders, initialize case workflow, assign to a team)
- **Input dependency**: Integration hook; notification APIs, workflow initialization, case management system updates
- **Notes**: Always succeeds in simulation; must be idempotent in production
- **Automation potential**: **High** — stakeholder notifications, workflow initialization, and state updates are all automatable via integration APIs.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.prioritize.OnAccept`
- **Call-out point shape**: Actuator — fires integration hooks on report acceptance; invokes notification APIs, workflow-initialization services, and case-management state writes.
  There is no content artifact placed on the blackboard; the side effects in external systems are the seam.
- **Factory-fn placement**: `vultron.core.behaviors.report.prioritize_tree.create_prioritize_subtree` — Actuator effect node appended to `EngageCaseTriggerBT` Sequence (in `create_engage_case_tree`), after `TransitionParticipantRMtoAccepted` and the sender-side subtree

## `EvaluateCasePriority`

- **Node name**: `EvaluateCasePriority`
- **btz type**: `AlwaysSucceed` (p=1.00)
- **Source file**: `vultron/demo/fuzzer/report_management/prioritize.py`
- **Parent tree**: `RMPrioritizeBt`
- **Semantic function**: Decision — evaluate case priority to determine whether the local actor should engage (accept) or defer the case.
  This is the SSVC integration seam: a production backend replaces this stub with a real priority evaluator.
- **Input dependency**: Human decision / Policy engine; SSVC scoring, asset inventory lookups, and policy-based engage/defer decisions.
- **Notes**: Always succeeds in simulation (always engage); SSVC evaluation deferred to PROTO-05-001.
- **Automation potential**: **High** — SSVC scoring, asset inventory lookups, and policy-based engage/defer decisions are fully automatable.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.prioritize.EvaluateCasePriority`
- **Call-out point shape**: Evaluator — `EvaluatorCallOutPoint`; outputs `evaluate_case_priority_verdict: str` on SUCCESS.
- **Factory-fn placement**: `vultron.core.behaviors.report.prioritize_tree.create_prioritize_subtree` — injected via `bundle.evaluate_priority_factory("EvaluateCasePriority")` as the first child of the `EngageCaseTriggerBT` Sequence (BT-18-004).
