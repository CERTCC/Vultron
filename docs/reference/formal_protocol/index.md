---
description: >
  The Multi-Party Coordinated Vulnerability Disclosure (MPCVD) process defined
  as a communicating hierarchical state machine.
stakeholder_type: [platform-developer, process-researcher]
level: 400
introduces: [Deterministic Finite Automaton (DFA), Global State, Communicating Hierarchical State Machine]
contents: generated
---

# A Formal Protocol Definition for MPCVD

{% include-markdown "../../includes/normative.md" %}

This section defines the Multi-Party Coordinated Vulnerability Disclosure (MPCVD) process formally, as a Communicating Hierarchical State Machine.
It is for implementers and researchers who already know the [Report Management (RM)](../../topics/process_models/rm/index.md), [Embargo Management (EM)](../../topics/process_models/em/index.md), and [Case State (CS)](../../topics/process_models/cs/index.md) process models and need their exact combined definition.

{% include-markdown "../../includes/do_not_start_here.md" %}

## Pages in this section

The pages follow the order of the protocol definition, one element at a time:

<!-- BEGIN GENERATED SECTION CONTENTS — do not edit; change the mkdocs.yml nav or a listed page's description: frontmatter, then run `uv run docs-site --write` -->

- [Protocol Definition](protocol_definition.md) — The formal definition of the Vultron protocol as a Brand-Zafiropulo communication protocol, its global state, and its number of processes.
- [States](states.md) — The set of states of each Participant and its start state.
- [Messages](messages.md) — The message types that Participants exchange.
- [Transitions](transitions.md) — The transition function for sending and receiving each message type.
- [Protocol Summary](conclusion.md) — A recap of the definition with summary diagrams of each process model.

<!-- END GENERATED SECTION CONTENTS -->

## Relationship to the specification

Where this section and the [Vultron Protocol Specification](../vultron-spec/index.md) disagree, the specification governs.
The specification's state-machine sections give the normative states and transitions of each machine, starting with [Report Management](../vultron-spec/tracking-models.md#6-report-management-rm-state-machine-n).
