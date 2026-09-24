---
description: >
  The Multi-Party Coordinated Vulnerability Disclosure (MPCVD) process defined
  as a communicating hierarchical state machine.
stakeholder_type: [platform-developer, process-researcher]
level: 400
---

# A Formal Protocol Definition for MPCVD

{% include-markdown "../../includes/normative.md" %}

This section defines the Multi-Party Coordinated Vulnerability Disclosure (MPCVD) process formally, as a Communicating Hierarchical State Machine.
It is for implementers and researchers who already know the [Report Management (RM)](../../topics/process_models/rm/index.md), [Embargo Management (EM)](../../topics/process_models/em/index.md), and [Case State (CS)](../../topics/process_models/cs/index.md) process models and need their exact combined definition.

{% include-markdown "../../includes/do_not_start_here.md" %}

## Pages in this section

The pages follow the order of the protocol definition, one element at a time:

- [Protocol Definition](protocol_definition.md) — the protocol quadruple, the global state of a protocol, and the number of processes in a case.
- [States](states.md) — the set of states $S_i$ of each Participant and its start state $o_i$.
- [Messages](messages.md) — the message types $M_{i,j}$ that Participants exchange.
- [Transitions](transitions.md) — the transition function $succ$ for sending and receiving each message type.
- [Protocol Summary](conclusion.md) — a recap of the definition with summary diagrams of each process model.

## Relationship to the specification

Where this section and the [Vultron Protocol Specification](../vultron-spec/index.md) disagree, the specification governs.
The specification's state-machine sections give the normative states and transitions of each machine, starting with [Report Management](../vultron-spec/index.md#6-report-management-rm-state-machine-n).
