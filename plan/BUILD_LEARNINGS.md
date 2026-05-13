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

**Fix applied in branch `task/463-two-actor-demo-replacement`**:

- `CreateCaseActorNode` now generates an HTTP-routable Case Actor ID
  (`{base_url}/actors/case-actor-{slug}`) instead of a URN-based path.
- `ASGIEmitter` (`vultron/adapters/driven/asgi_emitter.py`) delivers messages
  to co-located actors in-process via the ASGI interface, bypassing HTTP
  entirely for same-server recipients.
- `configure_default_emitter()` wires the `ASGIEmitter` at app startup so all
  outbox processing uses local delivery for co-located actors.

**Broader lesson**: Co-located actors must have HTTP-routable IDs, or an
in-process emitter must be configured so their inbox handlers actually fire.
The workaround of directly updating `SvcAddParticipantStatusUseCase` was
removed once proper delivery was in place.

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
