---
source: CONCERN-4015
timestamp: '2026-10-08T19:11:24.721901+00:00'
title: build → pr-ship spends 2–2.7 h per PR on full local reruns and merge-from-main
  loops that CI already covers
type: learning
---

## Summary

Getting one PR from `build` start to `READY-TO-MERGE` takes 2–2.7 hours, and PR size barely changes that.
Repeated full local suite runs set most of that time, and each merge from main restarts the loop.
The pipeline runs the full local suite before almost every push, after trivial fixes too.
It also treats any movement on main as a reason to sync again, rerun the suite and wait for CI, even though GitHub does not require that.

## Surface Symptom vs. Underlying Problem

**Surface reading:** the test suite is slow, so make it faster.
The suite was already sped up (#4277, xdist sized to the slot).
Local unit runs now take about 7 minutes, and the pipeline is still slow.

**Underlying problem:** the gates are in the wrong places, not too slow.
Two rules multiply the number of runs:

1. **A full local run before every push.**
   `create-pr` runs unit + integration.
   `pr-execute` Phase 5 runs the full suite on every Sync → Test → Push → Wait iteration (up to 4).
   `pr-execute/REFERENCE.md` says "Re-run the full suite after resolving, even if it passed pre-merge."
   A one-line docstring fix costs the same as a refactor.
   CI (`python-app.yml`) runs the *full* suite (`-m ""`) in about **5 minutes**.
   That is faster than the local unit-only run (about 7 minutes on a 2-CPU slot) and covers more.
   After the first push, a local full rerun often only repeats what CI is about to report, and more slowly.
2. **`BRANCH-BEHIND` blocks `READY-TO-MERGE` in `pr-verify`.**
   When main moves, verify fails the verdict, so the agent syncs again, reruns the full suite, pushes, waits for CI and verifies again.
   Main moves several times an hour during fan-out, so this loop can repeat for hours.
   GitHub does not enforce this rule.
   No ruleset sets strict ("require branches to be up to date") status checks, and there is no merge queue.
   CI on `pull_request` already tests the merge of the PR into main as of the push.

**Already correct — keep these:**

- One full local run before the **first** push, so obviously broken branches do not use CI time.
- Never merge on red, and read the `exit:` line rather than the tail (`run-tests`).
- The conflict-resolution rules in `pr-execute/REFERENCE.md` (read both sides, never delete base changes, abort on a conflict you do not understand).
- A real textual or semantic conflict with main still needs a fresh check.
  The fix is to stop re-checking when nothing relevant changed, not to stop checking.

## Category

- [x] Performance / scaling
- [x] Technical debt

## Severity

medium

## Evidence

Original measurements (Epic #1936 children, 2026-09-30 / 10-01), agent start to merge:

| PR | Issue | Wall clock |
|---|---|---|
| #3976 | #3828 (size:S) | 2.1 h |
| #3983 | #3829 (size:M) | 2.7 h |
| #3982 | #3827 (size:M) | 2.7 h |
| #4001 | #3831 (size:L) | 1.9 h build + 0.6 h ship |
| #4007 | #3832 (size:L) | 2.5 h |
| #4009 | #3833 (size:M) | 2.1 h |

Merges from main in recent PRs (2026-10-07 / 10-08):

| PR | Merges from main | Other commits | CI runs (fail) |
|---|---|---|---|
| #4326 | 7 (six of them between 13:41 and 15:22 on 10-08) | 3 | 8 (2) |
| #4329 | 4 | 5 | 4 (2) |
| #4320 | 3 | 4 | 4 (0) |
| #4332 | 3 | 7 | — |
| #4327 | 3 | 4 | — |

In #4326 the PR was finished after its fourth commit.
The six later commits are all merges from main.
Under the current rules each one meant a local full suite run, a CI wait and another verify.

Gate locations:

- `.agents/skills/create-pr/SKILL.md` — freshen onto `origin/main`, then unit + integration before push
- `.agents/skills/pr-execute/SKILL.md` § Phase 5 — full suite on each of up to 4 iterations
- `.agents/skills/pr-execute/REFERENCE.md` — "Re-run the full suite after resolving, even if it passed pre-merge"
- `.agents/skills/pr-verify/SKILL.md` — `BEHIND` → `BRANCH-BEHIND`, blocks `READY-TO-MERGE`
- `.github/workflows/python-app.yml` — `pull_request` trigger, `uv run pytest -m "" -n auto`, about 5 min
- Repo rulesets — no strict status-check policy, no merge queue

## Impact if Ignored

Unattended fan-out (Epic #3797) multiplies this cost by the number of agents.
More parallel slots make main move faster, which makes each PR fall behind more often.
The loop gets worse as throughput grows.
The 2-CPU slot cap (`start-dev.sh`) means faster hardware cannot help.
Agents spend most of their turn budget polling, which is where "waiting for notification" stalls come from.
Nothing records how many suite runs a PR used, so the cost does not show up in `velocity-report`.

## Suggested Action

Scale the local gate to how risky each change is, and let CI be the full-suite authority after the first push:

1. **First push — keep the full local gate.**
   This one run keeps failing branches out of CI.
2. **Fixes after the first push — targeted local run.**
   For triage or CI fixes, run linters, the test files for changed modules, and the architecture ratchets (`test/architecture/`), then push and let CI run the full suite.
   Escalate to a full local run only when the fix touches shared infrastructure (conftest, fixtures, factories, `pyproject.toml`) or CI just failed for a reason the targeted set would not catch.
3. **Merge from main — rerun only when the merge changed something relevant.**
   With no conflicts and no overlap between files main changed and files the PR changed, do not rerun locally; CI tests the merge ref.
   With conflicts or overlap, run the targeted set for the overlapping modules, then push.
   Replace the "re-run the full suite after resolving" rule with this.
4. **Drop `BRANCH-BEHIND` as a verdict blocker, or narrow it.**
   Since GitHub does not require it, block only when CI's last green run is on a merge base that main has since conflicted with, or when main changed files the PR also touches.
   Otherwise report "behind by N" as information.
   Sync once at the end only if GitHub reports a conflict.
5. **Measure it.**
   Record suite-run count, CI-run count and wall clock per PR in the execute artifact or ship-stage comment, so `velocity-report` can show the cost and confirm that steps 1–4 helped without more red CI runs on main.

Governing specs: PAD-17-002, TB-03-001.
CI run time itself is Epic #3791's concern; this one is about the local pipeline and its gate placement.

---

**Resolved**: 2026-10-08 — implementation tracked in #4357, #4358, #4359.
Docs PR: <https://github.com/CERTCC/Vultron/pull/4356>.
Spec: `specs/parallel-development.yaml` (PAD-18, Pipeline Test-Gate Placement).

**Planning corrections to the diagnosis above:**

- The `BRANCH-BEHIND` verdict blocker in `pr-verify` almost certainly never
  fires. GitHub reports `BEHIND` only when a ruleset requires branches to be
  up to date, and none of this repository's three active rulesets does. PR
  #4354 sat four commits behind main and GitHub reported `UNSTABLE`. Removing
  the flag is cleanup, not the fix.
- The real loop drivers are: `pr-execute` Phase 5 merging main on every pass,
  its rule to restart from the sync step after any fix, `UNSYNCED-EXECUTE`
  in `pr-verify` requiring the branch to contain main's latest commit, and
  orchestrators re-syncing every open PR after each merge.
- `work-epic-tasks` already carries the narrow rule this concern asked for:
  it re-runs `pr-ship` only when a sync touched the PR's files or conflicted.
- The targeted-test set does not need new analysis machinery.
  `vultron/metadata/specs/backstop/` already indexes which test files import
  which `vultron` symbols and which test file mirrors each module.

**Accepted risk**: merging main only on conflict or overlap leaves a rare
semantic conflict between files neither side shares, caught by CI on `main`
rather than prevented. Noted on #1863 (evaluate GitHub merge queue), which is
the mechanism that would close it; the per-week count of failed CI runs on
`main` from #4359 is the evidence that should decide whether the queue earns
its serialization cost.
