## 6. Report Management (RM) State Machine [N]

!!! note "Behavioral Layer — §6 through §11"
    [§6](index.md#6-report-management-rm-state-machine-n)–[§11](index.md#11-participant-lifecycle-within-a-case-n) together specify the five state machines of the Vultron protocol:
    **RM** ([§6](index.md#6-report-management-rm-state-machine-n)), **EM** ([§7](index.md#7-embargo-management-em-state-machine-n)), **VFD and PXA** ([§8](index.md#8-case-state-cs-dimensions-n), together the CS dimension),
    and **PEC** ([§9](index.md#9-participant-embargo-consent-pec-state-machine-n)). Model interactions and cascade rules are in [§10](index.md#10-model-interactions-and-cascade-rules-n); the
    participant lifecycle is in [§11](index.md#11-participant-lifecycle-within-a-case-n).

    **On scope: PEC.** The Participant Embargo Consent machine was not part of
    the original four-machine design. It is fully normative here; its provenance
    is recorded at its definition site
    ([§9](index.md#9-participant-embargo-consent-pec-state-machine-n)).

    **Two conventions apply throughout [§6](index.md#6-report-management-rm-state-machine-n)–[§11](index.md#11-participant-lifecycle-within-a-case-n):**

    - A participant maintains its own state **and** a model of other
      participants' states. Where a transition rule applies to one and not the
      other, this is stated explicitly ([§8.4](index.md#84-receiving-cs-messages-own-state-vs-model-of-others)).
    - Transitions listed without a named trigger are driven by the corresponding
      protocol message from [§4](index.md#4-semantic-layer-message-meanings-n).

### 6.1 States

Report Management tracks one report inside one participant, from the moment it
arrives to the moment that participant is finished with it. Every participant
runs its own RM machine and is the authority on its own value: two participants
working the same case are routinely at different RM states, and that is expected
rather than a disagreement to reconcile.

{% include-markdown "./includes/_rm-states-table.md" %}

The states divide into three groups. Start and Received precede any assessment.
Invalid and Valid record the outcome of triage. Deferred, Accepted and Closed
record what the participant decided to do about a report it considers valid —
except Invalid, which can also be closed directly.

!!! info "See also"
    - [Report Management Process Model](../../topics/process_models/rm/index.md)

### 6.2 Transitions and Guards

A participant drives its own RM transitions. Each transition below is a
participant-level state change: it records something that participant did, and it
does not change any other participant's RM state.

{% include-markdown "../../topics/process_models/rm/rm_state_machine_diagram.md" %}

| From | Trigger | Message | To |
|---|---|---|---|
| Start | receive | receipt of `RS` | Received |
| Received | validate | `RV` | Valid |
| Received | invalidate | `RI` | Invalid |
| Invalid | validate | `RV` | Valid |
| Valid | accept | `RA` | Accepted |
| Valid | defer | `RD` | Deferred |
| Deferred | accept | `RA` | Accepted |
| Accepted | defer | `RD` | Deferred |
| Invalid | close | `RC` | Closed |
| Deferred | close | `RC` | Closed |
| Accepted | close | `RC` | Closed |

These eleven transitions are the complete set. Three consequences are worth
stating, because each is a plausible assumption that does not hold:

- **A report cannot be closed from every state.** Only Invalid, Deferred and
  Accepted are closable. A participant at Start, Received or Valid MUST reach one
  of those states before it can close.
- **Valid does not return to Invalid.** Invalidation is available only from
  Received. Once a participant has assessed a report as valid it does not
  re-invalidate it; if it decides to stop work, it defers or closes.
- **Accepted and Deferred are mutually reachable.** A participant may defer work
  it had accepted and accept work it had deferred, without passing through Valid
  again.

!!! info "See also"
    - [RM Transitions Reference](../formal_protocol/transitions.md)

### 6.3 Per-Participant RM Tracking

Each participant tracks its own RM state independently; a participant is the
authority on its own RM state ([§5.4.1](index.md#541-single-writer-authority)).

Received is the entry state for a participant joining a case, reached by
several paths:

- **Invited participant** — on `Accept(Invite)`. This records willingness to
  join and, where an embargo is active, consent to it. It does **not** constitute
  validation of the report: the invitee has seen only a case stub at that point.
- **Direct report recipient** — on receiving a report.
- **Case proposal recipient** — on receiving a `CaseProposal`.

The triage cycle (`RECEIVED → VALID | INVALID → ACCEPTED | DEFERRED`) is a
distinct subsequent step that the participant runs **after** the full case
replica has been delivered to it.

!!! note "`Accept(Invite)` does not mean RM Accepted"
    Two different protocol acts are easily conflated: *joining a case* and
    *accepting a report for action*. `Accept(Invite)` is the former. A
    participant cannot accept what it has not seen, and the CASE_MANAGER MUST NOT
    treat a participant as having committed to the case until it receives an RM
    status message from that participant confirming the transition.

    See [§9.7](index.md#97-gating-full-case-delivery) for why this matters to case delivery.

---
