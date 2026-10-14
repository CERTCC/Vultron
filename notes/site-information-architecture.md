---
title: Site Information Architecture — Stakeholder Types, Levels, and Routing
status: active
kind: guidance
description: >
  Rules for organizing reader-facing documentation: the argument the site must
  win, stakeholder types versus CVD roles, the invisible 100-500 prerequisite
  levels and their check, the working record's door, generated landing pages
  and coverage matrix, and how docs remediation is partitioned.
related_notes:
  - notes/agentic-workflow.md
  - notes/diataxis-framework.md
  - notes/site-coverage-matrix.md
  - notes/documentation-strategy.md
  - notes/documentation-sweeps.md
  - notes/agents-md-structure.md
  - notes/rfc-spec-authoring.md
  - notes/user-story-catalog.md
  - notes/rfc-review-rubric.md
related_specs:
  - specs/diataxis-requirements.yaml
  - specs/meta-specifications.yaml
---

# Site Information Architecture — Stakeholder Types, Levels, and Routing

Write each page from the reader's situation, not from the research literature
or the implementation. A page written from the inside out fails louder when it
is moved earlier, so an information-architecture fix covers rewriting, not only
moving (ADR-0102).

## The argument the site must win

Three questions arrive before any other, in this order, and the site must
answer them above the fold:

1. **What kind of thing is this?** Software to install, a specification to
   implement, a data format, or a paper? Until this is settled a reader cannot
   evaluate anything else.
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
partner's coordination system.* Vultron removes that without centralizing
anything — you connect your own tracker and coordinate from it.

Prefer this framing to `lingua franca` and to bare "federated" or
"decentralized": all three are accurate, and all three require the reader to
already understand the thing being described.

## "Vultron doesn't do X" is the objection, and it has an answer

Readers evaluate Vultron against their local pain — automated analysis,
priority decisions, report verification, choosing who to invite, advisory
drafting — find none of it, and conclude there is no value. The problems
Vultron addresses are *between* organizations and are easy not to notice from
inside one.

The answer is never a denial. Every X is a **call-out point**: a declared seam
where the protocol stops and the reader's own judgment, tool, or service is
invoked. Follow every "Vultron is not…" statement with where the reader's own
system plugs in; a negative list without that answer is an unfinished thought.
`docs/topics/capability_model/index.md` carries this argument in its opening
section ("Vultron doesn't do X: your system does"); treat it as
argument-critical, not background reading.

## Stakeholder type is not CVD role

A **stakeholder type** is why someone is reading about Vultron. A **CVDRole**
is a position an actor holds in a case. Roles vary from case to case — the same
vendor is a Reporter in one case and a Vendor in the next — while what brought
its engineer to the documentation does not. So no stakeholder type is named
after a `CVDRole` value, which makes the conflation structurally impossible
(DF-11-001). The glossary's "CVD Roles and Participants" section defines roles
held in a case; never add stakeholder-type descriptions to it.

## The stakeholder types

**Read the members and their definitions in
`docs/includes/stakeholder_types.md`.** Do not restate them in a note, in
`notes/README.md`, or in the glossary: a list copied into four files drifts in
three of them.

| Where | What it is |
|---|---|
| **DF-11-001** | The normative enumeration. Every other form derives from it. |
| `vultron/metadata/docs/page_schema.py` | Implements DF-11-001 (`StakeholderType`, `LEVELS`, `AUDIENCE_DESCRIPTIONS`); `docs-frontmatter` validates every page against it |
| `docs/includes/stakeholder_types.md` | Generated from that schema by `uv run docs-site --write` and gated by the `docs-site-sync` hook (DF-11-011); the only form any `docs/` page includes |
| ADR-0102 | A dated literal copy, on purpose |

So a change to the members is made in DF-11-001 and in `page_schema.py`; the
fragment follows. ADR-0102 states the members literally and deliberately does
not include the fragment: a decision record that live-included a later member
would claim to have decided something it did not (DF-10-002's
documented-reason escape).

`stakeholder_type` records who a page is **addressed to** — not what it is
about, and not who could get use out of it. Tagging by subject matter collapses
the axis to `ALL`: almost every conceptual page is "about" everyone. A list
covering every type MUST be written `ALL` (DF-11-001).

Three consequences that are easy to get wrong:

- **The two developer audiences are different people.** Someone implementing
  Vultron in their own tracker and someone working on this repository need
  different material; conflating them buries the first under the second.
- **Research material belongs to neither developer audience.** It is a small
  section for a third reader, off the adoption path.
- **Cross-case interest needs no mechanism.** A national CSIRT wanting
  ecosystem health is a `cvd-practitioner` who also reads `process-researcher`
  pages. Readers read more than one type.

### Why `cvd-practitioner` stays whole

