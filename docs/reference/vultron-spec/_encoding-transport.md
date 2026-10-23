## 5. Encoding and Transport [N]

This section specifies how a Vultron message is encoded and delivered.
Where [§4 Messages](layers.md#4-messages-n) says what to send in each situation and what a received message means, this section says what a message looks like on the wire and how it reaches its addressee.

Vultron does not define its own message syntax.
It uses ActivityStreams 2.0 (AS2), a published World Wide Web Consortium (W3C) vocabulary for describing things that actors do, and extends it with the object types of [§4.3 Object Types](layers.md#43-object-types).
Reusing an existing vocabulary means the outer envelope is already specified, already tooled, and already understood by readers who have met it elsewhere.

The consequence is that Vultron messages look generic.
There is no `ProposeEmbargo` verb; there is an `Invite` whose object is an `EmbargoEvent`.
Meaning comes from the combination of verb, object and the fields that tell occasions apart, which is what the occasion tables of [§4 Messages](layers.md#4-messages-n) record.

### 5.1 Base Vocabulary

Every Vultron message is an AS2 **Activity**: an object describing an action, with the actor who performed it and the thing it was performed on.

Four fields are required on every Activity:

| Field | Contains |
|---|---|
| `type` | The Activity type: the verb, such as `Offer` or `Announce` |
| `actor` | The Uniform Resource Identifier (URI) of the actor that performed the action |
| `object` | The thing acted on, inline or by reference ([§5.2 Serialization](layers.md#52-serialization)) |
| `id` | A URI uniquely identifying this Activity, used for deduplication ([§15.3 Replay and Idempotency](considerations.md#153-replay-and-idempotency)) |

The fields that tell occasions apart, such as `target` and `context`, are the bracketed fields of the [Wire Activity Notation](annex-c-notation.md#wire-activity-notation).
Vultron's own types are declared in the vocabulary namespace `https://certcc.github.io/Vultron/ns`.
An implementation MUST use the Vultron ActivityStreams vocabulary for message structure.

Vultron uses AS2 verbs rather than defining its own:
`Create`, `Offer`, `Accept`, `Reject`, `TentativeReject`, `Announce`, `Update`, `Add`, `Remove`, `Invite`, `Read`, `Join`, `Leave`, `Ignore` and `Undo`.

Because the verbs are generic, meaning often comes from **nesting**: an Activity whose object is itself an Activity.
Accepting an embargo is `Accept(Invite(EmbargoEvent)[context=VulnerabilityCase])`, an `Accept` whose object is the `Invite` being accepted, which in turn carries the embargo.
The nesting is what distinguishes accepting an embargo from accepting a report, `Accept(Offer(VulnerabilityReport))`.

This version does not require full ActivityPub server behavior.
Inbox and outbox Hypertext Transfer Protocol (HTTP) delivery, WebFinger discovery and HTTP Signatures are not conformance requirements here.

!!! note "Informative: ActivityPub conformance is not required by this version"
    A future version is expected to raise the floor to ActivityPub; [§1.3 Relationship to Existing Standards](introduction.md#13-relationship-to-existing-standards) states the roadmap.

### 5.2 Serialization

Vultron messages are serialized as JavaScript Object Notation for Linked Data (JSON-LD).
JSON-LD is JavaScript Object Notation (JSON) with a context that maps short names to full URIs.
A message is therefore readable as ordinary JSON while remaining unambiguous about which vocabulary each term comes from.

An outbound message MUST set `@context` to the Vultron JSON-LD context document URI, `https://certcc.github.io/Vultron/ns/context.jsonld` ([VM-10-001](../specs/protocol.md#vm-10-001)).
That context document imports the AS2 namespace and declares every Vultron type name.
An implementation therefore cites only the Vultron URI and does not need to declare the AS2 namespace separately.

**Objects travel inline or by reference.**
As AS2 allows, an Activity MAY carry an object inline or name it by URI, and a receiver MUST cope with either form ([SE-01-002](../specs/foundation.md#se-01-002)).
An actor that names by reference an object its recipient cannot be expected to hold MUST use a reference the recipient can dereference ([AKM-02-002](../specs/protocol.md#akm-02-002), [§4.2 Knowledge Model and Actor Isolation](layers.md#42-knowledge-model-and-actor-isolation)).
A production implementation MUST be able to fetch an object named by a URI it holds no record of ([AKM-05-004](../specs/protocol.md#akm-05-004)).

How a case ledger entry records the objects of the activity it records is specified at [§10.4 Ledger Replication and Case Delivery](interactions.md#104-ledger-replication-and-case-delivery).

!!! note "The reference implementation inlines every object"
    The reference implementation does not yet dereference, so it carries every object inline and refuses a bare URI where it needs the object ([AKM-03-003](../specs/project.md#akm-03-003)).
    That is a shortcut of the prototype, not a Vultron rule.

!!! note "Provisional namespace URI"
    The namespace is currently hosted on GitHub Pages.
    A permanent URI may be registered in a future version ([§14 IANA and Namespace Considerations](considerations.md#14-iana-and-namespace-considerations-i)).

### 5.3 Transport [N/I]

The transport moves a serialized message from one actor to another.
The message schema of [§5.1 Base Vocabulary](layers.md#51-base-vocabulary) and [§5.2 Serialization](layers.md#52-serialization) is transport-agnostic: the same JSON payload is deliverable over any conformant transport.

An actor is identified by a URI, and that URI is also where it receives messages.
Each actor exposes an **inbox** to receive Activities and an **outbox** from which it sends them.
An actor's URI is its identity for every purpose in the protocol: there is no separate registry, and no name or hosting location carries authority ([§2.2 Roles](introduction.md#22-roles)).
Delivery is therefore inbox to inbox.

This version recognizes one required transport profile and describes a second that is anticipated.

#### REST (HTTP) profile [N]

This Representational State Transfer (REST) profile is the transport an implementation MUST provide.

- Each actor exposes an inbox endpoint that accepts inbound Activities.
- An outbound Activity is delivered by HTTP POST to the recipient's inbox.
- Authentication and authorization requirements are at [§15 Security Considerations](considerations.md#15-security-considerations-ni).

{% include-markdown "./_oq-transport-status-codes.md" %}

#### ActivityPub federation profile [I]

Full ActivityPub conformance is not required by this version.
The roadmap is at [§1.3 Relationship to Existing Standards](introduction.md#13-relationship-to-existing-standards).
[Annex E Relationship to ActivityPub](annex-e-activitypub.md#annex-e-relationship-to-activitypub-i) describes where Vultron follows ActivityPub conventions and where it diverges.

#### Participant discovery [I]

Before two actors can exchange messages they must locate each other.
WebFinger is the anticipated mechanism, consistent with its use alongside ActivityPub in federated systems.
This version does not specify participant discovery.

!!! note "Transport is not routing"
    Which inbox a message may go to is a protocol rule, specified at [§10.2 Routing Topology](interactions.md#102-routing-topology), and it applies whichever transport carries the message.
    The transport is responsible for getting a message to an inbox.
    The protocol is responsible for which inbox it may go to.

### 5.4 Worked Exchanges [I]

The exchanges below show occasions of [§4 Messages](layers.md#4-messages-n) as they appear on the wire.
Each one is given first in Wire Activity notation and then as the JSON a sender delivers.
The identifiers and hashes are illustrative, and optional fields such as `name` and `updated` are left out where the exchange does not need them.

#### Submitting a report

A Finder submits a report to a Vendor, which acknowledges the submission with Report Acknowledgment (`RK`).
No case exists yet, so both messages go directly between the two actors.

=== "Notation"

    | Step | Sender | Send to | Wire activity | Shorthand |
    |---|---|---|---|---|
    | 1 | Finder | Vendor | `Offer(VulnerabilityReport)` | `RS` |
    | 2 | Vendor | Finder | `Read(Offer(VulnerabilityReport))` | `RK` |

=== "Wire JSON"

    ```json
    {
      "@context": "https://certcc.github.io/Vultron/ns/context.jsonld",
      "type": "Offer",
      "id": "https://vultron.example/users/finndervul/activities/offer-1",
      "actor": "https://vultron.example/users/finndervul",
      "to": ["https://vultron.example/organizations/vendorco"],
      "object": {
        "type": "VulnerabilityReport",
        "id": "https://vultron.example/reports/FDR-8675309",
        "content": "I found a vulnerability!",
        "attributedTo": "https://vultron.example/users/finndervul"
      }
    }
    ```

    ```json
    {
      "@context": "https://certcc.github.io/Vultron/ns/context.jsonld",
      "type": "Read",
      "id": "https://vultron.example/organizations/vendorco/activities/read-1",
      "actor": "https://vultron.example/organizations/vendorco",
      "to": ["https://vultron.example/users/finndervul"],
      "content": "We've read the report. We'll get back to you soon.",
      "object": {
        "type": "Offer",
        "id": "https://vultron.example/users/finndervul/activities/offer-1",
        "actor": "https://vultron.example/users/finndervul",
        "to": ["https://vultron.example/organizations/vendorco"],
        "object": {
          "type": "VulnerabilityReport",
          "id": "https://vultron.example/reports/FDR-8675309",
          "content": "I found a vulnerability!",
          "attributedTo": "https://vultron.example/users/finndervul"
        }
      }
    }
    ```

#### Proposing and accepting an embargo

A Vendor proposes embargo terms for a case with no active embargo, Embargo Proposal (`EP`).
The CASE_MANAGER asks each other participant about the proposal, naming the proposer in `attributedTo` and the deadline for an answer in `endTime`.
A Coordinator agrees, Embargo Proposal Acceptance (`EA`), by accepting the `Invite` it received.

=== "Notation"

    | Step | Sender | Send to | Wire activity | Shorthand |
    |---|---|---|---|---|
    | 1 | Vendor | the case manager | `Invite(EmbargoEvent)[context=VulnerabilityCase]` | `EP` |
    | 2 | the case manager | Coordinator | `Invite(EmbargoEvent)[context=VulnerabilityCase]` | — |
    | 3 | Coordinator | the case manager | `Accept(Invite(EmbargoEvent)[context=VulnerabilityCase])` | `EA` |

=== "Wire JSON"

    ```json
    {
      "@context": "https://certcc.github.io/Vultron/ns/context.jsonld",
      "type": "Invite",
      "id": "https://vultron.example/cases/1/embargo_proposals/1",
      "actor": "https://vultron.example/organizations/vendorco",
      "to": ["https://vultron.example/case-actors/vendorco-case-actor"],
      "context": "https://vultron.example/cases/1",
      "summary": "We propose to embargo case 1 for 90 days.",
      "object": {
        "type": "EmbargoEvent",
        "id": "https://vultron.example/cases/1/embargo_events/2026-08-30T00:00:00+00:00",
        "context": "https://vultron.example/cases/1",
        "startTime": "2026-06-01T19:12:00+00:00",
        "endTime": "2026-08-30T00:00:00+00:00"
      }
    }
    ```

    ```json
    {
      "@context": "https://certcc.github.io/Vultron/ns/context.jsonld",
      "type": "Invite",
      "id": "https://vultron.example/cases/1/embargo_proposals/1/invites/coordinator",
      "actor": "https://vultron.example/case-actors/vendorco-case-actor",
      "attributedTo": "https://vultron.example/organizations/vendorco",
      "to": ["https://vultron.example/organizations/coordinator"],
      "context": "https://vultron.example/cases/1",
      "published": "2026-06-01T19:12:00+00:00",
      "endTime": "2026-06-08T19:12:00+00:00",
      "summary": "The vendor proposes to embargo case 1 for 90 days.",
      "object": {
        "type": "EmbargoEvent",
        "id": "https://vultron.example/cases/1/embargo_events/2026-08-30T00:00:00+00:00",
        "context": "https://vultron.example/cases/1",
        "startTime": "2026-06-01T19:12:00+00:00",
        "endTime": "2026-08-30T00:00:00+00:00"
      }
    }
    ```

    ```json
    {
      "@context": "https://certcc.github.io/Vultron/ns/context.jsonld",
      "type": "Accept",
      "id": "https://vultron.example/organizations/coordinator/activities/accept-1",
      "actor": "https://vultron.example/organizations/coordinator",
      "to": ["https://vultron.example/case-actors/vendorco-case-actor"],
      "context": "https://vultron.example/cases/1",
      "object": {
        "type": "Invite",
        "id": "https://vultron.example/cases/1/embargo_proposals/1/invites/coordinator",
        "actor": "https://vultron.example/case-actors/vendorco-case-actor",
        "attributedTo": "https://vultron.example/organizations/vendorco",
        "to": ["https://vultron.example/organizations/coordinator"],
        "context": "https://vultron.example/cases/1",
        "published": "2026-06-01T19:12:00+00:00",
        "endTime": "2026-06-08T19:12:00+00:00",
        "object": {
          "type": "EmbargoEvent",
          "id": "https://vultron.example/cases/1/embargo_events/2026-08-30T00:00:00+00:00",
          "context": "https://vultron.example/cases/1",
          "startTime": "2026-06-01T19:12:00+00:00",
          "endTime": "2026-08-30T00:00:00+00:00"
        }
      }
    }
    ```

#### Reporting a fix is ready

A Vendor reports that it has a fix ready, Fix Readiness (`CF`), as a claim in a new `ParticipantStatus` on its own participant record.
The `vfState` value `VF` is what distinguishes this occasion from the other claims that share the activity.

=== "Notation"

    | Step | Sender | Send to | Wire activity | Shorthand |
    |---|---|---|---|---|
    | 1 | Vendor | the case manager | `Add(ParticipantStatus)[target=CaseParticipant]`, with `vfState` `VF` | `CF` |

=== "Wire JSON"

    ```json
    {
      "@context": "https://certcc.github.io/Vultron/ns/context.jsonld",
      "type": "Add",
      "id": "https://vultron.example/organizations/vendorco/activities/add-status-3",
      "actor": "https://vultron.example/organizations/vendorco",
      "to": ["https://vultron.example/case-actors/vendorco-case-actor"],
      "target": "https://vultron.example/cases/1/participants/vendorco",
      "object": {
        "type": "ParticipantStatus",
        "id": "https://vultron.example/cases/1/participants/vendorco/status/3",
        "context": "https://vultron.example/cases/1",
        "attributedTo": "https://vultron.example/organizations/vendorco",
        "rmState": "ACCEPTED",
        "vfState": "VF",
        "caseEngagement": true,
        "cvdRole": ["VENDOR"]
      }
    }
    ```

#### Replicating a ledger entry

The CASE_MANAGER has committed a case event to the case ledger and sends the entry to every participant.
Each participant checks that the entry's `prevLogHash` matches the `entryHash` of the last entry it holds ([§4.12 Ledger Replication Messages](layers.md#412-ledger-replication-messages)).
The entry shown is the first in its case's ledger, so its `prevLogHash` is the all-zero genesis hash.

=== "Notation"

    | Step | Sender | Send to | Wire activity | Shorthand |
    |---|---|---|---|---|
    | 1 | the case manager | each participant | `Announce(CaseLedgerEntry)` | — |

=== "Wire JSON"

    ```json
    {
      "@context": "https://certcc.github.io/Vultron/ns/context.jsonld",
      "type": "Announce",
      "id": "https://vultron.example/case-actors/vendorco-case-actor/activities/announce-0",
      "actor": "https://vultron.example/case-actors/vendorco-case-actor",
      "to": ["https://vultron.example/organizations/coordinator"],
      "object": {
        "type": "CaseLedgerEntry",
        "id": "https://vultron.example/cases/1/log/0",
        "caseId": "https://vultron.example/cases/1",
        "logIndex": 0,
        "logObjectId": "https://vultron.example/activities/00000000-0000-0000-0000-000000000001",
        "semanticType": "create_case",
        "payloadSnapshot": {},
        "prevLogHash": "0000000000000000000000000000000000000000000000000000000000000000",
        "entryHash": "0dabc4e69c51c1fa7e30595ff3357fdcb1fbe4581aed3534bec1e92c30e84549",
        "receivedAt": "2024-01-01T12:00:00Z"
      }
    }
    ```

---
