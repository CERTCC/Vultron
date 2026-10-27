---
stakeholder_type: [project-contributor]
---

# Report validation fuzzer nodes

These stub nodes belong to `RMValidateBt` (`vultron/bt/report_management/_behaviors/validate_report.py`).
This sub-tree assesses whether an incoming vulnerability report is credible and valid for the receiving organization.

See the [fuzzer node index](index.md) for the entry format, the automation-potential and call-out shape values, and the base-type probabilities.

## `NoNewValidationInfo`

- **Node name**: `NoNewValidationInfo`
- **btz type**: `ProbablySucceed` (p=0.67)
- **Source file**: `report_management/fuzzer/validate_report.py`
- **Parent tree**: `RMValidateBt`
- **Semantic function**: Condition — check whether new information has arrived that makes a new evaluation of the validity of the report necessary
- **Input dependency**: Report change detection, through a metadata timestamp check, an event subscription, or a manual flag
- **Notes**: Succeeds (no new information) more often than not, to prevent unnecessary repeated evaluation loops
- **Automation potential**: **High** — an event subscription on the case record, or a metadata timestamp comparison.
  This check is fully automatable.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.validate.NoNewValidationInfo`
- **Call-out point shape**: ProtocolInternal — reads a change-detection flag that the upstream `NewValidationInfoSentinel` writes (see the next entry).
  The external seam is at that upstream writer, not at this behavior tree (BT) condition check.
- **Factory-fn placement**: `vultron.core.behaviors.report.validate_tree.create_validate_report_tree` — ProtocolInternal condition check at the top of the root `ValidateReportBT` Selector.
  It is not wired yet.
  The tree has `CheckRMStateValid` in that position, and the change-detection variant belongs next to it when the retry loop exists.

## `NewValidationInfoSentinel` *(upstream Sentinel stub)*

- **Node name**: `NewValidationInfoSentinel`
- **btz type**: *(not a BT node — upstream agent seam)*
- **Source file**: *(to be determined)*
- **Parent tree**: *(runs independently, outside the BT tick loop)*
- **Semantic function**: Sentinel — monitors the case record for new events that are relevant to validation, such as a reporter follow-up, a credibility update, or new threat intelligence.
  The Sentinel writes a change-detection flag that `NoNewValidationInfo` reads.
- **Input dependency**: The event stream of the case management system.
  The Sentinel compares metadata timestamps, or subscribes to events on case fields that are relevant to validation.
- **Notes**: This writer is the real seam that `NoNewValidationInfo` implies.
  The writer registers with an external event source and writes a flag to the BT blackboard or the local DataLayer.
  `NoNewValidationInfo` reads that flag each tick.
- **Automation potential**: **High** — an event subscription on the case record, or a metadata timestamp comparison.
  This work is fully automatable.
- **New-arch cross-ref**: `vultron.demo.fuzzer.call_out_point.NewValidationInfoSentinel`
- **Call-out point shape**: Sentinel — pending reclassification.
  Sentinel is no longer a call-out shape (ADR-0097, BT-18-013), and #3424 tracks the reclassification of this entry.
- **Factory-fn placement**: Not placed inside the BT tree.
  It writes the change-detection flag that `NoNewValidationInfo` reads at the top of the root `ValidateReportBT` Selector in `vultron.core.behaviors.report.validate_tree.create_validate_report_tree`.

## `EvaluateReportCredibility`

- **Node name**: `EvaluateReportCredibility`
- **btz type**: `AlmostAlwaysSucceed` (p=0.90)
- **Source file**: `report_management/fuzzer/validate_report.py`
- **Parent tree**: `RMValidateBt`
- **Semantic function**: Condition — assess whether the source and content of the report are credible, that is, whether the report probably describes a real vulnerability
- **Input dependency**: Human analyst judgment, with structured credibility criteria.
  Examples are Stakeholder-Specific Vulnerability Categorization (SSVC) Exploitation, reporter reputation, and technical plausibility.
  Triage tools based on machine learning (ML) can possibly automate this input.
- **Notes**: SSVC documentation gives structured criteria for this evaluation
- **Automation potential**: **Medium** — SSVC exploitation status, reporter reputation scoring, and technical plausibility checks are partially automatable.
  The final credibility decision usually needs a human analyst review.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.validate.EvaluateReportCredibility`
