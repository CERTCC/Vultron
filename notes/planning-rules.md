---
title: Planning Rules — Objectives, Milestones and the Focus Order
status: active
kind: guidance
description: >
  How quarterly objectives become milestones, which Project #24 tiers need a
  current-quarter milestone, the relevance test that sorts work into an objective
  or Health, the 70/20/10 attention budget, and the staggering rule that picks the
  next Epic for a free Focus slot. The current quarter's objectives live in the
  matching roadmap plan note.
related_notes:
  - notes/parallel-development.md
  - notes/epic-themes.md
  - notes/roadmap-2026q4.md
---

# Planning Rules — Objectives, Milestones and the Focus Order

These rules turn a quarter's objectives into a board an agent or a person can
read at a glance. The objectives themselves, and their finish lines, are in the
current roadmap note (`notes/roadmap-2026q4.md`). Tier mechanics (Schedule on
Epics, Status as a mirror) are in `notes/parallel-development.md` § "Project #24:
Two Paths".

## Objectives Are Milestones

- **One milestone per objective per quarter**, titled `YYYYQn · <name>` and due
  on the quarter's last day. A milestone is an objective, not a deliverable: an
  objective with several deliverables has one Epic per deliverable, and a closed
  Epic is the visible "done".
- **Name an objective by its outcome**, such as `Self-serve start`, never by a
  shorthand like `O2`. A shorthand means nothing to a reader outside the session
  that coined it.
- **Every objective has a finish line a reader can check.** For a draft, "done"
  is a tagged version (`Spec Draft 1`); later changes are the next draft, not an
  edit to the tagged one.
- **Every part of a finish line is covered by an Epic.** An objective whose
  finish line names work no Epic holds will not finish, and the board cannot
  show the gap.
- **Health is a milestone but a budget, not an objective.**

## Tiers Need Milestones

| Tier | Current-quarter milestone |
|---|---|
| Focus, Now, Next | required |
| Later, Someday | must not have one |

Reason: the milestone says *why* an Epic is scheduled this quarter. A Focus or Now
Epic with none is either goal work nobody labeled or work outside the plan.
`check-priority-status` reports a breach in either direction.

At each quarter boundary, every unfinished Epic either moves to the next
quarter's milestone or loses its milestone. Nothing carries over silently.

## The Relevance Test

An Epic serves an objective if it is on a list that objective's own tools
produced (an audit, a mapping, a newcomer run, a failed replay), or if it blocks
building one of those tools. It is **Health** if it keeps what exists working, or
if it will measurably cut the maintainer's attention per merged PR. Anything else
gets no milestone, however worthy.

Before you demote an Epic for failing the test, check it against current
stakeholder demand. An objective list set at the start of a quarter misses demand
that arrives later. Add an objective at the next review instead of pushing that
work to Later.

## The Attention Budget

Aim for about 70% objective work, 20% Health, and 10% discretionary. This is
measured by where the maintainer's review and steering time goes, not by PR or
issue counts. Check it weekly against the merged PRs, bucketed by the milestones
of their Epics. Without milestones the bucketing is a guess, so assign them first.

## The Focus Order

- **Focus has six slots.** The maintainer picks the Epics that fill them, by
  hand. Skill auto-selection is not the enforcement mechanism.
- **The Now tier is teed up in order.** An Epic's position within Now on
  Project #24 is its place in the queue for the next free slot. Reorder the board
  when the order changes; never keep the queue in a note, which goes stale within
  a week.
- **Stagger deliverables.** The next free slot goes to the Epic that finishes the
  deliverable closest to done. A few things fully done as the quarter goes on beat
  many things partly done that all finish at the end.
- **Keep Health's share steady.** When a Health Epic leaves Focus, the next Health
  Epic in Now takes its place, unless the budget says otherwise.
- **Don't run two Epics on the same code at once.** An Epic that edits the same
  specs or modules as a Focus Epic waits for that Epic to close, because parallel
  worktrees on one area turn into rebase conflicts.
