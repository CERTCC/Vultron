---
source: CONCERN-5204
timestamp: '2026-10-28T16:00:29.280279+00:00'
title: A pre-bootstrap CASE_MANAGER message dropped after the 300 s window is never
  resent
type: learning
---

## Concern

This is a delay bound, not an arrival-order dependency, so it is outside SYNC-19. Two audit passes in #5102 found it independently.

A CASE_MANAGER message that reaches a replica before the case seed is queued for a bounded interval, 300 s by default (CBT-03-001, CBT-03-003, CBT-03-005), then dropped with a warning. CBT-03-003 says the receiver must "require a resend after bootstrap", but nothing resends:

- The CBT-03-004 `Question` asks only for the bootstrap `Create(VulnerabilityCase)`.
- A joiner relay `Invite(EmbargoEvent)` (EP-09-011), a reinstatement Invite (CM-31-013) or a full-case Invite that is dropped this way is never sent again.
- `inbox_pipeline.py` also drops an activity that finds its queue already expired, without queueing it.

Effect: the joiner never answers the Invite, its consent row times out and it lapses. The replica converges on the ledger, but the joiner lost a chance to consent that the protocol meant to give it.

## Question

Is a 300 s pre-seed delay an accepted bound, recorded as such? Or should a dropped pre-bootstrap message be resent once the seed lands, for example by the CASE_MANAGER re-relaying open proposals when the joiner's first position statement (SYNC-18) arrives?

Where: vultron/adapters/driving/fastapi/inbox_pipeline.py, CBT-03-003

**Resolved**: 2026-10-28 — implementation tracked in #5334, #5335.

Planning found the replay `Question` (CBT-03-004) has no handler on the
CASE_MANAGER and asks for `Create(VulnerabilityCase)`, which no longer delivers
a case copy (PCR-02-005). Decision (ADR-0163, proposed): the CASE_MANAGER
resends each Invite a participant owes an answer to (an embargo Invite whose
consent row is `INVITED` for an open proposal before its RSVP deadline, and the
full-case Invite until replied) whenever that participant states its ledger
position. A resend is the original sealed activity, rate-bounded per Invite and
participant with a doubling cooldown, and is not ledgered. A participant states
its position once its replica is seeded; the replay `Question` is removed.
CBT-03-003 no longer says "require a resend". A full-case Invite RSVP deadline
is a separate Idea, #5320.

Docs PR: <https://github.com/CERTCC/Vultron/pull/5333>.
