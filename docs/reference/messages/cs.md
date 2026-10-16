---
stakeholder_type: [platform-developer]
level: 400
description: >
  Wire activities for the Case State message types CV, CF, CD, CP, CX, CA, CK, and CE.
---

# Case State (CS) Messages

The CS shorthands announce case-state events. Their wire vocabulary splits along
a scope boundary that the "case state" name obscures:

- **`V`, `F`, `D` are participant-scoped** — one per (actor × case). They ride
  `as_ParticipantStatus` (`vfState` and `dState`) on
  `Add(ParticipantStatus)[target=CaseParticipant]`.
- **`P`, `X`, `A` are case-scoped** — one per case. They ride
  the `pxaState` field of `as_CaseStatus` on `Add(CaseStatus)[target=VulnerabilityCase]`.

There are **no case-level `V`/`F`/`D` states**. A case-level status cannot
express *which* vendor became aware or ready, which is the purpose of the V/F/D
dimensions in multi-party CVD; those dimensions are always participant-specific
(ADR-0075). `vfState` and `dState` are absent for participants that are neither
Vendor nor Deployer.

The `Add` carries the new status object inline.
The protocol names one form for each: `Add(CaseStatus)` brings a case status into the case, and `Add(ParticipantStatus)` brings a participant status into the case ([ADR-0137](../../adr/0137-case-records-are-attached-by-one-message-never-created-first.md)).
A received `Create(CaseStatus)` or `Create(ParticipantStatus)` is not a protocol message, and an inbox refuses it and changes nothing (VAM-01-011).

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
  `Create(ProcessingFault)`, `as:Reject`, or `Create(Note)`, partitioned by
  failure mode
  ([ADR-0083](../../adr/0083-formal-message-set-and-as2-vocabulary-are-different-shapes.md)).
- **Formal definition:** [Message Types](../formal_protocol/messages.md#cs-message-types).
