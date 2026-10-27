---
stakeholder_type: [project-contributor]
---

# Report closure and other work fuzzer nodes

These stub nodes belong to two trees.
`RMCloseBt` (`vultron/bt/report_management/_behaviors/close_report.py`) models the closure of a report after the Coordinated Vulnerability Disclosure (CVD) workflow ends.
`RMDoWorkBt` (`vultron/bt/report_management/_behaviors/do_work.py`) is the fallback tree for miscellaneous work on an accepted report.

See the [fuzzer node index](index.md) for the entry format, the automation-potential and call-out shape values, and the base-type probabilities.

## Report closure

### `OtherCloseCriteriaMet`

- **Node name**: `OtherCloseCriteriaMet`
- **btz type**: `UsuallyFail` (p=0.25)
- **Source file**: `report_management/fuzzer/close_report.py`
- **Parent tree**: `RMCloseBt`
- **Semantic function**: Condition — check whether the case meets site-specific or case-specific closure criteria, in addition to the standard CVD completion conditions
- **Input dependency**: Human analyst decision or a policy-driven checklist, specific to the CVD policy of the organization
- **Notes**: Fails most of the time in simulation, because non-standard closure criteria are uncommon.
  Examples are an editorial board sign-off or the completion of a legal review.
- **Automation potential**: **Low** — site-specific.
  Closure criteria vary widely by organization and case context.
  They usually need a human policy evaluation or an explicit sign-off.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.close_report.OtherCloseCriteriaMet`
- **Call-out point shape**: Evaluator
- **Factory-fn placement**: `vultron.core.behaviors.report.close_report_tree.create_close_report_tree` (`other_close_criteria_factory` param, DETERMINISTIC default `AlwaysFail`).
  That tree is a seam-only stub that no use case calls.
  See [Closure model](#closure-model).
  The call-out is superseded: the decision it asked is now the act of calling the `leave-case` trigger (ADR-0145).

### `PreCloseAction`

- **Node name**: `PreCloseAction`
- **btz type**: `AlwaysSucceed` (p=1.00)
- **Source file**: `report_management/fuzzer/close_report.py`
- **Parent tree**: `RMCloseBt`
- **Semantic function**: Action — do the site-specific tasks that must be complete before a report can close, such as a quality assurance review, a final Participant notification, or archiving
- **Input dependency**: Integration hook to a quality assurance (QA) pipeline, an archiving system, or a final notification application programming interface (API)
- **Notes**: Always succeeds in simulation.
  In production, it can include multi-step pre-close workflows.
- **Automation potential**: **Medium** — archiving and standard notification steps are automatable.
  QA review and final approvals usually need human involvement.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.close_report.PreCloseAction`
- **Call-out point shape**: Actuator — fires integration hooks before case closure.
  It invokes QA pipeline checks, final notification APIs, and case-archiving services.
  It puts no content artifact on the blackboard.
  The side effects in external systems are the seam.
- **Factory-fn placement**: `vultron.core.behaviors.case.leave_case_trigger_tree.create_leave_case_trigger_tree` — Actuator after the embargo guard of the Case Owner, and before the tree builds and queues the `Leave(VulnerabilityCase)` (TRIG-13-002, TRIG-13-003).
  The DETERMINISTIC default is `AlwaysSucceed`, because a missing pre-close backend must not block closure.
  It runs for every participant that calls `leave-case`.
  A failing backend fails the trigger, and the trigger sends nothing.

## Closure model

Case closure is always the decision of the Case Owner, sent as `Leave(VulnerabilityCase)` through the `leave-case` trigger (CM-23-001, TRIG-13-001).
After a case holds the report, no actor sends `Close(Report)` for it, and the CASE_MANAGER refuses one from every sender (CM-23-019).
No protocol state closes a case on its own.
Public awareness (CS `P`) already tears down the embargo, and coordination often continues after embargo exit and disclosure.

The same `Leave(VulnerabilityCase)` from a non-owner participant removes only that participant (CM-23-003).
`create_close_report_tree` exists only as the injection seam for a future close-readiness monitor.
That monitor would suggest closure to the Case Owner, and would not close the case itself.

---

## Other work

These nodes belong to `RMDoWorkBt` (`vultron/bt/report_management/_behaviors/do_work.py`), the general "do work" fallback tree.
It represents miscellaneous active work on an accepted vulnerability report that the more specific sub-trees do not cover.

### `OtherWork`

- **Node name**: `OtherWork`
- **btz type**: `AlwaysSucceed` (p=1.00)
- **Source file**: `report_management/fuzzer/other_work.py`
- **Parent tree**: `RMDoWorkBt`
- **Semantic function**: Action — placeholder for other work activities that the more specific behavior tree (BT) sub-trees do not cover.
  Examples are internal documentation, stakeholder meetings, legal review, and more analysis.
- **Input dependency**: Site-specific work queue, with human analyst tasks or automated workflow steps that the BT does not model yet
- **Notes**: Always succeeds.
  This node is an extension point, where organizations can add their own workflow steps.
- **Automation potential**: **Low** — intentional extension stub for unmodeled work.
  Its automation potential is fully site-specific, and a general assessment is not possible.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.other_work.OtherWork`
- **Call-out point shape**: Evaluator
- **Factory-fn placement**: Not placed in a production factory.
  `RMDoWorkBt` is a simulator compositor, and its sub-behaviors became individual trigger trees in `vultron/core/behaviors/report/`.
