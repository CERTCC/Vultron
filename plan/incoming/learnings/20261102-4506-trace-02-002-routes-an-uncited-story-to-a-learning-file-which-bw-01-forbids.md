---
title: >
  TRACE-02-002 routes a story with no requirements to a learning file, which
  BW-01's content policy forbids and a generated flag has made redundant
type: learning
timestamp: 2026-11-02T21:27:15Z
source: ISSUE-4506
signal: spec-ambiguity
---

## Trigger

You are editing `specs/traceability.yaml`, or deciding what to do about a user
story that no requirement cites, and TRACE-02-002 tells you to write a file
into `plan/incoming/learnings/`.

## Question `learn` must settle

TRACE-02-002 says a story with insufficient spec coverage SHOULD be recorded
as an incoming learning file with the gap and concrete remediation steps. Two
things have since made that route wrong, and the requirement was not revisited:

- **BW-01's content policy.** The learnings queue holds lessons awaiting a
  second witness, not work items. A per-story gap record is a backlog entry,
  and `upward-reflection.md` is explicit that a learning file cannot be
  assigned, scheduled or closed, so a gap parked there is inert. The same
  argument that moved code-review findings to issues (BW-07-009) applies here.
- **The gap is now generated.** #4506 made the uncited set a computed fact:
  every story no requirement cites is flagged *No mapped requirements* in both
  the index table and the traceability matrix (TRACE-01-002), and the count is
  in the table. Writing a file to record what the artifact already states adds
  a second ledger that can disagree with the first.

So: is TRACE-02-002 still the right route? The candidate answers are to
retire it in favour of the generated flag, to replace it with a `type:Idea`
issue per genuinely unserved need, or to narrow it to the one case the flag
cannot express — a story whose coverage exists but is too thin to serve it,
which no check can detect.

## Evidence

The live uncited set is 14 story pages (#4506, PR #5690). Five are the bounty
stories 055, 056, 057, 084 and 085, whose disposition waits on the scope
decision in #2563 — a decision, not a gap to remediate. The other nine are the
`story_2026_*` pages added by PR #5425, which the per-area drafting Tasks
(#4508 through #4513) will cite as they work. Neither group wants a learning
file: one is blocked on a scope question and the other is already scheduled
work.

## How to apply

Until this is settled, do not write a learning file for an uncited story. Read
the flag in the generated matrix, and if a story names a need the protocol
should serve and nothing tracks it, file a `type:Idea` issue through
`create-issue`. #4506 left TRACE-02-002 untouched deliberately: it is advisory,
and rewording it was outside that Task's acceptance criteria.
