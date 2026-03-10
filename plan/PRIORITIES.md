# Priorities

## Important note about priority numbers

Priority numbers are ascending, so lower numbers are higher priority. 
The scale is not linear, it's just intended to provide a rough ordering and 
allow for space between to add new priorities in the future if needed. The
priority numbers themselves do not have any inherent meaning beyond their 
relative order.

## PRIORITY 30: Implement triggerable behaviors

Existing demos have primarily focused on updating local state based on receipt
of ActivityStreams activity messages. However, the Vultron Protocol also defines
a set of triggerable behaviors that are initiated by an actor based on their
internal state and decision-making processes, rather than being solely reactive to
external messages. Implementing demos that showcase these triggerable behaviors
will be important for demonstrating the full capabilities of the Vultron Protocol 
and the behavior tree implementation. Many of the behavior patterns are 
already present in the demo scripts, but they might not be fully exposed as 
triggerable behaviors. These triggerable behaviors will become an important 
part of the application API and will need to be implemented and demonstrated 
in some way. Details will need to be worked out as part of the design and 
planning process. 

Reference docs:
- `docs/topics/behavior_logic/rm_bt.md`
- `docs/topics/behavior_logic/rm_validation_bt.md`
- `docs/topics/behavior_logic/rm_prioritization_bt.md`
- `docs/topics/behavior_logic/rm_closure_bt.md`
- `docs/topics/behavior_logic/em_bt.md`
- `docs/topics/behavior_logic/em_eval_bt.md`
- `docs/topics/behavior_logic/em_propose_bt.md`
- `docs/topics/behavior_logic/em_propose_bt.md`


## Priority 50: Shift toward hexagonal architecture and port/adapter design sooner than later

Closely related to the Actor independence priority that follows, we want to 
shift towards a cleaner implementation of hexagonal architecture and port/adapter design. 
This will require some refactoring of the existing codebase to separate 
concerns more clearly, see `notes/architecture-ports-and-adapters.md` and  
`specs/architecture.md` for details. This will also enable the future demo 
scenarios to be more cleanly implemented. A number of implementations of the 
triggerable behaviors in `vultron/api/v2/routers/triggers.py` (which is too 
large and also needs to be split) wound up being procedural and mixed domain logic in 
with router code. Rather than merely splitting the large file, we need to refactor this code to 
separate concerns and move towards a cleaner architecture at the same time. 
Also, the datalayer implementation has 
similar problems where it would be cleaner if we were doing dependency 
injection in a way that is consistent with the hexagonal architecture.
This will entail some refactoring of the code base to reorganize modules and 
split out responsibilities more cleanly.

## Priority 60: Continue hexagonal architecture refactor

The hexagonal architecture refactor is a large task that will require multiple
iterations to fully implement. Some basics are in place (core and wire 
packages exist but are not fully populated). Some other packages just need 
to be relocated (e.g., `vultron/as_vocab` to `wire/as2`, `vultron/behaviors` 
to `core/behaviors`, etc.) but splitting `vultron/api` into adapters will 
take a little more finesse. The API layer has a lot of domain logic mixed in 
with routing and request handling, which properly belong in ports or adapters. 
`vultron/enums.py` needs to be split across core, ports, and adapters as 
well. The focus here should be on separating concerns and moving towards a 
cleaner architecture overall, starting to put the pieces in place to avoid 
large refactors later.

## Priority 65: Address all outstanding architecture violations in `notes/architecture-review.md`

Following an architecture review of the codebase, we have identified a 
number of architecture violations that need to be addressed. These are 
documented in `notes/architecture-review.md`. Addressing these violations is 
important so that we can move forward with a clean architecture that 
properly separates concerns from the front-end (driving adapters), wire, 
core (use cases, etc.), and back-end layers (driven ports and adapters). 
This continues Priority 50 and 60, and pre-empts or blends in with Priority 70 
below. Use the architecture review notes as a checklist to identify and 
address each violation, ensuring that tasks are grouped appropriately in 
`plan/IMPLEMENTATION_PLAN.md` to avoid excessive fragmentation of related work.

## Priority 70: DataLayer refactor into ports and adapters

The DataLayer implementation should be refactored to become a port (Protocol), 
with the TinyDB implementation as a (driven) adapter that implements it. 
Move files around as needed to fit the new structure cleanly. This sets us 
up for adding new db backends in the future without needing to change core 
logic. (That part is mostly already true since the DataLayer is reasonably 
well abstracted already, but we still need to make sure the files and their 
contents are 
organized to reflect the architecture.)

## Priority 100: Actor independence

