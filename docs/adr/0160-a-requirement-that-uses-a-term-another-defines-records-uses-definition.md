---
status: accepted-provisional
date: 2026-10-26
created: 2026-10-26
updated: 2026-10-26
revision: 1
deciders: Allen D. Householder
consulted: >-
  Claude Opus 5.5; design interview of 2026-10-26 on issue #5118, with a pilot audit
  of the HP, CS, ARCH and OX spec links
informed: []
stakeholder_type: [project-contributor]
---

# A Requirement That Uses a Term Another Requirement Defines Records `uses_definition`, and a Link No Type Fits Is Not Recorded

## Context and Problem Statement

Each spec relationship type states what it asserts and which end is upstream (SR-13).
The requirements graph built from those links answers "what does a change to this requirement affect?".
Most links in the corpus were written before the types were defined, so issue #5118 audited them.

A pilot over four spec families judged 135 links and 50 statement citations that had no link.
About four links in five were wrong.
Most were `refines` or `depends_on` recorded between siblings or unrelated requirements as a loose "related to".

Some relations fitted no type at all.
The most common was a requirement that uses a term another requirement defines, such as "an active participant (CM-10-004)".
A change to that definition changes what the citing requirement asks for, so the impact query should find it.
`depends_on` does not hold, because the citing requirement can often be met without the defining one being met.

The plan also makes spec-lint fail on a statement that cites a requirement it has no link to.
Without a type for this relation, every such citation would have to be reworded out of its statement.

## Decision Drivers

- The impact query must not miss a change that alters what a requirement asks for.
- A link must assert something true, or it gives the impact query a false answer.
- A statement should keep citing the requirement that defines its terms, because that is the clearest way to write it.

## Considered Options

- Add a `uses_definition` type, with B upstream
- Record such citations as `depends_on`
- Leave them unlinked, and exempt them from the citation check

## Decision Outcome

Chosen option: "Add a `uses_definition` type, with B upstream", because it is the only option that keeps every link true and still lets the impact query find a changed definition.

The same decision fixes what an auditor does with a link no type fits.
The link is deleted, not kept under the closest type.
A false link misleads the impact query, while a missing one costs at most a missed answer, and the statement's prose still cites the other requirement.

The second relation the pilot looked for was "this requirement must obey that general rule".
It turned up four times, and `constrains` recorded on the general rule already expresses it, so it gets no new type.

### Consequences

- Good, because a changed definition now reaches every requirement that uses it.
- Good, because `depends_on` keeps one meaning and does not become the new catch-all.
- Bad, because authors have one more type to choose between, and `uses_definition` can be misused as a loose "see also".

## Pros and Cons of the Options

### Record such citations as `depends_on`

- Good, because it adds no type.
- Bad, because the link would claim that A cannot be met unless B is met, which is false for most of these citations.

### Leave them unlinked, and exempt them from the citation check

- Good, because it adds no type.
- Bad, because the impact query misses a changed definition.
- Bad, because an exemption marker would need a reason on every such citation, and the markers would grow like the unchecked links did.

## More Information

Revisit this decision if `uses_definition` links come to name requirements whose terms the glossary defines better, because then the term belongs in the glossary rather than in a requirement.

Generated spec requirements: `spec-registry.yaml` SR-13-017, SR-13-018.
