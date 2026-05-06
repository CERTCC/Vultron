---
name: build
description: >
  Completes the highest-priority pending implementation task: loads project
  context, selects the next task from GitHub Issues, implements it, validates,
  opens a PR, and updates plan history. Use when the user asks to continue
  planned implementation work or turn the next prioritized item into a
  completed changeset.
---

# Skill: Build

## Quick start

1. Invoke the `study-project-docs` skill to load all specs and read project
   context.
2. Select the highest-priority unblocked leaf GitHub Issue in the top-priority
   group (read from `plan/PRIORITIES.md`), then claim it by creating the task
   branch.
3. Verify the current implementation in `vultron/` and `test/` before coding.
4. Implement only the selected task, then run the required validation.
5. If validation succeeds, run a pre-PR code review, open a PR with
   "Closes #N", and archive the completion summary.

## Inputs

- `repo_root` (optional, default `.`): repository root containing the plan,
  specs, source, and tests.

## Workflow

### Phase 1 - Review context

Invoke the `study-project-docs` skill. It loads all specs, reads all plan/,
docs/adr/, notes/, and AGENTS.md files, and scans vultron/ and test/.

### Phase 2 - Select and claim work

1. Read `plan/PRIORITIES.md` to identify the current top-priority group name.
2. Query GitHub for open, unblocked **leaf Issues** (no sub-issues) with that
   `group:` label, excluding Issues that have `stale-claim` set or are already
   assigned. Use `github-mcp-server-list_issues` with the appropriate label
   filter.
3. From the resulting list, pick the highest-priority unblocked Issue. Account
   for blockers (`Blocked by #N` in the Issue body), prerequisites, and whether
   the work fits in a single run.
4. Fetch the Issue body and comments using `github-mcp-server-issue_read`
   (`method: get` then `method: get_comments`). Use the combined content as
   implementation context throughout Phases 3–5.
5. **Claim the Issue**:
   - Create a branch: `git switch -c task/<issue-number>-<slug>`
   - If the branch already exists, abort — the task is already claimed.
   - Assign the Issue to the triggering user:
     `gh issue edit <N> --add-assignee @me --repo CERTCC/Vultron`
   - Post a claim comment:
     `gh issue comment <N> --repo CERTCC/Vultron --body "Claimed by <agent-session> on branch task/<N>-<slug>"`

### Phase 3 - Verify before coding

1. Search `vultron/` and `test/` to confirm the current implementation.
2. Do not assume missing functionality; verify it in code.
3. If a blocking prerequisite is discovered, create a new GitHub Issue for it
   with `group:unscheduled` and the appropriate `size:` label, then
   immediately link it as a sub-issue of the current task Issue
   (PAD-01-003). First resolve the node IDs, then use GraphQL `addSubIssue`:

   ```bash
   # Resolve node IDs
   gh api graphql -f query='{ repository(owner:"CERTCC", name:"Vultron") {
     parent: issue(number: <CURRENT_TASK_NUMBER>) { id }
     child:  issue(number: <NEW_ISSUE_NUMBER>) { id }
   } }'

   # Link as sub-issue
   gh api graphql -f query='
   mutation {
     addSubIssue(input: {
       issueId: "<PARENT_NODE_ID>"
       subIssueId: "<CHILD_NODE_ID>"
     }) { issue { number } subIssue { number } }
   }'
   ```

   Record the dependency in `plan/BUILD_LEARNINGS.md` and stop. Do not add
   prerequisite tasks to `plan/IMPLEMENTATION_PLAN.md`.
4. If more than one prerequisite is required, or the prerequisite work is
   non-trivial, update `plan/BUILD_LEARNINGS.md` with details and stop.

### Phase 4 - Implement

1. Implement only the selected task.
2. Follow project conventions and keep the change focused.
3. Add or update tests for new or changed behavior.
4. Reuse existing helpers and keep the implementation DRY.
5. Sub-agents may help with implementation, but main-agent validation is
   mandatory.

