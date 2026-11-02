---
description: >
  Requirements captured as user stories.
stakeholder_type: [cvd-practitioner, process-researcher]
level: 200
page_type: reference
subject: implementation
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

## Coverage

The table below gives each story's **coverage**: how many requirements in the specifications name that story as one of the needs they exist to serve.
The count links the story's entry in the [User Story Traceability Matrix](traceability.md), which lists those requirements grouped by specification file.

A story whose coverage cell reads *No mapped requirements* is one that no requirement names yet.
That is a recorded gap rather than an error.
Some of these stories describe needs the protocol has not taken up, and the stories about bug bounties are waiting on a decision about whether bounty programs are in scope at all.

Coverage is a count read from the specifications, not a judgment of how well the protocol serves a story.
The specifications hold the mapping, so both this table and the matrix are generated from them and a check in the build fails when either one drifts.

The story pages from the 2022 catalog still carry a **Support Level** line under Metadata, reading *Provided*, *Allowed*, *Unsupported* or *Out-of-scope* as of v0.4.0.
That line is a dated judgment that coverage replaces, and it is being removed from those pages; nine of the eleven stories it calls out-of-scope are cited by requirements today.
Read the coverage count, not the support level.

## User Stories Table

{% include-markdown "./table.md" %}

{% include-markdown "../../start/_paths/coordinate-cases/reference__user_stories__index.md" %}

{% include-markdown "../../start/_paths/study-the-process/reference__user_stories__index.md" %}
