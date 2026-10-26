---
stakeholder_type: [project-contributor]
---

# Report prioritization fuzzer nodes

These stub nodes belong to `RMPrioritizeBt` (`vultron/bt/report_management/_behaviors/prioritize_report.py`).
This sub-tree decides whether to accept (engage) or defer a valid report.

See the [fuzzer node index](index.md) for the entry format, the automation-potential and call-out shape values, and the base-type probabilities.

## `NoNewPrioritizationInfo`

- **Node name**: `NoNewPrioritizationInfo`
- **btz type**: `ProbablySucceed` (p=0.67)
- **Source file**: `report_management/fuzzer/prioritize_report.py`
- **Parent tree**: `RMPrioritizeBt`
- **Semantic function**: Condition — check whether new information has arrived that makes a new prioritization of the report necessary
- **Input dependency**: Report change detection, through a metadata timestamp or an event subscription
- **Notes**: Succeeds more often than not, to prevent unnecessary repeated evaluation
- **Automation potential**: **High** — a metadata timestamp or case-update event check.
  This check is fully automatable.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.prioritize.NoNewPrioritizationInfo`
- **Call-out point shape**: ProtocolInternal — reads a change-detection flag that the upstream `NewPrioritizationInfoSentinel` writes (see the next entry).
  The external seam is at that upstream writer, not at this behavior tree (BT) condition check.
- **Factory-fn placement**: `vultron.core.behaviors.report.prioritize_tree.create_prioritize_subtree` — ProtocolInternal condition check at the top of the `PrioritizeBT` Selector.
  It is not wired yet.
  It belongs here when the re-prioritization loop exists.

## `NewPrioritizationInfoSentinel` *(upstream Sentinel stub)*

- **Node name**: `NewPrioritizationInfoSentinel`
- **btz type**: *(not a BT node — upstream agent seam)*
- **Source file**: *(to be determined)*
- **Parent tree**: *(runs independently, outside the BT tick loop)*
- **Semantic function**: Sentinel — monitors the case record for new events that are relevant to prioritization.
  One example is new Stakeholder-Specific Vulnerability Categorization (SSVC) scoring data.
  Other examples are new threat intelligence or a Common Vulnerability Scoring System (CVSS) score update.
  The Sentinel writes a change-detection flag that `NoNewPrioritizationInfo` reads.
- **Input dependency**: The event stream of the case management system.
  The Sentinel compares metadata timestamps, or subscribes to events on case fields that are relevant to prioritization.
  Examples of these fields are SSVC decision points and CVSS scores.
- **Notes**: This writer is the real seam that `NoNewPrioritizationInfo` implies.
  The writer registers with an external event source and writes a flag to the BT blackboard or the local DataLayer.
  `NoNewPrioritizationInfo` reads that flag each tick.
- **Automation potential**: **High** — an event subscription on the case record, or a metadata timestamp comparison.
  This work is fully automatable.
- **New-arch cross-ref**: `vultron.demo.fuzzer.call_out_point.NewPrioritizationInfoSentinel`
- **Call-out point shape**: Sentinel — pending reclassification.
  Sentinel is no longer a call-out shape (ADR-0097, BT-18-013), and #3424 tracks the reclassification of this entry.
- **Factory-fn placement**: Not placed inside the BT tree.
  It writes the change-detection flag that `NoNewPrioritizationInfo` reads at the top of the `PrioritizeBT` Selector in `vultron.core.behaviors.report.prioritize_tree.create_prioritize_subtree`.

## `EnoughPrioritizationInfo`

- **Node name**: `EnoughPrioritizationInfo`
- **btz type**: `UsuallySucceed` (p=0.75)
- **Source file**: `report_management/fuzzer/prioritize_report.py`
- **Parent tree**: `RMPrioritizeBt`
- **Semantic function**: Condition — find out whether there is enough context to make an accept/defer decision
- **Input dependency**: Human analyst assessment, or an automated completeness check, such as the availability of SSVC decision points
- **Notes**: Insufficient information starts a gathering phase
- **Automation potential**: **Medium** — the availability check of SSVC decision-point data, such as the CVSS score or exploitation status, is automatable.
  The judgment that the data is sufficient for a final accept/defer decision usually needs a human analyst review.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.prioritize.EnoughPrioritizationInfo`
- **Call-out point shape**: Evaluator
- **Factory-fn placement**: `vultron.core.behaviors.report.prioritize_tree.create_prioritize_subtree` — Evaluator condition guard in the `PrioritizeBT` Sequence (not wired yet).
  It is the gate before the info-gathering loop that `GatherPrioritizationInfo` fills.

## `GatherPrioritizationInfo`

