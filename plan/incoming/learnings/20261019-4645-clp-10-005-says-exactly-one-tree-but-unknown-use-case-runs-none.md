---
title: "CLP-10-005 says every received use case runs exactly one tree, but UnknownUseCase runs none"
type: learning
timestamp: "2026-10-19T14:10:00Z"
source: ISSUE-4645
signal: spec-contradiction
---

**Trigger.** You are reading or enforcing CLP-10-005 ("A received-side use case
MUST run exactly one BT per inbox delivery") or the `RUNS_NO_TREE` set in
`test/architecture/test_single_bt_execution_received_side.py`.

**Claim.** The statement says "exactly one", but
`vultron/core/use_cases/received/unknown.py` `UnknownUseCase.execute()`
refuses unrecognized semantics without running a tree, and its verification
text says "at most one". The test therefore asserts at most one, plus an exact
`RUNS_NO_TREE` set naming the one zero-run handler. Either the statement should
name the unroutable-delivery case (refused before any case is known) as outside
"exactly one", or `UnknownUseCase` should run a refusal tree. The statement also
names helpers "under `vultron/core/use_cases/`" while the test, like CLP-10-020's,
also follows `vultron/core/services/` (BT-22-005); the statement could say so.

**Evidence.** PR #4875 (ISSUE-4645) pre-push review finding
`phase10-embargo-exactly-one-coverage-lost-0` and its `self-check` note.
