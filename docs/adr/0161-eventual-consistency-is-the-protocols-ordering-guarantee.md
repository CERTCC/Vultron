---
status: accepted-provisional
date: 2026-10-26
created: 2026-10-26
updated: 2026-10-26
revision: 1
deciders: Allen D. Householder
consulted: >-
  Claude Opus 5.5; ADR-0037, ADR-0079, ADR-0112, ADR-0142, ADR-0155, ADR-0156;
  specs/sync-ledger-replication.yaml SYNC-00, SYNC-03, SYNC-08, SYNC-14, SYNC-16,
  SYNC-17; specs/case-ledger-processing.yaml CLP-14-001; specs/embargo-policy.yaml
  EP-08-002, EP-09-002, EP-09-011; specs/outbox.yaml OX-01-005; issues #3364, #5102
informed: []
stakeholder_type: [project-contributor]
---

# Eventual Consistency Is the Protocol's Ordering Guarantee

## Context and Problem Statement

The CASE_MANAGER commits each case event to the case ledger and sends it to every active participant as `Announce(CaseLedgerEntry)`.
It also sends some messages outside the ledger: relayed embargo Invites, case copies, refusal notices, case invitations and others.
The transport promises no delivery order ([ADR-0037](0037-buffer-out-of-order-ledger-entries.md)), and other implementations may share the wire.
So a participant can receive a direct message before, between or after the ledger entries it relates to, and the CASE_MANAGER can receive one sender's two messages in either order.

The `log_index` sequence is the case's causal order ([ADR-0079](0079-case-ledger-causal-ordering.md)), and a replica holds an early entry until its predecessor arrives (ADR-0037).
It was believed that no decision used arrival order, but that belief was never checked.
It was wrong once before: embargo proposal selection used arrival order until EP-08-002 forbade it.

Our outbox delivers in order per recipient ([ADR-0112](0112-per-recipient-ordered-outbox-delivery.md)), which hides most reordering in our own runs.

What ordering guarantee does the protocol make, and may any decision depend on arrival order?

## Decision Drivers

- The transport gives no order, and another implementation may deliver in any order.
- An ordered outbox loses its order whenever an `Announce` is lost and replayed later, which is exactly when recovery matters.
- Every replica must reach the CASE_MANAGER's case file from the same ledger (SYNC-08-002).
- A participant must be able to explain every outcome from the ledger.

## Considered Options

- Eventual consistency: hash-chain apply and gap repair are the guarantee, and no decision depends on an arrival order the ledger does not define.
- Causal delivery: the protocol requires each sender to deliver in order, and receivers rely on it.
- Total order: every participant receives every message, direct ones included, in one sequence that the CASE_MANAGER assigns.

## Decision Outcome

Chosen option: "Eventual consistency", because the ledger already gives one causal order, and recovery already brings every replica to it, without anything from the transport.

- **The ledger is the one order.** The CASE_MANAGER's observation order is the case's causal order (CLP-14-001). When the CASE_MANAGER takes concurrent assertions from different senders in the order it sees them, the ledger records that order, and every replica learns the same outcome. That is not an arrival-order dependence; it is how the order is defined.
- **Every other decision is the same in every order.** A participant's apply, store or answer must not differ with the order of a direct message and the ledger entries it relates to. The CASE_MANAGER's record must not differ with the order of two assertions that one sender sent before the first was committed, because it cannot see which was sent first.
- **The guarantee is eventual consistency.** A replica that receives the committed entries, in any order, reaches the CASE_MANAGER's case file through hash-chain apply and gap repair. A direct message may not leave a replica in a state its ledger entries do not determine.
- **Per-recipient order is an optimization.** An implementation may deliver in order per recipient. No receiver or sender may rely on it for correctness.
- **A dependency the audit finds is a bug against the rule.** The rule stands whatever the audit found; each order dependency is fixed to meet it, not written into it.

### Consequences

