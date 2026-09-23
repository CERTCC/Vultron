---
status: accepted-provisional
date: 2026-09-23
deciders: Allen Householder
consulted: CERT/CC Vultron team
informed: Vultron contributors
stakeholder_type: [project-contributor]
---

# Organize reader-facing documentation by stakeholder type and invisible prerequisite level

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

Underneath that sits a second problem, found while planning the first. The
project does not have one audience model; it has several, none authoritative,
and no two agree:

| Where | Enumeration |
|---|---|
| `docs/index.md` | security researchers, vulnerability coordinators, tool builders, "anyone seeking interoperability" |
| #607, #3511 | CVD practitioners, developers, contributors |
| `docs/reference/terms.md` | Reporter, Finder, Vendor, Deployer, Coordinator, Observer, Exploit Publisher |
| `docs/reference/user_stories/` `Roles:` | Participant, Vendor, Coordinator, Reporter, Other, Finder, Deployer |
| `docs/topics/other_uses/roles_influence.md` | vendors, system owners, security research community, coordinators, governments |

The first two are reader audiences; the last three are **CVD roles** — positions
an actor holds in a case. They are routinely read as one list, which is the
conflation this decision has to make structurally impossible rather than merely
discourage. A role is assumable, inhabitable, temporal: an organization's roles
vary from case to case. What brings someone to this documentation is more
constant than that.

How should reader-facing documentation be organized so that a newcomer reaches a
coherent picture, given that nothing is known about real readers beyond the
questions the team answers repeatedly?

## Decision Drivers

- First contact is where the site fails; organization must serve that first.
- Several conflicting audience enumerations are already in circulation and none
  is authoritative, so any new one must retire the others rather than join them.
- Reader identity and case role must not be expressible in the same vocabulary.
  They change on different timescales and answer different questions.
- Roughly 200 of 333 navigated pages are the project's own working record or
  research archive, at the same visual weight as the pages a newcomer needs.
- Ordering must become *reviewable*; today no order can be shown to be wrong.
- Nothing is known about actual readers — no analytics, no search logs, no
  observed newcomer. A large restructuring would be steered by guesswork.
- Classification a page must carry is a recurring cost across ~430 pages, so
  each declared key has to earn its place against a consumer that would
  otherwise be impossible.
- Two in-force rules contradicted each other on whether nav order is reading
  order (`docs-style-guide.md` SG-07 versus `write-docs` Phase 6).

## Considered Options

- **Stakeholder types plus invisible prerequisite levels.** Keep the four
  Diátaxis sections, add a front door above them, assign every reader-facing
  page an audience `stakeholder_type` and a 100–500 prerequisite `level` in
  frontmatter, and keep the levels out of the rendered pages and the navigation.
- **A third axis for reader depth.** Declare an audience, a prerequisite level,
  and a separate novice/practitioner/expert *track* per page.
- **Levels as the navigation itself.** Present the site as a course catalogue:
  the reader sees 100-level, 200-level, and so on, and works up.
- **Reorganize the top level by reader goal.** Replace the four Diátaxis
  sections with goal-named sections.
- **Two separate sites.** Split reader-facing documentation from the project's
  working record into separate builds.
- **Ordering and landing pages only.** Keep all content inline at its current
  level and fix only the sequence, as the originating issue proposed.

## Decision Outcome

Chosen option: **stakeholder types plus invisible prerequisite levels**.

The four Diátaxis sections stay. The home page gains a real entry layer that
answers "what kind of thing is this" with a protocol-versus-platform analogy,
states the reader's own problem (needing an account on every partner's
coordination system), and follows every "Vultron does not do X" with where the
reader's own system plugs in.

Every reader-facing page declares exactly two keys in YAML frontmatter.

| Key | Values |
|---|---|
| `stakeholder_type` | `cvd-practitioner`, `platform-developer`, `process-researcher`, `project-contributor`, `ALL` |
| `level` | 100, 200, 300, 400, 500 |

