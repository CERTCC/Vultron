---
name: create-pr
description: >
  Branch-freshening PR submission. Cherry-picks the task branch onto a fresh
  origin/main base immediately before pushing, validates (linters for docs PRs;
  full suite for implementation PRs), and opens a PR. Called by build,
  plan-issue, bugfix, and learn. Can also be invoked conversationally ("pr that
  for me"). Returns the PR URL.
---

# Skill: Create PR

Centralized PR submission that freshens the task branch onto `origin/main`
before every push, regardless of how the PR is triggered.

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

## Phase 2 — Freshen Branch

Bring the task branch current with `origin/main` by cherry-picking its commits
onto a fresh branch rooted at `origin/main`. This avoids the git sequencer
duplicate-pick bug that `git rebase` triggers on large single-commit branches.

```bash
bash .agents/skills/shared/freshen-branch.sh
```

### Exit codes

| Code | Meaning | Action |
|------|---------|--------|
| `0`  | Branch freshened (or already current) | Proceed to Phase 3 |
| `1`  | Cherry-pick conflict | Open draft PR with `needs-rebase` label (see Phase 4) |
| `2`  | Unexpected error | Stop and investigate |

---

## Phase 3 — Post-Freshen Validation

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

```bash
uv run black vultron/ test/
uv run flake8 vultron/ test/ && uv run mypy && uv run pyright
uv run pytest --tb=short 2>&1 | tail -5
```

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

### Draft-with-conflict path (unresolvable conflicts)

If Phase 2 exited with code `1` (cherry-pick conflict): push the un-freshened
branch as-is, then open a draft PR with `needs-rebase` label per
[REFERENCE.md](REFERENCE.md) § "Conflict PR template".

---

## Constraints

- **Never push before freshening.** The `freshen-branch.sh` step in Phase 2 is
  mandatory and must run immediately before the push in Phase 4.
- **Never open a non-draft PR with lint failures or failing tests.**
- **Callers own `archive-history`.** This skill does not call it.
- If called from another skill, a dirty working tree is a hard stop, not a
  prompt — callers must arrive with a clean tree.
