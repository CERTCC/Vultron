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

---

## Post-Merge Validation on `main` (DEMOCI-05)

**Problem**: `demo-integration.yml` originally triggered only on
`pull_request`, so the demo + invariant harness validated only the *ephemeral
merge commit* (PR head merged onto `main` at test time) — never the actual
merged `main` HEAD. Two PRs each green in isolation can interact to break
`main`, and nothing re-ran the demos/invariants against the real merged result.
Because the trigger is path-filtered, a broken `main` could persist untested
until a *later* PR happened to touch a filtered path. The default branch had no
demo/invariant baseline at all — the classic "green PRs, red main" failure mode
(CONCERN-1859).

**Design**: `demo-integration.yml` also triggers on `push` to `main` with the
**same path filter** as the `pull_request` trigger (DEMOCI-02-003,
DEMOCI-05-001). The on-main run executes the full demo + invariant-harness
matrix against the merged `main` HEAD, producing a per-commit pass/fail signal.

### Why `push` (with concurrency) rather than a cron schedule

`push` gives an immediate per-commit signal with no blind window and preserves
single-commit failure attribution for bisection. A `schedule:` cron was
considered but rejected for this concern: it introduces up to a multi-hour
blind window, runs even when nothing merged, and attributes failures to a
commit *range* rather than a single commit. GitHub Actions has no native
"run at most once every N hours" throttle for `push`; the cost is bounded
instead by (a) the path filter — docs/spec-only merges cost nothing — and
(b) the concurrency group.

### Concurrency (DEMOCI-02-011, DEMOCI-05-002)

A single workflow file serves both triggers, so `cancel-in-progress` is an
expression: `true` off the default branch (PR bursts collapse to the newest
commit), `false` on `main` (every qualifying merge runs to completion and keeps
its own signal). Keyed on `${{ github.workflow }}-${{ github.ref }}`:

```yaml
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: ${{ github.ref != 'refs/heads/main' }}
```

Note: DEMOCI-02-011 was authored as a SHOULD but never implemented — neither
workflow carried a `concurrency` block before CONCERN-1859. It is now a MUST
and is wired on both triggers.

### Cache-warm workflow removal (DEMOCI-05-003)

`demo-image-cache-warm.yml` existed *only* because `demo-integration.yml` did
not run on `main`: it built the demo images on push-to-main and exported them
to the `demo-integration-main` GHA cache scope so new PR branches got a warm
fallback cache (PR-branch caches are not visible across branches). Once the
on-main run of `demo-integration.yml` exports that same scope, the dedicated
cache-warm workflow is a redundant second image build and is **removed**. One
on-main build now both validates the demo and warms the cache.

### Out of scope: merge queue

The concurrent-merge *interaction* gap (two green PRs that break `main` when
combined) is only fully closed by a GitHub **merge queue**, which re-runs
required checks against the actual merged result before landing. That is a
larger branch-protection / required-checks decision tracked separately as a
follow-up Idea; DEMOCI-05 only adds the post-merge baseline signal.
