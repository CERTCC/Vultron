---
name: pr-execute
description: >
  Execution phase of the PR review pipeline. Reads .claude/pr-{number}-triage.json,
  applies all FAIL/IMPROVE fixes inline, remediates CI failures, syncs the branch
  with its base and resolves merge conflicts, files GitHub issues for out-of-scope
  findings, resolves review thread comments, and writes
  .claude/pr-{number}-execute.json. Use after /pr-triage, or as the second step
  of /pr-ship.
---

# Skill: PR Execute

## Purpose

Execute consumes the closed finding list from `pr-triage` and processes it in
one batch pass. No new discovery happens here. The finding set is fixed at the
start; execute either resolves each item or records why it was skipped.

Execute's exit criterion is **CI green**: it does not hand off to pr-verify until
the branch is synced, tests pass locally, and all CI checks have completed
successfully (or the 4-iteration cap is reached).

**One exception to "no new discovery"**: the CI loop (Phase 5) re-reads CI state
and merge state from live sources rather than trusting triage's snapshots. CI
failures and conflicts are moving targets — execute's own fixes can create them,
and other PRs can land on the base branch mid-run.

## Quick Start

```bash
# Execute against the current branch's open PR
/pr-execute

# Execute against a specific PR number
/pr-execute 1234
```

## Prerequisites

`.claude/pr-{number}-triage.json` must exist. If absent, stop immediately:

```text
❌ No triage artifact found for PR #N.
Run /pr-triage first (or /pr-ship to run the full pipeline).
```

## Workflow

### Phase 1 — Load Triage Artifact

1. Detect PR number (current branch or explicit argument).
2. Read `.claude/pr-{number}-triage.json`.
3. Validate `schema_version == "1.0"`. If mismatch, stop and report.
4. Extract `pr_metadata.domains` and invoke `deepen-context` with those hints
   to load the same domain context that triage used.
5. Check `pr_metadata.needs_integration_tests` — determines test scope in Phase 5.
6. Note `pr_metadata.base_ref` — Phase 5 syncs against this branch, not
   necessarily `main`.

### Phase 2 — Apply fix-now Fixes

For each finding where `decision_outcome` is `fix-now` or `fix-now-expand-scope`
and `severity` is `FAIL` or `IMPROVE`:

> Note: findings with `severity: NEW-ISSUE` are handled exclusively in Phase 3,
> regardless of their `decision_outcome`. Do not process them here.

1. Apply the fix (edit files as needed).
2. Do not commit yet — batch all fixes, then commit once at the end of this phase.
3. After all fixes are applied: `uv run black <changed files>` then commit:

   ```text
   fix(pr-execute): address <N> findings from triage

   <bullet per finding: phase-name — short description>

   Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
   ```

4. Record `commit_ref` (short SHA) for each finding addressed in this commit.

**Do not push yet.** All pushes happen inside the CI loop (Phase 5) so that
every push includes the sync commit and passes local tests first.

### Phase 3 — Handle NEW-ISSUE Findings

For each finding with `severity: NEW-ISSUE`:

**`new-issue-ask`** (non-trivial, distant cousin):

1. File a GitHub issue via `manage-github-issue` capturing the finding description.
2. Add the issue to Project #24: `bash .agents/skills/shared/add-to-project.sh <N>`.
3. Record the finding as `outcome: deferred-ask` with the new `issue_number`.
4. Do NOT fold the work into this PR yet — the deferred-ask items are surfaced
   in the execute comment and again in pr-verify for the user to decide.

**`new-issue-no-ask`** (requires separate design effort):

1. File a GitHub issue via `manage-github-issue`.
2. Add to Project #24.
3. Record as `outcome: filed` with `issue_number`.

### Phase 4 — Resolve Review Thread Comments

For each unresolved review comment on the PR (fetched via
`gh api repos/CERTCC/Vultron/pulls/<number>/comments`):

Match each comment to the finding(s) it corresponds to. Then per
[REFERENCE.md](REFERENCE.md) § "Comment Resolution":

- ✅ Fully addressed → resolve with commit reference
- ⚠️ Partially addressed → reply explaining why; leave for reviewer to close
- ❌ Cannot address → reply explaining why; reference any filed issue

Do not mark a comment resolved unless the code actually addresses it.

### Phase 5 — CI Loop

This phase owns syncing, testing, pushing, and CI wait. It loops until CI is
green or the cap is reached. **Maximum 4 iterations.** One iteration = one full
Sync → Test → Push → Wait cycle.

#### Step 1 — Apply CI fixes

*Iteration 1*: apply any CI-failure findings from the triage artifact (triage
Phase 11). Fix lint/type/format failures directly. For test failures, apply Test
Failure Rules from [REFERENCE.md](REFERENCE.md).

*Subsequent iterations*: apply fixes for failures found in the previous
iteration's CI wait result. Fetch logs first:

```bash
gh run list --branch <head_ref> --limit 1
gh run view <run-id> --log-failed
```

