---
stakeholder_type: [project-contributor]
---

# Report closure and other work fuzzer nodes

These stub nodes belong to `RMCloseBt` (`vultron/bt/report_management/_behaviors/close_report.py`), which models closing a report once the Coordinated Vulnerability Disclosure (CVD) workflow concludes, and to `RMDoWorkBt` (`vultron/bt/report_management/_behaviors/do_work.py`), the fallback tree for miscellaneous work on an accepted report.

See the [fuzzer node index](index.md) for the entry format, the automation-potential and call-out shape values, and the base-type probabilities.

## Report closure

### `OtherCloseCriteriaMet`

- **Node name**: `OtherCloseCriteriaMet`
- **btz type**: `UsuallyFail` (p=0.25)
- **Source file**: `report_management/fuzzer/close_report.py`
- **Parent tree**: `RMCloseBt`
- **Semantic function**: Condition — check whether site-specific or case-specific closure criteria (beyond the standard CVD completion conditions) have been met
- **Input dependency**: Human analyst decision or policy-driven checklist; context-specific to organizational CVD policy
- **Notes**: Fails most of the time in simulation because non-standard closure criteria are uncommon; may represent editorial board sign-off, legal review completion, etc.
- **Automation potential**: **Low** — site-specific; closure criteria vary widely by organization and case context; typically requires human policy evaluation or explicit sign-off.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.close_report.OtherCloseCriteriaMet`
- **Call-out point shape**: Evaluator
- **Factory-fn placement**: `vultron.core.behaviors.report.close_report_tree.create_close_report_tree` (`other_close_criteria_factory` param; DETERMINISTIC default `AlwaysFail`).
  That tree is a seam-only stub that no use case calls; see [Closure model](#closure-model).

### `PreCloseAction`

- **Node name**: `PreCloseAction`
- **btz type**: `AlwaysSucceed` (p=1.00)
- **Source file**: `report_management/fuzzer/close_report.py`
- **Parent tree**: `RMCloseBt`
- **Semantic function**: Action — execute any site-specific tasks that must be completed before a report can be closed (e.g., quality assurance review, final Participant notification, archiving)
- **Input dependency**: Integration hook; quality assurance (QA) pipeline, archiving system, or final notification application programming interface (API)
- **Notes**: Always succeeds in simulation; production may involve multi-step pre-close workflows
- **Automation potential**: **Medium** — archiving and standard notification steps can be automated; QA review and final approvals typically require human involvement.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.close_report.PreCloseAction`
- **Call-out point shape**: Actuator — fires integration hooks before case closure; invokes QA pipeline checks, final notification APIs, and case-archiving services.
  There is no content artifact placed on the blackboard; the side effects in external systems are the seam.
- **Factory-fn placement**: `vultron.core.behaviors.report.trigger_report_trees.create_close_case_trigger_tree` — Actuator between the not-already-closed guard and `TransitionRMtoClosed`.
  The DETERMINISTIC default is `AlwaysSucceed`, because a missing pre-close backend must not block closure.

## Closure model

Case closure is always the Case Owner's decision, sent as `Leave(VulnerabilityCase)` through `create_close_case_trigger_tree` (CM-23-001).
No protocol state closes a case on its own: public awareness (CS `P`) already tears down the embargo, and coordination often continues after embargo exit and disclosure.
The same `Leave(VulnerabilityCase)` from a non-owner participant removes only that participant (CM-23-003).
`create_close_report_tree` exists only as the injection seam for a future close-readiness monitor, which would suggest closure to the Case Owner rather than close the case.

---

## Other work

These nodes belong to `RMDoWorkBt` (`vultron/bt/report_management/_behaviors/do_work.py`), the general "do work" fallback tree that represents miscellaneous active work on an accepted vulnerability report outside of the more specific sub-trees.

### `OtherWork`

- **Node name**: `OtherWork`
- **btz type**: `AlwaysSucceed` (p=1.00)
- **Source file**: `report_management/fuzzer/other_work.py`
- **Parent tree**: `RMDoWorkBt`
- **Semantic function**: Action — placeholder for any additional work activities not covered by the more specific behavior tree (BT) sub-trees (e.g., internal documentation, stakeholder meetings, legal review, additional analysis)
- **Input dependency**: Site-specific work queue; human analyst tasks or automated workflow steps not yet modeled in the BT
- **Notes**: Always succeeds; this is an extensibility point for organizations to plug in their own workflow steps
- **Automation potential**: **Low** — intentional extensibility stub for unmodeled work; automation potential is entirely site-specific and cannot be assessed generically.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.other_work.OtherWork`
- **Call-out point shape**: Evaluator
- **Factory-fn placement**: Not placed in a production factory: `RMDoWorkBt` is a simulator compositor, and its sub-behaviors became individual trigger trees in `vultron/core/behaviors/report/`.
