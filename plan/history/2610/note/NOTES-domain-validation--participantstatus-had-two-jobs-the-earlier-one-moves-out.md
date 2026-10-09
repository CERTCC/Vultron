---
source: NOTES-domain-validation--participantstatus-had-two-jobs-the-earlier-one-moves-out
timestamp: '2026-10-02T16:28:29.672247+00:00'
title: '`ParticipantStatus` had two jobs; the earlier one moves out'
type: note
---

**Archived:** 2026-10-02
**Reason:** delivered + redundant — the pre-case RM state moved to VultronReportCaseLink.rm_state; the marker helpers are deleted; the no-inner-writer rule is BTND-10-004 with its ratchet
**Superseded by:** ADR-0089; vultron/core/models/report_case_link.py; BTND-10-004, BTND-10-005

---

## `ParticipantStatus` had two jobs; the earlier one moves out

Most `ParticipantStatus` records are rungs on a participant's ladder, in
`CaseParticipant.participant_statuses`. `_ReportPhaseRMTransition` wrote a
*standalone* record under a deterministic id from `(actor, report, rm_state)`,
and callers asked "does that id exist?" to mean "has this step happened?" It
existed because RM state starts at report receipt and the case may not exist
yet — or ever: a receiver may declare a bare report `INVALID` or `CLOSED` and
never propose a case.

The two jobs were already entangled, which is why "separate lifecycle" was the
wrong reading:

- `_build_owner_initial_status()` reused the marker's **id** for the
  participant's first ladder rung, so marker and rung became one record.
- `_get_or_create_accepted_status()` assigned directly to the stored record
  (`existing.cvd_role = …`, `existing.consent = …`, `existing.context = …`) and
  saved it — the post-construction mutation door documented above — and created
  the record outright when absent.

ADR-0089 resolves it by relocation rather than by adding a rule: the pre-case RM
state becomes a field on `VultronReportCaseLink`, which ADR-0041 already created
for exactly that window, and the marker plus `_report_phase_status_id()`,
`report_phase_context()` and `_current_report_phase_rm_state()` are deleted.
`ParticipantStatus` is then ladder-only with one writer, and the writer always
has a case — so no fourth ADR-0087 disposition is needed.

**Do not reach for the writer from inside another node (BTND-10-004).** Five
sites used to build `CreateParticipantStatusNode` inside their own `update()`
and call `node.update()` directly — six such calls, because `develop_fix.py`
builds it once in a shared `_make_status_node()` helper and ticks it from two
places. That skips `setup()` and the tick cycle, and two of the sites
(`deploy_fix.py`, and `develop_fix.py` on both of its calls) wrapped it in
`try/except`, which is the swallowing shape
[bt-pitfalls.md](bt-pitfalls.md) § "Always Check
`BTBridge.execute_with_setup` Return Value" warns about. The node is always a
real tree child. The architecture ratchet
`test/architecture/test_participant_status_validation.py` (AC-9) fails any
`update()` body that re-introduces this construction.

**One mechanism per input (BTND-10-005).** `case_id` is always the blackboard
port (`CaseIdInputPortMixin`) — the only mechanism that works in received trees,
where the case is found at tick time by dereferencing the report; trees that
know it at build time seed `/case_id` through
`BTBridge.execute_with_setup(**context_data)`. The *subject* actor is always an
explicit argument, never a fallback to the blackboard `actor_id`, because the
blackboard actor is the *executing* actor and conflating the two was #2300.
`CreateParticipantStatusNode.__init__` deliberately has no `case_id` parameter;
the ratchet (AC-9) fails any constructor signature that adds one.
