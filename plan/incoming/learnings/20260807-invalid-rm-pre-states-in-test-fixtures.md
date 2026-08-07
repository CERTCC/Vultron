---
title: Test fixtures with invalid RM pre-states pass vacuously after fail-closed validation
type: learning
timestamp: 2026-08-07
source: ISSUE-2081
signal: concern
---

Three pre-existing test files (`test_develop_fix_tree.py`, `test_announce_tree.py`,
`test_close_case_role_semantics.py`) seeded participants at `RM.START` and then
attempted to write `RM.CLOSED`. These tests had been passing because
`CreateParticipantStatusNode` was fail-open — it accepted any target state.

After the fail-closed validation landed, those tests failed because `START→CLOSED`
is not a valid RM transition. The tests were fixed by seeding participants at
`RM.ACCEPTED` first (a valid pre-state for CLOSED).

The underlying risk: test fixtures can silently produce unrealistic protocol
scenarios (impossible state sequences) and the test suite won't catch this until
something validates the transitions. We have no BTTestScenario or fixture-level
guard that asserts "this participant's RM history is a valid sequence of transitions."

A future concern issue could track: add a fixture-level invariant check that
validates the RM/VFD/PXA transition sequence of seeded `ParticipantStatus` records,
or add a warning when `BTTestScenario.seed()` detects an impossible transition in
the seeded history.
