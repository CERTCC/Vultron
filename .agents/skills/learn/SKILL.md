---
name: learn
description: >
  Promote lessons learned from the build process into durable specifications
  and design notes. First refreshes docs/reference/codebase/ via
  acquire-codebase-knowledge, then reads plan/incoming/learnings/ and queries
  GitHub for open type:Concern issues (both as input queues), analyzes
  gaps, interviews the user with grill-me to align on scope, then writes
  to specs/, notes/, and AGENTS.md, opens a docs-only PR with the
  specs-notes label, and archives processed entries. Use when build
  execution has produced insights that should be reflected in specs or
  notes. For external ideas (GitHub Idea-type issues), use `plan-issue`
  instead.
---

# Skill: Learn

Integrate lessons learned from build execution into the project's durable
specification and design documentation. The inputs are what the build process
has discovered (`plan/incoming/learnings/` — individual per-entry files) and
open GitHub `type:Concern` issues tracked in the repository; the output is
refined `specs/`, `notes/`, and `AGENTS.md`.

**Constraint**: Modify **documentation files only**, including Markdown files
and YAML spec files in `specs/`. Do not modify code or tests.

**Trigger**: Use this skill when `plan/incoming/learnings/` has unprocessed
entries that should be promoted into durable docs.

> For new external ideas (GitHub Idea-type issues), use `plan-issue` instead.

## Quick Start

1. **Ensure synced** (before any writes): `manage_worktree.sh ensure-synced`
2. Invoke `acquire-codebase-knowledge` — full scan, refreshes all 7 docs
   in `docs/reference/codebase/`.
3. Read all files in `plan/incoming/learnings/` and query GitHub for open
   `type:Concern` issues (both are input queues).
4. Invoke `orient-agent` then `deepen-context` for full context (specs,
   notes, code) — it now reads the freshly updated codebase docs.
5. Analyze what the build process has learned vs. what specs and notes capture.
6. Invoke `grill-me` to align on scope and decisions — before writing anything.
   Include GitHub Concern issue triage in this phase (no separate triage step
   needed).
7. **Create the task branch**: `git switch -c learn/<YYYYMMDD>-<slug>`
   (worktree was already synced in step 1; branch here after slug is known)
8. Write to `specs/`, `notes/`, and `AGENTS.md`.
9. Archive each processed incoming learning file via
   `uv run append-history --from-file <path>` (which moves the file to
   `plan/history/YYMM/learning/` and deletes the source).
   Archive each resolved Concern issue via `uv run append-history learning`
   and close the issue with a resolution comment.
10. Invoke `format-markdown`.
11. Commit (including updated `docs/reference/codebase/` files), push, and
    open a docs-only PR with `specs-notes` label.

## Workflow

### Phase 0 — Sync and Refresh Codebase Knowledge

**First, ensure the worktree is synced to `origin/main`** before any file
writes, so all subsequent changes land on an up-to-date baseline:

```bash
SCRIPT="$HOME/.copilot/skills/manage-worktree/scripts/manage_worktree.sh"
if [ -f "$SCRIPT" ]; then
  bash "$SCRIPT" ensure-synced || { echo "❌ Aborted — sync check failed." >&2; exit 1; }
else
  git fetch origin --quiet 2>/dev/null || true
  BEHIND=$(git rev-list --count HEAD..origin/main 2>/dev/null || echo 0)
  [ "$BEHIND" -gt 0 ] && { echo "❌ Aborted: $BEHIND commit(s) behind origin/main. Run: git rebase origin/main" >&2; exit 1; }
fi
```text

Do this **before** `acquire-codebase-knowledge` runs — the scan regenerates
files in `docs/reference/codebase/` (uncommitted), and those outputs must not
be clobbered by a later `git reset --hard`.

Then invoke the `acquire-codebase-knowledge` skill (full scan, no focus area
restriction). This regenerates all seven files in `docs/reference/codebase/`
from the current state of the repository before any gap analysis begins,
ensuring `orient-agent` in Phase 1 reads an accurate baseline.

Always run this phase unconditionally — `learn` runs infrequently enough
that the cost of a full scan is justified on every invocation.

### Phase 1 — Load Internal Sources and Context

1. Read all files in `plan/incoming/learnings/` — open questions, observations,
   and constraints from recent build/bugfix runs (ephemeral queue; files are
   moved to `plan/history/YYMM/learning/` after archiving).
2. Query GitHub for all open `type:Concern` issues — these are the tracked
   technical concerns, risks, and debt items surfaced by prior codebase scans
   and the `process-concerns` skill (second input queue; resolved issues are
   archived and closed):

   ```bash
   gh issue list \
     --repo CERTCC/Vultron \
     --state open \
     --label concern \
     --json number,title,body
   ```text

