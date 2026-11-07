---
title: PAD-18-025's verification forbids the worktree its own named skill step needs
type: learning
timestamp: 2026-11-07T00:40:00Z
source: ISSUE-5950
signal: spec-contradiction
---

## Trigger

You are building a guard for a requirement and the obvious scan is the one its
`verification:` describes, but the scan fails on a file the verification names
as compliant. You are about to either weaken the guard or declare an exemption
the requirement says cannot exist.

## Claim

PAD-18-025's statement and its `verification:` scope the same prohibition to
different things, and only the statement is right. The question `learn` must
settle is which one the verification should be rewritten to match.

- **Statement**: "A conflict check of a Pull Request against its base MUST use
  a trial merge that moves no branch and writes no worktree." The prohibition
  is on the *conflict check*.
- **Verification**: "`sync-decision.sh` and `work-epic-tasks` step 4 find a
  conflict with `git merge-tree`, and neither runs `git worktree add`." The
  prohibition is on *the whole of step 4*.

`work-epic-tasks` step 4 does run `git worktree add`, on its first line, and
has to: it checks out the pushed head to run the checks from when the PR's own
worktree is gone. That checkout holds no merge and runs no test, so the
statement is satisfied and the verification's second clause is false of a file
it names. An inspector who follows the verification literally fails a
conformant skill.

## Evidence

Issue #5950 removed the local scratch-merge test gate. Nine markers went with
it — four on PAD-18-024, five on PAD-18-025 — replaced by a guard over "a
checkout the agent does not commit" and the test run in one
(`test/metadata/test_gate_ceiling.py`). The guard had to carry
`work-epic-tasks` step 4's `git worktree add` as a declared permanent
exemption, citing PAD-18-009 — a set the verification's wording says should be
empty. PR #6096. The run's instructions barred any edit to PAD-18-024 or
PAD-18-025, so the mismatch was left in place.

## How to apply

Scope the verification to the conflict check, not to the step: what must hold
is that the command answering "does this conflict?" is `git merge-tree`, and
that no checkout an agent makes is used to run tests on a merge. The second
half is PAD-18-024's territory, so PAD-18-025's verification can name the
trial-merge call sites alone. Before relying on that split, read what the
PAD-18-024 guard actually asserts: pinning *which* files build such a checkout
left the test run inside the one declared exemption unchecked, and the gate
stayed green on a block that merged the base and ran `pytest` in it. Closing
that took a second arm, over each block that builds a checkout, plus one over
the console-script modules, because the runner being replaced built its
worktree from argv items rather than from a written command. Any requirement
that forbids an *act* should say which call site performs it, because a
whole-file-or-whole-step prohibition picks up legitimate neighbours — and a
guard for one should assert the act, not a precondition of it.
