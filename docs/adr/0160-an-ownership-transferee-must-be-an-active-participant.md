---
status: proposed
date: 2026-10-26
created: 2026-10-26
updated: 2026-10-26
revision: 1
deciders: Allen D. Householder
consulted: >-
  Claude Opus 5.5; ADR-0114, ADR-0148; notes/ownership-transfer.md;
  issues #5186, #5189
informed: []
stakeholder_type: [project-contributor]
partially_supersedes:
  - 0148-an-owner-proposes-an-ownership-transfer-offer-and-the-case-manager-makes-it.md
---

# An Ownership Transferee Must Be an Active Participant

## Context and Problem Statement

ADR-0148 has the Case Owner propose an ownership transfer to the CASE_MANAGER, which checks the proposal and makes the `Offer(VulnerabilityCase)` itself.
The check it names on the transferee is only that it is an actor the CASE_MANAGER can address, neither the CASE_MANAGER nor the proposer.
It does not ask whether the transferee is in the case.

That leaves two gaps.
The Offer carries the case inline, with its active embargo, its participant records and its reports, so an actor outside the case is sent embargoed case content just by being offered the case.
The protocol's entitlement rule says only an active participant receives case content (CM-10-004, ADR-0114); the transfer Offer bypassed it.
And an actor with no participant record cannot be granted `CASE_OWNER`, since that role lives on the participant record (CM-21-002), so an accepted transfer to such an actor leaves the case with no owner.

Who may be offered ownership of a case?

## Decision Drivers

- No actor receives case content before it is entitled to it, and while an embargo is active that means agreeing to the embargo first (CM-10-004).
- A transfer must end with exactly one participant holding `CASE_OWNER` (CM-21-001).
- Taking over a case requires the embargo negotiation that joining it requires, so the transfer should not run a second path around it.
- Keep the propose-then-execute shape ADR-0148 chose.

## Considered Options

- **A. Any actor the CASE_MANAGER can address.** The rule as written before this record.
- **B. Any listed participant.** The transferee must have a participant record on the case, whether or not it has joined.
- **C. A listed participant, offered without case content.** As B, with the Offer carrying the case by reference only, so an invitee that has not joined can be offered the case.
- **D. An active participant.** The transferee must be an active participant (CM-10-004) both when the owner proposes the transfer and when the transferee accepts it.

## Decision Outcome

Chosen option: **D. An active participant**, because it is the only option under which the Offer's case content goes only to an actor already entitled to it, and it reuses the entitlement rule the protocol already has rather than adding a new one.

1. **The CASE_MANAGER checks the proposal.**
   It admits an ownership-transfer proposal only when the transferee it names is an active participant of the case, other than the CASE_MANAGER and the proposer.
   Otherwise it refuses the proposal, makes no Offer and commits no ledger entry.
2. **The CASE_MANAGER checks again at Accept.**
   A participant can stop being active between the Offer and the answer: it can be removed, or lapse when an embargo revision comes into force that it has not agreed to.
   The CASE_MANAGER admits the transferee's `Accept` only if the transferee is still an active participant, and otherwise refuses it with no role change.
3. **The owner invites first.**
   To hand a case to an actor not yet in it, the owner invites that actor, and offers the case once the actor has joined and agreed to any active embargo.

### Consequences

- Good, because the transfer Offer carries case content only to an actor entitled to it, so the transfer path no longer leaks embargoed information.
- Good, because the transferee always has a participant record, so an accepted transfer always ends with one `CASE_OWNER`.
- Good, because the embargo negotiation happens once, through the invitation, before ownership is offered.
- Bad, because handing a case to an actor outside it now takes two steps, an invitation and then an Offer.
- Neutral, because the routing, the Offer's identity and the answer flow of ADR-0148 are unchanged; only the admission check on the transferee is narrowed.

## Validation

- A test delivers a proposal naming an actor off the roster, an invitee that has not joined, a removed participant and a lapsed participant, and asserts each is refused with no ledger entry and no Offer made.
- A test lets the transferee stop being active between the Offer and its `Accept`, and asserts the `Accept` is refused with no role change.
- A test asserts that no admitted `Accept` leaves the case with no participant holding `CASE_OWNER`.

## Pros and Cons of the Options

### A. Any actor the CASE_MANAGER can address

- Good, because an owner can hand a case to anyone in one step.
- Bad, because the Offer sends the embargo, the reports and the participant list to an actor that has agreed to nothing.
- Bad, because an actor with no participant record cannot hold `CASE_OWNER`, so an accepted transfer leaves the case with no owner.

### B. Any listed participant

- Good, because the transferee has a participant record, so the role can always be granted.
- Bad, because an invitee that has not joined is not entitled to case content, and the Offer still sends it the whole case.

### C. A listed participant, offered without case content

- Good, because an invitee could be offered the case before it joins without seeing case content.
- Bad, because the transfer and the embargo negotiation then run in parallel, and an accepted Offer from an actor that later declines the embargo has to be reconciled.
- Bad, because it changes the Offer's shape that ADR-0148 settled, for a step the invitation already provides.

### D. An active participant (chosen)

- Good, because it uses the existing entitlement rule (CM-10-004) and closes both gaps.
- Bad, because it adds a step for a transferee outside the case.

## More Information

Generated spec requirements: CM-21-021, and the transferee check in CM-21-005.
