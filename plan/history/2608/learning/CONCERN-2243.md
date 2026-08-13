---
source: CONCERN-2243
timestamp: '2026-08-12T20:01:39.448481+00:00'
title: A red CI job is not evidence its assertions ran
type: learning
---

CONCERN-2243 reported that the `fvcv-handoff` invariant harness asserts an
`engage_case` ledger event that no code emits, and asked whether to implement
the emission or correct the assertion. Both halves of the premise were wrong,
and the way they were wrong is the reusable lesson.

## What was actually true

`engage_case` is emitted by **all nine** demo scenarios. Emission lives in the
shared helper layer, not in scenario files: `run_direct_path_rm_triage()` in
`vultron/demo/helpers/workflow.py` calls `receiver_engages_case()` for the
report's direct receiver (all eight multi-actor scenarios), and
`run_invite_path_rm_triage()` calls it again for the invited participant (seven
of them, per CM-11-002); `fv_demo.py:483` calls it directly. The commit chain is
complete end to end — `create_engage_case_tree` contains
`GuardedCommitCaseLedgerEntryBT`, and `("Join", "VulnerabilityCase")` is an
allowed canonical payload signature, correctly excluded from
`_CASE_AUTHORED_SIGNATURES` as a participant assertion.

The assertion was never unsatisfiable. `min_count=2` is arithmetically right:
Vendor1 engages via the direct path, Vendor2 via the invite path.

## The two misreadings

**1. A red CI job was read as evidence about the assertion.** The
`fvcv-handoff Invariant Harness` job had been permanently red, which was taken
as proof the assertion could never pass. The job was in fact dying at
`actions/download-artifact` — `Artifact not found for name:
fvcv-handoff-case-logs` — because the demo job failed before uploading devlogs.
**pytest never ran.** There were 0 successful demo-integration runs in the last
100, including all four on the branch of `915908c2` (PR #2018), the commit that
added the assertion. It merged never having executed once.

The inverse trap sits right next to it: `load_devlogs` calls `pytest.skip` when
`devlogs/<scenario>/` holds no ledger files, and the harness step is a bare
`uv run pytest`, so an all-skipped run exits 0 and reports **green** while
checking nothing.

**2. Absence was inferred from grepping the wrong layer.** Searching scenario
files — or even all of `vultron/demo/scenario/` — for `engage` finds nothing,
because every scenario reaches emission through a shared helper. Absence of a
call site is not absence of emission when a helper layer sits in between.

## Real defect found underneath

Every harness matches its DEMOMA-16 requirement exactly **except**
`fvcv-handoff`, which carries one extra entry — `engage_case` — that
`915908c2` added to the test without amending the spec. That is a
DEMOMA-16-008 violation, and its cost is that an engage-case regression is
silent in eight of nine scenarios. Since all nine scenarios drive engage-case,
the fix is to promote `engage_case` to the universal set in DEMOMA-16-001
alongside `validate_report` — the same instinct PR #2018 had, applied at the
right scope. The entries are currently absent for an unrelated reason: the
engage-case 422 tracked in #2233.

Investigation also surfaced four documentation drift defects in the
`notes/demo-ci-invariants.md` scenario table (three rows understating their
required types; the FCCV-extension and FCV-reject rows missing entirely).

## Planning consequence

DEMOMA-16-008 requires a spec requirement and its test constants to change in
the same PR. That makes the usual plan-issue split — docs now, code later —
illegal for this change. The DEMOMA-16-001 amendment was therefore deferred to
the implementation issue so it lands together with the nine test-constant
edits, and the docs PR carries only what does not depend on it.

## Outcome

- Docs PR: <https://github.com/CERTCC/Vultron/pull/2265>
  - `notes/demo-ci-invariants.md`: four scenario-table drift fixes, a `Spec`
    column, corrected `DEMOMA-16-001..011` range and harness counts, plus a new
    "Reading a Red Invariant Harness Job" section tabulating the job's three red
    modes and one false-green mode.
  - `AGENTS.md`: two Common Pitfalls entries — *A Red CI Job Is Not Evidence
    That Its Assertions Ran* and *Trace Shared Helper Layers Before Declaring an
    Event Unemitted*.
- Implementation issue: #2266 (blocked-by #2243, sub-issue of Epic #2230).
- No ADR: MS-11-001..006 step 2 is NO — once all nine scenarios are known to
  drive engage-case, universal promotion is uncontested, not a weighed fork.
- Left to siblings under Epic #2230: engage-case 422 root cause (#2233),
  ledger artifacts destroyed by an escaping assertion (#2239), skip-only run
  exits 0 and canonical-replica-only invariants (#2242).
