---
name: pr-ship
description: >
  End-to-end PR review pipeline. Detects the PR on the current branch, then
  runs pr-triage → pr-execute → pr-verify in sequence. Supports resume: if
  artifacts already exist from a prior run, skips forward to the right phase.
  No user prompts except the two gate pauses (defer-ask, inversion-halt) in pr-execute. Precondition:
  an open PR must exist for the current branch (or provide an explicit PR number).
---

# Skill: PR Ship

## Purpose

Single entry point for the full triage → execute → verify pipeline. Run this
after pushing a branch with an open PR and let it complete. The only expected
pauses are the two gates in execute — a `defer-ask` (may I defer this?) and an
`inversion-halt` (a premise was overturned) — all other steps run unattended.

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
| Both artifacts exist AND last verify verdict was not GAPS-FOUND / CONFLICTS-FOUND | Skip triage and execute; start at verify |
| Both artifacts exist AND last verify verdict was GAPS-FOUND | Delete `.claude/pr-{N}-execute.json`; re-run execute then verify |
| Both artifacts exist AND last verify verdict was CONFLICTS-FOUND | Delete `.claude/pr-{N}-execute.json`; re-run execute then verify — execute Phase 5 (CI Loop) owns the resolution |
| Both artifacts exist AND last verify verdict was PENDING-MERGE-CHECK | Skip triage and execute; re-run verify only (GitHub just needed time) |
| Both artifacts exist AND last verify verdict was PENDING-CI | Skip triage and execute; re-run verify only (CI timed out last run; try again now) |
| Verify ran and cleaned up (no artifacts) | Pipeline already completed; report last comment URL if available |

When resuming, print which phase is being skipped and why.

**Resume caveat**: an execute artifact can be stale about merge state even when
it is complete — the base branch may have moved since. That is fine and needs no
special handling here: verify re-checks mergeability live in its Phase 2, so a
resume that skips straight to verify still catches a newly-conflicted branch and
sends the pipeline back through execute.

## Execution Model

**Run all steps in a single uninterrupted pass.** Do not end your turn or wait
for user input between steps. When a sub-skill returns, proceed immediately to
the next step without pausing. The only valid mid-pipeline stops are the two
gate prompts inside pr-execute — `defer-ask` and `inversion-halt`. Every other
step transition is automatic.

## Workflow

### Step 1 — Detect PR

```bash
gh pr view --json number,title,headRefName,baseRefName,state,isDraft,mergeable,mergeStateStatus
```

Confirm state is `OPEN`. If no PR exists, stop:

```text
❌ No open PR found for branch <head_ref>.
Create a PR first, then re-run /pr-ship.
```

Print the base branch and merge state alongside the PR title. Do **not** stop on
a conflicting or draft PR — resolving conflicts is exactly what the pipeline is
for. `pr-execute` Phase 5 (CI Loop) syncs and resolves; `pr-verify` Phase 2 gates the
verdict. A conflicted PR at this point is a normal input, not an error.

If the PR is a draft carrying the `needs-rebase` label, note that `create-pr`
opened it that way because it could not freshen the branch, and that execute will
undraft it once the sync lands.

### Step 2 — Gitignore Check

As described in Preconditions above. **Run this before the worktree check** —
adding `.claude/pr-*.json` to `.gitignore` (when missing) creates a dirty file.
Commit the `.gitignore` change immediately if it was written:

```bash
git add .gitignore && git commit -m "chore: gitignore pr-*.json session artifacts"
```

### Step 3 — Worktree Check

```bash
git status --porcelain
```

If output is non-empty, stop:

```text
❌ Working tree is not clean. Stash or commit your changes before running /pr-ship.
Uncommitted files: <list>
```

### Step 4 — Run pr-triage (or skip)

If resuming past triage: print `⏩ Skipping triage — artifact found at .claude/pr-{N}-triage.json`

Otherwise: invoke the `pr-triage` skill with the PR number.

If triage fails (no findings written, error reported): stop. Do not proceed
to execute with a missing or malformed artifact.

When pr-triage returns successfully, proceed immediately to Step 5.

### Step 5 — Run pr-execute (or skip)

If resuming past execute: print `⏩ Skipping execute — artifact found at .claude/pr-{N}-execute.json`

Otherwise: invoke the `pr-execute` skill with the PR number.