1. Invoke `orient-agent` then `deepen-context` for full context: specs JSON,
   plan files, docs/adr/, notes/, AGENTS.md, and a code scan. Because
   Phase 0 has already refreshed the codebase docs, `orient-agent`/`deepen-context`
   will read up-to-date architecture and structure information.

> `plan/incoming/learnings/` is an ephemeral queue. Files are moved to
> `plan/history/YYMM/learning/` after archiving. Any critical insight
> in an entry **must be promoted** to `specs/` or `notes/` before being
> archived.

### Phase 2 — Analyze Gaps

See `.claude/skills/shared/completeness-doctrine.md` for the project standard
on what constitutes a complete lesson — loaded by `orient-agent` in Phase 1.

Identify what the build process and codebase scan have surfaced that is not
yet captured in durable docs. Consider both incoming learning files and
open GitHub Concern issues:

1. Missing requirements — behavior exists in code but has no spec.
2. Ambiguous or untestable requirements — reality diverges from what's written.
3. Redundant or contradictory requirements across spec files.
4. Agent guidance patterns that keep recurring in `plan/incoming/learnings/`
   but are not yet in `AGENTS.md`.
5. Open GitHub `type:Concern` issues that reveal missing spec requirements or
   durable design notes.
6. Recent completed-task insights — when needed, run `uv run show-history
   --month YYMM` to identify which history entries contain architectural
   lessons, then open those entry files.

A lesson is not complete until it has been promoted to `specs/`, `notes/`, or
`AGENTS.md`. An incoming learning file that is archived without producing a
durable output is a wasted lesson. If a learning entry clearly warrants a spec
or notes update but one cannot be written in this session, document why and
create a Concern issue — do not silently archive the entry without promotion.

### Phase 3 — Interview with Grill-Me

Invoke the `grill-me` skill. Resolve one question at a time (using `ask_user`)
with a recommended answer before writing anything:

- Which insights from `plan/incoming/learnings/` are most important to promote?
- Which open GitHub `type:Concern` issues are addressed by this session's
  insights, outdated, or should be promoted to specs/notes? (Resolved
  concerns go to `specs/` if they reveal missing requirements, `notes/`
  otherwise.)
- Which gaps are most critical to close in this run?
- Are there unresolvable conflicts that need a human decision?
- Does any spec change require code verification first?

Answer questions from codebase exploration where possible.

**After grill-me completes — create the task branch before writing any files:**

```bash
git switch -c learn/<YYYYMMDD>-<slug>
```text

The worktree was already synced to `origin/main` in Phase 0. All file writes (Phases 4–7)
happen on this branch so they are never at risk from a `git reset --hard`.

### Phase 4 — Refine Specifications (`specs/`)

- Clarify, split, merge, or remove requirements; keep each atomic, specific,
  concise, and verifiable.
- `specs/` are for *what*, not *how*.
- Eliminate redundancy; use `PROD_ONLY` tag for production-only requirements.
- Separate topics of concern into distinct files when a file has grown too
  broad.
- Update `specs/README.md` to reflect all file additions, removals, renames,
  and topic reorganizations.

**ADR decision (MS-11):** When adding new spec entries, apply the decision-tree
heuristic in `notes/specs-vs-adrs.md` to decide whether the underlying design
choice also warrants a new ADR. Write an ADR when a meaningful alternative was
evaluated and rejected; skip it for uncontested rules (MS-11-002, MS-11-005).
When both are created, cross-reference them: cite the ADR in the spec's per-requirement
`rationale` field (per MS-11-004 — not the spec-group `description`), and list the
generated spec IDs in the ADR's "More Information" section (MS-11-004).

### Phase 5 — Update Design Notes (`notes/`)

- Promote insights, tradeoffs, and lessons from `BUILD_LEARNINGS.md` and
  resolved GitHub Concern issues into the appropriate `notes/*.md` file.
  Do not duplicate spec text.
- Mark unresolved items explicitly: `Open Question:` / `Design Decision:`.
- Update `notes/README.md` when files are added, removed, or reorganized.
- Every `notes/*.md` (except `notes/README.md`) must have valid YAML
  frontmatter with at least `title` and `status`.

### Phase 6 — Update Agent Guidance (`AGENTS.md`)

Promote recurring implementation patterns and conventions from
`plan/incoming/learnings/` into `AGENTS.md`. Keep entries precise, actionable,
and minimal.

### Phase 7 — Prepare Archive Content and Close Processed Entries

