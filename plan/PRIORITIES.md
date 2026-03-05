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


## Priority 100: Actor independence

Each actor exists in its own behavior tree domain. So Actor A and Actor B
cannot see each other's Behavior Tree blackboard at all. They can only interact
through the Vultron Protocol through passing ActivityStreams messages with
defined semantics. This allows us to have a clean model of individual
actors making independent decisions based on their own internal state.

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

## Priority 300: Demo ideas currently in IDEAS.md

There are a few extended demo ideas in `plan/IDEAS.md` that are currently just
notes and need to be implemented. These demos will be important for showcasing
the capabilities of the Vultron Protocol and the behavior tree implementation,
and for demonstrating how the various components of the system work together
in practice. Implementing these demos will also help to identify any gaps or
issues in the current implementation and provide a basis for further  
development and refinement.

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
still an open question.

One possibility we can imagine coordination agents that behave as
ActivityPub Actors and participate in cases as CaseParticipants alongside
humans.

We want to support agentic AI agents interacting with cases as well on the
backend (i.e., not as ActivityPub Actors, but as API or command
line clients.) We may have local agents that interact directly with
the behavior trees or other internal system components either via a command line
or API calls. These agents would not be ActivityPub Actors and would not directly
participate in cases, but would instead be more like assistants to human participants
who are directing them to perform specific tasks.

We will need to design the system in a way that allows for either of these
possibilities to be implemented in the future without requiring major refactoring.

## Priority 2000: Upgrade former "fuzzer" nodes to full implementations

See `notes/bt-fuzzer-nodes.md` for details on a set of fuzzer nodes that 
were implemented as placeholders in the original simulator, but that 
represent external touchpoints for the real process. Some of these nodes can 
be fully automated, others will require outside judgment, human input, or 
manual work. They might rely on external tools or services that we will need 
to integrate with. Implementing these nodes will be important for moving 
from a protoype to a production-ready system, but they also represent a 
number of decisions and implementation work that is not core to being able 
to demonstrate the core behavior tree and coordination logic.

## Priority 99999: Remaining Requirements and Documentation Updates

The project is currently in prototype development mode, therefore requirements
that are marked as `PROD_ONLY` are temporarily a lower priority than other
requirements.