- **Call-out point shape**: Evaluator
- **Factory-fn placement**: `vultron.core.behaviors.report.validate_tree.create_validate_report_tree` — Evaluator condition guard in the `ValidationFlow` Sequence (second child, before `EvaluateReportValidity`).
  At this time, it is a stub `EvaluateReportCredibility` node that always returns SUCCESS.

## `EvaluateReportValidity`

- **Node name**: `EvaluateReportValidity`
- **btz type**: `AlmostAlwaysSucceed` (p=0.90)
- **Source file**: `report_management/fuzzer/validate_report.py`
- **Parent tree**: `RMValidateBt`
- **Semantic function**: Condition — assess whether the report is valid for the scope of this organization (credible AND meets the org-specific acceptance criteria)
- **Input dependency**: Human analyst judgment or a policy-driven scope check, specific to the Coordinated Vulnerability Disclosure (CVD) charter of the receiving organization
- **Notes**: A report can be credible but out of scope.
  Validity depends on the context and the role.
- **Automation potential**: **Medium** — scope checks against well-defined Common Vulnerabilities and Exposures (CVE) Numbering Authority (CNA) or charter rules are automatable.
  A validity judgment in the organizational context often needs human review.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.validate.EvaluateReportValidity`
- **Call-out point shape**: Evaluator
- **Factory-fn placement**: `vultron.core.behaviors.report.validate_tree.create_validate_report_tree` — Evaluator condition guard in the `ValidationFlow` Sequence (third child, before `RequireCaseForReport`).
  At this time, it is a stub `EvaluateReportValidity` node that always returns SUCCESS.

## `EnoughValidationInfo`

- **Node name**: `EnoughValidationInfo`
- **btz type**: `UsuallySucceed` (p=0.75)
- **Source file**: `report_management/fuzzer/validate_report.py`
- **Parent tree**: `RMValidateBt`
- **Semantic function**: Condition — find out whether there is sufficient information to make a validation decision
- **Input dependency**: Human decision, or an automated completeness check against the required report fields or evidence criteria
- **Notes**: Sufficient information is the normal case.
  If information is missing, the tree starts information gathering.
- **Automation potential**: **Medium** — a completeness check against the required fields or evidence criteria is automatable.
  The sufficiency threshold for a final decision often needs human judgment.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.validate.EnoughValidationInfo`
- **Call-out point shape**: Evaluator
- **Factory-fn placement**: `vultron.core.behaviors.report.validate_tree.create_validate_report_tree` — Evaluator condition guard in the `ValidationFlow` Sequence (not wired yet).
  It is the gate before the info-gathering loop that `GatherValidationInfo` fills.

## `GatherValidationInfo`

- **Node name**: `GatherValidationInfo`
- **btz type**: `AlmostAlwaysSucceed` (p=0.90)
- **Source file**: `report_management/fuzzer/validate_report.py`
- **Parent tree**: `RMValidateBt`
- **Semantic function**: Action — request or collect more information to validate the report, such as reproduction steps, affected versions, or a proof-of-concept
- **Input dependency**: Human analyst contact with the reporter, or automated intake forms or follow-up workflows
- **Notes**: Succeeds most of the time in simulation, so that the workflow continues
- **Automation potential**: **Medium** — structured intake form follow-ups and automated case-update requests are partially automatable.
  Direct contact with the reporter usually needs human involvement.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.validate.GatherValidationInfo`
- **Call-out point shape**: Retriever
- **Factory-fn placement**: `vultron.core.behaviors.report.validate_tree.create_validate_report_tree` — Retriever action node in the info-gathering Sequence (not wired yet).
  It runs when `EnoughValidationInfo` returns FAILURE.
