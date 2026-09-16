## 5. Syntactic Layer — Wire Format [N]

### 5.1 Base Vocabulary

- Vultron messages are ActivityStreams 2.0 Activities
- Required fields: `type`, `actor`, `object`, `id`
- Extended types defined by the Vultron vocabulary namespace
  (`https://certcc.github.io/Vultron/ns`)
- Implementations MUST use the Vultron AS2 vocabulary for message structure;
  full ActivityPub server semantics (inbox/outbox HTTP delivery, WebFinger
  discovery, HTTP Signatures) are not currently required by this specification

!!! note "Informative: ActivityPub conformance is not required by this version"
    This version requires the ActivityStreams 2.0 vocabulary but not full
    ActivityPub server behavior. A future version is expected to raise that floor;
    [§1.3](index.md#13-relationship-to-existing-standards) states the roadmap.

### 5.2 Object Types

- `VulnerabilityCase` — the shared coordination object
- `VulnerabilityReport` — the initial report artifact
- `CaseParticipant` — actor-in-role within a case
- `CaseParticipantRole` — a `CVDRole` being offered to an actor in a case
  context; introduced to make role delegation structurally distinct from case
  ownership transfer (both previously serialized as `Offer(VulnerabilityCase)`)
- `EmbargoEvent` — embargo proposal/acceptance/revision/termination records.
  This is an AS2 `Event` subtype; embargo activities therefore appear on the
  wire as `Invite(Event)`, not as a distinct embargo verb
- `CaseLedgerEntry` — an entry in the authoritative canonical case ledger; the
  unit of state replication from the CASE_MANAGER to participants
- `CaseProposal` — a proposed case, prior to case creation
- `CaseStatus` / `ParticipantStatus` — status records. **These are not
  interchangeable, and the distinction is load-bearing:**
  - `ParticipantStatus` is a *claim* — one participant's assertion about its
    own (or another participant's) state. Any participant may write one.
  - `CaseStatus` is *canonical* — the CASE_MANAGER's authoritative record of
    shared case state. Only the CASE_MANAGER may write it ([§5.4](index.md#54-addressing-and-channels)).

  The transition from claim to canonical is an explicit authorization step,
  not an implementation detail; see [§10.3](index.md#103-status-adoption-the-two-seam-model).

### 5.3 Activity Types and Canonical Message Forms

- Base AS2 verbs used by Vultron: `Create`, `Offer`, `Accept`, `Reject`,
  `Announce`, `Update`, `Add`, `Remove`, `Invite`, `Read`, `Join`, `Ignore`,
  `TentativeReject`
- Vultron-specific nested-object patterns, e.g.
  `Accept(Invite(Event)[context=VulnerabilityCase])` for embargo acceptance
- Two distinct activities govern bringing an actor into a case, and they are
  **not** the same message:
  - `Invite[target=VulnerabilityCase]` — the CASE_MANAGER invites an actor to
    join, on the Case Owner's behalf. Answered with `Accept(Invite)` or
    `Reject(Invite)`.
  - `Offer(CaseParticipant)` — the *suggest-actor* path: a participant
    proposes that some actor be brought into the case. Answered by the Case
    Owner, which may then cause an `Invite` to be emitted.

  Both paths converge on `Accept(Invite)`, but they originate differently and
  carry roles differently. Conflating them erases the suggest-actor round-trip.

- Each protocol operation corresponds to exactly one AS2 pattern. This
  specification defines that correspondence; an implementation derives its own
  dispatch table from it, not the other way around. The mapping is given in
  [§4.7](index.md#47-shorthand-wire-form-mapping), after the shorthands it maps
  from have been introduced.

### 5.4 Addressing and Channels

- Actor URIs as process identifiers (aligned with ActivityPub actor model)
- Inbox/outbox as the delivery model: each actor exposes an inbox (receive)
  and outbox (send/broadcast)

#### 5.4.1 Single-Writer Authority

The CASE_MANAGER is the **only** entity authorized to mutate shared case state —
the CS `PXA` axis, the EM state, the embargo record, and the case ledger. No
participant and no use-case handler may write shared case state directly; all
such mutations MUST route through the CASE_MANAGER.

The participant-specific axes (`RM`, `VFD`) are owned by each participant's own
`CaseParticipant` record and are explicitly **not** subject to this restriction —
a participant is the authority on its own RM and VFD state.

This single-writer rule is the axiom from which the routing topology below
follows. It exists to prevent concurrent-write races and to ensure every shared
state change passes through the CASE_MANAGER's consistency checks.

#### 5.4.2 Routing Topology

Once a case exists, all case-scoped participant messages MUST follow this path:

```text
Participant → CASE_MANAGER → CaseLedgerEntry → Announce(CaseLedgerEntry) → all Participants
```

- A participant MUST address case-scoped activities to the CASE_MANAGER only.
- A participant **MUST NOT** deliver a case-scoped message directly to another
  participant's inbox. Delivery MUST be mediated by the CASE_MANAGER and recorded
  in the case ledger before fan-out.
- `Announce(CaseLedgerEntry)` is the **only** mechanism by which participants
  learn of accepted case-state changes.

There are exactly **two** exceptions, both confined to case bootstrap, both
occurring before the CASE_MANAGER is available as an intermediary:

1. **Pre-case report submission** — the Reporter sends `Offer(VulnerabilityReport)`
   directly to the Vendor. No case, and therefore no case actor service, exists yet.
2. **Case creation handshake** — the receiving party sends
   `Create(VulnerabilityCase)` to the Reporter to introduce the CASE_MANAGER. This
   is the trust-bootstrap exchange ([§4.5](index.md#45-trust-and-bootstrap-semantics)).

After case creation, no direct participant-to-participant messaging is
permitted.

!!! note "Informative: why centralize"
    Routing through a single writer avoids the complexity of a distributed
    ledger while preserving actor-local state: each participant still maintains
    its own replica and its own view. The cost is that the CASE_MANAGER is a
    single point of coordination authority, and its availability bounds case
    progress. This is a deliberate trade-off, not an incidental property of the
    current implementation — but the *requirements* above are
    normative regardless of how one weighs the trade-off.

### 5.5 Serialization

- JSON-LD as the normative serialization
- Outbound Vultron messages MUST set `@context` to the Vultron JSON-LD context
  document URI: `https://certcc.github.io/Vultron/ns/context.jsonld`. This
  context document imports the ActivityStreams 2.0 namespace and declares all
  Vultron-specific type names, so implementations need cite only the Vultron
  URI.

    ```json
    {
      "@context": "https://certcc.github.io/Vultron/ns/context.jsonld",
      "type": "VulnerabilityCase",
      ...
    }
    ```

!!! note "Provisional namespace URI"
    The namespace is currently hosted on GitHub Pages
    (`certcc.github.io/Vultron`). A permanent namespace URI may be registered
    in a future version of this specification. See ADR-0069.

### 5.6 Transport Layer [N/I]

The transport layer defines how vultron-wire messages move between participants.
The message schema ([§5.1](index.md#51-base-vocabulary)–[§5.5](index.md#55-serialization)) is transport-agnostic: the same JSON payload is
deliverable over any conformant transport.

This specification recognizes two transport profiles.

#### REST (HTTP) profile [N]

- Each actor exposes an inbox endpoint for receiving inbound Activities.
- Outbound Activities are delivered by HTTP POST to the recipient's inbox.
- Authentication and authorization requirements are described in [§14](index.md#14-security-considerations-ni).

#### ActivityPub federation profile [I]

Full ActivityPub conformance — inbox and outbox HTTP delivery, HTTP Signatures,
WebFinger discovery — is not required by this version. The roadmap is stated at
[§1.3](index.md#13-relationship-to-existing-standards); [Annex E](index.md#annex-e-relationship-to-activitypub-i) describes where
Vultron follows ActivityPub conventions and where it diverges.

#### Participant discovery [I]

Before two actors can exchange messages, they must locate each other.
WebFinger is the anticipated discovery mechanism, consistent with its use
alongside ActivityPub in federated systems such as Mastodon.
A participant discovery specification is not yet included in this document.

!!! note "Transport vs. routing topology"
    The routing topology rule in [§5.4.2](index.md#542-routing-topology) — all case-scoped messages MUST route
    through the CASE_MANAGER — is a vultron-core protocol rule. It applies
    regardless of which transport carries the messages. The transport layer is
    responsible for delivery. The protocol layer is responsible for routing
    authority.

---
