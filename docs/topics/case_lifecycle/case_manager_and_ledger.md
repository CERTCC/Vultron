---
description: >
  Who writes a case's history, which entries it records, and how every participant receives them.
stakeholder_type: [platform-developer]
level: 300
page_type: explanation
introduces: [CASE_MANAGER, Case Ledger Entry, Ledger Admission, Participant Case Replica, Canonical Recorded Log, Single-Writer Regime, Ledger Fanout]
---

# The CASE_MANAGER and the Case Ledger

A vulnerability case is coordinated by organizations that do not share a database.
Each one keeps its own copy of the case.
This page explains who is allowed to change the case, where the authoritative history of the case lives, and how every participant's copy is kept up to date.

Three ideas carry the rest of the protocol:

- One participant, the **CASE_MANAGER**, is the only one that writes the case history.
- That history is the **case ledger**, and only the changes the CASE_MANAGER admits go into it.
- The CASE_MANAGER sends each new ledger entry to every participant, and each participant applies it to its own copy.

---

## One writer, many copies

Every participant in a case keeps a local copy of the case, called a **replica** (in the glossary, a **Participant Case Replica**).
No participant can read or write another participant's replica.
Knowledge travels only in messages — see the [Actor Knowledge Model](../actor-knowledge-model.md).

One peer is different.
Whichever participant holds the `CASE_MANAGER` role is the case's **single-writer authority** — the **CASE_MANAGER**.
It keeps the **case ledger**: the append-only history that is authoritative for the case, and it is the only peer that appends to that history ([CLP-01-003](../../reference/specs/protocol.md#clp-01-003)).
In the prototype this authority is enacted by a dedicated service actor (the **Case Actor**), but the authority derives from the role, never from that actor's name or URL ([ADR-0088](../../adr/0088-consolidate-case-authority-determination.md)).

The flow of a change is always the same:

1. A participant sends the CASE_MANAGER an assertion — *I accept the embargo*, *my report is now validated*, *here is a note*.
2. The CASE_MANAGER judges the assertion.
   If it admits the assertion, it appends an entry recording it.
   Each change the act causes beyond what the assertion itself states then follows as its own CASE_MANAGER-authored entry, carrying the changed record in full: a participant's new RM status after *my report is now validated*, for example ([CLP-07-013](../../reference/specs/protocol.md#clp-07-013)).
   If it refuses the assertion, it appends nothing and records the refusal in its structured logs instead.
3. The CASE_MANAGER sends each new entry to every participant as `Announce(CaseLedgerEntry)`.
4. Each participant records each entry and copies what it carries into its own replica, ids and times included, deriving nothing of its own ([CM-23-016](../../reference/specs/protocol.md#cm-23-016)).

Because there is exactly one writer, no participant ever has to reconcile two competing versions of the case history.
There is only one version.
A participant's replica is a projection of that history, not an independent record.

The same rule applies in reverse: a participant applies a case update only from the CASE_MANAGER for that case, and refuses an update from any other sender ([PCR-03-001](../../reference/specs/protocol.md#pcr-03-001)).
Nobody else can write to a replica, and the replica's owner does not edit it directly either — even when that owner is the organization that opened the case.

The CASE_MANAGER is a role, not an organization.
It is separate from the `CASE_OWNER` role, which belongs to the participant who makes decisions about the case.
The objects a case is made of, including the roles a participant can hold, are described in [The Case Model](case_model.md).

---

## Only admitted entries

The ledger holds only the assertions the CASE_MANAGER admitted.
The CASE_MANAGER's verdict on an assertion is called **Ledger Admission**: the assertion is either *admitted* or *refused* ([CLP-02-012](../../reference/specs/protocol.md#clp-02-012), [glossary](../../reference/glossary.md#sync-authority-replication)).
It is the authoritative history of the case ([CLP-04-001](../../reference/specs/protocol.md#clp-04-001)).
A refused assertion never becomes an entry ([CLP-04-007](../../reference/specs/protocol.md#clp-04-007)).
The CASE_MANAGER reports the refusal through its structured logs instead ([CLP-04-008](../../reference/specs/project.md#clp-04-008)).

Admitted and refused are not the same as the `Accept` and `Reject` activities.
A participant that declines an invitation or an offer sends a `Reject`, and that `Reject` is a case event like the `Accept` it could have sent.
The CASE_MANAGER admits it and appends an entry for it, so every replica sees the request closed ([CLP-02-012](../../reference/specs/protocol.md#clp-02-012)).

Because nothing in the ledger needs filtering out, a replica reconstructs case state from every entry it holds ([CLP-04-002](../../reference/specs/protocol.md#clp-04-002)).
The hash chain is computed over the same entries ([CLP-04-003](../../reference/specs/protocol.md#clp-04-003)).
Each entry names the entry before it as its predecessor, with nothing in between.

Each entry — a **Case Ledger Entry** — is immutable once written ([SYNC-01-001](../../reference/specs/protocol.md#sync-01-001)).
It carries its position in the case history, the time the CASE_MANAGER recorded it, a copy of the assertion it records, and two hashes: one of its own content and one of the entry before it ([SYNC-01-002, SYNC-01-003](../../reference/specs/protocol.md#sync-01)).
The hashes link the entries into a chain, so a participant can tell whether a new entry belongs at the end of the history it already holds.

---

## Fan-out: every participant gets every entry

After it appends an entry, the CASE_MANAGER sends that entry to each participant individually ([SYNC-02-003](../../reference/specs/protocol.md#sync-02-003)).
The message is an `Announce` whose object is the entry itself, carried inline or by reference ([SYNC-02-001, SYNC-02-004](../../reference/specs/protocol.md#sync-02)).
A participant needs every field of the entry to check it against the chain it already holds.
The reference implementation cannot yet fetch an object by reference, so it always sends the whole entry inline ([SYNC-02-005](../../reference/specs/project.md#sync-02-005)).

This one-way sending of entries from the CASE_MANAGER to every participant is the **Ledger Fanout**.
Participants never send ledger entries to each other; every copy comes from the one writer ([ADR-0077](../../adr/0077-ledger-replication-companion-spec.md)).
A replica is synchronized when the last entry it holds is the last entry the CASE_MANAGER wrote.

An active embargo is the one exception to sending every entry at once.
The ledger is case content, so the CASE_MANAGER sends no entry to a participant that has not accepted the active embargo ([CM-10-004, CM-10-005](../../reference/specs/protocol.md#cm-10)).
It also answers that participant's request for missing entries with nothing.
It records the first entry it held back.
When the participant accepts the embargo, or the embargo ends, the CASE_MANAGER sends it every entry from that one on, in order ([CM-10-006](../../reference/specs/protocol.md#cm-10-006)).
Embargo invitations are not ledger entries, so they still reach that participant.

A participant checks each entry before it applies it.
An entry that does not follow on from the participant's last entry is not applied.
The participant tells the CASE_MANAGER where its history ends, so that the CASE_MANAGER can send what is missing ([SYNC-03-001, SYNC-03-002](../../reference/specs/protocol.md#sync-03)).
Receiving the same entry twice changes nothing ([SYNC-03-003](../../reference/specs/protocol.md#sync-03-003)).

Messages can still arrive in the wrong order, because the transport makes no promise about order.
An entry that arrives ahead of a missing one is held rather than discarded ([SYNC-14-001](../../reference/specs/protocol.md#sync-14-001)).
How a replica holds that early entry until the one before it arrives, and why the order of the ledger is the order of the case, is the subject of [Case Ledger Synchronization](case_ledger_sync.md).

---

## Further reading

- [The Case Model](case_model.md) — the objects a case is made of and the roles participants hold
- [Case Ledger Synchronization](case_ledger_sync.md) — ordering, out-of-order entries, and what a replica guarantees
- [Case Ownership Transfer](ownership_transfer.md) — how the `CASE_OWNER` role moves from one participant to another
- [Case Authority, Trust, and Routing](case_authority_and_trust.md) — who may change what, why messages route through the CASE_MANAGER, and how a participant learns which actor to trust
- [Actor Knowledge Model](../actor-knowledge-model.md) — why nothing can be learned except by receiving a message
- [Federation](../future_work/federation.md#the-case-ledger-and-the-delivery-log) — future work on the ledger when each organization runs its own service
- [Protocol specifications](../../reference/specs/protocol.md) — the normative requirements behind this page, including CLP-01, CLP-04, PCR-03, and SYNC-01 through SYNC-03
