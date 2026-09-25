---
status: accepted-provisional
date: 2026-09-25
deciders: Allen D. Householder
consulted: Vultron maintainers
informed: Vultron implementers
stakeholder_type: [project-contributor]
---

# Version Each Machine-Facing Interface Independently of the Release Tag

## Context and Problem Statement

Vultron ships several things that other software depends on: the wire format that peers parse, the protocol behavior that peers rely on, the hash-chained case ledger, the HTTP API, the stored data, the configuration files, and the Python package.
Each changes at its own pace, and each breaks a different audience when it changes incompatibly.
ADR-0006 gives the project one CalVer number, and a pending amendment (#3553) will make that number the name of a release.
A release name tells a reader *when* something shipped.
It does not tell a peer, a client, or an upgrading deployment whether the interface it depends on is still compatible.

Planning for #2960 first proposed a maturity manifest: a tier (experimental, stable, …) for each page and artifact.
That premise was dropped.
A page has no "breaking change", so a maturity tier on a page means nothing.
The question this ADR answers is narrower: **besides the release tag, what gets a version, what carries it, and what bumps it?**

## Decision Drivers

- A version exists to tell a dependent that something incompatible changed.
  A version that nothing reads, or that moves when nothing broke, is noise.
- Interfaces break different audiences at different times.
  Tying them to one number makes every bump a false alarm for most of them.
- The prototype has no known external dependents, and it cannot count them: it is open source, and it does not phone home, for operational security.
  Dependents have to be assumed, never observed.
- Version negotiation between peers does not exist yet (#3368).
  Any version that only negotiation would read has no reader today.
- `GET /version` is reachable by anyone who can reach the server.
  An exact build string tells an attacker which known defects apply.
- Existing rules already cover part of the ground: requirement IDs are stable and never renumbered (MS-04-003), superseded requirements are deleted rather than deprecated (MS-04-005, MS-09-001), no compatibility shims are kept in code (CS-15-001), and each case ledger starts from a per-case genesis hash (CLP-08-001).

## Considered Options

1. **Version each machine-facing interface on its own, bumping it only on an incompatible change to that interface** (chosen).
2. **One combined wire-and-behavior version**, carried in the context document URL.
3. **A hand-bumped behavior version**, separate from the wire version.
4. **A ledger format identifier on every entry**, rather than once per case.
5. **Date-pinned API version headers**, as Stripe and GitHub use.
6. **NodeInfo as the place to advertise versions.**
7. **A maturity manifest** with a tier for each page and artifact.

## Decision Outcome

Chosen option: **version each machine-facing interface on its own, bumping it only on an incompatible change to that interface**.
It is the only option in which every version has a reader and every bump means that reader has something to act on.

**Interface versions are independent of the CalVer release tag.**
A release may bump none, one, or several interface versions.
The release tag never implies an interface version, and an interface version never implies a release.

### Interfaces, carriers, and bump rules

| Interface | Who it breaks | Version carrier | Bump rule |
|---|---|---|---|
| Wire format: vocabulary, object shapes, and error-type URIs | peers | One wire version, carried in the context document URL (for example `https://certcc.github.io/Vultron/ns/v1/context.jsonld`). The namespace IRI never changes. | Bump on an incompatible change to a term, a shape, or an error-type URI. An additive change goes into the current version's context document and does not bump. Negotiation stays with #3368. |
| Protocol behavior: state machines and what a message obliges | peers | No version. | An incompatible change to what a requirement obliges gets a **new requirement ID**; the old ID is removed (MS-04-005). An in-place edit to an existing ID is a clarification only. Release notes list the IDs added and removed since the previous tag. |
| Ledger hash format: algorithm, canonicalization, genesis derivation | peers, and every stored ledger | A format identifier, recorded **once per case, at genesis**. | A new format applies to new cases. An existing chain keeps verifying under the format it recorded. |
| HTTP API | clients | The path major, `/api/v2`. | Bump only on an incompatible change. Additive changes do not bump. |
| `GET /version` and OpenAPI `info.version` | clients | Report **compatibility**: API major, wire version, and ledger format. | Never report the exact build. |
| Stored data: the SQLite store and its JSON blobs | an upgrading deployment | A stored-format marker. | On a mismatch the server will refuse to start. There will be no migrations in the prototype; they are tracked as a productionization Idea (#3661). |
| Configuration YAML | deployers | No version. | Every configuration model will reject unknown keys, so a renamed or removed key will fail loudly. |
| Python library and CLI | library users | The package CalVer (ADR-0006, with the amendment pending in #3553). | As the release tag. |
| Spec-file `version:` fields | nobody | None: the fields are removed. | Not applicable. |

Four rows need more than the table gives them.

**Wire and behavior are split on purpose.**
The context document URL changes only on an incompatible change to the term map.
If behavior shared that version, a change to what a message *means*, with every term unchanged, would mint a new context URL whose document is identical to the old one.
Behavior is therefore tracked at the granularity it actually changes: the requirement.
MS-04-003 already makes a requirement ID permanent, so a new obligation under a new ID is visible in a diff of IDs, and the old obligation's removal is visible the same way.

**The ledger format is fixed per case.**
A chain's hashes are computed under one algorithm, one canonicalization, and one genesis derivation; the genesis is per case (CLP-08-001).
Changing any of them mid-chain would make the chain unverifiable at the join.
Recording the format once at genesis lets every existing chain keep verifying under its own format while new cases adopt a new one.

**The version endpoint reports compatibility, not the build.**
A client needs to know whether it can talk to the server.
The API major, the wire version, and the ledger format answer that.
An exact build string answers a different question, one that mainly helps an attacker match the server against known defects.

**Stored data refuses rather than migrates.**
A prototype deployment can be wiped and rebuilt.
Writing migrations now would build machinery that no deployment needs, and a store that is silently misread is worse than one that refuses to start.

### Maturity

Every interface is experimental: an incompatible change may happen in any release, and it is signalled by bumping that interface's version.
There are no maturity tiers and no manifest.
This is the smallest statement that is true, and adding tiers now would be building for a promise nobody has asked for (YAGNI).

The following is **non-normative guidance for later**, not a rule this ADR imposes:

- Promote an interface to a stated promise *before* inviting outsiders to build on it: before a standards submission, an integrator tutorial, or an interoperability event.
- A passing test is necessary for such a promise but not sufficient; the promise is a commitment about future changes, which no test observes.
- Assume that dependents exist.
  The project cannot observe them (open source, no telemetry), so the absence of known dependents is not evidence that there are none.

### Reconsider when

- **Version negotiation exists (#3368).** A separate behavior version then has a reader, and may be worth adding.
- **The first interface needs a promise.** Maturity tiers then have something to express.
- **A deployment cannot be wiped.** Stored-data migrations then become necessary.

### Consequences

- Good, because a dependent watches only the version of the interface it uses, and a bump always means that interface changed incompatibly.
- Good, because behavior changes become visible as requirement-ID additions and removals, which release notes can list mechanically.
- Good, because existing case ledgers stay verifiable across a hash-format change.
- Good, because `GET /version` will stop disclosing the exact build.
- Bad, because there are several version numbers to keep track of instead of one.
- Bad, because a behavior change carries no version at all until negotiation exists; a peer learns of it only from the release notes.
- Neutral, because a stored-data mismatch forces a wipe, which is acceptable only while no deployment holds data it cannot lose.

## Validation

None of the carriers above exist yet; each is delivered by its own issue, and each will be validated there.

- The wire version in the context document URL: #3653.
  VM-10-001 and VM-10-002 will be amended there to name the versioned URL.
- The ledger hash-format identifier recorded at genesis: #3654.
- The stored-format marker and refusal to start: #3655.
- Configuration models that reject unknown keys: #3656.
- `GET /version` and OpenAPI reporting compatibility versions: #3657.
- The new-requirement-ID rule and the generated changed-requirements list for release notes: #3658.
- Removing spec-file `version:` fields: #3652.

The ADR's status will advance to `accepted` once those carriers are built and tested.

## Pros and Cons of the Options

### One combined wire-and-behavior version

- Good, because there is one number for peers to compare.
- Bad, because a meaning-only change would bump the context document URL and publish a new context document identical to the old one: two URLs, one term map.
- Bad, because a wire-only change and a behavior-only change become indistinguishable to a reader.

### A hand-bumped behavior version

- Bad, because nothing reads it until version negotiation exists (#3368).
- Bad, because "incompatible" is not machine-detectable for behavior, so the bump rests on each author's judgment and drifts.
- Neutral, because it can be added later if negotiation gives it a reader; that is a reconsider trigger above.

### A ledger format identifier on every entry

- Bad, because it allows a chain to mix formats, which is exactly what makes a chain unverifiable at the join.
- Bad, because it repeats one value on every entry for no reader that needs it more than once.

### Date-pinned API version headers (Stripe, GitHub)

- Good, because they let a server evolve continuously while each client pins a date.
- Bad, because they require the server to keep every dated behavior alive, a standing compatibility layer that the prototype has no client for; CS-15-001 takes the same position on compatibility shims in code.
- Bad, because a path major is enough for an API with no known external clients.

### NodeInfo for version advertisement

- Neutral, because NodeInfo is a fediverse server-discovery document, not a compatibility contract; it is filed separately as an Idea (#3662) and does not decide how versions are carried.

### A maturity manifest per page and artifact

- Bad, because a page has no breaking change, so a tier on it means nothing.
- Bad, because a tier table is a hand-kept fact that no test can falsify, and it drifts (MS-16-002).

## More Information

- ADR-0006, with the amendment pending in #3553, governs release naming; this ADR does not change it.
- ADR-0069 chose the namespace host and IRI; this ADR changes only the path of the context document within it.
- Source: #2960, which enumerated the versionable components.
- Related bugs found while planning: #3659 (ledger canonicalization is not RFC 8785) and #3660 (outbound delivery's media type).

Generated spec requirements: none yet.
The implementing issues listed under Validation will add or amend them, and will cite this ADR.
