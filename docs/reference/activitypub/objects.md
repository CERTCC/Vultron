---
description: >
  The Vultron ActivityStreams objects that extend the ActivityStreams
  vocabulary.
stakeholder_type: [platform-developer]
level: 300
---

# Vultron ActivityStreams Objects

{% include-markdown "../../includes/not_normative.md" %}

Vultron ActivityStreams (Vultron AS) is an extension of the
[ActivityStreams vocabulary](https://www.w3.org/TR/activitystreams-vocabulary/){:target="_blank"}
to describe the mapping of Vultron to ActivityStreams.
This page shows each Vultron object as it appears on the wire.
The normative definition of the object types is [§5.2 Object Types](../vultron-spec/index.md#52-object-types) of the Vultron Protocol Specification; the activities that carry them are cataloged in [Message Types](../messages/index.md).
For why the extension is as small as it is, and when a new object type is minted
rather than reusing a native one, see
[Activity Vocabulary Design](../../topics/activity_vocabulary_design.md).

## ActivityStreams native objects

The ActivityStreams Vocabulary defines a number of native object types that can be used to represent objects in the
ActivityPub protocol. These fall into the following categories:

- **Actors** (see [below](#actors))
- **Activities** (see the [Vultron AS Activity Guides](../../howto/activitypub/activities/index.md) for more information)
- **Other (non-Activity) Object Types** (see [below](#other-non-activity-object-types))

### Actors

!!! info inline end "Actor vs CaseParticipant"

    The [`CaseParticipant`](#caseparticipant) object type (defined below) represents the participants
    in a `VulnerabilityCase`.
    The `as:Actor` types represent persistent identities within a larger ActivityPub network, while a
    `CaseParticipant` is a contextual identity that associates an actor to a specific `VulnerabilityCase`
    object. This distinction allows the Vultron protocol to represent a single actor participating in
    multiple cases, with discrete roles and statuses within the context of each case.

The standard ActivityStreams actor types can be used in Vultron. These include:

- `as:Person`
- `as:Organization`
- `as:Group`
- `as:Service`
- `as:Application`

### Other (non-Activity) Object Types

ActivityStreams also includes a number of native object types, including:

- `as:Article`
- `as:Collection`, including `as:OrderedCollection`
- `as:Document`, including `as:Audio`, `as:Image`, and `as:Video`
- `as:Event`
- `as:Note`
- `as:Page`
- `as:Place`
- `as:Profile`
- `as:Relationship`
- `as:Tombstone`

`as:Note` is used to represent comments on a [`VulnerabilityCase`](#vulnerabilitycase).
The [`EmbargoEvent`](#embargoevent) object is a specialization of the `as:Event` object.
Systems implementing the Vultron protocol may use other ActivityStreams object types as needed;
no special semantics are defined for those objects in the context of the Vultron protocol.

## Vultron-specific objects

!!! tip inline end "See also"

    These objects are also described in the [Case Model](../../topics/case_lifecycle/case_model.md) section.
    This section describes how these objects are represented as ActivityStreams objects.

The following objects are defined for use in the Vultron AS vocabulary:

- [`VulnerabilityReport`](#vulnerabilityreport)
- [`VulnerabilityCase`](#vulnerabilitycase)
- [`CaseStatus`](#casestatus)
- [`CaseParticipant`](#caseparticipant)
- [`ParticipantStatus`](#participantstatus)
- [`EmbargoEvent`](#embargoevent)
- [`CaseParticipantRole`](#caseparticipantrole)
- [`CaseLedgerEntry`](#caseledgerentry)
- [`CaseProposal`](#caseproposal)

A case contains its participants, its report, its status records, its embargo events, and its ledger entries; a `CaseProposal` precedes the case and asks for one to be created.

### VulnerabilityReport

A `VulnerabilityReport` object is used to represent a vulnerability report as an ActivityStreams object.
This protocol does not define a full vulnerability report data object.
Instead, it defines a minimal set of properties necessary to support the protocol.

The example below shows a `VulnerabilityReport` object containing a simple text description of a
vulnerability in the `content` property. In a real implementation, the `content` property may contain
any vulnerability report format that can be embedded as part of the JSON object.

Examples of what might go into the `content` property of a `VulnerabilityReport` object include:

- Community-developed Structured formats like [CSAF](https://oasis-open.github.io/csaf-documentation/){:target="_blank"} or
  [CVE JSON](https://github.com/CVEProject/cve-schema){:target="_blank"}
- Quasi-structured text formats based on templates like the
  [OWASP Vulnerability Template](https://owasp.org/www-community/vulnerabilities/Vulnerability_template){:target="_blank"}
- Proprietary formats used by vendors, coordinators, or finders, such as might be found behind a web form like
  [CERT/CC's Vulnerability Reporting Form](https://www.kb.cert.org/vuls/vulcoordrequest/){:target="_blank"}
- A plain text description of the vulnerability, for example a markdown-formatted text description with section
  headings and links to external resources

The format of the `content` property is deliberately open-ended to allow for flexibility in the types of
vulnerability reports that can be represented. The `content` property SHOULD represent a widely-used
structured format whenever possible, since this allows for more automation in the processing of
vulnerability reports.

Binary attachments (PDF documents, images, audio files, video files) are supported; in those cases,
the `content` property MAY contain a link to the binary file or an embedded encoding. Binary attachments
SHOULD be avoided whenever possible since they are more difficult to process automatically.

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import gen_report, json2md

print(json2md(gen_report()))
```

!!! tip "Articles and Documents"

    A VulnerabilityReport or advisory draft could also be an `as:Article` or
    `as:Document`, but those types are not used explicitly by the protocol.

### VulnerabilityCase

A `VulnerabilityCase` object is used to represent a vulnerability case as an ActivityStreams object.
As with `VulnerabilityReport`, this protocol does not define a full vulnerability case data object.
Instead, it defines a minimal set of properties necessary to support the protocol.
The `VulnerabilityCase` object is consistent with the [Case Model](../../topics/case_lifecycle/case_model.md) defined elsewhere.

!!! tip "ActivityStreams Objects are for Interoperability"

    These objects are intended to promote interoperability between systems that communicate using
    ActivityPub. They are not intended to be used as a data model for a single system. For example, one vendor might use
    Github issues to track vulnerability cases, while another might use Jira. Both vendors could use the same
    `VulnerabilityCase` object to represent their cases in ActivityPub, but they would not necessarily use the same
    data model internally.

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import json2md, populated_case

print(json2md(populated_case()))
```

### CaseStatus

A `CaseStatus` object is used to represent the participant-agnostic status of a `VulnerabilityCase` object.
It is canonical: it carries what the case asserts, and only the [CASE_MANAGER](../../topics/case_lifecycle/case_manager_and_ledger.md) writes it ([§5.4.1](../vultron-spec/index.md#541-single-writer-authority)).
The semantics of the `CaseStatus` object are described in the [Case Model](../../topics/case_lifecycle/case_model.md) section.
The distinction between *participant-agnostic* and *participant-specific* status is described in the
[Global vs Local](../../topics/process_models/model_interactions/index.md) section.

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import case_status, json2md

print(json2md(case_status()))
```

### CaseParticipant

As noted above,
the `CaseParticipant` object is a wrapper around an `as:Actor` object that associates the actor with a specific
`VulnerabilityCase` object.
The `CaseParticipant` object is intended to be consistent with the
[CaseParticipant](../../topics/case_lifecycle/case_model.md#caseparticipant) defined as part of the [Case Model](../../topics/case_lifecycle/case_model.md).
The `CaseParticipant` object also includes a `participantStatus` property that describes the
participant's status in the case as it progresses.

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import case_participant, json2md

print(json2md(case_participant()))
```

### ParticipantStatus

A `ParticipantStatus` object is used to represent the participant-specific status of a `CaseParticipant` within
the context of a `VulnerabilityCase` object.
As noted [above](#casestatus), see the [Global vs Local](../../topics/process_models/model_interactions/index.md)
section for more information about the distinction between *participant-agnostic* and *participant-specific* status.

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import participant_status, json2md

print(json2md(participant_status()))
```

!!! question "Why is there a CaseStatus inside the ParticipantStatus?"

    A `ParticipantStatus` is a claim, and a `CaseStatus` is canonical.
    The `CaseStatus` inside a `ParticipantStatus` lets a participant state what it believes the case as a whole has reached, without that belief becoming the case's state.
    For example, a vendor might observe that an exploit has been released while the case still records the vulnerability as unexploited.
    The vendor includes a `CaseStatus` in its `ParticipantStatus` showing _Exploit Public_.
    The [CASE_MANAGER](../../topics/case_lifecycle/case_manager_and_ledger.md) then decides whether to adopt the claim, by default with the Case Owner's authorization, and if it does it writes the canonical `CaseStatus` on the `VulnerabilityCase` with `pxaState` including _X_ ([§10.3 Status Adoption](../vultron-spec/index.md#103-status-adoption-the-two-seam-model), [§12.4.4](../vultron-spec/index.md#1244-case-owner-authority)).
    No other participant writes the canonical `CaseStatus` ([§5.4.1](../vultron-spec/index.md#541-single-writer-authority)).

### EmbargoEvent

An `EmbargoEvent` object is used to represent the end date and time of an embargo event as an ActivityStreams object.
It is a specialization of the `as:Event` object.

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import embargo_event, json2md

print(json2md(embargo_event()))
```

### CaseParticipantRole

A `CaseParticipantRole` object carries a single CVD role being offered to an actor in the context of a case.
It is a distinct type so that offering a role (`Offer(CaseParticipantRole)`) is structurally different from offering ownership of the case (`Offer(VulnerabilityCase)`); see [Case Management Messages](../messages/case_management.md#offer-case-participant-role).
The example is the object carried by such an offer.

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import offer_case_participant_role, json2md

print(json2md(offer_case_participant_role().object_))
```

### CaseLedgerEntry

A `CaseLedgerEntry` object is one entry in the canonical case ledger.
The [CASE_MANAGER](../../topics/case_lifecycle/case_manager_and_ledger.md) writes an entry for every case-scoped message and fans it out to participants with `Announce(CaseLedgerEntry)`; each entry carries the hash of the previous one, which is how participants detect a gap.
See [Ledger Replication](../messages/ledger_replication.md) for the activities that carry it.
The example is the object carried by such an announcement.

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import announce_case_ledger_entry, json2md

print(json2md(announce_case_ledger_entry().object_))
```

### CaseProposal

A `CaseProposal` object asks another actor to create and manage a case around a report.
It is used when the actor holding the report does not intend to manage the case itself; the actor that accepts the proposal becomes the case's creator.
The report is carried inline, and `target` names the prospective case-actor service.
See [Case Proposal](../messages/case_proposal.md) for the three-message flow.

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import create_case_proposal, json2md

print(json2md(create_case_proposal().object_))
```
