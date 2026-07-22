---
title: "BT Fuzzer Nodes: RM Report Validation"
status: active
description: >
  Catalog of fuzzer (stub) BT nodes for the Report Validation sub-workflow
  (`RMValidateBt`): credibility, validity checks, new-info sentinels,
  and report-rejection nodes used in simulation.
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

## Report Validation

These nodes belong to `RMValidateBt`
(`vultron/bt/report_management/_behaviors/validate_report.py`), the sub-tree
responsible for assessing whether an incoming vulnerability report is
credible and valid for the receiving organization.

### `NoNewValidationInfo`

- **Node name**: `NoNewValidationInfo`
- **btz type**: `ProbablySucceed` (p=0.67)
- **Source file**: `report_management/fuzzer/validate_report.py`
- **Parent tree**: `RMValidateBt`
- **Semantic function**: Condition — check whether any new information has
  arrived that should trigger re-evaluation of the report's validity
- **Input dependency**: Report change detection; could be a metadata
  timestamp check, event subscription, or manual flag
- **Notes**: Succeeds (no new info) more often than not, avoiding redundant
  re-evaluation loops
- **Automation potential**: **High** — event subscription on the case record or metadata timestamp comparison; fully automatable.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.validate.NoNewValidationInfo`
- **Call-out point shape**: ProtocolInternal — reads a change-detection flag written by the upstream
  `NewValidationInfoSentinel` agent (see stub entry below). The external agent seam is at the
  Sentinel (event subscription or polling hook), not at this BT condition check. In production this
  node reads from the BT blackboard or case metadata written by the upstream Sentinel.
  (Category 2 per issue #1199 triage — consumes a flag written by an upstream Sentinel.)
- **Factory-fn placement**:
  `vultron.core.behaviors.report.validate_tree.create_validate_report_tree` —
  ProtocolInternal condition check at the top of `ValidationOrShortcut` Selector;
  currently stubbed as `CheckRMStateValid` but the change-detection variant
  belongs here when the full retry loop is implemented (Phase 2)

### `NewValidationInfoSentinel` *(upstream Sentinel stub)*

- **Node name**: `NewValidationInfoSentinel`
- **btz type**: *(not a BT node — upstream agent seam)*
- **Source file**: *(to be determined)*
- **Parent tree**: *(runs independently, outside the BT tick loop)*
- **Semantic function**: Sentinel — monitors the case record for new
  validation-relevant events (e.g., reporter follow-up, credibility update,
  new threat intelligence) and writes a change-detection flag that
  `NoNewValidationInfo` consumes.
- **Input dependency**: Case management system event stream; metadata
  timestamp comparison or event subscription on validation-relevant case
  fields.
- **Notes**: This is the real call-out point implied by `NoNewValidationInfo`.
  The upstream Sentinel registers with an external event source and writes
  a flag to the BT blackboard / local DataLayer; `NoNewValidationInfo` then
  reads that flag each BT tick. Implementation tracked in FUZZ-08f.
- **Automation potential**: **High** — event subscription on the case record
  or metadata timestamp comparison; fully automatable.
- **New-arch cross-ref**: *(to be implemented — see FUZZ-08f)*
- **Call-out point shape**: Sentinel — registers with a case-event source;
  fires a change-detection signal into the BT blackboard when new
  validation-relevant information arrives; no output keys beyond the flag.
- **Factory-fn placement**: FUZZ-08f (planned) — upstream agent seam, not
  placed inside the BT tree; writes a change-detection flag to the blackboard
  key read by `NoNewValidationInfo` at the top of the
  `ValidationOrShortcut` Selector in
  `vultron.core.behaviors.report.validate_tree.create_validate_report_tree`

### `EvaluateReportCredibility`

- **Node name**: `EvaluateReportCredibility`
- **btz type**: `AlmostAlwaysSucceed` (p=0.90)
- **Source file**: `report_management/fuzzer/validate_report.py`
- **Parent tree**: `RMValidateBt`
- **Semantic function**: Condition — assess whether the report's source and
  content are credible (i.e., likely to describe a real vulnerability)
- **Input dependency**: Human analyst judgment; structured credibility
  criteria (e.g., SSVC Exploitation, reporter reputation, technical
  plausibility); potentially automatable with ML-based triage tools
- **Notes**: SSVC documentation provides structured criteria for this
  evaluation
- **Automation potential**: **Medium** — SSVC exploitation status, reporter reputation scoring, and technical plausibility checks can be partially automated; final credibility determination typically requires human analyst review.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.validate.EvaluateReportCredibility`
- **Call-out point shape**: Evaluator
- **Factory-fn placement**:
  `vultron.core.behaviors.report.validate_tree.create_validate_report_tree` —
  Evaluator condition guard in `ValidationFlow` Sequence (second child, before
  `EvaluateReportValidity`); currently a stub `EvaluateReportCredibility` node
  that always returns SUCCESS

