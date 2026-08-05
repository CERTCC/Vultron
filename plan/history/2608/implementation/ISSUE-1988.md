---
source: ISSUE-1988
timestamp: '2026-08-05T20:45:25.728841+00:00'
title: Logging narrative remediation (demote infra INFO, add RM/CS/EM lines)
type: implementation
---

## Issue #1988 — fix(logging): demote infrastructure INFO lines; add RM/CS/EM narrative messages

PR: <https://github.com/CERTCC/Vultron/pull/2008>

Implements the two-pass logging remediation from CONCERN-1968 (#1968) so that
reading an actor's INFO log tells the complete CVD protocol story without
dropping to DEBUG. All 22 acceptance criteria satisfied.

**Pass 1 (SL-04-007) — 11 infrastructure patterns demoted to DEBUG:**
DataLayer store/save/update, the `BT structure` and `Final BT state` tree dumps
(now also skipped entirely at INFO via an `isEnabledFor` guard), the duplicate
activity-parsing pair, the outbox preamble, pipeline outcome echoes, the
per-recipient sync queue line, per-participant storage chatter, routine
idempotency skips, and the `discover_actors()` object dump (ID only at INFO).

The `transitions` library logs FSM enter/exit callbacks at INFO on every
RM/EM/CS/PEC step and cannot be demoted at the call site. New
`vultron/logging_setup.py` pins those loggers above INFO from both entry points
(`configure_logging()`, demo CLI) and restores them on lifespan shutdown, so a
`TestClient` lifetime does not silently reconfigure logging for everything after
it.

**Pass 2 (SL-04-001, SL-04-006) — 7 narrative messages added** via shared
helpers in new `vultron/core/behaviors/narrative_log.py`, which owns the
template so call sites cannot drift (CS-22-001). Each line is wired at the
narrowest choke point that knows the before-state:

- RM → `update_participant_rm_state()` (the primary write path)
- RM → also `CreateParticipantStatusNode`, a *second* per-participant RM write
  path (used by the leave-case RM → CLOSED nodes) that would otherwise have
  left AC-12 unmet
- CS/VFD + CS/PXA → `CreateParticipantStatusNode` (shared writer)
- EM → `SetEmbargoActiveNode`, `ClearActiveEmbargoNode`, `ApplyEmbargoTeardownNode`
- engagement → `SvcEngageCaseUseCase`, reading the after-state back from storage
- invite receipt → `InviteActorToCaseReceivedUseCase`

AC-18 was satisfied by folding `get_failure_reason()` into the *existing*
`BT execution completed: Status.FAILURE` line rather than adding a second
record — a separate line would have double-logged, fired for the many callers
that treat FAILURE as an expected idempotent skip (and log their own reason at
DEBUG), and had no reliable `case_id` to report.

**Three correctness guards found during self-review**, each a case where the
new line would have been actively misleading:

1. No-op writes emit nothing. A repeat PXA write re-announced the
   public-disclosure milestone; a repeat engage claimed `RM ACCEPTED → ACCEPTED`.
2. The PXA before-state must come from the participant's own latest
   `case_status.pxa`. `CreateParticipantStatusNode` never appends to
   `case.case_statuses`, so reading `case.current_status` reported a stale `pxa`
   forever.
3. Backward CS moves log at WARNING labelled `state regression`. CS events are
   monotonic, so a regression is an anomaly, not a milestone; previously the
   label fell through to `no change`, producing a line that claimed a transition
   and denied it in the same breath.

**AC-22 is an executable ratchet**, not a manual grep:
`test/architecture/test_infrastructure_logs_not_at_info.py` walks `vultron/`
with `ast` and fails when any demoted fragment appears in a `logger.info()`
format string. Its own detector is tested so it cannot go vacuously green, and
its coverage limits are documented inline.

**Verification:** 6318 unit tests pass (79 new), 1006 integration tests pass,
0 failures. Black, flake8, mypy, pyright, markdownlint clean. Two regression
tests (repeat-PXA, RM-via-node) fail against the first-pass implementation and
pass after the fixes.

Also fixed an unclosed-`SqliteDataLayer` fixture in
`test_actor_and_announce_nodes.py` that made a latent `ResourceWarning` flake
reproducible.
