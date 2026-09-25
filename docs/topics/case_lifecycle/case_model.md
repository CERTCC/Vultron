---
stakeholder_type: [platform-developer, project-contributor]
level: 300
introduces: [VulnerabilityCase, CaseParticipant, Dimension Object, CVDRole]
---

# The Case Model

This page explains the objects that make up a Vultron coordination case, what each one is for, and how they relate to each other.
It describes their structure, not their fields: the field-by-field listing and a class diagram are in [Case Model Fields](../../reference/case_model_fields.md).

## The case as distributed shared state

A Vultron **case** is a distributed coordination object.
Multiple independent organizations — a Reporter, a Vendor, a Coordinator — each maintain their own local copy of the case's state.
They keep those copies in step by exchanging ActivityStreams 2.0 messages.

One participant, the [CASE_MANAGER](case_manager_and_ledger.md), keeps the authoritative history of the case: an append-only, hash-chained ledger.
Every other participant holds a replica that converges on that ledger as the CASE_MANAGER sends it each new entry in an `Announce(CaseLedgerEntry)` message.
[The CASE_MANAGER and the Case Ledger](case_manager_and_ledger.md) explains how.

## `VulnerabilityCase`

`VulnerabilityCase` is the object that represents a coordination case.
It gathers everything the case is about: its participants, the reports it covers, its status history, its embargo, and the hash that anchors its ledger.

`VulnerabilityCase` does not carry Report Management (RM) state directly — that belongs to each participant, through their `ParticipantStatus` history.
Only Embargo Management (EM) state and the case-wide Publication/eXploit/Active-attacks (PXA) state are recorded at the case level, through the `CaseStatus` history.

## `CaseActor`

ActivityStreams 2.0 defines five actor types: Person, Organization, Group, Application, and **Service**.
A `CaseActor` is a **Service** actor — it represents software infrastructure, not a human or organizational CVD stakeholder.

In the prototype, each case has one `CaseActor`, and it is the participant that holds the `CASE_MANAGER` role.
It is also a `CaseParticipant` (as a `CaseActorParticipant`, per ADR-0051): it holds both `CVDRole.COORDINATOR` and `CVDRole.CASE_MANAGER` and moves through the RM states like every other participant.
Embargo proposals, status updates, notes, and participant invitations all go to it, so that the ledger captures a causally ordered record of the whole coordination.

The `CaseActor` name and its `.../actors/case-actor` URL are provisioning conveniences and carry no protocol meaning.
Authority follows the role, so no protocol logic may read that name, that URL shape, or where an actor is hosted as evidence of who the authority is ([ADR-0088](../../adr/0088-consolidate-case-authority-determination.md)).
An ordinary participant that holds `CVDRole.CASE_MANAGER` is the authority just as fully as a spawned Service actor is.

Do not confuse the `CASE_MANAGER` role (the role that authorizes ledger writes) with the `CASE_OWNER` role (the participant who makes decisions about the case).

## `CaseParticipant`

A `CaseParticipant` binds an actor to their roles and protocol state within one case.
One `CaseParticipant` record exists for each actor engaged in a case.
Because a single actor may participate in many cases and hold different roles in each, `CaseParticipant` scopes an actor's obligations and history to a single coordination context.

A participant record holds the actor's roles in the case, the actor's status history, and where the actor stands on the case's embargo.

## Status objects

Vultron tracks protocol state through immutable snapshots rather than mutable fields.
A change appends a new snapshot to a history list; nothing is changed in place.
This makes the full state history auditable and replayable.

There are two kinds of snapshot:

- A **`CaseStatus`** records the state of the case as a whole: its EM state and its PXA state.
  The case keeps a history of them.
- A **`ParticipantStatus`** records one participant's state: its RM state, and, where the participant's roles call for it, its fix-readiness and fix-deployment state, together with its [embargo consent](../behavior_logic/use-cases/embargo-lifecycle.md).
  Each participant keeps its own history of them.

The difference between the state of the case as a whole and the state of each participant is explained in [Model Interactions](../process_models/model_interactions/index.md).

### Dimension objects

Each snapshot is made of **Dimension Objects** (ADR-0036): small, immutable objects that each own exactly one state machine.
EM, PXA, RM, fix readiness, fix deployment, and embargo consent each have one.
Because each dimension is its own object, it can be compared, serialized, and checked on its own.

!!! tip "Dimension state machines"
    See [Process Models](../process_models/index.md) for the EM, RM, and CS state machines and their transition rules.

## `CVDRole`

`CVDRole` names the roles a participant can hold in a case.
Each value is a single role, and a participant may hold several at once.

Some roles describe a participant's part in the coordination: `REPORTER`, `VENDOR`, `DEPLOYER`, `COORDINATOR`, `OBSERVER`, and `CVE_NUMBERING_AUTHORITY`.
Two describe authority over the case itself: `CASE_OWNER` decides for the case, and `CASE_MANAGER` writes its history.
`FINDER` is deprecated (ADR-0078).
The full list, with what each role obliges, is in [Case Model Fields](../../reference/case_model_fields.md#cvdrole).

## How the objects relate

A `VulnerabilityCase` aggregates:

- One `CaseParticipant` per engaged actor, each with an append-only `ParticipantStatus` history
- An append-only `CaseStatus` history recording EM and PXA state over time
- An append-only case ledger anchored at the case's genesis hash

The participant holding `CASE_MANAGER` — in the prototype, the `CaseActor` — writes the ledger for the case and relays messages between participants.

## See also

- [Case Model Fields](../../reference/case_model_fields.md) — every field of these objects, and a class diagram
- [The CASE_MANAGER and the Case Ledger](case_manager_and_ledger.md) — who writes the case history and how replicas receive it
- [Case Ledger Synchronization](case_ledger_sync.md) — how the canonical ledger orders events and how replicas catch up to it
- [Process Models](../process_models/index.md) — RM, EM, and CS state machines that drive status transitions
- [Demo Scenarios](../scenarios/index.md) — how the objects evolve end-to-end in practice
- ADR-0036: Per-Machine Dimension Objects for `CaseStatus` and `ParticipantStatus`
- ADR-0041: CaseActor-Authoritative Case Initialization
- ADR-0051: CaseActor Has Its Own RM Lifecycle Tracked via CaseParticipant
- ADR-0057: Observer role (`CVDRole.OBSERVER`)
- ADR-0078: Retire `CVDRole.FINDER` — Reporter Is the Protocol-Salient Role
