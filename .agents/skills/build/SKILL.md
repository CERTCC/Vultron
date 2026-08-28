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

0. Sync the worktree to `origin/main` before loading any context.
1. Invoke `orient-agent` to load baseline context.
2. Select a single target issue (auto or explicit) and fail fast on blockers.
3. Claim the issue.
4. Invoke `deepen-context` with hints from the issue.
5. Implement, validate, code-review, open PR, archive.

## Workflow

### Phase 0 — Sync

Move the worktree HEAD to `origin/main` before loading any context. Do **not**
use `git checkout main` — that branch may be checked out in another worktree.

```bash
git fetch origin main && git reset --hard origin/main
```

If this fails, stop and investigate before proceeding. On success, `orient-agent`
reads fresh specs/ADRs/notes, and the task branch created by `claim-issue.sh` in
Phase 2 will be rooted at the latest `origin/main` commit.

### Phase 1 — Orient

Invoke the `orient-agent` skill.

### Phase 2 — Select, Gate, and Claim

0. Determine the target issue mode:

   - If the user passed multiple issue numbers (for example `build 123 456`),
     ask whether to start with the first issue only (recommended). This skill
     executes one issue per run.
   - If the user passed one explicit issue number, use that issue.
   - If no explicit issue was passed, auto-select from the top-priority
     unblocked Now-Epic flow below.

1. List open Now-Epics:

   ```bash
   bash .agents/skills/shared/query-now-epics.sh
   ```

   The top-priority group is the first Epic with at least one unblocked
   open leaf sub-issue.

2. Query leaf Issues of that Epic:

   ```bash
   bash .agents/skills/shared/query-epic-subissues.sh <EPIC_NUMBER>
   ```

   A candidate issue must: `state=OPEN`, no assignees, no `stale-claim`
   label, all `blockedBy` entries `CLOSED`, `subIssues.totalCount==0`.

3. Pick the highest-priority candidate.

4. **Empty-Epic gate** — applies to both auto-selected and explicit issues:

   Query the selected issue's type and sub-issue count:

   ```bash
   bash .agents/skills/shared/query-issue-type.sh <ISSUE_NUMBER>
   ```

   If `issueType.name == "Epic"` and `subIssues.totalCount == 0`:

   1. Apply `needs-decomposition` label if not already present:

      ```bash
      gh issue edit <ISSUE_NUMBER> --repo CERTCC/Vultron \
        --add-label "needs-decomposition"
      ```

   2. Post an actionable comment on the Epic:

      ```bash
      gh issue comment <ISSUE_NUMBER> --repo CERTCC/Vultron \
        --body "No implementable sub-issues found. Run \`/plan-issue <ISSUE_NUMBER>\` to decompose this Epic into Tasks before building."
      ```

   3. Tell the user: "Epic #N has no sub-issues and cannot be built yet. Run `/plan-issue N` to decompose it into Tasks first."
   4. **Stop.** Do not claim, branch, or proceed.

5. Fail-fast blocker gate on the selected issue (auto-selected or explicit):

   - Query `blockedBy` for the issue and filter to `state=OPEN`.
   - If any OPEN blockers exist, print blocker numbers/titles and stop.
   - Do not claim, branch, or deepen context when blocked.

6. **Pre-claim AC verification gate** — fetch the issue body and verify
   each acceptance criterion against `origin/main` HEAD before claiming:

   For each `- [ ] AC-N: <text>` item in the issue body, grep or graphify
   `origin/main` for concrete evidence the AC is already satisfied (e.g.,
   the described file exists with the required content, the named function
   or class is present, the referenced behavior is implemented).

   If **no** `- [ ] AC-N:` items are found in the issue body (prose-format
   or free-form ACs), skip this gate and proceed directly to step 7.

   If **all** ACs are confirmed satisfied on `origin/main`:

   1. Post a reference comment on the issue citing the PR(s) that
      delivered the work:

      ```bash
      gh issue comment <N> --repo CERTCC/Vultron --body "$(cat <<'EOF'
      All acceptance criteria are already satisfied on `origin/main` (delivered
      by #<PR>). Closing without further work.
      EOF
      )"
      ```

   2. Close the issue:

      ```bash
      gh issue close <N> --repo CERTCC/Vultron
      ```

   3. **Stop.** Do not claim, branch, or deepen context.

   If any AC is unconfirmed, proceed to step 7 and claim normally.

