---
title: Site Information Architecture — Stakeholder Types, Levels, and Routing
status: active
kind: guidance
description: >
  Rules for organizing reader-facing documentation: the argument the site must
  win, stakeholder types versus CVD roles, the invisible 100-500 prerequisite
  levels and their check, the working record's door, generated landing pages,
  reading-path threads and coverage matrix, and how docs remediation is
  partitioned.
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

## The front desk and the floors

The site's top level is organized by subject and reader, not by Diátaxis type
(ADR-0136). The team thinks of it as a building: the home page is the **front
desk**, which says what kind of thing Vultron is and sends each visitor to the
floor they came for. **The metaphor is internal**, like the levels and
stakeholder types: it shapes the nav and never appears on the site.

| Floor | Tab | Primary stakeholder type | Landing page |
|---|---|---|---|
| Front desk | Home | `ALL` | `index.md` |
| Lobby signage | How Vultron Works | `ALL`, levels 200–300 | its own landing page (to write) |
| Offices | Coordinate Cases | `cvd-practitioner` | `start/coordinate-cases.md` |
| Engineering | Implement the Protocol | `platform-developer` | `start/connect-your-tracker.md` |
| Basement | Reference Implementation | `project-contributor` | `start/contribute.md` |
| Observation deck | Research | `process-researcher` | `start/study-the-process.md` |
| (building office) | Project | `ALL` | versioning, open questions, proposing a change |

The table maps each tab to its *primary* type; it is not one tab per type. A
later `stakeholder_type` split adds a thread, not a tab, which keeps the types
invisible (ADR-0102). The CERT/CC link stays as the parent-site link, outside
the seven tabs.

### Placement: the first rule that matches

1. Binds every implementation, or explains or teaches what does → Engineering.
2. About how *this* implementation is built or run → basement.
3. Otherwise, the tab of the page's `stakeholder_type`. `ALL`, or a page several
   tabs depend on → lobby signage. Project process → Project.

So **the protocol and the reference implementation never share a section.** A
page about CERT/CC's codebase, such as the Trigger API or a demo, is basement
material however protocol-shaped its subject is.

**The normative protocol is the Protocol Specification plus the Protocol and
Foundation requirement tiers**, all on Engineering; *Protocol Requirements* there
labels the specification's Requirements Catalog, which replaces the per-kind
pages (ADR-0147). The YAML is the source of truth: the specification
renders both tiers in its Requirements Catalog body section and shows rules in
its narrative only as rendered callouts, so the two cannot drift (DF-12,
ADR-0147). In the basement, the Architecture,
Project and Process tiers are *Implementation Requirements*: how we build ours,
not how others must build theirs. Messages, the Conformance Matrix, the Quick
Reference and Formal Protocol are companions that never add to the normative
set; protocol-floor pages outside it carry `not_normative.md`
(`reference/conventions.md`). Normative status is not a `page_type`.

**Edge placements decided so far:** Behavior Logic and Federation
(`platform-developer`) are Engineering; the Concept Taxonomy and Documentation
Conventions are lobby signage, out of the basement; User Stories are basement;
Measuring Your Program is Offices.

**Open Questions pages:** the specification's
(`reference/vultron-spec/open-questions.md`) is Engineering, beside the
specification it qualifies; the design one
(`topics/future_work/open_questions.md`, `platform-developer` at 400) goes with
Future Work; a project one, when written, is Project.

**Tutorials go by what they teach.** A tutorial that teaches protocol behavior
is Engineering, with a short note that it uses the reference implementation as
a test bench. One about running, configuring or extending the code is basement.

| Tutorial | Floor | Why |
|---|---|---|
| `tutorials/worked_example.md` | Engineering | sequence diagrams of protocol scenarios |
| `tutorials/submit-a-report.md` | Engineering | teaches the `Create(VulnerabilityReport)` message; the implementation is the test bench |
| `tutorials/rv-demo.md` | Engineering | walks a whole case through the protocol states |
| `tutorials/receive_report_demo.md` | basement | running the demo environment |
| `tutorials/container_demos.md` | basement | running the multi-actor containers |
| `tutorials/other_demos.md` | basement | running the remaining demos |

### Inside a tab: topics, landing pages, threads

