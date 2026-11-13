---
status: accepted-provisional
date: 2026-11-13
created: 2026-11-13
updated: 2026-11-13
revision: 1
deciders: [Allen D. Householder]
consulted: []
informed: []
stakeholder_type: [project-contributor]
---

# Every Wire Field Has a Typed JSON-LD Term, With One Meaning per Name

## Context and Problem Statement

The Vultron JSON-LD context document defines the Vultron type names and only a few properties.
About eighty field names that Vultron puts on the wire have no term in it.
The AS2 context maps an unknown term to a blank node (`"@vocab": "_:"`), so a JSON-LD processor loses the meaning of every such field.
Some of these fields duplicate an AS2 term under another name, and some names carry a different meaning on different classes.
How should a wire field get its term, and what stops a new field from arriving without one?

## Decision Drivers

- A JSON-LD reader resolves every field Vultron sends to the meaning Vultron intends.
- Vultron's terms are no weaker than AS2's: AS2 types its terms, so a link reads as a link.
- Each new field forces its author to ask whether AS2 already has the term.
- The check is reproducible offline and needs no network fetch.
- Signing is not the driver: `eddsa-jcs-2022` signs the JSON text, so an undefined term does not weaken a signature.

## Considered Options

1. **Explicit, typed, flat terms checked against pinned external contexts** (chosen).
2. **Terms derived for every unknown field**, with the existing drift check as the only guard.
3. **Type-scoped terms**, so one name may mean different things on different classes.
4. **External terms from a hand-written list** instead of the published context documents.

## Decision Outcome

Chosen option: **explicit, typed, flat terms checked against pinned external contexts**, because it is the only option that both covers every field and makes the "does AS2 already have this?" question unavoidable for each new one.

**A field's term is declared, never inferred.**
A Vultron field carries a property marker with a one-line definition.
A field without the marker must be a term that a context Vultron cites already defines.
A check fails on a field that is neither.

**Terms are typed as AS2 types its own.**
A field whose value is an IRI is `"@type": "@id"`.
A field whose value is received JSON kept verbatim is `"@type": "@json"`.
An array whose order matters is `"@container": "@list"`.
A map keyed by IRIs is `"@container": "@index"`, so its keys are not read as properties.

**One meaning per name.**
Each wire name has one global term, as in AS2.
Two fields that share a wire name share one definition and one value kind.
A Vultron term never reuses a name that a cited context defines.
A name used for two meanings is renamed apart.

**External terms come from pinned copies.**
The check reads the terms of every context Vultron cites from a byte-for-byte local copy with recorded digests, as the CSAF schemas are kept.
A copy moves only when its pin is moved on purpose.

**Pending fixes are owned debt.**
A field that the check would refuse today, and that waits on a rename, is listed in a ratchet whose owner is an open Task, never an Idea.

### Consequences

- Good, because a JSON-LD processor resolves every Vultron field, links included.
- Good, because a new field cannot reach the wire without a recorded decision about its term.
- Good, because the AS2 duplicates the review found are renamed to AS2 terms instead of carrying Vultron copies.
- Bad, because every Vultron field carries a marker, and the colliding names must be renamed on the wire.
- Bad, because the pinned copies can fall behind their sources; the four contexts change rarely, and a versioned context never changes at its URL.

## Validation

Tests fail on a wire field with no term, on two declarations of one name that disagree, on a Vultron term that reuses an external term, on an edited pinned copy, and on a ratchet entry that no longer matches a field.

## Pros and Cons of the Options

### Explicit, typed, flat terms checked against pinned external contexts

- Good, because each field's term is a decision its author made.
- Bad, because the markers are churn on every field.

### Terms derived for every unknown field

- Good, because no field is ever termless and nothing needs marking.
- Bad, because a field that duplicates an AS2 term passes without anyone looking.

### Type-scoped terms

- Good, because no field is renamed.
- Bad, because the context grows nested definitions that AS2 itself does not use.

### External terms from a hand-written list

- Good, because no third-party files are committed.
- Bad, because the list can disagree with the contexts a processor actually reads, and a Vultron field can pass as AS2.

## More Information

Source: #6253.
The governing note is `notes/as2-vocabulary-alignment.md` § "Every Vultron Property Has a JSON-LD Term".
Generated spec requirements: VM-10-007 to VM-10-013, ARCH-18-012.
