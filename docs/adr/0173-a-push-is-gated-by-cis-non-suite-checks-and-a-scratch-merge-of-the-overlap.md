---
status: accepted-provisional
date: 2026-11-02
created: 2026-11-02
updated: 2026-11-02
revision: 1
deciders: Allen D. Householder
consulted: >-
  Claude Opus 5.5; ADR-0126; ADR-0138; ADR-0143; specs/parallel-development.yaml
  PAD-18; issue #5580
informed: []
stakeholder_type: [project-contributor]
partially_supersedes:
  - 0138-a-pushed-pull-request-is-merged-locally-only-on-conflict.md
partially_superseded_by:
  - 0179-a-local-check-runs-only-when-it-answers-before-a-required-ci-gate.md
---

# A Push Is Gated by CI's Non-Suite Checks and a Scratch Merge of the Overlap

## Context and Problem Statement

[ADR-0126](0126-ci-is-the-full-suite-authority-after-the-first-push.md) made CI the full-suite authority after a Pull Request's first push, and [ADR-0138](0138-a-pushed-pull-request-is-merged-locally-only-on-conflict.md) let GitHub and CI handle every clean merge with the base.
Both cut local runs that repeated what CI was about to do.

Neither covered the checks CI runs that need no suite at all.
About one Pull Request in seven still spent a push, a CI wait and a review round on something CI found without running a suite.
An audit of 35 such fixes since 2026-09-01 traced each one to a cause.
Pre-commit hooks see only staged files.
Some guards are pytest files that the targeted set leaves out, and a Pull Request that changes no Python runs no pytest at all.
The site-publication and decision-record epoch checks run only in CI.
And the base moved after the local run: new ratchets and conflicting content arrived from `main` while the branch was out for review.

ADR-0138 held that a clean merge contains no line an agent wrote, so the only useful test of it is CI at merge time.
The audit found fixes where the base and the branch had each changed the same file without a conflict, and a fix push that passed on the branch alone failed in CI on the merged tree.

The question this record settles: what must a push be gated by locally so that CI rounds are not spent on findings a local step could have made, without bringing back the suite runs ADR-0126 and ADR-0138 removed?

## Decision Drivers

- A CI round costs a push, a wait of about seven minutes, and a review of the fix; a local check that finds the same failure costs seconds to a few minutes.
- The local gate must not drift from CI: a list of checks kept by hand falls behind the workflows.
- ADR-0126's and ADR-0138's savings must hold: no full local suite after the first push, and no local merge into the branch without a conflict.
- Overlap with the base is common during parallel fan-out, so its local cost must stay bounded.

## Considered Options

- Keep the gates as they are, and accept the CI rounds.
- Add more pre-commit hooks.
- Mirror CI's non-suite pull-request checks locally before every push, and test the overlap on a scratch merge.
- Run the full suite locally on the merged tree before every push.

## Decision Outcome

Chosen option: **mirror CI's non-suite pull-request checks locally before every push, and test the overlap on a scratch merge**.

Before every push of a Pull Request branch, the first push and each later one, the agent runs every check a pull-request CI run would run on the branch diff, except the full suites and the container demos.
That includes the limit-enforcing guard tests behind the audited failures, whatever the Pull Request's type.
Every pull-request CI step is either in that local mirror or excluded from it with a recorded reason, and a test fails on a step that is neither, so the mirror cannot fall behind the workflows.

After the first push, when the base has changed a file the Pull Request also changes and the two do not conflict, the agent merges the base into a scratch checkout, never into the branch, and runs there the tests for the shared files alone.
This partly supersedes ADR-0138's ruling that a clean merge is never tested locally.
The rest of ADR-0138 stands: the branch is merged locally only on a conflict, and the merger still updates an overlapping Pull Request on GitHub and waits for CI before merging it.

The reasoning is that a local check is worth its cost when it finds, before the push, what CI would find after it.
CI's non-suite checks are cheap, deterministic, and the most common cause of an extra CI round.
A clean overlap is where the base can break a fix that passes alone.
Testing only the shared files, as after a conflict, keeps that run small; testing the whole branch diff there would bring back the full-suite escalations ADR-0138 removed.

### Consequences

- Good, because a mechanical failure is found before the push that would have sent it to CI, whatever the Pull Request's type.
- Good, because the mirror and the workflows cannot drift apart unnoticed.
- Good, because an overlap with the base is tested before a fix push, on the files the base and the branch both changed.
- Bad, because every push waits for the mirror: about two minutes on a Python change, plus about six when a docs input changes and the site is built.
- Bad, because a check whose tool is missing locally blocks the push until it is satisfied another way and the skip is recorded.
- Neutral, because a semantic conflict between files the two sides do not share is still caught only by CI, as ADR-0126 accepted.

## Validation

PAD-18-021 to PAD-18-025 in `specs/parallel-development.yaml` carry the requirements, each with a `verification:` clause.
The decision is checked by the PAD-18-007 data: failed CI runs per Pull Request, and fix commits labelled as CI fixes, should fall, while local suite runs per Pull Request should not rise.

## Pros and Cons of the Options

### Keep the gates as they are

- Good, because nothing changes.
- Bad, because about one Pull Request in seven keeps paying an extra CI round for a finding a local step could make.

### Add more pre-commit hooks

- Good, because hooks run without anyone remembering to.
- Bad, because a hook sees only the staged files of one commit, the cause of a share of the audited failures.
- Bad, because a hook cannot see the base moving after the commit.

### Mirror CI's non-suite checks, and test the overlap on a scratch merge

- Good, because it covers every audited cause at a bounded cost.
- Bad, because the mirror adds wall-clock time to each push.

### Run the full suite on the merged tree before every push

- Good, because it finds nearly everything CI would.
- Bad, because it is the local repeat of CI's suite run that ADR-0126 and ADR-0138 removed, at 9 to 18 minutes a push on a two-CPU slot.

## More Information

The audit table of the 35 fixes is in the pull request that closes issue #5580.
