---
status: accepted
date: 2026-10-02
created: 2026-10-02
updated: 2026-10-02
revision: 1
deciders: Allen D. Householder
consulted: >-
  Claude Opus 5.5; Issue #4153, Concern #4133, Bug #4132, PR #4141;
  ADR-0048, ADR-0065, ADR-0093, ADR-0113; specs/case-management.yaml CM-18, CM-28;
  specs/em-behavior.yaml EMB-01, EMB-03, EMB-17; specs/handler-protocol.yaml HP-01;
  specs/message-semantics-mapping.yaml MSM-07
informed: []
stakeholder_type: [project-contributor]
---

# An Expired Invite Is Not a Decline, and a Terminated Embargo Is Not the Start State

## Context and Problem Statement

ADR-0048 settled the Participant Embargo Consent (PEC) machine at five states: `UNBOUND`, `INVITED`, `SIGNATORY`, `LAPSED` and `DECLINED`.
ADR-0065 added an RSVP deadline to an embargo Invite and, in its part 5, chose to record an invite that passes its deadline as `DECLINED` — the "pocket veto" — and to keep the difference between silence and refusal only in the ledger.
CM-28-004 made that a MUST NOT: no additional PEC state for "never responded".

Reviewing PR #4141, which builds the CASE_MANAGER's expiry evaluation and its replay, showed that the two facts are not interchangeable:

1. A participant that answered **no** has made a decision.
   A participant that **did not answer** has made none.
   Code, logs, demos and every replica read the scalar state, not the ledger provenance, so collapsing the two into `DECLINED` reports a decision nobody made.
2. CM-28-005 already requires the two to be distinguishable.
   ADR-0065 met it with a separate ledger event type, but a replica that reads the participant's state still cannot tell them apart.

The same review found a second conflation in the machine itself.
`UNBOUND` is both the initial state and the destination of `RESET`, which fires in exactly one place: `terminate_active_embargo`, the step that moves the case to `EM.EXITED`.
`EM.EXITED` has no outgoing transition, so a participant reset there can never be invited again, yet the state it holds says it can.
A rejected *proposed* embargo (`EM PROPOSED → NONE`) resets nobody.
"`UNBOUND` after termination" is therefore a sink wearing the start state's name.

A third question arose under the relay topology of ADR-0113.
EMB-03-003 says a participant that receives a revision while the case is public, exploited or attacked (P/X/A) MUST emit ET to terminate the embargo.
But termination is the case owner's decision, or the CASE_MANAGER's when delegated (EP-09-008, CM-24), and a participant answers only the Invite addressed to it (EP-09-003).
And Bug #4132 showed that a store holding a copy of an embargo activity it is not addressed by runs the receive tree, writes state and may answer, although HP-01-005 already says such a copy is REFUSED.

The question: **what PEC state records an invite that expired, what state records a terminated embargo, and who answers a revision Invite once the case is P/X/A?**

## Decision Drivers

- The scalar PEC state is what every reader consults (CM-18-001); a fact that matters must be visible there, not only in ledger provenance.
- CM-28-005: an expired invite must be distinguishable from an explicit refusal.
- A state the machine can never leave must say so; a sink must not share a name with a state that has outgoing transitions.
- Only the CASE_MANAGER writes shared EM state, and termination is the owner's (or delegated CASE_MANAGER's) decision (EP-09-008, ADR-0113).
- An actor acts only on mail addressed to it (HP-01-005).

## Considered Options

- Keep the five-state machine; carry silence-versus-refusal and termination in the ledger only (ADR-0065 part 5 as written).
- Add a reason field to `PecDimension` (rejected already by CM-28-010).
- Add two states, `EXPIRED` and `UNBOUND_EXITED`, as one revision of the ADR-0048 machine.

## Decision Outcome

Chosen option: "Add two states, `EXPIRED` and `UNBOUND_EXITED`", because it is the only option that makes the two facts visible where they are read, and it makes the machine's sink explicit.

### The seven-state machine

| State | Meaning |
|---|---|
| `UNBOUND` | Initial. Not bound by any embargo terms (ADR-0048). |
| `INVITED` | Invited; no answer yet. |
| `SIGNATORY` | Accepted the active embargo. |
| `LAPSED` | Was `SIGNATORY`; the owner activated longer terms this participant has not accepted (ADR-0093). |
| `DECLINED` | Explicitly refused: a `Reject(Invite(EmbargoEvent))` or a consent withdrawal (ADR-0093). |
| `EXPIRED` | Invited, and the RSVP deadline passed with no answer. |
| `UNBOUND_EXITED` | Terminal. The embargo terminated (`EM.EXITED`). |

| Trigger | Transitions |
|---|---|
| `INVITE` | `UNBOUND`, `LAPSED`, `DECLINED`, `EXPIRED` → `INVITED` |
| `ACCEPT` | `UNBOUND`, `INVITED`, `LAPSED`, `EXPIRED` → `SIGNATORY` |
| `DECLINE` | `UNBOUND`, `INVITED`, `LAPSED`, `SIGNATORY`, `EXPIRED` → `DECLINED` |
| `REVISE` | `SIGNATORY` → `LAPSED` |
| `EXPIRE` | `INVITED` → `EXPIRED` |
| `EXIT` | every state except `UNBOUND_EXITED` → `UNBOUND_EXITED` |

