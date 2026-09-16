## 4. Semantic Layer — Message Meanings [N]

This section defines what each protocol message *means*. It says nothing about how
a message is encoded; [§5](index.md#5-syntactic-layer-wire-format-n) specifies
that, and [§5.7](index.md#57-shorthand-to-wire-form-mapping) gives the mapping
between the two.

Messages are named by two-letter **shorthands**, grouped by the state machine they
concern: `R*` for report management, `E*` for embargo management, `C*` for case
state. A shorthand names a meaning, not a wire format. Several shorthands share one
wire form, so the mapping is not one-to-one in either direction.

Every message reports something that has already happened. A message does not
instruct its recipient to make a transition; it tells the recipient that the
sender has made one, or that the sender has observed something
([§3.1](index.md#31-coordination-model)).

Six of the message types the formal protocol defines have **no wire
representation** in this version. Each table below marks them, and
[§4.6](index.md#46-error-and-acknowledgement-messages) explains why they are
absent rather than merely unimplemented.

### 4.1 Report Management Messages

These eight messages concern one participant's handling of a report. Each reports a
change to the **sender's** report management state
([§6](index.md#6-report-management-rm-state-machine-n)).

| Shorthand | Name | Meaning | On the wire? |
|---|---|---|---|
| `RS` | Report Submission | The sender is sending a report to a new participant | yes |
| `RI` | Report Invalid | The sender assessed the report as invalid | yes |
| `RV` | Report Valid | The sender assessed the report as valid | yes |
| `RD` | Report Deferred | The sender is deferring further action | yes |
| `RA` | Report Accepted | The sender accepted the report for active work | yes |
| `RC` | Report Closed | The sender closed the report | yes |
| `RK` | Report Acknowledgement | The sender received the report submission | yes |
| `RE` | Report Error | The sender received an unexpected report message | **no** ([§4.6](index.md#46-error-and-acknowledgement-messages)) |

Only `RS` drives a state change in its **receiver**: receiving a report moves the
receiver to Received. The other seven tell the receiver something about the sender
and leave the receiver's own state alone.

!!! note "`RK` acknowledges the submission, not the reading"
    `RK` reports that the submission arrived. It does not report that the recipient
    has read the report, assessed it, or agreed to work on it — those are `RV`,
    `RI`, `RA` and `RD`.

    The protocol defines no message meaning "I have read the report". An
    implementation MUST NOT infer from `RK` that the recipient has examined the
    content, and MUST NOT treat `RK` as a substitute for a report management state
    message.

### 4.2 Embargo Management Messages

These nine messages negotiate the case's embargo
([§7](index.md#7-embargo-management-em-state-machine-n)). They fall into three
groups: proposing an embargo, revising one already in force, and ending one.

| Shorthand | Name | Meaning | On the wire? |
|---|---|---|---|
| `EP` | Embargo Proposal | The sender proposes embargo terms | yes |
| `ER` | Embargo Proposal Rejection | The sender rejects a proposal | yes |
| `EA` | Embargo Proposal Acceptance | The sender accepts a proposal | yes |
| `EV` | Embargo Revision Proposal | The sender proposes changing terms already in force | yes |
| `EJ` | Embargo Revision Rejection | The sender rejects a proposed revision | yes |
| `EC` | Embargo Revision Acceptance | The sender accepts a proposed revision | yes |
| `ET` | Embargo Termination | The sender ends the embargo, effective immediately | yes |
| `EK` | Embargo Acknowledgement | The sender received an embargo message | **no** ([§4.6](index.md#46-error-and-acknowledgement-messages)) |
| `EE` | Embargo Error | The sender received an unexpected embargo message | **no** ([§4.6](index.md#46-error-and-acknowledgement-messages)) |

The initial-proposal group (`EP`, `ER`, `EA`) and the revision group (`EV`, `EJ`,
`EC`) are distinct meanings. The distinction matters because the outcome of a
rejection differs: rejecting an initial proposal leaves the case with no embargo,
while rejecting a revision leaves the previously agreed terms in force
([§7.2](index.md#72-transitions-and-guards)).

!!! warning "The revision shorthands are indistinguishable on the wire"
    `EV`, `EJ` and `EC` share their wire forms with `EP`, `ER` and `EA`
    respectively. The distinction is not encoded in the message.

    An implementation MUST determine which it has received from its own embargo
    state. If the case embargo is Active or Revised, an arriving proposal is a
    revision. If it is None or Proposed, the same message is an initial proposal.

    An implementation that treats the wire form as self-describing will mishandle
    every revision. Because a mishandled revision rejection returns the case to
    None, it will silently drop embargoes that every participant still believes are
    in force.

**Choosing between `EV` and `ET`.** `ET` takes effect immediately. A sender that
wants the embargo to end at some future point SHOULD send `EV` proposing that end
date rather than `ET`.

Tacit acceptance of a receiver's default embargo policy is specified at
[§7.2](index.md#72-transitions-and-guards): submitting a report without proposing
terms accepts the receiver's default.

### 4.3 Case State Messages

These messages report facts about the vulnerability
([§8](index.md#8-case-state-cs-dimensions-n)). The first three concern what a
specific participant has done; the next three concern the state of the world.

| Shorthand | Name | Axis | Meaning | On the wire? |
|---|---|---|---|---|
| `CV` | Vendor Awareness | VFD | A vendor has been made aware of the vulnerability | yes |
| `CF` | Fix Readiness | VFD | A vendor has a fix ready | yes |
| `CD` | Fix Deployment | VFD | A fix has been deployed | yes |
| `CP` | Public Awareness | PXA | The vulnerability is publicly known | yes |
| `CX` | Exploit Public | PXA | An exploit has been published | yes |
| `CA` | Attacks Observed | PXA | Attacks exploiting the vulnerability have been seen | yes |
| `CK` | Case State Acknowledgement | — | The sender received a case state message | **no** ([§4.6](index.md#46-error-and-acknowledgement-messages)) |
| `CE` | Case State Error | — | The sender received an unexpected case state message | **no** ([§4.6](index.md#46-error-and-acknowledgement-messages)) |

All six reporting shorthands share a single wire form. Which fact is being reported
travels in the message's payload rather than in its type, so an implementation that
dispatches on message type alone cannot tell `CF` from `CA`
([§5.7](index.md#57-shorthand-to-wire-form-mapping)).

The three VFD messages report the sender's own progress, so receiving one updates
the receiver's model of the sender rather than the receiver's own state
([§8.4](index.md#84-receiving-cs-messages-own-state-vs-model-of-others)). The three
PXA messages report a claim about the world, which becomes canonical case state
only if the CASE_MANAGER adopts it
([§10.3](index.md#103-status-adoption-the-two-seam-model)).

### 4.4 Case Coordination Operations

Alongside the state machine messages, the protocol defines the operations that
create a case and manage who is in it. These have no two-letter shorthands, because
they concern the case as an object rather than any machine's state.

| Operation | Meaning |
|---|---|
| Case creation | An actor establishes a case for a vulnerability, and with it the case's authority chain ([§4.5](index.md#45-trust-and-bootstrap-semantics)) |
| Invitation | The CASE_MANAGER invites an actor to join, on the Case Owner's behalf; the actor accepts or declines ([§11.2](index.md#112-invitation-and-acceptance-n)) |
| Actor suggestion | A participant recommends that some actor be brought into the case; the Case Owner decides whether to invite it ([§11.2](index.md#112-invitation-and-acceptance-n)) |
| Role offer | The Case Owner offers a role to an actor, which accepts or declines ([§11.1](index.md#111-role-assignment-n)) |
| Ownership transfer | The Case Owner offers ownership of the case to another actor ([§11.3](index.md#113-case-ownership-transfer-n)) |
| Ledger replication | The CASE_MANAGER sends each committed ledger entry to every participant. This is the only way a participant learns of an accepted change to shared case state |
| Case delivery | The CASE_MANAGER sends a participant the full case, once that participant is admitted and its embargo consent is resolved ([§9.7](index.md#97-gating-full-case-delivery)) |
| Case metadata update | The CASE_MANAGER records a change to the case's own attributes |

The wire form of each is given at
[§5.3](index.md#53-activity-types-and-canonical-message-forms).

### 4.5 Trust and Bootstrap Semantics

A case begins before there is a case. The reporter's first message goes to a vendor
directly, because no case exists and so no CASE_MANAGER exists to route through.
Every later message routes through the CASE_MANAGER
([§5.4.2](index.md#542-routing-topology)). The transition between those two regimes
is the bootstrap, and it is where a case's trust is established.

**The case-creation message is the trust root.** When the receiving party creates
the case, it sends the reporter a case-creation message signed by the creating
actor. That message introduces the actor holding the `CASE_MANAGER` role. Every
participant's trust in the ledger derives from it: a participant accepts entries
from the CASE_MANAGER because it accepts the message that established which actor
holds the role.

**A late joiner inherits that trust transitively.** An actor invited after the case
is under way never sees the original creation message. It receives the case
snapshot and the prior ledger entries from the CASE_MANAGER
([§10.1](index.md#101-admitting-a-participant)), and it trusts them because it
trusts the invitation that named the CASE_MANAGER. The hash-chaining of the ledger
lets the joiner verify it received an unbroken history — a check against tampering
and omission, not a second source of trust.

**Messages that arrive before their case.** A case-scoped message may reach a
participant before the case it refers to has. A participant MUST NOT apply such a
message to a case it has not yet received. It holds the message until the case
arrives, and discards it if the case never does. Applying it early would create
case state from a message whose context was never established.

The threat model, identity verification, and the limits of this trust chain are
covered at [§14.1](index.md#141-trust-model).

### 4.6 Error and Acknowledgement Messages

The formal protocol defines an acknowledgement and an error message for each of the
three state machines: `RK`, `EK`, `CK` and `RE`, `EE`, `CE`. Their status here is
**not uniform**, and an implementation MUST NOT assume symmetry across the three.

Of the six, only `RK` exists on the wire. `EK`, `CK`, `RE`, `EE` and `CE` have no
wire representation. An implementation MUST NOT expect to receive any of the five,
and MUST NOT wait on one.

The two absences have different reasons.

**`EK` and `CK` are redundant.** Embargo and case state changes are replicated
through the case ledger, and a participant establishes that it received them by
holding an unbroken hash chain. A per-message acknowledgement would restate what
the chain already shows. `RK` survives because report submission happens before the
case exists, so there is no ledger to carry it.

**`RE`, `EE` and `CE` are deliberately unmodelled, not merely unimplemented.** The
protocol does not model inbound error messages typed by the state machine that
produced them, because that grouping tells a receiver nothing it can act on:
knowing *which* machine was confused does not indicate what to do about it. Errors
are grouped by **failure mode** instead, which is actionable:

| Failure mode | When it applies | What the sender can do |
|---|---|---|
| Not understood | The message could not be parsed, or its meaning is unrecognized | Re-send, or send a simpler equivalent |
| Understood but declined | The message was well-formed and meaningful, but the receiver will not act on it given the case's state | Reconsider; the state, not the message, is the obstacle |
| Needs explanation | The condition cannot be expressed as a structured message and requires prose | Read the explanation; there is no automatic recovery |

[§5.3](index.md#53-activity-types-and-canonical-message-forms) gives the wire form
of each failure mode.

**What is still missing.** A message that cannot be processed is currently set
aside for administrative attention, and its sender is not told. The three failure
modes give a receiver a way to report a problem where it is implemented, but this
version does not require it to.

{% include-markdown "./_oq-negative-ack.md" %}

### 4.7 Knowledge Model and Actor Isolation

Each participant knows only what it has been told. This subsection states what
follows from that, and it is the reason the wire format carries the inline-object
constraint of [§5.5](index.md#55-serialization).

**What a participant knows versus what is true.** A participant's replica reflects
the messages it has received. Two participants in the same case may hold different
views at the same moment, because a message is in transit or because a participant
has not yet reported a change. The protocol does not require every participant to
agree at every instant. It requires that each converge on the case's canonical
state as ledger entries reach it.

**No participant reads another's state.** An implementation MUST NOT read or write
another actor's state directly. Everything it knows about another participant MUST
be derived from a message that participant sent, or from the canonical ledger. This
is what makes a participant's knowledge independent of any other participant being
reachable.

!!! info "See also"
    - [Actor Knowledge Model](../../topics/actor-knowledge-model.md)
    - [ADR-0012: Per-Actor Data Layer Isolation](../../adr/0012-per-actor-datalayer-isolation.md)

---
