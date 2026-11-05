---
status: accepted-provisional
date: 2026-11-05
created: 2026-11-05
updated: 2026-11-05
revision: 1
deciders: Allen D. Householder
consulted: >-
  Claude Opus 5.5; the #5226 epic-run plan for issue #5213 (2026-11-05), after the
  #5118 sweep judged every statement citation in the corpus
informed: []
stakeholder_type: [project-contributor]
---

# A Requirement a Statement Cites With No Relationship Is Listed in `see_also`, With a Reason

## Context and Problem Statement

A statement often names another requirement by ID.
The #5118 sweep judged each such citation against the SR-13 relationship types.
Most got a typed link.
Many fit no type: a rationale, a scope boundary, an example, or a link that would close a loop.
SR-13-018 forbids a link for those, so the citations stay in the prose with nothing recorded about them.

spec-lint is to fail on a citation with no link, so that a new citation is judged when it is written.
That check needs some way to tell a citation already judged as "no relationship" from one nobody has looked at.
How does a requirement record that a citation is deliberately not a relationship?

## Decision Drivers

- A relationship must assert something true: a change to the target affects the source (SR-13-018, ADR-0160).
- A new citation must be judged when it is written, not found by the next audit.
- A reader of a citation that has no link should be able to tell why.

## Considered Options

- A per-requirement `see_also` field: a list of `{spec_id, reason}` entries
- A new `see_also` relationship type
- Reword every such citation out of its statement

## Decision Outcome

Chosen option: "A per-requirement `see_also` field", because it records the judgment without making the requirements graph claim anything.

Every requirement ID a statement names is then one of two things.
It is the target of a relationship recorded on either end, or it is listed in the citing requirement's `see_also` with a short reason.
spec-lint fails on a cited ID in neither place.
It also fails on a `see_also` entry that has gone stale: the ID is no longer cited, is now linked, or names no requirement.

ADR-0160 rejected an exemption marker because each would need a reason, and the markers could grow like the unchecked links did.
That cost is accepted here for the citations no type fits, and only for those.
A citation that a type fits still gets the link, and the stale-entry check keeps the list from outliving its citations.

### Consequences

- Good, because the requirements graph still holds only links whose definitions hold, so the impact walk gets no false answer.
- Good, because a new citation cannot land unjudged: spec-lint asks for a link or a reason.
- Good, because the reason for leaving a citation unlinked is written next to the requirement, where a reader finds it.
- Bad, because a requirement may carry a `see_also` list as well as its relationships, which is one more field to keep current.
- Bad, because an author can put a citation in `see_also` to quiet the check when a link fits; review must still judge the reason.

## Pros and Cons of the Options

### A new `see_also` relationship type

- Good, because the schema keeps one list of cross-references.
- Bad, because a relationship asserts that a change to the target affects the source, and a see-also mention asserts no such thing (SR-13-018).
- Bad, because every graph consumer, from the impact walk to the loop check, would have to skip the type, and one that forgot would give a false answer.

### Reword every such citation out of its statement

- Good, because no new field is needed.
- Bad, because the citation is often the clearest way to state a scope boundary or point to where a rule lives, and the reader loses it.

## More Information

Generated spec requirements: `spec-registry.yaml` SR-13-022 (the citation rule) and SR-02-021 (the `see_also` field).
