---
name: new-item
description: >
  Create or update a single GitHub Bug, Task, Idea, or Concern issue from
  freeform input, with type inference, duplicate checks, and mandatory Epic
  parent wiring. Use when a developer wants to quickly capture a new item, or a
  skill files a finding it will not fix now.
---

# Skill: New Item

Capture one freeform item as a structured GitHub `type:Bug`, `type:Task`,
`type:Idea`, or `type:Concern` issue. See `.agents/skills/shared/README.md` for
IDs.

## Workflow

### Phase 0 — Describe

Ask in plain text (an open-ended question): "Describe the item you want to
capture."

### Phase 1 — Infer + Confirm Type

Infer the type from the shape of the work, by the rule in
`shared/issue-creation-requirements.md` § "Determining the right values". A
caller's **Opened as** reason (such as `debt`) does not decide the type.

If the type is clear, use it and state the one-line rationale. Ask only when it
is unclear, with `ask_user` choices:

1. Use inferred type (Recommended)
2. Switch to another type (Bug, Task, Idea, Concern)
3. Cancel

If switched, continue with the same description. If the finding holds both a
ready fix and an open question, split it into two issues and run Phases 2–8 for
each.

### Phase 2 — Duplicate Scan (all types)

List open `Bug`, `Task`, `Idea`, and `Concern` issues and find near-duplicates
by title/body similarity. Recommend update-existing when a strong match exists.

Ask with `ask_user`:

1. Update existing issue (Recommended)
2. Create new issue anyway
3. Cancel

Cross-type updates are allowed; keep the existing issue type unchanged.

### Phase 3 — Draft-First Interview

Use `grill-me` style, but always propose a concrete draft first, then ask the
user to accept or refine each field.

- **Concern fields**: Summary, Surface Symptom vs. Underlying Problem, Category,
  Severity, Evidence, Impact if Ignored, Suggested Action.
- **Idea fields**: Summary, Motivation, Rough Approach (optional),
  References (optional; auto-seed related issue/spec/ADR links when possible).
- **Bug and Task fields**: Summary, Evidence or Context, Fix or Approach,
  Acceptance Criteria, and the required `Governing specs:` line
  (`shared/issue-creation-requirements.md` § "Governing specs").

For the **Surface Symptom vs. Underlying Problem** field, actively draw out
both halves: the naive, symptom-level reading someone would stop at, and the
deeper problem the concern is really about. Infer them from the description
when context allows; otherwise ask directly. Capture, when relevant, which
parts of the current design are already correct and should be left untouched.
Omit only when there is genuinely no gap between the surface reading and the
underlying problem. This field is Concern-only by design — an Idea's
Motivation/Rough Approach split already serves the equivalent guardrail, so
do not add a symptom/root frame to Ideas.

### Phase 4 — Epic Parent Selection

**A parent epic is required for all new issues.** Query open Epic issues and
rank likely matches. Present top ~5 suggestions, "Specify other epic number",
and **"Create new epic (none of these fit)"** as explicit choices. If the user
provides another issue number, validate it is an open Epic; re-prompt until
valid. Do **not** offer a "None / skip" option — an issue without a parent epic
is invisible to sprint planning and prioritisation.

If the user selects "Create new epic (none of these fit)", do not create the
issue yet: invoke `calve-epics` Mode 2 to propose a new epic, confirm it with
the user, and then proceed with that new epic as the parent. Allow at most one
parent epic.

### Phase 5 — Build Title + Body

Generate a clean title (no `[Bug]` / `[Idea]` / `[Concern]` prefix) and body
matching the corresponding GitHub template sections.

### Phase 6 — Create or Update

Use `.agents/skills/manage-github-issue/manage_github_issue.sh`.

- **Create**: set the issue type ID, apply its label (`bug`, `idea`, or
  `concern`; a Task takes none), wire parent epic, and pass
  `--planned`. When the caller supplies **Opened as** (for example `debt` with a
  `--where`), pass `--opened-as <reason> [--where <text>]` instead of `--planned`.
- **Update**: update title/body and optionally parent epic; do not change issue
  type. Post a refresh comment after updating.

### Phase 7 — Add to Project #24 (new issues only)

Add new issues to Project #24 **without** setting Schedule (leave unset):

```bash
PROJECT_ID=$(bash .agents/skills/shared/board-id.sh project)
gh api graphql -f query="mutation {
  addProjectV2ItemById(input: {
    projectId: \"${PROJECT_ID}\"
    contentId: \"${ISSUE_NODE_ID}\"
  }) { item { id } }
}"
```

### Phase 8 — Confirm

Print one line:
`✅ <Bug|Task|Idea|Concern> issue #<N> — "<title>" — <created|updated>. <URL>`

## Constraints

- Ask questions per `.agents/skills/shared/asking-the-user.md`: `ask_user` for
  discrete choices, plain text for open-ended ones.
- Use `manage-github-issue` for issue create/update + parent wiring.
- Do not write to `specs/`, `notes/`, `AGENTS.md`, or open a PR.
- Do not assign `size:` labels here.
