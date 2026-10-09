---
description: >
  Requirements captured as user stories.
stakeholder_type: [cvd-practitioner, process-researcher]
level: 200
---

# User Stories

{% include-markdown "../../includes/not_normative.md" %}

The Vultron Protocol is designed to support a variety of use cases.
The following user stories are intended to capture the requirements of these use cases.
While the protocol is designed to support these use cases, it is not required that all use cases be supported by the
protocol.

Where appropriate, a reference implementation will be provided for each applicable user story.
The [User Story Traceability Matrix](traceability.md) maps each story to the formal requirements in the specifications that satisfy it.

<br/>

!!! info "Original User Stories from 2022 CERT/CC Whitepaper"

    Stories numbered from `2022_001` through `2022_102` originated in
    the [Coordinated Vulnerability Disclosure User Stories](https://resources.sei.cmu.edu/library/asset-view.cfm?assetid=886543){:target="_blank"}
    whitepaper.
    
    > These user stories reflect
    > internal discussions with the CERT/Coordination Center (CC) based on our own experiences in developing and using the
    > VINCE platform as well as our ongoing CVD practices. The user stories are expected to be utilized by the CVD team to
    > better understand, create, and implement a CVD Protocol. In addition, the CERT/CC believes that these user cases will
    > be useful for any enterprise designing or implementing its own CVD policies, processes, and procedures.
    
    The remaining stories have been added since that whitepaper was published.

## Support Levels

Each story page carries a support level, assigned when the story was written against the protocol as it stood at the time:

- *Provided* - The protocol directly supports the story.
- *Allowed* - The protocol indirectly supports the story.
- *Unsupported* - The protocol does not support the story.
- *Out-of-scope* - The story is outside the protocol's scope.

A support level is a dated judgment, not a live conformance result.
The [User Story Traceability Matrix](traceability.md) is the current record of which requirements satisfy a story, and a story with mapped requirements may be better supported than its original level says.

## User Stories Table

{% include-markdown "./table.md" %}
