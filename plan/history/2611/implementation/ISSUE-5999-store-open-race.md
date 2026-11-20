---
source: ISSUE-5999-store-open-race
timestamp: '2026-11-20T15:54:29.575778+00:00'
title: Opening a new actor's SQLite store is safe under concurrent openers
type: implementation
---

PR: https://github.com/CERTCC/Vultron/pull/6768

Closes #5999 (opening a new actor's SQLite store can fail with
"table vultron_objects already exists"). Governing spec: DL-07-004.

Outcome: two openers of one new actor store both succeed.
- `get_datalayer` opens each (actor, URL) store under a per-key lock and
  returns one instance to concurrent callers.
- `get_actor_engine` makes one engine per store URL under a lock; disposal
  and the in-memory slug listing read the cache under it too.
- `SqliteDataLayer` takes a per-engine schema lock (`schema_guard`) around
  `create_all` on both pool kinds, inside `session_guard`.
- `get_all_actor_datalayers` and `reset_datalayer` read the instance cache
  under its lock, so a concurrent open cannot resize it mid-iteration.

Tests: `test/adapters/driven/datalayer_sqlite/test_concurrent_store_open.py`
pins both acceptance criteria (concurrent opens both succeed; one instance
per (actor, URL)).
