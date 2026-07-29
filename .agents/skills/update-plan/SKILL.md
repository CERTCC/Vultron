---
name: update-plan
description: >
  Perform a gap analysis between current specs/notes and the codebase, then
  create GitHub Issues for any untracked gaps and add them to Project #24.
  Observations and open questions go directly to notes/ files. Use after
  learn or `plan-issue` has updated specs/notes, and before running build.
---

# Skill: Update Plan

Perform a gap analysis between the current specifications, design notes, and
the actual codebase, then create GitHub Issues for any untracked gaps.

**Constraint**: Do not write new tasks to the plan — all new work items MUST be
GitHub Issues. Do not change
code, tests, `specs/`, or `notes/` (except when writing gap-analysis
observations). Do **not** write to `plan/incoming/learnings/` — that directory
is reserved for `build` and `bugfix`.

**Trigger**: Use after `learn` or `plan-issue` has updated specs or notes,
to translate those changes into concrete GitHub Issues. Also run periodically
to keep open Issues aligned with the codebase.

## Quick Start

1. Invoke `orient-agent` then `deepen-context` to load all specs and context.
2. Run a gap analysis: compare `specs/` + `notes/` against `vultron/` and
   `test/`.
3. For each gap, create a GitHub Issue, then **route it onto the epic it
   belongs to** via the `calve-epics` skill (rather than dropping it flat at
   Someday).
4. Surface any accumulated-mass observations as **calving candidates** for the
   user; do not re-shape epics on your own.
5. Write any significant observations or open questions directly to the
   appropriate `notes/*.md` file (not to `plan/incoming/learnings/`).
6. Invoke `commit`.

## How the roadmap evolves (the glacier model)

This skill generates *snowfall* — new issues precipitated from gap analysis —
and then **routes** each onto the glacier or iceberg (epic) it matches.
Routing is frequent, low-judgment classification and is this skill's job.
**Calving** — deciding where to break off a new schedulable epic, or to fuse,
split, or dissolve existing ones — is architectural judgment that requires a
human. The full model and decision rules live in the **`calve-epics`** skill;
this skill invokes it rather than duplicating that logic. If you only remember
one rule: **route freely, calve only with a human.**

## Workflow

### Phase 1 — Load Context

Invoke the `orient-agent` skill, then `deepen-context` to load all specs,
relevant plan files, docs/adr/, notes/, AGENTS.md, and scan vultron/ and test/.

To understand what has recently been completed and avoid re-adding finished
work, run `uv run show-history --month YYMM` (replacing `YYMM` with the
current year-month, e.g. `2604`) to see what has recently been completed.
Open individual entry files only when their titles suggest relevant context.

### Phase 1b — Resolve GitHub Issues

Fetch open issues from `CERTCC/Vultron` using `github-mcp-server-list_issues`
(state: `OPEN`). This gives a picture of what work is already tracked. When
writing new gap Issues, check this list to avoid creating duplicates.

### Phase 2 — Gap Analysis

Compare the current `specs/` + `notes/` against `vultron/` and `test/`:

- **Missing implementations**: a spec or note says X should exist, but code
  search finds no implementation.
- **Partial implementations**: code exists but tests or edge cases are
  missing.
- **Untested behaviors**: implementation exists but no test covers it.
- **Stale open Issues**: GitHub Issues for things already implemented — close
  these with a comment explaining they are done.
- **Known bugs**: open Bug-type GitHub Issues that block or relate to
  planned work.

> Do not assume missing functionality; confirm via code search first.

### Phase 3a — Create GitHub Issues for gaps, then route them

For each confirmed gap, create a GitHub Issue using the `manage-github-issue`
skill. If the issue has known blockers at creation time, wire them as
structured relationships — do **not** add `Blocked by #N` text to the body.

```bash
ISSUE_NUMBER=$(.agents/skills/manage-github-issue/manage_github_issue.sh \
  --title "<Gap description — one line>" \
  --body "## Summary

<What is missing and why it matters — one paragraph>

## Acceptance Criteria

- [ ] AC-1: <testable criterion>
- [ ] AC-2: <testable criterion>
...

## Reference

Spec: \`specs/<topic>.yaml\` <ID range>" \
  --label "size:<S|M|L>")
  # Add --blocked-by N for known blockers
echo "Created gap issue #${ISSUE_NUMBER}"
```

Set the `size:` label from AC count: 1–2 → `size:S`; 3–6 → `size:M`;
7+ → `size:L`.

Do **not** add tasks to GitHub Issues outside the `manage-github-issue`
workflow documented above.

**Then route each new issue onto the forest.** Do not drop new gap issues flat
at `Schedule=Someday`. Instead, invoke the **`calve-epics`** skill in its
routing mode to land each issue on the epic (glacier or iceberg) it matches:

- The clear-match case is auto-parented onto its epic and inherits that epic's
  Schedule tier.
- An ambiguous match (two or more plausible epics) is presented to the user to
  choose.
- An issue with **no** plausible epic is left at root with `Schedule=Someday`
  and recorded as a **calving candidate** for Phase 3b — do not invent an epic
  for it on your own.

`calve-epics` queries the live Project #24 field/option IDs and delegates the
board mutations, so this skill no longer hardcodes them.

### Phase 3b — Flag calving candidates (do not calve on your own)

The old heuristic — "if 2 or more related gaps, create a parent Task" — cut
epics on convenience (size and superficial theme) rather than on design grain,
and is retired. Grouping issues into a new epic is **calving**, an
architectural act reserved for a human decision.

When routing (3a) surfaces a region that has accumulated coherent mass — a set
of new gaps that realize one design idea with no existing home, or a pile of
root-level orphans — collect them and hand them to the user as calving
candidates via the `calve-epics` skill (Mode 2). State the one-sentence design
idea, list the issues, and let the user confirm the fracture line before any
epic is created. Never create the epic unprompted.

If the forest itself looks muddled (redundant epics, an epic mixing prod-only
and buildable-soon work, a grab-bag with no coherent identity), note it and
recommend a `calve-epics` recrystallization pass (Mode 3) — do not perform it
inline as part of gap analysis.

### Phase 4 — Write Observations to notes/

- Any gap-analysis observations, open questions, clarified assumptions, or
  architectural risks discovered during gap analysis SHOULD be written
  directly to the appropriate `notes/*.md` file.
- Do **not** write these observations to `plan/incoming/learnings/`.
  That directory is reserved for `build` and `bugfix` outputs.

### Phase 5 — Commit

Invoke the `commit` skill. Commit only modified notes/ files with a clear,
specific message (e.g.,
`plan: gap analysis — create N issues, update notes/`).

## Constraints

- Do not modify code or tests.
- Do not write to `plan/incoming/learnings/`.
- Do not speculate about missing functionality; verify with code search first.
- Do not implement anything — that is `build`'s domain.
- Use `uv run append-history implementation` only via `build` — never from
  within `update-plan`.

## Project Board

Issues created by this skill are added to Project #24 ("Vultron Planning") and
routed onto an epic via `calve-epics`, inheriting that epic's Schedule tier.
Only true orphans (no matching epic) stay at `Schedule=Someday` as calving
candidates. Use `review-priorities` to re-tier items, and invoke `calve-epics`
(Mode 2/3) when the epic structure itself needs to change.
