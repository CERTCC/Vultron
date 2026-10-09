---
status: proposed
date: 2026-10-09
created: 2026-10-09
updated: 2026-10-09
revision: 1
deciders: Allen D. Householder
consulted: >-
  Claude Opus 5.5; Epic #4283, Issue #4290, Issue #4427, Issue #4449; ADR-0122, ADR-0124;
  specs/em-behavior.yaml EMB-06, EMB-16, EMB-17, EMB-18
informed: []
stakeholder_type: [project-contributor]
---

# EM Is Computed From the Embargo Register Under the EM Transition Table

## Context and Problem Statement

ADR-0122 put an embargo register on the case and computed the case's EM state from it, so EM can no longer be set directly or disagree with the embargoes the case holds.
It also said "EM has no transition table of its own", and #4290 deleted the table.
The EM states survived, but nothing stated or checked which EM moves are legal.
That reading treats the register as replacing the EM state machine, when it was meant to be a layer underneath it: EM still moves `NONE → PROPOSED → ACTIVE ⇄ REVISE → EXITED`, and those moves are now computed from register changes instead of declared.

The EM model was first written assuming one proposal open at a time, so accepting one proposal implied rejecting any other.
The register allows several open proposals, and the multi-proposal moves were never written as EM transitions.

The question: **how does the EM state machine relate to the embargo register, and what are its transitions when several proposals are open?**

## Decision Drivers

- The EM state machine is part of the protocol model and must not be broken by a change to how its state is stored.
- EM is never set by fiat: it is computed from the register (ADR-0122), and the register changes only by replaying committed entries (ADR-0124).
- A defect in the register layer must surface as a refused change, not as a silent illegal EM move.
- `PROPOSED` and `REVISE` are the same negotiation, differing only in whether an embargo is already in force.
- A participant's consent is to an embargo's terms; a decision that does not change those terms should not discard it.
- A late answer to an invitation can still be honoured (EMB-17-001).

## Considered Options

- The derivation table is the only rule; the EM transition table is gone (ADR-0122 revision 3 as built).
- The EM transition table is restored and checked by tests only.
- The EM transition table is restored and every register change is checked against it.

## Decision Outcome

Chosen option: "The EM transition table is restored and every register change is checked against it", because it is the only option in which the EM state machine remains a rule the system enforces, rather than a property the register happens to have.

### The EM state machine sits on top of the register

EM is computed from the register with the derivation table of ADR-0122 and is never set directly.
The EM transition table is normative: every register step maps to one EM trigger, and the EM state before and after the step MUST be one of the table's moves for that trigger.
A step whose EM move is not in the table is refused with no write, in the same place a broken register invariant is refused.
Because the check sits in the register step, the CASE_MANAGER and every replica apply it through the one replay function (ADR-0124).
A step the register allows but the table refuses is a defect in the register layer, not a gap in the EM model.

| Register step | EM trigger |
|---|---|
| `PROPOSE` | `propose` |
| `ACTIVATE`, with `SUPERSEDE` of any `ACTIVE` entry | `accept` |
| `REJECT` | `reject` |
| `TERMINATE`, with `CANCEL` of each `PROPOSED` entry | `terminate` |
| `CANCEL` of each `PROPOSED` entry on a threat signal with no `ACTIVE` entry (EMB-16-001) | `reject` |

Withdrawal by `Leave(EmbargoEvent)` changes consent rows only, not the register, so it is not an EM move.

### The transitions, with several proposals open

| Trigger | Source → Destination |
|---|---|
| `propose` | `NONE → PROPOSED`, `PROPOSED → PROPOSED`, `ACTIVE → REVISE`, `REVISE → REVISE` |
| `reject` | `PROPOSED → NONE`, `PROPOSED → PROPOSED`, `REVISE → ACTIVE`, `REVISE → REVISE` |
| `accept` | `PROPOSED → ACTIVE`, `PROPOSED → REVISE`, `REVISE → ACTIVE`, `REVISE → REVISE` |
| `terminate` | `ACTIVE → EXITED`, `REVISE → EXITED` |

