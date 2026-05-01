---
title: "Bug Fixes: BUG-471.5, BUG-471.6, BUG-471.7a, BUG-471.7b"
type: implementation
timestamp: '2026-04-29T16:35:42+00:00'

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

---

## BUG-471.1 — CaseLogEntry Serialization + Hash-Check Timeout

Fixed `AnnounceLogEntryActivity` by overriding `object_: CaseLogEntry` with a
concrete typed field so `model_dump()` always serialises the full domain
payload. Applied `serialize_as_any=True` in both `_coerce_to_semantic_class()`
and `outbox_handler.handle_outbox_item()`. Regression tests added at both the
persistence and delivery boundaries. Resolves issues #378 and #379.

**Artifacts**: `vultron/wire/as2/vocab/activities/sync.py`,
`vultron/adapters/driven/datalayer_sqlite.py`,
`vultron/adapters/driving/fastapi/outbox_handler.py`,
`test/adapters/driven/test_sqlite_backend.py`,
`test/adapters/driving/fastapi/test_outbox.py`

## BUG-471.2 — Accept/Invite Dehydration Strips Nested Domain Fields

Fixed `vultron/wire/as2/parser.py` so inbound `Accept` activities correctly
carry their nested inline `Invite`. Regression tests in `test/wire/as2/test_parser.py`
and `test/adapters/driven/test_sqlite_backend.py`. Resolves issues #382, #386.

**Artifacts**: `vultron/wire/as2/parser.py`,
`vultron/wire/as2/vocab/activities/case.py`,
`test/wire/as2/test_parser.py`,
`test/adapters/driven/test_sqlite_backend.py`

## BUG-471.3 — Multi-Party Embargo Accept: 409 + PEC Invalid Transition

Fixed `SvcAcceptEmbargoUseCase` to gate the shared EM transition on
`is_case_owner and not case_already_active`. Non-owner participants now record
their per-participant PEC consent without triggering a second EM state
transition, eliminating the 409. Resolves issues #383 and #384.

**Artifact**: `vultron/core/use_cases/triggers/embargo.py`

## BUG-471.4 — actor_id Normalization in add_activity_to_outbox

Added `actor_id = actor.id_` after `resolve_actor()` in all trigger use cases
that call `add_activity_to_outbox` with a path-parameter UUID. Resolves #380.

**Artifacts**: `vultron/core/use_cases/triggers/case.py`,
`vultron/core/use_cases/triggers/actor.py`

## EMDEFAULT.1 — Default Embargo Initializes to EM.ACTIVE (not PROPOSED)

Updated `InitializeDefaultEmbargoNode.update()` in
`vultron/core/behaviors/case/nodes.py` to apply an atomic PROPOSE+ACCEPT
sequence via `create_em_machine()` + `EMAdapter` so `em_state` lands at
`EM.ACTIVE` immediately. The intermediate `EM.PROPOSED` state is never
persisted. Updated the test
`test_tree_sets_em_state_proposed_after_embargo_init` →
`test_tree_sets_em_state_active_after_embargo_init` to assert `EM.ACTIVE`.
Satisfies EP-04-001, EP-04-002.

**Artifacts**: `vultron/core/behaviors/case/nodes.py`,
`test/core/behaviors/case/test_receive_report_case_tree.py`