For each incoming learning file and each resolved GitHub Concern issue that
has been fully promoted to `specs/`, `notes/`, or `AGENTS.md`:

1. **For incoming learning files**: run `uv run append-history --from-file
   <path>` — this moves the file from `plan/incoming/learnings/` to
   `plan/history/YYMM/learning/`, deletes the source, and regenerates the
   monthly README. Add a promotion note to the end of the body **before**
   calling `append-history --from-file` (edit the file in-place):

   ```text
   **Promoted**: YYYY-MM-DD — captured in <destination file(s)>.
   Docs PR: <PR_URL>.   ← filled in after PR is opened
   ```

1. **For resolved GitHub Concern issues**: draft the archive body
   (store in memory — the actual `archive-history` invocations happen in
   Phase 9 after the PR URL is known):

   ```text
   TYPE    = learning
   TITLE   = <short concern title>
   SOURCE  = CONCERN-<ISSUE_NUMBER>
   BODY    = Full original concern body
             + "**Resolved**: YYYY-MM-DD — captured in <destination file(s)>."
             + "Docs PR: <PR_URL>."  ← filled in after PR is opened
   ```

2. **For resolved GitHub Concern issues**: close the issue and add a
   resolution comment after the PR is open (step in Phase 9):

   ```bash
   gh issue comment "${ISSUE_NUMBER}" --repo CERTCC/Vultron \
     --body "✅ Resolved.

   - Docs PR: <PR_URL>
   - Promoted to: \`specs/<topic>.yaml\` and/or \`notes/<topic>.md\`

   Design decisions are now captured in durable documentation."

   gh issue close "${ISSUE_NUMBER}" --repo CERTCC/Vultron
   ```text

Do **not** reference `plan/incoming/learnings/` from durable docs.

### Phase 8 — Lint, Commit, and Open PR

1. Invoke the `format-markdown` skill on all new/modified markdown files.
   Fix all errors.
2. If a requirement conflict cannot be resolved, create a learning file in
   `plan/incoming/learnings/` and **stop before committing**.
3. Stage and commit (branch was created at the end of Phase 3):

   ```bash
   git add specs/<changed-files> notes/<changed-files> AGENTS.md \
       plan/incoming/learnings/ docs/reference/codebase/
   git commit -m "docs: promote learnings — <topic>

   - <bullet: what was promoted and where>
   - Archive <N> entr[y/ies] via append-history --from-file (after PR)
   - Close <N> resolved GitHub Concern issue(s) with resolution comments
   - Refresh docs/reference/codebase/ via acquire-codebase-knowledge

   Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
   ```

   Use multiple commits for thematically distinct changes (e.g., spec
   refinements, notes promoted, AGENTS.md updates).

   Then invoke the `create-pr` skill:

   ```text
   type:         docs
   title:        docs: promote learnings — <topic>
   body:         <composed per pr-body-guide.md docs template>
   labels:       specs-notes
   issue_number: <issue if applicable; omit if none>
   ```

   `create-pr` performs the rebase on `origin/main`, runs linters, pushes, and
   returns the PR URL. Use the returned URL when filling in the `Docs PR:`
   field in the archive bodies (Phase 9).

### Phase 9 — Archive Entries and Close Issues

Now that the PR URL is known:

1. **For each incoming learning file**: edit it in-place to add the final
   PR URL to the promotion note (appended in Phase 7), then run:

   ```bash
   uv run append-history --from-file plan/incoming/learnings/<YYYYMMDD-SLUG>.md
   ```

   This moves the file to `plan/history/YYMM/learning/` and deletes the
   source. Stage `plan/history/` and commit.

2. **For each resolved GitHub Concern issue**: invoke the `archive-history`
   skill once per entry:

```text
TYPE    = learning
TITLE   = <short concern title>
SOURCE  = CONCERN-<ISSUE_NUMBER>
BODY    = <full original concern body>
          + "**Resolved**: YYYY-MM-DD — captured in <destination file(s)>."
          + "Docs PR: <PR_URL>."
```

For resolved GitHub Concern issues, post the resolution comment and close
the issue (see Phase 7 step 3 for the comment template).

## Constraints

- Do not modify code or tests.
- Do not process GitHub Idea-type issues — use `plan-issue` for those.
- Do not skip the grill-me phase — it must complete before any writing.
- Do not reference `plan/incoming/learnings/` from durable docs.
- Archive processed incoming learning files via
  `uv run append-history --from-file <path>`; do not leave files in
  `plan/incoming/learnings/` after promoting.
- Archive Concern issues via the `archive-history` skill.
- Verify assumptions against the codebase; do not assert absence without
  evidence.
