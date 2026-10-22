---
status: proposed
status_override: >-
  Decided in planning (#5080); SYNC-18-006 holds by construction, but nothing of
  the decision is built yet, so the record stays editable while its two
  implementation tasks land.
date: 2026-10-22
created: 2026-10-22
updated: 2026-10-22
revision: 1
deciders: Allen D. Householder
consulted: >-
  Claude Opus 5.5; ADR-0107, ADR-0121, ADR-0142; specs/sync-ledger-replication.yaml
  SYNC-03-004, SYNC-10-005, SYNC-16-003, SYNC-16-004, SYNC-16-005;
  specs/case-management.yaml CM-11-011, CM-11-012; specs/vultron-as2-mapping.yaml
  VAM-04-011; issues #5080, #5098, #4797
informed: []
stakeholder_type: [project-contributor]
---

# Every Case Activity States Its Sender's Ledger Position

## Context and Problem Statement

The CASE_MANAGER judges a participant's act against its own current case.
It has no record of what the participant knew when it acted, so an act built on a stale replica looks the same as one built on a current replica.

Three mechanisms already carry a ledger position, each in its own slot.
The full-case Invite and its three replies carry a `LedgerPosition` as a JSON string in `content` (VAM-04-011, CM-11-011).
`Reject(CaseLedgerEntry)` carries a bare entry hash in `context`, which SYNC-03-004 asks every participant message to carry and which nothing else does.
A full-case copy of a case carries a `ledgerTail` member on the case object (SYNC-16-005).

Which activities should state their sender's ledger position, where on the wire, and what should a receiver do with it?

## Decision Drivers

- The CASE_MANAGER's ledger records what each actor knew when it acted, as evidence beside the act.
- One fact has one wire form, so a receiver never reconciles two copies.
- A position that is only a record never refuses an act that is otherwise sound.
  Lagging the latest entry is normal under asynchronous fan-out, and SYNC-10-005 allows an actor to act while it lags.
- Stale answers to replaced objects are already refused by the object they name, such as a replaced embargo version (EP-09-004).
- Core code receives validated, non-optional values (ADR-0032).

## Considered Options

- Every case activity, from any sender, carries `ledgerTail`; a lag is recorded only.
- Only decisions (`Accept`, `Reject`, `TentativeReject` and proposals) carry it.
- Every case activity carries it, and each activity type declares whether a lag refuses it.
- Every case activity carries it, and any act whose position lags the CASE_MANAGER's latest entry is refused.

## Decision Outcome

Chosen option: "Every case activity, from any sender, carries `ledgerTail`; a lag is recorded only", because it gives every ledgered act its provenance with one rule and one wire form, and it leaves the judgment of the act where it already is.

- **Slot.** The position travels as the activity's `ledgerTail` property, an object with `logIndex` and `entryHash`, the same term and shape SYNC-16-005 puts on a case copy.
  `content` cannot be the general slot, because `Create(Note)` and other activities carry their text there.
- **Scope.** Every activity about a case whose ledger its sender holds carries the sender's tail as of building the activity, the CASE_MANAGER's activities included.
  Activities sent before the sender holds the ledger carry none, and so do activities whose object already states its position (`Announce(CaseLedgerEntry)`, `Announce(VulnerabilityCase)`).
- **One mechanism.** The full-case Invite, its replies and `Reject(CaseLedgerEntry)` move their positions to `ledgerTail`.
  SYNC-03-004's `context` hash is retired, and `context` returns to its AS2 meaning.
- **Required.** A receiver refuses, at the parse edge, a case activity in scope whose `ledgerTail` is missing or malformed.
- **A lag is recorded.** The CASE_MANAGER never refuses or holds an act because its position lags.
  The full-case reply's floor (CM-11-012) is the one per-activity rule, and it stays.
- **A split is repaired.** A position that names an entry the CASE_MANAGER does not hold means the sender's chain has split from the canonical ledger.
  The act is still judged on its own merits; the split is logged at ERROR and an active participant is re-seeded through the rate-bounded path of SYNC-16-003 and SYNC-16-004.
- **Ledgered by construction.** The position is part of the received body, which the entry records verbatim (ADR-0107).

### Consequences

- Good, because every ledgered act carries what its actor knew, with no change to how the act is judged.
- Good, because three slots become one, and a new message type is stamped without a per-type decision.
- Good, because a stamp is an implicit position statement, which the acknowledged-position record of #5098 can read.
- Bad, because every case activity gains a field.
  VAM-04-011 chose `content` so that no AS2 verb gained one; this reverses that choice, at the cost of the one vocabulary term SYNC-16-005 already adds.
- Bad, because a peer that omits the field is refused, so a second implementation must stamp from its first message.
- Neutral, because the CASE_MANAGER's response to a split position is undecided between three answers: re-seed, log only, or refuse the act.
  Re-seeding is chosen for now; the open question is kept in `notes/sync-ledger-replication.md`.

## Validation

The SYNC-18 requirements carry marker tests in `test/core/use_cases/received/test_activity_ledger_tail.py`, strict `xfail` until the behavior is built.

## Pros and Cons of the Options

### Every case activity, any sender, recorded only

- Good, because one rule covers every sender and every message type.
- Good, because it refuses nothing the protocol already admits.
- Bad, because it adds a field to every case activity.

### Decisions only

- Good, because fewer activities change.
- Bad, because someone keeps a list of which types are decisions, and notes and status updates go unrecorded.

### Per-activity rules

- Good, because a type whose correctness depends on currency can say so.
- Bad, because every new message type needs its own decision, and the existing object references already catch stale answers.

### Refuse any lagging act

- Good, because no act is ever built on an old view.
- Bad, because it refuses ordinary acts in a busy case and contradicts SYNC-10-005.

## More Information

The idea is #5080.
Issue #5098 adds `Read(CaseLedgerEntry)` for the quiet period, when a participant has nothing else to send; feeding received stamps into the same acknowledged position is planned there.

Generated spec requirements: `sync-ledger-replication.yaml` SYNC-18.
