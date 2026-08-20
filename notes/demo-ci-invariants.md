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

## Artifact Availability on Failure (DEMOCI-10)

**Problem**: The separate-job pattern above only pays off if the artifact
*exists* when the demo fails. It did not. Each `run_<name>_demo()` called
`_phase_dump_case_ledgers()` as its last statement, so an assertion escaping a
`demo_check`/`demo_gate` block skipped the dump; `main()`'s
`finally: assert_demo_success()` still raised, so CI reported the demo failure
but `devlogs/` was empty. The `invariant-harness` job then died on **artifact
download** — the run that most needed forensics produced none, and the harness
reported a plumbing error instead of an invariant result (issue #2239).

**Design**: five pieces in two layers, spec'd as DEMOCI-10-001 through
DEMOCI-10-006.

### Layer 1 — In-harness failures (DEMOCI-10-001 through DEMOCI-10-005)

These cover any failure that happens *inside* `scenario_harness()`.

1. **A shared harness owns the ordering.**
   `vultron/demo/helpers/harness.py` provides `scenario_harness(demo_name)`.
   Every `run_<name>_demo()` body runs inside it: it resets the failure
   accumulator, always dumps the case ledgers on the way out (normal return or
   any `BaseException`), then calls `assert_demo_success()` last. Scenarios
   register their dump with `harness.dump_with(...)` as soon as a case exists,
   so every later phase can fail without costing the ledgers. `main()` no longer
   wraps the run in `try/finally: assert_demo_success()` — a second owner of the
   accumulator would assert before the dump had run. See DEMOMA-23.

2. **The dump always leaves a manifest.**
   `vultron/demo/helpers/ledger_dump.py::dump_case_ledgers()` writes
   `devlogs/<demo>/dump-manifest.json` from a `finally`, recording `demoName`,
   `caseId`, `ledgerFileCount`, `targetCount`, an optional top-level `reason`,
   and a per-actor list naming each missing actor with the reason it was
   missing. So the artifact is non-empty even when there were no ledgers at all
   to capture — including the "died before any case existed" case, where the
   manifest records `ledgerFileCount: 0` and the reason why. The per-actor
   `reason` field also distinguishes a network-timeout dump failure from a
   scenario that never started: a timed-out dump records the actor's exception
   in `reason` alongside `captured: false`, while a pre-run sentinel records no
   actors at all (see Layer 2).

3. **`load_devlogs()` fails instead of skipping when a dump happened.**
   Previously a missing/empty `devlogs/` meant "no test data" → `pytest.skip`,
   which reads green. Now `load_devlogs()` distinguishes the two cases:

   | State of the downloaded artifact | Outcome |
   |---|---|
   | no `devlogs/`, or no `devlogs/<demo>/` | `skip` — the demo genuinely did not run |
   | `devlogs/<demo>/` exists, no ledger files, no manifest | **`fail`** — directory created but dump never ran (ISSUE-2411) |
   | no ledger files **and** no `dump-manifest.json`, no `demo_name` | `skip` — unscoped load with no data |
   | no ledger files **but** a manifest exists | **`fail`** — real invariant failure |
   | manifest present but unparseable | **`fail`** |
   | ledger files present | load and check normally |

   The failure message reproduces the manifest's own account — case ID, captured
   *X* of *Y* targets, and one line per missing actor with its route key and
   reason — so the harness output explains *why* there are no ledgers rather
   than leaving a reviewer to guess.

   A dump failure must not mask the scenario failure. Errors raised inside the
   dump are recorded in the manifest's `reason` field and swallowed; the harness
   re-raises the original exception with the accumulated `demo_check` failures
   attached as exception notes (DEMOCI-10-004).

4. **The harness exits non-zero on an all-skip session.**
   When `devlogs/` is absent or empty, `load_devlogs()` calls `pytest.skip()` at
   fixture level and every test skips. pytest exits 0 by default for skip-only
   sessions, which let CI report green even though no invariant was checked.
   An `_AllSkipGuard` pytest plugin registered in
   `test/ci/invariants/conftest.py` forces `session.exitstatus = 1` whenever at
   least one test was reported and all reported outcomes were `"skipped"`
   (DEMOCI-10-005). This converts a vacuous pass into a visible red.

### Layer 2 — Pre-harness failures (DEMOCI-10-006)

`scenario_harness()` only runs when the demo-runner container starts and the
scenario module imports successfully. Three failure modes exit before that
point — none of which the in-harness pieces above can catch:

- **Health-check gate**: `main()` calls `sys.exit(1)` when a container is
  unreachable.
- **Import error**: the scenario module fails to import before `main()` runs.
- **Docker startup failure**: the demo-runner container never starts at all.

In all three cases `devlogs/<demo>/` is never created. The `upload-artifact`
step publishes nothing, the `download-artifact` step fails with "Artifact not
found", and the invariant-harness job dies on a plumbing error instead of
reporting a protocol result.

1. **A CI sentinel step writes the manifest before the demo-runner starts.**
   The demo job writes `devlogs/<demo>/dump-manifest.json` (conforming to the
   DEMOCI-10-002 schema, `ledgerFileCount: 0`, `targetCount: 0`) immediately
   before `docker compose up`. If the demo-runner then runs normally, the
   harness overwrites the sentinel. If the runner exits early, the sentinel
   survives, the artifact is non-empty, the download succeeds, and
   `load_devlogs()` reports a real failure via the manifest-without-ledgers path
   (DEMOCI-10-003). Implementation: `write_prerun_sentinel(demo_name)` in
   `vultron/demo/helpers/ledger_dump.py` provides a testable Python entry point
   (exercised by `TestWritePrerunSentinel`). The CI step independently writes
   the same JSON inline via `python3 -c` with no vultron import, so no uv setup
   is needed in the demo job.

### Regression coverage

- `test/demo/test_issue_2239_ledger_dump_in_finally.py` (all nine scenarios)
- `test/demo/test_scenario_harness.py`
- `test/ci/invariants/test_common.py::TestLoadDevlogsManifestHandling`
- `test/ci/invariants/test_common.py::TestAllSkipGuard`
- `test/ci/invariants/test_common.py::TestCheckPerActorReplicaDivergence` (ISSUE-2411 Gap 1)
- `test/demo/test_ledger_dump.py::TestWritePrerunSentinel` (AC4 for #2281)

---

## Harness File Conventions

Each scenario gets **one self-contained harness file**,
`test/ci/invariants/test_<scenario>_invariants.py`. There is no shared
per-scenario base class and no registry module. A new harness follows the
existing nine:

1. Declare `_DEMO_NAME = "<scenario>"` at module scope.
2. Load replicas with `load_devlogs(demo_name=_DEMO_NAME)`, imported from
   `test/ci/invariants/common.py`. It skips when the demo did not run and
   **fails** when the demo ran, dumped, and still produced no ledgers — see
   "Artifact Availability on Failure" above.
3. Declare `_CHAIN_ACTORS` (scenario-role names, not docker service names) and
   `_<SCENARIO>_EXPECTED_EVENT_TYPES`.
4. Call the shared check functions from `common.py`; keep scenario-specific
   assertions in the scenario file.
5. Include `test_invariant_per_actor_replica_divergence` calling
   `check_per_actor_replica_divergence(replicas)`.  Pass
   `check_fix_ready=False` for scenarios where no Vendor ever becomes a case
   participant (currently only `fcv-reject`), mirroring the canonical
   `test_invariant_15_cs_state_transitions_observed` rule (ISSUE-2411 Gap 1).

**The scenario→harness registry is the CI matrix**, not a Python module. The
`demo:` / `test_file:` pairs in `.github/demo-scenarios.json` (read by the
workflow via `fromJson`) are the sole mapping from a scenario name to its
harness file; the pairs appear in both the `demo` and `invariant-harness` jobs
and must be kept in step.

> **Do not add a `conftest.py` scenario registry.** DEMOMA-19-008 originally
> required registering the FCVCV harness in `test/ci/invariants/conftest.py`
> "under the `fcvcv` scenario key". No such registry has ever existed, and the
> clause was written spec-first with no implementation to check against
> (CONCERN-2004). It has been amended to describe the pattern above.
>
> A `test/ci/invariants/conftest.py` *does* exist as of issue #1976, but it
> holds synthetic in-memory JSONL fixtures for unit-testing the check functions
> in `common.py` — it carries no scenario mapping. Do not bolt scenario routing
> onto it.

Known duplication: all nine harnesses re-implement the same ~14 universal
invariant tests as near-identical thin wrappers over `common.py`. Extracting
them is tracked separately; the per-file `_DEMO_NAME` + `load_devlogs` idiom is
not the duplication worth fixing.

---

## Per-Scenario Expected Event Types (DEMOMA-16)

**Problem**: All per-scenario `_XXX_EXPECTED_EVENT_TYPES` lists historically
contained only the four types then treated as universal (`validate_report`,
`add_participant_status_to_participant`, `close_case`, `add_note_to_case` —
`engage_case` became the fifth in ISSUE-2266),
regardless of the scenario's actual protocol coverage. This allowed
scenario-specific phases to regress silently (e.g. `invite_actor_to_case`
missing from a scenario that requires it).

**Design**: Each scenario defines its own required event-type list that
extends the universal types (DEMOMA-16-001) with scenario-specific required phases.
The spec requirements in `specs/multi-actor-demo.yaml` DEMOMA-16-001 through
DEMOMA-16-011 are the normative source; the test constants implement them.

### Scenario required event types

This table MUST match the DEMOMA-16 requirements one-for-one — one row per
scenario, no scenario omitted. It drifted from the spec on four counts before
CONCERN-2243 (three rows understated their required types; the FCCV-extension
and FCV-reject rows were absent entirely), which is exactly the drift
DEMOMA-16-008 exists to prevent.

| Scenario | Spec | Universal 5 | Additional required |
|---|---|---|---|
| FV | DEMOMA-16-002 | validate_report, add_participant_status_to_participant, close_case, add_note_to_case, engage_case | (none) |
| FVV | DEMOMA-16-003 | same | invite_actor_to_case, accept_invite_actor_to_case |
| FVCV-extension | DEMOMA-16-004 | same | invite_actor_to_case, offer_case_participant, accept_invite_actor_to_case, accept_actor_recommendation |
| FVCV-handoff | DEMOMA-16-005 | same | invite_actor_to_case, accept_invite_actor_to_case |
| FCCV-handoff | DEMOMA-16-006 | same | invite_actor_to_case, accept_invite_actor_to_case |
| FCV | DEMOMA-16-007 | same | invite_actor_to_case, accept_invite_actor_to_case |
| FCVCV | DEMOMA-16-009 | same | invite_actor_to_case (≥3), offer_case_participant (≥1), accept_invite_actor_to_case (≥3), accept_actor_recommendation (≥1) |
| FCCV-extension | DEMOMA-16-010 | same | invite_actor_to_case, offer_case_participant, accept_invite_actor_to_case, accept_actor_recommendation |
| FCV-reject | DEMOMA-16-011 | same | invite_actor_to_case, reject_invite_actor_to_case |

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

Corollary for planning work: an amendment to a DEMOMA-16 requirement and the
corresponding edits to `_XXX_EXPECTED_EVENT_TYPES` cannot be split across a
docs PR and a later implementation PR. Either both land now, or both are
deferred to the implementation PR together.

---

## Reading a Red Invariant Harness Job (CONCERN-2243)

**A red `<scenario> Invariant Harness` job is not evidence that any invariant
was violated — or even evaluated.** The job has three distinct red modes, and
they are easy to confuse:

| Job outcome | What actually happened | What it tells you about invariants |
|---|---|---|
| Red at `Download case log JSONL files` | The demo job never uploaded an artifact, so `actions/download-artifact` errored (`Artifact not found for name: <scenario>-case-logs`). **pytest never ran.** | Nothing at all |
| Red at `Run case-ledger invariant harness` | pytest ran and an assertion failed | A real invariant result |
| Red at `Run case-ledger invariant harness` with every test skipped | `load_devlogs` called `pytest.skip` because `devlogs/<scenario>/` held no `*-case-ledger.jsonl`; the `_AllSkipGuard` (DEMOCI-10-005) forces `exitstatus=1` | Nothing — vacuous red; no invariant was checked |

CONCERN-2243 was filed because a permanently-red `fvcv-handoff Invariant
Harness` was read as proof that its `engage_case` assertion could never pass.
The job was in fact dying in the first mode: it failed at artifact download on
every run, so the assertion had never once executed. The assertion itself is
correct — `engage_case` is emitted by all nine scenarios (see below) — and the
absence of the entries it looks for was a real protocol defect elsewhere.

Before drawing any conclusion from this job, open the log and confirm which
step failed.

### `engage_case` is universal, not scenario-specific

Every scenario drives an engage-case trigger, so `engage_case` is a universal
required event type on the same footing as `validate_report` — it is the fifth
type in DEMOMA-16-001 and appears in all nine `_XXX_EXPECTED_EVENT_TYPES`
lists (ISSUE-2266). The three emission paths are:

- `run_direct_path_rm_triage()` (`vultron/demo/helpers/workflow.py`) calls
  `receiver_engages_case()` for the report's direct receiver — used by all
  eight multi-actor scenarios.
- `run_invite_path_rm_triage()` calls it again for the invited participant —
  used by seven of them (CM-11-002).
- `fv_demo.py` calls `receiver_engages_case()` directly via
  `vendor_engages_case()`.

Emission is therefore located in the **shared helper layer**, not at scenario
call sites; grepping a single scenario file for `engage` finds nothing and
invites the false conclusion that no code emits it.

Before ISSUE-2266, only `test_fvcv_handoff_invariants.py` listed
`engage_case` — added by PR #2018 as a scenario-specific type without amending
the spec (a DEMOMA-16-008 violation), which left an engage-case regression
silent in the other eight scenarios. The `fvcv-handoff`
`check_event_type_count(..., "engage_case", min_count=2)` assertion remains
scenario-specific: it asserts the *count* Vendor2's post-join triage cycle
implies (CM-11-002), which is a stronger claim than the universal presence
check.

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

### Cache configuration (DEMOCI-02-007)

`demo-image-cache-warm.yml` was removed when `demo-integration.yml` gained an
on-main trigger (DEMOCI-05-001): a single build could then both validate the
demo and export the GHA cache, making a separate cache-warming run redundant.

Subsequently, the GHA cache export was found to be completely inoperable: the
required tokens (`ACTIONS_RUNTIME_TOKEN`, `ACTIONS_CACHE_URL`) are only
injected into `uses:` action steps, not into `run:` shell steps — so the
`docker buildx bake --set "*.cache-to=type=gha"` args in the composite
action's `run:` step could never reach the cache backend (#2248). The cache
configuration has been removed; every job builds from scratch.
DEMOCI-02-007 is retained as a SHOULD, documenting the intent when a
working caching mechanism becomes available.

### Out of scope: merge queue

The concurrent-merge *interaction* gap (two green PRs that break `main` when
combined) is only fully closed by a GitHub **merge queue**, which re-runs
required checks against the actual merged result before landing. That is a
larger branch-protection / required-checks decision tracked separately as a
follow-up Idea; DEMOCI-05 only adds the post-merge baseline signal.

---

## CI Failure Notification — `notify-failure` Composite Action (CISEC-05)

Design decisions and implementation guidance for `.github/actions/notify-failure`,
the shared composite action wired into every qualifying workflow (push to `main`
or `schedule` trigger). See ADR-0055 and `specs/ci-security.yaml` CISEC-05.

### Composite Action Interface

The action accepts three inputs:

- `mode`: `notify` (file/update issue on failure) or `close` (close open issue on
  recovery).
- `workflow-label`: the workflow-specific label, e.g. `ci:workflow-demo-integration`.
  Combined with the shared `ci:main-failure` label, the pair uniquely identifies the
  open failure issue for this workflow — enabling update-not-duplicate semantics.
- `run-url`: `${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}`.
  Included in the issue body so the failing run is one click away.

Each qualifying workflow wires **two** steps using `if:` conditions so no
workflow-status-detection logic lives inside the action:

```yaml
- name: Notify CI failure
  if: failure()
  uses: ./.github/actions/notify-failure
  with:
    mode: notify
    workflow-label: ci:workflow-<name>
    run-url: ${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}

- name: Close CI failure issue
  if: success()
  uses: ./.github/actions/notify-failure
  with:
    mode: close
    workflow-label: ci:workflow-<name>
    run-url: ${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}
```

Every qualifying workflow MUST declare `issues: write` permission (CISEC-05-001,
CISEC-05-002). Workflows with a root-level `permissions: contents: read` block MUST
expand it to a map that explicitly includes `issues: write`.

### Qualifying Workflows and Their Labels

| Workflow file                 | Trigger            | Workflow-specific label              |
|-------------------------------|--------------------|-----------------------------------------|
| `demo-integration.yml`        | push to main       | `ci:workflow-demo-integration`          |
| `python-app.yml`              | push to main       | `ci:workflow-python-app`                |
| `lint_md_all.yml`             | push to main       | `ci:workflow-lint-markdown`             |
| `spec-check.yml`              | push to main       | `ci:workflow-spec-check`                |
| `actions-lint.yml`            | push to main       | `ci:workflow-actions-lint`              |
| `quarterly_tag.yml`           | schedule           | `ci:workflow-quarterly-tag`             |
| `stale_claim_sweeper.yml`     | schedule           | `ci:workflow-stale-claim-sweeper`       |

### Deduplication Model

The composite action searches for any open issue with **both** `ci:main-failure`
and the workflow-specific label using `gh issue list --label`. If one exists,
`notify` appends a comment (avoids alert flooding across repeated failures without
a fix). If none exists, `notify` creates a new issue. `close` searches the same
label combination and closes any open match.

The `ci:main-failure` label is bot-managed; CISEC-05-005 enforces this via a
separate `issues: labeled` workflow that strips the label if `github.actor !=
github-actions[bot]`. This prevents label spoofing that could suppress a
legitimate failure notification.

---

## Invariant Scoping: Per-Scenario Participant Set Audit

Invariants in the harness are only invariant *within their scenario's protocol
path*. Before copying an invariant check to a new scenario, audit it against
that scenario's participant set and phase list.

**Example**: `check_cs_state_transitions_observed()` with `check_fix_ready=True`
(the default) requires a VFD `VFd` (fix ready) transition. This invariant holds
for all vendor-inclusive scenarios where VFD advances, but is inapplicable for
rejection flows where the Vendor rejects the invitation and VFd is structurally
unreachable. Pass `check_fix_ready=False` for those scenarios (DEMOCI-06-001
documents this class of copy-paste defect). *Source: ISSUE-2121*

**Related**: DEMOCI-06-001 already tracks this class of error. The general
pattern: any harness check that asserts "event X was observed" can become a
false failure if scenario Y never produces event X by design. The harness parameter
that enables/disables the check is the correct mechanism, not skipping the
invariant entirely.
