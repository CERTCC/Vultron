---
source: ISSUE-1525
timestamp: '2026-07-20T16:48:33.230339+00:00'
title: fix concurrent inbox background tasks out-of-order processing
type: implementation
---

## Issue #1525 — Flaky CI: FVV Demo Integration times out in `wait_for_contiguous_ledger_coverage`

### Symptoms

The FVV demo integration test intermittently timed out (15 s) waiting for all
ledger entries to be present on a replica's DataLayer during case closure.
The timeout was flaky — same code, same environment, so infrastructure was
ruled out; the root cause had to be a code-level race.

### Root Cause

`post_actor_inbox` (sync `def`) schedules `run_inbox_pipeline` as a FastAPI
`BackgroundTask`.  When two HTTP POSTs for the same actor arrive close
together (common during fan-out from `FanOutLogEntryNode`), each creates a
separate asyncio Task.  Within a single Task, `process_payload` is
synchronous and has no `await` points, so it runs atomically.  But if the
asyncio event loop schedules Task_{N+1} before Task_N has stored its ledger
entry, the hash-chain check in `CheckHashMatchesNode` sees:

    tail = hash(N-1)     entry_{N+1}.prev_log_hash = hash(N)  → MISMATCH

This triggers a Reject → Replay cycle that may not converge before the demo
timeout.

The existing `_BT_GLOBAL_LOCK` (`threading.RLock`) guards the BT blackboard
from thread-pool concurrency but does **not** prevent asyncio-level task
interleaving — these are orthogonal concerns.

The outbox was confirmed FIFO (`.order_by(col(QueueEntry.id))`); the problem
is exclusively on the inbox receive side.

### Fix

Added `_actor_inbox_locks: dict[str, asyncio.Lock]` and `_get_actor_lock()`
in `vultron/adapters/driving/fastapi/inbox_orchestration.py`.
`run_inbox_pipeline` acquires the per-actor lock before `process_payload` and
the inbox replay loop, and releases it before `outbox_handler` so HTTP
delivery for a second actor is not blocked.

### Regression Test

`test/adapters/driving/fastapi/test_inbox_orchestration_lock.py` — uses
`asyncio.gather` to schedule two pipelines for the same actor concurrently,
forcing the scheduler to interleave them.  With the lock both entries are
stored; without it entry N+1 fails the hash-chain check.

### PR

<https://github.com/CERTCC/Vultron/pull/1533>
