---
title: RFC Spec Document Authoring Decisions
status: active
description: >
  Structural and editorial conventions for the Vultron Protocol Specification
  under docs/reference/vultron-spec/: the page map (routing landing page, six
  body pages, seven annex pages, Open Questions, hidden full.md) and the
  fragments each page includes, fragment naming, the per-annex fragment split,
  the shared tip fragment, the section citation convention, source treatment,
  STE style, and the DAG-first authoring workflow.
related_notes:
  - notes/documentation-strategy.md
  - notes/rfc-review-rubric.md
  - notes/site-information-architecture.md
  - notes/spec-authoring-rules.md
  - notes/case-state-model.md
related_specs:
  - specs/diataxis-requirements.yaml
  - specs/docs-build-workflow.yaml
---

# RFC Spec Document Authoring Decisions

This note records the structural and editorial conventions of the Vultron
Protocol Specification, `docs/reference/vultron-spec/`. The document was
written under #3255 and paginated into a Reference section under #4059. These
are durable conventions for anyone continuing or extending it.

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

`docs/reference/vultron-spec/` holds sixteen pages, built by issue #4061. The
table lists each page, its nav title, and the fragments it includes, in include
order. Fragments that
other fragments pull in (the `_oq-*.md` open questions and the `includes/`
tables) are not listed; they arrive with their host fragment.

| Page | Nav title | Covers | Fragments included |
|---|---|---|---|
| `index.md` | Protocol Specification | Landing page | `_full-page-tip.md` |
| `introduction.md` | Introduction and Overview | Abstract, §1–§3 | `_full-page-tip.md`, `_abstract.md`, `_introduction.md`, `_terminology.md`, `_protocol-overview.md` |
| `layers.md` | Protocol Layers | §4–§5 | `_full-page-tip.md`, `_semantic-layer.md`, `_syntactic-layer.md` |
| `tracking-models.md` | Case Tracking Models | §6–§9 | `_full-page-tip.md`, `_rm-state-machine.md`, `_em-state-machine.md`, `_cs-dimensions.md`, `_pec-state-machine.md` |
| `interactions.md` | Interactions and Lifecycle | §10–§11 | `_full-page-tip.md`, `_model-interactions.md`, `_participant-lifecycle.md` |
| `conformance.md` | Conformance | §12 | `_full-page-tip.md`, `_conformance/_intro.md`, `_conformance/_capability-sets.md`, `_conformance/_role-taxonomy.md`, `_conformance/_role-requirements.md`, `_conformance/_conformance-testing.md` |
| `considerations.md` | Considerations and References | §13–§15 | `_full-page-tip.md`, `_iana.md`, `_security.md`, `_references.md` |
| `annex-a-single-vendor.md` | Annex A Worked Example: Single-Vendor CVD | Annex A | `_full-page-tip.md`, `_annex-a.md` |
| `annex-b-multi-party.md` | Annex B Worked Example: Multi-Party CVD | Annex B | `_full-page-tip.md`, `_annex-b.md` |
| `annex-c-notation.md` | Annex C Notation Reference | Annex C | `_full-page-tip.md`, `_annex-c.md` |
| `annex-d-case-histories.md` | Annex D Possible Case Histories | Annex D | `_full-page-tip.md`, `_annex-d.md` |
| `annex-e-activitypub.md` | Annex E Relationship to ActivityPub | Annex E | `_full-page-tip.md`, `_annex-e.md` |
| `annex-f-behavior-trees.md` | Annex F Behavior Trees as an Implementation Pattern | Annex F | `_full-page-tip.md`, `_annex-f.md` |
| `annex-g-capability-shapes.md` | Annex G Capability Shapes | Annex G | `_full-page-tip.md`, `_conformance/_capability-shapes.md` |
| `open-questions.md` | Open Questions | Open Questions | `_full-page-tip.md`, `_open-questions.md` |
| `full.md` | — (not in nav) | The whole document | Every fragment above except `_full-page-tip.md`, in document order, plus `_annexes-intro.md` immediately before `_annex-a.md` |

The section ranges by name:

- **Introduction and Overview** — the Abstract, §1 Introduction, §2 Terminology
  and §3 Protocol Overview.
- **Protocol Layers** — §4 Semantic Layer — Message Meanings and §5 Syntactic
  Layer — Wire Format.
- **Case Tracking Models** — §6 Report Management (RM) State Machine, §7 Embargo
  Management (EM) State Machine, §8 Case State (CS) Dimensions and §9
  Participant Embargo Consent (PEC) State Machine.