This record states the members literally and deliberately does **not** include the
shared fragment that defines them (`docs/includes/stakeholder_types.md`), which
every other location uses. A decision record is a dated account of what was
decided: if the enumeration later gains a member, an ADR that live-included it
would retroactively claim to have decided something it did not. This is
DF-10-002's documented-reason escape, used on purpose and only here.

`stakeholder_type` is the audience a page is **addressed to** — not what it is
about, and not who could get use out of it. It is list-valued, because a page
may legitimately serve two audiences and no others. A list that covers every
type must be written `ALL`, and the validator rejects the enumerated form, so
one fact never has two spellings. None of the values is a `CVDRole`, which is
what makes the role/type conflation structurally impossible rather than a matter
of author discipline.

`cvd-practitioner` is deliberately left whole rather than split into security
researchers, vendor PSIRTs, and national CSIRTs/ISACs/ISAOs. Those constituents
are named in its definition. It is split when — and only when — enough pages
tagged `cvd-practitioner` narrow in their own text to one constituent to form a
body of content aimed at that constituent. Splitting ahead of that evidence
would repeat the mistake that produced the competing enumerations above, and the
asymmetry favours waiting: an over-broad tag makes a page findable by a superset
of its readers, while a premature split makes it invisible to readers who needed
it.

The governing rule for levels is:

> No page may depend on a page above its own level.

There is **one** level ladder and it sorts site-wide: a 300 means the same
prerequisite depth in every part of the site, even though each subject area
judges its own 300 by its own criteria. A level is a property of a page and
never of a reader. Readers are not leveled, so different stakeholder types enter
at 100 and traverse different sequences — a `platform-developer` may reach a
300-level page early without that being a violation. Specialization rises with
level, so `ALL` predominates at 100 and thins as the level climbs. That is an
expected shape used as a diagnostic, not a rule.

Levels are an authoring and review discipline only. They are never rendered and
never navigated by, because readers sort themselves by goal rather than by
depth. The reader-facing routing pages generated per stakeholder type are titled
by **situation** — "You maintain a vulnerability tracker and want it to talk to
your partners" — and never name the stakeholder-type vocabulary. Recognition
replaces self-classification, and keeping the vocabulary internal is what makes
a later `cvd-practitioner` split invisible to readers rather than a change to
something they were taught.

The project working record — decision records, generated code documentation,
enumerated state pages, retained design history — declares
`stakeholder_type: [project-contributor]` and **no level at all**. It is a
different kind of thing rather than a greater depth, and it moves out of the
reader-facing navigation while remaining published and linkable. Research
material becomes its own small 500-level section addressed to
`process-researcher`.

Navigation enumerates groups; routing pages carry leaf sets. Section landing
pages are generated from frontmatter and gated by a check mode rather than
hand-maintained. The same generator emits a `stakeholder_type` × `level`
coverage matrix into unpublished `notes/`, also gated by a check mode. That
check enforces the matrix's *currency*, never its fullness: an empty cell is a
recorded fact that makes a missing audience visible, not a merge blocker. The
matrix cannot live under `docs/`, because it prints levels.

### Consequences

- Good, because the ordering rule makes a wrong order falsifiable, which is
  exactly what was missing — ordering decisions become reviewable rather than
  matters of taste.
- Good, because one audience list replaces five, and reader identity can no
  longer be confused with a CVD role: no value in the enumeration is a role
  name.
- Good, because it is additive and reversible at the top: the four sections and
  their URLs are untouched, so a wrong call about readers costs an entry layer
  rather than a restructuring.
- Good, because generating landing pages retires a whole defect class. Every one
  of the four had drifted from the nav, and hand-maintained duplicates of a
  machine-readable structure always will.
- Good, because "we do not serve audience X" becomes a durable object — a cell
  in a committed matrix — instead of a recurring feeling.
- Good, because nothing is deleted and no URL breaks; the working record is
  demoted, not retired. This keeps the #3281 decision to retain design-intent
  pages intact.
- Bad, because assigning a type and level to every reader-facing page is a large
  one-time pass, and some assignments will be wrong until a real reader tests
  them.
