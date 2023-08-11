# Implementation Notes

While a complete MPCVD protocol implementation specification is out of scope for this report, we do have a few 
additional suggestions for future implementations.
In this chapter, we describe an abstract case object for use in tracking MPCVD cases.
Next, we touch on the core MPCVD protocol subprocesses (RM, EM, and CS), including how the CS model might integrate with
other processes.
Finally, we provide a few general notes on future implementations.

## Process Implementation Notes {#sec:process_implementation_notes}

Integrating the MPCVD protocol into everyday MPCVD operations
requires each Participant to consider how their business processes
interact with the individual RM, EM, and CS process models we described in Chapters
[\[sec:report_management\]](#sec:report_management){reference-type="ref"
reference="sec:report_management"},
[\[ch:embargo\]](#ch:embargo){reference-type="ref"
reference="ch:embargo"}, and
[\[sec:model\]](#sec:model){reference-type="ref" reference="sec:model"}.
In this section, we offer some thoughts on where such integration might
begin.

### RM Implementation Notes

Roughly speaking, the RM process is very close to a normal
ITSM incident or
service request workflow. As such, the RM process could be implemented
as a JIRA ticket workflow, as part of a Kanban process, etc. The main
modifications needed to adapt an existing workflow are to intercept the
key milestones and emit the appropriate RM messages:

-   when the reports are received ($RK$)

-   when the report validation process completes ($RI$, $RV$)

-   when the report prioritization process completes ($RA$, $RD$)

-   when the report is closed ($RC$)

##### Vulnerability Draft Pre-Publication Review.

MPCVD case
Participants often share pre-publication drafts of their advisories
during the embargo period{== [@ISO29147] ==}. Our protocol proposal is mute on
this subject because it is not strictly necessary for the
MPCVD process to
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
EM process is
strikingly parallel to the process of scheduling a meeting in a
calendaring system. In Appendix
[\[app:em_icalendar\]](#app:em_icalendar){reference-type="ref"
reference="app:em_icalendar"}, we suggest a potential mapping of many of
the concepts from the EM process onto `iCalendar` protocol
semantics.

### CS Implementation Notes {#sec:cs_implementation_notes}

Because part of the CS model is Participant specific and the
other is global to the case, we address each part below.

##### The $vfd$ Process.

Similar to the RM
process, which is specific to each Participant, the $vfd$ process is
individualized to each Vendor (or Deployer, for the simpler
$d \xrightarrow{\mathbf{D}} D$ state transition). Modifications to the
Vendor's development process to implement the
MPCVD protocol
are expected to be minimal and are limited to the following:

-   acknowledging the Vendor's role on report receipt with a $CV$
    message

-   emitting a $CF$ message when a fix becomes ready (and possibly
    terminating any active embargo to open the door to publication)

-   (if relevant) issuing a $CD$ message when the fix has been deployed

Non-Vendor Deployers are rarely involved in
MPCVD cases, but
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

-   IDS and
    IPS signatures
    might be deployed prior to fix availability to act as an early
    warning of adversary activity.

-   Well-known code publication and malware analysis platforms can be
    monitored for evidence of exploit publication or use.

## General Notes

The protocol and data structures outlined in this report are intended to
facilitate interoperability among individual organizations' workflow
management systems. As such, they are focused on the exchange of
information and data necessary for the MPCVD process to function and will not likely
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

While we have a predilection for JSON Schema-defined formats, other format
specifications (e.g., XSD or protobuf) could serve implementers' needs just as
well. In fact, to the degree possible, it seems preferable for the
container syntax to remain a late-binding decision in implementation. As
long as the structure and semantics are well defined, most standard data
formats should be adaptable to the task.

-   MPCVD
    Protocol Messages SHOULD use well-defined format specifications
    (e.g., JSON
    Schema, protobuf, XSD).

We anticipate that emerging formats like the OASIS
CSAF [@csaf-docs; @csaf-oasis] and ontologies
like the NIST
Vulnerability Data Ontology (Vulntology){== [@vulntology] ==} will play a part.

### Transport Protocol {#sec:transport_protocol}

We have not specified how MPCVD protocol implementations connect to each
other. Presumably, technologies such as REST APIs or WebSockets would be leading candidates
to resolve this gap. However, other system architectures could be
adapted as well. For example, an XMPP message-routing system might be desired,
or even blockchain-related technologies might be adaptable to portions
of this protocol as well.

-   MPCVD
    Protocol Implementations SHOULD use common API patterns (e.g.,
    REST,
    WebSockets).

### Identity Management {#sec:identity_mgt}

We have not addressed Participant authentication as part of the
protocol, but obviously implementers will need to determine how
Participants know who they are talking to. Individual user accounts with
multi-factor authentication are the de facto standard for modern
CVD tools, but in
an interoperable MPCVD world, the assumption of centralized
identity management may not be practical. Federated identity protocols
such as OAuth, SAML, and/or OpenID Connect may be useful.
