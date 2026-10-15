---
status: proposed
date: 2026-10-15
created: 2026-10-15
updated: 2026-10-15
revision: 1
deciders: Allen D. Householder
consulted: >-
  Claude Opus 5.5; ADR-0126; ADR-0138; specs/parallel-development.yaml PAD-07,
  PAD-17, PAD-18; issues #4711, #4712
informed: []
stakeholder_type: [project-contributor]
---

# A Fresh Agent Reviews the Branch Before Its First Push

## Context and Problem Statement

`build` reviewed its own branch before opening a Pull Request: the agent that wrote the code invoked `code-review` and resolved what it called blocking.
After the push, `pr-ship` ran `pr-triage` in a fresh agent, and that agent still found a median of six problems per Pull Request: one FAIL and five IMPROVE, over the first triage of 37 agent-built Pull Requests from 2026-10-12 to 2026-10-15.
Each finding was fixed after the push, so each cost a fix commit, a local gate and a CI run.
The stretch from the triage comment to the execute comment had a median of 45 minutes, the longest phase of a median Pull Request.

About a third of those findings are judgment only a reviewer that did not write the code makes well.
About 45% fall into four recurring oversights: stale text after the change, an untested branch, duplicated code, and a failure path that leaves partial state.

The question this record settles: where does the fresh-agent review run, and how does the post-push triage avoid repeating it?

## Decision Drivers

- A finding fixed before the first push costs no fix commit, no extra CI run and no post-push gate, because `create-pr`'s one full local run (PAD-18-001) covers it.
- A review by the agent that wrote the change misses what that agent overlooked while writing it, so the reviewer must not share the author's context.
- Most `pr-triage` phases read only the branch and its issues, and only a few need the Pull Request to exist.
- The author can catch the four recurring oversights with a checklist, and a reviewer can then check the record against the diff.
- A Pull Request not opened by `build` must still get the full triage.
- ADR-0138's rule that a pushed Pull Request is merged locally only on conflict stays as it is.

## Considered Options

- **Keep the self-review**: `build` runs `code-review` itself, and the full triage runs after the push.
- **Run the whole pipeline before the push**: `build` runs triage, execute and verify locally, and opens the Pull Request only when they pass.
- **Run the PR-independent triage phases in a fresh agent before the push**: the post-push triage reuses that record and runs only the live-PR phases and the delta.

## Decision Outcome

Chosen option: **run the PR-independent triage phases in a fresh agent before the push**, because it moves most findings ahead of the push without running any phase twice.

The author and the reviewer each get a pass:

1. **Author's pass (`build` Phase 5).** The author runs a four-item self-check on the finished diff: an affected-text sweep, a failure-path pass, branch coverage and a reuse check.
   Each item ends in a written result that the Pull Request body's Verification section carries.
2. **Reviewer's pass (`build` Phase 7).** A subagent that did not write the change runs `pr-triage` in pre-push mode, against the branch diff and the draft body.
   It runs the phases that read only the branch: scope against the issues, domain context, spec conformance, the ADR check, AGENTS.md compliance, the code-review subagent, notes and docs currency up to the docs-page determination, and test coverage.
   The code-review subagent gets the same four self-check items as review prompts, from one shared checklist.
   The record goes to a local file named for the branch, because no Pull Request number exists yet.
   `build` fixes every FAIL and IMPROVE finding before `create-pr`, and records how it resolved each one.
3. **Post-push triage (`pr-ship`).** `pr-triage` finds the pre-push record by branch name.
   It runs the phases that need the Pull Request: issue links as posted, the body format, the `Docs:` line comparison, CI status and merge state.
   It also re-runs the reviewer's phases on the delta.
   The delta is the change to the branch's own added and removed lines since the review, so `create-pr`'s cherry-pick onto a newer base adds nothing to it.
   It confirms each pre-push finding's recorded fix is on the head, and re-emits any that is not.
4. **Full triage instead of a delta** runs when there is no usable pre-push record, when `create-pr` could not freshen the branch without a conflict, or when the delta is more than half the size of the reviewed change.

The first-push gate does not move.
The review runs no tests, and `create-pr` still runs the full suites once, after the review's fixes (PAD-18-001, PAD-18-008).
The fixes `build` makes after the review are not reviewed again before the push.
The post-push delta review covers them.
The pre-push findings and their resolutions are posted on the Pull Request once it opens, so a human can still read what the review found.

### Consequences

- Good, because a FAIL or IMPROVE the reviewer finds is fixed before the push, so it costs no fix commit and no extra CI run.
- Good, because each triage phase runs once per change: the reviewer's phases on the reviewed diff, and again only on lines that changed after it.
- Good, because the four recurring oversights are checked twice, by the author on a checklist and by the reviewer against the author's record.
- Good, because the post-push triage is short when nothing changed, so a Pull Request reaches execute sooner.
- Bad, because `build` takes longer before the push: one more subagent context and its review.
- Bad, because the pre-push record lives in the worktree, so a `pr-ship` run on another machine finds no record, runs the full triage, and the review happens twice.
- Bad, because a finding introduced by a pre-push fix is found only after the push, by the delta review.
- Neutral, because a Pull Request not opened by `build` still gets the full triage it got before.

## Validation

The PAD-07 requirements in `specs/parallel-development.yaml` carry the rules, each naming the skill step that implements it.
`.agents/skills/pr-triage/prepush-delta.sh` computes the delta and chooses between delta and full triage.
The decision is checked by the measurements in issues #4711 and #4712: post-push triage findings per Pull Request in the reviewer's phases should fall toward zero, and fix commits after open and open-to-merge time should fall too.

## Pros and Cons of the Options

### Keep the self-review

- Good, because it adds no work before the push.
- Bad, because the measured cost is in the post-push findings it leaves for the fresh agent: a median of six per Pull Request.
- Bad, because the author reviews with the same blind spots it wrote with.

### Run the whole pipeline before the push

- Good, because the Pull Request would open with every finding resolved.
- Bad, because CI status, merge state and the posted body do not exist before the push, so part of triage and all of verify would still run after it.
- Bad, because a local execute run would gate each fix with tests, then `create-pr` would run the full suites, and CI would run them again.

### Run the PR-independent triage phases in a fresh agent before the push

- Good, because it removes most post-push findings without running any phase twice.
- Good, because Pull Requests not from `build` keep the full triage unchanged.
- Bad, because the post-push triage depends on a local record, so it falls back to a full run when that record is missing.

## More Information

Generated spec requirements: `parallel-development.yaml` PAD-07-001 through PAD-07-009, and PAD-17-002.

Issue #4712 carries the measurements and the design questions.
Issue #4711 carries the self-check and its baseline tally.