- **Interactions and Lifecycle** — §10 Model Interactions and Cascade Rules and
  §11 Participant Lifecycle Within a Case.
- **Conformance** — §12 Conformance.
- **Considerations and References** — §13 IANA and Namespace Considerations, §14
  Security Considerations and §15 References.

### The landing page

`index.md` is a routing page (`contents: routing`, DF-11-005): its framing
links every part page, every annex page, `open-questions.md` and `full.md`, and
`docs-site --check` holds it to linking each member. It is recorded in the
decided-set table of `notes/site-information-architecture.md` § "Sub-section
index decisions".

### `full.md`, the all-in-one page

`full.md` includes every section fragment in document order: the sequence the body
pages, the annex pages and `open-questions.md` give when read in nav order, with
the annexes nested under §16 Informative Annexes, which `_annexes-intro.md`
supplies. It exists for readers who want
the whole document on one page, to read through or print. It is listed in
`not_in_nav` and sets `search: exclude: true` in its frontmatter, so search
results always land on the page that owns a section. It is reached only through
the shared tip. It is a published page, so it is still a `lint-docs` target and
its page-scoped rules are evaluated (ADR-0092).

### The shared tip fragment

`_full-page-tip.md` is one inline admonition that links `full.md`. The landing
page and every content page include it; `full.md` does not. It is a fragment
like any other, so its wording is changed in one place.

### Nav

In the Reference nav the Protocol Specification comes first after the Reference
landing page, followed by Protocol Quick Reference, then Conformance Matrix. The
section opens on `index.md`, then lists the six part pages by name, then an
**Annexes** nav group with one entry per annex page and no index page of its
own, then **Open Questions** last. Nav titles carry no `[N]`/`[I]` tag; the
headings inside the fragments keep theirs.

---

## Annex Fragments

Each annex is its own fragment, `_annex-a.md` through `_annex-f.md`. Annex G
lives at `_conformance/_capability-shapes.md`, beside the §12 Conformance
fragments: it carries the informative account of capability shapes, and §12.6
Capability Shapes keeps the short normative text with its one conditional MUST.

On an annex page the annex heading is the page's top section (`##`). `full.md`
nests the annexes under §16 Informative Annexes by including each annex fragment
with a `heading-offset`.

`_annexes-intro.md` holds the §16 Informative Annexes heading and its paragraph
stating that no annex is normative and that a normative section governs where
the two appear to disagree. Only `full.md` includes it, so it is the one
fragment that renders on a single page. An annex page does not need it: the
`[I]` tag on the annex heading marks the annex as informative.

### Annex Sources

Annexes pull in existing site pages where a page already holds the content. An
included source page MUST read correctly both standalone and embedded, which can
mean light revision of headers that assume standalone context.

| Annex | Source |
|---|---|
| A Worked Example: Single-Vendor CVD | `docs/tutorials/worked_example.md`, `single-vendor` region |
| B Worked Example: Multi-Party CVD | `docs/tutorials/worked_example.md`, `multi-party` region |
| C Notation Reference | `docs/reference/notation.md`, `notation-math` region |
| D Possible Case Histories | `docs/topics/measuring_cvd/possible_histories.md`, `possible-histories` region |
| E Relationship to ActivityPub | Written in place; links `docs/howto/activitypub/activities/` for wire examples |
| F Behavior Trees as an Implementation Pattern | Written in place; links `docs/topics/behavior_logic/` |
| G Capability Shapes | Written in place, in `_conformance/_capability-shapes.md` |

The regions are `include-markdown` `start`/`end` markers in the source page. A
renamed or deleted marker silently includes the wrong span, so the review rubric
checks they still exist.

---

## File Layout