EM leaves `PROPOSED` or `REVISE` only when the last open proposal is off the table.
Rejecting one of several proposals leaves EM where it is; only rejecting the last returns `PROPOSED` to `NONE` or `REVISE` to `ACTIVE`.
`PROPOSED` and `REVISE` are symmetric: both mean at least one proposal is open, and `REVISE` also means an embargo is in force.

### Activating one proposal leaves the others open

When the case owner activates one proposal, every other open proposal stays open, now as a revision of the embargo in force.
So `accept` from `PROPOSED` reaches `REVISE` when another proposal is open, and `accept` from `REVISE` stays at `REVISE`.
A participant's consent row for a proposal is about that proposal's terms, which activation does not change, so every answer already given stays valid and nothing is re-asked.
The owner who does not want a leftover proposal rejects it explicitly.

### A proposal ends only by an explicit decision or by termination

An open proposal leaves `PROPOSED` only by the owner's `ACTIVATE` or `REJECT`, or by `CANCEL` when the embargo question becomes moot (termination or a threat signal).
RSVP deadlines time out invitees' consent rows (`INVITED → TIMED_OUT`, ADR-0118) and never close the proposal itself.
The owner reads the timed-out rows and decides.

### Consequences

- Good, because the EM state machine stays the protocol's model: its states, triggers and transitions are written once and enforced on every change.
- Good, because a register defect that would produce an illegal EM move is refused when it happens, on the CASE_MANAGER and every replica alike.
- Good, because EM remains computed, so the EM table adds a rule and no second way to set EM.
- Good, because a leftover proposal keeps the consent already given to it, and a "start short, extend later" negotiation needs no re-proposal.
- Good, because late answers can still be honoured: a proposal whose RSVP deadlines have passed is still open.
- Good, because tools that draw or export the EM machine (the demo state export, #4427) read the table instead of encoding their own copy.
- Bad, because the table and the derivation must be kept consistent; the every-change check makes a mismatch fail loudly.
- Bad, because a leftover proposal nobody pursues keeps the case in `REVISE` until the owner rejects it.

### Effect on earlier decisions

- ADR-0122 is amended: its "EM is derived from the register" section no longer retires the EM transition table, and points here.
  Its register, consent rows, derivation table and messages stand.
- ADR-0124 is unchanged; the EM check is part of the replay function's register step.
- EMB-06-001 (receive ER) and EMB-16-001 are read with the multi-proposal moves: a reject returns EM to `NONE` only when no other proposal is open.

## Validation

- A property test enumerates register states, applies every legal register step, and asserts that each `(trigger, EM before, EM after)` is in the table (EMB-18-005).
- A test asserts that `vultron/core/states/em.py` holds the table and that a register step whose EM move is not in it is refused (EMB-18-006; strict `xfail` until #4449 lands).

## Pros and Cons of the Options

### The derivation table is the only rule

- Good, because there is one table to maintain.
- Bad, because the EM state machine survives only as a picture: nothing stops a register change from producing a move the EM model forbids, such as `ACTIVE → NONE`.
- Bad, because tools that show the EM machine have nothing to read, and each encodes its own copy (#4427).

### The table restored, checked by tests only

- Good, because nothing runs at change time.
- Bad, because it protects only the register states the test generator reaches; a path no test covers can still make an illegal move.

### The table restored, checked on every change

- Good, because an illegal EM move is refused when it happens, on every node.
- Good, because EM is already derived on every register change, so the check costs one lookup.
- Bad, because the table, the derivation and the register's own transitions are three related tables to keep consistent.

### Activating one proposal tacitly closes the others

- Good, because `accept` always ends in `ACTIVE`, as the single-proposal model drew it.
- Bad, because it discards consent that is still accurate, and each closed proposal's proposer must propose again.
- Bad, because the closures are side effects a reader of the ledger must know the rule to see.

### RSVP deadlines close the proposal

- Good, because stale proposals clean themselves up.
- Bad, because a proposal everyone agreed to would close before the owner decides, unless further exceptions are added.
- Bad, because a timed-out invitee's late answer could no longer be honoured (EMB-17-001).

## More Information

Decided in the maintainer's design session of 2026-10-09, reviewing the open issues of epic #4283.
Implementation is tracked in #4449.

Generated spec requirements: `em-behavior.yaml` EMB-18-005, EMB-18-006; EMB-06-001 updated.