7. **Claim the Issue**:

   ```bash
   bash .agents/skills/shared/claim-issue.sh <N> task <slug>
   ```

   Abort immediately if this exits non-zero.

8. Fetch the issue body and comments (including any comments not yet
   loaded in step 6). Use the full content as implementation context
   throughout Phases 3–5.

### Phase 3 — Deepen Context

Invoke `deepen-context` with focus hints derived from the issue body
(e.g., `"wire layer"`, `"BT integration"`, `"embargo lifecycle"`).

### Phase 4 — Verify Before Coding

1. **Compose-before-create gate (all domain types — blocking)**:
   Load `.agents/skills/shared/compose-before-create.md` and apply the
   per-subsystem search patterns for every subsystem the task touches (use
   cases, wire handlers, adapters, demo helpers). Do not write any new code
   until this search is complete. If an existing artifact covers the
   requirement, compose or subclass it — do not re-implement.

2. Search `vultron/` and `test/` to confirm the current state.
3. Do not assume missing functionality; verify in code.
4. If a blocking prerequisite is discovered, create and wire it:

   ```bash
   NEW_ISSUE=$(.agents/skills/manage-github-issue/manage_github_issue.sh \
     --title "<prerequisite title>" \
     --body "<description>" \
     --label "size:<S|M|L>" \
     --parent <CURRENT_TASK_NUMBER>)
   bash .agents/skills/shared/add-to-project.sh "${NEW_ISSUE}"
   ```

   Record the dependency as a learning file in `plan/incoming/learnings/` and stop.

5. If more than one prerequisite is required, or the work is non-trivial,
   create a learning file in `plan/incoming/learnings/` and stop.

### Phase 5 — Implement

See `.claude/skills/shared/completeness-doctrine.md` for the project standard
on what "done" means — loaded by `orient-agent` in Phase 1.

1. Implement the full intent of the selected task, not just the happy path.
   Edge cases, error handling, and type correctness are part of the task, not
   optional add-ons.
2. Follow project conventions. "Keep the change focused" means do not expand
   into adjacent unscoped work — it does not mean implement less than the task
   requires.
3. Add or update tests for every new or changed behavior. A behavior with no
   test is not done.
4. Reuse existing helpers and keep the implementation DRY.

   **If this task creates or modifies a BT node (required — BTC-01-001,
   BTND-07-005):**

   a. **Node inventory**: grep `vultron/core/behaviors/` for existing node
      classes whose protocol state, domain, or semantic action overlaps with
      what you are about to implement. Search for the target state value, the
      action name, and the affected domain (e.g. `"RM.CLOSED"`,
      `"EM.EXITED"`, `"active_embargo = None"`, `"add_participant_status"`).
      If a matching node exists, compose or delegate from it — do not
      re-implement.

   b. **Base-class check (BTND-07-009, BTND-07-010)**: for any emit, send,
      or state-transition node, check `vultron/core/behaviors/` for an
      existing base class whose `update()` frame covers the same
      guard+emit+outbox or guard+transition+log pattern. Consult the domain
      base-class table in
      [`vultron/core/behaviors/AGENTS.md`](../../../vultron/core/behaviors/AGENTS.md).
      If a matching base exists, subclass it. If none exists for your domain,
      create it first, then write the concrete node.

   c. **Sibling-domain scan**: check peer trees in sibling modules for the
      same trigger condition appearing more than once. A shared trigger (e.g.
      `IsRemoveEmbargoEvent` appearing in two trees) signals a shared behavior
      need that should be a single composed subtree, not two parallel
      implementations.

   d. **AC-1 compliance gate**: any node that reads EM/RM/CS state MUST do
      so through the appropriate `Read*StateNode`. Any node that writes
      EM/RM/CS state MUST do so through `Write*StateNode`. Inline reads
      (e.g. `case.current_status.em.state`) and inline writes are AC-1
      violations regardless of context and must be caught before review.

