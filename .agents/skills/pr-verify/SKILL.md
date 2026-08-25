---
name: pr-verify
description: >
  Verification phase of the PR review pipeline. Reads .claude/pr-{number}-execute.json,
  re-checks mergeability as a hard gate, spot-checks each claimed fix against HEAD
  (not just the commit diff), validates CI and test suite, and posts a per-finding
  verdict comment on the PR. Cleans up both artifact files as its final step. Makes
  NO code changes. Use after /pr-execute, or as the third step of /pr-ship.
---

# Skill: PR Verify

## Purpose

Verify closes the loop. It checks what execute *claimed* to do against what
actually exists at HEAD, posts a verdict, and cleans up the session artifacts.
It does not fix anything — if gaps are found, they are flagged for the user to
re-run `/pr-execute` or fix manually.

Verify is also the **last and authoritative mergeability check**. Because it runs
after every mutation in the pipeline, its merge-state reading is the only one
that can be trusted at verdict time. `READY-TO-MERGE` is impossible without a
live `MERGEABLE` result — a PR that cannot merge is never ready to merge,
regardless of how many findings were confirmed.

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
   (merge state and CI must still be checked). After Phase 3, skip Phases 4–5
   and go directly to Phase 6 with an overall verdict of `GAPS-FOUND`.
5. **Merge-state block check**: if `execute.merge_state` is absent, or
   `merge_state.synced` is not `true`, flag `UNSYNCED-EXECUTE`. Continue to
   Phase 2 — the live check there is what decides the verdict — but this flag
   alone blocks `READY-TO-MERGE`, because it means execute never confirmed the
   branch could merge.

### Phase 2 — Merge State Gate

This is a hard gate and runs before the per-finding spot checks: a conflicted PR
cannot be ready to merge no matter what those checks find.

1. Re-check merge state live — never reuse the value from either artifact:

   ```bash
   bash .agents/skills/shared/merge-state.sh <number>
   ```

2. Map the result:

   | Exit | `mergeable` | Flag | Effect on overall verdict |
   |---|---|---|---|
   | `0` | `MERGEABLE` | none | No block from this phase |
   | `1` | `CONFLICTING` | `MERGE-CONFLICT` | Forces `CONFLICTS-FOUND` |
   | `2` | `UNKNOWN` | `MERGE-STATE-UNKNOWN` | Forces `PENDING-MERGE-CHECK` |

3. Check `merge_state_status` independently of `mergeable`:
   - `DIRTY` → flag `MERGE-CONFLICT` even if `mergeable` says `MERGEABLE`
   - `BEHIND` → flag `BRANCH-BEHIND`; blocks `READY-TO-MERGE`
   - `DRAFT` → flag `PR-IS-DRAFT`; blocks `READY-TO-MERGE`. Report whether the
     `needs-rebase` label is still attached.
   - `BLOCKED` → note it in the comment (missing required review, etc.). This
     does *not* block the verdict — it is a repo policy state a human resolves,
     not a defect in the PR.

4. If `MERGE-CONFLICT` is flagged, list the conflicting paths as evidence:

   ```bash
   git fetch origin <base_ref>
   git merge-tree --write-tree HEAD origin/<base_ref> 2>&1 | grep -i "^CONFLICT" || true
   ```

   Verify does not resolve them. Report and stop after posting the comment.

5. If `execute.merge_state.conflicts_resolved` is non-empty, confirm no markers
   survived the resolution — a resolved-then-recommitted marker passes CI lint on
   some file types and would otherwise ship:

   ```bash
   git grep -nE '^(<<<<<<<|>>>>>>>) ' -- . || echo "clean"
   ```

   Any hit is a `MERGE-CONFLICT` flag regardless of what GitHub reports.

   > Match only the `<<<<<<<` and `>>>>>>>` markers, each followed by a space.
   > Do **not** grep for `=======` — a bare row of equals signs is a valid
   > markdown setext heading underline, and this repo is docs-heavy.

### Phase 3 — CI and Test Suite Check

1. `gh pr checks <number>` — fetch current CI status.
2. If `execute.integration_tests_run == true`: confirm the integration test CI
   job is green, not just unit tests.
3. If CI is still failing after execute's pushes: mark all findings as
   `UNVERIFIED-CI-FAILING` and set overall verdict to `GAPS-FOUND` — the code
   changes may be correct but CI must be green before the PR can be considered
   ready.
