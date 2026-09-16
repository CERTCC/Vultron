## 6. Report Management (RM) State Machine [N]

!!! note "Behavioral Layer — §6 through §11"
    [§6](index.md#6-report-management-rm-state-machine-n)–[§11](index.md#11-participant-lifecycle-within-a-case-n) together specify the five state machines of the Vultron protocol:
    **RM** ([§6](index.md#6-report-management-rm-state-machine-n)), **EM** ([§7](index.md#7-embargo-management-em-state-machine-n)), **VFD and PXA** ([§8](index.md#8-case-state-cs-dimensions-n), together the CS dimension),
    and **PEC** ([§9](index.md#9-participant-embargo-consent-pec-state-machine-n)). Model interactions and cascade rules are in [§10](index.md#10-model-interactions-and-cascade-rules-n); the
    participant lifecycle is in [§11](index.md#11-participant-lifecycle-within-a-case-n).

    **On scope: PEC.** The original Vultron protocol design specified four state
    machines: RM, EM, VFD, and PXA. A fifth — the Participant Embargo Consent
    (PEC) machine — emerged during implementation when it became clear that the
    case-level EM state was insufficient to capture individual participant
    consent posture. PEC is fully normative; implementations that predate this
    specification should treat it as a required addition.

    **Two conventions apply throughout [§6](index.md#6-report-management-rm-state-machine-n)–[§11](index.md#11-participant-lifecycle-within-a-case-n):**

    - A participant maintains its own state **and** a model of other
      participants' states. Where a transition rule applies to one and not the
      other, this is stated explicitly ([§8.4](index.md#84-receiving-cs-messages-own-state-vs-model-of-others)).
    - Transitions listed without a named trigger are driven by the corresponding
      protocol message from [§4](index.md#4-semantic-layer-message-meanings-n).

### 6.1 States

{% include-markdown "./includes/_rm-states-table.md" %}

!!! info "See also"
    - [Report Management Process Model](../../topics/process_models/rm/index.md)

### 6.2 Transitions and Guards

| From | Message | To |
|---|---|---|
| `START` | receive `RS` | `RECEIVED` |
| `RECEIVED` | send `RI` | `INVALID` |
| `RECEIVED` | send `RV` | `VALID` |
| `INVALID` | send `RV` | `VALID` |
| `VALID` | send `RI` | `INVALID` |
| `VALID` | send `RA` | `ACCEPTED` |
| `VALID` | send `RD` | `DEFERRED` |
| `DEFERRED` | send `RA` | `ACCEPTED` |
| `DEFERRED` | send `RC` | `CLOSED` |
| `ACCEPTED` | send `RC` | `CLOSED` |
| Any | send `RC` | `CLOSED` |

!!! info "See also"
    - [RM Transitions Reference](../formal_protocol/transitions.md)

### 6.3 Per-Participant RM Tracking

Each participant tracks its own RM state independently; a participant is the
authority on its own RM state ([§5.4.1](index.md#541-single-writer-authority)).

`RM.RECEIVED` is the entry state for a participant joining a case, reached by
several paths:

- **Invited participant** — on `Accept(Invite)`. This records willingness to
  join and, where an embargo is active, consent to it. It does **not** constitute
  validation of the report: the invitee has seen only a case stub at that point.
- **Direct report recipient** — on receiving a report.
- **Case proposal recipient** — on receiving a `CaseProposal`.

The triage cycle (`RECEIVED → VALID | INVALID → ACCEPTED | DEFERRED`) is a
distinct subsequent step that the participant runs **after** the full case
replica has been delivered to it.

!!! note "`Accept(Invite)` does not mean `RM.ACCEPTED`"
    Two different protocol acts are easily conflated: *joining a case* and
    *accepting a report for action*. `Accept(Invite)` is the former. A
    participant cannot accept what it has not seen, and the CASE_MANAGER MUST NOT
    treat a participant as having committed to the case until it receives an RM
    status message from that participant confirming the transition.

    See [§9.7](index.md#97-gating-full-case-delivery) for why this matters to case delivery.

---
