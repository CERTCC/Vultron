---
title: RFC Spec Document Authoring Decisions
status: active
kind: guidance
description: >
  Structural and editorial conventions for the Vultron Protocol Specification
  under docs/reference/vultron-spec/: the page map (routing landing page, body
  pages, annex pages, Open Questions, hidden full.md) and the fragments each
  page includes, the full.md in-page link rewrite, fragment kinds and naming,
  annex embedding, the section citation convention, normative text rendered
  from the YAML (callouts and the Requirements Catalog), source treatment, STE
  style, and the DAG-first authoring workflow.
related_notes:
  - notes/documentation-strategy.md
  - notes/rfc-review-rubric.md
  - notes/site-information-architecture.md
related_specs:
  - specs/diataxis-requirements.yaml
  - specs/docs-build-workflow.yaml
  - specs/spec-registry.yaml
---

# RFC Spec Document Authoring Decisions

This note records the structural and editorial conventions of the Vultron
Protocol Specification, `docs/reference/vultron-spec/`, for anyone continuing or
extending it.

The lint model the page structure relies on — fragments linted as source,
page-scoped rules evaluated on each page that renders them — is
[ADR-0092](../docs/adr/0092-lint-fragments-as-source-page-rules-on-rendered-page.md).

---

## Fragments and Pages

All prose lives in `_`-prefixed **fragments**. A fragment is authored once and
never copied. **Pages** hold no prose of their own beyond frontmatter and an H1:
each is a thin shell of `{% include-markdown %}` directives over fragments. The
one exception is the landing `index.md`, whose routing framing is its own prose
(see "The landing page" below). Every section fragment a body or annex page
includes therefore renders on at least two pages — that page and `full.md`.

Section headings inside the fragments carry the section numbers and are what
the heading anchors derive from. Splitting the document into pages does not
change a heading, so it changes no anchor; it changes which page an anchor is
on.

---

## Page Map

The table lists each page of `docs/reference/vultron-spec/`, its nav title, and
the fragments it includes, in include order. Fragments that other fragments pull
in (the `_oq-*.md` open questions and the `includes/` tables) are not listed; they
arrive with their host fragment.

| Page | Nav title | Covers | Fragments included |
|---|---|---|---|
| `index.md` | Protocol Specification | Landing page | `_full-page-tip.md` |
| `introduction.md` | Introduction and Overview | Abstract, §1–§3 | `_full-page-tip.md`, `_abstract.md`, `_introduction.md`, `_terminology.md`, `_protocol-overview.md` |
| `layers.md` | Messages and Encoding | §4–§5 | `_full-page-tip.md`, `_messages.md`, `_encoding-transport.md` |
| `tracking-models.md` | Case Tracking Models | §6–§9 | `_full-page-tip.md`, `_rm-state-machine.md`, `_em-state-machine.md`, `_cs-dimensions.md`, `_pec-state-machine.md` |
| `interactions.md` | Coordination, Interactions, and Lifecycle | §10–§12 | `_full-page-tip.md`, `_case-coordination.md`, `_model-interactions.md`, `_participant-lifecycle.md` |
| `conformance.md` | Conformance | §13 Conformance | `_full-page-tip.md`, `_conformance/_intro.md`, `_conformance/_capability-sets.md`, `_conformance/_role-taxonomy.md`, `_conformance/_role-requirements.md`, `_conformance/_conformance-testing.md` |
| `considerations.md` | Considerations and References | §14–§16 | `_full-page-tip.md`, `_iana.md`, `_security.md`, `_references.md` |
| `annex-a-single-vendor.md` | Annex A Worked Example: Single-Vendor CVD | Annex A | `_full-page-tip.md`, `_annex-a.md` |
| `annex-b-multi-party.md` | Annex B Worked Example: Multi-Party CVD | Annex B | `_full-page-tip.md`, `_annex-b.md` |
| `annex-c-notation.md` | Annex C Notation Reference | Annex C | `_full-page-tip.md`, `_annex-c.md` |
| `annex-d-case-histories.md` | Annex D Possible Case Histories | Annex D | `_full-page-tip.md`, `_annex-d.md` |
| `annex-e-activitypub.md` | Annex E Relationship to ActivityPub | Annex E | `_full-page-tip.md`, `_annex-e.md` |
| `annex-f-behavior-trees.md` | Annex F Behavior Trees as an Implementation Pattern | Annex F | `_full-page-tip.md`, `_annex-f.md` |
| `annex-g-capability-shapes.md` | Annex G Capability Shapes | Annex G | `_full-page-tip.md`, `_conformance/_capability-shapes.md` |
| `open-questions.md` | Open Questions | Open Questions | `_full-page-tip.md`, `_open-questions.md` |
| `full.md` | — (not in nav) | The whole document | Every fragment above except `_full-page-tip.md`, in document order, plus `_annexes-intro.md` immediately before `_annex-a.md` |

