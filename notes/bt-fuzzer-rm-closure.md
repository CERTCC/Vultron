---
title: "BT Fuzzer Nodes: RM Report Closure and Other Work"
status: active
description: >
  Catalog of fuzzer (stub) BT nodes for Report Closure (`CloseReportBt`)
  and Other Work (`RMDoWorkBt`) sub-workflows: close-case eligibility,
  transition guards, and extensibility stub nodes used in simulation.
  Includes design rationale for the trigger-driven closure model and
  Close Readiness Monitoring pattern.
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
- **Factory-fn placement**: Implemented as a call-out seam stub in
  `vultron.core.behaviors.report.close_report_tree.create_close_report_tree`
  (`other_close_criteria_factory` param; DETERMINISTIC default = `AlwaysFail`).
  This tree is a seam-only stub — it is **not invoked autonomously**. Case
  closure is always Case Owner-triggered via
  `create_close_case_trigger_tree`. The `OtherCloseCriteriaMet` Evaluator
  seam is the injection point for a future Close Readiness Monitoring Sentinel
  (see epic #1147 / #1143 Sentinel agent type) that observes protocol state
  and posts an observational note to the Case Owner when objective closure
  criteria are met; the Case Owner then issues `Leave(VulnerabilityCase)`
  directly. Resolved by IDEA-1253 (plan/1253-close-report-seam).

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
- **Factory-fn placement**: Wired in `create_close_case_trigger_tree`
  (issue T1 from IDEA-1253 planning, completed in #1854) — wired as an
  Actuator node between `CheckReportNotClosed` (or equivalent guard) and
  `TransitionRMtoClosed`. The DETERMINISTIC default is `AlwaysSucceed`
  (pre-close hooks are optional infrastructure; absence of a real
  implementation must not block closure). Not placed in
  `create_close_report_tree` — that tree is a seam-only stub for autonomous
  monitoring, not the trigger path.

---

## Design Rationale: Trigger-Driven Closure Model (IDEA-1253)

Derived from IDEA-1253 planning session (2026-07-31).

### Case closure is always Case Owner-triggered

There is no autonomous close path in Vultron. Case closure always requires
an explicit decision by the Case Owner (or Case Manager acting on their
behalf). The standard simulator closure criteria — CS.DEPLOYED across all
vendors, RM.DEFERRED, RM.INVALID — do not fire the `Leave(VulnerabilityCase)`
activity autonomously because:

- **CS.P → EM teardown cascade risk**: `CS.P` (public awareness) already
  triggers embargo teardown via the `#1836/#1841/#1842` mechanics. If
  `EM.EXITED + CS.P` were wired as an autonomous close trigger, every public
  disclosure would close the case — which is wrong. Coordination often
  continues after embargo exit and public disclosure.
- **Case Owner policy governs**: "nothing left to do, no reason to hold it
  open" is an organizational policy judgment, not a universal protocol signal.
  Standard protocol states (deployed, deferred, invalid) are necessary but not
  sufficient conditions; the Case Owner still decides when to close.

### `create_close_report_tree` is a call-out seam stub

`vultron.core.behaviors.report.close_report_tree.create_close_report_tree`
is intentionally a seam-only stub. It is **not called by any use case**. Its
`OtherCloseCriteriaMet` Evaluator seam is the injection point for a future
Close Readiness Monitoring Sentinel (see **Close Readiness Monitoring** below).

### `PreCloseAction` belongs in the trigger tree

`PreCloseAction` (Actuator) fires *after* the Case Owner has decided to close
— it is wired in `create_close_case_trigger_tree` (completed in #1854),
between the not-already-closed guard and `TransitionRMtoClosed`. It is a pre-close hook
for QA pipelines, archiving, and final notification. The DETERMINISTIC default
is `AlwaysSucceed`; pre-close hooks must not block closure when no real
backend is injected.

### `Leave(VulnerabilityCase)` is correctly overloaded

`_RmCloseCaseActivity` (`as_Leave` of `as_VulnerabilityCase`) is used by both
Case Owners and non-owner participants:

- **Case Owner** sends it → case closes for all participants.
- **Non-owner participant** sends it → they are removed from case participants.

The distinction is enforced by the Case Owner role, not a separate message
type. No vocabulary change is needed.

### Close Readiness Monitoring (future — epic #1147 / #1143)

When a future Sentinel coordination agent is implemented, the intended pattern
is:

1. A Sentinel observes protocol state for objective preconditions (e.g.,
   all vendors at CS.DEPLOYED, embargo exited and no pending activity for N
   days, all participants at RM.DEFERRED or RM.INVALID).
2. When preconditions are met, the Sentinel posts an **observational note** to
   the VulnerabilityCase (not a formal protocol question). The note surfaces
   the evidence and suggests the Case Owner consider closing.
3. The Case Owner reads the note and issues `Leave(VulnerabilityCase)` when
   ready. There is no protocol-level reply to the note.

This pattern avoids inventing a new `Question` → `Answer` message exchange.
The Sentinel fires into `OtherCloseCriteriaMet` seam in
`create_close_report_tree`; the Case Owner's subsequent `Leave` flows through
`create_close_case_trigger_tree` as usual.

Track under epic #1147 (Coordination Agents), linked to #1143 (Sentinel
agent type).

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
