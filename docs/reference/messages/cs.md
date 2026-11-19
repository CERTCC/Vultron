---
stakeholder_type: [platform-developer]
level: 400
page_type: reference
subject: protocol
description: >
  Wire activities for the Case State message types CV, CF, CD, CP, CX, CA, CK, and CE.
---

# Case State (CS) Messages

The CS shorthands announce case-state events. Their wire vocabulary splits along
a scope boundary that the "case state" name obscures:

- **`V`, `F`, `D` are participant-scoped** — one per (actor × case). They ride
  `as_ParticipantStatus` (`vfState` and `dState`) on
  `Add(ParticipantStatus, target=<participant>/statuses)`.
- **`P`, `X`, `A` are case-scoped** — one per case, in the `pxaState` field of `as_CaseStatus`.
  A participant reports them in the case status its own `Add(ParticipantStatus, target=<participant>/statuses)` embeds.
  Only the CASE_MANAGER sends `Add(CaseStatus, target=<case>/statuses)`, to participants, as its record of the value it adopted, and a receiver refuses one from any other sender (RSH-04-001, RSH-04-005).

There are **no case-level `V`/`F`/`D` states**. A case-level status cannot
express *which* vendor became aware or ready, which is the purpose of the V/F/D
dimensions in multi-party CVD; those dimensions are always participant-specific
(ADR-0075). `vfState` and `dState` are absent for participants that are neither
Vendor nor Deployer.

The `Add` carries the new status object inline.
Its `target` is the status history the status joins, and its `context` is the case ([ADR-0204](../../adr/0204-the-case-ledger-and-status-histories-are-named-ordered-collections.md)).
Each participant's statuses are `<participant>/statuses`, and the case's are `<case>/statuses`.
Each history is an `OrderedCollection` that has an identity only: no route serves it.
A status is never updated, so the newest item in a history is the current status.
In the occasion tables, the history shows as `target=OrderedCollection` and the case as `context=VulnerabilityCase`.
The protocol names one form for each: `Add(CaseStatus)` brings a case status into the case, and `Add(ParticipantStatus)` brings a participant status into the case ([ADR-0137](../../adr/0137-case-records-are-attached-by-one-message-never-created-first.md)).
A received `Create(CaseStatus)` or `Create(ParticipantStatus)` is not a protocol message, and its receiver must not change the case file because of it (VAM-01-019).
This implementation's inbox refuses either one as an unrecognized activity and changes nothing (VAM-01-017).

## Occasions

{% include-markdown "./_occasions/lookup-cs.md" %}

{% include-markdown "./_occasions/sections/public-awareness.md" %}

- **Triggering transition:** p → P (case-scoped).

{% include-markdown "./_occasions/sections/exploit-public.md" %}

- **Triggering transition:** x → X (case-scoped).

{% include-markdown "./_occasions/sections/attacks-observed.md" %}

- **Triggering transition:** a → A (case-scoped).

{% include-markdown "./_occasions/sections/vendor-awareness.md" %}

- **Triggering transition:** vfd → Vfd (participant-scoped).
- **Sender:** a Participant with direct knowledge of the notification.

{% include-markdown "./_occasions/sections/fix-readiness.md" %}

- **Triggering transition:** Vfd → VFd (participant-scoped).

{% include-markdown "./_occasions/sections/fix-deployed.md" %}

- **Triggering transition:** VFd → VFD (participant-scoped, deployer path).

{% include-markdown "./_occasions/sections/participant-public-awareness.md" %}

- **Triggering transition:** p → P (case-scoped, reported in the sender's participant status).

{% include-markdown "./_occasions/sections/participant-exploit-public.md" %}

- **Triggering transition:** x → X (case-scoped, reported in the sender's participant status).

{% include-markdown "./_occasions/sections/participant-attacks-observed.md" %}

- **Triggering transition:** a → A (case-scoped, reported in the sender's participant status).

## Formal messages with no dedicated wire activity

### CK — CS Acknowledgment

- **Protocol role:** Acknowledges receipt of a CS message.
- **Triggering transition:** any valid CS message.
- **Wire activity:** none dedicated. Case-status changes are ledger-replicated,
  so acknowledgment is cumulative and implicit through hash-chain continuity
  ([ADR-0083](../../adr/0083-formal-message-set-and-as2-vocabulary-are-different-shapes.md)).
- **Formal definition:** [Message Types](../formal_protocol/messages.md#cs-message-types).

### CE — CS Error

- **Protocol role:** Indicates a Participant received an unexpected CS message.
- **Triggering transition:** any unexpected CS message.
- **Wire activity:** none dedicated. Faults are conveyed by
  `Create(ProcessingFault)`, `as:Reject`, or `Add(Note)`, partitioned by
  failure mode
  ([ADR-0083](../../adr/0083-formal-message-set-and-as2-vocabulary-are-different-shapes.md)).
- **Formal definition:** [Message Types](../formal_protocol/messages.md#cs-message-types).
