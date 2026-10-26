---
description: >
  A reading path for people who build or maintain a vulnerability tracker,
  platform, or tool that must coordinate with partners' systems.
stakeholder_type: [platform-developer]
level: 100
page_type: routing
thread:
  - title: Understand the shape of the integration
    kind: chain
    members:
      - page: topics/background/what-is-vultron.md
        blurb: >-
          the protocol, its four senses, and what conformance means for your system.
      - page: topics/capability_model/index.md
        blurb: >-
          every decision the protocol leaves open, and the call-out point where your system answers it.
      - page: howto/process_implementation.md
        blurb: >-
          where an existing ticket workflow's milestones map onto protocol messages.
  - title: Send your first message
    kind: chain
    members:
      - page: tutorials/submit-a-report.md
        blurb: >-
          one report, sent to a running actor, end to end.
      - page: howto/activitypub/index.md
        blurb: >-
          the wire format every message uses.
      - page: topics/message_semantics.md
        blurb: >-
          what each message means to the participant who receives it.
      - page: topics/protocol_flow.md
        blurb: >-
          how a received message turns into state changes and replies.
  - title: Build against the contract
    kind: set
    members:
      - page: reference/vultron-spec/index.md
        blurb: >-
          the normative protocol, including the conformance claims your system can make.
      - page: reference/messages/index.md
        blurb: >-
          every message, its fields, and when it is sent.
      - page: reference/trigger-api.md
        blurb: >-
          the endpoints your system calls to act on a case.
      - page: howto/wire_capability.md
        blurb: >-
          replacing a stub decision with your own service.
      - page: howto/index.md
        blurb: >-
          the remaining task-oriented guides.
---

# You maintain a vulnerability tracker and want it to talk to your partners

You build or run the system where vulnerability reports and cases live: a tracker, a coordination platform, a disclosure portal, or an internal tool.
Today your partners reach it through accounts on your system, or you reach theirs through accounts on theirs.
This page is a reading path through the parts of this site that describe what your system sends, when it sends it, and where your own logic plugs in.
Each section builds on the ones before it; read a numbered list in order and a bulleted list in any order.

[Send your first message](../tutorials/submit-a-report.md){ .md-button .md-button--primary }
[Read the Protocol Specification](../reference/vultron-spec/index.md){ .md-button }

<!-- BEGIN GENERATED READING PATH — do not edit; change this page's thread: frontmatter, then run `uv run docs-site --write` -->

## Understand the shape of the integration

1. [What Is Vultron?](../topics/background/what-is-vultron.md) — the protocol, its four senses, and what conformance means for your system.
2. [Capability Model](../topics/capability_model/index.md) — every decision the protocol leaves open, and the call-out point where your system answers it.
3. [Process Implementation Notes](../howto/process_implementation.md) — where an existing ticket workflow's milestones map onto protocol messages.

## Send your first message

1. [Tutorial: Submit a report to a Vultron actor](../tutorials/submit-a-report.md) — one report, sent to a running actor, end to end.
2. [Vultron and ActivityPub](../howto/activitypub/index.md) — the wire format every message uses.
3. [Message Semantics](../topics/message_semantics.md) — what each message means to the participant who receives it.
4. [Protocol Event Flow](../topics/protocol_flow.md) — how a received message turns into state changes and replies.

## Build against the contract

- [Vultron Protocol Specification](../reference/vultron-spec/index.md) — the normative protocol, including the conformance claims your system can make.
- [Message Types](../reference/messages/index.md) — every message, its fields, and when it is sent.
- [Trigger API Reference](../reference/trigger-api.md) — the endpoints your system calls to act on a case.
- [Wiring a Capability into the Reference Implementation](../howto/wire_capability.md) — replacing a stub decision with your own service.
- [How-to Guides](../howto/index.md) — the remaining task-oriented guides.

<!-- END GENERATED READING PATH -->
