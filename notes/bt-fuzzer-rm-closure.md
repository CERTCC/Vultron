---
title: "BT Fuzzer Nodes: RM Report Closure and Other Work"
status: active
description: >
  Catalog of fuzzer (stub) BT nodes for Report Closure (`CloseReportBt`)
  and Other Work (`RMDoWorkBt`) sub-workflows: close-case eligibility,
  transition guards, and extensibility stub nodes used in simulation.
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

## Report Closure

These nodes belong to `RMCloseBt`
(`vultron/bt/report_management/_behaviors/close_report.py`), which models
the process of closing a vulnerability report once the CVD workflow is
complete (or otherwise concluded).

### `OtherCloseCriteriaMet`

- **Node name**: `OtherCloseCriteriaMet`
- **btz type**: `UsuallyFail` (p=0.25)
- **Source file**: `report_management/fuzzer/close_report.py`
- **Parent tree**: `RMCloseBt`
- **Semantic function**: Condition — check whether site-specific or
  case-specific closure criteria (beyond the standard CVD completion
  conditions) have been met
- **Input dependency**: Human analyst decision or policy-driven checklist;
  context-specific to organizational CVD policy
- **Notes**: Fails most of the time in simulation because non-standard
  closure criteria are uncommon; may represent editorial board sign-off,
  legal review completion, etc.
- **Automation potential**: **Low** — site-specific; closure criteria vary widely by organization and case context; typically requires human policy evaluation or explicit sign-off.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.close_report.OtherCloseCriteriaMet`
- **Call-out point shape**: Evaluator
- **Factory-fn placement**: Phase 1 stub now exists as of PR #1357 —
  `vultron.core.behaviors.report.close_report_tree.create_close_report_tree`
  (`other_close_criteria_factory` param). FUTURE full placement:
  `vultron.core.behaviors.report.create_close_report_tree`
  (issue #1253) — Evaluator precondition guard in the `RMCloseBt` Sequence;
  evaluated before `PreCloseAction`; blocks closure until site-specific
  criteria are satisfied

### `PreCloseAction`

- **Node name**: `PreCloseAction`
- **btz type**: `AlwaysSucceed` (p=1.00)
- **Source file**: `report_management/fuzzer/close_report.py`
- **Parent tree**: `RMCloseBt`
- **Semantic function**: Action — execute any site-specific tasks that must
  be completed before a report can be closed (e.g., quality assurance
  review, final stakeholder notification, archiving)
- **Input dependency**: Integration hook; QA pipeline, archiving system,
  or final notification API
- **Notes**: Always succeeds in simulation; production may involve
  multi-step pre-close workflows
- **Automation potential**: **Medium** — archiving and standard notification steps can be automated; QA review and final approvals typically require human involvement.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.close_report.PreCloseAction`
- **Call-out point shape**: Actuator — fires integration hooks before case closure; invokes QA pipeline checks, final notification APIs, and case-archiving services. There is no content artifact placed on the blackboard; the side effects in external systems are the seam.
- **Factory-fn placement**: FUTURE:
  `vultron.core.behaviors.report.create_close_report_tree`
  (issue #1253) — Actuator effect node after `OtherCloseCriteriaMet`;
  last node before the RM → CLOSED state transition fires

---

## Other Work (Do Work)

These nodes belong to `RMDoWorkBt`
(`vultron/bt/report_management/_behaviors/do_work.py`), the general
"do work" fallback tree that represents miscellaneous active work on an
accepted vulnerability report outside of the more specific sub-trees.

### `OtherWork`

- **Node name**: `OtherWork`
- **btz type**: `AlwaysSucceed` (p=1.00)
- **Source file**: `report_management/fuzzer/other_work.py`
- **Parent tree**: `RMDoWorkBt`
- **Semantic function**: Action — placeholder for any additional work
  activities not covered by the more specific BT sub-trees (e.g.,
  internal documentation, stakeholder meetings, legal review, additional
  analysis)
- **Input dependency**: Site-specific work queue; human analyst tasks or
  automated workflow steps not yet modeled in the BT
- **Notes**: Always succeeds; this is an extensibility point for
  organizations to plug in their own workflow steps
- **Automation potential**: **Low** — intentional extensibility stub for unmodeled work; automation potential is entirely site-specific and cannot be assessed generically.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.other_work.OtherWork`
- **Call-out point shape**: Evaluator
- **Factory-fn placement**: FUTURE:
  `vultron.core.behaviors.report.create_do_work_tree`
  (issue #1255) — primary Evaluator leaf of `RMDoWorkBt`; the main
  extensibility seam for organization-specific in-flight case work
  not covered by more specific sub-trees

---