- Good, because the protocol needs nothing from the transport beyond eventual delivery.
- Good, because a new message type has one test to pass: its outcome is the same in every arrival order.
- Good, because ordered delivery stays free to use as an optimization without becoming load-bearing.
- Bad, because one sender's back-to-back assertions lose their send order, so a decision that needs it must get it some other way.
- Bad, because a direct message that writes replica state outside the ledger is order-dependent unless the ledger later makes it idempotent.

## Validation

`test/core/use_cases/received/test_arrival_order.py` delivers an embargo revision's proposal entry, its relayed Invite and the entry that records the Invite's emission to a participant in all six orders.
Every order ends with the CASE_MANAGER's case file, one proposal-index entry and one answer.
Each order dependency still open has a strict `xfail` test in the same file.

## Pros and Cons of the Options

### Eventual consistency

- Good, because it is what the ledger, the holding area and gap repair already give.
- Good, because it holds for any implementation on the wire.
- Bad, because every decision outside the ledger order must be checked for order independence, by test.

### Causal delivery

- Good, because one sender's assertions would keep their send order.
- Bad, because the transport does not give it, so each implementation would need sequence numbers, buffering and retransmission per sender.
- Bad, because a lost message would block every later message from that sender until it was repaired.

### Total order

- Good, because every participant would see one sequence.
- Bad, because every direct message would have to pass through the ledger or a second sequencer, which changes what a direct message is.
- Bad, because it adds a round trip to every message for a property the ledger already gives the case events that need it.

## More Information

### The audit (#5102, 2026-10-26)

The audit classified every received semantic type at a participant and at the CASE_MANAGER, and inventoried every message the CASE_MANAGER sends outside the ledger.
The rules it produced are in `notes/sync-ledger-replication.md` § "No Decision Depends on Arrival Order (SYNC-19)", and the maintained list of direct messages is in `docs/topics/case_lifecycle/case_ledger_sync.md`; the tables below record the audit as it stood.
"Ledger-ordered" below means that the CASE_MANAGER's first committed decision wins and later ones are refused, which SYNC-19-001 allows.

**Ledger apply** (`announce_case_ledger_entry` at a participant) is order-independent by construction.
Effects run only on an entry that extends the chain tail, a forward gap is held and drained in `log_index` order (SYNC-14), case-state checks run at drain time (CSB-19), an entry before genesis is held until the seed (SYNC-15), and an entry a case copy already reflects is stored without effects (SYNC-16-007).
Repairing a lost last entry before a quiet period relies on the participant's position statements (SYNC-17, SYNC-18).

**At a participant:**

| Semantic type | Verdict | Reason |
|---|---|---|
| `announce_case_ledger_entry` | independent | Hash chain, hold and drain, and case-copy position, as above. |
| `announce_vulnerability_case` | independent | A copy is judged by the position it names (SYNC-16-006). Its proposal index is the second path of #5200. |
| `create_case` | independent | The trust anchor is recorded when the request is sent, and earlier entries are held before genesis. |
| `accept_case_proposal`, `reject_case_proposal` | independent | Checked against the case creator recorded at send. |
| `invite_actor_to_case` | independent | Comes causally before the invitee's seed, which follows its answer. |
| `invite_actor_to_full_case` | independent | Stored only; the reply waits until the replica reaches the Invite's ledger position (CM-11-012). |
| `invite_to_embargo_on_case` | **dependent** | Non-owner revision: independent (the permutation test). Owner at EM `NONE`: #5199. Arriving after its proposal is decided: #5200. |
| `announce_embargo_event_to_case`, `remove_embargo_event_from_case` | **dependent** when paused | Stored only by an active replica. A paused signatory applies them locally (CM-31-010): #5201. |
| `reject_invite_to_embargo_on_case` (ER from the CASE_MANAGER) | independent | Closes a pending assertion only. |
| `refusal_notice` | independent | Closes a pending assertion; a repeat is a no-op. |
| `create_processing_fault` | independent | Writes no replica state. |
| `offer_case_participant` (forwarded recommendation), `accept_actor_recommendation`, `reject_actor_recommendation` | independent | Stored; the owner answers by trigger, and the recommender records the answer only. |
| `offer_case_participant_role` (forwarded) | independent | The target re-checks admissibility on its replica, and no check it makes can flip back. |
| `add_case_participant_to_case`, `remove_case_participant_from_case` (notices) | independent | Stored; the replica applies the ledger entry, not the notice. |
| `offer_case_ownership_transfer`, `undo_case_ownership_transfer` | independent | Stored; the effect and the judgement of the answer come from the ledger. |
| `ack_report`, `create_report`, `submit_report` | independent | Before any case; idempotent by report id and checked against the sender's own Offer. |
| `unknown`, `unknown_unresolvable_object` | independent | No state change. |
| Every other type | not applicable | Addressed to the CASE_MANAGER only; a replica refuses it in any order (PCR-08-001). |

