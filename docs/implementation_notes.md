# Implementation Notes {#ch:implementation notes}

While a complete [MPCVD]{acronym-label="MPCVD"
acronym-form="singular+short"} protocol implementation specification is
out of scope for this report, we do have a few additional suggestions
for future implementations. In this chapter, we describe an abstract
case object for use in tracking [MPCVD]{acronym-label="MPCVD"
acronym-form="singular+short"} cases. Next, we touch on the core
[MPCVD]{acronym-label="MPCVD" acronym-form="singular+short"} protocol
subprocesses ([RM]{acronym-label="RM" acronym-form="singular+short"},
[EM]{acronym-label="EM" acronym-form="singular+short"}, and
[CS]{acronym-label="CS" acronym-form="singular+short"}), including how
the [CS]{acronym-label="CS" acronym-form="singular+short"} model might
integrate with other processes. Finally, we provide a few general notes
on future implementations.

## An MPCVD Case Object {#sec:case_object}

In this section, we describe a notional [MPCVD]{acronym-label="MPCVD"
acronym-form="singular+short"} *Case* object that incorporates the state
machines and formal protocol of the previous chapters. The object model
we describe is intended to provide the necessary core information for an
implementation of the protocol described in
§[\[sec:formal_protocol\]](#sec:formal_protocol){reference-type="ref"
reference="sec:formal_protocol"} to function. Figure
[\[fig:mpcvd_uml_class_diagram\]](#fig:mpcvd_uml_class_diagram){reference-type="ref"
reference="fig:mpcvd_uml_class_diagram"} depicts a
[UML]{acronym-label="UML" acronym-form="singular+short"} Class Diagram
of the *Case* model. It is not the minimal possible model required by
the [MPCVD]{acronym-label="MPCVD" acronym-form="singular+short"}
protocol of this report; for example, strictly speaking, a Participant
does not need to attempt to track the state of every other Participant,
but it might help to do so. Rather, this model is intended to be compact
yet sufficient enough for an implementation to effectively track the
coordination effort of an [MPCVD]{acronym-label="MPCVD"
acronym-form="singular+short"} case.

The remainder of this section provides details about Figure
[\[fig:mpcvd_uml_class_diagram\]](#fig:mpcvd_uml_class_diagram){reference-type="ref"
reference="fig:mpcvd_uml_class_diagram"}.

### The *Case* Class

The *Case* class has attributes to track the [EM]{acronym-label="EM"
acronym-form="singular+short"} state as described in
§[\[ch:embargo\]](#ch:embargo){reference-type="ref"
reference="ch:embargo"} and the global portion of the
[CS]{acronym-label="CS" acronym-form="singular+short"} (i.e., the *pxa*
substates), as outlined in
§[\[sec:model\]](#sec:model){reference-type="ref"
reference="sec:model"}. The *Case* class aggregates one or more
*Report*s and *Participant*s, and 0 or more *Message*s and *LogEvent*s.

### The *Report* Class

The *Report* class represents the vulnerability report that serves as
the impetus for the case. Since it is possible for multiple reports to
arrive that describe the same vulnerability, the cardinality of the
composition relationship allows for a *Case* to have many *Report*s. In
most *Case*s, however, there will be only a single associated *Report*.

### The *Message* Class

The *Message* class represents a protocol message as outlined in
§[\[sec:protocol_message_types\]](#sec:protocol_message_types){reference-type="ref"
reference="sec:protocol_message_types"}. We expect that any
implementation of this model will expand this data type to include
numerous message-related attributes. Here, we highlight the minimum
requirements that the protocol demands: Each *Message* has an identified
sender (who is a *Participant* in the case) and one or more message
types from
§[\[sec:protocol_message_types\]](#sec:protocol_message_types){reference-type="ref"
reference="sec:protocol_message_types"}. Message types are represented
as flags since a single actual message might represent multiple message
types. For example, a report submission that includes an embargo
proposal might have both the $RS$ and $EP$ message type flags set.

Conceptually, one might think of the *Case* as a shared object among
*engaged Participants* and that *Messages* are sent to the *Case* for
all *Participants* to see. In other words, the *Case* acts as a
broadcast domain, a topic queue, or a blackboard pattern (depending on
your preferences for networking or software engineering terminology).
Because of this shared-channel assumption, we omit a $receiver$
attribute from the *Message* class, as the *Case* itself can serve as
the recipient of each message emitted by any *Participant*.
Implementations of this model could, of course, choose a more
traditional messaging model with specified recipients.

### The *LogEvent* Class

The *LogEvent* class is a placeholder to represent an event log or
history for the *Case*. Although not required for the protocol to
operate, it is a good idea for *Case* tracking to include a timestamped
list of events (e.g., state changes or messages sent or received) so
that new *Participants* can be brought up to speed and so that cases can
be analyzed for process improvement in the future.

