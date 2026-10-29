---
name: create-issue
description: >
  The only way agents create a GitHub issue. Creates or updates one Bug, Task,
  Feature, Idea, or Concern from freeform input or a calling skill's fields:
  infers the type, checks for duplicates, picks the one `theme:` label and
  writes the `Theme:` line, and routes the issue to an Epic with the same
  theme, calving an auto-calved Someday Epic when none fits and no user is
  present. Use when a developer wants to capture an item, or any skill files
  an issue (a finding, a prerequisite, a deferred item, an impl issue).
---

# Skill: Create Issue

Create one structured GitHub issue that already passes every theme rule, so
`theme-fit` never has to report it. Every skill that files an issue calls this
skill; none calls `manage_github_issue.sh` to create, `createIssue`, or
`gh issue create` itself. The rules come from `notes/epic-themes.md`
(PAD-02-014 to PAD-02-018) and `shared/issue-creation-requirements.md`.

`manage_github_issue.sh` enforces the result on create: it refuses an issue
without exactly one active catalog theme, without a `Theme:` line naming it,
or under a parent that does not carry that theme. A refusal means a step
below went wrong; fix the input and run the step again. Never work around it.

## Inputs

A user describes the item in Phase 0. A calling skill passes what it already
knows instead, and this skill asks only for what is missing:

| Input | Required | Notes |
|---|---|---|
| Description or drafted fields | yes | the Phase 3 fields for the type |
| Type | no | inferred in Phase 1 when absent |
| Reason | yes | `planned`, or `opened-as <excursion\|separate-defect\|debt\|deferred>`; `debt` also needs `where` |
| `size:` | Bug and Task | from `pr-size --acs <N>` (`shared/sizing.md`) |
| Blockers | no | `blocked-by` and `blocks` issue numbers |
| Suggested parent | no | the Epic the caller expects; used only if it carries the theme (Phase 5) |
| User present | yes | whether a person can answer questions now |

When no user is present, never stop to ask: take the recommended answer at
each step and report every choice in Phase 8.

## Workflow

### Phase 0 — Describe

If no caller supplied the description, ask in plain text: "Describe the item
you want to capture."

### Phase 1 — Infer the Type

Infer the type from the shape of the work, by the rule in
`shared/issue-creation-requirements.md` § "Determining the right values". The
reason (for example `debt`) does not decide the type. State the type with a
one-line rationale. Ask only when it is unclear and a user is present, with
`ask_user` choices: the inferred type (recommended), another type, or cancel.

If the finding holds both a ready fix and an open question, split it into two
issues and run Phases 2 to 8 for each, wiring the blocker if one gates the
other.

### Phase 2 — Duplicate Scan

List open `Bug`, `Task`, `Feature`, `Idea`, and `Concern` issues and find
near-duplicates by title and body. When a strong match exists, recommend
updating it. With a user present, ask: update existing (recommended), create
new anyway, or cancel. Unattended, update the match and report it.

Cross-type updates keep the existing issue's type.

### Phase 3 — Draft the Fields

Propose a concrete draft first, then let a present user accept or refine each
field. A caller's fields are the draft.

- **Concern**: Summary, Surface Symptom vs. Underlying Problem, Category,
  Severity, Evidence, Impact if Ignored, Suggested Action.
- **Idea**: Summary, Motivation, Rough Approach (optional), References
  (optional; seed related issue, spec, and ADR links when possible).
- **Bug, Task, and Feature**: Summary, Evidence or Context, Fix or Approach,
  Acceptance Criteria, and the required `Governing specs:` line
  (`shared/issue-creation-requirements.md` § "Governing specs").

For **Surface Symptom vs. Underlying Problem**, draw out both halves: the
symptom-level reading someone would stop at, and the deeper problem. Note which
parts of the current design are correct and should stay. Omit the field only
when the two readings are the same. Ideas do not take this field; Motivation
and Rough Approach serve the same purpose.

### Phase 4 — Pick the Theme

Read the catalog block in `notes/epic-themes.md` and pick **one** active theme
by the outcome this issue's own content delivers (PAD-02-014, PAD-02-016):

- Classify by outcome, never by the mechanism used or the work that found it.
  A production bug found while working a test Epic is
  `theme:protocol-correctness`, not `theme:test-and-ci`.
- Do not copy the suggested parent's or the caller's theme. Judge the issue.
- Check the theme's `out_of_bounds` list; if the issue matches an entry, take
  the theme that entry names.
