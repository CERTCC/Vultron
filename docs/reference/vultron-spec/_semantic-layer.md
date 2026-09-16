## 4. Semantic Layer — Message Meanings [N]

Protocol messages are referred to by two-letter shorthands throughout this
specification. The shorthand names a *protocol meaning*; [§4.7](index.md#47-shorthand-wire-form-mapping) maps each
shorthand to its AS2 wire form.

!!! note "Error and acknowledgement messages: read §4.6 first"
    Several messages below are part of the formal protocol definition but have
    **no wire representation** in the current semantic registry. [§4.6](index.md#46-error-and-acknowledgement-messages) states
    which, and why. Implementers should read that subsection before treating any
    `*E` or `*K` shorthand as dispatchable.

### 4.1 Report Management Messages

$M^{rm} = \{RS, RI, RV, RD, RA, RC, RK, RE\}$

| Shorthand | Name | Meaning |
|---|---|---|
| `RS` | Report Submission | A report is sent to a new participant |
| `RI` | Report Invalid | Sender has designated the report invalid |
| `RV` | Report Valid | Sender has designated the report valid |
| `RD` | Report Deferred | Sender is deferring further action |
| `RA` | Report Accepted | Sender has accepted the report for further action |
| `RC` | Report Closed | Sender has closed the report |
| `RK` | Report Acknowledgement | Acknowledges receipt of any RM message above |
| `RE` | Report Error | Sender received an unexpected RM message (see [§4.6](index.md#46-error-and-acknowledgement-messages)) |

All RM state changes are reported from the **sender's** perspective, not the
recipient's. `RS` is the only RM message whose *receipt* directly drives an RM
state change in the receiver; the rest inform the receiver about the sender.

Unlike the other acknowledgement shorthands, `RK` **is** a dispatchable message:
it maps to `MessageSemantics.ACK_REPORT` with wire form
`Read(Offer(VulnerabilityReport))`.

### 4.2 Embargo Management Messages

$M^{em} = \{EP, ER, EA, EV, EJ, EC, ET, EK, EE\}$

Nine messages, in three related groups. The initial-proposal shorthands and the revision shorthands are distinct:

| Shorthand | Name | Meaning |
|---|---|---|
| `EP` | Embargo Proposal | Proposed embargo terms |
| `ER` | Embargo Proposal **Rejection** | Sender rejected an embargo proposal |
| `EA` | Embargo Proposal Acceptance | Sender accepted an embargo proposal |
| `EV` | Embargo **Revision** Proposal | Proposed revision to existing terms |
| `EJ` | Embargo **Revision** Rejection | Sender rejected a proposed revision |
| `EC` | Embargo **Revision** Acceptance | Sender accepted a proposed revision |
| `ET` | Embargo Termination | Sender terminated the embargo; immediate effect |
| `EK` | Embargo Acknowledgement | Acknowledges any EM message above (see [§4.6](index.md#46-error-and-acknowledgement-messages)) |
| `EE` | Embargo Error | Sender received an unexpected EM message (see [§4.6](index.md#46-error-and-acknowledgement-messages)) |

!!! warning "`EV`/`EJ`/`EC` are wire-identical to `EP`/`ER`/`EA`"
    The revision shorthands share their AS2 wire forms with their
    initial-proposal counterparts. The distinction is **not** encoded in the
    activity structure.

    An implementation MUST infer revision-versus-initial context from **local EM
    state**: a proposal arriving while EM is `ACTIVE` or `REVISE` is a revision
    (`EV`); the same wire message arriving while EM is `NONE` or `PROPOSED` is an
    initial proposal (`EP`).

    This is a genuine interoperability hazard. An implementation that treats the
    wire form as self-describing will mis-handle every revision.

If early termination is desired but the termination time is in the future, that
SHOULD be expressed as an `EV` (revision proposal) rather than an `ET`, since
`ET` takes immediate effect.

Tacit acceptance semantics are specified in [§7.2](index.md#72-transitions-and-guards).

### 4.3 Case State Messages

$M^{cs} = \{CV, CF, CD, CP, CX, CA, CK, CE\}$

| Shorthand | Name | CS axis | Meaning |
|---|---|---|---|
| `CV` | Vendor Awareness | VFD (`v→V`) | A report has been delivered to a specific Vendor |
| `CF` | Fix Readiness | VFD (`f→F`) | A specific Vendor has a fix ready |
| `CD` | Fix Deployment | VFD (`d→D`) | A fix has been deployed |
| `CP` | Public Awareness | PXA (`p→P`) | The vulnerability is publicly known |
| `CX` | Exploit Public | PXA (`x→X`) | An exploit has been published |
| `CA` | Attacks Observed | PXA (`a→A`) | Attacks exploiting the vulnerability are observed |
| `CK` | CS Acknowledgement | — | Acknowledges any CS message above (see [§4.6](index.md#46-error-and-acknowledgement-messages)) |
| `CE` | CS Error | — | Sender received an unexpected CS message (see [§4.6](index.md#46-error-and-acknowledgement-messages)) |

All six status shorthands (`CV`–`CA`) share a single wire form and semantic:
`Add(CaseStatus)[target=VulnerabilityCase]` →
`MessageSemantics.ADD_CASE_STATUS_TO_CASE`. **The specific transition is encoded
in the object payload, not in the activity type.** An implementation dispatching
on activity type alone cannot distinguish `CF` from `CA`.

Receiving a CS message updates the receiver's model of the **sender's** CS state;
it does not change the receiver's own CS state. See [§8.4](index.md#84-receiving-cs-messages-own-state-vs-model-of-others).

### 4.4 Case Coordination Messages

- `Create(VulnerabilityCase)` — case initiation
- `Invite[target=VulnerabilityCase]` / `Accept(Invite)` / `Reject(Invite)` —
  invitation lifecycle (the CASE_MANAGER invites on the Case Owner's behalf)
- `Offer(CaseParticipant)` / `Accept(Offer(...))` / `Reject(Offer(...))` —
  suggest-actor lifecycle (a participant proposes an actor; see [§5.3](index.md#53-activity-types-and-canonical-message-forms))
- `Announce(CaseLedgerEntry)` — canonical state replication and broadcast
- `Announce(VulnerabilityCase)` — full case snapshot delivery to a participant
- `Update(VulnerabilityCase)` — case metadata change

### 4.5 Trust and Bootstrap Semantics

- Creator-signed `Create(VulnerabilityCase)` as the trust root
- Late-joiner invite path and trust establishment
- Pre-bootstrap message queuing

### 4.6 Error and Acknowledgement Messages

The formal protocol definition includes acknowledgement (`RK`, `EK`, `CK`) and
error (`RE`, `EE`, `CE`) message types for each state model. Their status in this
specification is **not uniform**, and implementers must not assume symmetry.

| Shorthand | Dispatchable? | Notes |
|---|---|---|
| `RK` | **Yes** | `MessageSemantics.ACK_REPORT`; wire form `Read(Offer(VulnerabilityReport))` |
| `EK`, `CK` | No | No `MessageSemantics` value; no entry in `SEMANTIC_REGISTRY` |
| `RE`, `EE`, `CE` | No | No `MessageSemantics` value; no wire representation |

**Error message types are deliberately unmodeled, not merely unimplemented.**
The decision (ADR-0049) is that the protocol core does not model inbound error
message types at all. Error signaling is instead handled through a three-way
fault partition (ADR-0083):

| Fault kind | Wire form | When to use |
|---|---|---|
| Received and not understood | `Create(ProcessingFault)` | An inbound message could not be parsed or its semantics are unrecognized |
| Understood but declined | `as:Reject` | An inbound message was valid but the receiver will not act on it |
| Narrative explanation needed | `Create(Note)` / `Add(Note → Case)` | A condition requiring prose description cannot be expressed as a structured message |

**Rationale.** The three-way partition groups errors by *failure mode* — which is
actionable to a receiver — rather than by originating state machine (`RE`/`EE`/`CE`),
which is not. A receiver that knows a message was not-understood can re-send or
simplify; knowing *which* state machine was confused does not add information.
`RK` survives as a real wire activity because report submission is not
ledger-replicated; `EK` and `CK` are redundant because ledger acknowledgement
is implicit via hash-chain continuity.

Consequences for implementers:

- An implementation MUST NOT expect to receive `RE`, `EE`, `CE`, `EK`, or `CK`
  as dispatchable protocol messages.
- Unprocessable inbound messages are currently dead-lettered with no sender
  notification. Whether the protocol should define a negative-acknowledgement
  facet is an open question.

{% include-markdown "./_oq-negative-ack.md" %}

### 4.7 Shorthand → Wire Form Mapping

Normative mapping from protocol shorthand through dispatch semantic to AS2 wire
form. Where a wire form is shared by several shorthands, disambiguation is by
local state or object payload as noted.

| Shorthand | `MessageSemantics` | AS2 wire form |
|---|---|---|
| `RS` | `SUBMIT_REPORT` | `Offer(VulnerabilityReport)` |
| `RI` | `INVALIDATE_REPORT` | `TentativeReject(Offer(VulnerabilityReport))` |
| `RV` | `VALIDATE_REPORT` | `Accept(Offer(VulnerabilityReport))` |
| `RD` | `DEFER_CASE` | `Ignore(VulnerabilityCase)` |
| `RA` | `ENGAGE_CASE` | `Join(VulnerabilityCase)` |
| `RC` | `CLOSE_REPORT` | `Reject(Offer(VulnerabilityReport))` |
| `RK` | `ACK_REPORT` | `Read(Offer(VulnerabilityReport))` |
| `EP`, `EV` | `INVITE_TO_EMBARGO_ON_CASE` | `Invite(Event)[context=VulnerabilityCase]` |
| `EA`, `EC` | `ACCEPT_INVITE_TO_EMBARGO_ON_CASE` | `Accept(Invite(Event)[context=VulnerabilityCase])` |
| `ER`, `EJ` | `REJECT_INVITE_TO_EMBARGO_ON_CASE` | `Reject(Invite(Event)[context=VulnerabilityCase])` |
| `ET` | `REMOVE_EMBARGO_EVENT_FROM_CASE` | `Remove(Event)` |
| `CV`–`CA` | `ADD_CASE_STATUS_TO_CASE` | `Add(CaseStatus)[target=VulnerabilityCase]` |
| `RE`, `EE`, `CE`, `EK`, `CK` | *(none — see [§4.6](index.md#46-error-and-acknowledgement-messages))* | *(none)* |

Two collision classes exist: embargo revision shorthands collide with their
initial-proposal counterparts (resolve via local EM state, [§4.2](index.md#42-embargo-management-messages)), and all six CS
status shorthands collide (resolve via `CaseStatus` payload, [§4.3](index.md#43-case-state-messages)).

### 4.8 Knowledge Model and Actor Isolation

Each actor maintains its own replica of case state. This isolation is
architectural (ADR-0012), not incidental.

**Full inline object rule.** An actor MUST include the full object inline in
every activity it emits. Cross-actor object references by ID are not permitted.
This rule prevents the state of one actor's knowledge from depending on another
actor's availability, and it is the basis for the actor-local consistency model.

**What an actor knows vs. what is globally true.** An actor's replica reflects
the messages it has received. Two actors in the same case may have different
views of case state at the same moment — because a message is in transit, or
because a participant has not yet reported a state change. The protocol does
not require instantaneous global consistency; it requires that each actor
converge on the canonical state as it receives `Announce(CaseLedgerEntry)`
messages from the CASE_MANAGER.

**Actor isolation as a conformance requirement.** An implementation MUST NOT
read or write another actor's state directly. All knowledge of another actor's
state MUST be inferred from messages received from that actor or from the
canonical ledger.

!!! info "See also"
    - [Actor Knowledge Model](../../topics/actor-knowledge-model.md)
    - [ADR-0012: Per-Actor Data Layer Isolation](../../adr/0012-per-actor-datalayer-isolation.md)

---
