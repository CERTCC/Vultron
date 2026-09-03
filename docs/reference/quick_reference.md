# Protocol Quick Reference

{% include-markdown "../includes/not_normative.md" %}

This page is a single-stop summary of the Vultron Protocol's state
machines, message types, and their interactions. It is intended for
implementers who want a consolidated view before diving into the
detailed, normative pages.

The authoritative sources for everything summarized here are the
[Formal Protocol](formal_protocol/index.md) pages —
[States](formal_protocol/states.md),
[Messages](formal_protocol/messages.md), and
[Transitions](formal_protocol/transitions.md) — together with the
[Protocol Specification](specs/protocol.md). Where this page and a
formal page disagree, the formal page wins.

## State Machines at a Glance

A Participant's state is the triple
$S_i = (q^{cs}, q^{rm}, q^{em})$ — one state from each of the three
process models below.

| Process Model | States | Initial | Terminal |
| --- | --- | --- | --- |
| **RM** — Report Management | Start (`S`), Received (`R`), Invalid (`I`), Valid (`V`), Deferred (`D`), Accepted (`A`), Closed (`C`) | `S` (Start) | `C` (Closed) |
| **EM** — Embargo Management | None (`N`), Proposed (`P`), Active (`A`), Revise (`R`), eXited (`X`) | `N` (None) | `X` (eXited) |
| **CS** — Case State | Product of six one-way binary substates in order `vfdpxa`: Vendor aware (`v→V`), Fix ready (`f→F`), Fix deployed (`d→D`), Public aware (`p→P`), eXploit public (`x→X`), Attacks observed (`a→A`) | `vfdpxa` (all lowercase) | `VFDPXA` (all uppercase) |

!!! note "Reading CS states"

    Each CS substate is monotonic: it changes in one direction only
    (lowercase → uppercase) and never reverts. The full CS state is the
    combination of all six substates, always written in the order
    `vfdpxa`. A dot ($\cdot$) is a single-position wildcard — e.g.
    $Vfd\cdot\cdot\cdot$ matches any CS state whose Vendor-awareness
    substate is `V`, regardless of the public substates.

## Message Types at a Glance

The complete message set is
$M_{i,j} = M^{rm} \cup M^{em} \cup M^{cs} \cup M^{*}$ (28 types).
Every message is emitted by the Participant whose state changed; the
"Response Expected" column shows what the recipient is expected to send
back.