1. **`EXPIRED` is distinct from `DECLINED`.**
   The CASE_MANAGER's expiry evaluation (CM-28-003, CM-28-014) applies `EXPIRE`, never `DECLINE`.
   `DECLINED` is reached only by an explicit refusal.
   The handling is otherwise the same: an expired participant can be re-invited (`EXPIRED → INVITED`, EMB-17-003), and a late Accept the CASE_MANAGER honours moves it straight to `SIGNATORY` (`EXPIRED → SIGNATORY`, EMB-17-002).
   A late *Reject* is an explicit answer and records `DECLINED` (`EXPIRED → DECLINED`): an answer is a stronger fact than the silence that preceded it, exactly as a late Accept is honoured rather than refused (EMB-17-001).
   CM-28-005 is now satisfied by the state itself; the distinct ledger entry (CM-28-009) remains, so a replica learns the move from the CASE_MANAGER and never computes it (CM-28-014).
   The ledger event type is renamed from `invite_to_embargo_on_case_lapsed` to `invite_to_embargo_on_case_expired`, with snapshot type `Expire`: it never named the `LAPSED` state, and "invite expiry", not "invite lapse", is the term in code, notes and specs.
2. **`UNBOUND_EXITED` is a distinct terminal state tied to `EM.EXITED`.**
   The trigger `RESET` is renamed `EXIT`, so its link to `EM.EXITED` is visible.
   `EXIT` moves every non-terminal state to `UNBOUND_EXITED`, the initial `UNBOUND` included, and no transition leaves it: a later `INVITE` is refused (CM-18-009).
   It fires where `RESET` fired — the embargo termination cascade — on the CASE_MANAGER and, through the teardown replay, on every replica.
   The initial `UNBOUND` keeps its name and its full chain.
   A late Accept on a case with no current embargo (EMB-17-004) changes no consent: in `EM.EXITED` the participant already holds `UNBOUND_EXITED`, and in `EM.NONE` an expired participant stays `EXPIRED`, which a later embargo may re-invite.
   `embargo_adherence` is unchanged — it is `True` only for `SIGNATORY` (CM-18-008) — so `UNBOUND_EXITED` reads `False`, as `UNBOUND` did.
3. **A non-owner participant answers a P/X/A revision with ER, never ET.**
   EMB-03-003's ET is withdrawn for any participant that is neither the case owner nor the CASE_MANAGER.
   Such a participant that believes the case is public, exploited or attacked rejects every further embargo proposal, Invite or revision with ER, addressed to the CASE_MANAGER, as EMB-01-002 already requires for a first proposal, and writes no EM state.
   Termination is initiated only by the case owner, or by the CASE_MANAGER when delegated (EP-09-008, CM-24, ADR-0113).
4. **An unaddressed copy is refused at the door.**
   Every received embargo use case checks addressing — the receiver is the sender, or is named in `to` or `cc` — before any receive tree runs.
   A copy that fails reports `REFUSED` naming the receiver and the actual recipients (HP-01-005), writes nothing, and sends no ER: EMB-01-002's ER duty binds only the addressee.

### Consequences

- Good, because every reader of the scalar state can tell a decision from silence, and a live state from a sink, without consulting the ledger.
- Good, because the machine now refuses an Invite after termination instead of presenting a re-invitable state that EM forbids.
- Good, because P/X/A handling no longer asks a participant to make the owner's decision.
- Bad, because the PEC table grows from five states to seven and from five triggers to six; every consumer that enumerated states had to be revisited.
- Bad, because stored records and ledger entries written before this ADR carry `DECLINED` for an expired invite, `UNBOUND` after termination and the old event type name; they are left as they are (the prototype keeps no migration for them).

## Validation

- State-machine tests cover every new transition, the refusal of every trigger from `UNBOUND_EXITED`, and the expiry evaluation applying `EXPIRE` rather than `DECLINE`.
- A per-actor-store test terminates an embargo and asserts every participant reads `UNBOUND_EXITED` on the CASE_MANAGER and on a replica, and that a later `INVITE` is refused.
- A per-actor-store test delivers a relayed revision Invite to a participant whose case is P/X/A and asserts one ER to the CASE_MANAGER, no ET and no EM change.
- Tests pin `REFUSED` with the addressing reason for an unaddressed copy of each received embargo activity.

## Pros and Cons of the Options

### Keep the five-state machine; carry the facts in the ledger only

- Good, because no consumer that enumerates PEC states has to change.
- Bad, because a reader of the scalar state cannot tell an expired invite from a refusal without walking the ledger, which CM-28-005 asks it to do.
- Bad, because `UNBOUND` stays both the initial state and the post-termination sink, so the machine offers an `INVITE` that EM `EXITED` forbids.

### Add a reason field to `PecDimension`

- Good, because the state table keeps five states.
- Bad, because CM-28-010 already rejected it: a reason field beside the state is a second source of truth that can drift from the ledger.
- Bad, because it does nothing for the post-termination sink.

### Add `EXPIRED` and `UNBOUND_EXITED`

- Good, because both facts are visible in the scalar state, where every reader looks (CM-18-001).
- Good, because the sink is explicit and the machine refuses every trigger from it.
- Bad, because every consumer that enumerated PEC states had to be revisited.

## More Information

- Amends ADR-0048 (the five-state machine and its transition table, CM-18-001, CM-18-003) and ADR-0065 part 5 ("No new PEC state"), which this ADR reverses.
- ADR-0114's note that an expired embargo Invite records `DECLINED` is corrected in place to `EXPIRED`.
- Amended specs: CM-18-001, CM-18-002, CM-18-003, CM-18-004, CM-28-004, CM-28-005, CM-28-007, CM-28-009, CM-28-014, CM-23-014, MSM-07-002, MSM-07-006, MSM-07-007, EMB-17-002, EMB-17-003, EMB-17-004, EMB-13-001, EMB-03-003, EMB-01-002, EP-09-001, EP-09-004.
- Notes: `notes/participant-embargo-consent.md`, `notes/embargo-lifecycle.md`.
- Source: Issue #4153 (owner decisions of 2026-10-02), Concern #4133, Bug #4132.
