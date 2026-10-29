---
name: manage-github-issue
description: >
  Create or update a GitHub Issue with structured relationships (parent/child
  sub-issues, blocking/blocked-by) using the GraphQL API. Idempotent for all
  relationship wiring. Strips legacy body-text markers ("Blocked by #N",
  "Blocks #N", "Parent: #N") when structured relationships are applied. Its
  script refuses to create an issue without one theme, a `Theme:` line, and a
  same-theme parent. Create issues through `create-issue`, which calls this;
  call this directly to update an issue or wire its relationships.
---

# Skill: Manage GitHub Issue

Create or update a GitHub Issue and wire structured relationships via GraphQL.
All relationship operations are **idempotent** — existing relationships are
checked and skipped before adding. Legacy body-text markers are stripped when
structured relationships are wired.

**Never embed relationship information in the issue body as text.**

**To create an issue, use the `create-issue` skill.** It decides the type,
theme, `Theme:` line, and same-theme parent that this script's create mode
requires, then calls it (`create-issue` Phase 7 shows the call). Other skills
never call the create mode themselves.

## Quick Start (helper script)

```bash
# Update an existing issue — wire relationships
.agents/skills/manage-github-issue/manage_github_issue.sh \
  --issue-number 99 \
  --blocked-by "50 51" \
  --blocks "100 101" \
  --clean-body

# Wire sub-issues onto a parent
.agents/skills/manage-github-issue/manage_github_issue.sh \
  --issue-number 42 \
  --sub-issue 99 \
  --sub-issue 100
```

## Parameters

| Parameter | Default | Description |
|---|---|---|
| `--issue-number` | — | Issue # to update; omit to create |
| `--title` | — | Title (required for create) |
| `--body` | — | Body markdown |
| `--label` | — | Label name (repeatable, or comma-separated); on create, exactly one must be a `theme:` label |
| `--assignees` | — | Comma-separated GitHub usernames |
| `--issue-type-id` | — | GraphQL node ID of the issue type (**required** on create) |
| `--parent` | — | Parent epic issue number (**required** on create; must be open and carry the issue's theme) |
| `--milestone` | — | Milestone number (optional; use only for a release milestone) |
| `--blocked-by` | — | Space-separated issue numbers that block this one |
| `--blocks` | — | Space-separated issue numbers this one blocks |
| `--sub-issue` | — | Child issue number (repeatable) |
| `--clean-body` | — | Strip legacy body-text relationship markers |
| `--opened-as` | — | Why an agent opened the issue: `excursion`, `separate-defect`, `debt`, `deferred`; applies the `opened:<reason>` label (**required** on create unless `--planned`) |
| `--where` | — | File, directory, or spec the issue concerns (**required** with `--opened-as debt`) |
| `--planned` | — | Issue comes from planning or a user request (**required** on create unless `--opened-as`) |

> **On create**, `--issue-type-id`, `--parent`, and one of
> `--opened-as` / `--planned` are all required, and the theme gate requires
> exactly one active `theme:` label, a `Theme: <label> — <outcome>` line in
> `--body`, and a parent carrying that theme. The script exits non-zero,
> creating nothing, if any is missing. See
> `shared/issue-creation-requirements.md` § "The script gate".

Outputs: issue number on **stdout**; progress messages on **stderr**.

## Conventions

- Always use this skill (or its helper script) when creating/updating issues
  with relationships. Never write `Blocked by #N`, `Blocks #N`, or
  `Parent: #N` into an issue body.
- When detecting blockers before claiming work (e.g., in `build`), query
  `blockedBy { nodes { number } }` via GraphQL — do not parse issue body text.
- `--blocks` and `--blocked-by` are inverses: `--blocks 50` on issue 42 is
  equivalent to `--blocked-by 42` on issue 50.
- **Never pass backtick-containing markdown in a double-quoted `--body` string.**
  Backticks inside `"..."` are shell-interpreted and render as `\`` on GitHub.
  Always pass bodies via a single-quoted heredoc:

  ```bash
  --body "$(cat <<'EOF'
  Use `code` freely here — no escaping needed.
  EOF
  )"
  ```

  This applies to `--body` on `gh issue comment`, `gh pr create`,
  `gh issue edit`, and any other CLI command accepting markdown.

## Reference

For full GraphQL examples, API discovery commands, issue type IDs, and
idempotency implementation details, see `REFERENCE.md` in this directory.
