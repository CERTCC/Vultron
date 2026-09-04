---
title: Known Flaky Tests
status: active
related_notes:
  - notes/testing-pitfalls.md
---

# Known Flaky Tests

Fast-lookup catalog of known flaky tests and CI jobs mapped to their tracking
issues. Used by `pr-execute` as a cache before querying GitHub.

**GitHub is always ground truth.** Before trusting an entry here, verify the
issue is still open: `gh issue view <N> --json state`. A closed issue means the
flaw was resolved — evict the stale entry and fall through to create a new one.

Entries are added by `pr-execute` when a pre-existing failure is confirmed.
Entries are removed by `bugfix` or `build` when the tracking issue is closed.

---

## Unit Tests (pytest node IDs)

A `—` in the Issue column means no tracking issue has been filed yet.
When `pr-execute` encounters a match with `—`, skip the `gh issue view` step
and fall through to Level 2 (GitHub label search).

| Test node ID | Issue | Last blocked |
|---|---|---|
| `test/bt/test_vultrabot.py::MyTestCase::test_main` | — | 2026-05-05 |
| `test/demo/test_delivery_fallback_speed.py::test_demo_completes_under_5_seconds` | #2738 | 2026-08-26 |

> Note: the two `test_integration_script_scenarios` entries were **hard-broken
> on `main`, not flaky** — they failed deterministically. #2114 added a test that
> scrapes `DEMO=` from `demo-integration.yml` while #2118/#2119 moved the
> scenario matrix to `.github/demo-scenarios.json`, leaving nothing to scrape.
> A semantic merge collision between two individually-correct PRs. **Fixed by
> #2123**; rows removed 2026-08-08.
>
> Note: the two `TestBootstrapSequence` entries were **deterministic
> cross-module config leakage, not nondeterminism** — root-caused and **fixed by
> #2126**; rows removed 2026-08-08.
>
> An earlier revision of this note claimed they were "genuinely
> nondeterministic" because `pytest -m "" test/demo/` gave `[2,0,2]` bootstrap
> failures over three identical runs. That reading was an artifact of the
> measurement. `timeout = 5` with `timeout_method = "thread"`
> (`pyproject.toml:123`) kills the **whole pytest process**, not just the slow
> test, so a run that trips it emits no summary line and never reaches
> `test_pcr_bootstrap.py` at all — scoring a phantom `0`. Re-running the same
> command with a driver that records the `+++ Timeout +++` marker reproduces
> `[2,0,2]` and shows the `0` run aborted mid-session.
>
> At any granularity that actually runs both modules to completion, the failure
> is deterministic on clean `origin/main`:
>
> | Invocation (`-p no:randomly`, 3× each) | Bootstrap failures |
> |---|---|
> | `test_fvcv_handoff_demo.py` + `test_pcr_bootstrap.py` | `[2, 2, 2]` |
> | `...::TestOwnershipTransferAnnounceReachesFinderAC5c` + bootstrap | `[2, 2, 2]` |
> | `test_pcr_bootstrap.py` alone | `[0, 0, 0]` |
>
> The earlier pairwise bisect that found "no single polluting file (all 27
> checked)" disagrees with the first row above; treat that sweep as unreliable.
> The cause was `reload_config()` running before `monkeypatch.undo()` in four
> demo fixture teardowns, pinning a fake CaseActor host into the module-level
> config cache for the rest of the session. See #2086 and PR #2126.
>
> **Lesson for future triage here**: a pytest run that aborts on the global
> thread-method timeout looks identical to a clean pass if you only count
> `FAILED` lines. Always check for a summary line and the `+++ Timeout +++`
> marker before concluding a test is nondeterministic.
>
> Note: `test_vultrabot` shows `SUBFAILED` in the full suite due to py_trees
> blackboard global-state ordering, but exit code stays 0 (unittest subtest
> failures don't trigger pytest's failure exit code). Documented in
> `test/AGENTS.md`. No open issue — not a merge blocker.

---

## Integration-Marker Tests (pytest node IDs)

No open entries.

> Note: `test/demo/test_pcr_late_joiner.py::test_late_joiner_receives_case_replica`
> and `test/metadata/test_decision_audit_inventory.py` were **not flaky tests** —
> they were honest 3.5-4.3s tests colliding with a 5s ceiling sized for the unit
> suite. Because `timeout_method = "thread"` kills the whole pytest process,
> `uv run pytest -m integration` aborted with **no summary line**, so a red
> integration run carried no information about the branch. Reliably red in random
> order (2/2 on clean `origin/main` 65fe33f1b); passed under `-p no:randomly`,
> which is what made it look like nondeterminism. Only *which* test tripped
> followed the `pytest-randomly` seed.
>
> **Fixed by #2270** — `test/conftest.py` now gives `integration`-marked tests a
> 60s tier while the unit suite runs at 30s (raised from 5s in the same issue,
> because AST-walking ratchets at ~3.4s were tripping the old ceiling under
> full-suite load). Verified 2/2 random-order runs at
> exit 0, 0 timeout aborts, 1101 passed. Never catalogued as flaky; rows added
> and removed in the same change (2026-08-12).
>
> **Lesson**: before adding a row here, ask whether the test is nondeterministic
> or whether the *ceiling* is wrong. A timeout tuned for one tier of tests will
> masquerade as flakiness in another. See also #2249 for the opposite error —
> cataloguing a deterministic protocol bug as noise.

---

## CI / Demo Integration Jobs (job name granularity)

