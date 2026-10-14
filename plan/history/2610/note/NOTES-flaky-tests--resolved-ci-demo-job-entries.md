---
source: NOTES-flaky-tests--resolved-ci-demo-job-entries
timestamp: '2026-10-12T23:54:12.646078+00:00'
title: 'flaky-tests: resolved CI demo job rows and their notes'
type: note
---

Archived from `notes/flaky-tests.md` by #4497: every tracker these notes
explain is closed (#2898, #3033, #3602, #3903, #4113, #2257, #2768,
issues #2233, #2733, #2376 and #2221), and the post-merge `demo-integration.yml` runs on
`main` since 2026-10-07 fail only on the `rcvv-embargo` jobs (#4424, still
catalogued). The rows are evicted per the `pr-execute` catalog rule (a closed
issue evicts its entry).

---

## CI / Demo Integration Jobs (as archived)

| Job name | Issue | Last blocked |
|---|---|---|
| `rcvv-embargo Demo Integration` — `Vendor2 received the full-case Invite` gate times out while Vendor2's replica replays the backfill | #4424 | 2026-10-09 |
| `rcvv-embargo Invariant Harness` | #4424 | 2026-10-09 |
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
