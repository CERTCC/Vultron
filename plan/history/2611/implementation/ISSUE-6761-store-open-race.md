---
source: ISSUE-6761-store-open-race
timestamp: '2026-11-20T15:54:28.845877+00:00'
title: Demo Integration failure from the SQLite store first-open race
type: implementation
---

PR: https://github.com/CERTCC/Vultron/pull/6768

Closes #6761 (CI failure: Demo Integration on main).

Root cause: a request thread and a background timer (sender-sequence hold
sweep, ledger position statements) could open the same new actor store at
once. Each ran `create_all` on its own connection; both checked for the
tables before either created them, and the loser failed with
"table vultron_objects already exists", returning 500 during demo seeding.

Outcome: `get_datalayer` opens each (actor, URL) store under a per-key lock;
`get_actor_engine` builds one engine per URL under a lock; the store caches
are snapshotted under their locks; `SqliteDataLayer` holds a per-engine
`schema_guard` around `create_all`. The fix is shared with #5999.
