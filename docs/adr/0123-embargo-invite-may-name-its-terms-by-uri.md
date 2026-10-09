---
status: accepted-provisional
date: 2026-10-06
created: 2026-10-06
updated: 2026-10-06
revision: 1
deciders: Allen D. Householder
consulted: >-
  Claude Sonnet 5.5; specs/message-semantics-mapping.yaml MSM-05-001, MSM-05-003;
  specs/embargo-policy.yaml EP-09-010; specs/em-behavior.yaml EMB-01-002;
  ISSUE-4181, ISSUE-4140, ISSUE-4104
informed: []
stakeholder_type: [project-contributor]
---

# An Embargo Invite May Name Its Terms by URI

## Context and Problem Statement

A receiver whose case is public, exploited or attacked MUST answer an `Invite(EmbargoEvent)` with ER, a `Reject` of the Invite (EMB-01-002).
The ER factory required the whole Invite as the `Reject`'s object, and the Invite required an inline `EmbargoEvent`, which needs an `endTime` and a context.
An Invite that named its terms by bare URI, on a receiver that held no copy, therefore could not be answered.
The receiver logged a warning and sent nothing, and EMB-01-002's MUST was recorded as unachievable (ISSUE-4104, ISSUE-4181).

MSM-05-001 partitions faults by failure mode: `Create(ProcessingFault)` for a message received but not understood, and `as:Reject` for a message received, understood and declined.
A P/X/A refusal is the second kind, and it does not depend on the terms.

## Decision Outcome

`_EmProposeEmbargoActivity.object_` accepts the `EmbargoEvent` or its URI.
An Invite that names its terms by URI is answered with ER like any other: the `Reject` carries the Invite, and the Invite carries the URI.
The ER names the Invite by id and needs no terms.
The proposer, who holds the Invite it sent, correlates on that id.

The alternative was to leave that case unanswered and amend EMB-01-002 to exempt a receiver that holds no copy of the terms.
It was rejected because it leaves a protocol MUST unmet and lets a redelivery of the Invite be answered twice, since nothing records the decision.

### Consequences

- Any `Invite(EmbargoEvent)` now parses with its object as a URI, not only the one being refused.
  The receive tree still answers such an Invite only when it holds the terms (`CanAnswerEmbargoInviteNode`, ADR-0087), so accepting is unchanged.
- The refusal is recorded by the ER itself: its id derives from the rejecting actor and the Invite, so a redelivery finds it sent and is `SKIPPED` (HP-01-003).
  The ER is sealed before it is queued, so an ER sealed but no longer pending is queued again under its own id, and the receiver deduplicates it (ID-04-005).
- A shape violation (an Invite naming no `to` recipient or several, EP-09-010, or naming no embargo) is received but not understood, and is answered with `Create(ProcessingFault)` (MSM-05-001).