| Type | Name | Model | Trigger (emit when) | Response Expected |
| :---: | --- | :---: | --- | --- |
| `RS` | Report Submission | RM | Sender $\in$ Accepted (`A`) sends report to a new Participant | `RK` (+ `CV` if recipient is a Vendor) |
| `RI` | Report Invalid | RM | `R` $\xrightarrow{i}$ `I` | `RK` |
| `RV` | Report Valid | RM | `{R,I}` $\xrightarrow{v}$ `V` | `RK` |
| `RD` | Report Deferred | RM | `{V,A}` $\xrightarrow{d}$ `D` | `RK` |
| `RA` | Report Accepted | RM | `{V,D}` $\xrightarrow{a}$ `A` | `RK` |
| `RC` | Report Closed | RM | `{I,D,A}` $\xrightarrow{c}$ `C` | `RK` |
| `RK` | Report Acknowledgement | RM | Any valid RM message received | — |
| `RE` | Report Error | RM | Any unexpected RM message received | `RK` + `GI` |
| `EP` | Embargo Proposal | EM | `{N,P}` $\xrightarrow{p}$ `P` | `EK` (or `ER` if embargo not viable) |
| `ER` | Embargo Proposal Rejection | EM | `P` $\xrightarrow{r}$ `N` | `EK` |
| `EA` | Embargo Proposal Acceptance | EM | `P` $\xrightarrow{a}$ `A` | `EK` |
| `EV` | Embargo Revision Proposal | EM | `A` $\xrightarrow{p}$ `R` | `EK` (or `ET` if embargo not viable) |
| `EJ` | Embargo Revision Rejection | EM | `R` $\xrightarrow{r}$ `A` | `EK` |
| `EC` | Embargo Revision Acceptance | EM | `R` $\xrightarrow{a}$ `A` | `EK` |
| `ET` | Embargo Termination | EM | `{A,R}` $\xrightarrow{t}$ `X` | `EK` |
| `EK` | Embargo Acknowledgement | EM | Any valid EM message received | — |
| `EE` | Embargo Error | EM | Any unexpected EM message received | `EK` + `GI` |
| `CV` | Vendor Awareness | CS | $vfd\cdot\cdot\cdot \xrightarrow{\mathbf{V}} Vfd\cdot\cdot\cdot$ | `CK` |
| `CF` | Fix Readiness | CS | $Vfd\cdot\cdot\cdot \xrightarrow{\mathbf{F}} VFd\cdot\cdot\cdot$ | `CK` |
| `CD` | Fix Deployed | CS | $VFd\cdot\cdot\cdot \xrightarrow{\mathbf{D}} VFD\cdot\cdot\cdot$ | `CK` |
| `CP` | Public Awareness | CS | $\cdot\cdot\cdot p\cdot\cdot \xrightarrow{\mathbf{P}} \cdot\cdot\cdot P\cdot\cdot$ | `CK` |
| `CX` | Exploit Public | CS | $\cdot\cdot\cdot\cdot x\cdot \xrightarrow{\mathbf{X}} \cdot\cdot\cdot\cdot X\cdot$ | `CK` |
| `CA` | Attacks Observed | CS | $\cdot\cdot\cdot\cdot\cdot a \xrightarrow{\mathbf{A}} \cdot\cdot\cdot\cdot\cdot A$ | `CK` |
| `CK` | CS Acknowledgement | CS | Any valid CS message received | — |
| `CE` | CS Error | CS | Any unexpected CS message received | `CK` + `GI` |
| `GI` | General Inquiry | General | Any time (non-state-change information) | `GK` |
| `GK` | General Acknowledgement | General | Any valid GI message received | — |
| `GE` | General Error | General | Any unexpected GI message received | `GI` |

!!! note "AS2 wire-format collapse"

    The [ActivityStreams 2.0](../howto/activitypub/activities/index.md)
    wire format collapses the revision-negotiation messages: `EV` is
    sent as `EP`, `EC` is sent as `EA`, and `EJ` is sent as `ER`. The
    formal 28-type set above remains normative for protocol semantics;
    the collapse is an implementation detail of the current prototype.

## State Transition Summary

The tables below give the sender-side transitions — the state change a
Participant undergoes when it emits each message. Full sender **and**
receiver transition tables (including error and out-of-embargo cases)
are in [Transitions](formal_protocol/transitions.md).

### RM transitions

| From | Event | To | Message |
| :---: | :---: | :---: | :---: |
| `A` | (already accepted) | `A` | `RS` |
| `R` | invalid ($i$) | `I` | `RI` |
| `{R,I}` | valid ($v$) | `V` | `RV` |
| `{V,A}` | defer ($d$) | `D` | `RD` |
| `{V,D}` | accept ($a$) | `A` | `RA` |
| `{I,D,A}` | close ($c$) | `C` | `RC` |

### EM transitions

| From | Event | To | Message |
| :---: | :---: | :---: | :---: |
| `{N,P}` | propose ($p$) | `P` | `EP` |
| `P` | reject ($r$) | `N` | `ER` |
| `P` | accept ($a$) | `A` | `EA` |
| `A` | propose revision ($p$) | `R` | `EV` |
| `R` | reject revision ($r$) | `A` | `EJ` |
| `R` | accept revision ($a$) | `A` | `EC` |
| `{A,R}` | terminate ($t$) | `X` | `ET` |

### CS transitions

Each substate advances once, in the order shown, and never reverts.

