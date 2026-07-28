---
name: pr-verify
description: >
  Verification phase of the PR review pipeline. Reads .claude/pr-{number}-execute.json,
  spot-checks each claimed fix against HEAD (not just the commit diff), validates CI
  and test suite, and posts a per-finding verdict comment on the PR. Cleans up both
  artifact files as its final step. Makes NO code changes. Use after /pr-execute,
  or as the third step of /pr-ship.
---

# Skill: PR Verify

## Purpose

Verify closes the loop. It checks what execute *claimed* to do against what
actually exists at HEAD, posts a verdict, and cleans up the session artifacts.
It does not fix anything — if gaps are found, they are flagged for the user to
re-run `/pr-execute` or fix manually.

## Quick Start

```bash
# Verify the current branch's open PR
/pr-verify

# Verify a specific PR
/pr-verify 1234
```

## Prerequisites

`.claude/pr-{number}-execute.json` must exist. If absent, stop immediately:

```text
❌ No execute artifact found for PR #N.
Run /pr-execute first (or /pr-ship to run the full pipeline).
```

Also requires `.claude/pr-{number}-triage.json` for finding descriptions. If
the triage artifact is missing but the execute artifact exists, proceed using
only the execute artifact data — but note the missing triage artifact in the
comment.

## Workflow

### Phase 1 — Load Artifacts

1. Detect PR number (current branch or explicit argument).
2. Read `.claude/pr-{number}-execute.json`; validate `schema_version == "1.0"`.
3. Read `.claude/pr-{number}-triage.json` if present.
4. **Integrity check**: verify `len(execute.results) == len(triage.findings)`.
   If counts diverge, flag `INCOMPLETE-EXECUTE` and **continue to Phase 2**
   (CI status must still be checked). After Phase 2, skip Phases 3–4 and go
   directly to Phase 5 with an overall verdict of `GAPS-FOUND`.

### Phase 2 — CI and Test Suite Check

1. `gh pr checks <number>` — fetch current CI status.
2. If `execute.integration_tests_run == true`: confirm the integration test CI
   job is green, not just unit tests.
3. If CI is still failing after execute's pushes: mark all findings as
   `UNVERIFIED-CI-FAILING` and set overall verdict to `GAPS-FOUND` — the code
   changes may be correct but CI must be green before the PR can be considered
   ready.
4. If CI is pending: note it; proceed with spot-checks but mark overall verdict
   as `PENDING-CI`.

### Phase 3 — Spot-Verify FAIL Findings

For each finding with `severity: FAIL` and `outcome: fixed`:

1. Confirm `commit_ref` exists on the PR branch:
   `git log --oneline <commit_ref>` must not error.
2. **Check the file at HEAD** (not just the commit diff) — verify the corrected
   state is present in the current working tree. A fix that was applied and
   then reverted shows a clean diff at the commit ref but a broken HEAD.
   - If `file` and `line` are recorded in the triage finding: read the file at
     that location and confirm the fix is present.
   - If no file/line: diff the relevant section against the commit ref to
     confirm the change persists.
3. Assign verdict:
   - `CONFIRMED` — fix present at HEAD, commit ref valid
   - `UNRESOLVED` — commit ref exists but HEAD does not show the fix
   - `MISSING-COMMIT` — commit ref not found on branch

### Phase 4 — Spot-Verify IMPROVE Findings

Lighter check:

1. Confirm `commit_ref` exists on the branch.
2. Check the file at HEAD for the improvement (same HEAD-check as Phase 3).
3. Assign `CONFIRMED` or `UNRESOLVED`.

For findings with `outcome: filed`, `skipped`, or `deferred-ask`: assign
`NOTED` — no code check needed, just confirm the issue number is real:
`gh issue view <issue_number> --json number,state` must return an open issue.

### Phase 5 — Render Verdict and Post Comment

1. Build the per-finding verdict table.
2. Determine overall verdict:
   - `READY-TO-MERGE` — all FAIL findings `CONFIRMED`, CI green,
     no `INCOMPLETE-EXECUTE`, no `UNVERIFIED-CI-FAILING`
   - `GAPS-FOUND` — any FAIL finding is `UNRESOLVED` or `MISSING-COMMIT`, or
     `INCOMPLETE-EXECUTE` was flagged, or any finding is `UNVERIFIED-CI-FAILING`
   - `PENDING-CI` — all findings confirmed but CI not yet complete (pending)
3. If `deferred-ask` items exist: list them explicitly for user decision.
4. Post comment: `gh pr review <number> --comment --body "<verdict>"`

See [REFERENCE.md](REFERENCE.md) § "Verify Comment Format" for the template.

### Phase 6 — Cleanup

Only runs if overall verdict is `READY-TO-MERGE` or `PENDING-CI` (i.e., no
gaps that require re-running execute).

1. Delete `.claude/pr-{number}-triage.json`
2. Delete `.claude/pr-{number}-execute.json`
3. Print:

   ```text
   Artifacts cleaned up.
   PR #N is READY-TO-MERGE / PENDING-CI.
   ```

If verdict is `GAPS-FOUND`: do NOT delete artifacts. The user or a retry of
`/pr-execute` will need them.

## This Skill Does Not Fix

If `UNRESOLVED` or `MISSING-COMMIT` findings appear, verify posts the gap and
stops. The user re-runs `/pr-execute` or fixes manually. Verify never mutates
files, never commits, never creates issues.
