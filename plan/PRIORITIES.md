# Priorities

## Important note about priority numbers

Priority numbers are ascending, so lower numbers are higher priority.
The scale is not linear, it's just intended to provide a rough ordering and
allow for space between to add new priorities in the future if needed. The
priority numbers themselves do not have any inherent meaning beyond their
relative order.

## Priority 80: Resolve technical debt and ensure Hexagonal Architecture is fully realized

We need to clean up
all the technical debt that we accumulated during the hexagonal architecture
refactor. This includes things like ensuring that core, adapters, and wire
are appropriately separated, that there is not architectural leakage from
the "outer" layers into core, that error handling is consistent,
hierarchical, well-defined, and not overly generalized (e.g., don't
blindly catch `Exception`) Getting the architecture solid is important for
the remainder of the implementation to go smoothly and for us to be able to
parallelize work on different components without running into merge conflicts or
other issues caused by architectural inconsistencies.

## Priority 85: Capture all tasks and requirements in IDEAS.md

IDEAS.md contains a significant number of ideas and tasks resulting from
multiple recent code reviews. Each of these needs to be fully captured and
reflected in `specs/`, `notes/` and `plan/` documents as appropriate. Tasks
that are not already in `plan/IMPLEMENTATION_PLAN.md` should be added there  
with a clear description and any relevant details. Requirements that are not
already in `specs/` should be added there with a clear requirement id,  
description, and any relevant details. Design ideas and research that are
not  already in `notes/` should be added there with a clear description and  
any relevant details. These updates are critical to ensure we are ready to
move forward with the upcoming phase 100 tasks. Some items might expand or
contradict existing notes, specs, or tasks. In those cases, whatever is in
IDEAS.md should be considered the source of truth, and the existing notes,
specs, or tasks should be updated to reflect the new information from
IDEAS.md. DOCS-2 is required at this stage so we can merge a clean PR with all
github action CI tasks passing.

## Priority 90: Fully address ADR-0013 and OPP-06

`docs/adr/0013-unify-rm-state-tracking.md` was created to capture the decision to unify state
tracking for the RM lifecycle. As noted in `notes/state-machine-findings.md`,
there are a number of steps to be taken to fully implement this
decision. We need to clearly identify and execute those steps before we
proceed with the next priority. These need to be added to `notes/`, `specs/`,
and `plan/IMPLEMENTATION_PLAN.md` tasks as appropriate.

We should also capture references to OPP-06
in the relevant `notes/` files, and in `specs/` and in the implementation
plan.

This priority covers both *capturing* the tasks, requirements, and notes,
and *implementing* the changes needed to fully realize this aspect of the
design.

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
requirements. See `specs/prototype-shortcuts.md` for the prototype-stage
deferral policy.
