---
name: pr-ship
description: >
  End-to-end PR review pipeline. Detects the PR on the current branch, then
  runs pr-triage → pr-execute → pr-verify in sequence. Supports resume: if
  artifacts already exist from a prior run, skips forward to the right phase.
  No user prompts except the one deferred-ask pause in pr-execute. Precondition:
  an open PR must exist for the current branch (or provide an explicit PR number).
---

# Skill: PR Ship

## Purpose

Single entry point for the full triage → execute → verify pipeline. Run this
after pushing a branch with an open PR and let it complete. The only expected
pause is a `new-issue-ask` finding in execute — all other steps run unattended.

## Quick Start

```bash
# Run full pipeline for the current branch's PR
/pr-ship

# Run full pipeline for a specific PR number
/pr-ship 1234
```

## Preconditions

1. An open PR must exist for the current branch (or an explicit PR number is
   provided).
2. The working tree must be clean (`git status --porcelain` returns empty).
   Execute will commit fixes — a dirty worktree creates ambiguity about which
   changes are pre-existing. Stop and report if the worktree is dirty.
3. `.claude/pr-*.json` files must be gitignored (see below). Stop and warn if
   not, before writing any artifact.

## Gitignore Check

Before Phase 1, verify that `.claude/pr-*.json` is covered by `.gitignore`.

```bash
git check-ignore -q .claude/pr-1-triage.json 2>/dev/null
```

If the check fails (exit non-zero), add the pattern and note it:

```bash
echo '.claude/pr-*.json' >> .gitignore
```

Do not commit this change as part of pr-ship — leave it as an uncommitted
one-liner for the user to include in whatever commit makes sense, or as a
standalone commit if it would otherwise be lost.

## Resume Behavior

Before running any phase, check for existing artifacts:

| Condition | Action |
|---|---|
| No artifacts exist | Run full pipeline: triage → execute → verify |
| `pr-{N}-triage.json` exists, `pr-{N}-execute.json` absent | Skip triage; start at execute |
| Both artifacts exist | Skip triage and execute; start at verify |
| Verify ran and cleaned up (no artifacts) | Pipeline already completed; report last comment URL if available |

When resuming, print which phase is being skipped and why.

## Workflow

### Step 1 — Detect PR

```bash
gh pr view --json number,title,headRefName,state
```

Confirm state is `OPEN`. If no PR exists, stop:

```text
❌ No open PR found for branch <head_ref>.
Create a PR first, then re-run /pr-ship.
```

### Step 2 — Worktree Check

```bash
git status --porcelain
```

If output is non-empty, stop:

```text
❌ Working tree is not clean. Stash or commit your changes before running /pr-ship.
Uncommitted files: <list>
```

### Step 3 — Gitignore Check

As described in Preconditions above.

### Step 4 — Run pr-triage (or skip)

If resuming past triage: print `⏩ Skipping triage — artifact found at .claude/pr-{N}-triage.json`

Otherwise: invoke the `pr-triage` skill with the PR number.

If triage fails (no findings written, error reported): stop. Do not proceed
to execute with a missing or malformed artifact.

### Step 5 — Run pr-execute (or skip)

If resuming past execute: print `⏩ Skipping execute — artifact found at .claude/pr-{N}-execute.json`

Otherwise: invoke the `pr-execute` skill with the PR number.

If execute pauses for a `new-issue-ask` decision: wait for the user's response,
then continue. This is the only interactive pause in the pipeline.

If execute stops due to a blocking test failure (pre-existing with linked Bug
issue): report the blocked status and stop pr-ship. The user must resolve the
blocker before re-running.

### Step 6 — Run pr-verify

Invoke the `pr-verify` skill with the PR number.

### Step 7 — Final Report

After verify completes, print:

```text
PR #N — <title>
Overall verdict: READY-TO-MERGE / GAPS-FOUND / PENDING-CI

PR URL: https://github.com/CERTCC/Vultron/pull/N
```

If `GAPS-FOUND`: print which findings are unresolved and suggest re-running
`/pr-execute` after addressing them manually.

If `PENDING-CI`: print the PR URL and note that CI is still running. Re-run
`/pr-ship` (or `/pr-verify`) after CI completes to get the final verdict and
clean up artifacts.

## Failure Handling

If any step fails (unexpected error, not a structured stop):

- Stop immediately at that phase.
- Report which phase failed.
- Print artifact paths for any files written so far.
- Do NOT clean up artifacts — they preserve the work done up to the failure
  point for manual inspection or resume.

Artifacts are only cleaned up by `pr-verify` on a successful `READY-TO-MERGE`
or `PENDING-CI` verdict.
