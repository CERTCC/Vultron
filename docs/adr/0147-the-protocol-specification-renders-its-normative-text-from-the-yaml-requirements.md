---
status: accepted-provisional
date: 2026-10-19
created: 2026-10-19
updated: 2026-10-21
revision: 1
deciders: Allen D. Householder
consulted: >-
  Claude Opus 5.5; ADR-0092, ADR-0128, ADR-0134, ADR-0136;
  notes/rfc-spec-authoring.md; specs/diataxis-requirements.yaml DF-10
informed: []
stakeholder_type: [project-contributor]
---

# The Protocol Specification Renders Its Normative Text from the YAML Requirements

## Context and Problem Statement

ADR-0136 made the Protocol and Foundation requirement tiers in `specs/*.yaml` the source of truth for the normative protocol, and made the Protocol Specification the document that presents them.
Any divergence between the two is a bug.

The specification does not present them today.
Its fragments are hand-written prose that restates a small selection of requirements in its own words.
About 120 lines carry an RFC 2119 keyword, many with no requirement ID beside them, and the prose cites 93 distinct IDs.
The two tiers hold about 1,230 requirements.
Some cited IDs are not normative at all: 14 of the 93 are Project or Architecture requirements.
Every restatement is a place where the specification and the YAML can drift apart, and a reader of the specification cannot see most of the rules a conformant implementation must obey.

How does the specification present the normative requirements so that it cannot state one differently from the YAML, and so that it presents all of them?

## Decision Drivers

- One authoritative source with many render points (DF-10-002): a requirement's wording exists only in the YAML.
- The specification is the complete normative text: a reader can find every rule a conformant implementation must obey without leaving it.
- Normative content belongs in the body of the specification, not in an annex.
- The explanatory sections that lead a reader into the protocol keep their flow; a list of more than a thousand rows must not interrupt them.
- Each requirement has one published home, so a link to it lands in one place.
- Drift is prevented by a check, not by authoring discipline.

## Considered Options

- Render selected requirements at their point of use, and leave completeness to the per-kind requirement pages.
- Map every requirement to the narrative section it supports, and render each section's full list under its narrative.
- Render selected requirements at their point of use, and render all of them in a Requirements Catalog body section.
- Keep hand-written prose, and require an ID beside each normative statement.

## Decision Outcome

Chosen option: "Render selected requirements at their point of use, and render all of them in a Requirements Catalog body section", because it is the only option that makes the specification both drift-proof and complete without breaking the flow of its explanatory sections.

The decision has five parts.

1. **A Requirements Catalog is a body section.**
   It follows the Conformance section and precedes the back matter.
   It renders every Protocol and Foundation requirement exactly once, across several pages.
   A subsection is one requirement file, and requirement files are grouped into themed pages.
   Foundation requirements, which Vultron inherits unchanged from ActivityStreams 2.0, ActivityPub, or HTTP, are on a page of their own, so the line between what Vultron adds and what it inherits stays visible.
2. **The catalog row is a requirement's one home.**
   The anchor for a requirement is defined only by its catalog row, and by that row's copy in the single-page edition of the specification.
   Every other place that shows or links the requirement links to that row.
   The separate Protocol Requirements and Foundation Requirements pages are retired, and their published URLs redirect to the catalog.
   On Implement the Protocol, the **Protocol Requirements** label that ADR-0136 gave the two tiers now names the catalog.
3. **The narrative shows requirements as rendered callouts.**
   Where an explanatory section needs a rule, it shows the rule as a callout rendered from the YAML by ID, in the same row format as the catalog.
   A callout fails the build when an ID does not name a Protocol or Foundation requirement.
4. **Hand-written normative keywords are not allowed in the specification.**
   Outside rendered blocks, the specification's prose carries no RFC 2119 keyword.
   The one exception is the Document Conventions paragraph in the Introduction, which states the keyword convention.
   A check enforces this.
   An existing normative statement becomes a callout when the YAML holds it; the YAML wording governs, and the YAML is corrected where the prose was right.
   A statement the YAML does not hold becomes a new requirement or is reworded as informative.
5. **Where each requirement file appears is declared once, on the documentation side.**
   The requirement files keep their format.
   A check fails when a file that holds Protocol or Foundation requirements is placed on no catalog page, or on more than one for the same tier.

The catalog does not publish until the kind of every Protocol and Foundation requirement has been re-checked against the who-must-obey decision tree (ADR-0134).
Publishing the tiers in full makes them the normative text, so a misfiled requirement would become protocol law.

### Consequences

- Good, because the specification cannot state a requirement differently from the YAML: the words a reader sees are the YAML's words.
- Good, because the specification is complete: every Protocol and Foundation requirement renders in it.
- Good, because the explanatory sections stay readable: they show only the rules they discuss, and the full list follows them.
- Good, because a requirement has one anchor, so links to it cannot disagree about where it lives.
- Bad, because a page redirect cannot keep a fragment: an old deep link to a requirement on a retired page lands at the top of the catalog, not on its row.
- Bad, because the catalog adds a section, so the back-matter sections and the annex section are renumbered once, and links to them are updated.
- Bad, because the specification grows by more than a thousand rows, which the single-page print form carries in full.
- Neutral, because the reconcile work turns up statements the YAML lacks; adding them is work the drift already owed.

## Validation

- A check fails when any Protocol or Foundation requirement renders in the catalog zero times or more than once, or when a requirement file holding either tier is unplaced or placed twice.
- A callout that names an ID outside the two tiers fails the documentation build.
- A check fails on an RFC 2119 keyword in the specification's prose outside rendered blocks and the Document Conventions paragraph, and reports an empty target set as a failure (DF-09-009).
- The strict site build and the link and continuity checks (DOCBW-03) cover the renumbered sections and the redirected pages.

## Pros and Cons of the Options

### Render selected requirements at their point of use, and leave completeness to the per-kind requirement pages

- Good, because it is the smallest change and stops drift in what the specification states.
- Bad, because the specification stays incomplete: most normative rules live only on a separate page that is not part of the specification.

### Map every requirement to the narrative section it supports

- Good, because each rule appears beside the explanation it belongs to.
- Bad, because about 255 requirement groups each need a section assignment that must be kept current.
- Bad, because a full list under each explanatory section breaks the flow of the lead-in material.

### Render selected requirements at their point of use, and render all of them in a Requirements Catalog body section

- Good, because it meets every decision driver.
- Neutral, because it needs one placement table, at the granularity of a requirement file rather than a group.
- Bad, because it renumbers the sections after Conformance once.

### Keep hand-written prose, and require an ID beside each normative statement

- Good, because the narrative keeps its own wording.
- Bad, because the wording can still drift from the YAML; the ID shows which requirement is meant, not that the words agree.
- Bad, because the specification stays incomplete.

## More Information

An annex was considered as the home of the catalog and rejected: the specification's annex section states that no annex is normative, and the catalog is the normative text.
Placing the catalog after the Conformance section renumbers the fewest cited sections.

ADR-0128 made the message vocabulary documentation a projection of the semantic registry; this decision applies the same principle to the specification's requirements.

The renderer's kind-routing requirements, SR-09-001 and SR-09-002, were amended to route the two tiers to the catalog.

Generated spec requirements: `diataxis-requirements.yaml` DF-12-001 through DF-12-006.
