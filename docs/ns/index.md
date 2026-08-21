---
draft: true
---

# Vultron Vocabulary Namespace

**Namespace URI**: `https://certcc.github.io/Vultron/ns`

**JSON-LD context document**: [`context.jsonld`](context.jsonld)

---

This namespace defines the Vultron-specific vocabulary types used in
[Vultron protocol](https://certcc.github.io/Vultron/) wire messages.
Vultron messages are ActivityStreams 2.0 Activities; the Vultron vocabulary
extends the AS2 core vocabulary with CVD-specific object types.

## Declared types

| Type name | Description |
|-----------|-------------|
| `CaseLedgerEntry` | Entry in the canonical append-only case ledger |
| `CaseParticipant` | Actor-in-role binding within a specific case |
| `CaseParticipantRole` | A CVD role being offered to an actor in a case context |
| `CaseProposal` | Request to a CaseActor service to initialize a new case |
| `CaseReference` | Typed external URL reference attached to a case |
| `CaseStatus` | Snapshot of all three state machines (RM/EM/CS) at one moment |
| `EmbargoEvent` | Embargo proposal, acceptance, revision, or termination record |
| `EmbargoPolicy` | Actor-level declaration of embargo preferences |
| `ParticipantStatus` | Per-participant snapshot of RM state and embargo consent |
| `VulnerabilityCase` | Coordination container for a vulnerability disclosure case |
| `VulnerabilityCaseStub` | Lightweight reference form of `VulnerabilityCase` |
| `VulnerabilityRecord` | Persistent identifier record for a confirmed vulnerability |
| `VulnerabilityReport` | Initial report artifact submitted to a case |

## Usage in wire messages

Vultron wire messages MUST declare the Vultron JSON-LD context to allow
receivers to resolve Vultron type names to their full URIs. The context
document at this URI imports the ActivityStreams 2.0 namespace, so
implementations cite only the Vultron context URI:

```json
{
  "@context": "https://certcc.github.io/Vultron/ns/context.jsonld",
  "type": "VulnerabilityCase",
  ...
}
```

## Stability note

This namespace is currently hosted on GitHub Pages
(`certcc.github.io/Vultron`). A permanent namespace URI (e.g., a `w3id.org`
redirect or a CERT/CC-controlled domain) may be registered in a future
version of this specification. Implementations should anticipate that the URI
may migrate; the context document will carry a `owl:sameAs` declaration when
a permanent URI is established.
