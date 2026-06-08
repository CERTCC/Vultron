---
name: new-item
description: >
  Create or update a single GitHub Idea or Concern issue from freeform input,
  with type inference, duplicate checks, and optional Epic parent wiring. Use
  when a developer wants to quickly capture a new planning item as type:Idea or
  type:Concern.
---

# Skill: New Item

Capture one freeform item as a structured GitHub `type:Idea` or
`type:Concern` issue. See `.agents/skills/shared/README.md` for IDs.

## Workflow

### Phase 0 — Describe

Ask for freeform input via `ask_user`: "Describe the idea or concern you want
to capture."

### Phase 1 — Infer + Confirm Type

Infer `Idea` vs `Concern` with a short rationale from the description.
Confirm with `ask_user` choices:

1. Use inferred type (Recommended)
2. Switch to other type
3. Cancel

If switched, continue with the same description.

### Phase 2 — Duplicate Scan (both types)

List open `Idea` and `Concern` issues and find near-duplicates by title/body
similarity. Recommend update-existing when a strong match exists.

Ask with `ask_user`:

1. Update existing issue (Recommended)
2. Create new issue anyway
3. Cancel

Cross-type updates are allowed; keep the existing issue type unchanged.

### Phase 3 — Draft-First Interview

Use `grill-me` style, but always propose a concrete draft first, then ask the
user to accept or refine each field.

- **Concern fields**: Summary, Category, Severity, Evidence, Impact if Ignored,
  Suggested Action.
- **Idea fields**: Summary, Motivation, Rough Approach (optional),
  References (optional; auto-seed related issue/spec/ADR links when possible).

### Phase 4 — Epic Parent Selection

Query open Epic issues and rank likely matches. Present top ~5 suggestions, plus
"Specify other epic" and "None". If user provides another issue number, validate
it is an open Epic; re-prompt until valid or none selected. Allow at most one
parent epic.

### Phase 5 — Build Title + Body

Generate a clean title (no `[Idea]` / `[Concern]` prefix) and body matching
the corresponding GitHub template sections.

### Phase 6 — Create or Update

Use `.agents/skills/manage-github-issue/manage_github_issue.sh`.

- **Create**: set issue type ID (`Idea` or `Concern`), apply exactly one label
  (`idea` or `concern`), and wire parent epic if chosen.
- **Update**: update title/body and optionally parent epic; do not change issue
  type. Post a refresh comment after updating.

### Phase 7 — Add to Project #24 (new issues only)

Add new issues to Project #24 **without** setting Schedule (leave unset):

```bash
gh api graphql -f query="mutation {
  addProjectV2ItemById(input: {
    projectId: \"PVT_kwDOAjf0s84BZnre\"
    contentId: \"${ISSUE_NODE_ID}\"
  }) { item { id } }
}"
```

### Phase 8 — Confirm

Print one line:
`✅ <Idea|Concern> issue #<N> — "<title>" — <created|updated>. <URL>`

## Constraints

- Use `ask_user` for all user-facing questions.
- Use `manage-github-issue` for issue create/update + parent wiring.
- Do not write to `specs/`, `notes/`, `AGENTS.md`, or open a PR.
- Do not assign `size:` labels here.
