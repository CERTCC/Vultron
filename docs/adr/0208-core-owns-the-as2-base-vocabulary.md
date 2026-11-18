---
status: proposed
date: 2026-11-17
created: 2026-11-17
updated: 2026-11-17
revision: 1
status_override: >-
  Kept proposed at the maintainer's instruction (Allen D. Householder, 2026-11-17, PR
  #6611): the decision is implemented against while the rest of the AS2 base vocabulary
  moves into core (ADR-0120).
deciders: Allen D. Householder
consulted: >-
  Claude Opus 5.5; the Epic #5746 run of Issue #6456 (PR #6611); ADR-0099;
  ADR-0198; specs/architecture.yaml ARCH-01, ARCH-12, ARCH-22, ARCH-25
informed: []
partially_supersedes:
  - 0099-one-object-model-as2-is-a-serialization.md
stakeholder_type: [project-contributor]
---

# Core Owns the AS2 Base Vocabulary

## Context and Problem Statement

The domain layer does not import the wire layer, and the wire layer may import only the domain's models and states.
That rule exists so the domain does not get stuck on the ActivityStreams 2.0 (AS2) data structures.
ADR-0099 then made every domain type one class in the domain, with AS2 as its serialization, and kept the remaining AS2 vocabulary (the base `Object`, `Link`, `Activity`, `Collection` and actor types) in a separate wire hierarchy.

That split now blocks domain rules that are about AS2 itself.
A received collection is exempt from the rule that a received whole object carries its time (CLP-15-011), but a slot of the domain that admits any object cannot know a collection: the collection types live only on the wire, and the domain may not import them.
The workaround, a second list of AS2 type names kept in the domain, duplicates what the wire already defines.
The AS2 base structures turned out to be useful for what the domain does, not a burden on it.

## Decision Drivers

- The domain needs to reason about AS2 base types (a collection, an actor, a link) without importing the wire.
- One definition of each AS2 type, with no copy of its names or fields kept elsewhere.
- Vultron stays interoperable: a valid AS2 object from a peer still validates, and Vultron's output stays valid AS2.
- The wire keeps what is about the wire: parsing and type resolution, its registries, the JSON-LD context, rehydration, factories, signing and the handling of unknown keys.

## Considered Options

- The domain owns the AS2 base vocabulary, held to AS2 by a conformance check.
- Keep the AS2 base vocabulary on the wire, and keep a copy of the type names the domain needs.
- Allow the domain to import the wire's AS2 base classes.

## Decision Outcome

Chosen option: "The domain owns the AS2 base vocabulary, held to AS2 by a conformance check", because it gives each AS2 type one definition that both layers can use, and keeps the import rule one-directional.

The AS2 base data classes are defined in the domain's models, and the wire's names for them are aliases of, or thin subclasses of, the domain classes, as ADR-0099 made the domain types.
The layer rule reads: the domain never imports the wire, and the wire may import the domain's models.

The domain's AS2 base classes stay AS2 models.
Each one models an AS2 type as the Activity Vocabulary defines it, under that type's name; it carries only properties AS2 allows on that type, and no Vultron property; and on receipt it requires nothing AS2 does not require, apart from Vultron receive rules that are recorded as departures.
Their serialized `type` values and property names are AS2's.
A conformance check against the pinned AS2 ontology enforces this, and it covers every base class the domain holds, including ones added later.

The base classes move into the domain as the work needs them; the collection types move first, and the rest of the base vocabulary follows.

This partially supersedes ADR-0099, detail 4: the wire and the domain no longer keep fully separate roots for the AS2 base vocabulary.
ADR-0099's other decisions, one class per domain type and AS2 as its serialization, are unchanged.

### Consequences

- Good, because a domain rule about an AS2 type (the collection exemption of CLP-15-011) reads the type's own class, with no second list of names.
- Good, because each AS2 base type has one definition, which the wire builds on.
- Good, because the conformance check catches a Vultron property, a renamed property or a changed `type` on a base class before it reaches a peer.
- Neutral, because a wire name for a base type becomes an alias, so a stored row of one keeps no `@context`, as a domain type's row already does.
- Neutral, because the order of keys in a serialized base object can change; AS2 gives key order no meaning.
- Bad, because the base vocabulary moves in steps, so for a time some AS2 base types are the domain's and some are the wire's.
- Bad, because a domain class is stricter than a lenient wire class (it refuses an unknown key at construction), so a base type that moves must keep the wire's receive leniency at the parse edge.

## Validation

An architecture test reads the pinned AS2 ontology, with its recorded departures from the Activity Vocabulary Recommendation, and checks every registered domain AS2 base class: its type is an AS2 type that the wire resolves to that class; each serialized property is one the ontology allows on that type; no property is marked as Vultron's; and an object carrying only its type and the recorded Vultron receive departures validates, with each departure still binding.
The layer-import ratchets keep the domain from importing the wire.

## Pros and Cons of the Options

### The domain owns the AS2 base vocabulary

- Good, because both layers share one definition of each AS2 type.
- Good, because the import rule stays one-directional.
- Bad, because the move is staged across several changes.

### Keep the base vocabulary on the wire, and copy the names the domain needs

- Good, because nothing moves.
- Bad, because the copy must be kept in step with the wire by hand or by a test, and each new domain rule about an AS2 type adds another copy.

### Allow the domain to import the wire's base classes

- Good, because it is the smallest change.
- Bad, because the domain then depends on the wire, which is the coupling the layer rule exists to prevent, and the wire's parsing and registration come with the import.

## More Information

Generated spec requirements: `architecture.yaml` ARCH-25-034, ARCH-25-035; amended ARCH-12-001 and ARCH-25-004.