- **Node name**: `GatherPrioritizationInfo`
- **btz type**: `AlmostAlwaysSucceed` (p=0.90)
- **Source file**: `report_management/fuzzer/prioritize_report.py`
- **Parent tree**: `RMPrioritizeBt`
- **Semantic function**: Action — collect more context to support a prioritization decision, such as severity scores, asset inventory, and threat landscape data
- **Input dependency**: Human analyst research, CVSS/SSVC scoring tools, asset management systems, threat intelligence feeds
- **Notes**: Succeeds almost always in simulation, so that the workflow continues
- **Automation potential**: **Medium** — application programming interfaces (APIs) can fully automate data retrieval.
  This data includes CVSS scores, Exploit Prediction Scoring System (EPSS) scores, National Vulnerability Database (NVD) data, and asset inventory.
  Analyst interpretation and gap-filling still need human involvement.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.prioritize.GatherPrioritizationInfo`
- **Call-out point shape**: Retriever
- **Factory-fn placement**: `vultron.core.behaviors.report.prioritize_tree.create_prioritize_subtree` — Retriever action node in the info-gathering Sequence (not wired yet).
  It runs when `EnoughPrioritizationInfo` returns FAILURE.

## `OnDefer`

- **Node name**: `OnDefer`
- **btz type**: `AlwaysSucceed` (p=1.00)
- **Source file**: `report_management/fuzzer/prioritize_report.py`
- **Parent tree**: `RMPrioritizeBt`
- **Semantic function**: Action — do site-specific tasks when a report is deferred, such as notify Participants, schedule a follow-up, or update the case status
- **Input dependency**: Integration hook to notification APIs, task scheduling services, and case management system updates
- **Notes**: Always succeeds in simulation.
  In production, it must be idempotent.
- **Automation potential**: **High** — integration APIs can automate Participant notifications, follow-up scheduling, and state updates.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.prioritize.OnDefer`
- **Call-out point shape**: Actuator — fires integration hooks on report deferral.
  It invokes notification APIs, task-scheduling services, and case-management state writes.
  It puts no content artifact on the blackboard.
  The side effects in external systems are the seam.
- **Factory-fn placement**: `vultron.core.behaviors.report.prioritize_tree.create_prioritize_subtree` — Actuator effect node appended to the `DeferCaseTriggerBT` Sequence (in `create_defer_case_tree`).
  It comes after `TransitionParticipantRMtoDeferred` and the sender-side subtree.

## `OnAccept`

- **Node name**: `OnAccept`
- **btz type**: `AlwaysSucceed` (p=1.00)
- **Source file**: `report_management/fuzzer/prioritize_report.py`
- **Parent tree**: `RMPrioritizeBt`
- **Semantic function**: Action — do site-specific tasks when a report is accepted, such as notify Participants, start the case workflow, or assign the case to a team
- **Input dependency**: Integration hook to notification APIs, workflow initialization, and case management system updates
- **Notes**: Always succeeds in simulation.
  In production, it must be idempotent.
- **Automation potential**: **High** — integration APIs can automate Participant notifications, workflow initialization, and state updates.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.prioritize.OnAccept`
- **Call-out point shape**: Actuator — fires integration hooks on report acceptance.
  It invokes notification APIs, workflow-initialization services, and case-management state writes.
  It puts no content artifact on the blackboard.
  The side effects in external systems are the seam.
- **Factory-fn placement**: `vultron.core.behaviors.report.prioritize_tree.create_prioritize_subtree` — Actuator effect node appended to the `EngageCaseTriggerBT` Sequence (in `create_engage_case_tree`).
  It comes after `TransitionParticipantRMtoAccepted` and the sender-side subtree.

## `EvaluateCasePriority`

- **Node name**: `EvaluateCasePriority`
- **btz type**: `AlwaysSucceed` (p=1.00)
- **Source file**: `vultron/demo/fuzzer/report_management/prioritize.py`
- **Parent tree**: `RMPrioritizeBt`
- **Semantic function**: Decision — evaluate the case priority to decide whether the local actor engages (accepts) or defers the case.
  This node is the SSVC integration seam.
  A production backend replaces this stub with a real priority evaluator.
- **Input dependency**: Human decision or policy engine, through SSVC scoring, asset inventory lookups, and policy-based engage/defer decisions.
- **Notes**: Always succeeds in simulation (always engage).
  PROTO-05-001 defers the SSVC evaluation.
- **Automation potential**: **High** — SSVC scoring, asset inventory lookups, and policy-based engage/defer decisions are fully automatable.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.prioritize.EvaluateCasePriority`
- **Call-out point shape**: Evaluator — `EvaluatorCallOutPoint`.
  It outputs `evaluate_case_priority_verdict: str` on SUCCESS.
- **Factory-fn placement**: `vultron.core.behaviors.report.prioritize_tree.create_prioritize_subtree` — injected through `bundle.evaluate_priority_factory("EvaluateCasePriority")` as the first child of the `EngageCaseTriggerBT` Sequence (BT-18-004).