**At the CASE_MANAGER:**

| Semantic type | Verdict | Reason |
|---|---|---|
| `invite_to_embargo_on_case` | independent | Concurrent proposals stay open and are chosen by `end_time` (EP-08-002); a proposal after EM `EXITED` is refused. |
| `accept_invite_to_embargo_on_case`, `reject_invite_to_embargo_on_case` | **dependent** for one sender | Across senders: independent, since each row is per participant. One sender's Accept then Reject: the last to arrive wins, #5202. |
| `activate_embargo_on_case`, `reject_embargo_proposal_on_case` | ledger-ordered | The first decision closes the proposal; the second is refused with a notice. |
| `remove_embargo_event_from_case` | independent | Termination cancels every open proposal in the same register step (EP-08-004). |
| `withdraw_from_embargo_on_case` | ledger-ordered | A Leave naming a superseded embargo is refused (EP-09-013). Assertions sent before it share #5203's mechanism. |
| `add_participant_status_to_participant`, `engage_case`, `defer_case` | independent | P/X/A are only added; RM, VF and D are judged against the sender's own record, and the trigger checks its replica first. |
| `add_case_status_to_case` | not applicable | Only the CASE_MANAGER sends it (RSH-04-001). |
| `close_case` | **dependent** for one sender | An assertion sent before the sender's Leave is refused silently when the Leave overtakes it, #5203. |
| `add_note_to_case`, `remove_note_from_case` | independent across senders | A Remove needs the note in the author's replica, so it follows the Add's commit. A note overtaken by its own sender's Leave is #5203, under `close_case`. |
| `add_case_participant_to_case`, `remove_case_participant_from_case`, `invite_actor_to_case`, `accept_invite_actor_to_case`, `reject_invite_actor_to_case` | ledger-ordered | A removal racing an Accept ends removed in either order; a superseded Invite's Accept is refused. |
| `accept_invite_actor_to_full_case`, `tentative_reject_invite_actor_to_full_case`, `reject_invite_actor_to_full_case` | independent | Checked against the Invite's ledger position (CM-11-012). |
| `offer_actor_to_case`, `offer_case_participant`, `accept_offer_case_participant`, `reject_offer_case_participant`, `accept_actor_recommendation`, `reject_actor_recommendation`, `offer_case_participant_role`, `accept_case_participant_role`, `reject_case_participant_role` | ledger-ordered | The first committed answer closes the offer; later answers are refused. |
| `propose_case_ownership_transfer`, `offer_case_ownership_transfer`, `accept_case_ownership_transfer`, `reject_case_ownership_transfer`, `undo_case_ownership_transfer` | ledger-ordered | One Offer may be open at a time; an Accept racing an Undo resolves by commit order. |
| `create_case_proposal`, `accept_case_proposal`, `reject_case_proposal`, `create_case` | independent | A redelivery after the case exists is answered with that case. |
| `create_report`, `submit_report`, `validate_report`, `invalidate_report`, `close_report`, `ack_report`, `add_report_to_case` | independent | Idempotent by report id; the report travels inline. |
| `reject_case_ledger_entry` | independent | A stale Reject causes at most one redundant replay, bounded by the replay guard (SYNC-15-003). |
| `create_processing_fault` | independent | A re-seed is rate-limited and its copy is judged by its position (SYNC-16-004, SYNC-16-006). |
| `announce_case_ledger_entry`, `announce_vulnerability_case`, `announce_embargo_event_to_case`, `refusal_notice` | not applicable | The CASE_MANAGER sends these; it skips a copy of its own. |
| `unknown`, `unknown_unresolvable_object` | independent | No state change. |

