---
title: Demo CI Invariant Harness Design
status: active
related_specs:
  - specs/demo-ci.yaml
  - specs/multi-actor-demo.yaml
---

# Demo CI Invariant Harness Design

Design notes for the case-ledger invariant harness in the demo CI workflow.

---

## Separate CI Job Pattern (DEMOCI-04)

**Problem**: When the demo run and the invariant harness share the same CI
job, a primary demo failure draws reviewer attention away from invariant
failures. In PR #1590, a missing notes-exchange phase failed silently across
multiple fix cycles because the invariant failure was masked by the demo
failure in the same job output.

**Solution**: The invariant harness for each scenario runs as a **separate
parallel CI job** that depends on the demo job via `needs:` and always runs
(`if: always()`). The invariant job downloads the case-log JSONL artifact
uploaded by the demo job and runs pytest against it.

This gives each scenario two independent pass/fail status entries on the PR:
one for the demo run, one for the invariant harness. Reviewers can see both
signals even when the demo itself fails.

**Job relationship per scenario matrix entry:**

```text
demo (matrix: fv) → uploads devlogs artifact
    ↓ (needs: demo, if: always())
invariant-harness (matrix: fv) → downloads artifact → runs pytest
```

---

## Per-Scenario Expected Event Types (DEMOMA-16)

**Problem**: All per-scenario `_XXX_EXPECTED_EVENT_TYPES` lists historically
contained only the four universal types (`validate_report`,
`add_participant_status_to_participant`, `close_case`, `add_note_to_case`),
regardless of the scenario's actual protocol coverage. This allowed
scenario-specific phases to regress silently (e.g. `invite_actor_to_case`
missing from a scenario that requires it).

**Design**: Each scenario defines its own required event-type list that
extends the four universal types with scenario-specific required phases.
The spec requirements in `specs/multi-actor-demo.yaml` DEMOMA-16-001 through
DEMOMA-16-008 are the normative source; the test constants implement them.

### Scenario required event types

| Scenario | Universal 4 | Additional required |
|---|---|---|
| FV | validate_report, add_participant_status_to_participant, close_case, add_note_to_case | (none) |
| FVV | same | invite_actor_to_case |
| FVCV-extension | same | invite_actor_to_case, offer_case_participant |
| FVCV-handoff | same | invite_actor_to_case, accept_invite_actor_to_case |
| FCCV-handoff | same | invite_actor_to_case, accept_invite_actor_to_case |
| FCV | same | invite_actor_to_case |

### Relationship to scenario-specific test functions

The expected-event-types list (Invariant 5) checks **presence** of an event
at least once. Scenarios that require an event to appear **N or more times**
(e.g. `invite_actor_to_case` at least twice in FCV, FVCV-*, FCCV-*) use
separate `test_XXX_<event>_at_least_N` functions built on
`check_event_type_count`. These two mechanisms complement each other.

---

## Keeping Spec and Code in Sync

When a scenario phase is added or removed, update both:

1. The DEMOMA-16-XXX spec requirement in `specs/multi-actor-demo.yaml`.
2. The corresponding `_XXX_EXPECTED_EVENT_TYPES` constant in
   `test/ci/invariants/test_XXX_invariants.py`.

Both MUST change in the same PR per DEMOMA-16-008. Failure to update the spec
is a latent silent-failure risk; failure to update the test means the new spec
requirement is untested.
