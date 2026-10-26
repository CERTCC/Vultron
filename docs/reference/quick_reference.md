---
description: >
  A single-page summary of the protocol's state machines, message types, and
  how they interact.
stakeholder_type: [platform-developer]
level: 400
page_type: reference
---

# Protocol Quick Reference

{% include-markdown "../includes/not_normative.md" %}

This page is a single-stop summary of the Vultron Protocol's state
machines, message types, and their interactions. It is intended for
implementers who want a consolidated view before diving into the
detailed, normative pages.

The authoritative source for everything summarized here is the [Vultron Protocol Specification](vultron-spec/index.md), with the [Formal Protocol](formal_protocol/index.md) pages — [States](formal_protocol/states.md), [Messages](formal_protocol/messages.md), and [Transitions](formal_protocol/transitions.md) — carrying the formal treatment and the [protocol requirements](specs/protocol.md) the normative statements.
Where this page and any of those disagree, the specification wins.

## State Machines at a Glance

Every Participant tracks five state machines ([§13.2 Capability Sets](vultron-spec/conformance.md#132-capability-sets)).
Two of them, the vendor fix path (VFD) and the public state (PXA), together make up the Case State (CS), which the formal protocol pages write as one six-letter string.

| State Machine | Scope | States | Initial | Terminal |
| --- | --- | --- | --- | --- |
| **RM** — Report Management | Per Participant | Start (`S`), Received (`R`), Invalid (`I`), Valid (`V`), Deferred (`D`), Accepted (`A`), Closed (`C`) | `S` (Start) | `C` (Closed) |
| **EM** — Embargo Management | Per case | None (`N`), Proposed (`P`), Active (`A`), Revise (`R`), eXited (`X`) | `N` (None) | `X` (eXited) |
| **PEC** — Participant Embargo Consent | Per Participant, per embargo | Uninvited, Invited, Agreed, Declined, Timed out; *signatory* and *lapsed* are reads, not states | Uninvited | none; a row is frozen once its embargo's register entry is final |
| **VFD** — Vendor fix path (CS) | Per Participant | Three one-way binary substates in order `vfd`: Vendor aware (`v→V`), Fix ready (`f→F`), Fix deployed (`d→D`) | `vfd` | `VFD` |
| **PXA** — Public state (CS) | Per case | Three one-way binary substates in order `pxa`: Public aware (`p→P`), eXploit public (`x→X`), Attacks observed (`a→A`) | `pxa` | `PXA` |

The specification names the EM states *Revise* and *eXited* as *Revised* and *Exited* ([§7.1 States](vultron-spec/tracking-models.md#71-states)); the shorthand letters are the same.
PEC is specified in [§9 Participant Embargo Consent (PEC) State Machine](vultron-spec/tracking-models.md#9-participant-embargo-consent-pec-state-machine-n) and explained in the [Embargo Lifecycle](../topics/behavior_logic/use-cases/embargo-lifecycle.md).

!!! note "The formal protocol's triple"

    The [Formal Protocol](formal_protocol/index.md) pages model the RM, EM, and CS machines and write a Participant's state as the triple $S_i = (q^{rm}, q^{em}, q^{cs})$, where $q^{cs}$ is the six-letter CS string `vfdpxa` that combines VFD and PXA.
    PEC is not part of the triple.
    The triple is the form the transition tables below use.

!!! note "Reading CS states"

    Each CS substate is monotonic: it changes in one direction only
    (lowercase → uppercase) and never reverts. The full CS state is the
    combination of all six substates, always written in the order
    `vfdpxa`. A dot ($\cdot$) is a single-position wildcard — e.g.
    $Vfd\cdot\cdot\cdot$ matches any CS state whose Vendor-awareness
    substate is `V`, regardless of the public substates.

## Message Types at a Glance

### Occasion table

Each row of the [occasion table](messages/index.md) is a situation in a case, with the ActivityStreams 2.0 (AS2) activity that conveys it, whom to send it to, who may send it, and the section that documents it.
The table is generated from the semantic registry, the list of patterns that [semantic extraction](glossary.md#activity-wire-format) matches each inbound activity against.

{% include-markdown "./messages/_occasions/lookup.md" heading-offset=2 %}

### Formal message set

The formal message set is $M_{i,j} = M^{rm} \cup M^{em} \cup M^{cs} \cup M^{*}$, the union of the report management, embargo management, case state and general messages ([§4.13 Formal Message Set in the specification](vultron-spec/layers.md#413-formal-message-set)).
The table below lists each type with the wire activities that carry it, and is generated from the same registry as the occasion table.
The state transition that emits each type is on [Messages](formal_protocol/messages.md), and the response the formal protocol expects from a recipient is on [Transitions](formal_protocol/transitions.md).

{% include-markdown "./messages/_occasions/shorthands.md" %}

The formal set and the wire vocabulary are many-to-many ([Mapping status](messages/index.md#mapping-status)).
Several types share one wire activity, as `EP` and `EV` share `Invite(EmbargoEvent)`, and the occasion's section states what tells them apart.
A type whose row reads "none" has no wire activity of its own: [Faults and Acknowledgments](messages/faults_and_acknowledgements.md) describes the fault reporting and the cumulative hash-chain acknowledgment that replace such types.

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
| `{R,I,D,A}` | close ($c$) | `C` | `RC` |

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

All Participants share the same message vocabulary and the same five state machines; roles differ in where they start and which messages they typically originate.
The roles are defined in [§2.2 Roles in the specification](vultron-spec/introduction.md#22-roles); see [States](formal_protocol/states.md) for the per-role reachable state spaces and start states.
Finder is not a protocol role: an actor that discovers a vulnerability and reports it holds the Reporter role (ADR-0078).

| Role | RM start | Typically sends | Typically receives |
| --- | :---: | --- | --- |
| **Reporter** | `A` (Accepted) | `RS` (the initial report), embargo proposals (`EP`/`EV`), observations (`CP`/`CX`/`CA`) | `RK`, `CV`, RM status, embargo negotiation |
| **Vendor** | `S` (Start) | `CV` (own awareness), `CF` (fix ready), own RM status (`RV`/`RA`/`RC`…), embargo messages | `RS`, `RK`, embargo negotiation, CS updates |
| **Coordinator** | `S` (Start) | `RS` (forwarding reports), `GI`, embargo proposals, `CP` | reports and effectively any message type — a Coordinator facilitates across Participants |
| **Deployer** | `S` (Start) | `CD` (fix deployed), acknowledgments | `CV`, `CF`, `RS` |
| **Observer** | `S` (Start) | observations (`CP`/`CX`/`CA`), acknowledgments, embargo consent | every case-scoped message; an Observer tracks state but drives no VFD transition |

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

- **[Vultron Protocol Specification](vultron-spec/index.md)** — the normative definition of every state machine, message, and role summarized here.
- **[States](formal_protocol/states.md)** — full state definitions,
  reachable/unreachable states, and per-role state spaces.
- **[Messages](formal_protocol/messages.md)** — message-type
  definitions, descriptions, and the combined "Message Type Redux"
  table.
- **[Message Types](messages/index.md)** — the occasion table, from a situation in a case to the wire activity that conveys it.
- **[Transitions](formal_protocol/transitions.md)** — complete
  sender and receiver transition functions, including error handling
  and cross-model interactions.
- **[Protocol Summary](formal_protocol/conclusion.md)** — the formal
  protocol tuple pulled together.
- **[Protocol Specification](specs/protocol.md)** — the normative
  RMB/EMB/CSB requirements referenced throughout the transition tables.

{% include-markdown "../start/_paths/connect-your-tracker/reference__quick_reference.md" %}