### Phase 5 - Validate

1. Invoke the `format-code` skill, then `run-linters`, then `run-tests`.
2. Do not skip or delegate validation.
3. If incidental bugs are discovered, add them to `plan/BUGS.md` with clear
   reproduction notes and do not pursue them unless they block the current task.

### Phase 6 - Pre-PR code review

Invoke the `code-review` agent against the current branch diff relative to
`main`. Every finding will be tagged `[BLOCKING]` or `[ADVISORY]`:

- `[BLOCKING]` — bugs and security issues. Fix **all** of these before
  continuing. After fixing, re-run the code review to confirm no new
  `[BLOCKING]` findings were introduced.
- `[ADVISORY]` — style and quality observations. Do not block on these; log
  them in a PR comment after the PR is opened (Phase 7 step 4).

### Phase 7 - Open PR and finalize

1. Compute the actual diff size (total lines added + removed across all changed
   files):
   - ≤50 lines → `size:S`
   - 51–300 lines → `size:M`
   - 301+ lines → `size:L`

   Update the `size:` label on the Issue to match.

2. Push the branch and open a PR:

   ```bash
   git push -u origin task/<issue-number>-<slug>
   gh pr create --repo CERTCC/Vultron \
     --title "<short title>" \
     --body "Closes #<N>

   <summary of changes>" \
     --label "size:<X>"
   ```

3. If there were `[ADVISORY]` findings from the code review, post them as a
   PR comment:

   ```bash
   gh pr comment <PR-number> --repo CERTCC/Vultron \
     --body "Code review advisory findings: ..."
   ```

4. Append a completion summary to `plan/history/` using the `append-history`
   tool:

   ```bash
   cat <<'EOF' | uv run append-history implementation \
       --title "<short task title>" \
       --source "https://github.com/CERTCC/Vultron/issues/<N>"

   ## Issue #<N> — <title>

   <completion summary: what was done, outcome, PR link>
   EOF
   ```

5. Record **observations, open questions, and constraints** discovered during
   implementation in `plan/BUILD_LEARNINGS.md`. Use a dated header per entry
   (e.g., `### 2026-04-28 LABEL — Short description`). Do **not** write
   completion summaries here.

6. Invoke the `commit` skill if any local files (BUGS.md, BUILD_LEARNINGS.md)
   were updated. The implementation changes themselves are on the PR branch.

### Phase 8 - Merge conflict recovery (if needed)

If the PR reports merge conflicts:

1. Attempt an automatic rebase:

   ```bash
   git fetch origin main
   git rebase origin/main
   ```

2. If the rebase succeeds: `git push --force-with-lease`. CI re-runs.
3. If the rebase fails: post a comment on the PR explaining the conflict, add
   the `needs-rebase` label, and stop. Human intervention is required.

## Constraints

- Preserve focus on a single task, or a tightly related set of trivial tasks.
- Do not modify unrelated tasks.
- Do not skip validation or the pre-PR code review.
- Each run starts in a fresh context.
- Do not commit directly to `main`. All work goes through a PR.
- Do not add tasks to `plan/IMPLEMENTATION_PLAN.md`. New work items are GitHub
  Issues.

## Label Naming Rules (PAD-02-007)

When creating prerequisite Issues or updating `group:` labels on any issue:

- **Never include a priority number** in the `group:` label name.
  Use `group:architecture-hardening`, **not** `group:473-architecture-hardening`.
  Priority numbers in PRIORITIES.md can change; label names must remain stable.
- **Derive the slug** from the priority group title in kebab-case
  (e.g., "Bug Fixes and Demo Polish" → `group:bug-fixes-demo-polish`).
- **Check for label existence** before assigning. Create it if missing:

  ```bash
  gh label create "group:<slug>" \
    --repo CERTCC/Vultron \
    --description "<Priority group title (no number)>" \
    --color "#1d76db"
  ```
