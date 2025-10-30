# Vultron ActivityStreams Objects

{% include-markdown "../../includes/not_normative.md" %}

Vultron ActivityStreams (Vultron AS) is an extension of the
[ActivityStreams vocabulary](https://www.w3.org/TR/activitystreams-vocabulary/){:target="_blank"}
to describe the mapping of Vultron to ActivityStreams.

## ActivityStreams native objects

The ActivityStreams Vocabulary defines a number of native object types that can be used to represent objects in the
ActivityPub protocol. These fall into the following categories:

- **Actors** (see [below](#actors))
- **Activities** (see the [Activities](./activities/index.md) section for more information)
- **Other (non-Activity) Object Types** (see [below](#other-non-activity-object-types))

### Actors

!!! info inline end "Actor vs CaseParticipant"

    As we will see below, we will introduce a new object type called [`CaseParticipant`](#caseparticipant)
    to represent the participants in a `VulnerabilityCase`.
    This is because the `as:Actor` types are intended to represent persistent identities within a larger 
    ActivityPub network, while a `CaseParticipant` is a contextual identity that associates an actor to a 
    specific `VulnerabilityCase` object.
    We need to make this distinction so that the Vultron protocol can represent a single actor participating in 
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
- `as:Collection`
- `as:CollectionPage`, including `as:OrderedCollection` and `as:OrderedCollectionPage`
- `as:Document`, including `as:Audio`, `as:Image`, and `as:Video`
- `as:Event`
- `as:Note`
- `as:Page`
- `as:Place`
- `as:Profile`
- `as:Relationship`
- `as:Tombstone`

Of these, we mainly use `as:Note` to represent comments on a [`VulnerabilityCase`](#vulnerabilitycase).
The [`EmbargoEvent`](#embargoevent) object a specialization of the `as:Event` object.
There is nothing stopping systems that implement the Vultron protocol from using other ActivityStreams object types
as needed, but we do not define any special semantics for these objects in the context of the Vultron protocol.

## Vultron-specific objects

!!! tip inline end "See also"

    As a reminder, we already described these objects in the [Case Object](../case_object.md) section.
    This section is intended to describe how these objects are represented as ActivityStreams objects.

We define the following objects for use in the Vultron AS vocabulary:

- [`VulnerabilityReport`](#vulnerabilityreport)
- [`VulnerabilityCase`](#vulnerabilitycase)
- [`CaseStatus`](#casestatus)
- [`CaseParticipant`](#caseparticipant)
- [`ParticipantStatus`](#participantstatus)
- [`EmbargoEvent`](#embargoevent)

### VulnerabilityReport

A `VulnerabilityReport` object is used to represent a vulnerability report as an ActivityStreams object.
We are not attempting to fully define a vulnerability report data object in this protocol.
Instead, we are defining a minimal set of properties that are necessary to support the protocol.

In the example below, we show a `VulnerabilityReport` object that contains a simple text description of a
vulnerability in the `content` property. However, in a real implementation, the `content` property might contain
any sort of vulnerability report format that could be embedded as part of the JSON object.

Examples of what might go into the `content` property of a `VulnerabilityReport` object include:

- Community-developed Structured formats like [CSAF](https://oasis-open.github.io/csaf-documentation/){:target="_blank"} or
  [CVE JSON](https://github.com/CVEProject/cve-schema){:target="_blank"}
- Quasi-structured text formats based on templates like the
  [OWASP Vulnerability Template](https://owasp.org/www-community/vulnerabilities/Vulnerability_template){:target="_blank"}
- Proprietary formats used by vendors, coordinators, or finders, such as might be found behind a web form like
  [CERT/CC's Vulnerability Reporting Form](https://www.kb.cert.org/vuls/vulcoordrequest/){:target="_blank"}
- A plain text description of the vulnerability, for example a markdown-formatted text description with section
  headings and links to external resources

We are deliberately leaving the format of the `content` property open-ended in order to allow for flexibility in the
types of vulnerability reports that can be represented. However, we do recommend that the `content` property be used to
represent a widely-used structured format whenever possible, since this will allow for more automation in the processing of
vulnerability reports.

While we recommend that the `content` property be used to contain text-based vulnerability report formats, we also
recognize the potential need for some vulnerability reports to take the form of binary attachments, such as PDF
documents, images, audio files, or video files. In these cases, the `content` property could contain a link to the binary
file or an embedded encoding of the binary file. However, we recommend that binary attachments be avoided whenever
possible, since they can be more difficult to process automatically.

```python exec="true" idprefix=""
from vultron.scripts.vocab_examples import gen_report, json2md

print(json2md(gen_report()))
```

!!! tip "Articles and Documents"

    Obviously a VulnerabilityReport or advisory draft could also be an 
    `as:Article` or `as:Document`, but at the moment we don't use those types 
    explicitly.

### VulnerabilityCase

A `VulnerabilityCase` object is used to represent a vulnerability case as an ActivityStreams object.
As with `VulnerabilityReport`, we are not attempting to fully define a vulnerability case data object in this protocol.
Instead, we are defining a minimal set of properties that are necessary to support the protocol.
The `VulnerabilityCase` object is intended to be consistent with the [Case Object](../case_object.md) defined elsewhere.

!!! tip "ActivityStreams Objects are for Interoperability"

    The objects we define here are intended to be used to promote interoperability between systems that communicate using
    ActivityPub. They are not intended to be used as a data model for a single system. For example, one vendor might use
    Github issues to track vulnerability cases, while another might use Jira. Both vendors could use the same
    `VulnerabilityCase` object to represent their cases in ActivityPub, but they would not necessarily use the same
    data model internally.

```python exec="true" idprefix=""
from vultron.scripts.vocab_examples import case, json2md, gen_report

_case = case()
_case.add_report(gen_report())
_case.add_participant("https://vultron.example/cases/1/participants/vendor")
_case.add_participant("https://vultron.example/cases/1/participants/finder")

print(json2md(_case))
```

### CaseStatus

A `CaseStatus` object is used to represent the participant-agnostic status of a `VulnerabilityCase` object.
We describe the semantics of the `CaseStatus` object in the [Case Object](../case_object.md) section.
The distinction between *participant-agnostic* and *participant-specific* status is described in the
[Global vs Local](../../topics/process_models/model_interactions/index.md) section.

```python exec="true" idprefix=""
from vultron.scripts.vocab_examples import case_status, json2md

print(json2md(case_status()))
```

### CaseParticipant

As noted above,
the `CaseParticipant` object is a wrapper around an `as:Actor` object that associates the actor with a specific
`VulnerabilityCase` object.
The `CaseParticipant` object is intended to be consistent with the
[Participant Class](../case_object.md#the-participant-class) defined as part of the [Case Object](../case_object.md).
The `CaseParticipant` object also includes a `participantStatus` property that describes the
participant's status in the case as it progresses.

```python exec="true" idprefix=""
from vultron.scripts.vocab_examples import case_participant, json2md

print(json2md(case_participant()))
```

### ParticipantStatus

A `ParticipantStatus` object is used to represent the participant-specific status of a `CaseParticipant` within
the context of a `VulnerabilityCase` object.
As noted [above](#casestatus), see the [Global vs Local](../../topics/process_models/model_interactions/index.md)
section for more information about the distinction between *participant-agnostic* and *participant-specific* status.

```python exec="true" idprefix=""
from vultron.scripts.vocab_examples import participant_status, json2md

print(json2md(participant_status()))
```

!!! question "Why is there a CaseStatus inside the ParticipantStatus?"

    The `ParticipantStatus` object allows for a `CaseParticipant` to include a `CaseStatus` object that is specific to
    that participant. This allows for a participant to indicate that they believe the case as a whole is in a different
    state than the case owner believes it to be in. For example, a vendor might believe that a an exploit has been
    released for a vulnerability, while the coordinating case owner believes that the vulnerability is still unexploited. In this
    case, the vendor could include a `CaseStatus` object in their `ParticipantStatus` that indicates that the case has
    reached _Exploit Public_. Upon confirmation of this status by the case owner, the case owner would update the
    `CaseStatus` object in the `VulnerabilityCase` object to reflect the new status by changing the `pxaState` to 
    include _X_.

### EmbargoEvent

An `EmbargoEvent` object is used to represent the end date and time of an embargo event as an ActivityStreams object.
It is a specialization of the `as:Event` object.

```python exec="true" idprefix=""
from vultron.scripts.vocab_examples import embargo_event, json2md

print(json2md(embargo_event()))
```
