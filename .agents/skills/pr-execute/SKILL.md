---
name: pr-execute
description: >
  Execution phase of the PR review pipeline. Reads .claude/pr-{number}-triage.json,
  applies all FAIL/IMPROVE fixes inline, remediates CI failures, files GitHub issues
  for out-of-scope findings, resolves review thread comments, and writes
  .claude/pr-{number}-execute.json. Use after /pr-triage, or as the second step
  of /pr-ship.
---

# Skill: PR Execute

## Purpose

Execute consumes the closed finding list from `pr-triage` and processes it in
one batch pass. No new discovery happens here. The finding set is fixed at the
start; execute either resolves each item or records why it was skipped.

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
5. Check `pr_metadata.needs_integration_tests` — determines test scope in Phase 4.

### Phase 2 — Apply fix-now Fixes

For each finding where `decision_outcome` is `fix-now` or `fix-now-expand-scope`
and `severity` is `FAIL` or `IMPROVE`:

1. Apply the fix (edit files as needed).
2. Do not commit yet — batch all fixes, then commit once at the end of this phase.
3. After all fixes are applied: `uv run black <changed files>` then commit:

   ```text
   fix(pr-execute): address <N> findings from triage

   <bullet per finding: phase-name — short description>

   Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
   ```

4. Record `commit_ref` (short SHA) for each finding addressed in this commit.

### Phase 3 — CI Remediation

For findings from Phase 11 (CI failures) in the triage artifact:

1. Fetch current CI failure logs: `gh run list --branch <head_ref> --limit 1`
   then `gh run view <run-id> --log-failed`.
2. Parse failure output — identify root causes (lint, type errors, test failures).
3. Fix lint/type/format failures directly (these are always branch-owned).
4. For test failures: apply the branch-ownership rule from [REFERENCE.md](REFERENCE.md)
   § "Test Failure Rules" before classifying anything as pre-existing.
5. Commit CI fixes separately from Phase 2 fixes:

   ```text
   fix(ci): resolve CI failures — <summary>

   Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
   ```

6. Record `commit_ref` for each CI finding addressed.

### Phase 4 — Run Test Suite

Based on `pr_metadata.needs_integration_tests`:

**Unit tests only** (flag is false):

```bash
uv run pytest --tb=short 2>&1 | tail -20
```

**Full suite** (flag is true):

```bash
uv run pytest --tb=short 2>&1 | tail -20
uv run pytest integration_tests/ -v 2>&1 | tail -40
```

If tests fail: apply the rules from [REFERENCE.md](REFERENCE.md) § "Test Failure
Rules". Fix branch-owned failures and re-run. If failure is proven pre-existing,
file a Bug issue with evidence via `manage-github-issue`, wire structured blockers,
and record the finding outcome as `skipped` with a `skip_reason` referencing the
issue number.

Do not proceed to Phase 5 until tests pass or all remaining failures are
documented as pre-existing with linked Bug issues.

### Phase 5 — Handle NEW-ISSUE Findings

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

### Phase 6 — Resolve Review Thread Comments

For each unresolved review comment on the PR (fetched via
`gh api repos/CERTCC/Vultron/pulls/<number>/comments`):

Match each comment to the finding(s) it corresponds to. Then per
[REFERENCE.md](REFERENCE.md) § "Comment Resolution":

- ✅ Fully addressed → resolve with commit reference
- ⚠️ Partially addressed → reply explaining why; leave for reviewer to close
- ❌ Cannot address → reply explaining why; reference any filed issue

Do not mark a comment resolved unless the code actually addresses it.

### Phase 7 — Emit Artifact and Post Comment

1. Build the execute artifact in memory throughout Phases 2–6; write it only now.
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
