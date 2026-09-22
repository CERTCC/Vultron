# Case State (CS) Messages

The CS shorthands announce case-state events. Their wire vocabulary splits along
a scope boundary that the "case state" name obscures:

- **`V`, `F`, `D` are participant-scoped** — one per (actor × case). They ride
  `as_ParticipantStatus` (`vf_state` and `d_state`) on
  `Add(ParticipantStatus)[target=CaseParticipant]`.
- **`P`, `X`, `A` are case-scoped** — one per case. They ride
  `as_CaseStatus.pxa_state` on `Add(CaseStatus)[target=VulnerabilityCase]`.

There are **no case-level `V`/`F`/`D` states**. A case-level status cannot
express *which* vendor became aware or ready, which is the purpose of the V/F/D
dimensions in multi-party CVD; those dimensions are always participant-specific
(ADR-0075). `vf_state` and `d_state` are absent for participants that are neither
Vendor nor Deployer.

## Message mapping

```python exec="true" idprefix=""
from vultron.metadata.msm.render import render_page

# heading=False omits render_page's "## <model> Messages" heading so it does
# not duplicate this page's H1. The table is the #2998-rendered artifact.
print(render_page("cs", heading=False))
```

## Create Participant Status

- **Protocol role:** Mints a participant-status object carrying `vf_state`,
  `d_state`, and `rm_state`. No formal shorthand; it precedes the `Add`.
- **Triggering transition:** none (object construction).
- **Wire activity:** `Create(ParticipantStatus)`.
- **How-to:** [How to Post a Status Update or a Case Note](../../howto/activitypub/activities/status_updates.md).

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import create_participant_status, json2md

print(json2md(create_participant_status()))
```

## CV — Vendor Awareness

- **Protocol role:** Announces that a report has been delivered to a specific
  Vendor. Sent only by Participants with direct knowledge of the notification.
- **Triggering transition:** vfd → Vfd (participant-scoped).
- **Wire activity:** `Add(ParticipantStatus)[target=CaseParticipant]`.
- **Discriminator:** `vf_state`.
- **How-to:** [How to Post a Status Update or a Case Note](../../howto/activitypub/activities/status_updates.md).
- **Formal definition:** [Message Types](../formal_protocol/messages.md#cs-message-types),
  [Transitions](../formal_protocol/transitions.md).

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import add_status_to_participant, json2md

print(json2md(add_status_to_participant()))
```

## CF — Fix Readiness

- **Protocol role:** Announces that a specific Vendor has a fix ready.
- **Triggering transition:** Vfd → VFd (participant-scoped).
- **Wire activity:** `Add(ParticipantStatus)[target=CaseParticipant]`.
- **Discriminator:** `vf_state`.
- **How-to:** [How to Post a Status Update or a Case Note](../../howto/activitypub/activities/status_updates.md).
- **Formal definition:** [Message Types](../formal_protocol/messages.md#cs-message-types),
  [Transitions](../formal_protocol/transitions.md).

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import add_status_to_participant, json2md

print(json2md(add_status_to_participant()))
```

## CD — Fix Deployed

- **Protocol role:** Announces that a Deployer has completed fix deployment.
- **Triggering transition:** VFd → VFD (participant-scoped, deployer path).
- **Wire activity:** `Add(ParticipantStatus)[target=CaseParticipant]`.
- **Discriminator:** `d_state`.
- **How-to:** [How to Post a Status Update or a Case Note](../../howto/activitypub/activities/status_updates.md).
- **Formal definition:** [Message Types](../formal_protocol/messages.md#cs-message-types),
  [Transitions](../formal_protocol/transitions.md).

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import add_status_to_participant, json2md

print(json2md(add_status_to_participant()))
```

## Create Case Status

- **Protocol role:** Mints a case-status object carrying `em_state` and
  `pxa_state`. No formal shorthand; it precedes the `Add`.
- **Triggering transition:** none (object construction).
- **Wire activity:** `Create(CaseStatus)[context=VulnerabilityCase]`.
- **How-to:** [How to Post a Status Update or a Case Note](../../howto/activitypub/activities/status_updates.md).

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import create_case_status, json2md

print(json2md(create_case_status()))
```

## CP — Public Awareness

- **Protocol role:** Announces evidence that the vulnerability is known to the
  public.
- **Triggering transition:** p → P (case-scoped).
- **Wire activity:** `Add(CaseStatus)[target=VulnerabilityCase]`.
- **Discriminator:** `pxa_state`.
- **How-to:** [How to Post a Status Update or a Case Note](../../howto/activitypub/activities/status_updates.md).
- **Formal definition:** [Message Types](../formal_protocol/messages.md#cs-message-types),
  [Transitions](../formal_protocol/transitions.md).

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import add_status_to_case, json2md

print(json2md(add_status_to_case()))
```

## CX — Exploit Public

- **Protocol role:** Announces evidence that an exploit is publicly available.
- **Triggering transition:** x → X (case-scoped).
- **Wire activity:** `Add(CaseStatus)[target=VulnerabilityCase]`.
- **Discriminator:** `pxa_state`.
- **How-to:** [How to Post a Status Update or a Case Note](../../howto/activitypub/activities/status_updates.md).
- **Formal definition:** [Message Types](../formal_protocol/messages.md#cs-message-types),
  [Transitions](../formal_protocol/transitions.md).

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import add_status_to_case, json2md

print(json2md(add_status_to_case()))
```

## CA — Attacks Observed

- **Protocol role:** Announces evidence that attackers are exploiting the
  vulnerability.
- **Triggering transition:** a → A (case-scoped).
- **Wire activity:** `Add(CaseStatus)[target=VulnerabilityCase]`.
- **Discriminator:** `pxa_state`.
- **How-to:** [How to Post a Status Update or a Case Note](../../howto/activitypub/activities/status_updates.md).
- **Formal definition:** [Message Types](../formal_protocol/messages.md#cs-message-types),
  [Transitions](../formal_protocol/transitions.md).

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import add_status_to_case, json2md

print(json2md(add_status_to_case()))
```

## CK — CS Acknowledgement

- **Protocol role:** Acknowledges receipt of a CS message.
- **Triggering transition:** any valid CS message.
- **Wire activity:** none dedicated. Case-status changes are ledger-replicated,
  so acknowledgement is cumulative and implicit through hash-chain continuity
  ([ADR-0083](../../adr/0083-formal-message-set-and-as2-vocabulary-are-different-shapes.md)).
- **Formal definition:** [Message Types](../formal_protocol/messages.md#cs-message-types).

## CE — CS Error

- **Protocol role:** Indicates a Participant received an unexpected CS message.
- **Triggering transition:** any unexpected CS message.
- **Wire activity:** none dedicated. Faults are conveyed by
  `Create(ProcessingFault)`, `as:Reject`, or `Create(Note)`, partitioned by
  failure mode
  ([ADR-0083](../../adr/0083-formal-message-set-and-as2-vocabulary-are-different-shapes.md)).
- **Formal definition:** [Message Types](../formal_protocol/messages.md#cs-message-types).
