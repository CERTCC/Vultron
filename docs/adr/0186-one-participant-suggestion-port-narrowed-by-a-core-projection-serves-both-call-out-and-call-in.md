---
status: proposed
date: 2026-11-09
created: 2026-11-09
updated: 2026-11-09
revision: 2
lint_suppress: [phantom_symbol_ref, phantom_path_ref]
deciders: Allen D. Householder
consulted: Claude Opus 5.5
informed: []
stakeholder_type: [project-contributor]
---

# One Participant-Suggestion Port, Narrowed by a Core Projection, Serves Both a Call-Out and a Call-In Caller

## Context and Problem Statement

A case often needs parties nobody has invited yet: a vendor whose product is affected, a coordinator with reach into a sector.
Idea #1142 described a Retriever-plus-Evaluator workflow that finds them.
ADR-0047 put the trigger for that work behind a call-in Sentinel, and ADR-0097 split the work in two: the search is a capability, and the monitor that decides when to run it is a Sentinel.
Task #3426 then planned the search as a composite call-out point.

Two questions were left open.
A highly automated actor may want to ask "who else should be in this case?" from inside its own tree, while a Sentinel asks the same question from outside core.
Do they need two interfaces?
And what case information may the answering service see, when much of a case is under embargo?

The word "discovery" was also misleading.
The answer is a suggestion with a reason, not a definitive fact, and the codebase already used "actor discovery" for something else: resolving one actor URI to its profile.

## Decision Drivers

- Core should state what it requires from the answering service, without building a directory or recommender service now.
- The same question, asked from a tree or from a Sentinel, should have one answer shape, so an adapter is written once.
- Which embargoed case information leaves the actor is a disclosure decision.
  It should be made once and tested once, not re-made by every adapter.
- An answering service built outside Vultron, for example one that reads CSAF, should be able to sit behind the interface without core knowing its format.
- Call-out points answer synchronously within a bounded budget (ADR-0097).

## Considered Options

### For the interface

1. **A composite call-out capability only** (#3426 as first filed).
   The question is a Retriever with typed blackboard ports, reachable only from a tree.
2. **No core interface.** Suggestion lives entirely beside the Sentinel, and core's only contract is the `suggest-actor-to-case` trigger.
3. **One core driven port with two callers.** A thin call-out wrapper uses it inside a tree, and a Sentinel uses the same port from outside.

### For where the case is narrowed

1. **The adapter narrows.** The port takes the whole case, and each adapter picks the fields it sends on.
2. **Core narrows.** The port takes a core-owned suggestion context, and one core projection builds it from the case.

### For the shape of the suggestion context

1. **A subclass of the case** that hides the fields it does not carry.
2. **A free-standing model** whose fields bear no checked relation to the case.
3. **A case profile**: its own model, whose fields are a checked subset of the case's, built from a case.

## Decision Outcome

### 1. One driven port, two callers

<a id="one-port-two-callers"></a>

Chosen: **option 3**.
A ParticipantSuggestionPort in `vultron/core/ports/` answers "given this case context, who would you suggest, and why?".
One core service projects the case and asks the port.
A thin Retriever call-out wraps that service for inline use in a tree.
A Sentinel calls the same service and fires `suggest-actor-to-case` for each suggestion it accepts.

Option 1 was rejected because it makes the question reachable only from a tree, so a Sentinel would need a second interface for the same answer.
Option 2 was rejected because it leaves core with no statement of what it needs, which is the thing this work exists to learn, and it rules out an automated actor asking the question inline.

The call-out wrapper is still bound by ADR-0097: it answers within the configured budget.
An adapter too slow for that budget is reachable only through the Sentinel, which is not bound by a tick.

### 2. Core narrows the case before the port sees it

<a id="core-owned-projection"></a>

Chosen: **core narrows**.
The port's signature takes a core-owned suggestion context, not the case.
One core projection builds the context from the case, and every caller reaches the port through it.

The adapter-narrows option was rejected because each new adapter would make the disclosure decision again, and one careless adapter would leak the whole case.
With a core-owned context type, an adapter cannot send what it never receives, and widening the context is a visible change to a core type.

### 3. The suggestion context is a declared profile of the case

<a id="case-profile"></a>

Chosen: **a case profile**, not a subclass of the case and not a free-standing shape.
A case profile is its own model class, whose every field has the name and type of a field of the case or of an object the case holds.
The class builds itself from a case (`from_case(case)`), so the projection is a defined object with one constructor, not a loose function over a case.
The profile carries two things, and the suggester needs both.
The reports' descriptive content is the evidence: a report may name vendors and products that are not yet in the case, and finding those parties is the point of the port.
The participants are who is already included: each keeps its actor id and roles and nothing else, and the case's current vendors are the participants holding the VENDOR role.
Nested objects are profiled the same way as the case.

A subclass was rejected because it fails open.
It is a case, so it inherits every field, including one added to the case later, and any code that takes a case would take it.
A profile fails closed: a new case field reaches it only when someone declares it there, and a ratchet checks that its fields remain a subset of the case's.

The profile is a reusable pattern.
The suggestion context is its first use; a CSAF adapter, a Sentinel's view of a case, or publication may declare their own profiles the same way.

### 4. A suggestion names an identity, and nothing about timing

<a id="identity-only-suggestion"></a>

Each suggestion carries an actor id, a suggested role and a rationale, and an answer may be empty.
The suggestion carries no timing.
Scheduling an invite against the invitee's published embargo policy and the case's remaining embargo belongs to whoever receives the suggestions, which keeps the suggester a pure question of identity.

### 5. Names

<a id="names"></a>

The new interface is **ParticipantSuggestion**, matching the `suggest-actor-to-case` trigger that consumes its output.
The existing actor-discovery call-out, which resolves an actor URI to a profile, is renamed **ActorResolution**, so the two are not confused.

### Consequences

- Good, because one adapter serves both callers, and the demo can use a static adapter that answers from a declared table while the port's shape settles.
- Good, because a CSAF-speaking suggester becomes an adapter that turns the suggestion context into a CSAF document, and core never depends on CSAF.
- Good, because the disclosure decision has one home and one test.
- Bad, because core owns one more type, and an adapter that wants richer input has to argue for it as a change to core.
- Neutral, because a deployment that points the port at a third-party service is making a trust decision the port cannot make for it.
  The port's documentation says so.

## Validation

The requirements in `specs/behavior-tree-integration.yaml` group BT-24 state the rules this record decides.
A ratchet that no caller reaches the port except through the projection, and a test that the static demo adapter drives the 5-party scenario's second-vendor suggestion, are the checks the implementation adds.

## More Information

- Source: Idea #1142; reshapes Task #3426.
- Related: ADR-0026 (CASE_MANAGER-routed suggestion), ADR-0029 (`suggest-actor-to-case`), ADR-0047 (Sentinel over inline loop), ADR-0097 (capability layer), ADR-0183 (backend answers yes, no or error).
- Generated spec requirements: `behavior-tree-integration.yaml` BT-24-001 through BT-24-009.
