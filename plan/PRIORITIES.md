# Priorities

The first phase of the Behavior Tree demo implementation is complete.
There are two significant phases coming up next.

## PRIORITY 10: Phase DEMO-4: Integrate individual demos into unified interface 

The top priority at present is preparing the behavior tree demo
scripts for a consolidated demo. See notes in `plan/IDEATION.md` 
**Unify demos into a single script with CLI and dockerize** for details.
This includes refactoring the existing demo scripts to be callable from a 
new combined demo script with a CLI, and then dockerizing the new
combined demo script so that it can be run interactively from within 
the container. The individual demo scripts should also retain their ability 
to be run independently, but they should be refactored to ensure that they 
can be run in sequence without interference. As part of the refactoring, 
**TECHDEBT-2** from `plan/IMPLEMENTATION_PLAN.md` should also be addressed to
centralize the demo utilities and reduce code duplication across the demos.
It is preferred to tackle the tech debt task first to create a clean foundation
for the demo refactoring.

## PRIORITY 20: Address some technical debt

Specifically, in the `plan/IMPLEMENTATION_PLAN.md`, we need to address
**TECHDEBT-1** and **TECHDEBT-5** to reduce module size for future 
maintainability.

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
