---
name: manage-github-issue
description: >
  Create or update a GitHub Issue with structured relationships (parent/child
  sub-issues, blocking/blocked-by) using the GraphQL API. Idempotent for all
  relationship wiring. Strips legacy body-text markers ("Blocked by #N",
  "Blocks #N", "Parent: #N") when structured relationships are applied. Call
  this skill wherever any other skill creates or modifies issues that carry
  relationships.
---

# Skill: Manage GitHub Issue

Create or update a GitHub Issue and wire structured relationships via GraphQL.
All relationship operations are **idempotent** — existing relationships are
checked and skipped before adding. Legacy body-text markers are stripped when
structured relationships are wired.

**Never embed relationship information in the issue body as text.**

## Quick Start (helper script)

```bash
# Create a new issue (prints issue number to stdout)
ISSUE_NUMBER=$(.agents/skills/manage-github-issue/manage_github_issue.sh \
  --title "Implement X" \
  --body "$(cat body.md)" \
  --label "size:M" \
  --parent 42 \
  --blocked-by 50)

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
| `--label` | — | Comma-separated label names |
| `--assignees` | — | Comma-separated GitHub usernames |
| `--issue-type-id` | — | GraphQL node ID of the issue type |
| `--parent` | — | Parent issue number |
| `--blocked-by` | — | Space-separated issue numbers that block this one |
| `--blocks` | — | Space-separated issue numbers this one blocks |
| `--sub-issue` | — | Child issue number (repeatable) |
| `--clean-body` | — | Strip legacy body-text relationship markers |

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