| Job name | Issue | Last blocked |
|---|---|---|
| `fcvcv Demo Integration` | #2819 | 2026-08-28 |
| `fcvcv Invariant Harness` | #2819 | 2026-08-28 |
| `fvcv-extension` | #2422 | 2026-08-26 |
| `fccv-extension` | #2422 | 2026-08-26 |
| `fv Demo Integration` | #3033 | 2026-09-02 |
| `fv Invariant Harness` | #3033 | 2026-09-02 |
| `fvcv-handoff Demo Integration` | #2257 | 2026-08-18 |
| `fvcv-handoff Invariant Harness` | #2257 | 2026-08-18 |
| `fcv-reject Demo Integration` | #2390 | 2026-08-19 |
| `fcv-reject Invariant Harness` | #2390 | 2026-08-19 |

> `fv Demo Integration` / `fv Invariant Harness` were **repointed to #3033 on
> 2026-09-02**.  #2422 (vendor RM.RECEIVED timeout at M3, cascading
> `notify-fix-ready` 422 from the cross-machine entailment guard, then vfd_state
> timeouts at M4/M5/M6) was fixed 2026-08-26 and is closed — but the jobs still
> flake at an *earlier* gate: the vendor's `VulnerabilityCase` replica never
> arrives from the CaseActor before validate-report, raised at
> `vultron/demo/helpers/workflow.py` in `run_direct_path_rm_triage()`
> (ADR-0041, PCR-01-003).  Same async race-window class as #2376 (fcvcv,
> coordinator/engage-case), distinct window.  Confirmed 2026-09-02 on PR #3029:
> failed once, passed on re-run with all 25 checks green, `main` green throughout.
> Invariant Harness fails as a downstream consequence of incomplete devlogs.
>
> `fvcv-extension` / `fccv-extension` still cite #2422 and so are also pointing
> at a closed issue; no fresh evidence was gathered for those two jobs.  Verify
> before deleting or repointing them.
>
> **Do not delete a row merely because its issue closed.**  Check whether the
> flake still reproduces first — a closed tracker plus an observed failure means
> the tracker was closed prematurely, or fixed only one of several races sharing
> a job name.  Repoint in that case; delete only when the flake is gone.
>
> **`fvcv-handoff` has two distinct signatures — match on the message, not the
> job name.** The row above points at #2257, but a second, unrelated failure
> shape is live as of 2026-09-03 and is tracked by **#2768**:
>
> ```text
> CHECK FAILED: Vendor2 replica matches authoritative Vendor1 state —
> Auth has no entry at index 19 — replica is ahead of auth or coverage check is stale
> ```
>
> Confirmed on `main` @ `dd93fecbd` as well as twice on PR #3110, always at index
> 19 — the scenario is deterministic in shape so the race window sits at the same
> entry, which makes a single log look deterministic. `main` passed the run
> before, so it is intermittent. Note that `auth` here is Vendor1, itself a
> fanout recipient rather than the CaseActor, so this is two replicas racing and
> `sync.py` tolerates auth ahead but not auth behind.
>
> `fvcv-handoff Demo Integration` / `fvcv-handoff Invariant Harness` also point to
> #2257 (`AddCaseParticipantReceivedBT` failure).  Root error:
> `VultronValidationError: AddCaseParticipantReceivedBT did not succeed ... case '...' not found`
> — finder receives `add_case_participant_to_case` before the case exists in its
> DataLayer, so the participant is silently dropped, `actor_participant_index` never
> reaches 5, and `wait_for_case_participants` times out.  Previously pointed at #2221
> (causal gating epic); updated 2026-08-18 to the specific bug.
>
> The rows with no issue number fail intermittently due to inter-container HTTP
> delivery timeouts (async race windows). Root cause documented in
> `plan/incoming/learnings/` entry `20260731-async-race-windows-in-fv-demo.md`.
> When a new occurrence is confirmed, `pr-execute` will open or comment on a
> `flaky-test` + `bug` issue and record it here.
>
> **Removed 2026-08-13:** `fcvcv Demo Integration`, `fvcv-handoff Demo
> Integration`, `fvcv-handoff Invariant Harness`, `fcvcv Invariant Harness`,
> `fcv-reject Invariant Harness`, `fv Invariant Harness` — these were
> **deterministic** failures caused by the engage-case 422 (#2233, now fixed).
> They are gone from this catalog because the fix lands with the PR for #2233.
>
> **Removed 2026-08-27:** `fcvcv Demo Integration`, `fcvcv Invariant Harness` — fixed by PR #2756
> (`Closes #2733`). Root: `_phase_sync_verification` used `demo_check` for ledger coverage
> waits; outer `wait_for_case_on_container` precondition was missing (SYNC-15-001, ADR-0058).
>
> **Removed 2026-08-24:** `fcvcv Demo Integration` — fixed by PR #2508 (`Closes #2376`).
> Both race windows resolved: invite-path `engage-case` now gated on own RM.VALID
> (`demo_gate`), and `verify_publicly_disclosed` now polls reporter pxa_state
> before asserting (ADR-0058).
>
> **Re-added 2026-08-13 (`fvcv-handoff` only):** a new intermittent occurrence
> of `fvcv-handoff Demo Integration` and `fvcv-handoff Invariant Harness` was
> confirmed during PR #2303 with the temporal-poll-timeout shape ("Timed out
> waiting for participant count 5"). This is a different failure mode from the
> #2233 deterministic failure — it is an async race window of the class tracked
> by #2221 (causal gating epic) and #2203 (migration task). Rows re-added
> pointing to #2221; see also breadcrumbs on those issues.

---

## How pr-execute uses this catalog

See `.claude/skills/pr-execute/REFERENCE.md` § "Flaky Test Dedup" for the
full fractal search procedure. Short version:

1. Check this file first (fast, no API call).
2. If match found: `gh issue view <N> --json state` — open → use it; closed →
   evict entry, fall through.
3. If no match: GitHub search (`--label flaky-test`), then agent judgment.
4. If still no match: create new issue with `bug` + `flaky-test` labels.