4. If CI is pending: wait for completion before proceeding:

   ```bash
   bash .agents/skills/shared/wait-for-ci.sh <number>
   ```

   | Exit | Meaning | Action |
   |---|---|---|
   | `0` | All checks passed | Proceed with CI green |
   | `1` | One or more checks failed | Mark all findings `UNVERIFIED-CI-FAILING`; set verdict to `GAPS-FOUND` |
   | `2` | Timed out (10 min) | Note it; proceed with spot-checks; set overall verdict to `PENDING-CI` |

   A `PENDING-CI` verdict here is a fallback for a genuine race condition (CI
   re-triggered after execute finished, or unusually slow CI). Under normal
   operation execute already waited for CI, so this path should be rare.

### Phase 4 — Spot-Verify FAIL Findings

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

### Phase 5 — Spot-Verify IMPROVE Findings

Lighter check:

1. Confirm `commit_ref` exists on the branch.
2. Check the file at HEAD for the improvement (same HEAD-check as Phase 4).
3. Assign `CONFIRMED` or `UNRESOLVED`.

For findings with `outcome: filed`, `skipped`, or `deferred-ask`: assign
`NOTED` — no code check needed, just confirm the issue number is real:
`gh issue view <issue_number> --json number,state` must return an open issue.

### Phase 6 — Render Verdict and Post Comment

1. Build the per-finding verdict table.
2. Determine the overall verdict. Evaluate the blocking conditions **in this
   order** and take the first that matches:

   | # | Condition | Verdict |
   |---|---|---|
   | 1 | `MERGE-CONFLICT` flagged | `CONFLICTS-FOUND` |
   | 2 | Any FAIL `UNRESOLVED`/`MISSING-COMMIT`, or `INCOMPLETE-EXECUTE`, or `UNVERIFIED-CI-FAILING` | `GAPS-FOUND` |
   | 3 | `MERGE-STATE-UNKNOWN` flagged | `PENDING-MERGE-CHECK` |
   | 4 | CI still pending | `PENDING-CI` |
   | 5 | All FAIL findings `CONFIRMED`, CI green, `mergeable == MERGEABLE`, and no `UNSYNCED-EXECUTE` / `BRANCH-BEHIND` / `PR-IS-DRAFT` flag | `READY-TO-MERGE` |
   | 6 | Otherwise | `GAPS-FOUND` (name the flag that blocked it) |

   `READY-TO-MERGE` requires a live `MERGEABLE`. There is no path to it via
   confirmed findings alone — row 5 is the only rule that emits it, and it is
   reachable only when every merge-state flag is clear.

3. Always print the merge-state line in the comment, including on the happy path.
   A verdict that does not state its merge state is the bug this gate exists to
   prevent.
4. If `deferred-ask` items exist: list them explicitly for user decision.
5. Post comment: `gh pr review <number> --comment --body "<verdict>"`

See [REFERENCE.md](REFERENCE.md) § "Verify Comment Format" for the template.

### Phase 7 — Cleanup

Only runs if overall verdict is `READY-TO-MERGE`.

Do **not** clean up on `PENDING-CI`, `CONFLICTS-FOUND`, or `PENDING-MERGE-CHECK`
— all three may need a follow-up pass, which needs the artifacts.

1. Delete `.claude/pr-{number}-triage.json`
2. Delete `.claude/pr-{number}-execute.json`
3. Print:

   ```text
   Artifacts cleaned up.
   PR #N is READY-TO-MERGE.
   ```

If verdict is `PENDING-CI`, `GAPS-FOUND`, `CONFLICTS-FOUND`, or
`PENDING-MERGE-CHECK`: do NOT delete artifacts. The user or a retry of
`/pr-verify` or `/pr-execute` will need them.

## This Skill Does Not Fix

If `UNRESOLVED` or `MISSING-COMMIT` findings appear, verify posts the gap and
stops. The user re-runs `/pr-execute` or fixes manually. Verify never mutates
files, never commits, never creates issues.

This includes merge conflicts. Verify **detects** conflicts; `pr-execute` Phase 4
**resolves** them. Verify must not run `sync-with-main.sh`, `git merge`, or any
other mutation — its job is to be the honest reporter that the pipeline's earlier
phases cannot be, because they run before the last thing that can change.
