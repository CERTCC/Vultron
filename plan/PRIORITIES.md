# Priorities

## Priority 1: Behavior Tree Prototype Implementation and ActivityPub Workflow Demonstrations

The top priority is the Behavior Tree prototype implementation 
partially outlined in
`specs/behavior-tree-integration.md` and `plan/IMPLEMENTATION_PLAN.md`.
BT integration from this point forwards should focus on implementing 
and integrating workflow demonstrations of the ActivityPub processes outlined in

`docs/howto/activitypub/activities`, specifically:

Higher priority:
- `docs/howto/activitypub/activities/acknowledge.md`
- `docs/howto/activitypub/activities/initialize_case.md`
- `docs/howto/activitypub/activities/initialize_participant.md`
- `docs/howto/activitypub/activities/manage_case.md`
- `docs/howto/activitypub/activities/invite_actor.md`
- `docs/howto/activitypub/activities/establish_embargo.md`
- `docs/howto/activitypub/activities/status_updates.md`
- `docs/howto/activitypub/activities/manage_embargo.md`
- `docs/howto/activitypub/activities/manage_participants.md`
Lower priority:
- `docs/howto/activitypub/activities/transfer_ownership.md`
- `docs/howto/activitypub/activities/suggest_actor.md`
- `docs/howto/activitypub/activities/error.md`

Workflow demonstrations should be implemented
as distinct demo scripts similar to `vultron/scripts/receive_report_demo.py` 
that can be run independently to demonstrate the specific workflow. Each of 
these would require some amount of setup to create the necessary preconditions,
then execute the workflow and demonstrate side effects and outputs. They 
should also be dockerized and use the same `api-dev` container so that the
demo is legitimately demonstrating the backend API.

The ActivityPub processes often refer to message types that correspond to 
behavior tree nodes in the BT simulator in `vultron/bt` that will need to be 
reimplemented in the new BT implementation in `vultron/behavior`. Additional 
insights on mapping processes to semantics can also be found in the 
`ontology/vultron_*.ttl` files. Note similarities in names between the 
documentation and the behavior tree nodes, these are not accidental. 

Behavior logic documentation can be found in `docs/topics/behavior_logic/*.md`, 
start with `docs/topics/behavior_logic/cvd_bt.md` for a map of content. Note 
that the behavior tree documentation is older than even the `vultron/bt` 
implementation, so there may be some discrepancies between the documentation and
the simulator implementation. The simulator implementation is the more 
up-to-date reference for the behavior tree design, but the documentation may still be
useful for understanding the rationale behind design decisions and the overall
structure and purpose of the behavior tree. Updating the documentation to 
reflect the eventual design of the new BT implementation will be necessary but
is a lower priority than implementing the BT itself and demonstrating the
ActivityPub processes through the BT.

## Priority 50: Refactoring large modules

There are some implementation notes about refactoring large modules in  
`plan/IMPLEMENTATION_NOTES.md` that are worth keeping in mind as we implement
the prototype. These are not high priority from a feature perspective, but they
are important because these large files are being manipulated on nearly 
every task in the `plan/IMPLEMENTATION_PLAN.md` and so refactoring them 
sooner rather than later will make the implementation process smoother and 
less error-prone.

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

---
## Priority 99999: Remaining Requirements and Documentation Updates

The project is currently in prototype development mode, therefore requirements
that are marked as `PROD_ONLY` are temporarily a lower priority than other 
requirements.

