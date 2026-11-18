---
status: accepted-provisional
date: 2026-11-18
created: 2026-11-18
updated: 2026-11-18
revision: 1
deciders: Allen D. Householder
consulted: >-
  Claude Opus 5.5; ADR-0126, ADR-0138, ADR-0143, ADR-0173, ADR-0179 (the records
  this one consolidates); specs/parallel-development.yaml PAD-18; Concern #4015;
  issues #4699, #5580, #5945; Epic #5944; Idea #1863
informed: []
supersedes:
  - 0126-ci-is-the-full-suite-authority-after-the-first-push.md
  - 0138-a-pushed-pull-request-is-merged-locally-only-on-conflict.md
  - 0143-a-fix-commits-local-gate-escalates-only-for-shared-test-infrastructure.md
  - 0173-a-push-is-gated-by-cis-non-suite-checks-and-a-scratch-merge-of-the-overlap.md
  - 0179-a-local-check-runs-only-when-it-answers-before-a-required-ci-gate.md
stakeholder_type: [project-contributor]
---

# Which Checks Run Locally, Which Run Only in CI, and When to Merge the Base Branch

## Context and Problem Statement

Agents work Pull Requests in parallel on one host, and `main` moves several times an hour.
Five records, from 2026-10-08 to 2026-11-05, decided which checks an agent runs locally and when it merges the base into a Pull Request.
ADR-0126 made CI the full-suite authority after the first push.
ADR-0138 stopped merging the base locally except on a conflict.
ADR-0143 stopped a fix commit's gate escalating for the integration-bearing layers.
ADR-0173 added a local mirror of CI's non-suite checks.
ADR-0179 moved the remaining full-suite runs and the heavy mirror checks to CI, once GitHub required the CI gate.