Split `cvd-practitioner` only when enough pages tagged with it narrow in their
own text to one constituent that a body of content for that constituent
exists; the next docs audit records that narrowing per page. Splitting ahead of
the evidence costs more than waiting: an over-broad tag makes a page findable
by a superset of its readers, while a premature split hides it from readers
who needed it. A vendor-versus-coordinator distinction belongs on routing
pages, never in frontmatter, because it *is* the case-role axis.

Do not admit `policy-owner` (VDP or program owner, regulator, standards body)
until someone writes its first page: nothing in the tree is addressed to one,
so the type would be a column of holes with no owner.

## Levels 100–500: a rule, not a label

Every reader-facing page carries a level recording **how much the reader must
already know**. Levels make ordering reviewable; they are never rendered and
never used for navigation.

| Level | Assumes the reader already knows |
|---|---|
| **100** | Nothing about CVD or Vultron; works in security |
| **200** | What CVD is, what Vultron is for, and that it is a protocol rather than a platform |
| **300** | How a case works: the roles, the lifecycle, embargo, and that state machines drive it |
| **400** | The protocol as a working system — enough to read normative detail and formalism |
| **500** | Level 400, or an independent research background in process engineering |

The table states assumed knowledge and deliberately does not say which topics
live at each rung: each subject area judges its own 300, like a
course-catalogue number. There is one ladder and it sorts site-wide.

> **No page may depend on a page above its own level** (DF-11-002).

A violation means the page is misplaced, its prerequisites are unstated, or it
is doing two jobs. **Do not render the level, and do not navigate by it**
(DF-11-004): a reader sorts themselves by goal, never by depth, and exposing
levels makes them rank themselves before their first click.

### A level describes a page, never a reader

There is no "300-level reader". Every stakeholder type enters at 100 and
traverses its own sequence, so a `platform-developer` may reach a 300-level
page early. Expect `ALL` to predominate at 100 and thin out above it, as the
types diverge; use that shape as a diagnostic when reading the coverage matrix.
It is not a rule, and nothing fails because of it.

### How the rule is checked

`uv run docs-level-order` (`vultron/metadata/docs/level_order.py`) checks
DF-11-002. The glossary stays the concept registry (SG-11); the page that is a
term's canonical introduction names it in its frontmatter:

```yaml
level: 400
introduces: [CASE_MANAGER, Case Ledger Entry]
```

A term has one introducer, and it must be a glossary term. For each leveled
page, the check finds the first prose use of each term introduced above that
page's level; the use passes when the page links to the introducer before or
at the use (a link later on the same line does not count), or when the use is
itself a glossary link. Otherwise it is a finding at `path:line:col`.

Consequences of that design:

- **One ladder.** Levels are compared across the whole tree, never per
  `stakeholder_type`.
- **Unleveled pages are skipped**, not read as level 0, and may not declare
  `introduces:`.
- **Fragments** are checked at their lowest host's level (DF-11-010). A link
  inside a fragment counts for its host; a host's link above the include does
  not excuse a use inside the fragment.
- **The glossary is exempt**: it is the registry the scan reads.
- **Defining in place is not detected.** The check cannot tell a definition
  from a use, so such a page links out instead.
- **Headings and indented blocks are prose** (an admonition nests its prose by
  indentation). Fenced code, `<code>` and `<pre>` are masked.
- **Only glossary terms are tracked.** Add a term to the glossary to track a
  dependency on it.
- **Choose specific terms for `introduces:`.** Everyday phrases such as
  "participant status" match ordinary prose on dozens of pages, so the matches
  measure word frequency, not dependency.

Pre-existing violations go in `vultron/metadata/docs/level_order_baseline.txt`
(`page | term | reason`). The list may only shrink: fix a new violation with a
link or a re-level, never an entry.

## Reader-facing content versus the project working record

The working record — decision records, generated code documentation,
enumerated state pages, retained design history, and the individual user-story
pages with their traceability matrix — is a different kind of thing, not a
greater depth, so it has **no level** (DF-11-003, DF-11-012). It stays
published and linkable, and out of the reader-facing nav behind one labeled
door: `docs/about/project_record.md`, a `project-contributor` page that links
one routing page per working-record group. `uv run docs-frontmatter` fails a
working-record page that is navved or matched by no `not_in_nav` pattern,
because an unmatched page breaks `mkdocs build --strict`.

A working-record page declares `stakeholder_type: [project-contributor]`
because it is addressed to somebody; the missing level is then a property of
one audience's material, not a special exemption.

