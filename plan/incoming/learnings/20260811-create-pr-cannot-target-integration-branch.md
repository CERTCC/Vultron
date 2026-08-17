---
title: create-pr cannot finalize a PR that targets an integration branch
type: learning
timestamp: 2026-08-11
source: ISSUE-2134
signal: tooling-issue
---

## What happened

While finalizing PR #2168 (fix for #2134), the `create-pr` skill could not be
used as written. The skill:

- freshens the task branch by cherry-picking onto a fresh `origin/main`
  (`freshen-branch.sh`), and
- hardcodes `gh pr create ... --base main`.

PR #2168 targets the integration branch `fix/demo-ci`, not `main`. Running
`create-pr` verbatim would have:

1. cherry-picked the branch off `origin/main`, tearing it away from the ~75-file
   accumulated `fix/demo-ci` work and producing a large spurious conflict, and
2. attempted `gh pr create --base main`, colliding with the already-open PR
   #2168.

## Workaround used

Bypassed `create-pr`: verified the branch was already current with
`origin/fix/demo-ci`, committed, and pushed directly to the existing branch
(which updates the open PR in place). Ran the skill's validation intent manually
(black / flake8 / mypy / pyright + full unit suite + affected integration
suite) before pushing.

## Suggested fix

`create-pr` should accept an optional `base` parameter (default `main`) and
thread it through both `freshen-branch.sh` (freshen onto `origin/<base>`) and
`gh pr create --base <base>`. It should also detect an already-open PR for the
current head and push-to-update rather than attempting a duplicate
`gh pr create`.

**Promoted**: 2026-08-17 — captured in AGENTS.md pitfall: create-pr cannot target integration branches.
Docs PR: TBD.
