---
stakeholder_type: [project-contributor]
---

# Report prioritization fuzzer nodes

These stub nodes belong to `RMPrioritizeBt` (`vultron/bt/report_management/_behaviors/prioritize_report.py`).
This sub-tree decides whether to accept (engage) or defer a valid report.

{% include-markdown "./_index_pointer.md" %}

## `NoNewPrioritizationInfo`

- **Node name**: `NoNewPrioritizationInfo`
- **btz type**: `ProbablySucceed` (p=0.67)
- **Source file**: `report_management/fuzzer/prioritize_report.py`
- **Parent tree**: `RMPrioritizeBt`
- **Semantic function**: Condition — check whether new information has arrived that makes a new prioritization of the report necessary
- **Input dependency**: Change detection on the sources of prioritization information outside the protocol, through a timestamp or an event subscription
- **Notes**: Succeeds more often than not, to prevent unnecessary repeated evaluation
- **Automation potential**: **High** — a timestamp or update-event check on those sources.
  This check is fully automatable.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.prioritize.NoNewPrioritizationInfo`
- **Call-out point shape**: Retriever (binary) — the tree asks the sources of prioritization information on its own tick whether anything new has arrived, such as new Stakeholder-Specific Vulnerability Categorization (SSVC) data or a Common Vulnerability Scoring System (CVSS) score update.
  The answer is the `SUCCESS` or `FAILURE` result itself, with no output keys (BT-18-006, BT-18-010).
  It is not ProtocolInternal, because its input comes from outside the protocol (BT-18-017).
  It is not a Sentinel: a Sentinel acts on its own initiative through a trigger and never answers a question the tree asks (BT-18-013).
- **Store-held answer**: Whether new information reached the outside sources is not recorded in the case file or the actor's store, so no read-first guard precedes this Retriever (BT-18-039).
- **Factory-fn placement**: `vultron.core.behaviors.report.prioritize_tree.create_prioritize_subtree` — a binary Retriever call-out at the top of the `PrioritizeBT` Selector.
  It is not wired yet.
  It belongs here, as a `PrioritizationCallOutBundle` factory field, when the re-prioritization loop exists.

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
- **Store-held answer**: The case file does not record the outside context this node collects, such as scores and threat data, so no read-first guard precedes this Retriever (BT-18-039).
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
  PROTO-05-001 lets the prototype use an always-engage stub in place of an SSVC evaluation.
- **Automation potential**: **High** — SSVC scoring, asset inventory lookups, and policy-based engage/defer decisions are fully automatable.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.prioritize.EvaluateCasePriority`
- **Call-out point shape**: Evaluator — `EvaluatorCallOutPoint`.
  It outputs `evaluate_case_priority_verdict: str` on SUCCESS.
- **Factory-fn placement**: `vultron.core.behaviors.report.prioritize_tree.create_prioritize_subtree` — injected through `bundle.evaluate_priority_factory("EvaluateCasePriority")` as the first child of the `EngageCaseTriggerBT` Sequence (BT-18-004).
