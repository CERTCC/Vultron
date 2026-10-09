---
status: proposed
date: 2026-10-08
created: 2026-10-08
updated: 2026-10-09
revision: 2
deciders: Allen D. Householder
consulted: >-
  Claude Opus 5; Concern #4015, Issues #4357, #4358, #4359, Idea #1863;
  specs/parallel-development.yaml PAD-11, PAD-17, PAD-18
informed: []
stakeholder_type: [project-contributor]
---

# CI Is the Full-Suite Authority After a Pull Request's First Push

## Context and Problem Statement

Getting one Pull Request from `build` start to `READY-TO-MERGE` took 2–2.7 hours, and the Pull Request's size barely moved that number.
Two pipeline rules multiplied the number of local test runs: `pr-execute` re-ran the full suite on every Sync → Test → Push → Wait iteration, and `pr-verify` withheld `READY-TO-MERGE` from any branch that did not contain `main`'s latest commit.
Because `main` moves several times an hour during agent fan-out, the second rule made every merge to `main` invalidate every other ready Pull Request, restarting the loop.

The suite had already been made faster (#4277), and the pipeline was still slow.
That ruled out "the tests are too slow" as the problem and pointed at where the gates sit.
One measured fact reframes the question: CI on `pull_request` runs the *full* suite (`-m ""`) against the Pull Request merged into its base in about five minutes, which is faster than the local *unit-only* run on a 2-CPU slot (about seven minutes) and covers strictly more.
After the first push, a local full rerun largely repeats a CI run that is about to happen anyway, more slowly.

The question this record settles: after the first push, what is local testing *for*, and when is being behind `main` a real problem rather than an assumed one?

## Decision Drivers

- Unattended fan-out (Epic #3797) multiplies any per-Pull-Request cost by the number of agents, and more parallel slots make `main` move faster, which makes each Pull Request fall behind more often. The loop gets worse as throughput grows.
- The 2-CPU slot cap in `start-dev.sh` means faster hardware cannot buy a way out.
- Agents spend most of their turn budget polling, which is where "waiting for notification" stalls come from.
- Never merge on red is non-negotiable (`completeness-doctrine.md`). Any change here must reduce redundant checking without reducing the checking that actually catches things.
- No repository ruleset requires up-to-date branches: none of the three active rulesets carries a `required_status_checks` rule at all, so there is no `strict_required_status_checks_policy`. The "must contain the base tip" rule was ours, not GitHub's.

## Considered Options

- **Make the suite faster again** — keep every gate where it is and attack runtime.
- **Adopt GitHub's merge queue** — let GitHub serialize merges and test each candidate against the real post-merge tree.
- **Move the gates: one full local run before the first push, targeted runs after, and merge the base only when it matters** — treat CI as the full-suite authority once a Pull Request is pushed.

## Decision Outcome

Chosen option: **move the gates**.

Concretely: the full local unit and integration suites run exactly once, in `create-pr`, before an implementation Pull Request's first push (PAD-18-001, PAD-18-008).
After that push, a fix commit is gated by the linters plus a targeted test set derived from the branch diff, escalating to the full suite for shared test infrastructure and the integration-bearing layers (PAD-18-002, PAD-18-003).
The base branch is merged into a pushed Pull Request only when GitHub reports it `CONFLICTING` or when files the base changed overlap files the Pull Request changes (PAD-18-004).
`pr-verify` stops computing base-tip containment itself and defers to GitHub's reported merge state (PAD-18-005).

The reasoning is that a local run after the first push is worth its cost only when it catches something *before* CI would — that is, when it saves a CI round trip that counts against `pr-execute`'s four-iteration cap.
A targeted set does that for the fix shapes agents actually produce.
A full local rerun does not; it buys the same answer CI is already computing, later.

### Consequences

- Good, because the dominant cost driver is removed: a finished Pull Request no longer re-runs the suite and re-waits for CI every time `main` moves.
- Good, because the remaining local gate sits adjacent to the push it guards, which is the only position in which it is not redundant with CI.
- Good, because the cost becomes visible: PAD-18-006 and PAD-18-007 record suite runs, CI runs, merges from the base, and open-to-merge time, so this decision can be checked against data rather than believed.
- Bad, because a **semantic** conflict — two Pull Requests that change no file in common but are nonetheless incompatible — is no longer caught before merge. It surfaces as a red CI run on `main` afterwards.
- Bad, because local runs after the first push no longer prove the whole suite passes on the developer's machine. A broken fix outside the targeted set costs one CI round trip to discover.

This record exists primarily to hold the first "Bad" item.
Accepting a rare red `main` in exchange for hours per Pull Request is a deliberate trade, not an oversight.
A future reader who finds a red `main` caused by a semantic conflict should not "fix" it by restoring per-movement syncing and full local reruns — that re-creates the loop this decision removes, and it would not have caught the conflict anyway unless the two Pull Requests shared a file.
The correct escalation is a merge queue (see below).

## Validation

PAD-18-001 through PAD-18-008 in `specs/parallel-development.yaml` carry the per-change requirements, each with a `verification:` clause naming the skill phase or command that implements it.
The decision is validated empirically by PAD-18-007: `scripts/velocity.py` reports, per merged Pull Request and by week, the CI runs, failed CI runs, merges from the base branch, local suite runs, and open-to-merge time, plus failed CI runs on `main`.
The last field is the one that falsifies this decision — if failed CI runs on `main` rise materially while open-to-merge time falls, the trade was mispriced and the residual risk is larger than estimated.

## Pros and Cons of the Options

### Make the suite faster again

- Good, because it requires no change to pipeline rules, so nothing can regress in how carefully changes are checked.
- Bad, because it was already done. #4277 sized xdist to the slot; local unit runs fell to about seven minutes and end-to-end Pull Request time did not move.
- Bad, because the 2-CPU slot cap bounds what any further speedup can achieve, and the cost is multiplicative in the number of runs, not just their duration. Halving the runtime of a loop that runs ten times is worth less than not running it ten times.

### Adopt GitHub's merge queue

- Good, because it closes the semantic-conflict gap properly: each candidate is tested against the actual tree it will land on, serialized.
- Good, because it removes the up-to-date question from the agent's hands entirely.
- Neutral, because it does not by itself address post-first-push local reruns; the gate-placement question would still need answering.
- Bad, because it is a larger change to evaluate and adopt than this one, and it is unproven in this repository. It is tracked separately as Idea #1863.

This option is **deferred, not rejected.** It is the correct way to close the residual risk this decision accepts, and #1863 is the place that work belongs.

### Move the gates

- Good, because it targets the actual cost driver — the *number* of full runs and merge-from-base cycles — rather than their individual duration.
- Good, because it aligns our rules with the repository's real enforcement: GitHub never required up-to-date branches, so `BRANCH-BEHIND` was blocking on a rule nobody had set.
- Neutral, because it depends on new tooling (a targeted-tests command, #4357) to be auditable and repeatable rather than a judgment call per run.
- Bad, because it accepts the semantic-conflict risk described under Consequences.

## More Information

Concern #4015 carries the measurements: per-Pull-Request wall clock across six Epic #1936 children, and merge-from-`main` counts for five recent Pull Requests (#4326 took six merges from `main` after its work was finished).
The archived analysis is at `plan/history/2610/learning/CONCERN-4015.md`.

Implementation is split across #4357 (the targeted-tests and overlap command), #4358 (rewiring `pr-execute`, `pr-verify`, `work-epic-tasks`, `pr-ship`, `pr-triage`, and `build`), and #4359 (velocity reporting).

PAD-11-001 and PAD-11-002 originally required an automatic rebase plus force-push on conflict, which contradicted PAD-18-004's merge-based sync and `pr-execute/REFERENCE.md` § "Merge, do not rewrite".
Issue #4358 reconciled them with the maintainer's approval: a conflicted PR now has the base merged in and pushed normally, never rebased or force-pushed, and PAD-18-004 `extends` PAD-11-001 instead of declaring a `conflicts` relationship with PAD-11-002.

Generated spec requirements: `specs/parallel-development.yaml` PAD-18-001 through PAD-18-008.
