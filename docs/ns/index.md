---
stakeholder_type: [platform-developer]
level: 300
---

# Vultron Vocabulary Namespace

**Namespace URI**: `https://certcc.github.io/Vultron/ns`

**JSON-LD context document**: [`context.jsonld`](context.jsonld)

---

This namespace defines the Vultron-specific vocabulary types used in [Vultron protocol](https://certcc.github.io/Vultron/) wire messages.
Vultron messages are ActivityStreams 2.0 (AS2) Activities; the Vultron vocabulary extends the AS2 core vocabulary with Coordinated Vulnerability Disclosure (CVD) object types.
The shape of an activity is described in [Vultron and ActivityPub](../howto/activitypub/index.md).

## Declared types

| Type name | Description |
|-----------|-------------|
| `CaseLedgerEntry` | Entry in the canonical append-only case ledger |
| `CaseParticipant` | Actor-in-role binding within a specific case |
| `CaseParticipantRole` | A CVD role being offered to an actor in a case context |
| `CaseProposal` | Request to a Case Actor Service to initialize a new case |
| `CaseReference` | Typed external URL reference attached to a case |
| `CaseStatus` | Case-level status snapshot: the Embargo Management (EM) state and the public (pxa) dimensions of the Case State (CS) |
| `EmbargoEvent` | Embargo proposal, acceptance, revision, or termination record |
| `EmbargoPolicy` | Actor-level declaration of embargo preferences |
| `ParticipantStatus` | Per-participant snapshot: Report Management (RM) state, the vendor fix (vf) and deployment (d) dimensions of the CS, roles, and [embargo consent](../topics/behavior_logic/use-cases/embargo-lifecycle.md#which-messages-move-consent) |
| `ProcessingFault` | Negative acknowledgment returned when a received activity could not be processed |
| `VulnerabilityCase` | Coordination container for a vulnerability disclosure case |
| `VulnerabilityCaseStub` | Minimal stand-in for a case, sent as the target of a case Invite so the invitee can give informed consent before it holds the case |
| `VulnerabilityRecord` | Persistent identifier record for a confirmed vulnerability |
| `VulnerabilityReport` | Initial report artifact submitted to a case |

This table must list exactly the terms `context.jsonld` declares.
Those terms come from the wire `type` value each class emits, never from its class name, so a class that emits another class's `type` value gets no term of its own.
The stub form of a case is its own type: it is transmitted as `"type": "VulnerabilityCaseStub"` and gets its own term.

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
