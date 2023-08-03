# Documentation Overview

MPCVD is comprised of independent Participants performing their own CVD-related processes.

## Process Models

Those processes can be represented by Finte State Machines (FSMs), specifically as Deterministic Finite Automata (DFAs).
CVD processes (and the DFAs representing them) can be decomposed hierarchically. 
We propose three main DFAs as the core of our MPCVD protocol:

1.  A [Report Management](/topics/process_models/rm) DFA represents each CVD Participant's engagement with a particular report
2.  An [Embargo Management](/topics/process_models/em) DFA negotiates and establishes the timing of future disclosures and publications
3.  A [Case State](/topics/process_models/cs) DFA tracks the events in {== Table [\[tab:cs_transitions\]](#tab:cs_transitions){reference-type="ref"
    reference="tab:cs_transitions"} ==}, as originally described in the {== Householder and Spring 2021 report [@householder2021state] ==}.

[Model Interactions](/topics/process_models/model_interactions) contains a discussion of the interactions
among these three state machine models.

## Formal Protocol

However, a set of agents independently executing processes is not coordinated, and if they are not coordinated, 
then whatever they are doing does not deserve the name CVD.
Hence, there is a need for a protocol to describe the interactions necessary to coordinate these processes.
[Communicating FSMs](https://doi.org/10.1145/322374.322380) provide a formal way to define a communications protocol, which coordinates the activities of 
independent DFAs through the interchange (e.g., sending and receiving) of messages.
We map our multiple DFA model onto a formal protocol definition in [Formal Protocol](/reference/formal_protocol).

### Behavior Logic 

However, an MPCVD
protocol needs to do more than just provide formally defined
communication mechanisms. It also needs to normalize the expected
behaviors and activities that the communication protocol enables. In
this sense, our protocol expands upon
[ISO/IEC 29147:2018](https://www.iso.org/standard/72311.html), 
[ISO/IEC 30111:2019](https://www.iso.org/standard/69725.html),
and
[ISO/IEC TR 5895:2022](https://www.iso.org/standard/81807.html),
which, taken together, provide a high-level normative standard for CVD activities.

Developed in response to the growing complexity of video game
Non-Player Character (NPC) Artificial Intelligence (AI) FSMs, Behavior Trees
offer a way to organize and describe agent behaviors in a
straightforward, understandable way. Using Behavior Trees, agent
processes can be modeled as sets of behaviors (e.g., pre-conditions,
actions, and post-conditions) and the logic that joins them together.
Today, Behavior Trees are used in video game software to develop
realistic NPCs and in robotics to create reactive and adaptive behaviors from autonomous
agents. Behavior Trees offer a high potential for automating complex
tasks through a hierarchical decomposition of the logic and actions
required to complete those tasks.

The behaviors we are interested in modeling are the various
CVD activities described in the [*CVD Guide*](https://vuls.cert.org/confluence/display/CVD) (e.g., find contacts, send
reports, validate reports, prioritize reports, create fixes, publish
reports, publish fixes, deploy fixes).
{== Chapter
[\[ch:behavior_trees\]](#ch:behavior_trees){reference-type="ref"
reference="ch:behavior_trees"} ==} uses Behavior Trees to describe
MPCVD Participant activities and their interactions with the [formal protocol](/reference/formal_protocol).

## Implementation Notes

Additional [implementation notes](/topics/implementation_notes), including a simplified case data model, are provided.
Future work is discussed in [Future Work](/topics/future_work).
{== Our conclusion is in Chapter
[\[ch:conclusion\]](#ch:conclusion){reference-type="ref"
reference="ch:conclusion"}. ==}

Appendices are included to provide connections to closely related work:
In Appendix
[\[app:ssvc_mpcvd_protocol\]](#app:ssvc_mpcvd_protocol){reference-type="ref"
reference="app:ssvc_mpcvd_protocol"}, we provide a mapping between the
MPCVD protocol
and relevant portions of the SSVC, a vulnerability response prioritization
model also developed by the [CERT/CC]{acronym-label="CERT/CC"
acronym-form="singular+short"}. Appendix
[\[app:iso_crosswalk\]](#app:iso_crosswalk){reference-type="ref"
reference="app:iso_crosswalk"} contains a detailed crosswalk of our
protocol with ISO/IEC 29147:2018 *Vulnerability Disclosure*, ISO/IEC
30111:2019 *Vulnerability Handling Processes*, and ISO/IEC TR 5895:2022
*Multi-party coordinated vulnerability disclosure and handling*.
Appendix [\[app:em_icalendar\]](#app:em_icalendar){reference-type="ref"
reference="app:em_icalendar"} maps concepts from the
EM process onto the
`iCalendar` protocol.

A list of acronyms is provided at the end of the report.
