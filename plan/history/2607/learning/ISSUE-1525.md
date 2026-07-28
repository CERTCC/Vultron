---
title: "Per-actor asyncio.Lock required to serialize concurrent inbox BackgroundTasks"
type: learning
timestamp: "2026-07-20T00:00:00+00:00"
source: ISSUE-1525
---

## Observation

FastAPI `BackgroundTask` schedules async coroutines as asyncio Tasks.
When two HTTP POSTs arrive for the same actor at nearly the same time (common
in demo flows where the CaseActor fans out to multiple participants in a tight
loop), each POST creates its own asyncio Task for `run_inbox_pipeline`.

`process_payload` is synchronous and has no `await` points, so within a single
Task it runs atomically.  But if the asyncio event loop schedules Task_{N+1}
before Task_N has completed, Task_{N+1}'s hash-chain check sees tail =
hash(N-1) while entry_{N+1}.prev_log_hash = hash(N) → MISMATCH → Reject →
Replay.  In a demo context the replay may not converge within 15 s, causing
`wait_for_contiguous_ledger_coverage` to time out.

## Fix

Added a per-actor `asyncio.Lock` (`_actor_inbox_locks` dict keyed by
`actor_id`) in `vultron/adapters/driving/fastapi/inbox_orchestration.py`.
`run_inbox_pipeline` acquires the lock before calling `process_payload` and
releases it before `outbox_handler`, so:

- Entries for the same actor are processed in arrival order.
- HTTP delivery (outbox) can proceed concurrently, so entries for a SECOND
  actor are not blocked while the first actor's outbox is being drained.

## Pitfall

The existing `_BT_GLOBAL_LOCK` (`threading.RLock`) protects against
thread-level concurrency from the sync thread pool but does NOT protect against
asyncio-level task interleaving within the single event loop thread.  These are
orthogonal concerns requiring orthogonal primitives.

## Test pattern

Regression test at `test/adapters/driving/fastapi/test_inbox_orchestration_lock.py`
uses `asyncio.gather` to run two pipelines for the same actor concurrently,
which forces the scheduler to interleave them.  With the lock, both entries are
stored; without it, the second fails the hash-chain check.

This project does NOT use `pytest-asyncio`.  Async tests are wrapped in a sync
`def test_...()` that calls `asyncio.run(_run())`.
