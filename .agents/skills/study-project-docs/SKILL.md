---
name: study-project-docs
description: >
  Load all specs and read key project context files so the agent has a
  complete picture before doing any implementation, design, or documentation
  work. Invokes load-specs and reads plan/, docs/adr/, notes/, AGENTS.md,
  docs/reference/codebase/, and docs/reference/glossary.md.
  Run this at the start of every workflow skill.
---

# Skill: Study Project Docs

Load the full specification set and read key project context so the agent can
work accurately without guessing. This is the standard "orient yourself" step
that all workflow skills (`build`, `bugfix`, `learn`, `ingest-idea`) run
before doing anything else.

## Procedure

### Step 0 — Read the ubiquitous language glossary

Read `docs/reference/glossary.md` **before** loading specs. This establishes
the domain vocabulary used throughout all requirements, notes, and ADRs.

### Step 1 — Load specs

Invoke the `load-specs` skill (run `uv run spec-dump`). Capture the JSON
output. Do **not** read raw `specs/*.yaml` files directly.

### Step 2 — Read plan context

Read the following (do **not** recurse into `plan/history/`):

- `plan/BUILD_LEARNINGS.md` — ephemeral build/bugfix observations (queue for `learn`)

Then query Project #24 ("Vultron Planning") for open items with `Schedule=Now`
to understand current top-priority work:

```bash
gh api graphql --jq '
  .data.node.items.nodes[]
  | select(.content.state == "OPEN")
  | {
      number: .content.number,
      title:  .content.title,
      type:   .content.issueType.name,
      schedule: (
        .fieldValues.nodes[]
        | select(.field.name == "Schedule")
        | .name
      )
    }
  | select(.schedule == "Now")
  | "#\(.number) [\(.type)]: \(.title)"
' -f query='{
  node(id: "PVT_kwDOAjf0s84BZnre") {
    ... on ProjectV2 {
      items(first: 100) {
        nodes {
          content { ... on Issue { number title state issueType { name } } }
          fieldValues(first: 10) { nodes {
            ... on ProjectV2ItemFieldSingleSelectValue {
              name field { ... on ProjectV2SingleSelectField { name } }
            }
          }}
        }
      }
    }
  }
}'
```

> **`plan/history/` is excluded from this step.** It is an archive of
> completed work, not active planning context. Read it only when specifically
> investigating historical changes or extracting lessons from prior
> implementation phases (e.g., during the `learn` skill).

### Step 3 — Read design documentation

Read in parallel:

- `docs/adr/` directory listing, then each relevant ADR
- `notes/README.md`, then any `notes/*.md` files relevant to the current task
- `AGENTS.md` — agent rules and conventions
- `docs/reference/codebase/index.md` — codebase reference overview
- `docs/reference/codebase/ARCHITECTURE.md` — system flow and layer rules
- `docs/reference/codebase/STRUCTURE.md` — top-level module map and entry points
- `docs/reference/codebase/CONVENTIONS.md` — naming, formatting, import rules

Read the following codebase reference files **only when relevant to the task**:

- `docs/reference/codebase/STACK.md` — when adding or evaluating dependencies
- `docs/reference/codebase/TESTING.md` — when writing or reviewing tests
- `docs/reference/codebase/CONCERNS.md` — when assessing risk or technical debt
- `docs/reference/codebase/INTEGRATIONS.md` — when working on external integrations

### Step 4 — Scan the codebase

Search `vultron/` and `test/` to verify assumptions about what is currently
implemented. Do not assert missing functionality without evidence from code
search.

## Notes

- `BUILD_LEARNINGS.md` is an ephemeral queue. Any critical insight
  in it **must be preserved elsewhere** before the session ends. Ideas are
  tracked as GitHub Idea-type issues — query them with `gh issue list` when
  needed.
- Do not skip this skill for "small" tasks — it ensures constraints from
  cross-cutting specs (`ARCH`, `CS`, `TB`, `HP`, `SL`, `EH`) are always in
  context.
- If the task is narrowly scoped, you may skip the ADR deep-read, but always
  run Steps 0, 1, and 2.
