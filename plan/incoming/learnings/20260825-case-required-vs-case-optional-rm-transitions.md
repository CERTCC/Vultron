---
title: RM transitions split into case-required and case-optional; one node cannot serve both
type: learning
timestamp: 2026-08-25
source: ISSUE-2548
signal: design-question
---

The #2548 brief was to put "resolve this store's case for a report" behind a
single reusable BT rather than N implementation sites. That was done — but not by
collapsing every RM transition into one node, and the reason is worth recording
because it will come up again.

The RM transitions divide cleanly on whether a case is *required*:

| Case **required** | Case **optional** |
|---|---|
| `TransitionRMtoValid` (DUR-07-004 needs an embargo, which only exists on a case; engage-case reads the case-scoped participant state) | `TransitionRMtoInvalid` |
| `TransitionCaseParticipantRMtoClosed` / `…toInvalid` | `TransitionRMtoClosed` |
| `EnsureEmbargoExists` | `_get_or_create_accepted_status` |

A receiver may legitimately declare a bare report invalid, or close it, before any
case exists — that is the ordinary reject path. Requiring the case there would
turn a correct refusal into a FAILURE, so a single "resolve the case or fail" node
in front of everything would be wrong, not merely strict. The case-optional sites
need the case only to pick a `context` value (case URI once a case exists,
report URI before that — CLP-07-007).

So the DRY answer taken was to name the distinction **once** rather than to erase
it:

- case-optional sites share one `report_phase_context()` helper
  (`models/_helpers.py`) — was 4 verbatim copies of
  `case.id_ if isinstance(...) else report_id`;
- case-required sites share one producer/consumer pair,
  `RequireCaseForReport` (writes `/case_id`) and `CaseIdInputPortMixin` (reads
  it), both in `behaviors/case/nodes/case_lookup.py`;
- the report-phase latch itself has exactly one construction site,
  `_ReportPhaseRMTransition._write_latch`, down from three near-identical ~55-line
  nodes. The architecture ratchet in
  `test/architecture/test_vfd_rm_pxa_write_sites.py` records the 3→1 collapse.

A tree now resolves "the case for this report" once per tick, and the mixin lives
next to its producer so the `/case_id` contract has one definition.

**How to apply.**

- Before unifying protocol nodes that look alike, check whether they differ on a
  *precondition* rather than on behaviour. Same body, different required inputs is
  a base class plus declarations — not one node with a flag.
- `CaseIdInputPortMixin` declares `case_id` **optional** deliberately: required
  would make `setup()` raise, where a missing case should be ordinary control flow
  the enclosing composite handles. The node still MUST return FAILURE on absence
  (ARCH-15-001) — that is `_resolve_case_id()`'s whole job.
- Pre-existing debt this consolidation concentrated rather than created:
  `rm_transitions.py` imports `_idempotent_create` and
  `update_participant_rm_state` from `use_cases/`, which `BTND-04-003` forbids.
  One base class now carries the violation instead of three nodes — smaller, but
  more central.
