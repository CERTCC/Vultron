## 6. Report Management (RM) State Machine [N]

Report Management is the first of the five state machines, and every case starts with it.
Before there is an embargo to negotiate or a fix to track, a participant receives a report and decides what to do with it.
This section specifies the states of that decision and the transitions between them.

!!! note "Behavioral Layer — §6 through §12"
    [§6 Report Management (RM) State Machine](tracking-models.md#6-report-management-rm-state-machine-n) through [§12 Participant Lifecycle Within a Case](interactions.md#12-participant-lifecycle-within-a-case-n) together specify the five state machines of the Vultron protocol:
    **RM** ([§6 Report Management (RM) State Machine](tracking-models.md#6-report-management-rm-state-machine-n)), **EM** ([§7 Embargo Management (EM) State Machine](tracking-models.md#7-embargo-management-em-state-machine-n)), **VFD and PXA** ([§8 Case State (CS) Dimensions](tracking-models.md#8-case-state-cs-dimensions-n), together the CS dimension), and **PEC** ([§9 Participant Embargo Consent (PEC) State Machine](tracking-models.md#9-participant-embargo-consent-pec-state-machine-n)).
    How the CASE_MANAGER coordinates a case is in [§10 Case Coordination](interactions.md#10-case-coordination-n).
    Model interactions and cascade rules are in [§11 Model Interactions and Cascade Rules](interactions.md#11-model-interactions-and-cascade-rules-n).
    The participant lifecycle is in [§12 Participant Lifecycle Within a Case](interactions.md#12-participant-lifecycle-within-a-case-n).

    **On scope: PEC.** The Participant Embargo Consent machine was not part of the original four-machine design.
    It is fully normative here.
    Its definition site records its provenance ([§9 Participant Embargo Consent (PEC) State Machine](tracking-models.md#9-participant-embargo-consent-pec-state-machine-n)).

    **Two conventions apply throughout [§6 Report Management (RM) State Machine](tracking-models.md#6-report-management-rm-state-machine-n) through [§12 Participant Lifecycle Within a Case](interactions.md#12-participant-lifecycle-within-a-case-n):**

    - A participant maintains its own state **and** a model of the states of other participants.
      Where a transition rule applies to only one of the two, the rule says so explicitly ([§8.4 Receiving CS Messages: Own State vs. Model of Others](tracking-models.md#84-receiving-cs-messages-own-state-vs-model-of-others)).
    - For a transition listed without a named trigger, the corresponding protocol message from [§4 Messages](layers.md#4-messages-n) drives it.

### 6.1 States

Report Management tracks one report inside one participant, from the moment the report arrives until that participant is finished with it.
Every participant runs its own RM machine and is the authority on its own value.
Two participants that work on the same case are often at different RM states.
This difference is expected, and it is not a disagreement to reconcile.

{% include-markdown "./includes/_rm-states-table.md" %}

The states divide into three groups.
Start and Received come before any assessment.
Invalid and Valid record the outcome of triage.
Deferred, Accepted and Closed record what the participant decided to do about a report that it considers valid.
The exception is that a participant can also close a report directly from Received or Invalid.

!!! info "See also"
    - [Report Management Process Model](../../topics/process_models/rm/index.md)

### 6.2 Transitions and Guards

A participant drives its own RM transitions.
Each transition below is a participant-level state change.
It records an action of that participant, and it does not change the RM state of any other participant.

{% include-markdown "../../topics/process_models/rm/rm_state_machine_diagram.md" %}

| From | Trigger | Message | To |
|---|---|---|---|
| Start | receive | receipt of `RS` | Received |
| Received | validate | `RV` | Valid |
| Received | invalidate | `RI` | Invalid |
| Received | close | `RC` | Closed |
| Invalid | validate | `RV` | Valid |
| Valid | accept | `RA` | Accepted |
| Valid | defer | `RD` | Deferred |
| Deferred | accept | `RA` | Accepted |
| Accepted | defer | `RD` | Deferred |
| Invalid | close | `RC` | Closed |
| Deferred | close | `RC` | Closed |
| Accepted | close | `RC` | Closed |

These twelve transitions are the complete set.
Three consequences follow.
Each one corrects a plausible assumption that is not true:

- **A report cannot be closed from every state.** Only Received, Invalid, Deferred and Accepted are closable.
  A participant at Start or Valid has to reach one of those states before it can close.
  A `Reject` sent from Received is the Received → Closed transition, and a participant at Valid that leaves a case is recorded as Valid → Deferred → Closed.

- **Valid does not return to Invalid.** Invalidation is available only from Received.
  When a participant has assessed a report as valid, it does not invalidate it again.
  If the participant decides to stop work, it defers or closes.

- **Accepted and Deferred are mutually reachable.** A participant can defer work it had accepted and accept work it had deferred, without passing through Valid again.

Closed has no transition out of it.
A participant that expects to resume work on a report defers it instead of closing it.

```python exec="true" idprefix=""
from vultron.metadata.specs.docs_render import requirement_callout; print(requirement_callout("RMB-14-004", "RMB-14-005", "RMB-14-006", "RMB-14-007", "VP-02-004"))
```

!!! info "See also"
    - [RM Transitions Reference](../formal_protocol/transitions.md)

### 6.3 Per-Participant RM Tracking

Each participant tracks its own RM state independently.
A participant is the authority on its own RM state ([§10.1 Single-Writer Authority](interactions.md#101-single-writer-authority)).
A receiver that processes an RM transition records it on the sender's participant record, never on its own.

```python exec="true" idprefix=""
from vultron.metadata.specs.docs_render import requirement_callout; print(requirement_callout("CM-01-002", "CM-03-002", "CM-04-001"))
```

Received is the entry state for a participant in a case.
A participant reaches it by several paths:

- **Invited participant** — the CASE_MANAGER creates an inert participant record at RM Received when it sends the stub `Invite`.
- **Direct report recipient** — on receiving a report.
- **Case proposal recipient** — on receiving a `CaseProposal`.

An invited participant answers the stub `Invite` before it has seen more than a case stub.
`Accept(Invite)` activates the inert record, recording willingness to join and, where an embargo is active, consent to it.
RM stays at Received.
`Reject(Invite)` closes the record (RM Received → Closed) and retains it as history.
Neither answer is a validation of the report.

```python exec="true" idprefix=""
from vultron.metadata.specs.docs_render import requirement_callout; print(requirement_callout("CM-11-006", "CM-11-001", "CM-11-007"))
```

After the participant joins, the CASE_MANAGER sends the case and the ledger.
It then sends a second Invite, the full-case Invite, which carries the ledger position of the CASE_MANAGER as a floor.
The participant judges the case when it answers this Invite with its own ledger position.
The answer is `Accept` (RV, Received → Valid), `TentativeReject` (RI, Received → Invalid) or `Reject` (RC, Received → Closed).
A reply behind the floor, or naming a ledger entry the CASE_MANAGER does not hold, is refused.

```python exec="true" idprefix=""
from vultron.metadata.specs.docs_render import requirement_callout; print(requirement_callout("CM-11-010", "CM-11-011", "CM-11-012"))
```

The triage cycle (`RECEIVED → VALID | INVALID → ACCEPTED | DEFERRED`) is a different, later step.
The participant runs it **after** it receives the full case replica.

!!! note "Two Invites, two different acts"
    *Joining a case* and *judging a case* are different protocol acts, and each has its own Invite.
    The stub Invite asks whether the actor will join.
    `Accept(Invite)` joins the case and consents to the embargo, and leaves RM at Received.

    The full-case Invite asks whether the case is valid.
    Its `Accept` is RV (Received → Valid), and only a later `Join(VulnerabilityCase)` reaches RM Accepted.
    A participant cannot accept what it has not seen, so the CASE_MANAGER does not treat a participant as having committed to the case until that participant sends `Join(VulnerabilityCase)`.

    See [§9.7 Gating Full Case Delivery](tracking-models.md#97-gating-full-case-delivery) for why this matters to case delivery.

```python exec="true" idprefix=""
from vultron.metadata.specs.docs_render import requirement_callout; print(requirement_callout("CM-11-002", "CM-11-004"))
```

---
