---
title: Known Flaky Tests
status: active
related_notes:
  - notes/testing-pitfalls.md
  - notes/sync-ledger-replication.md
  - notes/bt-integration.md
  - notes/outbox-delivery-reliability.md
  - notes/datalayer-design.md
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

> Note: the two `test_datalayer_get_existing_actor*` entries (#3732, #3726)
> were **a wire-format defect, not nondeterminism**, and were removed
> 2026-09-29 with the fix. `as_Actor` derived an actor's `inbox`/`outbox`
> collections stamped with `now_utc()`; the datalayer read path keeps only the
> endpoint URI (ARCH-12-006) and rebuilt the collection — stamped again — on
> read, so the round-trip equality held only when create and read shared a
> wall-clock second. A derived endpoint is an address and now carries no
> stamp. The two tests pin the clock an hour ahead between create and read
> (`test/support/clock.py`), so they now fail deterministically if the
> regression returns. See `notes/datalayer-design.md` § "A Default Minted
> From the Clock Cannot Round-Trip Through a Field That Does Not Store It".
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
| `fcvcv Demo Integration` | #2898 | 2026-09-28 |
| `fcvcv Invariant Harness` | #2898 | 2026-09-28 |
| `fvcv-extension` | #2898 | 2026-08-26 |
| `fccv-extension` | #2898 | 2026-08-26 |
| `fv Demo Integration` | #3033 | 2026-09-02 |
| `fv Invariant Harness` | #3033 | 2026-09-02 |
| `fvcv-handoff Demo Integration` — `AddCaseParticipantReceivedBT did not succeed … case not found` / `wait_for_case_participants` timeout | #2257 | 2026-08-18 |
| `fvcv-handoff Invariant Harness` (downstream of the row above) | #2257 | 2026-08-18 |
| `fvcv-handoff Demo Integration` — `Case attributed_to updated to Coordinator on Vendor1's DataLayer (AC-1)` timeout | #3602 | 2026-09-23 |
| `fcv-reject Demo Integration` | #3033 | 2026-09-02 |
| `fcv-reject Demo Integration` — `Finder ledger coverage (sync-verification phase)` timeout on `0…11` | #4113 | 2026-10-01 |
| `fcv-reject Invariant Harness` | #3033 | 2026-09-02 |
| `fccv-handoff Demo Integration` — `M6 receiver: pxa_state is not public-aware, found None` | #3903 | 2026-09-30 |
| `fcv Demo Integration` — `M6 receiver: pxa_state is not public-aware, found None` | #3903 | 2026-09-30 |

> **Root fix landed 2026-09-29 for the #2898 / #3033 rows** (one PR closing
> both). Two faults compounded: the CaseActor queued its initialization ledger
> fan-out ahead of `Create(VulnerabilityCase)` (and the add-participant entry
> ahead of a late joiner's `Announce(VulnerabilityCase)`), so every replica took
> the SYNC-15 pre-genesis reject/replay path on the normal route; and the inbox
> background task ran the synchronous BT pipeline on the event loop, so each
> delivery to a busy container cost a full BT tick (CP-09-009, CM-17-009,
> IE-06-003). **Do not delete these rows on issue closure** (#3033 AC-4):
> delete them only after the post-merge `demo-integration.yml` runs on `main`
> have stayed green for these jobs — the closed issue is the fix record, the
> green runs are the evidence the flake is gone.
>
> **Root fix landed for the #3602 row (ADR-0112, one PR closing #3602 and
> #3878).** The CaseActor's outbox was drained concurrently by every inbound
> activity's background task and the `OutboxMonitor`, so a ledger fan-out
> reached a replica scrambled; each forward gap drew a `Reject`, each `Reject`
> a full-suffix replay, and the replays queued ahead of the next entry's
> fan-out to every other peer — the `log/15` Announce to Vendor1 waited 14.4 s
> *in the queue* behind 77 replay rows for the Coordinator (run 35917721682).
> Fixed by one drain per actor with per-recipient lanes (OX-01-004/005/006),
> lane-ordered re-queue (OX-13-012) and replay dedup (SYNC-15-012); the phase
> now gates on the CaseActor's own commit before reading any replica. Same
> deletion rule as the #2898 / #3033 rows: **keep until post-merge `main` runs
> stay green for this signature.**
>
> `fccv-handoff Demo Integration` / `fcv Demo Integration` **M6 `pxa_state`
> rows added 2026-09-29 → #3903**: the first `main` run after #3883
> (36623680376) failed both at the publication milestone with a signature
> closed #1839 once carried; distinct from every ownership/fan-out gate above.
> **Root fix landed 2026-09-30 (PR closing #3903; #3981 was the auto-filed
> tracker):** `verify_publicly_disclosed` polled `pxa_state` on the reporter
> replica only (the #2376 fix) and then read the receiver replica once. The
> CaseActor's ledger fan-out reaches each replica independently, and in run
> 36770113456 the receiver applied the entry 66 ms after that read. The helper
> now polls every replica it asserts, for `EM.EXITED` as well as `pxa_state`.
> Same deletion rule as above: **keep until post-merge `main` runs stay green
> for this signature.**
>
> `fcv-reject Demo Integration` / `fcv-reject Invariant Harness` were
> **repointed from closed #2390 to #3033 on 2026-09-29**: the 2026-09-02
> occurrences on `main` (`7dd4c49b`) and PR #3018 failed on the same
> `run_direct_path_rm_triage()` replica gate as `fv`, with the coordinator as
> the waiting actor. `fvcv-extension` / `fccv-extension` were **repointed from
> closed #2422 to #2898 on 2026-09-29**: both scenarios carry the #2819 drain
> workaround and share the late-joiner path #2898 fixes; no fresh failure was
> gathered for them, so treat the rows as provisional and delete them with the
> others.
>
> `fcvcv Demo Integration` / `fcvcv Invariant Harness` were **repointed to
> #2898 on 2026-09-28**. #2819 (CaseActor invite race, vendor v2) is closed; its
> fix was a per-scenario ledger drain, and #2898 tracks the delivery-ordering
> race underneath it. Fresh occurrence on PR #3819: the third `validate-report`
> trigger POST (to `vendor-deployer`) hit the 30s client timeout while the vendor
> replayed the ledger from genesis (`ReconstructChainTail` pre-genesis window,
> then `SendRejectLogEntry` hash mismatches). `main` at the merge base passed;
> the PR's diff never runs on that path.
>
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
> **Do not delete a row merely because its issue closed.**  Check whether the
> flake still reproduces first — a closed tracker plus an observed failure means
> the tracker was closed prematurely, or fixed only one of several races sharing
> a job name.  Repoint in that case; delete only when the flake is gone.
>
> **`fvcv-handoff` has three distinct signatures — match on the message, not the
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
> A **third** shape is live as of 2026-09-23 and is tracked by **#3602**:
>
> ```text
> CHECK FAILED: Case attributed_to updated to Coordinator on Vendor1's DataLayer (AC-1)
>   — Timed out waiting for case 'urn:uuid:…' attributed_to='http://coordinator:…'
>     on container http://vendor:7999/api/v2
> ```
>
> Raised from `wait_for_case_attributed_to` at
> `vultron/demo/scenario/fvcv_handoff_demo.py:458`, the first check after
> `Coordinator accepts case ownership transfer (TRIG-11-002)`. The two shapes
> above bracket it in scenario order — #2257's gate is the participant fan-out
> *before* the transfer, #2768's is ledger coverage *after* it — so neither
> covers the transfer's own state mutation. Note which side fails: Vendor1 is the
> *transferor*, waiting to observe a mutation to a case it no longer owns, which
> it can only learn from the CaseActor's fan-out. Confirmed 2026-09-23 on PR
> #3585 (metadata/specs/docs diff only): failed once, green on re-run of the same
> commit with all 27 checks passing, `main` green throughout.
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