- If two themes fit, the issue does two things: split it, or take the outcome
  its acceptance criteria test.
- Never pick a theme with `status: retiring`.

Write the reason line as the **first line** of the body (PAD-02-018):

```text
Theme: theme:<name> — <what this issue delivers toward that theme>.
```

The outcome is this issue's, not the catalog outcome copied.

### Phase 5 — Route to a Same-Theme Epic

Every issue gets a parent. Candidates are the open Epics that carry the
Phase 4 theme; an Epic in another theme is never a candidate, however close
its title.

1. **Suggested parent.** If the caller suggested an Epic that carries the
   theme and whose design idea the issue advances, use it.
2. **Otherwise, route** with `calve-epics` Mode 1 ("Route an issue onto the
   forest"), restricted to the candidates: match by design grain, inherit the
   Epic's tier. Read the full open-Epic list, never a truncated one.
   - **One clear match**: use it.
   - **Several plausible**: with a user present, ask with `ask_user`, one line
     of rationale per Epic; unattended, take the best match and report it.
   - **None fits**: go to step 3.
3. **No Epic fits.**
   - **User present**: ask whether to pick an Epic anyway (list the
     candidates) or calve a new one. Calving goes through `calve-epics`
     Mode 2, which the user confirms.
   - **No user present**: calve a Someday Epic yourself through `create-epic`
     with the Phase 4 theme. Its body starts with a `Theme:` line, states the
     one-sentence design idea the issue advances, and carries the line
     `<!-- auto-calved -->` (`notes/epic-themes.md` § "The Structural
     Check"). Report the new Epic in Phase 8 so a person reviews it
     (PAD-02-024).

Never create the issue without a parent, and never under an Epic whose theme
differs: the script refuses both.

### Phase 6 — Build the Title and Body

Generate a clean title with no `[Bug]`, `[Idea]`, or `[Concern]` prefix. An
Idea or Concern body follows the sections of its GitHub template; a Bug, Task,
or Feature body uses the Phase 3 fields as headings. The `Theme:` line comes
first. Never write `Blocked by #N`, `Parent: #N`, or similar into the body:
relationships are wired structurally.

### Phase 7 — Create or Update

Pass the body through a single-quoted heredoc so backticks survive.

```bash
TYPE_ID=$(bash .agents/skills/shared/board-id.sh issue-type <Type>)
NUM=$(.agents/skills/manage-github-issue/manage_github_issue.sh \
  --title "${TITLE}" \
  --body "$(cat <<'EOF'
Theme: theme:<name> — <outcome>.

## Summary
...
EOF
)" \
  --issue-type-id "${TYPE_ID}" \
  --label "theme:<name>" \
  --label "size:<S|M|L>" \
  --parent "${EPIC}" \
  --planned)        # or: --opened-as <reason> [--where <text>]
```

- Add `--label bug`, `idea`, or `concern` for those types; a Task or Feature
  takes none. Never set `size:` on an Idea or a Concern.
- Add `--blocked-by N` and `--blocks N` for the caller's blockers.
- **Update**: pass `--issue-number N` with the new title or body; keep the
  type. Keep the `Theme:` line; if the theme changed, swap the label with
  `gh issue edit N --remove-label <old> --add-label <new>` and move the issue
  to a same-theme Epic by Phase 5. Post a short refresh comment.

### Phase 8 — Board and Report

Add a new issue to Project #24 with **no** `Schedule` (PAD-02-001): its tier
is its Epic's.

```bash
gh project item-add 24 --owner CERTCC \
  --url "https://github.com/CERTCC/Vultron/issues/${NUM}"
```

Return the issue number to a calling skill, and print one line:

```text
<Type> #<N> — "<title>" — <created|updated> — <theme> under Epic #<E>. <URL>
```

When this run calved an Epic, add a second line naming it as auto-calved and
awaiting review. When it ran unattended, list each choice it made for a user
(type, duplicate, Epic).

## Constraints

- Ask questions per `.agents/skills/shared/asking-the-user.md`: `ask_user` for
  discrete choices, plain text for open-ended ones.
- Create only through `manage_github_issue.sh`, and Epics only through
  `create-epic`. Never `gh issue create` or a raw `createIssue` mutation.
- One theme, one `Theme:` line, one parent with that theme, every time.
- Do not write to `specs/`, `notes/`, or `AGENTS.md`, and do not open a PR.
