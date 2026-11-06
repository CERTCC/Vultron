---
status: accepted-provisional
date: 2026-11-06
created: 2026-11-06
updated: 2026-11-06
revision: 1
deciders: Allen D. Householder
consulted: Claude Opus 5.5; ADR-0069, ADR-0106; specs/vocabulary-model.yaml VM-10
informed: Vultron implementers
stakeholder_type: [project-contributor]
lint_suppress: [phantom_path_ref]
---

# Wire Artifacts Publish Under the Versioned Namespace, and Type Schemas Are Informative

## Context and Problem Statement

Vultron declares its own JSON-LD terms (`VulnerabilityCase`, `EmbargoEvent`, `CaseParticipant`, …) in a context document under the namespace host chosen by [ADR-0069](0069-vultron-namespace-uri.md).
An implementer outside the project has the context and the message examples, but no machine-readable description of what each Vultron object looks like.
JSON Schema is the common way to give one, and the Pydantic models that define those objects can produce it.

Three questions follow.
What role does a published schema play next to the specification?
At what URL does it live?
Where do the other machine-readable wire artifacts, the message examples, live alongside it?

JSON-LD itself sets no rule here.
JSON-LD and JSON Schema are separate standards: JSON-LD needs only the `@context` document to be dereferenceable, and a schema's `$id` is any URI its publisher picks.
[ADR-0106](0106-versioning-machine-facing-interfaces.md) already decides that vocabulary and object shapes share one wire version, carried in the context document's URL path.

## Decision Drivers

- JSON-LD lets the same data take several equivalent layouts: compacted or expanded, aliased keys, extra properties.
  JSON Schema checks one layout.
- A description that can drift from the code misleads the implementers it is meant to help.
- Object shapes are part of the wire version (ADR-0106), so every artifact that describes a shape is tied to that version.
- A peer looking for Vultron's machine-readable artifacts should find them in one place, under one versioning rule.
- A contributor browsing the repository should find them without knowing the namespace layout.

## Considered Options

1. **Everything wire-shaped under the versioned namespace; type schemas informative and generated** (chosen).
2. **A separate `data/` tree beside the docs**, as the SSVC project uses (`data/json/`, `data/schema/`), served from its own path.
3. **Unversioned schemas** at `ns/schema/`, published before the wire version exists.
4. **Normative schemas**, where a message that fails a schema is non-conforming.

## Decision Outcome

Chosen option: **everything wire-shaped under the versioned namespace, with type schemas informative and generated**, because it is the only option that gives each artifact the version ADR-0106 already assigns it without adding a second home or a second versioning rule.

**Type schemas are informative.**
A schema describes the compacted JSON form Vultron accepts.
The specification's requirements stay the authority on conformance.
A peer may use a schema to check its own output or to generate code; failing a schema does not by itself make a message non-conforming.

**Type schemas are generated, never hand-written.**
Each one is the Pydantic JSON Schema of the class that defines the term, in the form Vultron accepts.
A class that only shares the term's `type` value as a wire alias, such as the `{id, type}` case reference, contributes no schema.
The generated files are committed, and a drift check fails when a model changes without a regenerate, as it does for the context document.

**One schema per Vultron type.**
The set of type schemas covers exactly the Vultron type terms the context document declares.
The context's property terms, such as `senderSequence`, get no schema of their own.

**One versioned home.**
Every published machine-readable wire artifact lives under the wire-version segment of the namespace path:

| Artifact | Path under `https://certcc.github.io/Vultron/ns/` |
|---|---|
| JSON-LD context document | `v1/context.jsonld` |
| Type schemas | `v1/schema/types/<Type>.json` |
| Message examples | `v1/examples/<message>.json` |

`v1` stands for the current wire version.
A schema's `$id` is its published URL.
The namespace IRI, `https://certcc.github.io/Vultron/ns#`, does not change.

**Repository shortcuts are not URLs.**
Top-level `data/schema` and `data/examples` symlinks point at the current version's directories so the artifacts are easy to find when browsing the repository.
No published URL, `$id`, or documentation link goes through them.

**Moved artifacts leave no copy behind.**
When the message examples move into the namespace, their old URLs stop resolving.
A second URL serving the same file would hide the version from anyone who used it.

### Consequences

- Good, because a peer finds the context, the schemas, and the examples under one versioned path, and a wire-version bump moves all of them together.
- Good, because generated schemas cannot drift from the models without a failing check.
- Good, because informative schemas never make Vultron reject JSON-LD that is valid but laid out differently.
- Bad, because a schema's descriptions are the models' docstrings, which are written for developers rather than outside implementers.
- Bad, because the old example URLs stop resolving, and an outside link to one breaks.
- Neutral, because a checkout without symlink support shows the `data/` shortcuts as plain files, which costs only the browsing convenience.
- Neutral, because the artifacts cannot be public before the wire-versioned path is, since the namespace section is withheld from the site until then.

## Validation

- A drift check fails when a committed type schema differs from the one its model generates.
- A test fails when the set of type schemas differs from the set of Vultron type terms the context document declares.
- A test fails when a type schema declares no properties, which is what a schema generated in serialization form looks like.
- A test fails when a type schema's `$id` is not its published URL under the wire-versioned path.
- A test fails when the committed examples directory is not the versioned one, or when the old examples directory still holds an example.
- Review checks that no published URL, `$id`, or documentation link goes through the `data/` shortcuts.

## Pros and Cons of the Options

### Everything wire-shaped under the versioned namespace

- Good, because each artifact carries the wire version ADR-0106 gives it, with no new rule.
- Good, because the context and the schemas that describe its terms sit side by side.
- Bad, because the namespace layout is less obvious than a top-level `data/` folder when browsing the repository; the `data/` shortcuts answer this.

### A separate `data/` tree

- Good, because the folder is obvious when browsing the repository, and SSVC contributors already know the layout.
- Bad, because the wire artifacts end up in two homes, `ns/` and `data/`, and each needs its own version segment kept in step with the other.
- Bad, because the site is built from `docs/` alone, so the tree needs a symlink or a copy step before it gets a URL.

### Unversioned schemas

- Good, because they could be published before the wire version exists.
- Bad, because they contradict ADR-0106, and their URLs would move when the version arrives.

### Normative schemas

- Good, because they would give implementers a mechanical conformance check.
- Bad, because a schema checks one JSON layout while JSON-LD allows several, so a peer could refuse a valid message.
- Bad, because every schema change would become a question about the conformance contract, not only about documentation.

## More Information

Per-message schemas, one per Vultron message shape, are not part of this decision.
Under this layout they would live at `ns/v1/schema/messages/`.
Whether they are needed at all is an open Idea, #6065.
The layout itself is built by #6064, after the wire-versioned context path (#3653).

Generated spec requirements: `vocabulary-model.yaml` VM-10-006, VM-10-007.