Design history is **retained deliberately**: the `docs/topics/behavior_logic/`
pages are the design-intent view the generated reference pages do not carry
(see the three-views table in `notes/documentation-strategy.md`). Demoting
them from the reader path is not a step toward deleting them (#3281).

## Routing: nav enumerates groups, routing pages carry leaves

A large set of leaf pages goes behind a routing page; the nav carries the
group, not the members (DF-11-006). `docs/reference/user_stories/` is the
model: its story pages are out of the nav and reached through
`traceability.md`.

Research is the one reader-facing group with its own top-level section:
Measuring CVD and Other Uses sit under `docs/research/index.md` (500,
`process-researcher`), off the adoption path without being hidden. Future Work
stays in Explanation, because its pages are addressed to `platform-developer`
at 400.

### Landing pages are generated, never hand-maintained

A hand-written landing page duplicates the nav and drifts from it; the defect
class is the duplication (DF-11-005). `uv run docs-site --write`
(`vultron/metadata/docs/landing_pages.py`) generates each section landing
page's contents listing, and the `docs-site-sync` hook gates it. The nav
supplies membership, labels, and fallback order; each listed page's
`description:` supplies the text beside its link, and a declared `level`
reorders the listing. Only the text between the generated-contents markers is
replaced, so framing and cross-section pointers stay hand-written.

Every `index.md` that opens a nav group declares its shape in a `contents:`
frontmatter key, and an undeclared one fails the check:

- `contents: generated` — the listing above.
- `contents: routing` — the page links its members inside framing prose or an
  editorial grouping. Nothing is generated; `--check` fails when the page stops
  linking a member: the group's nav members plus every reader page in its own
  directory that the nav omits. A leaf `index.md` whose directory holds pages
  the nav omits must declare `routing`.
- `contents: rendered` — rendered at build time from a registry
  (DEMOCI-11-009), so nothing is committed to drift.

`test/metadata/docs/test_site_sync.py` pins the decided sets, so decide a new
group index's shape before it lands.

A generated `description:` is rendered on the landing page, so
`docs-level-order` reads it at the landing page's level. When a child's blurb
uses a term above the index's level, fix it with plainer wording in the
description, not a link the generator cannot carry.

### An `index.md` is a routing surface, not a content page

Generation fixes an index that under-routes; it cannot fix a full content
essay wearing an index's filename, because it preserves hand-written prose. An
`index.md` orients and routes. Anything on it that is neither belongs on a
named page of its own, with the index linking to it.

### Entry pages are titled by situation, never by type

There is one routing page per stakeholder type under `docs/start/`, titled by a
situation the reader recognizes — *"You maintain a vulnerability tracker and
want it to talk to your partners"*, not *"For platform developers"*. The type
vocabulary decides which pages exist and what they link; it never appears on
them. A situation is recognizable without asking the reader to identify with a
label, and a later `cvd-practitioner` split then just adds a page with a
narrower situation.

The entry pages are hand-written curated paths, not enumerations, so
DF-11-005's generate-and-gate rule does not apply. They sit in the nav as a
*Start Here* section opened by `start/index.md`; its cards come from
`docs/includes/start_here_cards.md`, the fragment the home page also includes.

### The coverage matrix is generated too

The same generator emits a `stakeholder_type` × `level` matrix,
[site-coverage-matrix.md](site-coverage-matrix.md), so "we do not serve
audience X" is a fact in a file (DF-11-008):

- **It lives in `notes/`, not `docs/`**, because it prints levels.
- **The check enforces currency, not fullness.** `--check` fails when the
  committed matrix disagrees with the tree, never because a cell is empty. An
  empty cell is planning input, not a merge blocker. Gating currency is what
  keeps the matrix a checked object rather than a WARN by another name.

## How remediation is partitioned

**Audit routes; the fix decides.** An audit records, per page, its level,
stakeholder type, any `cvd-practitioner` narrowing, a verdict, a one-line
evidence note, and the owning task — not the fix. The remediation task reads
its pages with context loaded and decides the fix; a prescription written by
one session and applied by another is a lossy handoff.

The exception is a judgment that **cannot be made from inside one page**, which
the audit must settle itself:

- which of several overlapping pages wins, and what each carries over
- inbound link counts, which decide whether a move is cheap (78 inbound links
  made retiring `behavior_logic/` too expensive, #3281)
- level violations, which are a property of a pair of pages
- missing pages, which appear in no file list

**Flip the axis between analysis and remediation.** Analysis fans out by
dimension (level, register, overlap, nav, gaps); remediation partitions by
**page**, each task owning its files exclusively. Dimension-shaped fix tasks
leave one page claimed by three of them. This mirrors the code-migration rule
in `notes/agentic-workflow.md`.

`mkdocs.yml` is the file every structural change touches: one task owns all
navigation edits at a time.

## Pages stay self-sufficient; nav order carries dependency

Repeated openings and re-expanded acronyms serve readers who arrive from search
and deep links, so they are required, not accretion damage; do not deduplicate
them to make neighbors read as a sequence (DF-11-007, SG-07). Nav order still
carries meaning, but what it carries is dependency and prominence, and the
level rule makes a wrong order falsifiable. Transitions and forward/back
references between neighbors remain real work.

## Validation

There is no analytics, search-log data, or observed newcomer for this site, so
every audience claim here rests on indirect signals — the questions the team
answers repeatedly. A cold read of the entry path by someone who has never seen
Vultron is the test that would falsify it; it is a person, not a check, so it
cannot gate a change.
