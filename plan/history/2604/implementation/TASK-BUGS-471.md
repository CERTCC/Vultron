---
title: "Bug Fixes: BUG-471.5, BUG-471.6, BUG-471.7a, BUG-471.7b"
type: implementation
date: 2026-04-29
source: TASK-BUGS-471
---

## BUG-471.5 — Spurious Rehydration Warning on Invite Target

Lowered `_rehydrate_fields` miss log from `WARNING` to `DEBUG` in
`vultron/adapters/driven/datalayer_sqlite.py`. This is an expected condition
during the normal INVITE→ANNOUNCE sequence: the case has not yet arrived, so
the string URI is kept unchanged. The handler already defers correctly; only
the log level was wrong.

**Artifact**: `vultron/adapters/driven/datalayer_sqlite.py`

## BUG-471.6 — EngageCaseBT / DeferCaseBT Empty Failure Reason

Replaced `result.feedback_message` with `BTBridge.get_failure_reason(tree)`
in all three BT failure warnings in `vultron/core/use_cases/received/case.py`
(CreateCaseBT, EngageCaseBT, DeferCaseBT). The Sequence root node's
`feedback_message` is always empty when a child fails; `get_failure_reason`
walks the tree depth-first to return the failing leaf's class name or message.
Two regression tests added to `test/core/use_cases/received/test_case.py`
verifying the warning includes a non-empty reason when participant is missing.

**Artifact**: `vultron/core/use_cases/received/case.py`,
`test/core/use_cases/received/test_case.py`

## BUG-471.7a — Docker README Before-You-Start Section

Added a "Before you start" section at the top of `docker/README.md`
instructing users to run `cp docker/.env.example docker/.env` before any
`docker compose` command. Resolves #390.

**Artifact**: `docker/README.md`

## BUG-471.7b — DataLayer Storage INFO Log Lines

Added `logger.info("DataLayer stored/saved/updated ...")` to the `create`,
`save`, and `update` methods of `SqliteDataLayer` so that demo steps that
reference DataLayer storage are now verifiable in live log output. Resolves
issue 391.

**Artifact**: `vultron/adapters/driven/datalayer_sqlite.py`
