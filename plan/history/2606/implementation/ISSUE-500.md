---
source: ISSUE-500
timestamp: '2026-06-02T19:41:09.608578+00:00'
title: 'CBT-03: bounded pre-bootstrap queue expiry and replay'
type: implementation
---

## Issue #500 — CBT-03: Implement bounded pre-bootstrap queue expiry and replay

Implemented configurable expiry for the `VultronPendingCaseInbox` pre-bootstrap
queue so that CaseActor-originated activities held without a bootstrap
`Create(VulnerabilityCase)` are dropped with a warning after a configurable
timeout and a replay `Question` is sent to request re-bootstrap.

### Changes

- **`VultronPendingCaseInbox`**: added `queued_at` (UTC datetime,
  `default_factory=_now_utc`) and `case_actor_id` (`UriString | None`)
  fields to track queue age and originating CaseActor.
- **`AppConfig`**: added `pre_bootstrap_queue_timeout_seconds` (default 300 s,
  configurable via env var `VULTRON_PRE_BOOTSTRAP_QUEUE_TIMEOUT_SECONDS`).
- **`factories/case.py`**: added `bootstrap_replay_question_activity()` factory
  for the outbound replay `Question` (CBT-03-004 SHOULD); exported from
  `factories/__init__.py`.
- **`inbox_handler.py`**:
  - `_expire_pending_case_activities()` — checks queue age, drops expired
    queues with per-item WARNING logs, and emits a replay `Question`
    (CBT-03-003 MUST, CBT-03-004 SHOULD).
  - `_dispatch_or_defer_inbox_item()` — calls expiry check before queuing;
    if expired, drops the triggering activity (resend-required semantics).
  - `_replay_pending_case_activities()` — guards against late-arriving
    bootstrap for an already-expired queue; accepts optional `actor_id` for
    Question construction.
- **Tests**: 3 new tests covering AC-5 (queued not dispatched), AC-6
  (expiry drops + warns), AC-7 (expiry emits Question); all per CBT-05-003.

### Outcome

2557 unit tests pass. All linters clean (Black, flake8, mypy, pyright).
Code reviewed by rubber-duck and code-review agents — no issues found.

PR: [#674](https://github.com/CERTCC/Vultron/pull/674)