Each actor exists in its own behavior tree domain. So Actor A and Actor B
cannot see each other's Behavior Tree blackboard at all. They can only interact
through the Vultron Protocol through passing ActivityStreams messages with
defined semantics. This allows us to have a clean model of individual
actors making independent decisions based on their own internal state.

Implementation Phase OUTBOX-1 logically falls under this priority, because 
it's part of getting messages flowing between actors. But it does not
fully achieve this goal by itself.


## Priority 200: Case Actor as source of truth for case state

The CaseActor becomes a resource that can manages the VulnerabilityCase. While
each Actor may maintain a copy of the case within their own system, the CaseActor
is the source of truth for the case state. It can update the case based on
inputs from other actors, and other actors can query the CaseActor for the
current state of the case when needed. The CaseActor is also responsible for
enforcing any rules or constraints on the case state, and for coordinating
actions between actors based on the case state. It can act as a broadcast
hub for case updates, sending notifications (as direct messages) to other actors
(listed as CaseParticipants) in the case.

The CaseActor must be instantiated at the beginning of the case lifecycle and
must exist until the case is closed. Each CaseActor handles exactly one VulnerabilityCase,
the one it was instantiated for. The CaseActor knows who the case owner (another Actor, NOT the CaseActor) is because
it is stored in the VulnerabilityCase itself. The CaseActor must restrict certain
activities to the case owner, such as closing the case or transferring ownership.
These details are defined in the `vultron_as:CaseOwnerActivity`
in `ontology/vultron_activitystreams.ttl`.

## Priority 300: Multi-Actor Demo Scenarios

Extended multi-actor demo scenarios are documented in
`notes/demo-future-ideas.md`. These demos — Two-Actor (Finder + Vendor),
Three-Actor (Finder + Vendor + Coordinator), and MultiParty (with ownership
transfer and expanded participants) — are important for showcasing the
capabilities of the Vultron Protocol and demonstrating how components work
together. Implementing these demos will help identify gaps in the current
implementation and provide a basis for further development and refinement.
Each scenario requires actors running in independent containers communicating
via the Vultron Protocol, with CaseActor managing case state.

See `notes/demo-future-ideas.md` for the full scenario descriptions.




## Priority 500: Re-implement "fuzzer" nodes from the original simulator

As we originally built out the `py_trees` implementation, we replaced 
certain fuzzer nodes from the simulator (`vultron/bt`) with deterministic nodes 
that simply 
return success. While this initially allowed us to focus on the core 
behavior tree logic, it also means that we are not able to demonstrate the 
full range of behaviors that the Vultron Protocol is designed to support. 
Re-implementing these nodes with more realistic behavior will be important for showcasing the
capabilities of the system and for moving towards a production-ready implementation.
The "fuzzer" implementation in the simulator worked well enough, so there is 
not much need to change the overall design, but we will need to reimplement 
it in the new codebase using `py_trees` as the foundation. The underlying 
`vultron/bt/base/fuzzer.py` module (and all the other `fuzzer.py` modules in 
`vultron/bt/`) can be used as a structural reference for the new implementation.

## Priority 1000: Agentic AI readiness

We are going to want to allow for the possibility of agentic AI integration
into the vultron coordination process in the future. How this will happen is
still an open question. One possibility we can imagine coordination agents 
that behave as ActivityPub Actors and participate in cases as CaseParticipants alongside
humans.

A more likely scenario is that we want to support agentic AI agents 
interacting with cases as well on the
backend (i.e., not as ActivityPub Actors, but as API or command
line clients.) We may have local agents that interact directly with
the behavior trees or other internal system components via MCP. This would 
be an adapter that parallels the API and CLI adapters in the hexagonal 
architecture. These agents would not be ActivityPub Actors and would not 
directly participate in cases, but would instead be more like assistants to human participants
who are directing them to perform specific tasks.

`AR-09-001` through `AR-09-004` and similar tasks will fall here.

We will need to design the system in a way that allows for either of these
possibilities to be implemented in the future without requiring major refactoring.

## Priority 2000: Upgrade former "fuzzer" nodes to full implementations

See `notes/bt-fuzzer-nodes.md` for details on a set of fuzzer nodes that 
were implemented as placeholders in the original simulator, but that 
represent external touchpoints for the real process. Some of these nodes can 
be fully automated, others will require outside judgment, human input, or 
manual work. They might rely on external tools or services that we will need 
to integrate with. Implementing these nodes will be important for moving 
from a prototype to a production-ready system, but they also represent a 
number of decisions and implementation work that is not core to being able 
to demonstrate the core behavior tree and coordination logic.

## Priority 99999: Remaining Requirements and Documentation Updates

The project is currently in prototype development mode, therefore requirements
that are marked as `PROD_ONLY` are temporarily a lower priority than other
requirements.
