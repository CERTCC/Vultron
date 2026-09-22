---
title: Site Information Architecture — Tracks, Levels, and Routing
status: active
description: >
  How reader-facing documentation is organized: the argument the site must win,
  the three audience tracks, the invisible 100-500 prerequisite levels, and the
  rule that nav enumerates groups while routing pages carry leaf sets.
related_notes:
  - notes/diataxis-framework.md
  - notes/documentation-strategy.md
  - notes/documentation-sweeps.md
  - notes/agents-md-structure.md
related_specs:
  - specs/diataxis-requirements.yaml
---

# Site Information Architecture — Tracks, Levels, and Routing

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
moving (ADR-0101).

## The argument the site must win

Three questions arrive before any other, in this order, and the site must
answer them above the fold:

1. **What kind of thing is this?** Readers cannot tell whether Vultron is
   software to install, a specification to implement, a data format, or a
   paper. Until this is settled they cannot evaluate anything else.
2. **Would it help me?**
3. **It doesn't do X — so why would I want it?**

The answer to the first is an analogy, and the analogy answers all three:

> Vultron is a protocol, like SMTP — not a platform, like a messaging
> service. It connects the trackers that already exist rather than moving
> everyone onto one system.

The paired form is the load-bearing device, because each pair contrasts a
protocol with the centralized product that competes with it:

| Protocol | Not the platform |
|---|---|
| SMTP | a proprietary messaging service |
| XMPP | a single-vendor chat network |
| RSS / Atom | a publishing platform you must join |

Stated as the reader's own problem: *today you need an account on every
partner's coordination system.* CERT/CC runs one, CISA runs another, each
bug-bounty platform runs its own, and vendors wanting to coordinate directly
with each other fall back to encrypted mail and hand-updated local tickets.
Vultron is the automation that removes that, without centralizing anything —
you connect your own tracker and coordinate from it.

Prefer this framing to `lingua franca` and to bare "federated" or
"decentralized". All three are accurate and all three require the reader to
already understand the thing being described.

## "Vultron doesn't do X" is the objection, and it has an answer

Readers evaluate Vultron against their local pain — automated analysis,
priority decisions, report verification, choosing who to invite to a case,
advisory drafting — find none of it, and conclude there is no value. The
reasoning is sound from a local vantage point and the conclusion is wrong,
because the problems Vultron addresses are *between* organizations and are
easy not to notice from inside one.

The answer is never a denial. Every X on that list is a **call-out point**: a
declared seam where the protocol stops and your own judgment, tool, or
service is invoked. SMTP does not write your mail either. The obligation on
the site is to follow every "Vultron is not…" statement with where the
reader's own system plugs in.

`docs/topics/capability_model/index.md` is the page that carries this, and
its section headings are close to a restatement of the objection list
(Report Validation, Report Prioritization, Case Admission, Embargo
Management, Publication, Threat Monitoring). Treat that page as
argument-critical rather than as background reading. A negative list that
ends without the plug-in answer is an unfinished thought, not a scoping
statement.

## The three tracks

A track is *who the page is for*. Tracks do not nest and a page belongs to
exactly one.

| Track | Reader | Wants |
|---|---|---|
| **Adopter / implementer** | Building or extending a system that must coordinate with others | To decide whether to adopt, then what to send and when |
| **Project developer** | Working on this reference implementation | How this codebase is built and why it was built that way |
| **Process researcher** | CVD process engineering, process-improvement research | The models, measurements, and where the process theory leads |

Two consequences that are easy to get wrong:

- **The two developer audiences are different people.** Someone implementing
  Vultron in their own tracker and someone working on this repository need
  different material, and conflating them buries the first under the second.
- **Research material belongs to neither of the other two.** It is not
  advanced adopter reading and it is not project internals. It is a small
  section for a third reader, and it sits off the adoption path entirely.

## Levels 100–500: a rule, not a label

Every reader-facing page carries a level recording **how much the reader must
already know**. Levels exist to make ordering reviewable. They are *not*
navigation labels and are never rendered.

| Level | Assumes | Typically |
|---|---|---|
| **100** | Works in security. Nothing about CVD or Vultron | What this is, the portal-login problem, why it matters |
| **200** | 100 | How a case works: roles, lifecycle, embargo, the state machines |
| **300** | 200 | Implementing: which messages to send when, wiring a capability |
| **400** | 300 | Formal specification and deep detail |
| **500** | 400, or a research background | CVD process research and measurement |

The rule, and the whole reason levels exist:

> **No page may depend on a page above its own level.**

A violation means the page is misplaced, its prerequisites are unstated, or
it is doing two jobs. This is the reviewable ordering rationale that was
missing: before this, no ordering decision could be wrong, so none could be
reviewed.

Levels are declared in each page's YAML frontmatter so the rule can be
checked mechanically and landing pages can be generated from it. **Do not
render the level, and do not navigate by it.** A reader sorts themselves by
goal, never by depth: someone who needs to wire a scanner into report
validation thinks "how do I plug this in", not "I need a 300-level page".
Exposing levels re-creates the self-classification problem that the
Study/Work split already has — the reader must rank themselves before their
first click.

The pedagogical point is that the student sees a linear flow and the teacher
sees the hierarchy that produced it. If a reader ever notices the levels, it
should be in retrospect.

## Reader-facing content versus the project working record

These are different kinds of thing, not different depths, and the working
record has **no level**. Giving it one is a category error: it is not harder
Vultron, it is how this particular implementation came to be.