### The landing page

`index.md` is a routing page (`contents: routing`, DF-11-005): its framing
links every body page, every annex page, `open-questions.md` and `full.md`, and
`docs-site --check` holds it to linking each member.

### `full.md`, the all-in-one page

`full.md` includes every section fragment in document order: the sequence the
body pages, the annex pages and `open-questions.md` give when read in nav order,
with the annexes nested under §17 Informative Annexes, which `_annexes-intro.md`
supplies. It exists for readers who want the whole document on one page, to read
through or print. It is listed in `not_in_nav` and sets `search: exclude: true`
in its frontmatter, so search results always land on the page that owns a
section. Readers reach it through the shared tip and the landing page. It is a
published page, so it is still a `lint-docs` target and its page-scoped rules
are evaluated (ADR-0092).

On `full.md` a cross-reference stays on the page. The MkDocs hook
`vultron/metadata/docs/full_page_links.py` runs after `include-markdown` and
rewrites each link to another page of the section that has a fragment to a bare
`#fragment` link. Links without a fragment, `index.md` links and every other page
are left unchanged, so no fragment is edited (#4092).

### The shared tip fragment

`_full-page-tip.md` is one inline admonition that links `full.md`. The landing
page and every content page include it; `full.md` does not. It is a fragment
like any other, so its wording is changed in one place.

### Nav

In the Reference nav the Protocol Specification comes first after the Reference
landing page, followed by Protocol Quick Reference, then Conformance Matrix. The
section opens on `index.md`, then lists the six body pages by name, then an
**Annexes** nav group with one entry per annex page and no index page of its
own, then **Open Questions** last. Nav titles carry no `[N]`/`[I]` tag; the
headings inside the fragments keep theirs.

---

## Annex Fragments

Each annex is its own fragment, `_annex-a.md` through `_annex-f.md`. Annex G
lives at `_conformance/_capability-shapes.md`, beside the §13 Conformance
fragments: it carries the informative account of capability shapes, and §13.6
Capability Shapes keeps the short normative text with its one conditional MUST.

On an annex page the annex heading is the page's top section (`##`). `full.md`
nests the annexes under §17 Informative Annexes by including each annex fragment
with a `heading-offset`.

`_annexes-intro.md` holds the §17 Informative Annexes heading and its paragraph
stating that no annex is normative and that a normative section governs where
the two appear to disagree. Only `full.md` includes it, so it is the one
fragment that renders on a single page. An annex page does not need it: the
`[I]` tag on the annex heading marks the annex as informative.

### Annex Sources

Annexes A–D pull in existing site pages that already hold the content, through
`include-markdown` `start`/`end` regions named in each annex fragment; Annexes
E–G are written in place. An included source page MUST read correctly both
standalone and embedded, which can mean light revision of headers that assume
standalone context. The region markers live in the source page; a renamed or
deleted marker silently includes the wrong span, so the review rubric checks
they still exist.

---

## Fragment Kinds

**§13 Conformance** is split into per-subsection files under `_conformance/`
because it is the longest section and its subsections are independently
authorable. Annex G lives there too (see "Annex Fragments").

**Open-question fragments** (`_oq-*.md`) are each one admonition. Most are
included in two places in the specification: inline at the point of use, in the
section fragment that first needs the answer, and in `_open-questions.md`. Such a
question renders on its point-of-use page, on `open-questions.md`, and twice on
`full.md`. A question with no point of use yet is included by
`_open-questions.md` alone. A question the model has since answered is closed
by deleting its fragment and stating the answer where the model is specified,
as the `UNINVITED`/`DECLINED` question was in §9.1 (#4296). Every one of them is
also included by `docs/topics/future_work/open_questions.md`, an Explanation
page, so each must satisfy that host's quadrant as well (DF-09-008).

**`includes/`** holds shared fragments reused across sections — the state
tables and the four-dimensions note. It is covered by
`not_in_nav: reference/vultron-spec/includes/*`.

---

## File Naming

- Section fragments: `_<semantic-slug>.md`, with no number. §13 Conformance
  subsections: `_conformance/_<semantic-slug>.md`.
- Annex fragments: `_annex-<letter>.md`.
- Open-question fragments: `_oq-<slug>.md`. Shared includes: `includes/<slug>.md`.
- Pages: an unprefixed semantic slug; annex pages `annex-<letter>-<slug>.md`.

Numbers are absent from fragment filenames on purpose. Document order is the
include order of `full.md`, and each body page includes a contiguous run of it.
Moving a section means editing `full.md`, the body pages that lose and gain it,
and the landing page if a body page's coverage changes — never renaming a file.

---

## Include Mechanism

The repository uses the `mkdocs-include-markdown` plugin, so the directive is
`{% include-markdown "./_file.md" %}`, not the `pymdownx.snippets` `--8<--` form.
The plugin's `heading-offset`, `start` and `end` arguments are what make annex
embedding work. Its `rewrite-relative-urls` (on by default) is what lets a
fragment's relative links resolve on every page that renders it; all pages sit in
one directory, so a fragment link resolves the same way on each.

State machine diagrams are included from the existing snippets under
`docs/topics/`, not redrawn. A diagram embedded in a larger topic page is
extracted to its own snippet first, so the topic page and the specification
include one source; the PEC diagram (`pec_state_machine_diagram.md`) is the
worked instance.

---

## Section Citations and Links

A section citation carries the section number **and** the section name: "§6
Report Management (RM) State Machine", never a bare "§6". This holds in prose
and in link text alike. The document spans pages, and a bare number does not say
which page to go to. The heading's `[N]`/`[I]` tag is not part of the name. An
annex is cited by letter and name: "Annex A Worked Example: Single-Vendor CVD".
The "—" after the annex letter in the heading is a separator and is dropped from
the citation; a "—" inside a section name is kept ("§8.1 VFD — Vendor Aware,
Fix Ready, Fix Deployed"). The docs style guide states the rule and a test under
`test/metadata/docs/` enforces it for `docs/` (#4062).

A link to a section targets the page that owns the section, with the heading
anchor: `tracking-models.md#6-report-management-rm-state-machine-n`. That keeps
every link valid on every page that renders the fragment. On `full.md` the
`full_page_links.py` hook rewrites such a link to the in-page `#anchor` (see
"`full.md`, the all-in-one page"), which holds only while every heading id is
the same on `full.md` as on its owning page and no two headings on `full.md`
share an id.

---

## Page-Scoped Rules on the Pages

Each page is evaluated as published (DF-09-003, DF-09-007; ADR-0092), so the
split decides what a fragment must carry:

- **Acronym expansion** (SG-07) resets per page. A fragment that is first to use
  an acronym on its page carries the expansion, even when an earlier page
  already made it. `full.md` then renders the expansion more than once, which is
  compliant (SG-44, DF-11-007).
- **Concept order** (SG-10) holds within a page. A concept a page needs from an
  earlier page is linked to its owning page (SG-11), not assumed.
- **Furniture** (SG-21, SG-39, SG-41) belongs to the page shell: the H1 matches
  the nav title, and the fragments' own headings stay below it.
- **Quadrant and audience** come from the hosting pages (DF-09-008, DF-11-010).
  Every specification page is Reference, and the annex sources keep their own
  quadrant as standalone pages too.

---

## Section Ordering: DAG-First Workflow

**Step 1 — DAG analysis before writing.** Map concept dependencies across
sections and within sections. A concept MUST NOT be used before it is
introduced. Record the confirmed section order and per-section concept
introduction notes in a `kind: plan` note that tracks the authoring issue, and
archive it when the PR merges; the PR description draws from it.

**Step 2 — Parallel section writes.** Subagents write each section independently
using the confirmed order and the per-section writing briefs from the DAG
analysis.

**Step 3 — Assembly and second DAG pass.** Read `full.md` to verify no concept
appears before its introduction, then read each body page on its own to verify
it introduces or links every concept it uses. Section order is adjustable
because only include directives need updating.

Keep the current order; each alternative was measured and is worse:

- Swapping §4 Messages and §5 Encoding and Transport increases unresolved
  forward references rather than reducing them.
- Moving §9 Participant Embargo Consent (PEC) State Machine ahead of §7 Embargo
  Management (EM) State Machine creates a definitional cycle, because PEC's
  states are defined by EM triggers.
- §10 Case Coordination stays a normative section of its own, ahead of §11 Model
  Interactions and Cascade Rules: the CASE_MANAGER is a protocol role every case
  has, so its duties are protocol, stated about the role. The dedicated Case
  Actor appears only in an informative note, because it is one way to hold the
  role, not the protocol's (ADR-0158).
- §13 Conformance before the back matter is correct per RFC 7322: conformance
  is a body section. §14 IANA and Namespace Considerations precedes §15 Security
  Considerations, and §16 References closes the body.

---

## Normative Text Comes from the YAML

The specification writes no normative sentence of its own (DF-12, ADR-0147).
The `protocol` and `foundation` tiers of `specs/*.yaml` are the normative text,
and the specification renders them in two forms:

- **Callouts** in the narrative: an `info` admonition holding a short table of
  the requirements a passage discusses, rendered by ID in the catalog's row
  format. The ID cell links to the catalog row. A callout naming an ID of any
  other kind fails the build (DF-12-003). Write one as a one-line exec block,
  `requirement_callout` from `vultron/metadata/specs/docs_render.py`:

  ````markdown
  ```python exec="true" idprefix=""
  from vultron.metadata.specs.docs_render import requirement_callout; print(requirement_callout("VM-10-001"))
  ```
  ````

- **The Requirements Catalog**, a body section after §13 Conformance: every
  requirement of the two tiers, once, one subsection per requirement file,
  files grouped onto themed pages, `foundation` rows on a page of their own
  (DF-12-001). The catalog row is the requirement's only anchor, apart from its
  in-page copy in `full.md` (DF-12-002).

Rules for the narrative around them:

- **No RFC 2119 keyword in prose** outside a rendered block; the §1.4 Document
  Conventions paragraph that states the convention is the one exception
  (DF-12-004). Prose
  says what a rule is for and how rules work together; the rule itself is a
  callout.
- **Reconcile, don't restate.** A prose statement the YAML holds becomes a
  callout and the YAML wording wins; if the prose was right, fix the YAML. A
  statement the YAML lacks becomes a new requirement or is reworded as
  informative. A cited ID that is not `protocol` or `foundation` is dropped or
  re-checked with the MS-12 tree — the specification never presents it as
  protocol.
- **Exec-printed links bypass the `full.md` rewrite.** The `full.md` link hook
  skips fenced code, which is how exec blocks are written, so the callout and
  catalog renderers emit in-page links themselves when rendering for `full.md`
  (DF-12-002).
- **The catalog waits for the kind re-audit.** Publishing makes the two tiers
  the normative text, so the catalog does not publish until every `protocol` and
  `foundation` item's kind is re-checked with the MS-12 tree (ADR-0147, #4888).
- **Placement is one table on the docs side** (DF-12-005): `CATALOG_PAGES` in
  `vultron/metadata/docs/requirement_catalog.py`. A new requirement file
  holding either tier fails `test_real_placement_table_is_sound` until it is
  placed on a catalog page; the requirement files carry no placement field.
  `render_catalog_page` in `docs_render.py` renders a page by its key.
- **Links follow the catalog's publication.** Until the catalog publishes,
  `CATALOG_PUBLISHED` is `False` and a callout links the row on the per-kind
  requirements page, which is the row the built site has; publishing flips the
  constant (#4901). The renderers learn the page they print on from the
  `exec_page.py` hook, so a fragment shared by several pages links correctly
  on each.
- **The keyword check grows with reconciliation.** `RECONCILED_FRAGMENTS` in
  `vultron/metadata/docs/rfc2119_keywords.py` lists the fragments the check
  enforces; each reconcile task adds its page's fragments (DF-12-004).
- **A message rule is stated on its occasion**: a situation in a case that a
  sender conveys with a particular wire activity. A two-letter protocol
  shorthand is a cross-reference tag and the vocabulary of the state machine
  transition tables, never the unit a rule is stated on, because the message
  reference already documents occasions and two message units would drift
  (ADR-0158).

---

## Source Treatment

A draft section may carry `*Source:` pointers. These are **author construction
notes**, not citations that appear in the published document.

| Source type | Treatment in published doc |
|---|---|
| `specs/*.yaml` pointers | Render as a callout (see "Normative Text Comes from the YAML"); never absorb into prose |
| `docs/**/*.md` pointers | Convert to `!!! info "See also"` admonition |
| `notes/*.md` pointers | Internal only; remove entirely |
| Bare YAML filenames | Never appear in published output |

The document is a **self-contained printable artifact**, and `full.md` is its
printable form. A reader MUST NOT need to chase a YAML file or implementation
code to understand what a conformant implementation must do.

"Self-contained" does not mean "duplicative." Prefer `{% include-markdown %}`
includes over rewriting content that already exists in the site. Whether to
include or rewrite is a per-section judgment call: include when the source page
works as a standalone reference; rewrite when the specification needs a tighter
or more normative framing.

---

## STE Style

Sections are written to ASD-STE100 aspirational style:

- Short sentences. Active voice. One instruction per sentence.
- Normative requirements are rendered callouts, never prose with RFC 2119
  keywords (DF-12-004).
- Apply the `simplified-technical-english` skill per section after drafting.

Enforcement is aspirational (style-guide level), not linted. Protocol vocabulary
(`VulnerabilityCase`, `EV`, `EC`, etc.) is exempt from any general word list.
