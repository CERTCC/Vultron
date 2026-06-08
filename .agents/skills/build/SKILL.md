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

## Quick Start

1. Invoke `orient-agent` to load baseline context.
2. Select the highest-priority unblocked leaf Issue from the top Now-Epic.
3. Invoke `deepen-context` with hints from the issue.
4. Claim the issue and implement.
5. Validate, code-review, open PR, archive.

## Workflow

### Phase 1 — Orient

Invoke the `orient-agent` skill.

### Phase 2 — Select and Claim

1. List open Now-Epics:

   ```bash
   bash .agents/skills/shared/query-now-epics.sh
   ```

   The top-priority group is the first Epic with at least one unblocked
   open leaf sub-issue.

2. Query leaf Issues of that Epic:

   ```bash
   gh api graphql -f query='{
     repository(owner:"CERTCC", name:"Vultron") {
       issue(number: <EPIC_NUMBER>) {
         subIssues(first: 50) {
           nodes {
             number title state
             assignees(first: 1) { nodes { login } }
             blockedBy(first: 10) { nodes { number state } }
             subIssues(first: 1) { totalCount }
             labels(first: 10) { nodes { name } }
           }
         }
       }
     }
   }'
   ```

   A candidate issue must: `state=OPEN`, no assignees, no `stale-claim`
   label, all `blockedBy` entries `CLOSED`, `subIssues.totalCount==0`.

3. Pick the highest-priority candidate.

4. Fetch the issue body and comments. Use the content as implementation
   context throughout Phases 3–5.

5. **Claim the Issue**:

   ```bash
   bash .agents/skills/shared/claim-issue.sh <N> task <slug>
   ```

   Abort immediately if this exits non-zero.

### Phase 3 — Deepen Context

Invoke `deepen-context` with focus hints derived from the issue body
(e.g., `"wire layer"`, `"BT integration"`, `"embargo lifecycle"`).

### Phase 4 — Verify Before Coding

1. Search `vultron/` and `test/` to confirm the current state.
2. Do not assume missing functionality; verify in code.
3. If a blocking prerequisite is discovered, create and wire it:

   ```bash
   NEW_ISSUE=$(.agents/skills/manage-github-issue/manage_github_issue.sh \
     --title "<prerequisite title>" \
     --body "<description>" \
     --label "size:<S|M|L>" \
     --parent <CURRENT_TASK_NUMBER>)
   bash .agents/skills/shared/add-to-project.sh "${NEW_ISSUE}"
   ```

   Record the dependency in `plan/BUILD_LEARNINGS.md` and stop.

4. If more than one prerequisite is required, or the work is non-trivial,
   record details in `plan/BUILD_LEARNINGS.md` and stop.

### Phase 5 — Implement

1. Implement only the selected task.
2. Follow project conventions; keep the change focused.
3. Add or update tests for new or changed behavior.
4. Reuse existing helpers and keep the implementation DRY.
5. Sub-agents may help, but main-agent validation is mandatory.

### Phase 6 — Validate

1. Invoke `format-code`, then `run-linters`, then `run-tests`.
2. Do not skip or delegate validation.
3. File incidental bugs as Bug-type GitHub issues via `manage-github-issue`;
   do not pursue them unless they block the current task.

### Phase 7 — Pre-PR Code Review

Invoke the `code-review` agent against the current branch diff vs `main`.
Findings are tagged `[BLOCKING]` (fix before continuing) or `[ADVISORY]`
(log in PR comment after opening).

### Phase 8 — Open PR and Finalize

1. Compute diff size: ≤50 lines → `size:S`; 51–300 → `size:M`; 301+ → `size:L`.
   Update the `size:` label on the Issue.

2. Push and open a PR:

   ```bash
   git fetch origin main && git rebase origin/main
   git push -u origin task/<N>-<slug>
   gh pr create --repo CERTCC/Vultron \
     --title "<short title>" \
     --body "Closes #<N>

   <summary of changes>" \
     --label "size:<X>"
   ```

   If the rebase reports conflicts, stop, resolve them, and re-run validation
   before pushing. This check must happen immediately before the push, not
   earlier in the workflow.

3. Post `[ADVISORY]` findings as a PR comment (if any).

4. Invoke `archive-history`:

   ```text
   TYPE    = implementation
   TITLE   = <short task title>
   SOURCE  = ISSUE-<N>
   BODY    = "## Issue #<N> — <title>\n\n<completion summary, PR link>"
   ```

5. Record observations in `plan/BUILD_LEARNINGS.md`
   (`### YYYY-MM-DD LABEL — description`). Do not write completion summaries
   here.

6. Invoke `commit` if `BUILD_LEARNINGS.md` was updated.

### Phase 9 — Merge Conflict Recovery (if needed)

```bash
git fetch origin main && git rebase origin/main
# Success: git push --force-with-lease
# Failure: post PR comment, add needs-rebase label, stop.
```

## Constraints

- One task per run (or a tightly related set of trivial tasks).
- Do not skip validation or the pre-PR code review.
- Do not commit directly to `main`. All work goes through a PR.