The working record is decision records, generated code documentation,
exhaustively enumerated state pages, and retained design history. It stays
published, linkable, and unbroken — and it stays out of the reader-facing
navigation, behind one labeled door for the project-developer track.

Design history is **retained deliberately**, not tolerated. `#3281` decided
against retiring `docs/topics/behavior_logic/` because those pages are the
design-intent view that the auto-generated reference pages do not carry (see
the three-views table in `notes/documentation-strategy.md`). Demoting them
from the reader path is not a step toward deleting them.

## Routing: nav enumerates groups, routing pages carry leaves

A large set of leaf pages goes behind a routing page. The navigation carries
the group, not the members.

The pattern is already proven in this repository and simply is not applied
consistently: `docs/reference/user_stories/` holds 111 story pages that are
excluded from the nav entirely and reached through `traceability.md`, which
links all of them. Two nav entries carry 111 pages. Meanwhile the nav
enumerates every decision record, every generated code page, and every
enumerated case state inline. Same shape of content, opposite treatment. The
`traceability.md` treatment is the correct one.

### Landing pages are generated, never hand-maintained

Every section landing page was a hand-written duplicate of the nav, and every
one had drifted from it — pages missing, order disagreeing, and in one case a
taxonomy that no longer existed being described to readers. Hand-maintained
duplicates of a machine-readable structure always drift; the defect class is
the duplication, not any individual omission.

Generate the landing pages from page frontmatter and gate them with a sync
check. Three working examples to build on:

| Prior art | Pattern to reuse |
|---|---|
| `vultron/metadata/adr/index_gen.py` | Generates a landing page from frontmatter; `missing_nav_entries()` proves nav completeness by parsing the nav structurally rather than by substring match (MS-14-006) |
| `vultron/metadata/notes/` + `validate-notes-frontmatter` | Frontmatter schema, loader, and pre-commit hook |
| `demo-scenarios-sync` (ADR-0098) | `--write` / `--check` so a generated artifact refuses to be hand-edited |

## How remediation is partitioned

Two rules, learned from the shape of this work rather than from a failure.

**Audit routes; the fix decides.** An audit records, per page, its level,
track, verdict, a one-line evidence note, and which task owns it. It does
*not* prescribe the fix. The remediation task reads its pages properly and
fixes them in one session, with the context loaded. A prescription written by
one session and applied by another is the lossy handoff the completeness
doctrine warns about; re-deriving the fix at the moment of the edit is
cheaper and better than specifying it twice.

The exception is any judgment that **cannot be made from inside a single
page**, which a page-local fixer will get wrong. The audit must settle these
itself:

- which of several overlapping pages wins, and what each carries over
- inbound link counts, which decide whether a move is cheap (78 inbound
  occurrences is what made retiring `behavior_logic/` too expensive in #3281)
- level violations, which are a property of a pair of pages
- missing pages, which by definition appear in no file list

**Flip the axis between analysis and remediation.** Analysis fans out by
dimension — level, register, overlap, nav enumeration, gaps. Remediation
partitions by **page**, and each task owns its files exclusively. Partitioning
both halves the same way is the mistake: five dimension-shaped fix tasks
leave one page claimed by three of them, one saying rewrite it, one saying
move it, one saying merge it away. This mirrors the existing rule for large
code migrations — partition by shape, then batch by subsystem
(`notes/agentic-workflow.md`).

`mkdocs.yml` is the one file every structural change touches. One task owns
all navigation edits at a time; they are never done in parallel.

## Two premises that were in conflict

Both were in force before this note and they contradicted each other.

- `docs-style-guide.md` SG-07 justifies resetting acronym expansion per page
  because "readers arrive from search and from deep links, not by reading in
  nav order". SG-10 through SG-12 make each page self-sufficient.
- `write-docs` Phase 6 states that "nav order carries reading order" and asks
  the author to propose a slot — with no artifact to propose against.

Both survive, scoped. **Pages remain self-sufficient**: repeated openings and
re-expanded acronyms serve deep-link arrivals and are required, not accretion
damage. Do not "deduplicate" them. **Nav order still carries meaning**, but
what it carries is dependency and prominence rather than narrative flow — and
it is now reviewable, because the level rule makes a wrong order falsifiable.
Deleting a page's self-sufficiency to make neighbors read as a sequence is a
regression.

## Validation

There is no analytics, no search-log data, and no observed newcomer for this
site, so every audience claim here rests on indirect signals: the questions
the team answers repeatedly. Treat it accordingly.

The intended test is a cold read: hand the entry path to one person who has
never seen Vultron and record where they stall. That is a person rather than
a check, so it cannot gate a change — but an organization justified by
recognition is worth confirming against one real reader, and a single cold
read will falsify more of this note than any amount of internal review.

## Measured baseline

Recorded at the time of writing, so later structural claims have something to
be compared against.

| | Pages |
|---|---|
| `docs/**/*.md` total | 544 |
| In nav | 333 |
| Not in nav (57 include fragments, 161 matching `not_in_nav`, 3 unaccounted) | 211 |
| Tutorials | 7 |
| How-to Guides | 20 |
| Explanation | 97 |
| Reference | 203 |
| — of which decision records | 100 |
| — of which enumerated case states | 33 |
| — of which generated code pages | 22 |
| Retained design-history pages | 23 |
| Research pages (measurement, other uses, future work) | 22 |
| Capability model — the answer to the most common objection | 1 |

Reachability was checked and is *not* a problem: pages outside the nav are
almost entirely deliberate. The problem is proportion. Roughly 200 pages
written by the team, for the team or for the record, sit at the same visual
weight as the couple of dozen a newcomer can use.
