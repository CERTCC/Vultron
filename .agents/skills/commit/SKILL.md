---
name: commit
description: >
  Thin git stage-and-commit wrapper. Stages the specified files and commits
  with a clear message and the required Co-authored-by trailer. Does not
  perform finalization (history updates, plan cleanup) — the caller owns that.
  Use after all finalization and validation steps are complete.
---

# Skill: Commit

Stage and commit changes with the required Co-authored-by trailer. This skill
does only one thing: git add + git commit. The caller is responsible for all
finalization steps (updating history files, cleaning plan files, running
linters and tests) before invoking this skill.

## Procedure

### Step 1 — Verify working tree

Run `git status` and confirm:

- Only the expected files are staged or modified.
- No unintended changes are present.

### Step 2 — Stage files

```bash
git add <files>
```

Stage only the files changed by the current task. Do not use `git add -A`
unless every change in the working tree belongs to this commit.

### Step 3 — Commit

```bash
git commit -m "<subject line>

<body: what changed and why, as bullet points>

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

Commit message conventions:

- Subject line: imperative mood, ≤72 characters, no trailing period
- Body: bullet points describing what changed and why
- Always include the `Co-authored-by` trailer as the last line

## Constraints

- Do not run `git push` — that is the user's responsibility.
- Do not stage unrelated files.
- Never amend an existing commit unless the user explicitly asks.
- Run all validation (`format-code`, `run-linters`, `run-tests`,
  `format-markdown`) and complete all finalization before calling this skill.
