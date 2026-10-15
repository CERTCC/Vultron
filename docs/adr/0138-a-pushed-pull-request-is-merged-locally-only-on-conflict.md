---
status: proposed
date: 2026-10-15
created: 2026-10-15
updated: 2026-10-15
revision: 1
deciders: Allen D. Householder
consulted: >-
  Claude Opus 5.5; ADR-0126; specs/parallel-development.yaml PAD-11-001,
  PAD-18; issues #4699, #1863
informed: []
stakeholder_type: [project-contributor]
partially_supersedes:
  - 0126-ci-is-the-full-suite-authority-after-the-first-push.md
---

# A Pushed Pull Request Is Merged Locally Only on Conflict

## Context and Problem Statement

[ADR-0126](0126-ci-is-the-full-suite-authority-after-the-first-push.md) made CI the full-suite authority after a Pull Request's first push.
It kept three reasons to merge the base into a pushed Pull Request: GitHub reports a conflict, GitHub reports `BEHIND`, or the base changed a file the Pull Request also changes.
After such a merge, the local gate was the targeted set derived from the whole post-merge branch diff.

During parallel fan-out the overlap reason fired far more often than conflicts did, and every merge it caused paid for a local suite run.
Across the 60 Pull Requests merged from 2026-10-12 to 2026-10-15, agents merged `main` into their branches 67 times, and one Pull Request did so five times.
The files most often shared were specifications, notes, and generated files, such as `specs/case-management.yaml`, edited by 12 of the 60.
Those files merge cleanly, and no test can tell whether they "overlap".
The gate after the merge was derived from the whole branch diff, so it escalated to the full suite whenever the Pull Request touched any PAD-18-003 path, which 34 of the 60 did.
Of the 41 Pull Requests whose execute summary could be read, the pipeline recorded 65 full local runs and 19 targeted ones.

Two parts of the pipeline turned each merge into a loop.
`pr-execute` re-checked for overlap when CI went green and returned to the merge step if `main` had moved onto the Pull Request's files during the CI wait.
`work-epic-tasks` re-checked every open Pull Request after each merge and re-ran the whole review pipeline for any that overlapped.
On the busiest day of that window 42 Pull Requests merged, so `main` moved during almost every seven-minute CI wait, and a ready Pull Request could go through the loop several times.

The question this record settles: once a Pull Request is pushed, which syncs with the base need an agent and a local test run, and which can GitHub and CI do alone?

## Decision Drivers

- A local suite run on a shared slot is the most expensive step an agent repeats, and parallel agents running it at once slow each other down.
- CI on `pull_request` already tests the Pull Request merged into its base, as of each push, with the full suite.
- `gh pr update-branch` makes the same merge commit a local `sync-with-main.sh` makes, on GitHub, and the push triggers CI. It needs no agent and no local run.
- A conflict cannot be resolved without an agent, so its cost is unavoidable. Every other sync is a clean merge.
- Never merge on red stays non-negotiable (`completeness-doctrine.md`).
- The repository's rulesets require no status checks and no up-to-date branches, so a change that needs no workflow or ruleset edit is preferred.

## Considered Options

- **Keep ADR-0126's overlap rule** — merge locally on conflict, `BEHIND`, or overlap, and gate on the post-merge branch diff.
- **Adopt GitHub's merge queue** — require status checks and a queue, so GitHub tests each Pull Request against the base it lands on.
- **Merge locally only on conflict, and let GitHub make every clean merge** — gate a conflict merge on the conflicted files alone, and have the merger update an overlapping Pull Request on GitHub right before merging it.

## Decision Outcome

Chosen option: **merge locally only on conflict, and let GitHub make every clean merge**.

An agent merges the base into a pushed Pull Request locally only when the two conflict (PAD-18-004).
The gate after resolving that conflict is the linters plus the tests for the conflicted files, each treated as wholly changed, because both sides edited it.
Only shared test configuration among those files sends the gate to the full suite.
CI runs the full suite on the push.

A Pull Request that merges cleanly is never merged locally, whether it is behind the base or shares files with it.
A Pull Request GitHub reports `BEHIND` is updated on GitHub.
An overlapping Pull Request is updated on GitHub by the agent merging it, right before the merge, and merged only after CI passes on the updated head (PAD-18-009).
That check runs on the Pull Request about to merge, once, and never as a sweep of the other open Pull Requests.

The reasoning is that a local run is worth its cost only when it covers lines an agent wrote.
A conflict resolution is such a line, and its tests are known.
A clean merge contains no line any agent wrote, so the only useful test of it is CI against the base it lands on, and the merge moment is the only time that base is known.

### Consequences

- Good, because an overlap no longer costs a local merge, a local suite run, or a re-run of the review pipeline; it costs one CI wait at merge time.
- Good, because overlapping Pull Requests get a stronger check than before: a full CI run on the exact tree that will land, instead of a local targeted run on a tree that `main` will move past again.
- Good, because the gate after a conflict covers the conflicted files and no longer escalates for paths the merge never touched.
- Good, because a Pull Request is synced at most twice per merge, by its own conflict and by the merger's update, instead of once per movement of `main`.
- Bad, because a Pull Request can be marked ready to merge while behind the base on files it changed. The merger's update is now the only check of that combination before merge, so a merger that skips it ships an untested overlap.
- Bad, because a merge can wait one extra CI run, about seven minutes, when the Pull Request overlaps the base.
- Neutral, because the semantic-conflict risk ADR-0126 accepted is unchanged: two Pull Requests that share no file but are incompatible are still caught by CI on `main`, after the merge.

## Validation

PAD-18-004 and PAD-18-009 in `specs/parallel-development.yaml` carry the requirements, each with a `verification:` clause naming the skill step that implements it.
`targeted-tests --paths` carries the conflict gate, and `test/metadata/test_targeted_tests.py` tests its selection and escalation.
The decision is checked by the same PAD-18-007 data as ADR-0126: merges from the base and local suite runs per Pull Request should fall, while failed CI runs on `main` should not rise.

## Pros and Cons of the Options

### Keep ADR-0126's overlap rule

- Good, because an overlapping Pull Request is merged and tested before review finishes, so the reviewer sees the merged tree.
- Bad, because the measured cost is dominated by it: most merges were for overlap, and most gates after a merge were full runs.
- Bad, because it has no bound under fan-out: each merge to `main` can restart every overlapping Pull Request's loop.

### Adopt GitHub's merge queue

- Good, because it tests every candidate against the tree it lands on, which closes the semantic-conflict gap as well.
- Bad, because it requires adding required status checks, a `merge_group` trigger on every required workflow, and an always-running aggregate job to get past the path filters, all of them CI and ruleset changes.
- Bad, because it does not by itself stop the agents' local merges and runs; the skill changes this record makes would still be needed.

This option stays open as Idea #1863 for the semantic-conflict gap.

### Merge locally only on conflict, and let GitHub make every clean merge

- Good, because it removes the cost without a CI or ruleset change.
- Good, because each remaining local run covers lines an agent wrote.
- Bad, because the merge-time update adds a step the merger must not skip.

## More Information

This record partially supersedes ADR-0126: it replaces the decision to merge the base on `BEHIND` or file overlap, and the post-merge gate derived from the branch diff.
ADR-0126's other decisions stand: one full local run before the first push, targeted gates for fix commits, and `pr-verify` deferring to GitHub's reported merge state.

Issue #4699 carries the measurements and the change list.
