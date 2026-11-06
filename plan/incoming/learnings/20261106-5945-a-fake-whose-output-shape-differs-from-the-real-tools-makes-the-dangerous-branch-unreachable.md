---
title: A fake whose output shape differs from the real tool's makes the dangerous branch unreachable
type: learning
timestamp: 2026-11-06T16:45:00Z
source: ISSUE-5945
signal: theme-candidate
---

## Trigger

You are reading code that parses another tool's output — `gh --json`, a
subprocess, an API client — and its tests drive it through a hand-written fake
that returns the same *fields* the real tool returns. Every test passes. Ask
what the real tool emits for an **absent or not-yet-set** value, and whether the
fake emits that too.

## Claim

A fake that agrees with the real tool on the happy-path shape but not on its
*empty* and *unset* renderings does not merely leave a branch untested — it
makes the branch **unreachable from the suite**, so no amount of added cases
finds the defect. The suite then reports full coverage of a reading that is
wrong on exactly the inputs the code exists to handle, and only a reviewer who
goes back to the real tool's output can see it.

The sharp edge is that the two disagreements compound. A fake emitting `null`
where the tool emits `""` silently disarms every `//` default in the jq or
Python that reads it; a fake always supplying a real timestamp where the tool
supplies a zero value hides that the zero value *sorts*, and sorts to the wrong
end. Each alone is survivable. Together they turn a fail-open bug into a green
test run.

## Evidence

`verify-merge-gate.sh` (#5945, PR #6036) read a PR's `CI gate` runs with
`sort_by(.startedAt // "") | last`, intending the newest run. `gh` renders an
unstarted run's `startedAt` as Go's zero time (`0001-01-01T00:00:00Z`) and a
missing field as `null`; both sort *below* every real timestamp, so `last`
returned an **older** run. A still-running gate beside an older green one read
as `SUCCESS`, and `pr-verify` would have answered `READY-TO-MERGE` for a PR
GitHub was blocking — a fail-open bug in the very check added to stop
fail-open merges. Its fake (`status_rollup()` in
`test/metadata/_script_sandbox.py`) gave every run a real `startedAt` and
`conclusion: None`, so the broken input could not be constructed. 50 tests
passed; the pre-push review found it by re-deriving the reading from `gh`'s
documented output.

## What would confirm it

A second instance where a test double's rendering of an absent value differed
from the real source's and hid a branch. Likely homes: the `_fake_gh.py`-driven
skill-script tests, `DataLayer` row fakes versus real SQLite `NULL`, and wire
fixtures hand-built instead of round-tripped through the parser. Two sibling
entries already in this queue (`20261031-5534`, `20261102-5536`) concern test
doubles going stale when their *target* moves; this is the adjacent claim about
the double's *data*, and corroboration should not be read across from them.

## How to apply

When a fake stands in for a tool whose output you parse, derive its empty and
unset renderings from the real tool once — capture one real payload — and make
the fake reproduce them, naming each as a constant (`ZERO_TIME`) so the next
reader sees that it was a deliberate choice. Then write the case that uses it.
Where it is cheap, prefer a recorded real payload to a constructed one.
