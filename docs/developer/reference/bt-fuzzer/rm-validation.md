---
stakeholder_type: [project-contributor]
---

# Report validation fuzzer nodes

These stub nodes belong to `RMValidateBt` (`vultron/bt/report_management/_behaviors/validate_report.py`).
This sub-tree assesses whether an incoming vulnerability report is credible and valid for the receiving organization.

{% include-markdown "./_index_pointer.md" %}

## `NoNewValidationInfo`

- **Node name**: `NoNewValidationInfo`
- **btz type**: `ProbablySucceed` (p=0.67)
- **Source file**: `report_management/fuzzer/validate_report.py`
- **Parent tree**: `RMValidateBt`
- **Semantic function**: Condition — check whether new information has arrived that makes a new evaluation of the validity of the report necessary
- **Input dependency**: Change detection on the sources of validation information outside the protocol, through a timestamp check, an event subscription, or a manual flag
- **Notes**: Succeeds (no new information) more often than not, to prevent unnecessary repeated evaluation loops
- **Automation potential**: **High** — an event subscription on those sources, or a timestamp comparison.
  This check is fully automatable.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.validate.NoNewValidationInfo`
- **Call-out point shape**: Retriever (binary) — the tree asks the sources of validation information on its own tick whether anything new has arrived, and the answer is the `SUCCESS` or `FAILURE` result itself, with no output keys (BT-18-006, BT-18-010).
  It is not ProtocolInternal, because its input comes from outside the protocol (BT-18-017).
  It is not a Sentinel: a Sentinel acts on its own initiative through a trigger and never answers a question the tree asks (BT-18-013).
- **Store-held answer**: Whether new information reached the outside sources is not recorded in the case file or the actor's store, so no read-first guard precedes this Retriever (BT-18-039).
- **Factory-fn placement**: `vultron.core.behaviors.report.validate_tree.create_validate_report_tree` — a binary Retriever call-out at the top of the root `ValidateReportBT` Selector.
  It is not wired yet.
  The tree has `CheckRMStateValid` in that position, and this call-out belongs next to it, as a `ValidationCallOutBundle` factory field, when the retry loop exists.

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
- **Store-held answer**: The case file does not record the outside information this node collects, so no read-first guard precedes this Retriever (BT-18-039).
- **Factory-fn placement**: `vultron.core.behaviors.report.validate_tree.create_validate_report_tree` — Retriever action node in the info-gathering Sequence (not wired yet).
  It runs when `EnoughValidationInfo` returns FAILURE.
