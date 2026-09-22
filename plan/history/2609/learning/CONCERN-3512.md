---
source: CONCERN-3512
timestamp: '2026-09-22T16:17:30.829689+00:00'
title: Site nav below the second tier is in accretion order, and no artifact states
  the intended reader journey
type: learning
---

## Original concern

The site navigation below the second tier had drifted into accretion order:
inside `Explanation`, `How-to Guides`, and `Reference`, pages sat where they
happened to be added rather than where a reader would need them. No artifact
anywhere in the repo stated the intended reader journey, so no page-level edit
could be wrong and no ordering could be reviewed. The concern named three
tangled failures — no stated journeys, no routing layer, and no continuity
between neighboring pages — and asked for an information-architecture pass
covering the journeys artifact and the routing design, with nav reordering,
a continuity pass, and gap-filing left to follow-on issues.

## What planning found

**The concern was a symptom, not the disease.** The site was written from the
inside out — from the research literature and from the implementation — and
never from the reader's situation. The witness page is
`docs/topics/background/interoperability.md`, titled "The Need for
Interoperability in Coordinated Vulnerability Disclosure", which makes that
argument through five block quotations from two SEI research reports (2004 and
2005), discusses syntactic versus semantic interoperability and "unbounded
systems of systems", and never mentions a coordination portal, an account on
someone else's platform, or any situation a practitioner would recognize. Its
"Objectives" section lists objectives *of the documentation*. Repositioning such
a page makes it fail sooner, not better — which is why the plan covers
rewriting and not only moving.

**The real failure is first contact, and the argument the site needs was never
written down.** The recurring questions are "what kind of thing is this?",
"would this help me?", and the objection "Vultron doesn't do X" — where X is
automated analysis, priority decisions, report verification, choosing who to
invite, advisory drafting. The answer is that Vultron is a protocol like SMTP
rather than a platform, so you stop needing an account on every partner's
coordination system; and every X is a call-out point where the reader's own
tool plugs in. The paired analogies (SMTP, XMPP, RSS/Atom against their
centralized competitors) answer all three questions at once and appear
**nowhere** in `docs/` — the site instead uses `lingua franca` and bare
"federated", both of which require the reader to already understand the thing.

**The answer to the hardest objection is one page, and it is unreachable.**
`docs/topics/capability_model/index.md` is 341 lines whose section headings are
nearly a restatement of the objection list (Report Validation, Report
Prioritization, Case Admission, Embargo Management, Publication, Threat
Monitoring), and it is absent from its own section's landing page. It is also
stale: it says "The five shapes" and counts Sentinel among them, where ADR-0097
and the glossary say four and name "the five shapes" as a phrase to avoid.

**Four of the concern's evidence bullets had gone stale.** #607 is closed, and
issue #3281 closed `NOT_PLANNED` — the ~23 design-history behavior pages are
retained deliberately as the design-intent view (78 inbound link occurrences), so
demotion is not a step toward deletion. `howto/case_object.md` is now a 10-line
redirect stub rather than a Gen-1 UML design doc. `howto/process_implementation.md`
has been rescoped into a legitimate integration guide.

**Reachability was checked and is not a problem.** Of 544 pages, 333 are navved
and of the 211 that are not, all but 3 are deliberate (57 include fragments,
161 matching `not_in_nav`). The problem is proportion: roughly 200 pages written
by the team, for the team or for the record — 100 decision records, 33
enumerated case states, 22 generated code pages, 23 design-history pages, 22
research pages — sit at the same visual weight as the couple of dozen a
newcomer can use.

**The routing pattern already exists and is applied inconsistently.**
`docs/reference/user_stories/` holds 111 story pages kept out of the nav
entirely and reached through `traceability.md`, so two nav entries carry 111
pages. The same nav enumerates the 100 decision records, 33 case states, and 22
code pages inline. Same shape of content, opposite treatment.

