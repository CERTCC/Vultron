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

<!-- BEGIN GENERATED PROPERTY TABLE — do not edit; change the field's vultron_property() declaration, then run `uv run wire-context --write` -->

| Property name | Value kind | Description |
|---------------|------------|-------------|
| `activeEmbargo` | iri | The embargo active on a case, as its case stub carries it: an EmbargoEvent or its id |
| `actorParticipantIndex` | index of iri | A map from the id of each actor in a case to the id of its CaseParticipant |
| `caseActivity` | set of iri | The ids of activities about a case |
| `caseEngagement` | plain | Whether a participant reports itself engaged in a case |
| `caseParticipants` | set of iri | The participants of a case, each a CaseParticipant or its id |
| `caseReferences` | set of iri | The external references of a case, each a CaseReference or its id |
| `caseRoles` | set | The CVD roles a participant holds in a case |
| `caseStatus` | iri | The case status a participant status or a case stub reports: a CaseStatus object or its id |
| `caseStatuses` | list of iri | The statuses of a case, oldest first, each a CaseStatus or its id; the last is its current status |
| `category` | plain | The CSAF category of a vulnerability note, such as description or summary |
| `cause` | plain | Why an embargo ended early: an object whose kind names the cause |
| `childCases` | set of iri | The ids of a case's child cases |
| `cvdRole` | set | The CVD roles a participant status reports its participant holding in the case |
| `cve` | plain | The CVE ID of a vulnerability |
| `dState` | plain | A deployer participant's fix-deployed (D) dimension of the Case State (CS) |
| `emState` | plain | The Embargo Management (EM) state of a case: NONE, PROPOSED, ACTIVE, REVISE or EXITED |
| `embargo` | iri | The embargo an embargo-register entry records: an EmbargoEvent or its id |
| `embargoConsents` | set | A participant's consent rows, one for each embargo in its case's embargo register |
| `embargoId` | iri | The id of the embargo a consent row records an answer to |
| `embargoPolicy` | plain | The embargo policy an actor publishes in its profile: an EmbargoPolicy object |
| `embargoRegister` | list | Every embargo ever proposed on a case, in the order proposed, each an entry that gives its status |
| `entryHash` | plain | The SHA-256 hash, in hex, of a case ledger entry's canonical content; the case's genesis hash in a ledger position that names no entry |
| `expectedSenderSequence` | plain | On a refusal notice for an activity's senderSequence: the positive integer the CASE_MANAGER expects next from that sender, so the sender numbers its next activity for the case no lower |
| `failureClass` | iri | The URI of the class of failure that stopped a received activity from being processed |
| `genesisHash` | plain | The hash that starts a case's ledger chain, computed from its owner; the first ledger entry's prevLogHash |
| `ids` | set | The identifiers other systems give a vulnerability, each an object with a systemName and a text |
| `joined` | plain | Whether a participant has joined its case: it was seated when the case was created, or it accepted its case invitation |
| `kind` | plain | The kind of an embargo's early-termination cause: THREAT_SIGNAL, FIX_READY, FIX_DEPLOYED or OTHER |
| `ledgerPosition` | plain | The last entry of a case's ledger that a case file, or the sender of an activity about the case, holds: an object whose logIndex and entryHash name that entry, or logIndex -1 with the case's genesis hash when it holds none |
| `logIndex` | plain | The position of an entry in its case's ledger, counting from 0; -1 in a ledger position that names no entry |
| `logObjectId` | iri | The id of the activity or object a case ledger entry records |
| `maximumDuration` | plain | The longest embargo duration an actor accepts, as an ISO 8601 duration |
| `minimumDuration` | plain | The shortest embargo duration an actor accepts, as an ISO 8601 duration |
| `parentCases` | set of iri | The ids of a case's parent cases |
| `participantStatuses` | list | A participant's statuses in a case, oldest first; the last is its current status |
| `payloadSnapshot` | json | The activity a case ledger entry records, kept verbatim as its sender sent it |
| `pendingEmbargoProposalIndex` | index of iri | A map from the id of each open embargo proposal on a case to the id of the Invite that relayed it |
| `preferredDuration` | plain | The embargo duration an actor prefers, as an ISO 8601 duration |
| `prevLogHash` | plain | The SHA-256 hash, in hex, of the case ledger entry before this one, or the case's genesis hash for the first entry |
| `proposedEmbargo` | iri | The embargo a reporter proposes for a report, on its Offer of the report: an EmbargoEvent or its id |
| `proposerCaseRoles` | set | The CVD roles a case proposer holds in a case it owns |
| `pxaState` | plain | The public-awareness, exploit and attack (P, X, A) dimensions of a case's Case State (CS), as one state name |
| `receivedAt` | plain | When the CASE_MANAGER received the activity a case ledger entry records, as a UTC date-time |
| `references` | set of iri | The external references about a vulnerability, each a CaseReference or its id |
| `removalActivity` | iri | The id of the Remove activity that took a participant out of active participation in its case; absent while it is not removed |
| `replaces` | iri | The id of the embargo that an activated revision replaced |
| `rmState` | plain | A participant's Report Management (RM) state in a case |
| `role` | plain | The CVD role offered to an actor in a case |
| `roles` | set | The CVD roles an Invite to a case offers the invitee |
| `rsvpDeadline` | plain | The time by which an invited participant is to answer an embargo invitation, as a UTC date-time |
| `semanticType` | plain | The Vultron message-semantics label of the act a case ledger entry records |
| `senderSequence` | plain | A participant's number for a case activity it sends the CASE_MANAGER: a positive integer, 1 for its first on the case and one more for each next one, kept by a resend |
| `siblingCases` | set of iri | The ids of a case's sibling cases |
| `signals` | set | The threat signals (P, X, A) set on a case when its embargo ended |
| `state` | plain | A participant's consent to one embargo: UNINVITED, INVITED, AGREED, DECLINED or TIMED_OUT |
| `status` | plain | The status of an embargo in its case's embargo register, such as PROPOSED, ACTIVE or TERMINATED |
| `stubSummary` | plain | The summary a case owner chose for the case stub it sends to invitees, which may say less than the case's name |
| `suggestedRoles` | set | The CVD roles an Offer that recommends an actor suggests it take in a case |
| `systemName` | plain | The name of the system that issued a vulnerability identifier |
| `term` | plain | The cluster term in which the CASE_MANAGER committed a case ledger entry; absent on a single-node deployment |
| `termination` | plain | How a terminated embargo ended: an object that gives the reason and, when recorded, its cause |
| `terminationCause` | plain | Why an embargo ended early, on the Remove that terminates it: an object whose kind is THREAT_SIGNAL, FIX_READY, FIX_DEPLOYED or OTHER |
| `title` | plain | The title of a vulnerability note |
| `trackingId` | plain | A participant's own tracking identifier for a case, such as its internal ticket number |
| `vendors` | set of iri | The ids of the vendors whose readiness to fix made the quorum that ended an embargo |
| `vfState` | plain | A vendor participant's vendor-awareness and fix-readiness (V, F) dimensions of the Case State (CS), as one state name |
| `vulnerabilityItems` | set of iri | The vulnerabilities a case covers, each a VulnerabilityItem or its id |
| `vulnerabilityReports` | set of iri | The vulnerability reports of a case, each a VulnerabilityReport or its id |

<!-- END GENERATED PROPERTY TABLE -->

This table lists exactly the properties `context.jsonld` declares, and it is generated from the declarations that define them.
A property's term is its name in the wire message.
Its value kind is how the context document types the term, as the AS2 context types its own: a `plain` value is a literal or an embedded object and needs no type, an `iri` value is read as a link (`"@type": "@id"`), a `json` value is kept verbatim (`"@type": "@json"`), a `list` keeps its order (`"@container": "@list"`), a `set` does not (`"@container": "@set"`), and an `index` is a map keyed by IRIs (`"@container": "@index"`).
A container kind names the kind of each value in it, as in `set of iri`.

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