### `EvaluateReportValidity`

- **Node name**: `EvaluateReportValidity`
- **btz type**: `AlmostAlwaysSucceed` (p=0.90)
- **Source file**: `report_management/fuzzer/validate_report.py`
- **Parent tree**: `RMValidateBt`
- **Semantic function**: Condition — assess whether the report is valid for
  this organization's scope (credible AND meeting org-specific acceptance
  criteria)
- **Input dependency**: Human analyst judgment or policy-driven scope check;
  context-specific to the receiving organization's CVD charter
- **Notes**: A report can be credible but out of scope; validity is
  contextual and role-dependent
- **Automation potential**: **Medium** — scope checks against well-defined CNA/charter rules are automatable; organizational-context validity judgment often requires human review.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.validate.EvaluateReportValidity`
- **Call-out point shape**: Evaluator
- **Factory-fn placement**:
  `vultron.core.behaviors.report.validate_tree.create_validate_report_tree` —
  Evaluator condition guard in `ValidationFlow` Sequence (third child, before
  `ValidationActions`); currently a stub `EvaluateReportValidity` node that
  always returns SUCCESS

### `EnoughValidationInfo`

- **Node name**: `EnoughValidationInfo`
- **btz type**: `UsuallySucceed` (p=0.75)
- **Source file**: `report_management/fuzzer/validate_report.py`
- **Parent tree**: `RMValidateBt`
- **Semantic function**: Condition — determine whether sufficient information
  is available to reach a validation decision
- **Input dependency**: Human decision or automated completeness check
  against required report fields or evidence criteria
- **Notes**: Sufficient information is the normal case; absence triggers
  info-gathering
- **Automation potential**: **Medium** — completeness check against required fields or evidence criteria can be automated; the sufficiency threshold for final decision often involves human judgment.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.validate.EnoughValidationInfo`
- **Call-out point shape**: Evaluator
- **Factory-fn placement**:
  `vultron.core.behaviors.report.validate_tree.create_validate_report_tree` —
  Evaluator condition guard in `ValidationFlow` Sequence (Phase 2); gate
  before the info-gathering loop that `GatherValidationInfo` populates

### `GatherValidationInfo`

- **Node name**: `GatherValidationInfo`
- **btz type**: `AlmostAlwaysSucceed` (p=0.90)
- **Source file**: `report_management/fuzzer/validate_report.py`
- **Parent tree**: `RMValidateBt`
- **Semantic function**: Action — request or collect additional information
  needed to validate the report (e.g., reproduction steps, affected
  versions, proof-of-concept)
- **Input dependency**: Human analyst outreach to reporter, or automated
  intake forms / follow-up workflows
- **Notes**: Succeeds most of the time in simulation to keep the workflow
  progressing
- **Automation potential**: **Low–Medium** — structured intake form follow-ups and automated case-update requests are partially automatable; direct reporter outreach typically requires human involvement.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.validate.GatherValidationInfo`
- **Call-out point shape**: Retriever
- **Factory-fn placement**:
  `vultron.core.behaviors.report.validate_tree.create_validate_report_tree` —
  Retriever action node in the info-gathering Sequence (Phase 2), triggered
  when `EnoughValidationInfo` returns FAILURE

---
