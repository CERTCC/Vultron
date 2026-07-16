---
name: create-pr
description: >
  Rebase-safe PR submission. Rebases the current branch on origin/main
  immediately before pushing, validates (linters for docs PRs; full suite
  for implementation PRs), resolves minor conflicts automatically, and
  opens a PR. Called by build, plan-issue, bugfix, and learn. Can also be
  invoked conversationally ("pr that for me"). Returns the PR URL.
---

# Skill: Create PR

Centralized PR submission that enforces rebase-before-push on every invocation,
regardless of how the PR is triggered.

## Interface

All parameters are optional. Supply what you have; the skill derives what's
missing from `git log origin/main..HEAD` and the current diff.

| Parameter | Description |
|---|---|
| `title` | PR title (derived from commits if omitted) |
| `body` | Full PR body text (derived from diff if omitted) |
| `type` | `docs` or `implementation` (inferred from changed files if omitted) |
| `labels` | Space-separated label names (e.g., `"size:M specs-notes"`) |
| `issue_number` | Issue to close (parsed from branch name if omitted; optional) |
| `draft` | `true` to open as draft (default: `false`) |

**Returns**: the PR URL as a string. Callers own `archive-history`.

---

## Phase 1 — Pre-flight Checks

### 1a — Uncommitted changes

```bash
git status --porcelain
```

- **Called from another skill** (clean tree expected): if any uncommitted
  changes are detected, hard stop with:
  > "❌ Uncommitted changes detected. Commit or stash before calling create-pr."
- **Conversational invocation** (user said "pr that for me"): ask the user
  what to do:
  > "There are uncommitted changes. Should I (a) commit them now with an
  > auto-generated message, (b) stash and discard after the PR, or (c) abort?"

  Wait for the user's answer and act accordingly before continuing.

### 1b — Infer missing parameters

If any required values were not passed by the caller, derive them now:

```bash
# Commits on this branch not on main
git log origin/main..HEAD --oneline

# Full diff
git diff origin/main..HEAD

# Changed files — determines PR type if not provided
git diff --name-only origin/main..HEAD
```

**Type inference rule**: if any `.py` file appears in the diff → `implementation`;
otherwise → `docs`.

**Issue number inference**: if not provided, parse from the branch name
(e.g., `task/1466-create-pr-skill` → `1466`, `plan/1362-lifecycle-staged` → `1362`).
If still absent, proceed without a closing reference.

**Title inference** (if not provided): use the most recent commit subject,
stripping any commit-hash prefix.

**Body inference** (if not provided): compose using the template from
`.agents/skills/shared/pr-body-guide.md` for the inferred type.
For `implementation`: Summary + Changes + Verification sections.
For `docs`: Summary + Changes sections (no Verification).

---

## Phase 2 — Rebase

```bash
git fetch origin main
git rebase origin/main
```

### Conflict handling

If the rebase exits cleanly, proceed to Phase 3.

If the rebase reports conflicts:

1. **Attempt auto-resolution**: read each conflict marker in the affected
   files. For conflicts that are clearly mechanical (whitespace differences,
   non-overlapping additions, comment-only changes), resolve them directly
   and continue the rebase:

   ```bash
   git add <resolved-file>
   git rebase --continue
   ```

2. **If ambiguous conflicts remain** (both sides modified the same logic,
   semantic collision): abort immediately:

   ```bash
   git rebase --abort
   ```

   Then open a draft PR with conflict notes (see Phase 4, draft-with-conflict
   path below). **Do not push the un-rebased branch.**

---

## Phase 3 — Post-Rebase Validation

Run the appropriate suite based on PR type:

**Docs PR** (`type: docs`):

```bash
# Linters only — no Python changed
uv run black --check .
uv run flake8
uv run mypy vultron
uv run pyright
```

If any linter fails, fix the failure, stage, and amend the relevant commit
before proceeding. Do not open a PR with lint failures.

**Implementation PR** (`type: implementation`):

Invoke `format-code`, then `run-linters`, then `run-tests`.

If any step fails, fix, re-validate, and continue. Do not open a PR with
failing tests or lint errors.

---

## Phase 4 — Push and Open PR

### Happy path

```bash
git push "https://x-access-token:$(gh auth token)@github.com/CERTCC/Vultron.git" \
  "$(git branch --show-current)"

gh pr create --repo CERTCC/Vultron \
  --head "$(git branch --show-current)" \
  --base main \
  --title "<title>" \
  --body "<body>" \
  --label "<labels>"
```

Capture and return the PR URL emitted by `gh pr create`.

### Draft-with-conflict path (unresolvable rebase)

If Phase 2 aborted with unresolvable conflicts:

1. Push the **un-rebased** branch as-is:

   ```bash
   git push "https://x-access-token:$(gh auth token)@github.com/CERTCC/Vultron.git" \
     "$(git branch --show-current)"
   ```

2. Open a **draft** PR with conflict notes and `needs-rebase` label:

   ```bash
   gh pr create --repo CERTCC/Vultron \
     --head "$(git branch --show-current)" \
     --base main \
     --title "<title> [NEEDS REBASE]" \
     --body "<!-- needs-rebase -->
   > ⚠️ **This PR requires manual conflict resolution before it can be merged.**
   >
   > The \`create-pr\` skill attempted an automatic rebase on \`origin/main\`
   > but encountered conflicts it could not resolve:
   >
   > **Conflicting files:**
   > <list each conflicting file>
   >
   > **Nature of each conflict:**
   > <one line per file: what both sides changed>
   >
   > **To resolve:**
   > \`\`\`bash
   > git fetch origin main
   > git rebase origin/main
   > # resolve conflicts in the files listed above
   > git rebase --continue
   > git push --force-with-lease
   > \`\`\`
   > Then convert this draft PR to ready for review.

   <original PR body below>

   <body>" \
     --draft \
     --label "needs-rebase"
   ```

3. Tell the user the draft PR URL and what needs resolving.
4. Return the draft PR URL.

---

## Constraints

- **Never push before rebasing.** The rebase step in Phase 2 is mandatory
  and must happen immediately before the push in Phase 4.
- **Never open a non-draft PR with lint failures or failing tests.**
- **Callers own `archive-history`.** This skill does not call it.
- If called from another skill, a dirty working tree is a hard stop, not a
  prompt — callers must arrive with a clean tree.