- Bad, because levels are invisible, so nothing stops a reader from entering at
  400 by deep link. Page self-sufficiency (SG-10 through SG-12) remains the only
  defense, and it must be preserved rather than "deduplicated".
- Bad, because a coverage matrix that never fails will show holes that nobody is
  obliged to fill. That is deliberate — the alternative hardens into a rule
  requiring every audience at every level, which the divergence-at-the-top shape
  says is wrong — but it does depend on someone reading it.
- Bad, because the whole audience model rests on indirect signals. It is a
  hypothesis wearing the clothes of a decision until a cold read confirms it.

## Validation

Mechanically: the declarations are enforced by a frontmatter schema and
validator (modeled on `vultron/metadata/notes/`), including the rule that a
full type list must be written `ALL`; the dependency rule by a check that fails
when a page depends on a page above its level; and both generated artifacts —
section landing pages and the coverage matrix — by a `--check` mode following
`demo-scenarios-sync` (ADR-0098).

Judgmentally: a cold read. One person who has never seen Vultron is given the
entry path and their stalling points are recorded. This cannot gate a change —
it is a person, not a test — but an organization justified by reader recognition
should be confirmed against at least one real reader. Retiring the redundant
third axis removed a guess; it did not add evidence.

## Pros and Cons of the Options

### Stakeholder types plus invisible prerequisite levels

- Good, because it separates the axis readers navigate by (goal) from the axis
  authors order by (prerequisite depth), so neither has to serve both jobs.
- Good, because both keys live in frontmatter and are therefore checkable.
- Good, because two keys is the minimum that supports both the ordering rule and
  the coverage question.
- Neutral, because it keeps the Diátaxis sections, which remain a sound
  authoring taxonomy even though they were not the source of the failure.
- Bad, because it introduces a second classification every page must carry.

### A third axis for reader depth

- Good, because "novice / practitioner / expert" is how people describe
  themselves, so it reads as the most natural of the three axes.
- Bad, because it is redundant twice over. Its values are audience identities,
  which `stakeholder_type` already carries, and its depth sense is `level` seen
  from the reader's side rather than the page's.
- Bad, because a third declaration is a third thing to assign across ~430 pages
  and a third thing to drift, bought with no check that the other two cannot
  already perform.

### Levels as the navigation itself

- Good, because sequence becomes explicit and prerequisites unmissable.
- Bad, because it asks a newcomer to rank their own knowledge before their first
  click — the same defect as asking whether they are studying or working.
- Bad, because readers arrive by search and deep link, where a level label on a
  menu they never saw does nothing.

### Reorganize the top level by reader goal

- Good, because it would address the self-classification problem directly.
- Bad, because there is no reader data to steer it, and it is the least
  reversible option on the table.
- Bad, because it discards a taxonomy that works for authors and for returning
  readers who already know what they want.
- Note that the situation-framed routing pages adopted above are a partial,
  additive form of this option: they give goal-shaped entry points *above* the
  four sections without replacing them, so a wrong guess about reader goals
  costs a generated page rather than the site's URL structure.

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

Design rationale, the argument and its analogies, the stakeholder-type
definitions and level table, the routing rule, the remediation-partitioning
rules, and the measured baseline are in `notes/site-information-architecture.md`
in the repository.

**Stakeholder Type** and **CVDRole** are distinguished in
`docs/reference/glossary.md`: a role is assumable, inhabitable, temporal, and
varies from case to case; a type is ontological, identity-formed, and slow to
change. `docs/reference/terms.md` defines roles held in a case and is not a
register of reader types.

This decision makes the stakeholder-type enumeration authoritative and retires
the competing audience lists in `docs/index.md` and in #607/#3511.

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
DF-11-012.

This record is `accepted-provisional` rather than `accepted` on purpose. The
structure is decided and is being implemented; the *audience model underneath it*
rests on indirect signals and has not met a real reader, as the Consequences and
Validation sections above say plainly. Status is the confidence signal agents
read (MS-14-002), so it should not claim more than the Validation section
delivers. It advances to `accepted` when a cold read confirms the types, or the
types change and it is amended.