5. Sub-agents may help, but main-agent validation is mandatory.
6. **Pattern-change checklist** — run this before opening the PR:
   - If this PR retires a method or establishes a new pattern, grep
     `AGENTS.md` for the old name and update any stale pitfalls in this PR.
   - Grep `notes/` for references to any symbol, method, or table entry
     you changed and update stale rows in this PR.
   - If any new `SvcXxxUseCase` class was added, confirm a matching file
     exists under `test/core/use_cases/triggers/` (see
     `notes/triggers-test-coverage.md`).

**Scope expansion judgment:** If implementing this task reveals adjacent work
that clearly belongs with it, apply the following:

- Would it require a new GitHub issue, a design decision, or an irreversible
  change? → Ask the user if present. If unattended, make the best-judgment
  call, record the rationale as a learning file in `plan/incoming/learnings/`,
  and continue.
- Trivially additive (clearly-missing test, obvious type annotation fix)?
  → Just do it.

### Phase 6 — Validate

1. Run in order:

   ```bash
   uv run black vultron/ test/
   uv run flake8 vultron/ test/ && uv run mypy && uv run pyright
   uv run pytest --tb=short 2>&1 | tee /tmp/pytest-unit.log | tail -5
   uv run pytest -m integration --tb=short 2>&1 | tee /tmp/pytest-integration.log | tail -5
   ```

   Both suites must pass. The first command covers the unit suite (integration
   tests excluded by `addopts`); the second explicitly runs the integration
   suite so demo-layer regressions are caught before the PR opens.

2. Do not skip or delegate validation.
3. Apply branch-ownership and pre-existing-failure rules from
   `completeness-doctrine.md` § "Finding Severity".
4. If pre-existing is proven: create/update a Bug issue via `manage-github-issue`
   with evidence (failing command/output, clean-base proof, causality check,
   blocked/unblocked impact), wire structured blockers, add a handoff comment,
   and record the Bug link as a learning file in `plan/incoming/learnings/`.
   Set `--parent "${CURRENT_TASK_NUMBER}"` so the bug is wired under the same
   task (and therefore the same epic) where it was discovered — this keeps it
   visible in the epic tree and off the `no:parent-issue` orphan list.

### Phase 7 — Pre-PR Code Review

Invoke the `code-review` agent against the current branch diff vs `main`.

Findings use the three-category system from
`.claude/skills/shared/completeness-doctrine.md`:

- **FAIL** — broken, spec violated, changed behavior untested → fix before
  the PR opens
- **IMPROVE** — correct but incomplete → fix in this session, document in the
  PR body
- **DEFER** — genuinely out of scope → requires creating a follow-up GitHub
  issue immediately; surface to the user for acknowledgment; do not defer
  unilaterally

There is no "ADVISORY" category that can be logged and forgotten. Every
finding is either fixed here or gated via DEFER.

Because this phase runs before the final commit, `git diff main...HEAD` may
be empty if changes are unstaged. Stage all changed files first (`git add`),
then pass `git diff --cached` as the diff source for the review, or do a
draft commit and use `git diff main...HEAD` normally.

### Phase 8 — Open PR and Finalize

1. Compute diff size: ≤50 lines → `size:S`; 51–300 → `size:M`; 301+ → `size:L`.
   Update the `size:` label on the Issue.

2. Invoke the `create-pr` skill to push and open the PR:

   ```text
   type:         implementation
   title:        <short title>
   body:         <composed per pr-body-guide.md implementation template>
   labels:       size:<X>
   issue_number: <N>
   ```

   `create-pr` performs the rebase on `origin/main`, validates, pushes, and
   returns the PR URL. Use the returned URL in the `archive-history` call
   below.

3. Post `[ADVISORY]` findings as a PR comment (if any).

4. Invoke `archive-history`:

   ```text
   TYPE    = implementation
   TITLE   = <short task title>
   SOURCE  = ISSUE-<N>
   BODY    = "## Issue #<N> — <title>\n\n<completion summary, PR link>"
   ```

5. Run the **upward-reflection checklist** per
   `.agents/skills/shared/upward-reflection.md`. Record each triggered signal
   as a learning file. Do not write completion summaries here.

6. Invoke `commit` if any learning files were created in `plan/incoming/learnings/`.

## Constraints

- One issue is executed per run.
- Multi-issue input may be accepted for user guidance, but this skill should
  ask how to proceed and then continue with one issue only.
- Do not skip validation or the pre-PR code review.
- Do not commit directly to `main`. All work goes through a PR.
