---
status: accepted-provisional
date: 2026-08-21
deciders: Allen D. Householder
consulted: Vultron maintainers
informed: Vultron implementers
---

# Adopt certcc.github.io/Vultron as the Initial Vultron Vocabulary Namespace Host

## Context and Problem Statement

Vultron wire messages use ActivityStreams 2.0 vocabulary extended with
CVD-specific types (`VulnerabilityCase`, `EmbargoEvent`, `CaseParticipant`,
etc.). JSON-LD requires that type names be declared in a dereferenceable
`@context` document so receivers can resolve them to full URIs. Without a
stable namespace URI, the draft Vultron protocol specification cannot cite
a normative `@context` value, blocking external review and independent
implementation.

The blocker is deciding the namespace URI and making it dereferenceable.
Publishing a permanent namespace registration (e.g., `w3id.org`) and serving
a production-quality context document are deferred as follow-on work.

## Decision Drivers

- The draft spec (§4.1, §4.5) must cite a concrete namespace URI to circulate
  for review.
- The URI must be dereferenceable so JSON-LD processors can retrieve the
  context document.
- No new external infrastructure should be required before the PR merges.
- A permanent URI may be registered later; the initial choice should make
  migration straightforward.

## Considered Options

1. **GitHub Pages (`certcc.github.io/Vultron/ns`)** — the existing Vultron
   documentation site; context document lives in `docs/ns/context.jsonld`;
   no new infrastructure required.
2. **`w3id.org` redirect** — a community-managed permanent redirect service;
   would require a separate PR to the w3id.org GitHub repo and adds an external
   dependency with no code-change gate.
3. **Opaque URN (`urn:vultron:vocab:v1`)** — no dereference; violates JSON-LD
   best practice and prevents receivers from looking up the vocabulary.
4. **CERT/CC-controlled custom domain** (e.g., `vocab.vultron.org`) — maximum
   control; requires DNS and web-hosting setup outside this repository.

## Decision Outcome

Chosen option: **GitHub Pages (`certcc.github.io/Vultron/ns`)**, because it
is already under CERT/CC control, requires only a `docs/ns/` directory in
this repository, and makes the context document dereferenceable immediately
upon PR merge — with no external dependencies.

The namespace URI is `https://certcc.github.io/Vultron/ns`. The JSON-LD
context document is served at
`https://certcc.github.io/Vultron/ns/context.jsonld`. Outbound Vultron wire
messages MUST set `@context` to the context document URI (VM-10-001).

This decision is `accepted-provisional` because the GitHub Pages URI is tied
to the repository's current hosting location. If the project migrates to a
custom domain or registers a permanent URI with `w3id.org`, a new ADR
superseding this one will be written, and the context document will carry an
`owl:sameAs` declaration linking the old and new URIs.

### Consequences

- Good, because the namespace URI resolves immediately with no external steps.
- Good, because the `docs/ns/` directory is version-controlled alongside the
  vocabulary it describes.
- Good, because migrating to a permanent URI later is well-understood: update
  the context document, add an `owl:sameAs` triple, redirect the old URI.
- Bad, because the URI is tied to the GitHub Pages hostname, which is not
  a conventional permanent namespace host.
- Neutral, because `w3id.org` registration remains available as a future
  permanent-URI option without blocking the current work.

## Validation

VM-10-001 (in `specs/vocabulary-model.yaml`) requires outbound Vultron messages
to declare the Vultron context URI. Compliance is verified by serialization
tests that check `@context` values on `VultronAS2Object` subclass instances.

## More Information

Generated spec requirements: `vocabulary-model.yaml` VM-10-001, VM-10-002.

Source issue: CONCERN-2105 — "no stable Vultron vocabulary namespace URI to
cite (circulation blocker for draft spec)".
