# Review Priorities — Reference

## Interview question templates (Phase 4)

For each untracked item, ask one question at a time using `ask_user`.

### Starter question for each item

> "**[Item: `<id>` — `<title>`]**
> This item is open but not referenced in PRIORITIES.md.
> Where should it go?"

Choices (adapt to actual priority blocks present in the file):

- `"Insert into Priority NNN: <existing block title>"` (one choice per
  relevant existing block)
- `"Create a new priority block"`
- `"Defer — not priority now (skip)"`

If the user picks **insert into an existing block**, ask which sub-section if
the block has multiple sub-sections.

If the user picks **create a new priority block**, follow up with:

1. What is the priority number? (show the current gap between adjacent blocks)
2. What is the title for the new block?
3. Write a one-sentence description.

### Batching low-signal items

If multiple untracked items clearly belong to the same existing priority block
(e.g., several bugs obviously related to Priority 471), you may group them in
a single `ask_user` confirmation:

> "I found N items that appear to belong under Priority 471: Bug Fixes and
> Demo Polish — `#NNN`, `#MMM`, …
> Should I add all of them there, or handle some differently?"

Choices: `"Add all to Priority 471"`, `"Handle individually"`.

## PRIORITIES.md format rules

- Priority blocks: `## Priority NNN: Title` (ascending numbers, sparse)
- Sub-issues list item: `- [#NNN](URL) — short description`
- Parent issue cross-reference: `Tracked under parent issue [#NNN](URL).`
- Plain task ID reference: add a `**See also**: TASK-ID` line in the block
  body, or list the task ID inline in the description.
- Completed priorities MUST be archived via `uv run append-history priority`
  before removal; do **not** remove them directly.

## Gap detection rules

A plan task is untracked if its task ID root (e.g., `TASK-AF`) does **not**
appear in PRIORITIES.md. Subtask IDs (e.g., `AF.1`) do not need individual
mentions — the parent task ID is sufficient.

A GitHub issue is untracked if neither `#NNN` nor the full URL appears in
PRIORITIES.md.

Closed GitHub issues are out of scope; only `state: OPEN` issues are
considered.

## Priority number selection

When inserting a new block, choose a number that:

- Is greater than any block it should follow.
- Is less than any block it should precede.
- Leaves at least 5–10 units of headroom on each side for future insertions.

Example: inserting between 473 and 475 → suggest 474.
Inserting between 475 and 500 → suggest 480 or 490.

## What to skip

- Issues labeled `question`, `wontfix`, or `duplicate` without open work.
- Sub-issues whose parent issue is already in PRIORITIES.md and is itself open
  (the parent entry implicitly covers them).
- Tasks in IMPLEMENTATION_PLAN.md that exist solely as sub-items of a
  higher-level task already tracked in PRIORITIES.md.
