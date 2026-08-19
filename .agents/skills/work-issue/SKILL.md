---
name: work-issue
description: >
  Universal entry point for any GitHub issue. Auto-detects issue type via
  GraphQL and routes to the right workflow: Bug → bugfix (test-first, gated
  clarification); Task/Feature → build (priority-queue, implementation);
  Idea/Concern/Epic → plan-issue (interview, docs, impl-issue creation).
  Use when the user says "work on", "fix", "implement", "plan", or "do" an
  issue number, or asks what to work on next.
---

# Skill: Work Issue

Thin router. Detects issue type via GraphQL and delegates to `bugfix`,
`build`, or `plan-issue` without duplicating their logic.

## Phase 0 — Parse Input

Collect issue numbers from the invocation arguments.

- **No issue number** → Phase 0b.
- **One issue number** → Phase 1.
- **Multiple issue numbers** → Phase 1 (type-check all before routing).

### Phase 0b — Type-Category Picker

Use `ask_user` to ask which category the user wants to work on:

> Which type of issue would you like to work on?  
> `[Bug]` fix a defect  
> `[Task / Feature]` implement planned work  
> `[Idea / Concern / Epic]` plan or decompose an issue

Then load the matched skill file and follow its own selection logic from its
natural starting point — the issue number is not yet known, so the sub-skill's
own picker runs as normal:

| Selection | Load and follow | Entry point |
|---|---|---|
| Bug | `.claude/skills/bugfix/SKILL.md` | Phase 1 — its own Bug picker |
| Task / Feature | `.claude/skills/build/SKILL.md` | Phase 2 — its own Now-Epic auto-select |
| Idea / Concern / Epic | `.claude/skills/plan-issue/SKILL.md` | Phase 0 — its own multi-type picker |

## Phase 1 — Detect Type

For each issue number, fetch the type via GraphQL:

```bash
ISSUE_TYPE=$(bash .agents/skills/shared/query-issue-type.sh "${ISSUE_NUMBER}" \
  | jq -r '.data.repository.issue.issueType.name // ""')
```

**Unknown type** — if the result is empty or not one of the six supported
values, stop immediately:

```text
❌ #N has unrecognized type "<VALUE>".
Supported types: Bug, Task, Feature, Idea, Concern, Epic.
```

**Mixed types** (multiple issues only) — if not all issues map to the same
skill path, stop immediately:

```text
❌ Mixed issue types: #N (TypeA) → <path>, #M (TypeB) → <path>.
work-issue handles one type-path per run. Invoke /work-issue separately for each.
```

## Phase 2 — Route

Read the matched skill file and follow it **as if the user had invoked that
skill directly with the same issue number(s)**. All invocation arguments pass
through unchanged. The sub-skill's own issue-number-provided shortcuts apply
(e.g. bugfix skips its picker when an issue number is given; build uses the
explicit issue directly; plan-issue skips Phase 0).

| Issue type | Load and follow |
|---|---|
| Bug | `.claude/skills/bugfix/SKILL.md` |
| Task | `.claude/skills/build/SKILL.md` |
| Feature | `.claude/skills/build/SKILL.md` |
| Idea | `.claude/skills/plan-issue/SKILL.md` |
| Concern | `.claude/skills/plan-issue/SKILL.md` |
| Epic | `.claude/skills/plan-issue/SKILL.md` |
