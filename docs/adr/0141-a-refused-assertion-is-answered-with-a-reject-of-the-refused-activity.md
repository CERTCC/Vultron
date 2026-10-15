---
status: accepted-provisional
date: 2026-10-15
created: 2026-10-15
updated: 2026-10-15
revision: 1
deciders: Allen D. Householder
consulted: >-
  Claude Opus 5.5; ADR-0067, ADR-0131; specs/case-ledger-processing.yaml
  CLP-02-005, CLP-05-001, CLP-10-022; specs/message-semantics-mapping.yaml
  MSM-05-001
informed: []
stakeholder_type: [project-contributor]
---

# A Refused Assertion Is Answered With a Reject of the Refused Activity

## Context and Problem Statement

CLP-02-005 requires the CASE_MANAGER to answer a refused assertion with a `Reject` directed at the asserting participant, and CLP-05-001 calls that `Reject` a refusal notice.
Neither says what the `Reject` carries, and no participant has a use case that reads one.

The reference implementation mostly refuses in silence (#4632).
No embargo received tree answers a refusal by its own precondition guards: a `Reject` of an embargo that is neither active nor open, a withdrawal (`Leave(EmbargoEvent)`) from a row that is not `AGREED`, and the owner's decision on an embargo that is not an open proposal all report `REFUSED` in the handler result and send nothing.
The trees that do answer use the RSH-06-004 gap `Note`, which MSM-05-001 reserves for a condition that needs narrative explanation, not for "received and understood but declined".
A sender that is refused never learns why, and the pending assertion it recorded stays open until it times out (CLP-06-004).

Two refusals already answer with a `Reject` of the refused activity: a refused embargo proposal gets `Reject(Invite(EmbargoEvent))`, which closes the proposer's pending entry (EP-09-008), and a declined owner close gets `Reject(Leave(VulnerabilityCase))` (CM-23-011).
Nothing on the participant side routes the second one: it matches no pattern.

ADR-0131 weighed a general `Reject` reply for traffic after `case_fully_closed` and set it aside, because a `Reject` that wraps an `Invite` or an `Offer` already means a decision on that request.
It left the door open for a later record if a reply to other traffic became a need.
Refusals before close are that need.

## Decision Drivers

- CLP-02-005 names a `Reject`, and MSM-05-001 reserves `Reject` for a message received and understood but declined.
- A refused sender should learn that it was refused, and why, and close its pending assertion.
- One shape, one emitter and one receiving use case for every refusal, not one per message (CS-22-001).
- No reply may be read as something it is not (ADR-0131).
- A refusal writes no state and enters no ledger (CLP-05-002, CLP-10-022).

## Considered Options

- **A — One refusal notice: `Reject` whose object is the refused activity.**
- **B — One `Reject` message type per refused activity**, each with its own pattern and receiving use case, as `Reject(Leave(VulnerabilityCase))` has.
- **C — A directed `Note`**, as the RM gap note is.

## Decision Outcome

Chosen option: **A**.

The refusal notice is a `Reject` whose object is the refused activity, inline, with `inReplyTo` naming that activity's id, addressed to the asserting participant alone, and with the refusing guard's reason in its `summary`.
Its id is derived from the CASE_MANAGER and the refused activity, so a resend under the same id is recognised as the same notice.
It is not a case event and is never ledgered (CLP-02-013 already lists it).

Every refusal by a precondition guard at the case's CASE_MANAGER sends one, through the received-tree factory's refusal stage (CLP-10-022).
A refusal by the sender guard does not: an unentitled sender is owed no answer (HP-01-006).
A guard failure that is an idempotent repeat, reported `SKIPPED`, does not either: the sender's earlier assertion already had its effect, and a `Reject` would contradict it.
Traffic after `case_fully_closed` keeps ADR-0131's policy; this record changes nothing there.

The receiving participant has one use case for the notice.
It closes the pending assertion it recorded for the refused activity and logs the reason at WARNING.
It writes no case state and does not retry (CLP-06-005).

When the refused activity is itself an `Invite` or an `Offer`, the notice has the same shape as a decline of that request, so the shape cannot tell them apart.
It does not need to: to the sender, a decline and a refusal of its request have the same consequence, which is that the request had no effect.
A `Reject` from the case's CASE_MANAGER of an `Invite` or an `Offer` the participant sent is read by the use case that already reads a decline of it, which closes the pending entry, as `Reject(Invite(EmbargoEvent))` does today (EP-09-008).
Every other wrapped activity is read by the one refusal-notice use case, `Reject(Leave(VulnerabilityCase))` included.

Option B was rejected: it needs a message type, a pattern and a receiving use case for every message that can be refused, and they would all do the same thing.
Option C was rejected: a `Note` is not the `Reject` CLP-02-005 names, and MSM-05-001 reserves it for a condition that needs narrative explanation.

### Consequences

- Good, because one emitter and one receiving use case serve every refused message, and a tree adds feedback by passing one node as a refusal effect.
- Good, because the sender closes its pending assertion at once instead of waiting for it to time out.
- Good, because a `Reject(Leave(VulnerabilityCase))` that a participant receives today as an unknown activity is routed.
- Bad, because the patterns must recognise a `Reject` of each wrapped verb, and they must stay ordered after every more specific `Reject` pattern so the notice never shadows an existing message.
- Bad, because the reason in `summary` is visible to the sender, so a guard's reason must name the sender's own standing and nothing undisclosable about other participants.
- Neutral, because a refusal before the tree runs, in a use case's `execute()`, is outside the refusal stage and sends no notice until that check moves into the tree.

## Validation

- A test of the received-tree factory confirms the refusal stage queues the notice on a precondition refusal at the CASE_MANAGER, and queues nothing on a sender-guard refusal, an idempotent skip, a redelivery, or at a replica.
- For each embargo received tree, a test drives each refusal reason and confirms the notice's object, `inReplyTo`, recipient and `summary`.
- A participant-side test confirms the notice closes the pending assertion for the refused activity and writes no case state.

## More Information

- ADR-0067 — the RM gap note, a `Note` answer to an RM anomaly; unchanged by this record.
- ADR-0131 — post-close traffic is dropped; this record covers refusals before close.
- #4632 — the concern this record answers.

Generated spec requirements: `case-ledger-processing.yaml` CLP-05-001 and CLP-10-022.
