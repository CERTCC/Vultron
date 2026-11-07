---
status: accepted-provisional
date: 2026-11-05
created: 2026-11-05
updated: 2026-11-05
revision: 1
deciders: Allen D. Householder
consulted: >-
  Claude Opus 5.5; ADR-0126; ADR-0138; ADR-0143; ADR-0173;
  specs/parallel-development.yaml PAD-18; Epic #5944, issues #5945, #5946
informed: []
stakeholder_type: [project-contributor]
partially_supersedes:
  - 0126-ci-is-the-full-suite-authority-after-the-first-push.md
  - 0138-a-pushed-pull-request-is-merged-locally-only-on-conflict.md
  - 0143-a-fix-commits-local-gate-escalates-only-for-shared-test-infrastructure.md
  - 0173-a-push-is-gated-by-cis-non-suite-checks-and-a-scratch-merge-of-the-overlap.md
---

# A Local Check Runs Only When It Answers Before a Required CI Gate

## Context and Problem Statement

[ADR-0126](0126-ci-is-the-full-suite-authority-after-the-first-push.md) kept one full local run of the unit and integration suites before a Pull Request's first push, so that an obviously broken branch stayed out of CI.
[ADR-0138](0138-a-pushed-pull-request-is-merged-locally-only-on-conflict.md) kept a full local run after a conflict merge that touches shared test configuration.
[ADR-0143](0143-a-fix-commits-local-gate-escalates-only-for-shared-test-infrastructure.md) kept a full local run for a fix commit that touches shared test infrastructure.
[ADR-0173](0173-a-push-is-gated-by-cis-non-suite-checks-and-a-scratch-merge-of-the-overlap.md) added a local mirror of every non-suite CI check before each push, and a local test run on a scratch merge of the branch with its base.

All four rested on two premises.
The first was that CI was not an enforced gate: no ruleset required a green CI run before a merge, so a local run was the only check an agent could not skip.
The second was that a local run cost little next to a CI round.

