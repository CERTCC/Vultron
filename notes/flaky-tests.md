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
| `fcvcv Demo Integration` | #2233 | 2026-08-13 |
| `fvcv-handoff Demo Integration` | #2233 | 2026-08-13 |
| `fvcv-handoff Invariant Harness` | #2266 | 2026-08-13 |
| `fcvcv Invariant Harness` | — | 2026-08-10 |
| `fcv-reject Invariant Harness` | #2121 (closed) | 2026-08-10 |

> The rows with no issue number fail intermittently due to inter-container HTTP
> delivery timeouts (async race windows). Root cause documented in
> `plan/incoming/learnings/` entry `20260731-async-race-windows-in-fv-demo.md`.
> When a new occurrence is confirmed, `pr-execute` will open or comment on a
> `flaky-test` + `bug` issue and record it here.
>
> The three rows citing #2233 / #2266 are **not** flaky — they are deterministic
> and branch-independent. `engage-case` returns HTTP 422 on the invite path
> (`SvcEngageCaseUseCase failed: TransitionParticipantRMtoAccepted`), tracked as
> #2233; the harness row is the assertion-scope gap tracked as #2266. They are
> listed here because `pr-execute` records blocked jobs here regardless of
> cause, and because #2216 — the issue they used to cite — is closed and no
> longer the right pointer. Do not re-diagnose them as nondeterminism.

---

## How pr-execute uses this catalog

See `.claude/skills/pr-execute/REFERENCE.md` § "Flaky Test Dedup" for the
full fractal search procedure. Short version:

1. Check this file first (fast, no API call).
2. If match found: `gh issue view <N> --json state` — open → use it; closed →
   evict entry, fall through.
3. If no match: GitHub search (`--label flaky-test`), then agent judgment.
4. If still no match: create new issue with `bug` + `flaky-test` labels.
