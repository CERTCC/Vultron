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

1. Invoke `orient-agent` (spec map) then `deepen-context` (governing specs
   and context); walk the remaining topics with targeted `spec-dump` loads.
2. Run a gap analysis: compare `specs/` + `notes/` against `vultron/` and
   `test/`.
3. For each gap, **choose the epic it belongs to** (via the `calve-epics`
   skill's routing), then create the GitHub Issue as a sub-issue of that epic.
   An issue is never created at root (PAD-13-002).
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

Invoke the `orient-agent` skill, then `deepen-context` to load the governing
specs, relevant plan files, docs/adr/, notes/, AGENTS.md, and scan vultron/ and
test/.

Gap analysis needs broader spec coverage than one task. Walk the spec map
from `orient-agent` one topic at a time with
`PYTHONPATH= uv run spec-dump --topic <T> --text` rather than printing the
full dump, which is too large to read end to end.

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

Governing specs: <spec/group IDs the gap violates>

## Reference

Spec: \`specs/<topic>.yaml\`" \
  --issue-type-id "$(bash .agents/skills/shared/board-id.sh issue-type Task)" \
  --parent "<epic-number>" \
  --milestone "<milestone-number>" \
  --label "size:<S|M|L>")
  # Add --blocked-by N for known blockers
echo "Created gap issue #${ISSUE_NUMBER}"
```

Set the `size:` label from the AC count with
`PYTHONPATH= uv run pr-size --acs <N> --quiet`. Do not restate the bands — see
`.agents/skills/shared/sizing.md`. This is an **estimate**; the measured size is
applied to the PR by CI and never overwrites it (PAD-05-010).

Do **not** add tasks to GitHub Issues outside the `manage-github-issue`
workflow documented above.

**Route each gap onto the forest before creating it.** Every new issue is a
sub-issue of an Epic (PAD-01-007, PAD-13-002), and `manage_github_issue.sh`
refuses to create one without `--parent`. Use the **`calve-epics`** skill's
routing mode to pick the epic (glacier or iceberg) each gap matches:

- A clear match becomes the `--parent`. The issue takes that epic's Schedule
  tier and carries no `Schedule` value itself (PAD-02-001).
- An ambiguous match (two or more plausible epics) is presented to the user to
  choose.
- A gap with **no** plausible epic goes under the catch-all Epic whose stated
  scope fits it (#3712) and is recorded as a **calving candidate** for
  Phase 3b. If no catch-all fits, ask the user which Epic to use. Do not invent
  an epic for it yourself.

`calve-epics` queries the live Project #24 field/option IDs and delegates the
board mutations, so this skill no longer hardcodes them.

### Phase 3b — Flag calving candidates (do not calve on your own)

The old heuristic — "if 2 or more related gaps, create a parent Task" — cut
epics on convenience (size and superficial theme) rather than on design grain,
and is retired. Grouping issues into a new epic is **calving**, an
architectural act reserved for a human decision.

When routing (3a) surfaces a region that has accumulated coherent mass — a set
of new gaps that realize one design idea with no existing home, or a pile of
gaps parked under a catch-all Epic — collect them and hand them to the user as calving
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

Issues created by this skill are added to Project #24 ("Vultron Planning") as
sub-issues of the epic `calve-epics` routed them to, taking that epic's
Schedule tier (the issue itself carries no `Schedule` value). Gaps with no
matching epic sit under a catch-all Epic as calving candidates. Use
`review-priorities` to re-tier Epics, and invoke `calve-epics`
(Mode 2/3) when the epic structure itself needs to change.
