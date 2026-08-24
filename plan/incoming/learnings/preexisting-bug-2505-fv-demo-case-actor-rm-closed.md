# Pre-existing bug: FV demo CaseActor never reaches RM.CLOSED

Issue: #2505
Branch: task/1467-sync-write-producing-skills (issue #2287)

## Finding

`test/demo/test_fv_demo.py::TestCaseLedgerInvariants::test_all_participants_rm_closed_at_scenario_end`
fails on `main` with the same error as on the issue #2287 branch:
`Participants not in RM=CLOSED at scenario end: {'…/case-actor-…': 'ACCEPTED'}`

## Root Cause

The FV demo scenario never closes the case from the CaseActor's perspective,
so the CaseActor's `CaseParticipant` stays at `RM.ACCEPTED`.

## How it was masked

Before #2287, `_CommitNativeLedgerEntriesNode` received no `wire_render_port`
and returned FAILURE early, leaving CaseActor ledger entries uncommitted.
The assertion only checked tracked participants, so the CaseActor was invisible.

## Evidence

Verified by stashing all branch changes and running the test on clean main —
it fails identically.

## Fix needed (issue #2505)

Update the FV demo scenario to drive the CaseActor to RM.CLOSED, or exclude
CaseActors from the RM.CLOSED invariant check if they are not expected to
participate in the FV RM lifecycle.
