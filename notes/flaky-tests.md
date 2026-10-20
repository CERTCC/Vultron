---
title: Known Flaky Tests
status: active
kind: guidance
description: >
  Fast-lookup catalog of known flaky tests and CI jobs mapped to their open
  tracking issues, used by `pr-execute` as a cache before searching GitHub,
  plus the triage rules for deciding that a failure is flaky at all.
related_notes:
  - notes/testing-pitfalls.md
  - notes/sync-ledger-replication.md
  - notes/bt-integration.md
  - notes/outbox-delivery-reliability.md
  - notes/datalayer-design.md
  - notes/git-workflow-pitfalls.md
---

# Known Flaky Tests

Fast-lookup catalog of known flaky tests and CI jobs mapped to their tracking
issues. `pr-execute` reads it before querying GitHub; the full procedure is
`.agents/skills/pr-execute/REFERENCE.md` § "Flaky Test Dedup".

**GitHub is always ground truth.** Before trusting an entry, check the issue is
still open (`gh issue view <N> --json state`). A closed issue evicts its entry;
fall through to the GitHub search. `pr-execute` adds an entry when it confirms a
pre-existing failure; `bugfix` or `build` removes it when the issue closes.

## Before Adding a Row

- **No summary line means the run was killed, not that a test failed or
  passed.** The gate's `timeout` ceiling (exit 124) or an OOM kill (exit 137)
  ends the whole session, so counting `FAILED` lines scores an aborted run as
  clean. Check for the summary line first. See
  [testing-pitfalls.md](testing-pitfalls.md) § "Reading Test Output".
- **Ask whether the test is nondeterministic or the ceiling is wrong.** A test
  near its timeout tier is not flaky; fix the tier (#2270). The opposite error,
  cataloguing a deterministic protocol bug as noise, is just as costly (#2249).
- **Match a CI job on the failure message, not only the job name.** One job can
  carry several unrelated race signatures; the table names the signature where a
  job has more than one tracker.

## Unit Tests (pytest node IDs)

A `—` in the Issue column means no tracking issue exists; `pr-execute` skips the
`gh issue view` step and falls through to the GitHub label search.

| Test node ID | Issue | Last blocked |
|---|---|---|
| `test/bt/test_vultrabot.py::MyTestCase::test_main` | — | 2026-05-05 |

`test_vultrabot` shows `SUBFAILED` but pytest still exits 0, so it never blocks
a merge; see [testing-pitfalls.md](testing-pitfalls.md).

## Integration-Marker Tests (pytest node IDs)

No open entries.

## CI / Demo Integration Jobs (job name granularity)

| Job name | Issue | Last blocked |
|---|---|---|
| `rcvv-embargo Demo Integration` — `Vendor2 received the full-case Invite` gate times out while Vendor2's replica replays the backfill | #4424 | 2026-10-12 |
| `rcvv-embargo Invariant Harness` | #4424 | 2026-10-12 |
