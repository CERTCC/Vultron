# Process Implementation Notes

{% include-markdown "../includes/not_normative.md" %}

Integrating the Vultron Protocol into everyday MPCVD operations requires each Participant to consider how their business processes
interact with the individual [RM](../topics/process_models/rm/index.md), [EM](../topics/process_models/em/index.md),
and [CS](../topics/process_models/cs/index.md), process models, respectively.
Here we offer some thoughts on where such integration might begin.

## RM Implementation Notes

Roughly speaking, the RM process is very close to a normal [IT Service Management](https://en.wikipedia.org/wiki/IT_service_management){:target="_blank"} (ITSM)
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
Our protocol proposal is mute on this subject because it is not strictly necessary for the MPCVD process to complete successfully.
However, as we observe in the [ISO Crosswalk](../reference/iso_crosswalks/index.md), the *GI* and *GK* message types appear to provide sufficient mechanics for this
process to be fleshed out as necessary.
This draft-sharing process could be built into the [*prepare publication*](../topics/behavior_logic/publication_bt.md#prepare-publication-behavior) process, where appropriate.

## EM Implementation Notes

### Embargo Management and Calendaring

In terms of the proposal, acceptance, rejection, etc., the EM process is strikingly parallel to the process of
scheduling a meeting in a calendaring system, and could be mapped onto
[`iCalendar`](https://en.wikipedia.org/wiki/ICalendar){:target="_blank"} protocol semantics.

### Embargo Management Does Not Deliver Synchronized Publication

In our protocol design, we were careful to focus the EM process on establishing when publication restrictions are
lifted.
That is not the same as actually scheduling publications following the embargo termination.
Our experience at the CERT/CC shows that this distinction is rarely a significant problem since many case Participants
simply publish at their own pace shortly after the embargo ends.
However, at times, case Participants may find it necessary to coordinate even more closely on publication scheduling.

!!! example "TLP and Embargoes"

    The [Traffic Light Protocol (TLP)](https://www.first.org/tlp){:target="_blank"} is a useful tool for managing the
    dissemination of sensitive information.
    TLP can be used to indicate how widely information can be shared and what restrictions apply during an embargo.
    For example, an embargoed case might be marked <span style="color:#FFC000;background-color:#000000">**TLP:AMBER**</span>
    to indicate that the information is sensitive and should be shared only with those who need to know.
    Thus, an embargo declaration might take the form of "This case is <span style="color:#FFC000;background-color:#000000">**TLP:AMBER**</span>
    until 2024-03-31 23:59:59 UTC, at which time it becomes <span style="color:#FFFFFF;background-color:#000000">**TLP:CLEAR**</span>." 
    We have more to say about the use of TLP in CVD in the [CERT Guide to CVD](https://certcc.github.io/CERT-Guide-to-CVD/howto/operation/opsec/){:target="_blank"}.

## CS Implementation Notes

Because part of the CS model is Participant specific and the other is global to the case, we address each part below.

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

- IDS and IPS signatures might be deployed prior to fix availability to act as an early warning of adversary activity.

- Well-known code publication and malware analysis platforms can be monitored for evidence of exploit publication or use.

## Conformance Levels

Independent implementors can achieve different levels of protocol conformance.
The Vultron Protocol defines four levels, each building on the previous:

**L1 — Syntax**
: Well-formed messages that conform to the wire format.
  This level is covered by the [wire format specifications](../reference/specs/language.md).

**L2 — Semantic**
: Correct state transitions in response to received messages and local events.
  This level is covered by the [Vultron Protocol spec (VP)](../reference/specs/general.md) and the
  [Transition Functions](../reference/formal_protocol/transitions.md).

**L3 — Behavioral**
: Correct observable outputs — the right messages emitted and the right states reached
  in response to a given (input state + received message/event) combination.
  This level is covered by the domain behavioral specifications:

    - [RMB — Report Management Behavioral Requirements](../reference/specs/domain.md#rmb)
    - [EMB — Embargo Management Behavioral Requirements](../reference/specs/domain.md#emb)
    - [CSB — CVD Case State Behavioral Requirements](../reference/specs/domain.md#csb)

**L4 — Process**
: Correct internal decision structure — for example, precondition checks before state writes
  before protocol effects, audit-log ordering, and idempotency guarantees.
  This level is enforceable only through a reference implementation.
  The `vultron/core/behaviors/` behavior tree layer in this repository provides the
  reference implementation for L4.

!!! tip "Start with L2"

    Most implementations will naturally achieve L1 by using a compliant message serializer.
    L2 conformance is the practical minimum for interoperability: a Participant that transitions
    states correctly can exchange messages with any other L2-conformant Participant.
    L3 adds observable-output guarantees that matter for multi-party coordination correctness.
