---
title: "Full unit run on a fresh origin/main branch fails in test_reject_sync — the reject tree now reaches SendMissingEntries without a sync_port"
type: learning
timestamp: "2026-09-28T17:30:00Z"
source: ISSUE-3760
---

While validating the `embargo_lifecycle` package split (#3760), the unit suite
reported two failures unrelated to the diff. One is the already-tracked flaky
`test_datalayer_get_existing_actor_by_id` (#3732). The other,
`test/core/use_cases/received/test_reject_sync.py::TestRejectLedgerEntryReceivedUseCase::test_updates_replication_state`,
fails deterministically on a detached checkout of `origin/main` at `c97286bac`
(the #3776 merge): `SendMissingEntries: sync_port must be injected to replay
entries`.

Filed as #3802, parented to #3760 so it stays visible in the epic tree. The
discovering PR does not touch `sync.py`, the sync BT, or that test.

Observation worth keeping: the last change to the reject tree reordered
`FindCaseActorNode` ahead of `UpdateReplicationStateNode`, and the test still
constructs the use case with no `sync_port`. Either the test's fixture or the
tree's gate is out of date; #3802 asks the #3776 author which.

**Promoted**: 2026-10-02 — Already closed — #3802 fixed and closed.
Docs PR: <https://github.com/CERTCC/Vultron/pull/4174>.
