---
status: accepted
date: 2026-09-22
deciders: Allen Householder
consulted: CERT/CC Vultron team
informed: Vultron contributors
---

# Organize reader-facing documentation by track and invisible prerequisite level

## Context and Problem Statement

The documentation site has 544 pages and was written from the inside out — from
the research literature and from the implementation — without anyone deciding
how a newcomer is supposed to move through it. No artifact stated the intended
reader path, so no ordering decision could be reviewed and drift was invisible
(#3512).

The reported failure is not wayfinding. Readers cannot tell what kind of thing
Vultron is, evaluate it against the pain they feel locally, find that it does
not automate analysis or prioritize reports or verify submissions, and conclude
there is no value. The page that answers that objection
(`docs/topics/capability_model/index.md`) is one page, absent from its own
section's landing page. The page that should win the central interoperability
argument (`docs/topics/background/interoperability.md`) makes it through five
block quotations from 2004–2005 research reports and never mentions a
coordination portal.

How should reader-facing documentation be organized so that a newcomer reaches
a coherent picture, given that nothing is known about real readers beyond the
questions the team answers repeatedly?

## Decision Drivers

- First contact is where the site fails; organization must serve that first.
- Three distinct readers exist and two of them are developers who need
  different material: adopters/implementers, project developers, and CVD
  process researchers.
- Roughly 200 of 333 navigated pages are the project's own working record or
  research archive, at the same visual weight as the pages a newcomer needs.
- Ordering must become *reviewable*; today no order can be shown to be wrong.
- Nothing is known about actual readers — no analytics, no search logs, no
  observed newcomer. A large restructuring would be steered by guesswork.
- Two in-force rules contradicted each other on whether nav order is reading
  order (`docs-style-guide.md` SG-07 versus `write-docs` Phase 6).

## Considered Options

- **Tracks plus invisible prerequisite levels.** Keep the four Diátaxis
  sections, add a front door above them, assign every reader-facing page an
  audience track and a 100–500 prerequisite level in frontmatter, and keep the
  levels out of the rendered pages and the navigation.
- **Levels as the navigation itself.** Present the site as a course catalogue:
  the reader sees 100-level, 200-level, and so on, and works up.
- **Reorganize the top level by reader goal.** Replace the four Diátaxis
  sections with goal-named sections.
- **Two separate sites.** Split reader-facing documentation from the project's
  working record into separate builds.
- **Ordering and landing pages only.** Keep all content inline at its current
  level and fix only the sequence, as the originating issue proposed.

## Decision Outcome

Chosen option: **tracks plus invisible prerequisite levels**.

The four Diátaxis sections stay. The home page gains a real entry layer that
answers "what kind of thing is this" with a protocol-versus-platform analogy,
states the reader's own problem (needing an account on every partner's
coordination system), and follows every "Vultron does not do X" with where the
reader's own system plugs in.

Every reader-facing page declares a **track** (adopter/implementer, project
developer, process researcher) and a **level** (100–500) in YAML frontmatter.
The governing rule is:

> No page may depend on a page above its own level.

Levels are an authoring and review discipline only. They are never rendered and
never navigated by, because readers sort themselves by goal rather than by
depth — exposing levels would re-create the self-classification problem the
Study/Work split already has. The student sees a linear flow; the hierarchy
that produced it belongs to the teacher.

The project working record — decision records, generated code documentation,
enumerated state pages, retained design history — carries **no level at all**.
It is a different kind of thing rather than a greater depth, and it moves out of
the reader-facing navigation while remaining published and linkable. Research
material becomes its own small 500-level section for the third track.

Navigation enumerates groups; routing pages carry leaf sets. Section landing
pages are generated from frontmatter and gated by a sync check rather than
hand-maintained.

### Consequences

- Good, because the ordering rule makes a wrong order falsifiable, which is
  exactly what was missing — ordering decisions become reviewable rather than
  matters of taste.
