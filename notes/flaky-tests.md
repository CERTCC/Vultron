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
| `test/ci/invariants/test_fv_invariants.py::test_invariant_5_expected_event_types_present[validate_report]` | #2274 | 2026-08-13 |
| `test/ci/invariants/test_fv_invariants.py::test_invariant_5_expected_event_types_present[engage_case]` | #2274 | 2026-08-13 |

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
| `fvcv-extension` | — | 2026-07-31 |
| `fccv-extension` | — | 2026-07-31 |
| `fcvcv Demo Integration` | #2233 (was #2216, closed) | 2026-08-13 |
| `fvcv-handoff Demo Integration` | #2233 (was #2216, closed) | 2026-08-13 |
| `fvcv-handoff Invariant Harness` | #2233 (was #2216, closed) | 2026-08-13 |
| `fcvcv Invariant Harness` | #2233 | 2026-08-13 |
| `fcv-reject Invariant Harness` | #2233 (was #2121, closed) | 2026-08-13 |
| `fv Invariant Harness` | #2233 | 2026-08-13 |
| `fv Demo Integration` | #2241 | 2026-08-13 |

> `fv Demo Integration` is a different animal from both the #2233 rows and the
> async-race rows above it. It passed at `dc31b6c6` and failed at
> `0b607c11` — a docs-only diff — while base `fe951d00` does not fail it at all,
> so the trigger is genuinely intermittent. But the *failure* is deterministic
> once triggered: `add-note-to-case` returns an intermittent 422, and
> `vultron/demo/helpers/notes.py:92` then reads `result` outside the
> `with demo_step(...)` block that assigned it. `demo_step` suppresses the
> exception, so control falls through and raises
> `UnboundLocalError: cannot access local variable 'result'`, which buries the
> real 422 under a traceback pointing at the wrong line. Pre-existing base code
> (last touched by #1387, #543).
>
> **#2241 already owns this pattern** — "assignment inside a swallowing
> `demo_check` block then used after it" — so this row cites it rather than a new
> issue. The concrete callsite and run evidence are recorded there; note the
> pattern reaches `demo_step` too, not just `demo_check`. The related reporting
> failure is #2240. The `ValueError: No case ledger entries` later in the same run
> is *not* a second bug: `ledger_dump.py:434` raises it deliberately because the
> run died before any ledger was written. See also #2281.
>
> The rows with no issue number fail intermittently due to inter-container HTTP
> delivery timeouts (async race windows). Root cause documented in
> `plan/incoming/learnings/` entry `20260731-async-race-windows-in-fv-demo.md`.
> When a new occurrence is confirmed, `pr-execute` will open or comment on a
> `flaky-test` + `bug` issue and record it here.
>
> **The six rows pointing at #2233 are not flaky** — they are deterministic and
> branch-independent, failing on *every* run until the engage-case 422 lands. The
> Demo Integration pair fails on
> `SvcEngageCaseUseCase failed: TransitionParticipantRMtoAccepted`; the four
> Invariant Harness rows fail downstream of it on
> `test_invariant_5_expected_event_types_present[engage_case]`, because the 422
> aborts the trigger before `GuardedCommitCaseLedgerEntryBT` can record the entry
> that #2266 made universally required across all nine scenarios — turning one
> silent gap into a red `Invariant Harness` job per scenario. `origin/main`
> `06bf60c2` fails **15** of these jobs on its own, so a PR that fails a subset
> of them has not caused them.
>
> Keep them in one row set: routing them to separate issues is what left #2216
> and #2121 as stale pointers here after they were closed. They are listed here
> at all because `pr-execute`'s dedup procedure looks here first and records
> blocked jobs regardless of cause. Do not re-diagnose them as nondeterminism,
> and do not "fix" them on a feature branch.

---

## How pr-execute uses this catalog

See `.claude/skills/pr-execute/REFERENCE.md` § "Flaky Test Dedup" for the
full fractal search procedure. Short version:

1. Check this file first (fast, no API call).
2. If match found: `gh issue view <N> --json state` — open → use it; closed →
   evict entry, fall through.
3. If no match: GitHub search (`--label flaky-test`), then agent judgment.
4. If still no match: create new issue with `bug` + `flaky-test` labels.