```text
docs/reference/vultron-spec/
  index.md, introduction.md, layers.md, tracking-models.md,
  interactions.md, conformance.md, considerations.md,
  annex-a-single-vendor.md … annex-g-capability-shapes.md,
  open-questions.md, full.md     ← pages (see Page Map)
  _full-page-tip.md              ← shared tip linking full.md
  _abstract.md                   ← Abstract
  _introduction.md               ← §1 Introduction
  _terminology.md                ← §2 Terminology
  _protocol-overview.md          ← §3 Protocol Overview
  _semantic-layer.md             ← §4 Semantic Layer — Message Meanings
  _syntactic-layer.md            ← §5 Syntactic Layer — Wire Format
  _rm-state-machine.md           ← §6 Report Management (RM) State Machine
  _em-state-machine.md           ← §7 Embargo Management (EM) State Machine
  _cs-dimensions.md              ← §8 Case State (CS) Dimensions
  _pec-state-machine.md          ← §9 Participant Embargo Consent (PEC) State Machine
  _model-interactions.md         ← §10 Model Interactions and Cascade Rules
  _participant-lifecycle.md      ← §11 Participant Lifecycle Within a Case
  _conformance/                  ← §12 Conformance, one file per subsection
    _intro.md
    _capability-sets.md
    _role-taxonomy.md
    _role-requirements.md
    _conformance-testing.md
    _capability-shapes.md        ← Annex G Capability Shapes
  _iana.md                       ← §13 IANA and Namespace Considerations
  _security.md                   ← §14 Security Considerations
  _references.md                 ← §15 References
  _annexes-intro.md              ← §16 Informative Annexes heading (full.md only)
  _annex-a.md … _annex-f.md      ← Annexes A–F, one fragment each
  _open-questions.md             ← Open Questions summary
  _oq-*.md                       ← one open question each
  includes/                      ← shared tables and notes
```

**§12 Conformance** is split into per-subsection files because it is the longest
section and its subsections are independently authorable.

**Open-question fragments** (`_oq-*.md`) are each one admonition. Most are
included in two places: inline at the point of use, in the section fragment that
first needs the answer, and in `_open-questions.md`. Such a question renders on
its point-of-use page, on `open-questions.md`, and twice on `full.md`. A
question with no point of use yet (`_oq-pec-unbound-declined-collapse.md`) is
included by `_open-questions.md` alone.

**`includes/`** holds shared fragments reused across sections — the state
tables and the four-dimensions note. It is covered by
`not_in_nav: reference/vultron-spec/includes/*`.

---

## File Naming

- Section fragments: `_<semantic-slug>.md`, with no number. §12 Conformance
  subsections: `_conformance/_<semantic-slug>.md`.
- Annex fragments: `_annex-<letter>.md`.
- Open-question fragments: `_oq-<slug>.md`. Shared includes: `includes/<slug>.md`.
- Pages: an unprefixed semantic slug; annex pages `annex-<letter>-<slug>.md`.

Numbers are absent from fragment filenames on purpose. Document order is the
include order of `full.md`, and each part page includes a contiguous run of it.
Moving a section means editing `full.md`, the part pages that lose and gain it,
and the landing page if a part's coverage changes — never renaming a file.

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
the citation; a "—" inside a section name is kept ("§4 Semantic Layer — Message
Meanings"). The docs style guide states the rule and a test under
`test/metadata/docs/` enforces it for `docs/` (#4062).

A link to a section targets the page that owns the section, with the heading
anchor: `tracking-models.md#6-report-management-rm-state-machine-n`. On `full.md`
such a link leaves the page for the owning page; that is the cost of
single-sourcing the fragments, and it keeps every link valid on every page.

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
introduced. Produce authoring scratch-pads in `notes/` documenting the confirmed
section order and per-section concept introduction notes. These scratch-pads are
archived after the PR merges; the PR description draws from them.

**Step 2 — Parallel section writes.** Subagents write each section independently
using the confirmed order and the per-section writing briefs from the DAG
analysis.

**Step 3 — Assembly and second DAG pass.** Read `full.md` to verify no concept
appears before its introduction, then read each part page on its own to verify
it introduces or links every concept it uses. Section order is adjustable
because only include directives need updating.

The current order was measured, not assumed:

- Swapping §4 Semantic Layer — Message Meanings and §5 Syntactic Layer — Wire
  Format increases unresolved forward references rather than reducing them.
- Moving §9 Participant Embargo Consent (PEC) State Machine ahead of §7 Embargo
  Management (EM) State Machine creates a definitional cycle, because PEC's
  states are defined by EM triggers.
- §12 Conformance before the back matter is correct per RFC 7322: conformance
  is a body section. §13 IANA and Namespace Considerations precedes §14 Security
  Considerations, and §15 References closes the body.

---

## Source Treatment

Draft sections carried `*Source:` pointers. These are **author construction
notes**, not citations that appear in the published document.

| Source type | Treatment in published doc |
|---|---|
| `specs/*.yaml` pointers | Absorb into prose; remove the pointer |
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
- Normative requirements use RFC 2119 keywords (MUST, SHOULD, MAY, etc.).
- Apply the `simplified-technical-english` skill per section after drafting.

Enforcement is aspirational (style-guide level), not linted. Protocol vocabulary
(`VulnerabilityCase`, `EV`, `EC`, etc.) is exempt from any general word list.
