---
stakeholder_type: [platform-developer]
level: 400
description: >
  Wire activities for the Report Management message types RS, RI, RV, RD, RA, RC, RK, and RE.
---

# Report Management (RM) Messages

The RM shorthands inform other Participants of the sender's report-handling
state. Receipt of a *Report Submission* is the only RM message whose receipt
directly triggers an RM state change in the receiver; all others convey the
sender's status.

The RM state ladder has **two** wire expressions: the dedicated report-scoped
activities listed below, and the `rm_state` field of an
`Add(ParticipantStatus)` broadcast (see [Case State (CS)](cs.md)). *Report/Case
Accepted* (`RA`) and *Report/Case Deferred* (`RD`) additionally take case-scoped
verbs — `Join(VulnerabilityCase)` and `Ignore(VulnerabilityCase)` — because
engaging or deferring is a case-participation decision rather than a
report-validity judgment (MSM-01-004, MSM-01-005).

The CASE_MANAGER applies one rule to an RM state whichever of these expressions carries it (RSH-06-006).
The state is recorded for the sender, never for the receiver (RSH-08-001), and only when the sender is a participant of the case.
A forward move is recorded even when it skips states, and the CASE_MANAGER then asks the sender in a note which path it took (RSH-06-001, RSH-06-004).
A backward move is refused and the recorded state stands (RSH-06-002), and the CASE_MANAGER tells the sender in a note that it refused the move (RSH-06-004).
An activity and an `Add(ParticipantStatus)` that report the same move record it once (RSH-08-002).

## Message mapping

```python exec="true" idprefix=""
from vultron.metadata.msm.render import render_page

# heading=False omits render_page's "## <model> Messages" heading so it does
# not duplicate this page's H1. The table is the #2998-rendered artifact.
print(render_page("rm", heading=False))
```

## Create Report

- **Protocol role:** A Participant mints a vulnerability report object. This
  wire activity has no formal shorthand; it precedes *Report Submission*.
- **Triggering transition:** none (object construction, not a state change).
- **Wire activity:** `Create(VulnerabilityReport)`.
- **How-to:** [How to Report a Vulnerability](../../howto/activitypub/activities/report_vulnerability.md).

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import create_report, json2md

print(json2md(create_report()))
```

## RS — Report Submission

- **Protocol role:** A message from one Participant to a new Participant
  containing a vulnerability report.
- **Triggering transition:** emitted when the sender is Accepted (sender ∈ A).
- **Wire activity:** `Offer(VulnerabilityReport)`.
- **Proposed embargo terms:** the Offer may carry `proposedEmbargo`, an inline `EmbargoEvent` whose `context` is the report; the case owner compares it with its own default at case creation and the shorter wins (EP-04-003, EP-04-004).
- **How-to:** [How to Report a Vulnerability](../../howto/activitypub/activities/report_vulnerability.md).
- **Formal definition:** [Message Types](../formal_protocol/messages.md#rm-message-types),
  [Transitions](../formal_protocol/transitions.md).

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import submit_report, json2md

print(json2md(submit_report()))
```

## RI — Report Invalid

- **Protocol role:** The Participant has designated the report as invalid.
- **Triggering transition:** Received → Invalid (R → I).
- **Wire activity:** `TentativeReject(Offer(VulnerabilityReport))`.
- **How-to:** [How to Report a Vulnerability](../../howto/activitypub/activities/report_vulnerability.md).
- **Formal definition:** [Message Types](../formal_protocol/messages.md#rm-message-types),
  [Transitions](../formal_protocol/transitions.md).

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import invalidate_report, json2md

print(json2md(invalidate_report()))
```

## RV — Report Valid

- **Protocol role:** The Participant has designated the report as valid.
- **Triggering transition:** Received or Invalid → Valid ({R,I} → V).
- **Wire activity:** `Accept(Offer(VulnerabilityReport))`.
- **How-to:** [How to Report a Vulnerability](../../howto/activitypub/activities/report_vulnerability.md).
- **Formal definition:** [Message Types](../formal_protocol/messages.md#rm-message-types),
  [Transitions](../formal_protocol/transitions.md).

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import validate_report, json2md

print(json2md(validate_report()))
```

## RD — Report/Case Deferred

- **Protocol role:** The Participant is deferring further action on a report.
- **Triggering transition:** Valid or Accepted → Deferred ({V,A} → D).
- **Wire activity:** `Ignore(VulnerabilityCase)` — a case-participation
  decision, not a report-validity judgment (MSM-01-004).
- **How-to:** [How to Advance a Case Through Report Management](../../howto/activitypub/activities/manage_case.md).
- **Formal definition:** [Message Types](../formal_protocol/messages.md#rm-message-types),
  [Transitions](../formal_protocol/transitions.md).

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import defer_case, json2md

print(json2md(defer_case()))
```

## RA — Report/Case Accepted

- **Protocol role:** The Participant has accepted the report for further action.
- **Triggering transition:** Valid or Deferred → Accepted ({V,D} → A).
- **Wire activity:** `Join(VulnerabilityCase)` — a case-participation decision,
  not a report-validity judgment (MSM-01-005).
- **How-to:** [How to Advance a Case Through Report Management](../../howto/activitypub/activities/manage_case.md).
- **Formal definition:** [Message Types](../formal_protocol/messages.md#rm-message-types),
  [Transitions](../formal_protocol/transitions.md).

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import engage_case, json2md

print(json2md(engage_case()))
```

Re-engaging a deferred case emits the same activity. There is no separate
re-engagement wire form, because `DEFERRED` → `ACCEPTED` is a forward transition
rather than a retraction of the earlier deferral.

## RC — Report Closed

- **Protocol role:** The Participant has closed the report.
- **Triggering transition:** Received, Invalid, Deferred, or Accepted → Closed
  ({R,I,D,A} → C).
- **Wire activity:** `Reject(Offer(VulnerabilityReport))`. This activity also
  appears as an ordinary refusal in the fault-and-acknowledgment mapping
  (MSM-05-003).
- **How-to:** [How to Report a Vulnerability](../../howto/activitypub/activities/report_vulnerability.md).
- **Formal definition:** [Message Types](../formal_protocol/messages.md#rm-message-types),
  [Transitions](../formal_protocol/transitions.md).

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import close_report, json2md

print(json2md(close_report()))
```

## RK — Report Acknowledgment

- **Protocol role:** Acknowledges receipt of an RM message.
- **Triggering transition:** any valid RM message.
- **Wire activity:** `Read(Offer(VulnerabilityReport))`. `RK` survives as a
  dedicated wire activity because report submission is not ledger-replicated
  (MSM-01-008). The `object` is the report's original `Offer`, not the report
  itself; a bare `Read(VulnerabilityReport)` matches no pattern.
- **How-to:** [How to Report a Vulnerability](../../howto/activitypub/activities/report_vulnerability.md).
- **Formal definition:** [Message Types](../formal_protocol/messages.md#rm-message-types).

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import read_report, json2md

print(json2md(read_report()))
```

## RE — Report Error

- **Protocol role:** Indicates a Participant received an unexpected RM message.
- **Triggering transition:** any unexpected RM message.
- **Wire activity:** none dedicated. Faults are conveyed by
  `Create(ProcessingFault)` (not understood), `as:Reject` (understood but
  declined), or `Create(Note)` (needing explanation), partitioned by failure
  mode rather than by state machine
  ([ADR-0083](../../adr/0083-formal-message-set-and-as2-vocabulary-are-different-shapes.md)).
- **Formal definition:** [Message Types](../formal_protocol/messages.md#rm-message-types).
