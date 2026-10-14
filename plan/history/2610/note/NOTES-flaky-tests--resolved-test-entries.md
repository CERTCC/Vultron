---
source: NOTES-flaky-tests--resolved-test-entries
timestamp: '2026-10-12T23:53:59.345555+00:00'
title: 'flaky-tests: resolved unit and integration-marker entry notes'
type: note
---

Archived from `notes/flaky-tests.md` by #4497: every entry these notes
describe is resolved and its catalog row removed. The fixes are the closed
issues they cite (#2123, #2126, #3732/#3726, #2270). The lasting triage rules
(no summary line means a killed run; check the ceiling before cataloguing)
stay in `notes/flaky-tests.md` and `notes/testing-pitfalls.md` § "Reading
Test Output".

---

## Unit Tests: resolved-entry notes

> Note: the two `test_datalayer_get_existing_actor*` entries (#3732, #3726)
> were **a wire-format defect, not nondeterminism**, and were removed
> 2026-09-29 with the fix. `as_Actor` derived an actor's `inbox`/`outbox`
> collections stamped with `now_utc()`; the datalayer read path keeps only the
> endpoint URI (ARCH-12-006) and rebuilt the collection — stamped again — on
> read, so the round-trip equality held only when create and read shared a
> wall-clock second. A derived endpoint is an address and now carries no
> stamp. The two tests pin the clock an hour ahead between create and read
> (`test/support/clock.py`), so they now fail deterministically if the
> regression returns. See `notes/datalayer-design.md` § "A Clock-Minted
> Default Cannot Round-Trip Through a Field That Does Not Store It".
>
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
> Note: exit 137 (SIGKILL) with no summary line also occurs from **container
> memory exhaustion** when the full suite is run repeatedly in one session —
> e.g. a third consecutive `uv run pytest` aborting mid-run while the first two
> passed — independent of any per-test timeout. Same triage rule: no summary
> line means the run was killed, not that a test failed (ISSUE-2458).
>
> Note: `test_vultrabot` shows `SUBFAILED` in the full suite due to py_trees
> blackboard global-state ordering, but exit code stays 0 (unittest subtest
> failures don't trigger pytest's failure exit code). Documented in
> `test/AGENTS.md`. No open issue — not a merge blocker.

## Integration-Marker Tests: resolved-entry notes

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
