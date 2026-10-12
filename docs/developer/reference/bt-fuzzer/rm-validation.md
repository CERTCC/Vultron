---
stakeholder_type: [project-contributor]
---

# Report validation fuzzer nodes

These stub nodes belong to `RMValidateBt` (`vultron/bt/report_management/_behaviors/validate_report.py`), the sub-tree that assesses whether an incoming vulnerability report is credible and valid for the receiving organization.

See the [fuzzer node index](index.md) for the entry format, the automation-potential and call-out shape values, and the base-type probabilities.

## `NoNewValidationInfo`

- **Node name**: `NoNewValidationInfo`
- **btz type**: `ProbablySucceed` (p=0.67)
- **Source file**: `report_management/fuzzer/validate_report.py`
- **Parent tree**: `RMValidateBt`
- **Semantic function**: Condition — check whether any new information has arrived that should trigger re-evaluation of the report's validity
- **Input dependency**: Report change detection; could be a metadata timestamp check, event subscription, or manual flag
- **Notes**: Succeeds (no new info) more often than not, avoiding redundant re-evaluation loops
- **Automation potential**: **High** — event subscription on the case record or metadata timestamp comparison; fully automatable.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.validate.NoNewValidationInfo`
- **Call-out point shape**: ProtocolInternal — reads a change-detection flag written by the upstream `NewValidationInfoSentinel` (see the next entry).
  The external seam is at that upstream writer, not at this behavior tree (BT) condition check.
- **Factory-fn placement**: `vultron.core.behaviors.report.validate_tree.create_validate_report_tree` — ProtocolInternal condition check at the top of `ValidationOrShortcut` Selector; not wired yet: the tree has `CheckRMStateValid` there, and the change-detection variant belongs beside it once the retry loop exists

## `NewValidationInfoSentinel` *(upstream Sentinel stub)*

- **Node name**: `NewValidationInfoSentinel`
- **btz type**: *(not a BT node — upstream agent seam)*
- **Source file**: *(to be determined)*
- **Parent tree**: *(runs independently, outside the BT tick loop)*
- **Semantic function**: Sentinel — monitors the case record for new validation-relevant events (e.g., reporter follow-up, credibility update, new threat intelligence) and writes a change-detection flag that `NoNewValidationInfo` consumes.
- **Input dependency**: Case management system event stream; metadata timestamp comparison or event subscription on validation-relevant case fields.
- **Notes**: This is the real seam implied by `NoNewValidationInfo`.
  The writer registers with an external event source and writes a flag to the BT blackboard or local DataLayer; `NoNewValidationInfo` reads that flag each tick.
- **Automation potential**: **High** — event subscription on the case record or metadata timestamp comparison; fully automatable.
- **New-arch cross-ref**: `vultron.demo.fuzzer.call_out_point.NewValidationInfoSentinel`
- **Call-out point shape**: Sentinel — pending reclassification: Sentinel is no longer a call-out shape (ADR-0097, BT-18-013), and #3424 tracks reclassifying this entry.
- **Factory-fn placement**: Not placed inside the BT tree; writes the change-detection flag read by `NoNewValidationInfo` at the top of the `ValidationOrShortcut` Selector in `vultron.core.behaviors.report.validate_tree.create_validate_report_tree`

## `EvaluateReportCredibility`

- **Node name**: `EvaluateReportCredibility`
- **btz type**: `AlmostAlwaysSucceed` (p=0.90)
- **Source file**: `report_management/fuzzer/validate_report.py`
- **Parent tree**: `RMValidateBt`
- **Semantic function**: Condition — assess whether the report's source and content are credible (i.e., likely to describe a real vulnerability)
- **Input dependency**: Human analyst judgment; structured credibility criteria (e.g., Stakeholder-Specific Vulnerability Categorization (SSVC) Exploitation, reporter reputation, technical plausibility); potentially automatable with triage tools based on machine learning (ML)
- **Notes**: SSVC documentation provides structured criteria for this evaluation
- **Automation potential**: **Medium** — SSVC exploitation status, reporter reputation scoring, and technical plausibility checks can be partially automated; final credibility determination typically requires human analyst review.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.validate.EvaluateReportCredibility`
- **Call-out point shape**: Evaluator
- **Factory-fn placement**: `vultron.core.behaviors.report.validate_tree.create_validate_report_tree` — Evaluator condition guard in `ValidationFlow` Sequence (second child, before `EvaluateReportValidity`); currently a stub `EvaluateReportCredibility` node that always returns SUCCESS

## `EvaluateReportValidity`

- **Node name**: `EvaluateReportValidity`
- **btz type**: `AlmostAlwaysSucceed` (p=0.90)
- **Source file**: `report_management/fuzzer/validate_report.py`
- **Parent tree**: `RMValidateBt`
- **Semantic function**: Condition — assess whether the report is valid for this organization's scope (credible AND meeting org-specific acceptance criteria)
- **Input dependency**: Human analyst judgment or policy-driven scope check; context-specific to the receiving organization's Coordinated Vulnerability Disclosure (CVD) charter
- **Notes**: A report can be credible but out of scope; validity is contextual and role-dependent
- **Automation potential**: **Medium** — scope checks against well-defined Common Vulnerabilities and Exposures (CVE) Numbering Authority (CNA) or charter rules are automatable; organizational-context validity judgment often requires human review.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.validate.EvaluateReportValidity`
- **Call-out point shape**: Evaluator
- **Factory-fn placement**: `vultron.core.behaviors.report.validate_tree.create_validate_report_tree` — Evaluator condition guard in `ValidationFlow` Sequence (third child, before `ValidationActions`); currently a stub `EvaluateReportValidity` node that always returns SUCCESS

## `EnoughValidationInfo`

- **Node name**: `EnoughValidationInfo`
- **btz type**: `UsuallySucceed` (p=0.75)
- **Source file**: `report_management/fuzzer/validate_report.py`
- **Parent tree**: `RMValidateBt`
- **Semantic function**: Condition — determine whether sufficient information is available to reach a validation decision
- **Input dependency**: Human decision or automated completeness check against required report fields or evidence criteria
- **Notes**: Sufficient information is the normal case; absence triggers info-gathering
- **Automation potential**: **Medium** — completeness check against required fields or evidence criteria can be automated; the sufficiency threshold for final decision often involves human judgment.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.validate.EnoughValidationInfo`
- **Call-out point shape**: Evaluator
- **Factory-fn placement**: `vultron.core.behaviors.report.validate_tree.create_validate_report_tree` — Evaluator condition guard in `ValidationFlow` Sequence (not wired yet); gate before the info-gathering loop that `GatherValidationInfo` populates

## `GatherValidationInfo`

- **Node name**: `GatherValidationInfo`
- **btz type**: `AlmostAlwaysSucceed` (p=0.90)
- **Source file**: `report_management/fuzzer/validate_report.py`
- **Parent tree**: `RMValidateBt`
- **Semantic function**: Action — request or collect additional information needed to validate the report (e.g., reproduction steps, affected versions, proof-of-concept)
- **Input dependency**: Human analyst outreach to reporter, or automated intake forms / follow-up workflows
- **Notes**: Succeeds most of the time in simulation to keep the workflow progressing
- **Automation potential**: **Medium** — structured intake form follow-ups and automated case-update requests are partially automatable; direct reporter outreach typically requires human involvement.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.validate.GatherValidationInfo`
- **Call-out point shape**: Retriever
- **Factory-fn placement**: `vultron.core.behaviors.report.validate_tree.create_validate_report_tree` — Retriever action node in the info-gathering Sequence (not wired yet), triggered when `EnoughValidationInfo` returns FAILURE
