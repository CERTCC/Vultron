---
description: >
  A reading path for people who build or maintain a vulnerability tracker,
  platform, or tool that must coordinate with partners' systems.
stakeholder_type: [platform-developer]
level: 100
---

# You maintain a vulnerability tracker and want it to talk to your partners

You build or run the system where vulnerability reports and cases live: a tracker, a coordination platform, a disclosure portal, or an internal tool.
Today your partners reach it through accounts on your system, or you reach theirs through accounts on theirs.
This page is a reading path through the parts of this site that describe what your system sends, when it sends it, and where your own logic plugs in.
Each step builds on the one before it.

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