**Repeated-failure rule**: if the same CI failure appears in two consecutive
iterations:

1. Apply Test Failure Rules from [REFERENCE.md](REFERENCE.md) to determine
   whether it is pre-existing.
2. Before filing or deferring: assess whether a fix is straightforward and
   context is in hand. If yes, fix it now — a pre-existing failure you can
   resolve is still a failure worth resolving.
3. Only file a bug issue and record `outcome: skipped` if the fix is genuinely
   non-trivial or requires design work outside this PR's scope.

Commit CI fixes separately from Phase 2 fixes:

```text
fix(ci): resolve CI failures — <summary>

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
```

Record `commit_ref` for each CI finding addressed.

#### Step 2 — Sync with base

```bash
bash .agents/skills/shared/sync-with-main.sh <base_ref>
```

| Exit | Meaning | Action |
|---|---|---|
| `0` | Already current, or merged cleanly | Continue to Step 3 |
| `1` | Conflicts left in the worktree | Resolve them (see below) |
| `2` | Unexpected error (dirty tree, merge in progress) | Stop and report; do not force anything |

Resolve each conflicted path per [REFERENCE.md](REFERENCE.md) § "Conflict
Resolution Rules". Read both sides before editing. Never resolve by
wholesale `--ours`/`--theirs` on a file you have not read.

```bash
uv run black <changed files>
git add <resolved files>
git commit --no-edit
```

Verify no markers survived:

```bash
git grep -nE '^(<<<<<<<|>>>>>>>) ' -- . && echo "MARKERS PRESENT — do not push" || echo "clean"
```

If `sync-with-main.sh` still reports `CONFLICTING` after resolution, record
the merge-state finding as `outcome: skipped` with the conflicted paths and stop
— do not push.

#### Step 3 — Run local tests

```bash
uv run pytest --tb=short 2>&1 | tee /tmp/pytest-unit.log | tail -20
```

If `pr_metadata.needs_integration_tests` is true, also run:

```bash
uv run pytest integration_tests/ -v 2>&1 | tee /tmp/pytest-integration.log | tail -40
```

**If the tail output is insufficient**, grep or read `/tmp/pytest-unit.log` or
`/tmp/pytest-integration.log` — **do not re-run the test suite for more output**.

If tests fail: fix branch-owned failures per [REFERENCE.md](REFERENCE.md)
§ "Test Failure Rules", then **restart this iteration from Step 2** — always
re-sync after a fix so the pushed commit includes both the fix and a clean merge.
Do not push failing code.

After tests pass, run the xfail ratchet per [REFERENCE.md](REFERENCE.md)
§ "xfail Ratchet".

#### Step 4 — Push

```bash
git push
```

If git demands a force-push, stop — something rewrote history and that needs
a human.

#### Step 5 — Wait for CI

```bash
bash .agents/skills/shared/wait-for-ci.sh <number>
```

| Exit | Meaning | Action |
|---|---|---|
| `0` | All checks passed | CI is green — proceed to "On CI green" below |
| `1` | One or more checks failed | Start next iteration with the failures as input |
| `2` | Timed out (10 min) | Record `final_ci_status: "timeout"`; exit loop |

**On CI green**:

1. Run `merge-state.sh <number>`. If it now reports `CONFLICTING`, return to
   Step 2 — a push can race a base-branch merge.

2. If the PR is a draft with a `needs-rebase` label, undraft it:

   ```bash
   gh pr ready <number>

   gh pr edit <number> --remove-label needs-rebase
   ```

3. Record `final_ci_status: "passing"`. Populate the `merge_state` block.
4. Exit the loop.

**On iteration 4 failure (eject)**:

Record `final_ci_status: "failing"`. List the unresolved CI failures. Run
`merge-state.sh <number>` and populate the `merge_state` block. Exit the loop.

### Phase 6 — Emit Artifact and Post Comment

1. Build the execute artifact in memory throughout Phases 2–5; write it only now.
   Write `.claude/pr-{number}-execute.json` per the schema in [REFERENCE.md](REFERENCE.md).
2. Render the execute summary comment (format in [REFERENCE.md](REFERENCE.md)
   § "Execute Comment Format").
3. Post comment: `gh pr review <number> --comment --body "<summary>"`
4. Record `execute_comment_url` in the artifact; re-write the file with the URL.
5. Print artifact path and outcome summary to stdout.

## No User Prompts (Except One)

Execute runs to completion without user prompts, with one exception:

**`new-issue-ask` findings**: after filing the issue, post a comment noting the
finding, then stop and ask the user:

> "Found a non-trivial issue (distant cousin): <description> — filed as #N.
> Should I fold this into the current PR, or leave it for the new issue?
> (If no response, I'll leave it for the issue and continue.)"

Wait for a response. If no response within the session, record as `deferred-ask`
and continue. The question is genuine — do not treat silence as approval to
expand scope.

## Artifact Location

`.claude/pr-{number}-execute.json` — never committed; must be gitignored.
