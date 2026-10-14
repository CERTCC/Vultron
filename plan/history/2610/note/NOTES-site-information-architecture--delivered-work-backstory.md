---
source: NOTES-site-information-architecture--delivered-work-backstory
timestamp: '2026-10-14T14:27:00.528675+00:00'
title: 'site-information-architecture: delivered-work backstory'
type: note
---

Archived from `notes/site-information-architecture.md` by #4498: the backstory of delivered work (#3512, #3524, #3526, #3528, #3619). The witness page and the background index were rewritten, the working record moved behind its door, and the #3512 continuity ask was settled by DF-11-007. The lasting rules stay in the note.

---

## The failure this answers

The documentation was written from the inside out — from the research
literature and from the implementation — and never from the reader's
situation. Ordering drift is a symptom of that, not the disease.

The witness page is `docs/topics/background/interoperability.md`. It is
titled "The Need for Interoperability in Coordinated Vulnerability
Disclosure", which makes it the page that should win the site's central
argument. It makes that argument through five block quotations from two SEI
research reports (2004 and 2005), discusses syntactic versus semantic
interoperability and "unbounded systems of systems", and never once mentions
a coordination portal, an account on someone else's platform, or any
situation a practitioner would recognize. Its "Objectives" section lists
objectives *of the documentation*. The argument is sound and unrecognizable:
it addresses a reviewer of a research report.

Repositioning such a page does not fix it. It fails louder, sooner. This is
why an information-architecture pass here covers rewriting and not only
moving (ADR-0102).

This is not a hypothetical hazard. Five audience or role enumerations were
already in circulation and none was authoritative: the four audiences in
`docs/index.md`, the three in #607/#3511, the seven roles in
`docs/reference/terms.md` (since merged into the glossary), the `Roles:` metadata
on the 111 user stories, and
the vendors/system-owners/coordinators/governments list in
`topics/other_uses/roles_influence.md`. The first two are audiences and the last
three are roles, and they were read as one list. The enumeration below is
authoritative and retires the first two.

The pattern is already proven in this repository and simply is not applied
consistently: `docs/reference/user_stories/` holds 111 story pages that are
excluded from the nav entirely and reached through `traceability.md`, which
links all of them. Two nav entries carry 111 pages. Until #3528 the nav
enumerated every decision record, every generated code page, and every
enumerated case state inline — same shape of content, opposite treatment. The
`traceability.md` treatment is the correct one, and #3528 applied it to all of
them.

What the generated form loses is recorded so nobody re-derives it: the
grid-card icons three sub-indexes carried, the external standards links on the
crosswalks index (each crosswalk page links the document it maps), and any
table column beyond the per-page blurb, which moved into each child's
`description:` — the frontmatter the rule says a listing is generated from. A
`description:` is rendered on the landing page, so `docs-level-order` reads it
at the landing page's level: a term the child may use unlinked at 400 is a
finding when its blurb lands on a 200 index, and the fix is plainer wording in
the description, not a link the generator cannot carry.

It walks the nav itself rather than reusing `vultron.metadata.base.nav_paths`,
because that helper flattens the nav to a path list, and a listing needs the
groups, their labels, and which group opens with its own `index.md`.

`docs/topics/background/index.md` was the worked instance — 211 lines titled
"Vultron Contextualized", which was an essay, not a door. #3526 decided where
each section went, because that depended on how the neighbouring
`background/` pages divide the same material — exactly the
several-overlapping-pages judgment an audit must settle rather than hand to a
page-local fixer. #3619 applied the ruling: the essay is now
`cvd-coordination-problem.md`, its protocol definitions and the "Why Vultron?"
sidebar live on `what-is-vultron.md`, and the index, retitled "Background",
keeps only the prerequisites admonition, the "New to Vultron?" pointer, and one
line per child in dependency order.

### This overturns one of #3512's own asks

Worth stating plainly, because the issue that commissioned this note asked for
the opposite. #3512's suggested action step 4 was a continuity pass that would
"fix transitions between neighbors, add forward/back references, and **remove
the duplicated openings** that came from pages being written standalone" — and
it called that the step most easily skipped.

Two of those three survive and are real work: transitions and forward/back
references are what make a correct order read as a sequence, and #3526 records
them per page alongside its other findings.

The third is rejected, and DF-11-007 now forbids it. The duplicated openings
were read as damage from pages having been written in isolation. They are not:
they are what lets a reader who arrived from a search result understand the page
they landed on. The premise underneath step 4 was that a reader moves through
the site in nav order, which is the same premise SG-07 already rejected on
different evidence. Deduplicating openings would have made the site read better
for the one reader who starts at the top and worse for every other.

This is the note's own thesis turned on the issue that asked for it: the request
to smooth the pages into a sequence was itself written from the inside out, by
someone who knows the whole tree, for a reader who does not exist.
