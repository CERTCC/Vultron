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
Some of these stories describe needs the protocol has not taken up.
The stories about bug bounties are waiting on a decision about whether bounty programs are in scope at all.

Coverage is a count read from the specifications, not a judgment of how well the protocol serves a story.
The specifications hold the mapping, so both this table and the matrix are generated from them and a check in the build fails when either one drifts.

The story pages from the 2022 catalog once carried a support level, a judgment made as of v0.4.0 of whether the protocol provided, allowed or did not support each story.
Coverage replaces it, and no page carries it now.

## Who Speaks in a Story

Each story is told by a persona: the "As a …" that opens it.
The personas form four families.
**Participant** is anyone who takes part in a case, and its members are the CVD roles, such as Vendor or Coordinator.
**Implementer** is anyone who builds or runs software that speaks the protocol: a Peer Implementer, a Node Operator or a Tool Author.
**Researcher** is anyone who studies or checks the protocol model and its records: a Protocol Author or an Auditor.
**Contributor** is anyone who works on this reference implementation: a Maintainer, a Coding Agent or a Demo Operator.

A story's speaker is the highest level that includes every party the story concerns and no party it does not.
"As a Participant" means every CVD role, and "As a Vendor" means only the Vendor.
A story names a member only when it does not hold for the whole family.
The [Story Personas](../glossary.md#story-personas) section of the glossary defines each persona.

## Adding a Story

Reuse an existing story when one already states the need; add a story only when none does.

- **ID.** A new story's ID is `story_<year>_NNN`: the year it is added, then the next unused number in that year.
  The `story_2022_*` stories are frozen.
  An ID is never reused, and a story page is never deleted: a story that is split or withdrawn keeps its page, marked superseded by the IDs that replace it.
- **Page.** The page is `story_<year>_NNN.md` in this directory.
  Its frontmatter declares only `stakeholder_type: [project-contributor]`.
  The story text sits on one line between the `<!-- story-start -->` and `<!-- story-end -->` markers.
  A **Notes** section explains the need, and a **Metadata** section gives the speaker, the CVD roles concerned when the speaker is a Participant, the issues the story came from or relates to, the issue it was drafted for, and the date it was added.
- **Table and matrix.** Do not edit the table below or the [User Story Traceability Matrix](traceability.md).
  Both are generated from the specifications: run `uv run docs-site --write` after adding a page, and the new story appears with *No mapped requirements* until a requirement names it in its `stories:` field.

## User Stories Table

{% include-markdown "./table.md" %}

{% include-markdown "../../start/_paths/coordinate-cases/reference__user_stories__index.md" %}

{% include-markdown "../../start/_paths/study-the-process/reference__user_stories__index.md" %}