### The *Participant* Class {#sec:case_object_participant_class}

The *Participant* class represents an individual or organization's
involvement in the case. The attributes of the *Participant* class are
as follows:

case_role.

:   A set of flags indicating the Role(s) this *Participant* plays in
    the *Case* (Flags are used instead of an enumeration to convey that
    a *Participant* may have multiple roles in a single *Case*. Roles
    may differ for the same actor across different cases. For example,
    an organization might be the Vendor in one case and the Coordinator
    in another.)

rm_state.

:   An enumeration attribute that captures the [RM]{acronym-label="RM"
    acronym-form="singular+short"} state for this *Participant*
    consistent with
    §[\[sec:report_management\]](#sec:report_management){reference-type="ref"
    reference="sec:report_management"}

case_engagement.

:   A Boolean attribute that indicates whether the *Participant* should
    be included in future communications about the *Case* (This
    attribute is provided to allow other *Participant*s to recognize the
    status of other *Participants*. For example, a Reporter who bows out
    of a case shortly after reporting it to a Coordinator might be
    listed as a *Participant* with $case\_engagement=False$ and could,
    therefore, be left out of further communication about the case.)

embargo_adherence.

:   A Boolean attribute that indicates the expectation that a
    *Participant* is adhering to any existing embargo (As discussed in
    §[\[sec:embargo_engagement\]](#sec:embargo_engagement){reference-type="ref"
    reference="sec:embargo_engagement"}, it is possible for a
    *Participant* to exit a case while still agreeing to abide by the
    terms of the extant embargo. Continuing our example of a Reporter
    leaving a case early, they might still be cooperative and indicate
    their $embargo\_adherence=True$. A more hostile *Participant* exit
    could warrant setting $embargo\_adherence=False$, likely triggering
    an embargo teardown procedure as a consequence.)

*Participant*s can also emit (send) and receive messages. The + on
$receive\_message$ indicates that this capability is accessible to
others (i.e., you can send a *Participant* a message). On the contrary
the - on $emit\_message$ conveys that this capability is only accessible
to the *Participant* class itself (i.e., each *Participant* gets to
decide if, when, and what messages to send).

##### *Vendor* and *Deployer* *Participant* Classes.

The presence of the *VendorParticipant* and *DeployerParticipant*
classes---depicted as implementations of the *Participant* class---is
necessitated by the discussion in
§[\[sec:vendor_states\]](#sec:vendor_states){reference-type="ref"
reference="sec:vendor_states"} and
§[\[sec:deployer_states\]](#sec:deployer_states){reference-type="ref"
reference="sec:deployer_states"}, where we described how Vendors and
Deployers have a unique part to play in the creation, delivery, and
deployment of fixes within the [CVD]{acronym-label="CVD"
acronym-form="singular+short"} process. These two classes add the
*vfd_state* attribute with different possible values. Vendors can take
on one of four possible values ($vfd$, $Vfd$, $VFd$, and $VFD$), whereas
Deployers only have two possible values ($\wc\wc d$ and $\wc\wc D$).
Other than that, Vendors and Deployers have the same attributes as other
*Participant*s.

### The *Contact* Class

Since a *Participant* is a specific relationship between an individual
or organization and the *Case* itself, we can safely assume that those
individuals or organizations exist and persist independently of the
*Case*s they participate in. Hence, each *Participant* class in a *Case*
is associated with a long-lived *Contact* record that represents an
individual or organization. Defining the *Contact* class is outside the
scope of this report, so we will simply say that there is nothing
particularly special about it. One might reasonably expect *Contact*s to
have names, email addresses, phone numbers, etc.

A separate contact management process and accompanying directory service
is a likely candidate for future integration work. We revisit this topic
in §[\[sec:cvd_directory\]](#sec:cvd_directory){reference-type="ref"
reference="sec:cvd_directory"}. For now, we observe that similar
directories already exist, although there is room for improvement:

