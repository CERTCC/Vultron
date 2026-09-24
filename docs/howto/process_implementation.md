---
description: >
  Integrate the Report Management (RM), Embargo Management (EM), and Case
  State (CS) state machines into an existing workflow management system.
stakeholder_type: [platform-developer]
level: 400
---

# Process Implementation Notes

{% include-markdown "../includes/not_normative.md" %}

!!! note "Scope of this page"
    This page covers how to integrate the Vultron Protocol's Report Management (RM),
    Embargo Management (EM), and Case State (CS) state machines
    into existing workflow management systems — for example, hooking an IT Service Management (ITSM) ticketing
    system into the RM lifecycle.

    For a conceptual overview of the *reference implementation's* architectural
    choices — hexagonal boundaries, the ActivityStreams-based inbox pipeline, and
    behavior tree orchestration — see
    [Reference Implementation Architecture](../topics/reference_architecture.md)
    in the Explanation section.

To integrate the Vultron Protocol into everyday Multi-Party Coordinated Vulnerability Disclosure (MPCVD) operations, identify where each of your business processes
intersects with the [RM](../topics/process_models/rm/index.md), [EM](../topics/process_models/em/index.md),
and [CS](../topics/process_models/cs/index.md) process models, then instrument each intersection to emit the
appropriate protocol message.

## RM Implementation Notes

Roughly speaking, the RM process is very close to a normal [ITSM](https://en.wikipedia.org/wiki/IT_service_management){:target="_blank"}
incident or service request workflow.
As such, the RM process could be implemented as a JIRA ticket workflow, as part of a Kanban process, etc.
The main modifications needed to adapt an existing workflow are to intercept the key milestones and emit the appropriate RM messages:

- when the reports are received (*RK*)

- when the report validation process completes (*RI*, *RV*)

- when the report prioritization process completes (*RA*, *RD*)

- when the report is closed (*RC*)

### Vulnerability Draft Pre-Publication Review

!!! tip inline end "Pre-Publication Drafts in Related Standards"

    [ISO/IEC 29148:2018](https://www.iso.org/standard/72311.html){:target="_blank"} includes a pre-publication review step in its process.

MPCVD case Participants often share pre-publication drafts of their advisories during the embargo period.
The Vultron Protocol does not prescribe this process, as it is not strictly necessary for the MPCVD process
to complete successfully.
However, as described in the [ISO Crosswalk](../reference/iso_crosswalks/index.md), the *GI* and *GK* message types
provide sufficient mechanics to support draft sharing.
To support this workflow, build the draft-sharing process into the
[*prepare publication*](../topics/behavior_logic/publication_bt.md#prepare-publication-behavior) step, where appropriate.

## EM Implementation Notes

### Embargo Management Does Not Deliver Synchronized Publication

The Vultron EM process establishes when publication restrictions are lifted.
That is not the same as scheduling publications following the embargo termination.
In practice, this distinction is rarely a significant problem since many case Participants
publish at their own pace shortly after the embargo ends.
However, at times, case Participants may find it necessary to coordinate more closely on publication scheduling.

!!! example "TLP and Embargoes"

    The [Traffic Light Protocol (TLP)](https://www.first.org/tlp){:target="_blank"} is a useful tool for managing the
    dissemination of sensitive information.
    TLP can be used to indicate how widely information can be shared and what restrictions apply during an embargo.
    For example, an embargoed case might be marked <span style="color:#FFC000;background-color:#000000">**TLP:AMBER**</span>
    to indicate that the information is sensitive and should be shared only with those who need to know.
    Thus, an embargo declaration might take the form of "This case is <span style="color:#FFC000;background-color:#000000">**TLP:AMBER**</span>
    until 2024-03-31 23:59:59 UTC, at which time it becomes <span style="color:#FFFFFF;background-color:#000000">**TLP:CLEAR**</span>." 
    The [CERT Guide to Coordinated Vulnerability Disclosure (CVD)](https://certcc.github.io/CERT-Guide-to-CVD/howto/operation/opsec/){:target="_blank"} covers TLP in CVD in more detail.

## CS Implementation Notes

Because part of the CS model is Participant-specific and the other is global to the case, the two parts are addressed separately below.

### The *vfd* Process

Similar to the RM process, which is specific to each Participant, the *vfd* process is
individualized to each Vendor (or Deployer, for the simpler $d \xrightarrow{\mathbf{D}} D$ state transition).
Modifications to the Vendor's development process to implement the Vultron Protocol are expected to be minimal and are
limited to the following:

- acknowledging the Vendor's role on report receipt with a *CV* message

- emitting a *CF* message when a fix becomes ready (and possibly terminating any active embargo to open the door to publication)

- (if relevant) issuing a *CD* message when the fix has been deployed

Non-Vendor Deployers are rarely involved in MPCVD cases, but when they are, their main integration point is to emit a
*CD* message when deployment is complete.

### The *pxa* Process

On the other hand, the *pxa* process hinges on monitoring public and private sources for evidence of information leaks,
research publications, and adversarial activity.
In other words, the *pxa* process is well positioned to be wired into Participants' threat intelligence and threat
analysis capabilities.
The goal would be to emit *CP*, *CX*, and *CA* messages as appropriate when such evidence is detected.
Some portions of this process can be automated:

- Human analysts and/or automated search agents can look for evidence of early publication of vulnerability information.

- Intrusion Detection System (IDS) and Intrusion Prevention System (IPS) signatures might be deployed prior to fix availability to act as an early warning of adversary activity.

- Well-known code publication and malware analysis platforms can be monitored for evidence of exploit publication or use.

## Conformance

A conformance claim names the capability sets an implementation provides and the roles it takes on, written `CapabilitySet / Role` ([§12.1](../reference/vultron-spec/index.md#121-conformance-model-overview)).
[What Is Vultron?](../topics/background/what-is-vultron.md#what-conformance-means-for-your-system) summarizes the three capability sets.

Conformance *tests* are organized in four layers, a separate axis from the capability sets ([§12.5](../reference/vultron-spec/index.md#125-conformance-testing-approach)).
A capability set says what your software provides; a layer says what a test checks.

**L1 — Syntax**
: Messages are well formed against the wire format.
  The wire format is defined in [§5 of the specification](../reference/vultron-spec/index.md#5-syntactic-layer-wire-format-n).

**L2 — Semantics**
: Each received message or local event drives the correct state transition.
  The [Vultron Protocol spec (VP)](../reference/specs/protocol.md) and the [Transition Functions](../reference/formal_protocol/transitions.md) define the transitions.

**L3 — Behavior**
: Given an input state and a received message or event, the right messages are emitted and the right states reached.
  The protocol behavioral specifications define the expected outputs:

    - [RMB — Report Management Behavioral Requirements](../reference/specs/protocol.md#rmb)
    - [EMB — Embargo Management Behavioral Requirements](../reference/specs/protocol.md#emb)
    - [CSB — CVD Case State Behavioral Requirements](../reference/specs/protocol.md#csb)

**L4 — Process**
: The internal order of decisions, such as precondition checks before state writes before protocol effects, audit-log ordering, and idempotency.
  L4 inspects internal structure, so it applies only to the reference implementation, whose behavior tree layer lives in `vultron/core/behaviors/`.

Independent implementations are tested at L1 through L3.
