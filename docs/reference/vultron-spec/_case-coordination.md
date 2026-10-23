## 10. Case Coordination [N]

Every case has a Case Manager.
The Case Manager is a protocol **role**, `CASE_MANAGER`, and a participant holds it from case creation onward ([CM-24-006](../specs/protocol.md#cm-24-006)).
The participant that holds it may be the actor that created the case, or an actor that the case's creator delegated case maintenance to.
Authority follows the role and never the actor's name, URI or hosting location ([§2.2 Roles](introduction.md#22-roles)), so this section names the authority *the CASE_MANAGER*: whichever participant holds the role for the case.

This section specifies what the CASE_MANAGER does for its case.
It is the only writer of the case's shared state ([§10.1 Single-Writer Authority](interactions.md#101-single-writer-authority)), and every case-scoped message passes through it ([§10.2 Routing Topology](interactions.md#102-routing-topology)).
The case-creation message is the root of every participant's trust in it ([§10.3 Case Bootstrap and the Trust Root](interactions.md#103-case-bootstrap-and-the-trust-root)).
It replicates the case ledger to every participant and delivers the case to each new one ([§10.4 Ledger Replication and Case Delivery](interactions.md#104-ledger-replication-and-case-delivery)).
It also decides which participants' claims become the case's canonical status ([§10.5 Claims and Canonical Status](interactions.md#105-claims-and-canonical-status)).

The cascades that the CASE_MANAGER runs when one state machine's transition obliges another are specified at [§11 Model Interactions and Cascade Rules](interactions.md#11-model-interactions-and-cascade-rules-n).
How a participant joins a case, changes role in it and leaves it is at [§12 Participant Lifecycle Within a Case](interactions.md#12-participant-lifecycle-within-a-case-n).

!!! note "Informative: the dedicated Case Actor is an implementation choice"
    The reference implementation provisions a dedicated service actor for each case, the *Case Actor*, to hold the `CASE_MANAGER` role.
    That choice goes further than the protocol requires.
    The protocol requires a participant that holds the role, and any participant can hold it, including the Case Owner itself.
    Nothing in this section depends on whether the holder is a dedicated actor.

### 10.1 Single-Writer Authority

The participant holding the `CASE_MANAGER` role is the **only** entity authorized to write the case's shared state: the PXA axis, the embargo state, the embargo record, and the case ledger.
No participant and no handler may write shared case state directly; every such change MUST be made by the CASE_MANAGER ([VP-17-001](../specs/protocol.md#vp-17-001)).

The participant-specific axes — report management and VFD — are owned by each participant's own `CaseParticipant` record and are explicitly **not** subject to this restriction.
A participant is the authority on its own report management and VFD state.

This rule exists to make concurrent claims resolvable.
Two participants may report contradictory observations about the world at the same moment.
With one writer, the case has one answer, and the decision about which claim becomes that answer is explicit ([§10.5 Claims and Canonical Status](interactions.md#105-claims-and-canonical-status)) rather than a race.
The routing rule below follows from it.

### 10.2 Routing Topology

Once a case exists, every case-scoped message follows this path:

```text
Participant → CASE_MANAGER → CaseLedgerEntry → Announce(CaseLedgerEntry) → all Participants
```

- A participant MUST address case-scoped Activities to the CASE_MANAGER ([PCR-08-001](../specs/protocol.md#pcr-08-001), [PCR-08-005](../specs/protocol.md#pcr-08-005)).
- The CASE_MANAGER MUST record a case-scoped message in the case ledger before sending it on to the other participants ([PCR-08-003](../specs/protocol.md#pcr-08-003)).
- `Announce` of a `CaseLedgerEntry` is the **only** mechanism by which a participant learns of an admitted change to shared case state ([PCR-08-002](../specs/protocol.md#pcr-08-002)).

There are exactly **two** exceptions, both confined to case bootstrap, both occurring before a CASE_MANAGER exists to route through ([§4.5 Trust and Bootstrap Semantics](layers.md#45-trust-and-bootstrap-semantics)):

1. **Pre-case report submission** — the reporter sends the report directly to the vendor.
   No case exists, and therefore no participant holds the `CASE_MANAGER` role.
2. **Case creation handshake** — the receiving party sends the case-creation message back to the reporter as itself, introducing the actor that holds the role ([§10.3 Case Bootstrap and the Trust Root](interactions.md#103-case-bootstrap-and-the-trust-root)).
   When that actor is not the receiving party, its first message to the reporter is a later sync, which the reporter holds if it arrives before the introduction ([CBT-01-010](../specs/protocol.md#cbt-01-010)).

The report acknowledgment `RK` falls outside this rule rather than adding a bootstrap exception.
It answers the reporter's original report offer, outside the case, so it goes to the reporter directly, never to the CASE_MANAGER ([PCR-08-001](../specs/protocol.md#pcr-08-001)).

!!! warning "This is a routing rule, not a prohibition on talking"
    The rule above scopes **Vultron protocol messages about a case**.
    It does not say that participants may not communicate with each other, and the protocol has no way to enforce such a thing.
    Participants routinely talk directly — by mail, by phone, in a shared channel — and that is outside the protocol's scope.

    What the rule means is narrower: a case-scoped Vultron Activity delivered directly from one participant to another is not part of the protocol, and a receiving implementation has no obligation to apply it.
    Case state changes through the ledger or not at all.

!!! note "Informative: why route through one writer"
    Routing through a single writer avoids the coordination cost of agreeing an order among peers, while still leaving each participant its own replica and its own view.
    The cost is that the CASE_MANAGER is a single point of coordination authority for the case, and its availability bounds how fast that case can progress.

    This is scoped per case.
    The role is held for one case at a time, different cases may be managed by different actors, and the role is transferable ([§12.3 Case Ownership Transfer](interactions.md#123-case-ownership-transfer-n)).

    The protocol deliberately leaves more decentralized realizations open — a ledger shared among peers, for instance, which would remove the single point of authority at the cost of needing agreement on ordering.
    This version does not specify one, and no implementation of one exists.

### 10.3 Case Bootstrap and the Trust Root

A case's trust is established at its bootstrap, the step from the pre-case exchange to a case with a CASE_MANAGER ([§4.5 Trust and Bootstrap Semantics](layers.md#45-trust-and-bootstrap-semantics)).

**The case-creation message is the trust root.**
When a case is created for a report, the receiving party sends the reporter a case-creation message as itself: the actor the reporter chose ([CBT-01-001](../specs/protocol.md#cbt-01-001)).
That message introduces the actor holding the `CASE_MANAGER` role, which may be the receiving party or another actor it delegated case maintenance to.
The reporter trusts the introduction because it came from the actor the reporter addressed, and never because a case snapshot names its own sender ([CBT-01-005](../specs/protocol.md#cbt-01-005), [CBT-01-011](../specs/protocol.md#cbt-01-011)).
Every participant's trust in the ledger derives from it: a participant accepts entries from the CASE_MANAGER because it accepts the message that established which actor holds the role.

**A late joiner inherits that trust transitively.**
An actor invited after the case is under way never sees the original creation message.
It trusts the invitation that named the CASE_MANAGER ([CBT-04-001](../specs/protocol.md#cbt-04-001), [CBT-04-002](../specs/protocol.md#cbt-04-002)).
It then receives the case snapshot and the prior ledger entries from the CASE_MANAGER ([§10.4 Ledger Replication and Case Delivery](interactions.md#104-ledger-replication-and-case-delivery)), and it trusts them because it trusts that invitation.
The hash-chaining of the ledger lets the joiner verify it received an unbroken history — a check against tampering and omission, not a second source of trust.

The threat model, identity verification, and the limits of this trust chain are covered at [§15.1 Trust Model](considerations.md#151-trust-model).

### 10.4 Ledger Replication and Case Delivery

The CASE_MANAGER keeps every participant's replica in step with the case through two operations.

| Operation | What the CASE_MANAGER does |
|---|---|
| Ledger replication | Sends each committed ledger entry to every participant, as `Announce(CaseLedgerEntry)`. This is the only way a participant learns of an admitted change to shared case state ([PCR-08-003](../specs/protocol.md#pcr-08-003)) |
| Case delivery | Sends a participant the full case, once that participant is admitted and its embargo consent is resolved ([§9.7 Gating Full Case Delivery](tracking-models.md#97-gating-full-case-delivery)), then the ledger entries committed before it joined, oldest first ([CM-17-004](../specs/protocol.md#cm-17-004), [§11.1 Admitting a Participant](interactions.md#111-admitting-a-participant)) |

Their wire forms are given at [§5.3 Activity Types and Canonical Message Forms](layers.md#53-activity-types-and-canonical-message-forms).

**A ledger entry records the asserted activity as it was sent.**
Its payload snapshot is the received body of an activity the CASE_MANAGER received, or the body it delivered for one it sent itself ([CLP-07-011](../specs/protocol.md#clp-07-011)).
Each nested object stays as the asserting activity carried it: inline where its sender inlined it, by reference where its sender named an object every replica already holds ([CLP-07-006](../specs/protocol.md#clp-07-006)).
The CASE_MANAGER never fills a reference in, because the entry hash covers the snapshot and nothing outside it, so a filled-in snapshot would record the CASE_MANAGER's reconstruction rather than what was sent.
How a message carries an object inline or by reference is specified at [§5.5 Serialization](layers.md#55-serialization).

### 10.5 Claims and Canonical Status

Two status records carry the case's state, and they are the most easily confused types in the protocol ([§5.2 Object Types](layers.md#52-object-types)).
The difference between them is one of authority rather than content.

- A `ParticipantStatus` is a **claim**.
  It carries what one participant reports about its own state, or observes about the world.
  Any participant may write one, and writing one does not change what the case asserts.
- A `CaseStatus` is **canonical**.
  It carries what the case asserts: its embargo state and what is publicly known.
  Only the CASE_MANAGER writes it ([§10.1 Single-Writer Authority](interactions.md#101-single-writer-authority)).

A claim becomes canonical only when the CASE_MANAGER adopts it, and adoption is an authorization decision with a named default rather than an automatic consequence of receipt ([§11.3 Status Adoption: The Two-Seam Model](interactions.md#113-status-adoption-the-two-seam-model)).
An implementation MUST NOT substitute one type for the other: a participant that emits `CaseStatus` is asserting authority it does not hold, and a CASE_MANAGER that treats an inbound `ParticipantStatus` as canonical has skipped the decision.

**The status messages depend on who is sending.**
The six case state shorthands ([§4.3 Case State Messages](layers.md#43-case-state-messages)) do not have one wire form; they have two, and the sender's authority decides which applies:

- A **participant** reporting its own VFD progress, or an observation about the world, sends `Add` of a **`ParticipantStatus`**.
  This is a claim.
- The **CASE_MANAGER**, having adopted a claim, sends `Add` of a **`CaseStatus`** targeting the case.
  This is the canonical write.

A participant MUST NOT send `Add` of a `CaseStatus`.
An implementation that maps all six shorthands to `CaseStatus` regardless of sender will have participants asserting authority they do not hold.
The rest of the shorthand mapping is at [§5.7 Shorthand to Wire Form Mapping](layers.md#57-shorthand-to-wire-form-mapping).

---