| From | Event | To | Message |
| :---: | :---: | :---: | :---: |
| $vfd\cdot\cdot\cdot$ | Vendor aware ($\mathbf{V}$) | $Vfd\cdot\cdot\cdot$ | `CV` |
| $Vfd\cdot\cdot\cdot$ | Fix ready ($\mathbf{F}$) | $VFd\cdot\cdot\cdot$ | `CF` |
| $VFd\cdot\cdot\cdot$ | Fix deployed ($\mathbf{D}$) | $VFD\cdot\cdot\cdot$ | `CD` |
| $\cdot\cdot\cdot p\cdot\cdot$ | Public aware ($\mathbf{P}$) | $\cdot\cdot\cdot P\cdot\cdot$ | `CP` |
| $\cdot\cdot\cdot\cdot x\cdot$ | Exploit public ($\mathbf{X}$) | $\cdot\cdot\cdot\cdot X\cdot$ | `CX` |
| $\cdot\cdot\cdot\cdot\cdot a$ | Attacks observed ($\mathbf{A}$) | $\cdot\cdot\cdot\cdot\cdot A$ | `CA` |

!!! note "Cross-model interactions"

    Public/exploit/attack CS transitions can force an embargo to end: a
    Participant that learns the vulnerability or an exploit for it is
    public SHALL initiate embargo termination (`ET`), and a Participant
    that becomes aware of attacks SHOULD do so. Conversely, a
    Vendor receiving a report (`RS`) it did not previously know about
    transitions $vfd\cdot\cdot\cdot \xrightarrow{\mathbf{V}}
    Vfd\cdot\cdot\cdot$ and responds with both `RK` and `CV`. See
    [Transitions](formal_protocol/transitions.md) for the full set of
    coupled transitions.

## Actor Roles Summary

All Participants share the same message vocabulary and the same three
state machines; roles differ in where they start and which messages
they typically originate. See [States](formal_protocol/states.md) for
the per-role reachable state spaces and start states.

| Role | RM start | Typically sends | Typically receives |
| --- | :---: | --- | --- |
| **Finder / Reporter** | `A` (Accepted) | `RS` (the initial report), embargo proposals (`EP`/`EV`), observations (`CP`/`CX`/`CA`) | `RK`, `CV`, RM status, embargo negotiation |
| **Vendor** | `S` (Start) | `CV` (own awareness), `CF` (fix ready), own RM status (`RV`/`RA`/`RC`…), embargo messages | `RS`, `RK`, embargo negotiation, CS updates |
| **Coordinator** | `S` (Start) | `RS` (forwarding reports), `GI`, embargo proposals, `CP` | reports and effectively any message type — a Coordinator facilitates across Participants |
| **Deployer** | `S` (Start) | `CD` (fix deployed), acknowledgements | `CV`, `CF`, `RS` |

!!! note "Who may send what"

    - A Participant MUST be in RM Accepted (`A`) to send a report
      (`RS`) to someone else.
    - Vendor Awareness (`CV`) SHOULD be sent only by Participants with
      direct knowledge of the notification — the Participant who sent
      the report to the Vendor, or the Vendor itself on receipt.
    - `CF` (Fix Readiness) is usually sent by a Vendor and `CD` (Fix
      Deployed) usually by a Deployer, but the protocol does not forbid
      other Participants from relaying them.

## Where to Go Next

- **[States](formal_protocol/states.md)** — full state definitions,
  reachable/unreachable states, and per-role state spaces.
- **[Messages](formal_protocol/messages.md)** — message-type
  definitions, descriptions, and the combined "Message Type Redux"
  table.
- **[Transitions](formal_protocol/transitions.md)** — complete
  sender and receiver transition functions, including error handling
  and cross-model interactions.
- **[Protocol Summary](formal_protocol/conclusion.md)** — the formal
  protocol tuple pulled together.
- **[Protocol Specification](specs/protocol.md)** — the normative
  RMB/EMB/CSB requirements referenced throughout the transition tables.
