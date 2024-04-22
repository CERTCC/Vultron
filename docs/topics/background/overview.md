# Documentation Overview

MPCVD is comprised of independent Participants performing their own CVD-related processes.

## Process Models

Those processes can be represented by Finte State Machines (FSMs), specifically as Deterministic Finite Automata (DFAs).
CVD processes (and the DFAs representing them) can be decomposed hierarchically.
We propose three main DFAs as the core of our Vultron Protocol:

1. A [Report Management](../process_models/rm/index.md) DFA represents each CVD Participant's engagement with a particular report
2. An [Embargo Management](../process_models/em/index.md) DFA negotiates and establishes the timing of future disclosures and publications
3. A [Case State](../process_models/cs/index.md) DFA tracks the events in [CVD Substates](../process_models/cs/index.md#cvd-case-substates),
    as originally described in [A State-Based Model for Multi-Party Coordinated Vulnerability Disclosure](https://resources.sei.cmu.edu/library/asset-view.cfm?assetid=735513){:target="_blank"}.

[Model Interactions](../process_models/model_interactions/index.md) contains a discussion of the interactions
among these three state machine models.

## Formal Protocol

However, a set of agents independently executing processes is not coordinated, and if they are not coordinated,
then whatever they are doing does not deserve the name CVD.
Hence, there is a need for a protocol to describe the interactions necessary to coordinate these processes.
[Communicating FSMs](https://doi.org/10.1145/322374.322380){:target="_blank"} provide a formal way to define a communications protocol, which coordinates the activities of
independent DFAs through the interchange (e.g., sending and receiving) of messages.
We map our multiple DFA model onto a formal protocol definition in [Formal Protocol](../../reference/formal_protocol/index.md).

### Behavior Logic

An MPCVD protocol needs to do more than just provide formally defined communication mechanisms.
It also needs to normalize the expected behaviors and activities that the communication protocol enables.
In this sense, our protocol expands upon
[ISO/IEC 29147:2018](https://www.iso.org/standard/72311.html){:target="_blank"},
[ISO/IEC 30111:2019](https://www.iso.org/standard/69725.html){:target="_blank"},
and
[ISO/IEC TR 5895:2022](https://www.iso.org/standard/81807.html){:target="_blank"},
which, taken together, provide a high-level normative standard for CVD activities.

Developed in response to the growing complexity of video game Non-Player Character (NPC) Artificial Intelligence (AI)
Finite State Machines (FSMs), Behavior Trees offer a way to organize and describe agent behaviors in a straightforward,
understandable way.
Using Behavior Trees, agent processes can be modeled as sets of behaviors (e.g., pre-conditions, actions, and
post-conditions) and the logic that joins them together.
Today, Behavior Trees are used in video game software to develop realistic NPCs and in robotics to create reactive and
adaptive behaviors from autonomous agents.
Behavior Trees offer a high potential for automating complex tasks through a hierarchical decomposition of the logic and
actions required to complete those tasks.

The behaviors we are interested in modeling are the various CVD activities described in the
[*CVD Guide*](https://certcc.github.io/CERT-Guide-to-CVD){:target="_blank"} (e.g., find contacts, send reports, validate reports,
prioritize reports, create fixes, publish reports, publish fixes, deploy fixes).
We use [Behavior Trees](../behavior_logic/index.md) to describe MPCVD Participant activities and their interactions with
the [formal protocol](../../reference/formal_protocol/index.md).

## Implementation Notes

Additional [implementation notes](../../howto/index.md), including a simplified case data model, are provided.

Future work is discussed in [Future Work](../future_work/index.md).

## Reference Material

Reference material includes

- the [Formal Protocol](../../reference/formal_protocol/index.md) description
- an [ISO Crosswalk](../../reference/iso_crosswalks/index.md) contains a detailed crosswalk of our
  protocol with ISO/IEC 29147:2018 *Vulnerability Disclosure*, ISO/IEC
  30111:2019 *Vulnerability Handling Processes*, and ISO/IEC TR 5895:2022
  *Multi-party coordinated vulnerability disclosure and handling*.
- an [SSVC Crosswalk](../../reference/ssvc_crosswalk.md) provides a mapping between the Vultron Protocol
  and relevant portions of the [Stakeholder Specific Vulnerability Categorization](https://github.com/CERTCC/SSVC){:target="_blank"}
  ([SSVC](https://github.com/CERTCC/SSVC){:target="_blank"}), a vulnerability response prioritization
  model also developed by the CERT/CC
