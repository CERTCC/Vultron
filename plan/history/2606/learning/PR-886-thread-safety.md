---
source: PR-886-thread-safety
timestamp: '2026-06-11T18:37:44.091468+00:00'
title: Global py_trees blackboard not thread-safe under FastAPI BackgroundTasks —
  BTBridge RLock fix
type: learning
---

## 2026-06-10 PR-886 — Global py_trees blackboard not thread-safe under FastAPI BackgroundTasks

- FastAPI runs synchronous `BackgroundTask` callables via
  `anyio.to_thread.run_sync`, putting them on a thread-pool. Two BT
  executions can therefore run on different threads simultaneously,
  both writing to `py_trees.blackboard.Blackboard.storage` (process-global).
- The race: Thread A's `execute_with_setup` writes `actor_id=A` and
  `datalayer=DL_A`; Thread B overwrites them with `actor_id=B` / `datalayer=DL_B`;
  Thread A then reads the wrong `actor_id`, queueing its outbound activity
  under the wrong actor's outbox — the activity is silently lost. Thread B
  may also crash when Thread A's cleanup removes `/datalayer` before B reads it.
- Fix: wrap the entire setup→execute→cleanup critical section in
  `BTBridge.execute_with_setup` with a module-level `threading.RLock`.
  `RLock` (not `Lock`) is required because `lifecycle.py` BT nodes call
  `execute_with_setup` recursively — a plain `Lock` deadlocks there.
- Demo symptom: M7 check ("all participants RM.CLOSED on both replicas") timed
  out because finder's CLOSED `Add(ParticipantStatus)` was silently queued to
  the case-actor's outbox in finder's DataLayer (never processed) instead of
  finder's own outbox.

**Promoted**: 2026-06-11 — corrected the "single-threaded execution" claim
in `notes/bt-integration.md` § "Concurrency Model"; added `AGENTS.md`
pitfall "BTBridge Global Blackboard Is Not Thread-Safe Under FastAPI
BackgroundTasks".
Docs PR: <https://github.com/CERTCC/Vultron/pull/900>.
