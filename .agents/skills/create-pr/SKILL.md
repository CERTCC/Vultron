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

**Returns**: the PR URL as a string. Callers own `archive-history`, and for
implementation PRs they own replacing the `Docs:` placeholder (Phase 1c).

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

**Body inference** (if not provided): compose using the exact scaffold below
(also in `.agents/skills/shared/pr-body-guide.md`). Do not invent different
section names — use these verbatim.

For `implementation`:

```markdown
- Closes #N
<!-- ⚠️  MUST BE FIRST — before any ## header -->

## Summary

<1–2 sentences, present tense>

## Changes

- **`path/to/file.py`**: <what changed and why>

## Specs

<Spec manifest from deepen-context, verbatim>

## Docs

Docs: pending check-docs-sync

## Verification

- All N unit tests pass (M new)
- ruff, mypy, pyright clean
```

If the caller supplied no Spec manifest, write `Spec manifest: not provided —
deepen-context was not run` under `## Specs` rather than omitting the section;
reviewers flag a missing manifest.

For `docs`:

```markdown
- Closes #N
<!-- ⚠️  MUST BE FIRST — before any ## header -->

## Summary

<1–2 sentences>

## Changes

- **`path/to/file.md`**: <what changed>
```

The `Closes #N` bullet **must be the very first line** of the body string
passed to `gh pr create --body`. If it ends up after a `##` header, GitHub
will not link the issue in the sidebar and triage will flag a FAIL.

### 1c — Docs placeholder (implementation PRs)

Every implementation or bug-fix PR body carries a `Docs:` line (PD-03-008;
scope defined in `.agents/skills/shared/pr-body-guide.md` § "Implementation PR
rules"), whether the body was inferred above or supplied by the caller. Apply
this whenever `type` is `implementation` (passed or inferred) **or** the
closed issue is a `Task`, `Feature`, or `Bug` — a skill-only or docs-only PR
that closes a Task is still in scope:

```bash
bash .agents/skills/shared/query-issue-type.sh <ISSUE_NUMBER> \
  | jq -r '.data.repository.issue.issueType.name'
```

If the body has no line beginning `Docs:`, insert this section immediately
before `## Verification` (or at the end of the body if there is no
Verification section):

```markdown
## Docs

Docs: pending check-docs-sync
```

A caller-supplied `Docs:` line is left as written. The placeholder is not a
final value: the caller runs `check-docs-sync` after the push and replaces it
with one of the final forms in `.agents/skills/shared/pr-body-guide.md`
§ "Implementation PR rules". A `docs` PR that closes no Task, Feature, or
Bug issue carries no `Docs:` line.

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
# Linters only — no Python changed. Each tool reads its scope from config.
uv run ruff check && uv run ruff format --check
uv run mypy
uv run pyright
```

If any linter fails, fix the failure, stage, and amend the relevant commit
before proceeding. Do not open a PR with lint failures.

**Implementation PR** (`type: implementation`):

```bash
uv run ruff check --fix && uv run ruff format
uv run ruff check && uv run mypy && uv run pyright
uv run pytest --tb=short > /tmp/pytest-unit.log 2>&1; rc=$?; tail -5 /tmp/pytest-unit.log; echo "exit: $rc"; (exit $rc)
uv run pytest -m integration --tb=short > /tmp/pytest-integration.log 2>&1; rc=$?; tail -5 /tmp/pytest-integration.log; echo "exit: $rc"; (exit $rc)
```

Both suites must pass. The first pytest command covers the unit suite
(integration tests excluded by `addopts`); the second explicitly runs the
integration suite so demo-layer regressions are caught before the PR opens.

If any step fails, fix, re-validate, and continue. Do not open a PR with
failing tests or lint errors.

---

## Phase 4 — Push and Open PR

### Happy path

```bash
git push -u origin HEAD

gh pr create --repo CERTCC/Vultron \
  --head "$(git branch --show-current)" \
  --base main \
  --title "<title>" \
  --body "<body>" \
  --label "<labels>"
```

Capture and return the PR URL emitted by `gh pr create`.

Always push with `-u` to the named remote `origin`. Without `-u` the branch
gets no upstream, so every later bare `git push` fails ("has no upstream
branch"). Never push to a token-embedded URL: with `-u`, git would record that
URL — token included — as the branch's remote in `.git/config` (#3893).

### Draft-with-conflict path (unresolvable conflicts)

If Phase 2 exited with code `1` (cherry-pick conflict): push the un-freshened
branch as-is with the same `git push -u origin HEAD`, then open a draft PR with
`needs-rebase` label per [REFERENCE.md](REFERENCE.md) § "Conflict PR template".

---

## Constraints

- **Never push before freshening.** The `freshen-branch.sh` step in Phase 2 is
  mandatory and must run immediately before the push in Phase 4.
- **Never open a non-draft PR with lint failures or failing tests.**
- **Callers own `archive-history`.** This skill does not call it.
- **Every implementation PR body gets a `Docs:` line** (Phase 1c). This skill
  writes the placeholder; it never runs `check-docs-sync` itself.
- If called from another skill, a dirty working tree is a hard stop, not a
  prompt — callers must arrive with a clean tree.