Neither premise holds now.
GitHub can refuse a merge into `main` unless the required CI check passed (#5945), and the measurements from 2026-10-06 to 2026-11-05 show the local runs cost more than the CI runs they repeat:

- The local unit suite took a median of 11.6 minutes, while CI ran the unit and integration suites together in about 9.8 minutes.
- Agents waited about 45 hours in total for local runs and about 11.6 hours for CI.
- 86% of merged Pull Requests got commits after they opened, so the full run before the first push almost never tested the tree that merged.
- The local CI mirror used a median of 824 seconds of check time on each push. The spec-corpus suite took 230 seconds of that, the site build 334 seconds, and the guard tests 94 seconds. CI runs its spec job in about 1.8 minutes and its docs job in about 2.7 minutes.
- pyright took a median of 2.0 minutes in each local linter step, and used enough memory to starve parallel test runs (#3156). mypy, with its cache, took about 8 seconds.
- CI on a Pull Request already tests the merge of the branch into its base, which the local scratch-merge run repeats.
- The shared dev container reached its memory limit 3,753 times, with 58 per-test timeouts, 19 memory kills and 18 hung runs in the transcripts.

The question this record settles: once GitHub refuses a merge without a green CI run, which checks still earn a local run?

## Decision Drivers

- Never merge on red is non-negotiable. Only a check GitHub enforces may be left to CI alone.
- A local check is worth its cost only when it answers before CI would. That is the test ADR-0126 and ADR-0173 already applied, with old numbers.
- Parallel agents share one host. A heavy local run slows every other agent on it, and a CI run slows none of them.
- A CI round still costs a push, a wait and a review of the fix. A cheap local check that finds the most frequent push failures in minutes, before CI would, keeps that saving.

## Considered Options

- Keep the gates as they are.
- Keep the gates, and make the local runs cheaper by queueing them.
- Run locally only the checks that answer before CI would, and leave the rest to the required CI gate.

## Decision Outcome

Chosen option: **run locally only the checks that answer before CI would, and leave the rest to the required CI gate**.

The rule is: a local pre-push check stays only when it answers before CI would, and a check is left to CI alone only when GitHub refuses a merge while that check is red or has not run.
The rule takes effect for each check when GitHub starts to require it.
Until then, the gates of ADR-0126, ADR-0138, ADR-0143 and ADR-0173 stand.

With the required CI gate in place, these checks run in CI only:

- The full unit and integration suites, at every point in the pipeline. This includes the run before the first push (ADR-0126), the escalation for shared test infrastructure (ADR-0143), and the escalation after a conflict merge (ADR-0138). A gate whose diff touches shared test infrastructure runs the tests it can still select, and CI's full run covers the rest.
- pyright.
- The heavy mirror checks: the spec-corpus suite, the mirror's separate run of the limit-enforcing guard tests, the site build, and the checks that read the built site (ADR-0173). Most guard tests sit in the architecture and metadata test directories, which every targeted gate still runs.
- The tests on a merge of the branch with its base (ADR-0173). CI already tests that merge. The fast conflict check on a trial merge, which runs no tests, stays local.

These checks stay local, before every push:

- ruff, lint and format, and mypy.
- The targeted test set of the diff, including the tree-reading architecture and metadata checks.
- The cheap mirror checks: generated-file sync, front matter, the decision-record index, spec lint, and Markdown lint on the changed files. These find the most frequent push failures in a few minutes.

With the required CI gate in place, a Pull Request meets the full suite for the first time in CI, so its first push opens it as a draft.
It is marked ready for review once a CI run on its current head passes, so a failed first run keeps it a draft only until a fix passes.
That first run does not count against the limit on CI rounds for fixes, because it is the full-suite run the local gate no longer makes.

The CI checks that each classification depends on can change.
The specs that cite this record hold the current lists.
The principle and the precondition above are what this record fixes.

This partly supersedes four records.
From ADR-0126, it replaces the full local run before the first push.
CI stays the full-suite authority after the push, and the targeted gate for fix commits stands.
From ADR-0138, it replaces the full local run after a conflict merge that touches shared test configuration.
The rest of ADR-0138 stands: a pushed branch is merged locally only on a conflict, and the conflict gate covers the conflicted files.
From ADR-0143, it replaces the full local run for shared test infrastructure.
The targeted set, and the directories it always selects, stand.
From ADR-0173, it replaces the heavy mirror checks and the scratch-merge test run.
The mirror of the cheap checks, and the rule that each CI step is either mirrored or excluded with a reason, stand.

### Consequences

- Good, because the local heavy-job time per Pull Request falls from about 75 minutes to about 21, by the estimate behind Epic #5944.
- Good, because a Pull Request reaches CI's full run about 14 minutes sooner, and that run tests the merge with the base.
- Good, because the dev container no longer runs the jobs that caused most memory kills and timeouts.
- Bad, because a broken change that the targeted set misses costs a CI round to discover, where a local full run would have found it first. The targeted set and the always-selected directories are where nearly every red local run failed (ADR-0143), so this case is rare.
- Bad, because a type error that only pyright finds, or a failure in a guard test outside the always-selected directories, is found in CI, one round later.
- Neutral, because a semantic conflict between files the two sides do not share is still found only by CI, as ADR-0126 accepted.

## Validation

PAD-18 in `specs/parallel-development.yaml` carries the per-change requirements.
The decision is checked by the PAD-18-007 data.
Open-to-merge time and local suite runs per Pull Request should fall.
CI failures per Pull Request may rise a little, and failed CI runs on `main` should not rise.
A rise in failed runs on `main` would mean the required gate is not holding, which this decision cannot accept.

## Pros and Cons of the Options

### Keep the gates as they are

- Good, because nothing changes, and a broken change is found locally before CI sees it.
- Bad, because every Pull Request pays about 75 minutes of local heavy jobs, mostly to repeat what the required CI gate runs anyway, and sooner.
- Bad, because the premise the gates rested on, that CI is not enforced, no longer holds.

### Keep the gates, and queue the local runs

- Good, because a host limit on concurrent heavy jobs stops memory kills and timeouts.
- Bad, because queueing makes each run wait longer. It does not remove the repeated work.
- Neutral, because a host limit is still useful for the heavy checks that remain, so it is built alongside this decision (#5947), not instead of it.

### Run locally only what answers before CI

- Good, because it removes the repeated work, not just its contention.
- Good, because the cheap checks that stay local find the most frequent push failures.
- Bad, because it moves a few rare failures from the local gate to a CI round.

## More Information

The measurements are in the local report behind Epic #5944, which tracks the work this record governs.
The precondition is the ruleset that requires the CI gate check before a merge into `main` (#5945).

Generated spec requirements: `specs/parallel-development.yaml` PAD-18-026 and PAD-18-031, and the PAD-18 amendments that take effect with the required CI gate.