**Messages the CASE_MANAGER sends outside the ledger**, with their verdict against the ledger entries they relate to:

| Message | Related ledger entries | Verdict | Reason |
|---|---|---|---|
| Relayed revision or first-proposal `Invite(EmbargoEvent)` (EP-09-002) | The proposal entry and its consent rows before it; its own emission entry and the invitee's row after it | **dependent** for the owner at EM `NONE` (#5199) and after the decision (#5200); otherwise independent | The replica stores the Invite and the embargo it carries; its answer reads only the case and the embargo. In our steady state the Invite reaches the invitee before its own emission entry. |
| Joiner relay and reinstatement `Invite(EmbargoEvent)` (EP-09-011, CM-31-013) | The joiner's seed, backfill, emission and row entries | independent within the pre-bootstrap window | Before the seed it is queued and replayed after it; past the window it is dropped (#5204). |
| `Announce(VulnerabilityCase)`: join seed, genesis pre-seed, re-seed (SYNC-16-003) | Every entry at or before the copy's position | independent | Judged by the position it names (SYNC-16-006); entries before the seed are held, and entries it reflects are no-ops. |
| Backfill and replay `Announce(CaseLedgerEntry)` | Themselves | independent | Ledger apply. |
| Full-case `Invite(Actor)` | Its own entry, whose position is the reply's floor | independent | Stored; the reply waits for the floor (CM-11-012). |
| Stub `Invite(Actor, CaseStub)` | The invitee's participant entry | independent | A superseded Invite's answer is refused by the CASE_MANAGER. |
| Refusal notice `Reject(activity)` (ADR-0141), ER `Reject(Invite(EmbargoEvent))`, `Reject(Leave(VulnerabilityCase))` | None | independent | Closes a pending assertion or answers an ask; writes no case state. |
| Removal and reinstatement notices `Remove`/`Add(CaseParticipant)` | The removal or reinstatement entry | independent | Stored; the replica applies the entry. |
| Ending notices `Remove(EmbargoEvent)`, `Announce(EmbargoEvent)` to a paused signatory (CM-31-009) | The termination or shorter-revision entry, which the paused replica gets only on backfill | **dependent** (#5201) | They write replica case state outside the ledger, as the relayed Invite writes the proposal index (#5200). |
| Forwarded `Offer(CaseParticipant)`, recommendation answers, forwarded `Offer(CaseParticipantRole)`, ownership `Offer(VulnerabilityCase)` | The offer's own entry | independent | Stored and answered by trigger; the CASE_MANAGER judges the answer against the ledger. |
| Case-actor `Accept`/`Reject(CaseProposal)`, bootstrap `Create(VulnerabilityCase)` | Genesis and creation entries | independent | Processed before the case is held; entries before genesis are held (SYNC-15). |
| `Create(ProcessingFault)` answering a malformed Invite | None | independent | Logged only. |

The audit also found one delay bound that is not an ordering question: a CASE_MANAGER message that reaches a replica more than the pre-bootstrap window before its seed is dropped and never resent (#5204).

Generated spec requirements: `sync-ledger-replication.yaml` SYNC-19-001 through SYNC-19-003.