**All four section landing pages are hand-maintained duplicates of the nav and
all four have drifted from it.** `topics/index.md` omits four nav children;
`reference/index.md` omits the Protocol Specification, Glossary, Concept
Taxonomy and Quick Reference, and still describes the six-kind spec taxonomy
retired by ADR-0038; `tutorials/index.md` omits Worked Example;
`howto/index.md` omits Demo How-Tos. The defect class is the duplication, not
any individual omission.

**Two in-force rules contradicted each other on whether nav order is reading
order.** `docs-style-guide.md` SG-07 justifies per-page acronym resets because
"readers arrive from search and from deep links, not by reading in nav order",
and SG-10 through SG-12 make each page self-sufficient; `write-docs` Phase 6
asserts "nav order carries reading order" with no artifact to propose against.
Both survive scoped: pages stay self-sufficient (so the concern's proposed
continuity pass, which would have removed duplicated openings, was dropped as
contrary to SG-07), and nav order carries dependency and prominence rather than
narrative flow.

## Decisions reached

- **Tracks, not a single audience.** Three: adopter/implementer, project
  developer, process researcher. The two developer audiences are different
  people, and research material belongs to neither of the other two.
- **Levels 100–500 as an invisible rule.** Declared in frontmatter, never
  rendered and never navigated by, governing the single rule that no page may
  depend on a page above its own level. Readers sort themselves by goal, not by
  depth; exposing levels would re-create the self-classification problem the
  Study/Work split already has. The student sees a linear flow, the teacher sees
  the hierarchy that produced it.
- **The working record carries no level at all** — it is a different kind of
  thing rather than a greater depth, and giving it a level is a category error.
  It leaves the reader-facing nav while staying published and linkable.
- **The four Diátaxis sections stay**; the home page gains a small entry layer
  above them. Additive and reversible, which matters because there is no
  reader data to steer a larger restructuring.
- **Landing pages are generated from frontmatter and gated by a check** rather
  than hand-maintained.
- **Audit routes; the fix decides.** The audit records level, track, verdict, a
  one-line evidence note, and the owning task — not the prescription. Depth
  lives in the remediation task, which reads its pages fresh. The exception is
  judgments invisible from inside one page (merges, inbound-link counts, level
  violations, gaps), which the audit must settle itself.
- **Flip the axis between halves.** Analysis fans out by dimension; remediation
  partitions by page, each task owning its files exclusively. Partitioning both
  the same way leaves one page claimed by three tasks. `mkdocs.yml` is the one
  file everything collides on, so one task owns all nav edits at a time.

## Not resolved

There is no analytics, no search-log data, and no observed newcomer, so every
audience claim rests on indirect signals — the questions the team answers
repeatedly. The intended validation is a cold read: hand the entry path to one
person who has never seen Vultron and record where they stall. That is a person
rather than a check, so it cannot gate a change, and it is recorded in the note
as the intended test rather than as an acceptance criterion.

## Outcome

**Resolved**: 2026-09-22 — implementation tracked in seven issues:

- #3524 — front door: what Vultron is, and where your tools plug in
- #3525 — declare `track` and `level` in docs frontmatter, with a validator
- #3526 — five-lens reader-facing content audit (Concern)
- #3527 — generate section landing pages from frontmatter
- #3528 — move the working record out of the reader-facing nav
- #3529 — check that no page depends above its own level
- #3530 — teach `write-docs` and `lint-docs` the architecture

Docs PR: <https://github.com/CERTCC/Vultron/pull/3523>
Spec: `specs/diataxis-requirements.yaml` DF-11-001 through DF-11-007 (v1.4.0).
Notes: `notes/site-information-architecture.md`.
ADR: `docs/adr/0101-docs-tracks-and-invisible-prerequisite-levels.md` — numbered
0101 rather than 0099 because ADR-0099 and ADR-0100 landed on `main` while the
branch was open.