-   The [FIRST]{acronym-label="FIRST" acronym-form="singular+short"}
    maintains a directory of member teams for incident response purposes
    (<https://www.first.org/members/teams/>).

-   Disclose.io offers a searchable list of bug bounty and vulnerability
    disclosure programs (<https://disclose.io/programs/>). Contributions
    are solicited as pull requests on GitHub
    (<https://github.com/disclose/diodb>).

-   Many vulnerability disclosure platform service providers host
    directories of the programs hosted on their platforms.

### The Enumeration Classes

The remainder of Figure
[\[fig:mpcvd_uml_class_diagram\]](#fig:mpcvd_uml_class_diagram){reference-type="ref"
reference="fig:mpcvd_uml_class_diagram"} consists of classes
representing the Role and Message Type flags and various enumerations.
The Roles are the same set we have used throughout this report, as taken
from the *CVD Guide* [@householder2017cert]. Message Type flags are
consistent with
§[\[sec:protocol_message_types\]](#sec:protocol_message_types){reference-type="ref"
reference="sec:protocol_message_types"}. The enumeration classes are
consistent with the [RM]{acronym-label="RM"
acronym-form="singular+short"}, [EM]{acronym-label="EM"
acronym-form="singular+short"}, and [CS]{acronym-label="CS"
acronym-form="singular+short"} state machines described in Chapters
[\[sec:report_management\]](#sec:report_management){reference-type="ref"
reference="sec:report_management"},
[\[ch:embargo\]](#ch:embargo){reference-type="ref"
reference="ch:embargo"}, and
[\[sec:model\]](#sec:model){reference-type="ref" reference="sec:model"},
respectively.

## Process Implementation Notes {#sec:process_implementation_notes}

Integrating the [MPCVD]{acronym-label="MPCVD"
acronym-form="singular+short"} protocol into everyday MPCVD operations
requires each Participant to consider how their business processes
interact with the individual [RM]{acronym-label="RM"
acronym-form="singular+short"}, [EM]{acronym-label="EM"
acronym-form="singular+short"}, and [CS]{acronym-label="CS"
acronym-form="singular+short"} process models we described in Chapters
[\[sec:report_management\]](#sec:report_management){reference-type="ref"
reference="sec:report_management"},
[\[ch:embargo\]](#ch:embargo){reference-type="ref"
reference="ch:embargo"}, and
[\[sec:model\]](#sec:model){reference-type="ref" reference="sec:model"}.
In this section, we offer some thoughts on where such integration might
begin.

### RM Implementation Notes

Roughly speaking, the [RM]{acronym-label="RM"
acronym-form="singular+short"} process is very close to a normal
[ITSM]{acronym-label="ITSM" acronym-form="singular+short"} incident or
service request workflow. As such, the RM process could be implemented
as a JIRA ticket workflow, as part of a Kanban process, etc. The main
modifications needed to adapt an existing workflow are to intercept the
key milestones and emit the appropriate [RM]{acronym-label="RM"
acronym-form="singular+short"} messages:

-   when the reports are received ($RK$)

-   when the report validation process completes ($RI$, $RV$)

-   when the report prioritization process completes ($RA$, $RD$)

-   when the report is closed ($RC$)

##### Vulnerability Draft Pre-Publication Review.

[MPCVD]{acronym-label="MPCVD" acronym-form="singular+short"} case
Participants often share pre-publication drafts of their advisories
during the embargo period [@ISO29147]. Our protocol proposal is mute on
this subject because it is not strictly necessary for the
[MPCVD]{acronym-label="MPCVD" acronym-form="singular+short"} process to
complete successfully. However, as we observe in Appendix
[\[app:iso_crosswalk\]](#app:iso_crosswalk){reference-type="ref"
reference="app:iso_crosswalk"}, the $GI$ and $GK$ message types appear
to provide sufficient mechanics for this process to be fleshed out as
necessary. This draft-sharing process could be built into the *prepare
publication* process outlined in
§[\[sec:prepare_publication_bt\]](#sec:prepare_publication_bt){reference-type="ref"
reference="sec:prepare_publication_bt"}, where appropriate.

### EM Implementation Notes

In terms of the proposal, acceptance, rejection, etc., the
[EM]{acronym-label="EM" acronym-form="singular+short"} process is
strikingly parallel to the process of scheduling a meeting in a
calendaring system. In Appendix
[\[app:em_icalendar\]](#app:em_icalendar){reference-type="ref"
reference="app:em_icalendar"}, we suggest a potential mapping of many of
the concepts from the [EM]{acronym-label="EM"
acronym-form="singular+short"} process onto `iCalendar` protocol
semantics.

### CS Implementation Notes {#sec:cs_implementation_notes}

Because part of the [CS]{acronym-label="CS"
acronym-form="singular+short"} model is Participant specific and the
other is global to the case, we address each part below.

##### The $vfd$ Process.

Similar to the [RM]{acronym-label="RM" acronym-form="singular+short"}
process, which is specific to each Participant, the $vfd$ process is
individualized to each Vendor (or Deployer, for the simpler
$d \xrightarrow{\mathbf{D}} D$ state transition). Modifications to the
Vendor's development process to implement the
[MPCVD]{acronym-label="MPCVD" acronym-form="singular+short"} protocol
are expected to be minimal and are limited to the following:

-   acknowledging the Vendor's role on report receipt with a $CV$
    message

-   emitting a $CF$ message when a fix becomes ready (and possibly
    terminating any active embargo to open the door to publication)

-   (if relevant) issuing a $CD$ message when the fix has been deployed

Non-Vendor Deployers are rarely involved in
[MPCVD]{acronym-label="MPCVD" acronym-form="singular+short"} cases, but
when they are, their main integration point is to emit a $CD$ message
when deployment is complete.

##### The $pxa$ Process.

On the other hand, the $pxa$ process hinges on monitoring public and
private sources for evidence of information leaks, research
publications, and adversarial activity. In other words, the $pxa$
process is well positioned to be wired into Participants' threat
intelligence and threat analysis capabilities. Some portions of this
process can be automated:

-   Human analysts and/or automated search agents can look for evidence
    of early publication of vulnerability information.

-   [IDS]{acronym-label="IDS" acronym-form="singular+short"} and
    [IPS]{acronym-label="IPS" acronym-form="singular+short"} signatures
    might be deployed prior to fix availability to act as an early
    warning of adversary activity.

-   Well-known code publication and malware analysis platforms can be
    monitored for evidence of exploit publication or use.

## General Notes

The protocol and data structures outlined in this report are intended to
facilitate interoperability among individual organizations' workflow
management systems. As such, they are focused on the exchange of
information and data necessary for the [MPCVD]{acronym-label="MPCVD"
acronym-form="singular+short"} process to function and will not likely
be sufficient to fully address any individual organization's
vulnerability response process.

We conclude the chapter with a few general implementation notes.

### Message Formats {#sec:msg_formats}

We defined a number of message types in
§[\[sec:protocol_message_types\]](#sec:protocol_message_types){reference-type="ref"
reference="sec:protocol_message_types"} and showed how they fit into a
case in §[1.1](#sec:case_object){reference-type="ref"
reference="sec:case_object"}, but we did not specify any format for
these messages. Message formats can be thought of as two related
problems:

##### Structure and Semantic Content of Each Message Type.

In addition to the commentary throughout this chapter, messages will
likely need to have some sort of consistent header information and some
content specifically designed to address the semantic needs of each
message type. Such a format must include fields, datatypes, and an
underlying formatting structure.

##### Container Syntax for Messaging and Data Exchange.

While we have a predilection for [JSON]{acronym-label="JSON"
acronym-form="singular+short"} Schema-defined formats, other format
specifications (e.g., [XSD]{acronym-label="XSD"
acronym-form="singular+short"} or [protobuf]{acronym-label="protobuf"
acronym-form="singular+short"}) could serve implementers' needs just as
well. In fact, to the degree possible, it seems preferable for the
container syntax to remain a late-binding decision in implementation. As
long as the structure and semantics are well defined, most standard data
formats should be adaptable to the task.

-   [MPCVD]{acronym-label="MPCVD" acronym-form="singular+short"}
    Protocol Messages SHOULD use well-defined format specifications
    (e.g., [JSON]{acronym-label="JSON" acronym-form="singular+short"}
    Schema, [protobuf]{acronym-label="protobuf"
    acronym-form="singular+short"}, [XSD]{acronym-label="XSD"
    acronym-form="singular+short"}).

We anticipate that emerging formats like the OASIS
[CSAF]{acronym-label="CSAF"
acronym-form="singular+short"} [@csaf-docs; @csaf-oasis] and ontologies
like the [NIST]{acronym-label="NIST" acronym-form="singular+short"}
Vulnerability Data Ontology (Vulntology) [@vulntology] will play a part.

### Transport Protocol {#sec:transport_protocol}

We have not specified how [MPCVD]{acronym-label="MPCVD"
acronym-form="singular+short"} protocol implementations connect to each
other. Presumably, technologies such as [REST]{acronym-label="REST"
acronym-form="singular+short"} [APIs]{acronym-label="API"
acronym-form="plural+short"} or WebSockets would be leading candidates
to resolve this gap. However, other system architectures could be
adapted as well. For example, an [XMPP]{acronym-label="XMPP"
acronym-form="singular+short"} message-routing system might be desired,
or even blockchain-related technologies might be adaptable to portions
of this protocol as well.

-   [MPCVD]{acronym-label="MPCVD" acronym-form="singular+short"}
    Protocol Implementations SHOULD use common [API]{acronym-label="API"
    acronym-form="singular+short"} patterns (e.g.,
    [REST]{acronym-label="REST" acronym-form="singular+short"},
    WebSockets).

### Identity Management {#sec:identity_mgt}

We have not addressed Participant authentication as part of the
protocol, but obviously implementers will need to determine how
Participants know who they are talking to. Individual user accounts with
multi-factor authentication are the de facto standard for modern
[CVD]{acronym-label="CVD" acronym-form="singular+short"} tools, but in
an interoperable [MPCVD]{acronym-label="MPCVD"
acronym-form="singular+short"} world, the assumption of centralized
identity management may not be practical. Federated identity protocols
such as OAuth, [SAML]{acronym-label="SAML"
acronym-form="singular+short"}, and/or OpenID Connect may be useful.
