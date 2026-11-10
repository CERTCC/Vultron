---
title: "The gate's wall-clock ceiling is calibrated for a slot it does not own, so exit 124 can be CPU contention on an honest run rather than a hang"
type: learning
timestamp: "2026-11-09T23:58:00Z"
source: ISSUE-6028
signal: theme-candidate
---

## Trigger

A targeted gate ends with `exit: 124`. Its log shows the progress dots reached
90-something percent, with no `F`, no `E` and no traceback anywhere in it, and
`run-heavy.py` printed its "all N heavy-check slots are busy; waiting" line
earlier in the same log naming two other worktrees.

## Claim

`notes/testing-pitfalls.md` § "Dead Worker" says the `timeout -k 30 1800`
ceiling is what a hang "still left" ends as, and `run-tests`' table reads 124
the same way. That is one cause, not the only one. The slot count
(`DEFAULT_SLOTS = 2` in `.agents/skills/shared/run-heavy.py`) and the ceiling
(`GATE_CEILING` in
`vultron/metadata/planning/targeted_tests/selection.py`) are calibrated
independently of each other, and a slot is not a CPU reservation: on a
two-CPU devcontainer VM two slot holders each run `pytest -n auto`, each sizes
its workers from the cgroup, and both then contend. The ceiling is set for a
run that has the machine.

So the reading of 124 has to start from the log, not from the exit status: a
run killed mid-collection or stalled at one test is a hang; a run that was
nearly finished and had company is a contention trip, and TB-14-003's remedy
(raise the tier, do not mark anything flaky) applies.

## Evidence

The first gate run of #6028 tripped the 1800-second ceiling at 99% with zero
failures while `/tmp/wt-5598` and `/tmp/wt-6026` held both slots on the same
host. The identical selection, rerun under a wider ceiling once the host was
quiet, finished in 341 seconds — a factor of five under the ceiling it had just
exceeded. Nothing about the branch changed between the two runs.

## What would confirm it

A second 124 whose log shows the same shape: high progress, no failure, and a
`run-heavy` wait line naming another worktree. Those logs are written to
`/tmp/vultron-<worktree>-gate.log`, so the shape is checkable on any host where
two agents are working at once. The counter-evidence would be a 124 at high
progress on an *idle* host, which would mean the ceiling is simply too tight
for the largest selections and belongs raised rather than explained.

## How to apply it

Before treating a 124 as a hang, read the tail of the gate log for progress and
the head for a `run-heavy` wait line. On the contention shape, rerun the same
selection rather than hunting a hang, and say in the PR body that the first run
tripped the ceiling and what the rerun did — a bare "rerun and it passed" is
the flaky claim `completeness-doctrine.md` § "Never Merge on Red" refuses. If
the pair turns out to be systematic, the fix is one of the two numbers: fewer
slots, or a ceiling that assumes it shares the host.
