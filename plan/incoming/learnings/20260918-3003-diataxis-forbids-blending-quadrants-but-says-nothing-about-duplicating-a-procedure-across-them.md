---
title: "DF forbids blending quadrants on a page but is silent on the same procedure appearing in two quadrants — and the how-to/tutorial pair is where that bites"
type: learning
timestamp: "2026-09-18T23:30:00Z"
source: ISSUE-3003
signal: spec-ambiguity
---

Issue #3003 asked for the remaining content of
`docs/howto/activitypub/activities/` to be reshaped into "real how-to guides",
naming the `!!! example "Try it: vultron-demo <scenario>"` blocks as the
task-oriented remainder. Following that literally produces 13 pages whose
procedure is one `vultron-demo <scenario>` command.

`docs/tutorials/other_demos.md` already runs every one of those scenarios. It is
462 lines, has a `## Prerequisites` section, a step per scenario with the same
command, a mermaid diagram for most, and a "See [the activity guide]" link back to
the very page being reshaped. `receive_report_demo.md` covers the twelfth.

So the question the ACs could not answer: **is "run the canned demo" how-to content
when a tutorial already walks the reader through the identical command?**

## What DF says, and where it stops

DF-01-002 requires each page to map to exactly one of the four user needs.
DF-01-003 forbids combining content types *within a single page or section*.
DF-04-001 through DF-04-008 govern how-to shape. Every one of them constrains a
page **in isolation**.

Nothing in DF addresses two pages in different quadrants covering the same
procedure. The framework note (`notes/diataxis-framework.md` §1) names the
tutorial/how-to "partial collapse" as the most common failure and locates it in
the Study/Work confusion — which is about a *single* page being unsure who it
serves, not about deliberate coverage in both.

The corpus has already answered it once, in the opposite direction from a
duplication reading: `docs/howto/demos/fvv-demo.md` is "How to Run the FVV Demo"
and `docs/tutorials/fv-demo.md` is "Tutorial: Run the FV Demo". Two pages, two
quadrants, adjacent scenarios, cross-linked. Nobody recorded why that is
legitimate, so the next agent re-derives it.

## The resolution used, and the test it rests on

The guides were written so the demo is the **last** section (`## See it end to
end`), not the procedure. The procedure is the activity sequence an implementer
must emit — ordered steps, conditional branches, a `## Verify` table — and the
demo is offered afterwards as confirmation, with a link to the tutorial for the
narrated pass.

The discriminator that made this decidable: **what is the reader's real-world
goal?** "I need my actor to propose an embargo" is Work, and the answer is which
activities to send. "I want to see an embargo negotiation happen" is Study, and the
answer is the demo. The same command serves both, so the duplication is not the
defect — *leading with the command in the how-to* would have been, because it
answers the tutorial's question.

## How to apply

When a how-to and a tutorial both cover one procedure, do not deduplicate by
deleting one. Ask which question each page answers and order the page's sections to
answer that one first. A how-to whose first section is the same command the
tutorial opens with has been written to the tutorial's question.

Watch for the inverted signal too: if a how-to page has *nothing* to put before the
demo invocation — no activities to send, no state to verify — that is evidence the
page has no task in it and belongs in the tutorial tree, not that it needs a
"How to" title. `ledger_replication.md` failed exactly that test in this session
and was retired.

Corroboration needed: one instance. A second witness would be any session
reshaping a tree where a tutorial already covers the procedure — the
`docs/howto/demos/` and `docs/tutorials/` demo pair is the obvious next place, and
if DF is going to grow an entry for this, that pair is the evidence it should be
written from.

Related: the four detection signals for a quadrant collapse now live in
`notes/message-type-reference.md` § "Diátaxis: these pages are an extraction".
Distinct from [[20260918-3337-a-doc-rots-first-in-the-column-no-test-can-hold]],
which is about unverifiable claims rather than quadrant boundaries; that entry's
rule was *applied* in this session (the guides name trigger behaviors, never URL
paths, because nothing ratchets a path — #3442), so this session is a confirming
application of it, not a second witness.
