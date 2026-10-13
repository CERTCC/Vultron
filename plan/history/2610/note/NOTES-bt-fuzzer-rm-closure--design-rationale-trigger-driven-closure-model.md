---
source: NOTES-bt-fuzzer-rm-closure--design-rationale-trigger-driven-closure-model
timestamp: '2026-10-12T19:39:00.736187+00:00'
title: 'Design Rationale: Trigger-Driven Closure Model (IDEA-1253)'
type: note
---

**Archived:** 2026-10-12
**Reason:** delivered: closure is Case Owner-triggered via create_close_case_trigger_tree and PreCloseAction is wired there; the lasting rule moved to the docs page, and the future close-readiness monitor plan moved to epic #1147
**Superseded by:** CM-23-001, CM-23-003; docs/developer/reference/bt-fuzzer/rm-closure.md § Closure model; #1147

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

When a future Sentinel capability is implemented, the intended pattern
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

Track under epic #1147 (Capability Shapes), linked to #1143 (Sentinel
capability shape).