- Good, because it is additive and reversible at the top: the four sections and
  their URLs are untouched, so a wrong call about readers costs an entry layer
  rather than a restructuring.
- Good, because generating landing pages retires a whole defect class. Every
  one of the four had drifted from the nav, and hand-maintained duplicates of a
  machine-readable structure always will.
- Good, because nothing is deleted and no URL breaks; the working record is
  demoted, not retired. This keeps the #3281 decision to retain design-intent
  pages intact.
- Bad, because assigning a track and level to every reader-facing page is a
  large one-time pass, and some assignments will be wrong until a real reader
  tests them.
- Bad, because levels are invisible, so nothing stops a reader from entering at
  400 by deep link. Page self-sufficiency (SG-10 through SG-12) remains the
  only defense, and it must be preserved rather than "deduplicated".
- Bad, because the whole audience model rests on indirect signals. It is a
  hypothesis wearing the clothes of a decision until a cold read confirms it.

## Validation

Mechanically: the level declaration is enforced by a frontmatter schema and
validator (modeled on `vultron/metadata/notes/`), and the dependency rule by a
check that fails when a page depends on a page above its level. Landing pages
are validated by a `--check` mode in their generator, following
`demo-scenarios-sync` (ADR-0098).

Judgmentally: a cold read. One person who has never seen Vultron is given the
entry path and their stalling points are recorded. This cannot gate a change —
it is a person, not a test — but an organization justified by reader
recognition should be confirmed against at least one real reader.

## Pros and Cons of the Options

### Tracks plus invisible prerequisite levels

- Good, because it separates the axis readers navigate by (goal) from the axis
  authors order by (prerequisite depth), so neither has to serve both jobs.
- Good, because levels live in frontmatter and are therefore checkable.
- Neutral, because it keeps the Diátaxis sections, which remain a sound
  authoring taxonomy even though they were not the source of the failure.
- Bad, because it introduces a second classification every page must carry.

### Levels as the navigation itself

- Good, because sequence becomes explicit and prerequisites unmissable.
- Bad, because it asks a newcomer to rank their own knowledge before their
  first click — the same defect as asking whether they are studying or working.
- Bad, because readers arrive by search and deep link, where a level label on a
  menu they never saw does nothing.

### Reorganize the top level by reader goal

- Good, because it would address the self-classification problem directly.
- Bad, because there is no reader data to steer it, and it is the least
  reversible option on the table.
- Bad, because it discards a taxonomy that works for authors and for returning
  readers who already know what they want.

### Two separate sites

- Good, because it gives the cleanest separation between reader-facing material
  and the working record.
- Bad, because it doubles the publishing setup and forces a placement decision
  for every borderline page.
- Bad, because cross-links between the two become external links, and the
  working record links into reader-facing reference material heavily.

### Ordering and landing pages only

- Good, because it is the smallest change and the one the originating issue
  proposed.
- Bad, because it cannot fix a page that addresses the wrong reader. Moving
  `interoperability.md` closer to the front makes it fail sooner.
- Bad, because it leaves 200 working-record pages inline, so the proportion
  problem — the actual reason the tree reads as accretion — is untouched.

## More Information

Design rationale, the argument and its analogies, the track and level tables,
the routing rule, the remediation-partitioning rules, and the measured baseline
are in `notes/site-information-architecture.md` in the repository.

This decision resolves a conflict between two rules that were both in force:
SG-07's "readers do not read in nav order" and `write-docs` Phase 6's "nav order
carries reading order". Both survive, scoped — pages stay self-sufficient, and
nav order carries dependency and prominence rather than narrative flow.

Scope boundary: this decision governs where reader-facing pages sit and what
they may assume. Per-page structure, voice, and terminology remain governed by
`.claude/skills/shared/docs-style-guide.md` and ADR-0092. Page accuracy and
staleness are a separate concern from placement.

Source: #3512, under epic #3511.

Generated spec requirements: `diataxis-requirements.yaml` DF-11-001 through
DF-11-007.
