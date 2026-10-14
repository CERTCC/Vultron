---
title: "Diátaxis in Vultron: Quadrant Classification and the Docs Tooling"
status: active
kind: guidance
description: >
  How Vultron applies the Diátaxis framework (https://diataxis.fr/): the
  compass that classifies a page into one quadrant, the style guide that makes
  the prose rules binding, and the write-docs / lint-docs skills that apply
  them.
related_specs:
  - specs/diataxis-requirements.yaml
related_notes:
  - notes/documentation-sweeps.md
  - notes/message-type-reference.md
  - notes/site-information-architecture.md
---

# Diátaxis in Vultron: Quadrant Classification and the Docs Tooling

The framework itself — the four quadrants, what each owes its reader, and why
blurring them fails — is documented upstream at <https://diataxis.fr/>. Read it
there; this note keeps only the rules that are specific to this project.

## One page, one quadrant

A `docs/` page MUST NOT mix content types (DF-01-003). The commonest blur is a
tutorial that turns into a how-to: "tutorial" means *study*, not *easy*, and
"how-to" means *work*, not *advanced*. When a requested topic spans quadrants,
split it into one page per quadrant and cross-link them rather than writing one
blended page (`write-docs` § "Cross-quadrant requests").

## The Diátaxis compass

Classify a page by two questions — does it inform *action* or *cognition*, and
does it serve *acquisition* (study) or *application* (work)?

- Action + acquisition → **Tutorial**
- Action + application → **How-to Guide**
- Cognition + application → **Reference**
- Cognition + acquisition → **Explanation**

The quadrant decides voice, list discipline, and which tree the page lands in,
so settle it before drafting. Reason: an intuitive classification ("this is
advanced, so it is a how-to") is the usual source of a mixed page.

## Authoring and linting tooling

The prose rules that operationalize the framework are the normative style guide
`.claude/skills/shared/docs-style-guide.md`, made binding by DF-09-001. Its
`SG-nn` rules cover terminology, acronym expansion, concept order, sentence
shape, voice per quadrant, lists, and diagrams. Two skills apply it:

- `write-docs` authors or rewrites a page: classify the quadrant, plan concept
  order, draft against the style guide, register terms and acronyms, wire the
  nav.
- `lint-docs` audits existing pages, fixing mechanical findings and reporting
  judgment findings with a recommendation. `check-docs-sync` runs it as a
  blocking gate whenever a change touches `docs/`.

The style guide rules on one page at a time. The rules *above* the page — who
it is addressed to (`stakeholder_type`), how much it may assume (`level`),
where it sits in the nav — come from `notes/site-information-architecture.md`
(ADR-0102, DF-11). `lint-docs` reports level dependency (DF-11-002) as a
page-scoped finding and treats a repeated opening or re-expanded acronym on an
adjacent page as compliant, because each page must stand alone for a reader
arriving directly (DF-11-007).