Groups inside a tab are named by topic, never by Diátaxis type ("Run the
Demos", not "Tutorials"). Every tab opens on a landing page. Large groups go
behind a routing page (DF-11-006) rather than nesting deeper.

Each reader tab's landing page starts a **thread**: a reading path that may
cross tabs; lobby signage has a shared thread. The nav is the structure and the
threads give the route. See "Threads: staged data, rendered at both ends".

A returning reader gets one cross-tab lookup page, linked from the front desk,
listing the reference pages (specification, requirement tiers, messages,
glossary, conformance matrix, quick reference); it can be generated from
`page_type: reference` (#4751).

### Page type is a label, not a section

Every reader-facing page declares one `page_type`: `tutorial`, `how-to`,
`explanation`, `reference` or `routing`. The key is required, so a missing key is
a fault (the same reasoning `contents:` uses in `landing_pages.py`). `routing` is
validated but not rendered; the other four render as a badge from frontmatter.
`page_type` is independent of `contents:`: an index that mostly explains is
`explanation`. Working-record pages declare none (DF-11-003 marks them). A
mixed-type page is split or clearly sectioned (DF-01-003); the Protocol
Specification declares a type per page. There are no hand-written badges.
Diátaxis still governs how a page is written (DF-01); it no longer decides where
the page sits. The key is not `content_type`, which reads as a MIME type.

### Type signal first, nav gated, files stay

The order is: the `page_type` schema, validator and badge land with the
DF-01-001 rewording (#4683); the usability test runs against a build with badges
(#4687); then the nav changes (#4684). The proposed nav stays on a branch or
preview build until it passes against `main`'s nav; a failing nav is revised
and retested, and `main` keeps its current top level meanwhile.

**Files stay where they are**, so no URL breaks, and a page's directory is not
evidence of its floor. Moving them is reconsidered only if contributors
repeatedly misplace pages or the routing check's directory assumption causes
real friction (#4686). That assumption is a known coupling: `landing_pages.py`
requires a routing page to link the reader pages in its own directory. The old
section indexes (`tutorials/`, `topics/`, `reference/`, `howto/`,
`start/index.md`) keep their URLs and are retargeted as routing pages or
redirect stubs.

## Routing: nav enumerates groups, routing pages carry leaves

A large set of leaf pages goes behind a routing page; the nav carries the
group, not the members (DF-11-006). `docs/reference/user_stories/` is the
model: its story pages are out of the nav and reached through
`traceability.md`.

Research has its own tab (ADR-0136): Measuring CVD and Other Uses sit under
`docs/research/index.md` (500, `process-researcher`), off the adoption path
without being hidden. Future Work stays out of it, because its pages are
addressed to `platform-developer` at 400.

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

An entry page's framing prose is hand-written; its reading path is its
thread, rendered from data (below). Each one opens its floor's tab (see "The
front desk and the floors"); there is no separate *Start Here* tab, because
every tab is an entry.

### Threads: staged data, rendered at both ends

A thread is a partial order, not a sequence: a progression where order matters
at some points and not at others (ADR-0150).

- **Shape.** One thread per start page: an ordered list of **stages**, each
  with a goal-named title and an optional stopping-point mark, and each an
  unordered set ("read any of these") or a short ordered chain of pages with a
  blurb apiece. Stages are the start page's sections; a chain is a numbered
  list, a set a bulleted one (DF-11-013). Add
  explicit page-to-page edges only when a real thread needs an order stages
  cannot express; nobody has yet.
- **One source.** The thread lives in its start page's frontmatter. The start
  page's listing is spliced between markers and gated (DF-11-014), so do not
  edit the listing by hand: edit the data.
- **Member pages.** A build hook adds a box per thread the page is on: the
  pages before it and after it, both as sets, and a link back to the start
  page (DF-11-015). The sets are the adjacent ones: the neighbor in a chain,
  or else the whole neighboring set stage (or the near end of a neighboring
  chain). It is titled by situation, never by `stakeholder_type`, and is the
  same for every reader, so no query parameter or referrer is needed. The
  theme's nav-order footer is suppressed on member pages so two "next" links
  never disagree (DF-11-017).
- **Not a level sort.** The level rule forbids depending upward; it does not
  require a thread to climb in level. Order a thread by what the reader needs
  first.
- **More threads, not more tabs.** The practitioner start page already serves
  someone deciding whether to adopt and someone working cases; splitting them
  adds a start page with its own thread, and no page's `stakeholder_type`
  changes.

Authoring practice:

- Name each stage for the reader's goal ("Decide whether it solves a problem
  you have"), never for a page type.
- Give each step a blurb saying what the reader gets from it, written for this
  thread; it need not match the page's `description:`.
- Mark early stages as stopping points: a reader who only needed "should we
  adopt this?" should know when they are done.
- Keep the main route to about 8–12 pages; anything beyond is a set stage.

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
cannot gate a change. It remains an open goal; nobody is available to do it.

What can gate a change is an **agent usability test**, which ADR-0136 uses to
gate the nav change. ADR-0136 § "Validation" fixes its essentials: `main`'s nav
is the baseline; the proposed nav passes when it is no worse on task success and
no task stalls at the front desk; personas and tasks are committed before the
proposed nav is evaluated; each pairing is repeated; the evaluator is
independent of the design. How to run it:

1. **Tree test.** Agents see only nav labels, baseline and proposed, and say
   where they would look for each task.
2. **Walkthrough.** Agents get the built site as HTML only: no repository, no
   site search, a click budget, and an explicit option to give up.

Brief about five personas, each with explicit "you don't know X" constraints;
an agent that knows the repo will find anything. Draw tasks from the user
stories, the FAQ and a few real questions from the maintainer, include at least
one "follow your thread" task per persona, and **fix the task list before anyone
sees the proposed tree**, or the tasks get written to fit it. The evaluator is a
different model, or a fresh context without access to the proof of concept. An
agent catches a nav that cannot work; it cannot show that a person finds one
natural.

**Rerun policy (guidance, not CI).** Rerun only on a structural nav change:
tabs or second-level groups added, removed, renamed or reordered, or a page
moving between tabs. A single rename or move needs only the tree test. To keep
cost down, run the cheap tree test on every pairing, escalate to walkthroughs
only where the navs differ or a task fails, reuse baseline results keyed on a
hash of the nav, and repeat runs only for pairings with mixed results.
