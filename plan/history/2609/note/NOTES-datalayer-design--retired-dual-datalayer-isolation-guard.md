---
source: NOTES-datalayer-design--retired-dual-datalayer-isolation-guard
timestamp: '2026-09-01T22:01:08.758931+00:00'
title: 'Retired: dual-DataLayer isolation guard in tests'
type: note
---

Archived from `notes/datalayer-design.md` § "RETIRED: Dual-DataLayer Isolation
Guard in Tests" (ISSUE-1749, 2026-08-08; retired by ADR-0073 / ISSUE-2238,
2026-08-20).

Removed from `notes/` because the pattern no longer has anything to guard and
notes/ states current understanding only. The section's *live* content — the two
store-scoping hazards and the autouse `_dispose_actor_stores_between_tests`
fixture — was kept in `notes/datalayer-design.md` under the accurate title
§ "One Actor Id Is One Database". Only the retirement narrative was archived:

> This pattern no longer has anything to guard. It asserted that a BT node had not
> written to the process-global *unscoped* singleton instead of the injected
> DataLayer, by checking the singleton was empty afterwards.
>
> There is no unscoped singleton. `get_datalayer()` requires an actor and returns
> that actor's own store (DL-07-002), so the "shared/admin" instance the guard
> watched does not exist. The four tests built on the pattern were rewritten, and
> one of them — `test_actor_isolation` — turned out to assert `... or True`, so it
> could not have failed either way.
>
> What replaces it is stronger and needs no test discipline: a BT's store is the
> store of its executing actor, reconciled once in `BTBridge._store_for_actor`
> (BT-05-005). A node cannot write to "some other" store by forgetting to use
> `self.datalayer`, because there is no ambient store to reach for.
>
> References: ADR-0073 and ISSUE-2238 for the decision itself. The rewritten
> tests are in
> `test/core/behaviors/case/test_case_proposal_received_tree.py::TestCreateCaseProposalReceivedBTCaseActorRecords`,
> which now asserts against each actor's own store rather than against an empty
> singleton.
