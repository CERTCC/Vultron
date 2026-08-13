---
title: Known Flaky Tests
status: active
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

## CI / Demo Integration Jobs (job name granularity)

| Job name | Issue | Last blocked |
|---|---|---|
| `fvcv-extension` | — | 2026-07-31 |
| `fccv-extension` | — | 2026-07-31 |
| `fcvcv Demo Integration` | #2233 (was #2216, closed) | 2026-08-13 |
| `fvcv-handoff Demo Integration` | #2233 (was #2216, closed) | 2026-08-13 |
| `fvcv-handoff Invariant Harness` | #2233 (was #2216, closed) | 2026-08-13 |
| `fcvcv Invariant Harness` | #2233 | 2026-08-13 |
| `fcv-reject Invariant Harness` | #2233 (was #2121, closed) | 2026-08-13 |
| `fv Invariant Harness` | #2233 | 2026-08-13 |

> Some of these jobs fail intermittently due to inter-container HTTP delivery
> timeouts (async race windows). Root cause documented in
> `plan/incoming/learnings/` entry `20260731-async-race-windows-in-fv-demo.md`.
> When a new occurrence is confirmed, `pr-execute` will open or comment on a
> `flaky-test` + `bug` issue and record it here.
>
> **The six rows pointing at #2233 are not flaky** — they fail on *every* run
> until the engage-case 422 lands, and they are listed here only because
> `pr-execute`'s dedup procedure looks here first. The Demo Integration pair
> fails on `SvcEngageCaseUseCase failed: TransitionParticipantRMtoAccepted`; the
> four Invariant Harness rows fail downstream of it on
> `test_invariant_5_expected_event_types_present[engage_case]`, because the 422
> aborts the trigger before `GuardedCommitCaseLedgerEntryBT` can record the
> entry that #2266 made universally required. Keep them in one row set: routing
> them to separate issues is what left #2216 and #2121 as stale pointers here
> after they were closed.

---

## How pr-execute uses this catalog

See `.claude/skills/pr-execute/REFERENCE.md` § "Flaky Test Dedup" for the
full fractal search procedure. Short version:

1. Check this file first (fast, no API call).
2. If match found: `gh issue view <N> --json state` — open → use it; closed →
   evict entry, fall through.
3. If no match: GitHub search (`--label flaky-test`), then agent judgment.
4. If still no match: create new issue with `bug` + `flaky-test` labels.
