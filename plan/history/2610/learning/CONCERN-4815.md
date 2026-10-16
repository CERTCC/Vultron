---
source: CONCERN-4815
timestamp: '2026-10-16T18:55:57.993750+00:00'
title: close-report trigger and PreCloseAction call-out are unreachable once a case
  holds the report
type: learning
---

## Concern

Once a case holds a report, no actor sends `Close(Report)` for it, and the CASE_MANAGER refuses one from every sender (CM-23-019, ADR-0144, #4746). Two things that lived on the `Close(Report)` path now have no live use:

- **The `close-report` trigger** (`SvcCloseCaseUseCase`, `create_close_case_trigger_tree`). It resolves the report's linked case and raises `VultronNotFoundError` when there is none, and it now fails closed (HTTP 409) when there is one. So it has no success path at all. A report no case holds is closed with `reject-report`; a case is closed with the owner's `close-case` (`Leave(VulnerabilityCase)`).
- **The `PreCloseAction` Actuator call-out** (capability model: "perform any pre-closure integration actions"). It is wired only into `create_close_case_trigger_tree`, between the not-already-closed guard and `TransitionRMtoClosed`, so it now never runs. The owner's `Leave` path (`SvcLeaveCaseUseCase`) runs no pre-close hook.

- **The `reject-report` trigger, by default.** It also sends `Close(Report)`, so it fails closed on a case too. Under the default `auto_create_case` policy the receiver creates the case when the report arrives, so in normal operation `reject-report` has a success path only for an actor running with `auto_create_case` off, before it creates a case.

## Why it needs a decision

Retiring the `close-report` endpoint is a client-visible API removal (the OpenAPI trigger snapshot freezes it), which agents may not make without approval. Moving `PreCloseAction` onto the `Leave` path is a design choice: whether it runs on every participant's `Leave` or only the Case Owner's, and whether before the CASE_MANAGER's decline check (CM-23-011) or only once the close is admitted.

## Options

1. Retire `close-report` and `create_close_case_trigger_tree`; move `PreCloseAction` into the owner's close-case trigger.
2. Keep `close-report` as a fail-closed compatibility endpoint; move `PreCloseAction` only.
3. Keep both as they are and document `PreCloseAction` as unreachable.

Where: `vultron/core/behaviors/report/trigger_report_trees.py` (`create_close_case_trigger_tree`), `vultron/core/use_cases/triggers/report.py` (`SvcCloseCaseUseCase`), `vultron/core/use_cases/triggers/case/leave.py`.

Where: vultron/core/behaviors/report/trigger_report_trees.py

**Resolved**: 2026-10-16 — implementation tracked in #4836.
Docs PR: <https://github.com/CERTCC/Vultron/pull/4835>.
Spec: `specs/triggerable-behaviors.yaml` (TRIG-02-001, TRIG-02-004, TRIG-02-006, TRIG-13).
ADR: ADR-0145 (proposed). Decision: retire `close-report`; replace demo `close-case` with a general-purpose `leave-case` trigger; run `PreCloseAction` on the leaving actor's side before the Leave, for every participant; fail the Case Owner's `leave-case` on an active embargo; `OtherCloseCriteriaMet` is superseded by calling the trigger.
