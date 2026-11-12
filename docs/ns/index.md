---
stakeholder_type: [platform-developer]
level: 300
page_type: reference
subject: protocol
---

# Vultron Vocabulary Namespace

**Namespace URI**: `https://certcc.github.io/Vultron/ns`

**JSON-LD context document**: [`context.jsonld`](context.jsonld)

---

This namespace defines the Vultron-specific vocabulary types and properties used in [Vultron protocol](https://certcc.github.io/Vultron/) wire messages.
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
| `EmbargoConsent` | One participant's consent to one embargo, a row of the consent table |
| `EmbargoEvent` | Embargo proposal, acceptance, revision, or termination record |
| `EmbargoPolicy` | Actor-level declaration of embargo preferences |
| `ParticipantStatus` | Per-participant snapshot: Report Management (RM) state, the vendor fix (vf) and deployment (d) dimensions of the CS, and roles |
| `ProcessingFault` | Negative acknowledgment returned when a received activity could not be processed |
| `VulnerabilityCase` | Coordination container for a vulnerability disclosure case |
| `VulnerabilityCaseStub` | Minimal stand-in for a case, sent as the target of a case Invite so the invitee can give informed consent before it holds the case |
| `VulnerabilityItem` | The case's entry for one vulnerability, in the identity fields of a CSAF 2.1 vulnerability entry |
| `VulnerabilityReport` | Initial report artifact submitted to a case |

This table must list exactly the terms `context.jsonld` declares.
Those terms come from the wire `type` value each class emits, never from its class name, so a class that emits another class's `type` value gets no term of its own.
The stub form of a case is its own type: it is transmitted as `"type": "VulnerabilityCaseStub"` and gets its own term.

## Declared properties

| Property name | Description |
|---------------|-------------|
| `expectedSenderSequence` | On a refusal notice for an activity's `senderSequence`: the positive integer the CASE_MANAGER expects next from that sender, so the sender numbers its next activity for the case no lower |
| `ledgerPosition` | The ledger position a `VulnerabilityCase` is a projection of: an object whose `logIndex` and `entryHash` name the last ledger entry its case file reflects, or `logIndex` -1 with the case's genesis hash before any |
| `senderSequence` | A participant's number for a case activity it sends the CASE_MANAGER: a positive integer, 1 for its first on the case and one more for each next one, kept by a resend |
| `terminationCause` | Why an embargo ended early, on the `Remove` that terminates it: an object whose `kind` is `THREAT_SIGNAL`, `FIX_READY`, `FIX_DEPLOYED` or `OTHER` |

This table must list exactly the properties `context.jsonld` declares.
A property's term is its name in the wire message.

## Link relation types

A `CaseReference` holds an AS2 `Link` in its `url`, and the Link's `rel` values say what kind of resource it points at.
Each value is a [CVE JSON schema](https://github.com/CVEProject/cve-schema) reference tag, written as an [RFC 8288](https://www.rfc-editor.org/rfc/rfc8288) link relation type.
A tag that IANA registers as a relation type keeps its bare name: `related` is the only one.
Every other tag is a URI under `https://certcc.github.io/Vultron/ns/rel/`, for example `https://certcc.github.io/Vultron/ns/rel/patch`.

| `rel` value | CVE reference tag |
|-------------|-------------------|
| `https://certcc.github.io/Vultron/ns/rel/broken-link` | `broken-link` |
| `https://certcc.github.io/Vultron/ns/rel/customer-entitlement` | `customer-entitlement` |
| `https://certcc.github.io/Vultron/ns/rel/exploit` | `exploit` |
| `https://certcc.github.io/Vultron/ns/rel/government-resource` | `government-resource` |
| `https://certcc.github.io/Vultron/ns/rel/issue-tracking` | `issue-tracking` |
| `https://certcc.github.io/Vultron/ns/rel/mailing-list` | `mailing-list` |
| `https://certcc.github.io/Vultron/ns/rel/media-coverage` | `media-coverage` |
| `https://certcc.github.io/Vultron/ns/rel/mitigation` | `mitigation` |
| `https://certcc.github.io/Vultron/ns/rel/not-applicable` | `not-applicable` |
| `https://certcc.github.io/Vultron/ns/rel/patch` | `patch` |
| `https://certcc.github.io/Vultron/ns/rel/permissions-required` | `permissions-required` |
| `https://certcc.github.io/Vultron/ns/rel/product` | `product` |
| `related` | `related` |
| `https://certcc.github.io/Vultron/ns/rel/release-notes` | `release-notes` |
| `https://certcc.github.io/Vultron/ns/rel/signature` | `signature` |
| `https://certcc.github.io/Vultron/ns/rel/technical-description` | `technical-description` |
| `https://certcc.github.io/Vultron/ns/rel/third-party-advisory` | `third-party-advisory` |
| `https://certcc.github.io/Vultron/ns/rel/vdb-entry` | `vdb-entry` |
| `https://certcc.github.io/Vultron/ns/rel/vendor-advisory` | `vendor-advisory` |

This table must list exactly the `rel` values a case reference accepts.

```json
{
  "type": "CaseReference",
  "id": "https://example.org/references/1",
  "name": "Vendor advisory",
  "url": {
    "type": "Link",
    "href": "https://vendor.example/advisories/2026-001",
    "mediaType": "text/html",
    "rel": ["https://certcc.github.io/Vultron/ns/rel/vendor-advisory"]
  }
}
```

## Usage in wire messages

A Vultron wire message lists two contexts in its top-level `@context`: the ActivityStreams 2.0 namespace first, then the Vultron JSON-LD context (VM-10-001).
The AS2 entry lets any AS2 receiver recognize the message, and the Vultron entry lets a receiver resolve Vultron type names to their full URIs.
The context document at this URI also imports AS2, but a receiver processes a message without fetching it (VM-10-003), so a message does not rely on that import:

```json
{
  "@context": [
    "https://www.w3.org/ns/activitystreams",
    "https://certcc.github.io/Vultron/ns/context.jsonld"
  ],
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