Each later record replaced part of the earlier ones, so the rule as it stands could be read only by laying the five over each other.
ADR-0179 also made its own rule conditional on GitHub requiring the CI gate; that condition now holds (#5945).

This record states the five decisions as one.
It decides nothing they did not.

Which checks earn a local run, and when does an agent merge the base into a Pull Request?

## Decision Drivers

- **Never merge on red.** Only a check that GitHub enforces may be left to CI alone (`completeness-doctrine.md`).
- **A local check is worth its cost only when it answers before CI would.** A local run that repeats a CI run that is about to happen buys the same answer later.
- **CI on `pull_request` runs the full suite on the Pull Request merged into its base**, and finishes sooner than the same suite on a 2-CPU slot.
- **Parallel agents share one host.**
  A heavy local run slows every other agent on it; a CI run slows none of them.
  Memory kills, per-test timeouts and hung runs came mostly from the heavy local jobs (#3156).
- **A CI round still costs a push, a wait and a review of the fix**, so a cheap local check that finds the most frequent push failures keeps its place.
- **The cost must not grow with fan-out.** A rule that restarts work each time `main` moves gets worse as throughput rises.
- **The local gate must not drift from CI.** A list of checks kept by hand falls behind the workflows.

## Considered Options

1. **CI is the full-suite authority; a local gate runs the linters, the targeted test set and the cheap CI checks; the base is merged locally only on a conflict.**
2. **Run the full suites locally at the gates**: before the first push, after a conflict merge, and for fix commits that touch an integration-bearing layer or shared test infrastructure.
3. **Merge the base and re-test locally whenever the Pull Request is behind or shares files with the base.**
4. **Add more pre-commit hooks** in place of a pre-push mirror.
5. **Adopt GitHub's merge queue.**

## Decision Outcome

Chosen option: **"CI is the full-suite authority"**, because it removes the local runs that repeat CI, keeps the cheap local checks that answer first, and bounds the work a moving `main` causes.

### Decision details

1. **The rule.**
   A local check stays only when it answers before CI would.
   A check is left to CI alone only when GitHub refuses a merge into the base while that check is red or has not run (PAD-18-031).
   The current lists of local and CI-only checks are in PAD-18; this record fixes the rule and its precondition, not the lists.

2. **CI runs the full suites, and no local gate does.**
   No gate runs the full unit or integration suites, before the first push or after it, whatever paths the diff touches (PAD-18-003, PAD-18-008).
   pyright runs only in CI (PAD-18-027).
   A skill that hands off to `create-pr` runs no suite itself (PAD-18-017).

3. **Every local test gate is the linters plus the targeted set.**
   The linters are ruff, lint and format, and mypy (PAD-18-026).
   The targeted set holds each test file that imports a changed symbol, each changed module's mirror test file, each changed test file, and the always-selected `test/architecture/` and `test/metadata/`, with the integration marker enabled (PAD-18-002, PAD-18-011).
   The always-selected directories hold the tree-reading checks — ratchets, generated-file sync and size limits — where nearly every red local run failed.
   This gate runs before an implementation Pull Request's first push and on each fix commit after it (PAD-18-001, PAD-18-002).
   A Pull Request that changes no Python is gated by the linters and the mirror (PAD-18-010).
   When the paths include shared test infrastructure, whose reach no import index can bound, the gate runs what it can select plus the always-selected directories, and CI's full run covers the rest (PAD-18-012).
   A fix for a CI failure outside the set adds that test's file to the gate (PAD-18-013).

4. **Every push runs the mirror of CI's cheap checks.**
   Before each push, the first included, the agent runs `prepush-ci-mirror` on the whole branch diff and pushes only on a pass (PAD-18-021).
   The mirror covers what pre-commit hooks and the targeted set miss: hooks see only staged files, some guards are tests outside the set, and a Pull Request with no Python runs no tests.
   Every step a pull-request CI run can execute is either mirrored or excluded in the mirror's registry with a reason, and a test fails a step that is neither, so the mirror cannot fall behind the workflows (PAD-18-022).
   The heavy checks — pyright, the spec-corpus suite, the separate guard-test run, the site build and the checks that read the built site — are excluded, because CI answers them sooner (PAD-18-023).

5. **The base is merged into a pushed Pull Request locally only on a conflict.**
   A conflict is GitHub reporting the Pull Request `CONFLICTING` or `DIRTY`, or a trial merge that conflicts; files changed on both sides without a conflict are not one (PAD-18-004).
   The trial merge moves no branch and writes no worktree (PAD-18-025).
   A conflict resolution is lines an agent wrote, so its gate is the linters and the targeted set for the conflicted files alone, each counted as wholly changed, plus the always-selected directories (PAD-18-015).
   A clean merge holds no line an agent wrote: a Pull Request GitHub reports `BEHIND` is updated on GitHub with `gh pr update-branch`, with no local merge and no local run (PAD-18-014).
   No ruleset requires a branch to be up to date with its base before a merge: the required CI gate is not strict, so being behind is not itself a reason to merge.
   No agent runs tests on an uncommitted scratch merge, because CI already tests the branch merged with its base (PAD-18-024).
   `pr-verify` defers to GitHub's reported merge state and does not compute base-tip containment itself (PAD-18-005).

6. **The merger checks only the Pull Request it is about to merge.**
   Right before a merge, the merging agent checks that Pull Request alone against the current base (PAD-18-009).
   A conflict sends it back through the review pipeline (PAD-18-018).
   A Pull Request that is `BEHIND`, or whose files the base also changed, is updated on GitHub at most once and merged only after CI passes on the updated head (PAD-18-019).
   The merge moment is the only time the base it lands on is known.
   A merge that moves the base re-checks no other open Pull Request (PAD-18-020).

7. **An implementation Pull Request is a draft until CI passes.**
   It meets the full suite first in CI, so `create-pr` opens it as a draft (PAD-18-028).
   An agent marks it ready when, and only when, CI's latest run on its head has passed (PAD-18-029).
   That first CI run is the full-suite run the local gate no longer makes, so it does not count against `pr-execute`'s limit on CI rounds (PAD-18-030).

8. **The trade is measured.**
   `pr-execute` records each Pull Request's local runs as `Suite runs: <N> full, <M> targeted`, counting only runs that happened (PAD-18-006, PAD-18-016).
   Velocity reporting gives, per Pull Request and by week, CI runs and failed CI runs, merges from the base, local suite runs and open-to-merge time, plus failed CI runs on `main` (PAD-18-007).
   A material rise in failed runs on `main` would mean the required gate is not holding, or the residual risk below is larger than accepted.

### Consequences

- Good, because a finished Pull Request no longer re-runs a suite and re-waits for CI each time `main` moves.
- Good, because each remaining local run covers lines an agent wrote, and answers before CI would.
- Good, because the most frequent push failures, the mechanical ones, are found in minutes before the push, whatever the Pull Request's type.
- Good, because an overlapping Pull Request is tested by CI on the exact tree it lands on, at merge time.
- Good, because the dev container no longer runs the jobs behind most memory kills and timeouts.
- Bad, because a **semantic** conflict between two Pull Requests that share no file is caught only by CI on `main`, after the merge.
  This is the deliberate trade.
  A red `main` from such a conflict is not fixed by restoring per-movement syncing or full local runs: that re-creates the loop this record removes, and would not catch a conflict between Pull Requests that share no file.
  A merge queue would close the gap; it was evaluated and set aside, because the measured rate of such conflicts fell to near zero (#1863).
- Bad, because a broken change the targeted set misses costs a CI round to discover, as does a type error only pyright finds or a guard-test failure outside the always-selected directories.
- Bad, because the merger's update is the only check of an overlapping Pull Request against its base before merge, so a merger that skips it ships an untested overlap.
- Bad, because every push waits for the mirror.

## Validation

- PAD-18 in `specs/parallel-development.yaml` carries each rule with a `verification:` clause naming the skill step or command that implements it.
- `test/metadata/test_targeted_tests.py` covers the targeted set, the always-selected directories, and the shared-test-infrastructure paths.
- `test/ci/test_prepush_ci_mirror_parity.py` fails a pull-request CI step that is neither mirrored nor excluded with a reason (PAD-18-022).
- The PAD-18-007 velocity data checks the trade: open-to-merge time and local suite runs per Pull Request should fall, and failed CI runs on `main` should not rise.

## Pros and Cons of the Options

### CI is the full-suite authority, with cheap local gates

- Good, because it removes the repeated work, not just its contention.
- Good, because the checks that stay local find the most frequent push failures first.
- Bad, because a few rare failures move from a local gate to a CI round.

### Run the full suites locally at the gates

- Good, because a broken change is found on the developer's machine before CI sees it.
- Bad, because the local run repeats CI's, more slowly: CI ran the unit and integration suites together faster than a 2-CPU slot ran the unit suite alone.
- Bad, because most Pull Requests got commits after they opened, so a full run before the first push rarely tested the tree that merged.
- Bad, because the full runs were the main source of shared-host memory exhaustion and of runs too long to watch from a tool call.

### Merge and re-test locally when behind or overlapping

- Good, because the reviewer sees a tree merged with the latest base.
- Bad, because the files most often shared — specifications, notes and generated files — merge cleanly and say nothing about tests, yet each merge paid for a local run.
- Bad, because the cost is unbounded under fan-out: each merge to `main` can restart every overlapping Pull Request's loop.

### Add more pre-commit hooks

- Good, because hooks run without anyone remembering to.
- Bad, because a hook sees only one commit's staged files, and cannot see the base moving after the commit.

### Adopt GitHub's merge queue

- Good, because it tests each candidate against the tree it lands on, which closes the semantic-conflict gap.
- Bad, because it needs a `merge_group` trigger on every required workflow and an aggregate job past the path filters.
- Bad, because it does not by itself stop the local runs this record removes.

## More Information

This record supersedes, whole:

- [ADR-0126](archived/0126-ci-is-the-full-suite-authority-after-the-first-push.md): CI as the full-suite authority, the targeted fix-commit gate, `pr-verify` deferring to GitHub's merge state, and the measured trade are details 2, 3, 5 and 8; its full local run before the first push and its merge on `BEHIND` or overlap had been replaced.
- [ADR-0138](archived/0138-a-pushed-pull-request-is-merged-locally-only-on-conflict.md): the local merge only on conflict, the conflict gate, and the merger's update are details 5 and 6.
- [ADR-0143](archived/0143-a-fix-commits-local-gate-escalates-only-for-shared-test-infrastructure.md): the always-selected directories and the narrowed shared-infrastructure paths are detail 3; its full local run for shared test infrastructure had been replaced.
- [ADR-0173](archived/0173-a-push-is-gated-by-cis-non-suite-checks-and-a-scratch-merge-of-the-overlap.md): the mirror and its registry are detail 4; its heavy mirror checks and scratch-merge test run had been replaced.
- [ADR-0179](archived/0179-a-local-check-runs-only-when-it-answers-before-a-required-ci-gate.md): the rule and its precondition are detail 1, the CI-only checks are details 2 and 4, and the draft until CI passes is detail 7.

Related:

- [ADR-0139](0139-a-fresh-agent-reviews-the-branch-before-its-first-push.md) decides the fresh-agent review before the first push.
- #5945 is the ruleset that requires the CI gate before a merge into `main`, the precondition of detail 1.
- Concern #4015, issues #4699 and #5580, and Epic #5944 carry the measurements behind the five records.

Generated spec requirements: `specs/parallel-development.yaml` PAD-18.
