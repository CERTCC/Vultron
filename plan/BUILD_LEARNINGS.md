## Implementation Notes

Longer-term notes can be found in `/notes/*.md`. This file is ephemeral
and will be reset periodically, so it's meant to capture more immediate
insights, issues, and learnings during the implementation process.

Append new items below any existing ones, marking them with the date and a
header.

### 2025-05-25 TWO-ACTOR-DEMO — Case Actor URN-based ID delivery limitation

**Issue**: The Case Actor uses a URN-based ID
(`urn:uuid:{uuid}/actors/case-actor`), so HTTP delivery via
`DeliveryQueueAdapter` always fails silently. Inbox handlers on the
Case Actor never execute for status updates sent by participants.

**Fix applied in #463 / PR #474**:

- `SvcAddParticipantStatusUseCase._update_local_participant()` appends
  status to the local participant record immediately after creation
  (self-report pattern with idempotency guard).
- `SvcAddParticipantStatusUseCase._maybe_terminate_embargo()` directly
  calls `SvcTerminateEmbargoUseCase` when CASE_OWNER signals public
  awareness — replicates what the Case Actor inbox handler would do.
- `_all_participants_closed()` and demo polling helpers skip
  CASE_MANAGER participants (coordinator role, not self-reporting).

**Broader lesson**: Any co-located deployment where Case Actor has a
non-HTTP ID needs local-consistency fallbacks. This is a workaround;
the proper fix is ensuring Case Actor has a routable HTTP ID or using
in-process dispatch for co-located actors.

---

### 2026-05-08 TWO-ACTOR-DEMO — Case Actor spawning blocks #463

**Issue**: Issue #463 (Two-actor demo, complete VFDPxa workflow) cannot be
implemented until Case Actor spawning and CASE_MANAGER delegation automation
are in place (tracked in new Issue #469, linked as sub-issue of #463).

**Root cause**: `_run_submit_report_case_creation` in `received/report.py`
calls `create_receive_report_case_tree` without an `actor_config`, so the
Vendor participant is created with only `[CVDRole.CASE_OWNER]`, not
`CASE_MANAGER`. `SvcAddParticipantStatusUseCase` (triggers/case.py line
406-420) iterates participants for `CVDRole.CASE_MANAGER` and raises
`VultronNotFoundError` if none found — which means all `notify-fix-ready`,
`notify-fix-deployed`, `notify-published`, and `close-case` demo triggers
fail immediately after case creation.

**Three non-trivial missing pieces** (consolidated into #469):

1. Case Actor spawning BT node in `receive_report_case_tree.py`
2. `OfferCaseManagerRoleReceivedUseCase` auto-accept + embargo init (skeleton
   only in `received/actor.py`; BT logic deferred by PR #468)
3. `AcceptCaseManagerRoleReceivedUseCase` trust bootstrap — send
   `Create(VulnerabilityCase)` to Reporter

**Note**: Issue #467 (refactor `AddParticipantStatusToParticipant` to BT) is
narrower than #469 and does not cover spawning or delegation.

---

### 2026-05-06 PCR — Replica seeding and deferred inbox replay

- First-time `Announce(VulnerabilityCase)` seeding cannot require a locally
  stored CaseActor yet; only reject the sender when a CaseActor for that case
  is already known and does not match.
- Unknown case-context activities need actor-scoped persisted deferral so the
  inbox can replay them after a later `Announce(VulnerabilityCase)` seeds the
  missing replica.
- Reporter-side report-to-case tracking benefits from a dedicated persisted
  link object so later announce handling can attach a received case replica to
  an earlier submitted report without scanning unrelated state.