If execute pauses for a `defer-ask` or `inversion-halt` decision: wait for the
user's response, then continue. On silence, execute applies its own rule
(fix-now for a defer-ask; halt the PR for an inversion-halt). These are the only
interactive pauses in the pipeline.

If execute stops due to a blocking test failure (pre-existing with linked Bug
issue): report the blocked status and stop pr-ship. The user must resolve the
blocker before re-running.

If execute stops because a merge conflict could not be resolved safely (Phase 5, CI Loop):
report the conflicting paths and stop. Do not skip ahead to verify — an
unresolved conflict is a hard stop, and running verify would only restate it.

When pr-execute returns successfully, proceed immediately to Step 6.

### Step 6 — Run pr-verify

Invoke the `pr-verify` skill with the PR number.

When pr-verify returns, proceed immediately to Step 7.

### Step 7 — Final Report

After verify completes, print:

```text
PR #N — <title>
Overall verdict: READY-TO-MERGE / GAPS-FOUND / CONFLICTS-FOUND / PENDING-CI / PENDING-MERGE-CHECK
Merge state:     MERGEABLE (CLEAN) / CONFLICTING (DIRTY) / BEHIND / DRAFT / UNKNOWN — base <base_ref>
CI status:       passing / failing / pending

PR URL: https://github.com/CERTCC/Vultron/pull/N
```

**Report verify's verdict verbatim — never upgrade it.** In particular, never
print `READY-TO-MERGE` unless verify itself emitted it. Confirmed findings and
green CI are not sufficient: if verify reported `CONFLICTS-FOUND`, the PR cannot
merge and the final report must say so. Always include the merge-state line, even
on the happy path.

If any findings in the execute artifact have `outcome: skipped` and a
`skip_reason` referencing a flaky-test issue, append a warning block:

```text
⚠ Flaky test skips:
  - <node_id or job_name> → #<issue_number> (blocked N PRs to date)
```

Fetch the blocked-PR count by counting `## Blocked PRs` list entries in the
issue body: `gh issue view <N> --json body`. This keeps recurring failures
visible at merge time.

If `GAPS-FOUND`: print which findings are unresolved. To retry:

1. Address the gaps manually (or re-run `/pr-execute` after deleting
   `.claude/pr-{N}-execute.json` to force re-execution).
2. Then re-run `/pr-ship` — the resume logic will detect the missing execute
   artifact and re-run execute before verify.

If `CONFLICTS-FOUND`: print the conflicting paths from verify's comment, then
delete `.claude/pr-{N}-execute.json` and re-run `/pr-ship` — execute Phase 5 (CI Loop) will
sync and resolve. If a re-run lands on the same conflict twice, stop and hand it
to the user; the resolution needs judgment the pipeline does not have.

If `PENDING-CI`: CI timed out during verify's 10-minute wait (or a race
condition re-triggered CI after execute finished). Print the PR URL and note
that CI is still running. Artifacts are preserved. Re-run `/pr-ship` (or
`/pr-verify`) after CI completes to get the final verdict.

If `PENDING-MERGE-CHECK`: GitHub had not finished computing mergeability. Wait a
moment and re-run `/pr-verify` — no execute re-run is needed.

## Failure Handling

If any step fails (unexpected error, not a structured stop):

- Stop immediately at that phase.
- Report which phase failed.
- Print artifact paths for any files written so far.
- Do NOT clean up artifacts — they preserve the work done up to the failure
  point for manual inspection or resume.

Artifacts are only cleaned up by `pr-verify` on a `READY-TO-MERGE` verdict.

## Where Merge Conflicts Are Handled

Conflicts are checked three times, deliberately, because the answer changes as
the pipeline runs:

| Phase | Check | Role |
|---|---|---|
| `pr-triage` Phase 12 | Read merge state, emit a FAIL finding | Early warning; recorded in `pr_metadata` |
| `pr-execute` Phase 5 (CI Loop) | Sync with base, resolve conflicts, re-verify | The only phase that **fixes** conflicts. Runs after all other mutation so execute's own fixes are included, and before the test suite so tests see the merged tree |
| `pr-verify` Phase 2 | Live re-check as a hard gate | The **authoritative** answer. Blocks `READY-TO-MERGE` |

Execute resolves rather than verify because verify is a read-only reporter by
design. Verify runs last, so it is the only phase whose reading is still true at
verdict time — but that also makes it the wrong place to start mutating. When
verify finds a conflict, the pipeline loops back through execute.
