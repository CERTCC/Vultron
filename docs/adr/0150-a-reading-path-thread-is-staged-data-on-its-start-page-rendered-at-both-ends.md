---
status: proposed
date: 2026-10-20
created: 2026-10-20
updated: 2026-10-26
revision: 2
deciders: Allen D. Householder
consulted: >-
  Claude Opus 5.5; ADR-0102, ADR-0128, ADR-0136;
  notes/site-information-architecture.md; specs/diataxis-requirements.yaml DF-11
informed: []
stakeholder_type: [project-contributor]
---

# A Reading-Path Thread Is Staged Data on Its Start Page, Rendered at Both Ends

## Context and Problem Statement

ADR-0136 organized the site's top level by subject and reader, and gave each reader tab a **thread**: an ordered reading path that starts on the tab's landing page and may cross tabs.
It left open how a thread is represented and shown (#4750).

The four start pages under `docs/start/` already carry hand-written reading paths.
Each one is a run of goal-named sections, some holding a numbered list where order matters and some a bulleted list where it does not, with a blurb per link written for that path.
Nothing checks them beyond a broken-link build, and nothing on a member page tells a reader where the path goes next.

A reader's route through the site is a progression, not a sequence: at some points order matters, and at others any of several pages will do.
How is a thread represented so that it gives direction without dictating a sequence, renders where readers need it, and cannot drift from itself?

## Decision Drivers

- A reader's route is a partial order over pages: deeper than wide, with places where order matters less than others.
- One source with many render points (DF-10-002): a thread's order is stated once, and every list or link that shows it is derived.
- Pages stay self-sufficient for a reader arriving directly (DF-11-007), and a rendered page is the same for every reader.
- No page shows its own `stakeholder_type` or `level` (DF-11-004, DF-11-009).
- A thread is reviewable in a diff by someone who has not seen the tooling.
- Drift is prevented by a check, not by authoring discipline.

## Considered Options

- Staged thread data in the start page's frontmatter, rendered on the start page and on each member page
- Hand-written start-page lists as the source, with a link checker
- Single "next" and "previous" links on each page, keyed to the thread the reader came from
- A free-form graph of page-to-page edges
- A thread generated from `stakeholder_type` and `level`, then curated

## Decision Outcome

Chosen option: "Staged thread data in the start page's frontmatter, rendered on the start page and on each member page", because it is the only option that states the order once, expresses a partial order without forcing a sequence, and gives a member page directions without knowing which reader is looking at it.

A thread is an ordered list of **stages**.
A stage is either an unordered set of pages ("read any of these") or a short ordered chain where the order matters.
That is a partial order shaped like the existing start pages: their section headings are stages, their numbered lists are chains, and their bulleted lists are sets.

The thread is declared in its start page's frontmatter, beside the page that opens it.
From that one declaration:

- the start page's stage headings, lists and per-step blurbs are generated between markers in its source, and a check fails when the committed text differs from the data;
- each member page, and the start page itself, carries a box per thread it is on, titled by the reader's situation, with a table of the thread's start page, the pages before it, the page itself and the pages after it, where before and after are sets;
- each box is a committed fragment generated from the declaration, the way the message-vocabulary fragments are (ADR-0128), and the page's author places it with `include-markdown` where directions onward belong; the build never adds one, and a check over the built site fails when a page is missing its box.

A member page on several threads shows one box per thread, so it never needs to know which thread a reader is following.
Because no box is added at the page end, the theme's navigation-order footer stays on every page.

The mechanism supports any number of threads.
A later split of one reader's path into narrower situations adds a thread, which is the move ADR-0136 anticipated for a `stakeholder_type` split.

### Consequences

- Good, because a thread's order exists in one place, and the start-page list and every member-page box are renders of it.
- Good, because a partial order is expressed directly: a set of predecessors and a set of successors, not one forced next page.
- Good, because rendered pages do not vary by reader, so no query parameter, script or referrer is involved, and every page still stands alone.
- Good, because a thread's data is plain YAML that reviews well in a diff.
- Bad, because a long thread makes for long frontmatter on its start page.
- Good, because a page's source shows which threads it is on, and a change to a thread shows in the diff of every box it moves.
- Good, because the author places the box where a reader needs it, including at the end of one section of a long page.
- Bad, because every member page needs an include line placed by hand; the check catches a missing box and a section's box outside its section, but where on a whole page a box sits is left to review.
- Neutral, because the theme's navigation-order footer and a thread box can name different next pages; the box is titled by its thread, so the two read as different routes.

## Validation

A check validates every thread: each listed page exists and is reader-facing, no page appears twice in one thread, and the start page's generated block and every committed box match its data.
A check over the built site, run in CI, fails when a member page or start page does not render its box for each of its threads, renders a box made for another page, or renders a section member's box outside that section.
It fails, rather than passes, when it finds no threads (DF-09-009).
The agent usability test that gates the navigation change has a "follow your thread" task for each persona (ADR-0136).

## Pros and Cons of the Options

### Staged thread data in the start page's frontmatter, rendered on the start page and on each member page

- Good, because one source feeds every render point.
- Good, because stages match how the start pages are already written, so converting them loses nothing.
- Good, because a stage-ordered structure cannot contain a cycle, so no cycle check is needed.
- Bad, because an edge that crosses stages in an unusual way cannot be expressed until explicit edges are added.

### Hand-written start-page lists as the source, with a link checker

- Good, because nothing about the start pages changes.
- Bad, because every further feature, such as member-page directions or an order check, has to parse prose to recover the order.
- Bad, because it keeps a hand-maintained enumeration, the defect class DF-11-005 exists to remove.

### Single "next" and "previous" links on each page, keyed to the thread the reader came from

- Good, because it is the familiar pattern of a book or a course.
- Bad, because it forces a sequence where the route is a partial order.
- Bad, because a page on several threads must learn which one the reader is on, through a query parameter or the referring page, so the same page renders differently for different readers and loses that state on a deep link.

### A free-form graph of page-to-page edges

- Good, because it can express any partial order.
- Bad, because a set of arbitrary edges is hard to review in a diff, and nobody has yet needed an order that stages cannot express.

### A thread generated from `stakeholder_type` and `level`, then curated

- Good, because ADR-0102's level rule guarantees an order exists for each audience, so a first draft is cheap.
- Bad, because the curated start pages already exist and are better than any sort by level, and a level order is not a reading order: the rule is only that no page depends on a page above its level.

## More Information

Explicit page-to-page edges can be added inside or across stages if a real thread needs an order that stages cannot express; that extends this decision rather than replacing it.

Generated spec requirements: `diataxis-requirements.yaml` DF-11-013 through DF-11-016, DF-11-022 and DF-11-023; DF-11-017 stands until #5170 retires it.
