## 10. Case Coordination [N]

Every case has a Case Manager.
The Case Manager is a protocol **role**, `CASE_MANAGER`, and a participant holds it from case creation onward.
The participant that holds it may be the actor that created the case, or an actor that the case's creator delegated case maintenance to.
This section names the authority *the CASE_MANAGER*: whichever participant holds the role for the case ([§2.2 Roles](introduction.md#22-roles)).

```python exec="true" idprefix=""
from vultron.metadata.specs.docs_render import requirement_callout; print(requirement_callout("CM-24-006"))
```

This section specifies what the CASE_MANAGER does for its case.
It is the only writer of the case's shared state ([§10.1 Single-Writer Authority](interactions.md#101-single-writer-authority)), and every case-scoped message passes through it ([§10.2 Routing Topology](interactions.md#102-routing-topology)).
The case-creation message is the root of every participant's trust in it ([§10.3 Case Bootstrap and the Trust Root](interactions.md#103-case-bootstrap-and-the-trust-root)).
It replicates the case ledger to every active participant and delivers the case to each new one ([§10.4 Ledger Replication and Case Delivery](interactions.md#104-ledger-replication-and-case-delivery)).
It also decides which participants' claims become the case's canonical status ([§10.5 Claims and Canonical Status](interactions.md#105-claims-and-canonical-status)).

The cascades that the CASE_MANAGER runs when one state machine's transition obliges another are specified at [§11 Model Interactions and Cascade Rules](interactions.md#11-model-interactions-and-cascade-rules-n).
How a participant joins a case, changes role in it and leaves it is at [§12 Participant Lifecycle Within a Case](interactions.md#12-participant-lifecycle-within-a-case-n).

!!! note "Informative: the dedicated Case Actor is an implementation choice"
    The reference implementation provisions a dedicated service actor for each case, the *Case Actor*, to hold the `CASE_MANAGER` role.
    That choice goes further than the protocol requires.
    The protocol requires a participant that holds the role, and any participant can hold it, including the Case Owner itself.
    Nothing in this section depends on whether the holder is a dedicated actor.

### 10.1 Single-Writer Authority

The participant holding the `CASE_MANAGER` role is the **only** entity authorized to write the case's shared state.
That shared state is the Public aware, eXploit public, Attacks observed (PXA) axis, the embargo state, the embargo record, and the case ledger.
No other participant writes shared case state directly.
Every such change goes through the CASE_MANAGER.

```python exec="true" idprefix=""
from vultron.metadata.specs.docs_render import requirement_callout; print(requirement_callout("VP-17-001"))
```

The participant-specific axes are report management and Vendor aware, Fix ready, fix Deployed (VFD).
Each participant's own `CaseParticipant` record owns these axes, and they are explicitly **not** subject to this restriction.
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

- A participant addresses a case-scoped Activity to the CASE_MANAGER alone, never to the other participants.
- The CASE_MANAGER records the message in the case ledger, and the ledger entry is what it sends on to the other participants.
- `Announce` of a `CaseLedgerEntry` is the **only** way a participant learns of an admitted change to shared case state.

```python exec="true" idprefix=""
from vultron.metadata.specs.docs_render import requirement_callout; print(requirement_callout("PCR-08-001", "PCR-08-005", "PCR-08-003", "PCR-08-002"))
```

There are exactly **two** exceptions, and both are confined to case bootstrap.
Both occur before the reporter has been introduced to the CASE_MANAGER, so the reporter has none to route through ([§10.3 Case Bootstrap and the Trust Root](interactions.md#103-case-bootstrap-and-the-trust-root)):

1. **Pre-case report submission** — the reporter sends the report directly to the vendor.
   No case exists, and therefore no participant holds the `CASE_MANAGER` role.
2. **Case creation handshake** — the receiving party sends the case-creation message back to the reporter as itself.
   That message introduces the actor that holds the role ([§10.3 Case Bootstrap and the Trust Root](interactions.md#103-case-bootstrap-and-the-trust-root)).
   When that actor is not the receiving party, its first message to the reporter is a later sync.
   The reporter holds that sync if it arrives before the introduction.

```python exec="true" idprefix=""
from vultron.metadata.specs.docs_render import requirement_callout; print(requirement_callout("CBT-01-010"))
```

The report acknowledgment, `RK`, falls outside this rule rather than adding a bootstrap exception.
It answers the reporter's original report offer, outside the case, so it goes to the reporter directly, never to the CASE_MANAGER.
The routing requirements above state this exception.

!!! warning "This is a routing rule, not a prohibition on talking"
    The rule above scopes **Vultron protocol messages about a case**.
    It does not say that participants may not communicate with each other, and the protocol has no way to enforce such a thing.
    Participants routinely talk directly — by mail, by phone, in a shared channel — and that is outside the protocol's scope.

    What the rule means is narrower.
    A case-scoped Vultron Activity delivered directly from one participant to another is not part of the protocol.
    A receiving implementation has no obligation to apply it.
    Case state changes through the ledger or not at all.

!!! note "Informative: why route through one writer"
    Routing through a single writer avoids the coordination cost of agreeing an order among peers, while still leaving each participant its own replica and its own view.
    The cost is that the CASE_MANAGER is a single point of coordination authority for the case, and its availability bounds how fast that case can progress.

    This is scoped per case.
    The role is held for one case at a time, different cases may be managed by different actors, and the role is transferable ([§12.3 Case Ownership Transfer](interactions.md#123-case-ownership-transfer-n)).

    The protocol deliberately leaves more decentralized realizations open.
    One example is a ledger shared among peers.
    It would remove the single point of authority, but it would need agreement on ordering.
    This version does not specify one, and no implementation of one exists.

### 10.3 Case Bootstrap and the Trust Root

A case's trust is established at its bootstrap, the step from the pre-case exchange to a case with a CASE_MANAGER.

**The case-creation message is the trust root.**
When a case is created for a report, the receiving party sends the reporter a case-creation message as itself: the actor the reporter chose.
That message introduces the actor holding the `CASE_MANAGER` role, which may be the receiving party or another actor it delegated case maintenance to.
The reporter trusts the introduction because it came from the actor the reporter addressed, and never because a case snapshot names its own sender.
Every participant's trust in the ledger derives from it: a participant accepts entries from the CASE_MANAGER because it accepts the message that established which actor holds the role.

```python exec="true" idprefix=""
from vultron.metadata.specs.docs_render import requirement_callout; print(requirement_callout("CBT-01-001", "CBT-01-005", "CBT-01-011"))
```

**A late joiner inherits that trust transitively.**
An actor invited after the case is under way never sees the original creation message.
It trusts the invitation that named the CASE_MANAGER.
It then receives the case snapshot and the prior ledger entries from the CASE_MANAGER ([§10.4 Ledger Replication and Case Delivery](interactions.md#104-ledger-replication-and-case-delivery)).
It trusts them because it trusts that invitation.

```python exec="true" idprefix=""
from vultron.metadata.specs.docs_render import requirement_callout; print(requirement_callout("CBT-04-001", "CBT-04-002"))
```

The hash-chaining of the ledger lets the joiner verify it received an unbroken history.
This is a check against tampering and omission, not a second source of trust.

The threat model, identity verification, and the limits of this trust chain are covered at [§15.1 Trust Model](considerations.md#151-trust-model).

### 10.4 Ledger Replication and Case Delivery

The CASE_MANAGER keeps every active participant's replica in step with the case through two operations.

| Operation | What the CASE_MANAGER does |
|---|---|
| Ledger replication | Sends each committed ledger entry to every active participant, as `Announce(CaseLedgerEntry)`. This is the only way a participant learns of an admitted change to shared case state ([§10.2 Routing Topology](interactions.md#102-routing-topology)) |
| Case delivery | Sends a participant the full case once it is an active participant ([§9.7 Gating Full Case Delivery](tracking-models.md#97-gating-full-case-delivery)), then the ledger entries committed before it joined, oldest first ([§11.1 Admitting a Participant](interactions.md#111-admitting-a-participant)) |

Their wire activities are given at [§4.12 Ledger Replication Messages](layers.md#412-ledger-replication-messages) and [§4.7 Case and Participant Messages](layers.md#47-case-and-participant-messages).
Both operations reach only active participants.
Being in the case's participant list is not enough.

```python exec="true" idprefix=""
from vultron.metadata.specs.docs_render import requirement_callout; print(requirement_callout("CM-10-004", "CM-17-005"))
```

**A ledger entry records the asserted activity as it was sent.**
Its payload snapshot is the received body of an activity the CASE_MANAGER received, or the body it delivered for one it sent itself.
Each nested object stays as the asserting activity carried it.
It stays inline where its sender inlined it, and by reference where its sender named an object every replica already holds.

```python exec="true" idprefix=""
from vultron.metadata.specs.docs_render import requirement_callout; print(requirement_callout("CLP-07-011", "CLP-07-006"))
```

The CASE_MANAGER never fills a reference in.
The entry hash covers the snapshot and nothing outside it.
A filled-in snapshot would thus record the CASE_MANAGER's reconstruction, not what was sent.
How a message carries an object inline or by reference is specified at [§5.2 Serialization](layers.md#52-serialization).

### 10.5 Claims and Canonical Status

Two status records carry the case's state, and they are the most easily confused types in the protocol ([§4.3 Object Types](layers.md#43-object-types)).
The difference between them is one of authority rather than content.

- A `ParticipantStatus` is a **claim**.
  It carries what one participant reports about its own state, or observes about the world.
  Any participant may write one, and writing one does not change what the case asserts.
- A `CaseStatus` is **canonical**.
  It carries what the case asserts: its embargo state and what is publicly known.
  Only the CASE_MANAGER writes it ([§10.1 Single-Writer Authority](interactions.md#101-single-writer-authority)).

A claim becomes canonical only when the CASE_MANAGER adopts it.
Adoption is an authorization decision with a named default, not an automatic consequence of receipt ([§11.3 Status Adoption: The Two-Seam Model](interactions.md#113-status-adoption-the-two-seam-model)).
The two types are not interchangeable.
A participant that emits `CaseStatus` is asserting authority it does not hold.
A CASE_MANAGER that treats an inbound `ParticipantStatus` as canonical has skipped the decision.

**The status messages depend on who is sending.**
The six case state shorthands ([§4.9 Case State Messages](layers.md#49-case-state-messages)) do not have one wire form; they have two, and the sender's authority decides which applies:

- A **participant** reporting its own VFD progress, or an observation about the world, sends `Add` of a **`ParticipantStatus`**.
  This is a claim.
- The **CASE_MANAGER**, having adopted a claim, sends `Add` of a **`CaseStatus`** targeting the case.
  This is the canonical write.

A participant never sends `Add` of a `CaseStatus`, and a receiver refuses one from any sender other than the CASE_MANAGER.

```python exec="true" idprefix=""
from vultron.metadata.specs.docs_render import requirement_callout; print(requirement_callout("RSH-04-001", "RSH-04-005"))
```

An implementation that maps all six shorthands to `CaseStatus` regardless of sender will have participants asserting authority they do not hold.
The rest of the shorthand mapping is at [§4.13 Formal Message Set](layers.md#413-formal-message-set).

---
