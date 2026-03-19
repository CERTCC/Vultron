# Project Ideas

~~## Avoid backwards-compatible shims in prototype~~

~~As we build out the prototype, we must avoid adding backwards-compatible shims~~
~~to support old versions of the code. We need to be able to iterate quickly~~
~~and make changes to code without worrying about maintaining backwards~~
~~compatibility. Nobody outside of this project is dependent on the code as it~~
~~currently exists, and shims create technical debt that we have to clean up~~
~~later anyway. When we are refactoring something, a shim is appropriate to~~
~~confirm changes are working as expected during a test run, but they should~~
~~be removed immediately after the test run confirms the change works as~~
~~expected. Going back through the code and replacing calls to the old code~~
~~with calls to the new code is critical at these moments to avoid~~
~~accumulating technical debt for abandoned interfaces. This is not to say~~
~~that we should break existing code: it's saying that we should go all the~~
~~way with refactors to eradicate the old code and not leave it around with~~
~~shims that just add to the maintenance burden. If you're going to refactor,~~
~~finish the job while you're already in the middle of the code and have the~~
~~context fresh to understand what needs to be changed. Don't leave it for~~
~~later.~~

→ captured in notes/architecture-ports-and-adapters.md; AGENTS.md
~~## Outbox-Based Delivery Model (Event-Core, Activity Boundary)~~

~~This design introduces a transport-agnostic messaging model for Vultron that~~
~~enables Actors to communicate across process and organizational boundaries~~
~~without coupling core logic to delivery mechanics or external protocols. Actors~~
~~emit domain Events to an outbox, which are then deterministically mapped to~~
~~ActivityStreams Activities and delivered via a separate delivery service to~~
~~recipient actor inboxes over HTTP. This preserves a strict separation between~~
~~core domain semantics and transport representation, supports asynchronous and~~
~~location-transparent communication, and establishes a foundation for distributed~~
~~execution and eventual federation without requiring full ActivityPub ~~
~~compliance up front.~~

~~### Canonical Message Model~~

~~- **Core representation:** `Event` (globally standardized across all Actors)~~
~~- **Transport representation:** Activity using ActivityStreams~~

~~**Invariant:**~~

~~- Every inter-actor message is:~~

~~    - **Produced and consumed as an Event in core**~~
~~    - **Serialized as an Activity at the boundary**~~

~~The Event → Activity transformation is **purely structural**:~~

~~- No enrichment~~
~~- No recipient injection~~
~~- No semantic alteration~~

~~Recipients are part of the Event model and originate from domain logic (e.g.,~~
~~case participation).~~

~~### Core Model~~

~~#### Event Semantics~~

~~Events are:~~

~~- Globally defined (shared schema across all Actors)~~
~~- Addressed (`recipients: list[ActorID]`)~~
~~- Semantically meaningful (domain-level validation applies)~~

~~Example (conceptual):~~

~~```python~~
~~class Event:~~
~~    id: EventID~~
~~    type: EventType~~
~~    actor: ActorID~~
~~    recipients: list[ActorID]~~
~~    payload: dict~~
~~```~~

~~---~~

~~### Core Ports~~

~~- `OutboxPort.publish(event: Event) -> None`~~
~~- `InboxPort.receive(event: Event) -> None`~~

~~**Constraints:**~~

~~- Core is unaware of Activities, HTTP, or delivery mechanics~~
~~- Core assumes:~~

~~    - Events it emits are valid~~
~~    - Events it receives have passed syntactic transport checks but still~~
~~      require semantic validation~~

~~---~~

~~### Adapter Layer~~

~~#### Event ⇄ Activity Mapping~~

~~- **Event → Activity**~~

~~    - Direct mapping:~~

~~        - `actor` → `actor`~~
~~        - `recipients` → `to`~~
~~        - `payload` → `object`~~
~~        - `type` → Activity type (or embedded object type)~~
~~- **Activity → Event**~~

~~    - Reverse mapping~~
~~    - No interpretation beyond structure~~

~~This layer is the only place where ActivityPub-style constructs exist.~~

~~---~~

~~### Delivery Model~~

~~#### Delivery Service Responsibilities~~

~~Operates on Activities:~~

~~- Reads from outbox-backed Activity stream~~
~~- Resolves ActorID → inbox endpoint~~
~~- Performs HTTP POST to **actor inbox endpoints**~~
~~- Handles:~~

~~    - fan-out~~
~~    - retries~~
~~    - idempotency~~

~~**Key constraint:**~~

~~- Delivery targets **actor inboxes directly**, not a server-level inbox~~

~~---~~

~~### Validation Model (Critical Distinction)~~

~~There are two distinct validation layers:~~

~~#### 1. Transport-Level Validation (Adapter Layer)~~

~~Performed by Inbox HTTP adapter:~~

~~- Is this a valid Activity?~~
~~- Is required structure present?~~
~~- Is the recipient actor local?~~

~~Failures here:~~

~~- Reject immediately (HTTP error)~~
~~- No Event constructed~~

~~---~~

~~#### 2. Semantic Validation (Core)~~

~~Performed by Actor via `InboxPort.receive(event)`:~~

~~- Is the Event valid in current state?~~
~~- Is sender authorized?~~
~~- Is this transition allowed?~~

~~Failures here:~~

~~- Occur **after delivery**~~
~~- May produce compensating Events (e.g., rejection, error signaling)~~

~~---~~

~~### Server-Level Inbox (Deferred Design)~~

~~A **per-server inbox** is explicitly **not part of the current model**, but~~
~~recognized as a future option.~~

~~#### Tradeoff Identified~~

~~| Approach              | Advantage                              | Cost                                     |~~
~~|-----------------------|----------------------------------------|------------------------------------------|~~
~~| Direct-to-Actor Inbox | Immediate semantic validation feedback | No durable pre-validation buffer         |~~
~~| Server-Level Inbox    | Durable buffering, centralized routing | Cannot perform actor-specific validation |~~

~~#### Current Decision~~

~~- **Do not introduce a server-level inbox yet**~~
~~- Maintain:~~

~~    - Delivery Service → Actor Inbox (HTTP)~~
~~- Rationale:~~

~~    - All messages are effectively **DMs**~~
~~    - No distinction between public vs. private routing~~
~~    - Early semantic validation is more valuable than buffering~~

~~#### Future Option~~

~~A server-level inbox may later act as:~~

~~- Durable ingress queue~~
~~- Routing layer for local actors~~

~~But would require:~~

~~- Clear handling of deferred validation failures~~
~~- Possibly new Event types for rejection/acknowledgment~~

~~---~~

~~### End-to-End Flow (Finalized)~~

~~```id="r6r1bh"~~
~~[Core Actor]~~
~~   └── publish(Event)~~
~~           ↓~~
~~     OutboxPort~~
~~           ↓~~
~~ [Outbox Adapter / Event Store]~~
~~           ↓~~
~~ [Event→Activity Adapter]~~
~~           ↓~~
~~     Activity~~
~~           ↓~~
~~     Delivery Service~~
~~           ↓~~
~~   HTTP POST~~
~~           ↓~~
~~ [Actor Inbox HTTP Adapter]~~
~~   (transport validation)~~
~~           ↓~~
~~ [Activity→Event Adapter]~~
~~           ↓~~
~~     InboxPort.receive(Event)~~
~~           ↓~~
~~   (semantic validation)~~
~~           ↓~~
~~       [Core Actor]~~
~~```~~

~~---~~

~~### Architectural Invariants~~

~~1. **Event purity in core**~~

~~    - No leakage of ActivityStreams types~~

~~2. **Deterministic mapping**~~

~~    - Event ⇄ Activity is lossless and mechanical~~

~~3. **Explicit addressing**~~

~~    - Recipients originate in domain logic, not infrastructure~~

~~4. **Delivery decoupling**~~

~~    - Emission ≠ delivery ≠ acceptance~~

~~5. **Validation split**~~

~~    - Transport validation at boundary~~
~~    - Semantic validation in core~~

~~---~~

~~### Net Effect~~

~~This design:~~

~~- Preserves a strict **domain/protocol boundary**~~
~~- Introduces **outbox-driven delivery** without full federation complexity~~
~~- Keeps **actor-level validation authoritative**~~
~~- Leaves room for **future ingress buffering** without forcing it prematurely~~

~~Vultron Code Review — March 17, 13:45~~

~~Design Constraints & Invariants (add to docs if moving this review into design docs)~~

~~These are strict constraints and invariants extracted from the transcript that~~
~~should be captured explicitly in any design documentation produced from this~~
~~review. They are not soft recommendations — they are architectural constraints.~~

~~1. Core ≥ Wire: Core models MUST be as rich as or richer than wire models. Wire~~
~~   models are projections of core models only.~~
~~2. Fail-fast models: Domain events and models must validate required fields on~~
~~   construction and fail immediately if required invariants are missing.~~
~~3. ActivityStreams alignment: Actor profiles and any protocol-exposed objects must~~
~~   follow ActivityStreams semantics where specified (discovery endpoint, actor~~
~~   profiles, reply activity formats).~~
~~4. Adapter / Core boundary: Adapters own transport concerns and instantiate wire~~
~~   objects; they must provide domain-ready data objects to core (no transport~~
~~   logic in core).~~
~~5. Non-breaking BT migration: Changes to Behavior Trees must be initially import-layer~~
~~   refactors and non-breaking at runtime.~~
~~6. Dispatcher port preservation: Do not remove dispatcher port without a validated~~
~~   migration plan; its removal is uncertain and must be justified with tests.~~

~~Append these to the design-docs as a short, numbered list of invariants.~~

~~→ captured in notes/architecture-ports-and-adapters.md; specs/architecture.md (ARCH-09, ARCH-10)~~

→ captured in notes/architecture-ports-and-adapters.md
~~## VCR-0317~~

~~The items prefixed with VCR-0317-* are specific action items resulting from~~
~~a recent code review. They are not ordered by priority but are numbered for~~
~~reference.~~

~~Vultron code review Tuesday, March 17, 13:45 PM~~
→ captured in plan/IMPLEMENTATION_PLAN.md (Phase VCR-0317)

~~## VCR-0317-001~~

~~We do not need `vultron/adapters/driven/dns_resolver.py` at all.~~
~~That's left for a future, and it's~~
~~currently just a stub. That should go away.~~

→ captured in plan/IMPLEMENTATION_PLAN.md (VCR-001)
~~## VCR-0317-002~~

~~Some fraction of the outbox~~
~~management piece probably belongs in `vultron/adapters/driven/http_delivery.py`~~

→ captured in plan/IMPLEMENTATION_PLAN.md (VCR-003/..., Batch VCR-B)
~~## VCR-0317-003~~

~~There is a tension between the `vultron/adapters/driving/http_inbox.py` and ~~
~~the `vultron/api/v2`~~
~~Because really, the API V2 is an older wrapper around the HTTP inbox.~~
~~We should create a `vultron/adapters/driving/fastapi/` subpackage and move the ~~
~~inbound API v2 and http_inbox.py into there and consolidate as appropriate. ~~
~~The API is just an adapter. The routers and everything else that is not ~~
~~eliminated in the API v2 should just be part of the adapter.~~

→ captured in plan/IMPLEMENTATION_PLAN.md (Batch VCR-B)
~~## VCR-0317-004~~

~~The app.py can live in `vultron/adapters/driving/fastapi` as well. This will ~~
~~require updating pyproject.toml and project documentation.~~

→ captured in plan/IMPLEMENTATION_PLAN.md (Batch VCR-B)
~~## VCR-0317-005~~

~~We're going to need to add a HTTP endpoint to the API that that~~
~~allows discovery of an actor or actors on a service. So presumably, ~~
~~`/actors/<actor_id>/profile`~~
~~would return an activity pub style profile that includes things like where ~~
~~their inbox is, where their outbox is, normal things~~
~~that occur in an actual profile within activity streams. That should be an~~
~~available endpoint. I don't think we have that currently implemented. ~~
~~It will be~~
~~necessary for discovery of actors when we get to the multiparty multi server~~
~~implementation later on. ~~

→ captured in plan/IMPLEMENTATION_PLAN.md (VCR-005, Batch VCR-E)
~~## VCR-0317-006~~

~~`vultron/api/v2/backend/handler_map.py` is a shim that we don't need anymore. ~~
~~Check to see if anything uses it then clean it up.~~

→ captured in plan/IMPLEMENTATION_PLAN.md (VCR-006, Batch VCR-A)
~~## VCR-0317-007~~

~~`vultron/api/v2/backend/inbox_handler.py` might just belong in ~~
~~`vultron/adapters/driving/fastapi` and appears to serve the same purpose as the existing ~~
~~http_inbox.py. Those might be the same thing. It might be a merge.~~

→ captured in plan/IMPLEMENTATION_PLAN.md (Batch VCR-B)
~~## VCR-0317-008~~

~~Similarly, `vultron/api/v2/outbox_handler.py` is probably ~~
~~also the same as `vultron/adapters/driven/http_delivery.py`.~~

→ captured in plan/IMPLEMENTATION_PLAN.md (Batch VCR-B)
~~## VCR-0317-009~~

~~Essentially, we need to have a cleanup task that takes care~~
~~of the API V2 items once we get all of this into the architecture, because I~~
~~really, increasingly do not think that we need to have a separate API~~
~~module parallel to adapters. I think these are just adapters. ~~

→ captured in plan/IMPLEMENTATION_PLAN.md (Batch VCR-B)
~~## VCR-0317-010~~

~~The trigger~~
~~services in `vultron/api/v2/trigger_services/*.py` all have an `svc_` prefix ~~
~~on the function names. We should be consistent with elsewhere and use a ~~
~~suffix like `trigger` instead of a prefix. So instead of `svc_trigger_embargo`.~~

→ captured in plan/IMPLEMENTATION_PLAN.md (VCR-010, Batch VCR-D); AGENTS.md
~~## VCR-0317-011~~

~~Many of the functions in `vultron/api/v2/trigger_services/*.py` have a lot of similar code in them,~~
~~like the same sort of `try: request; except` certain errors. We ~~
~~should abstract those exception handlers out into a decorator on each of those ~~
~~functions that could catch those exceptions so that we don't have to repeat ~~
~~all of that try/except stuff everywhere. We can just put it into a wrapper. ~~
~~For example, in `trigger_services/embargo.py` and `report.py` and `case.py`, they ~~
~~all have the same sorts of things.~~

→ captured in plan/IMPLEMENTATION_PLAN.md (VCR-011, Batch VCR-D)
~~## VCR-0317-012~~

~~There's a number of models in `trigger_services/_models.py`~~
~~that appear to possibly duplicate things that are over in core models or core~~
~~models events checked for similarly named objects in those two places, combine~~
~~them when possible because most of those models probably belong in core,~~
~~although maybe some of them might be more wire level models, but they still~~
~~should be. ~~

→ captured in plan/IMPLEMENTATION_PLAN.md (VCR-012, Batch VCR-D)
~~## VCR-0317-013~~

~~Again, we need to make sure that we're capturing this. idea that the~~
~~core models are always as rich as or richer than the adapter wire models, and~~
~~they do have semantic overlap because the wire model is so closely related to~~
~~the core models.~~

→ captured in notes/architecture-ports-and-adapters.md; specs/architecture.md (ARCH-09-001)
~~## VCR-0317-014~~

~~`vultron/api/v2/data/actor_io.py` is probably not needed.~~
~~Very likely a relic of previous versions~~
~~when we had not yet separated the core models from the wire models.~~
~~ActorIO is just an inbox/outbox pair that catches inbound messages or sends ~~
~~outbound messages. They're really just lists of objects received or to be ~~
~~sent from an Actor's perspective.~~

→ captured in plan/IMPLEMENTATION_PLAN.md (VCR-014, Batch VCR-C)
~~## VCR-0317-015~~

~~### VCR-0317-015a~~

~~`vultron/api/v2/data/status.py` ~~
~~is a shim that needs to just go away in lieu of direct imports. ~~

~~### VCR-0317-015b~~

~~`vultron/api/v2/data/types.py` might not be used anywhere. It only contains ~~
~~unique key dict. If we don't have that anywhere, just get rid of types.py in ~~
~~that data directory. ~~

→ captured in plan/IMPLEMENTATION_PLAN.md (VCR-015a/b, Batch VCR-A)
~~## VCR-0317-016~~

~~`vultron/api/v2/data/utils.py` has a number of utilities that are probably ~~
~~better suited for core and exported out to wire than they would be to ~~
~~maintain in the API itself. Or maybe they are better suited to live in ~~
~~`vultron/adapters`. Decide this based on whether core has duplicative or ~~
~~similar needs. If core duplicates them, they belong in core. If they are an ~~
~~adapter only thing, then they belong in adapters.~~

→ captured in plan/IMPLEMENTATION_PLAN.md (VCR-016, Batch VCR-B)
~~## VCR-0317-017~~

~~`vultron/api/v2/routers` should become an adapter submodule ~~
~~underneath Vultron adapter's driving. And perhaps `vultron/adapters/driving` ~~
~~just gets a `fastapi` submodule, and that's where these things go~~
~~into. ~~

→ captured in plan/IMPLEMENTATION_PLAN.md (Batch VCR-B)
~~## VCR-0317-018~~

~~`vultron/api/app.py` belongs in `vultron/adapters/driving/fastapi` as well.~~
~~This will require updating `pyproject.toml`, possibly the demos, and project ~~
~~documentation.~~

→ captured in plan/IMPLEMENTATION_PLAN.md (Batch VCR-B)
~~## VCR-0317-019~~

~~### VCR-0317-019a~~

~~`vultron/case_states` has a whole slew of `enums` in a submodule, a set of ~~
~~patterns in a submodule, and a number of other modules, many of which ~~
~~also contain Enums. Almost everything in here belongs in core and should be ~~
~~adapted appropriately.~~

~~### VCR-0317-019b~~

~~Note that there are an entire hierarchy of errors in there as~~
~~well that can be integrated into the error hierarchy for core.~~

~~### VCR-0317-019c~~

~~There may in~~
~~fact be some duplicativeness in the enums that are in various case states, and~~
~~some of those enums are just duplicated in places or ~~
~~have too many similarities to something else. We should do a study task to ~~
~~investigate which enums might be consolidated with others to clarify things.~~
~~We should be careful though that we do not add items to the EM, RM, or CS ~~
~~models since they are pretty central to the protocol design.~~

~~### VCR-0317-019d~~

~~Further down the line, once we consolidate the enums and have them in core, ~~
~~we should consider whether to use the `transitions` module to actually ~~
~~properly model the RM, EM, and CS state machines. That's a future item though.~~

~~### VCR-0317-019e~~

~~In general, older enums were not using `StrEnums`. They were just normal ~~
~~python enums. We should consider replacing them with `StrEnum` where that ~~
~~makes sense so that we can~~
~~consolidate into newer python abilities there. ~~

~~### VCR-0317-019f ~~

~~If you go through `vultron/bt` you will find a number of modules named ~~
~~`states.py` inside embargo management, for example, inside messaging, inside ~~
~~report management and just at the top level of~~
~~the `vultron/bt` module. each of those `states.py` files very often contains ~~
~~Enums. Most of them do contain Enoms that also could be combined into~~
~~this Enum hierarchy that we're talking about over in core that really belong in~~
~~core. That's going to require modifying some other code in `vultorn/bt` just ~~
~~for imports. (Do not leave compatibility shims behind)~~

~~But that's okay as long as they maintain compatibility and we're not changing~~
~~those things yet. Some of those `vultron/bt/**/states.py` are used elsewhere in ~~
~~the code, and those things really belong in core. ~~

→ captured in plan/IMPLEMENTATION_PLAN.md (VCR-019a-f, Batch VCR-C)
~~## VCR-0317-020~~

~~Inside most of the `vultron/core/models/events` many of them~~
~~have an activity that's defined as a `VultronActivity | None`, which makes it~~
~~look like it's optional. I don't think in any case that those are ever optional~~
~~activities. And in fact, there should be kind of a base class, actually, the~~
~~`VultronEvent` base class should just contain a required activity because it's~~
~~going to have to include that. Even though some of those classes, like ~~
~~`AcceptInviteActorToCaseReceivedEvent` doesn't have an activity listed ~~
~~there, but I think those are actually supposed to have activities in them. ~~
~~This seems like it~~
~~might be a situation where the translation from activity streams at the ~~
~~adapter level is not necessarily coherent to what's inside the core. ~~
~~Again, core should~~
~~reflect everything that's available in activity streams.~~

→ captured in plan/IMPLEMENTATION_PLAN.md (VCR-020, Batch VCR-C); specs/architecture.md (ARCH-10-001)
~~## VCR-0317-021~~

~~### VCR-0317-021a~~

~~Similar comments for `case`, `particpant`, `embargo`, `note`, `report`, and ~~
~~`unknown` modules. For example, in the case of a `CreateReportReceivedEvent`,~~
~~report is not optional and activity is not optional, and in fact, activity can be further~~
~~specified as it must be a must be a `Create` event (`Create` activity on the ~~
~~wire side), depending  on which way that works. So the `VultronEvent` might ~~
~~have those as that object or~~
~~optional, but then the subclass should be more strict and say that this is not~~
~~optional, but the same type. ~~

~~### VCR-0317-021b~~

~~There is a `VultronActivity` class in `vultron/core/models/activity` that ~~
~~on the surface looks like it might be very close to the `VultronEvent` ~~
~~which exists in `vultron/models/events/base.py`~~

~~We need to deliberately choose whether these are actually different things ~~
~~or the same thing. Because really the `VultronEvent` was meant to be the ~~
~~parallel to the wire side AS2 activity objects or AS2 activities. So they should be similar~~
~~things and have a similar hierarchy, and I don't really think we need to have~~
~~the `VultronActivities` separate from `VultronEvent` unless there is a very ~~
~~clear and deliberate reason that we can document.~~

→ captured in plan/IMPLEMENTATION_PLAN.md (VCR-021a/b, Batch VCR-C)
~~## VCR-0317-022~~

~~Inside `vultron/core/models`, there are~~
~~still a bunch of classes that are inheriting directly from `BaseModel` as opposed~~
~~to inheriting from a single `VultronObject`, again, parallel to ~~
~~the AS2 object~~
~~activities in the activity streams wire models. These things really are~~
~~parallel. They need to be parallel. They need to have a very similar inheritance~~
~~hierarchy. There's no reason for us to be specifying  and resspecifying all ~~
~~of these as custom objects. Vultron case status, Vultron~~
~~embargo event, Vultron note etc. might be an extension of that base ~~
~~object.~~

~~So we really should be collecting all of these things that have common fields~~
~~and have those fields match the activity streams fields. Those should all track~~
~~directly into a single `VultronObject` class, and then `VultronEvent` inherits ~~
~~from `VultronObject`~~
~~as well as all of these objects also inherit from `VultronObject`,~~
~~and they should be as DRY as possible so that we are not repeating~~
~~fields like as_id, as_type, name, attributed_to, context, those sorts of ~~
~~things. When they're uniquely specific, they~~
~~should be in the subclass (e.g., when required in a subclass but optional in ~~
~~the parent, or perhaps otherwise restricted values in a subclass), but when ~~
~~they're common, they should just be optional~~
~~in the parent class, and then if they have to be required or restricted, they ~~
~~should be~~
~~specified as required in a child class. This will really help us tighten up~~
~~up this model hierarchy because there are a lot of places right now where we're~~
~~seeing classes that are inheriting directly from `BaseModel` and that's a code~~
~~smell that we should not be putting up with for much longer. ~~

→ captured in plan/IMPLEMENTATION_PLAN.md (VCR-022=TECHDEBT-16, Batch VCR-C)
~~## VCR-0317-023~~

~~There's a file `vultron/core/ports/delivery_queue.py` that looks ~~
~~like it might actually be the `emitter`~~
~~module or the start of an `emitter` module. I don't think we need both if we're~~
~~going to build an `emitter` module we can probably just get rid of the `delivery~~
~~queue`. (furthermore, `delivery queue` is more of an adapter name than a ~~
~~port name -- it implies implementation details that are unnecessary at the ~~
~~port level) I don't think it's used anywhere. It's mentioned in  ~~
~~`architecture-ports-and-adapters.md` but that might be an older design. So we should check~~
~~the `notes/` and `specs/` documentation and ensure that we are not providing ~~
~~design notes that are outdated compared to the current architecture. I can ~~
~~see that specifically around lines 365~~
~~through 384 of `architecture-ports-and-adapters.md`~~

→ captured in plan/IMPLEMENTATION_PLAN.md (VCR-023, Batch VCR-C); notes/architecture-ports-and-adapters.md
~~## VCR-0317-024~~

~~We don't need the DNS resolver port. ~~

→ captured in plan/IMPLEMENTATION_PLAN.md (VCR-024, Batch VCR-A)
~~## VCR-0317-025~~

~~We might not need the dispatch port anymore because I think the~~
~~use case port actually covers that.~~

→ captured in plan/IMPLEMENTATION_PLAN.md (VCR-025, Batch VCR-C)
~~## VCR-0317-026~~

~~We~~
~~should probably discriminate core ports into inbound (driven) versus ~~
~~outbound (driving). Prefer inbound/outbound for clarity. So the things like~~
~~data layer would be an outbound port. emitter would be an outbound port. Use~~
~~case is an inbound port. DNS resolver goes away, dispatcher goes away.~~

→ captured in plan/IMPLEMENTATION_PLAN.md (VCR-026, Batch VCR-C); notes/architecture-ports-and-adapters.md; specs/architecture.md (ARCH-11-001)
~~## VCR-0317-027~~

~~`vultron/core/use_cases/_types.py`~~
~~seems like perhaps it~~
~~actually belongs as a core models. Again, these look very close to those models~~
~~and might need to be integrated a little bit better so that we don't have~~
~~representations scattered throughout the code. ~~

→ captured in plan/IMPLEMENTATION_PLAN.md (VCR-027, Batch VCR-C)
~~## VCR-0317-028~~

~~There are some strangenesses in~~
~~the use cases where the `execute()` method has,~~

~~`if _idempotent_create(): return`~~
~~and then the method just ends, so you're just going to return either way so~~
~~there's no reason for the `if` block around the function call. Those should go ~~
~~away. ~~

→ captured in plan/IMPLEMENTATION_PLAN.md (VCR-028, Batch VCR-C)
~~## VCR-0317-029~~

~~Object where we know what the expected object is like SubmitReportEvent~~
~~should fail immediately on creation if the report is~~
~~not a Vultron report. So those shouldn't be optional ~~
~~with `| None`. They should just be required. Similarly, the semantics of most of these~~
~~received events just require the events to be fully populated. They genuinely~~
~~should fail at creation if those things are not there. (Generally avoid `| ~~
~~None` on core event model creation)~~

→ captured in plan/IMPLEMENTATION_PLAN.md (VCR-021b/VCR-029, Batch VCR-C)
~~## VCR-0317-030~~

~~The `vultron/sim` can be removed. It's no longer needed at all.~~

→ captured in plan/IMPLEMENTATION_PLAN.md (VCR-030, Batch VCR-A)
~~## VCR-0317-031~~

~~The top-level `behavior_dispatcher.py` appears to be a backward ~~
~~compatibility shim that can go away As~~
~~soon as all of its dependencies have been altered to use the original or the~~
~~correct locations~~

→ captured in plan/IMPLEMENTATION_PLAN.md (VCR-031, Batch VCR-A)
~~## VCR-0317-032~~

~~Similarly, `dispatcher_errors.py` can be merged into `errors.py` or as ~~
~~appropriate into `adapters/errors.py` etc. assuming it's used anywhere.~~

→ captured in plan/IMPLEMENTATION_PLAN.md (VCR-032, Batch VCR-A)
~~## Priority 100 pre-implementation Review~~

~~We also conducted a review of the requirements and blockers for Priority 100, ~~
~~which is currently the next big milestone on the implementation roadmap. The ~~
~~review here confirms that there is some pre-requisite work outstanding that ~~
~~needs to be captured in implementation notes and in the implementation plan, ~~
~~prioritized appropriately, and completed before starting work on P100.~~

~~**Date**: 2026-03-17~~
~~**Based on**: Implementation plan refresh #44, test suite 913 passing~~

~~---~~

→ captured in plan/IMPLEMENTATION_PLAN.md (PREPX-1, PREPX-2, PREPX-3, ACT-1 scope expansion)
~~## What Priority 100 Requires~~

~~From `plan/PRIORITIES.md`:~~

~~> Each actor exists in its own behavior tree domain. Actor A and Actor B~~
~~> cannot see each other's Behavior Tree blackboard at all. They can only~~
~~> interact through the Vultron Protocol by passing ActivityStreams messages~~
~~> with defined semantics.~~

~~The planned tasks are:~~

~~- **ACT-1** — Draft an ADR for per-actor DataLayer isolation (Option B:~~
~~  TinyDB namespace prefix as bridge; MongoDB community edition for production).~~
~~- **ACT-2** — Implement per-actor DataLayer isolation so that Actor A's~~
~~  DataLayer operations cannot affect Actor B's state.~~
~~- **ACT-3** — Update `get_datalayer` dependency injection and all handler~~
~~  tests to use per-actor DataLayer fixtures.~~

~~OUTBOX-1 is described as "logically falling under this priority" because it~~
~~enables actors to communicate, though it does not technically block ACT-1/2/3.~~

~~---~~

~~## Formal Blockers~~

~~**None.** The only stated blocker — PRIORITY-70 (DataLayer refactor into ports~~
~~and adapters) — is fully complete as of P70-2 through P70-5.~~

~~The `DataLayer` Protocol lives in `vultron/core/ports/datalayer.py` and~~
~~`TinyDbDataLayer` lives in `vultron/adapters/driven/datalayer_tinydb.py`.~~
~~The abstraction boundary required for per-actor isolation is in place.~~

~~---~~

~~## Known Open Tasks (from the Plan) That Should Precede P100~~

~~These are on the books in `plan/IMPLEMENTATION_PLAN.md` but not yet~~
~~complete. They are not technically blocking, but completing them first~~
~~will reduce friction during P100 implementation.~~

~~### High Impact (should complete before starting P100)~~

~~#### 1. BT Status String Comparisons in `core/use_cases/case.py`~~

~~`case.py` lines 84, 170, and 206 use the brittle pattern~~
~~`result.status.name != "SUCCESS"` (string comparison) instead of~~
~~`result.status != Status.SUCCESS` (enum comparison). These are the~~
~~`EngageCaseReceivedUseCase`, `DeferCaseReceivedUseCase`, and~~
~~`CreateCaseReceivedUseCase.execute()` methods — core logic that P100~~
~~testing will exercise directly when isolating per-actor case state.~~
~~This is currently listed as **Deferred** in the plan. It should be~~
~~promoted and completed.~~

~~**Fix**: import `from py_trees.common import Status` and replace the three~~
~~comparisons. One-line change per call site; no logic change.~~

~~#### 2. Remove the `handlers/__init__.py` Backward-Compat Shim Layer~~

~~`vultron/api/v2/backend/handlers/__init__.py` is an acknowledged shim~~
~~(see `plan/IMPLEMENTATION_NOTES.md`: "The handlers `__init__.py` is~~
~~pointless?"). It re-exports every use case as a thin wrapper around~~
~~`XxxReceivedUseCase(dl, event).execute()`. The only callers are two test~~
~~files (`test_handlers.py` and `test_reporting_workflow.py`), which also~~
~~use the deprecated `DispatchEvent` type. P100 work will introduce new~~
~~handler paths (per-actor dispatch); leaving this shim in place means any~~
~~P100 changes must be threaded through two layers instead of one.~~

~~**Fix**: Update `test_handlers.py` and `test_reporting_workflow.py` to~~
~~call use-case classes directly with `VultronEvent`; delete~~
~~`handlers/__init__.py` and `handlers/_shim.py`.~~

~~#### 3. Remove `DispatchEvent` / `InboundPayload` Backward-Compat Aliases~~

~~`vultron/types.py` marks `DispatchEvent` as deprecated (P75-2c).~~
~~`vultron/core/models/events/__init__.py` exports `InboundPayload` as a~~
~~backward-compat alias. Both are still consumed by the test files listed~~
~~above. Removing the shim layer (item 2) also enables removing these~~
~~aliases. Leaving deprecated types in the codebase conflicts with the~~
~~"no backward-compat shims in prototype" rule from~~
~~`plan/IMPLEMENTATION_NOTES.md`.~~

~~**Fix**: After removing the handler shim, remove the `DispatchEvent`~~
~~deprecated wrapper from `types.py` and the `InboundPayload` alias from~~
~~`core/models/events/__init__.py`.~~

~~### Medium Impact (complete during or immediately after P100 starts)~~

~~#### 4. OX-1.0 — Define `ActivityEmitter` Protocol Stub~~

~~`vultron/core/ports/emitter.py` does not exist. The `ActivityEmitter`~~
~~Protocol is the outbound counterpart to `core/ports/dispatcher.py`. It~~
~~is the formal port interface that driven delivery adapters (the queue~~
~~and HTTP delivery adapters) must implement. Without this stub:~~

~~- `CloseCaseReceivedUseCase` continues to construct wire-type activities~~
~~  directly (`VultronActivity(as_type="Leave")`) instead of emitting a~~
~~  domain event through the port — an architecture violation.~~
~~- OUTBOX-1 delivery work (OX-1.1 through OX-1.4) cannot use the correct~~
~~  port abstraction.~~
~~- P100 messaging (actors talking to each other) lacks a clean port~~
~~  boundary for outbound activities.~~

~~OX-1.0 is a small task: define the Protocol with an `emit(activity,~~
~~recipients)` method. The full delivery implementation (OX-1.1–1.4) can~~
~~follow; the stub alone is enough to unblock the architecture issue.~~

~~**Fix**: Create `vultron/core/ports/emitter.py` with the `ActivityEmitter`~~
~~Protocol. Reference `core/ports/dispatcher.py` as the structural model.~~

~~#### 5. DOCS-1 and DOCS-2~~

~~`docker/README.md` still describes per-demo containers that were~~
~~consolidated into a single `demo` service. `docs/reference/code/as_vocab/`~~
~~references old `vultron.as_vocab.*` module paths that no longer exist.~~
~~These are low-risk but `mkdocs build` surfaces errors and the Docker~~
~~README misleads anyone who runs the demos. Both should be resolved while~~
~~the rest of the team is not disrupted by P100 changes.~~

~~---~~

~~## As-Yet-Unrecognized Tasks That Should Be Completed First~~

~~These are not currently tracked in `plan/IMPLEMENTATION_PLAN.md` as~~
~~explicit to-do items.~~

~~### A. Per-Actor `get_datalayer` Dependency Injection Design~~

~~The current `get_datalayer()` in `datalayer_tinydb.py` is a zero-argument~~
~~singleton factory. P100 requires it to accept an `actor_id` argument and~~
~~return an actor-isolated instance. However, **every FastAPI route and~~
~~trigger endpoint** in `vultron/api/v2/routers/` injects it via~~
~~`Depends(get_datalayer)` — also without an `actor_id`.~~

~~Before ACT-2 (implementation), the DI strategy needs to be decided:~~

~~- Option 1: Change the FastAPI `Depends` expression to a closure that~~
~~  captures `actor_id` from the path parameter~~
~~  (`Depends(lambda actor_id: get_datalayer(actor_id))`).~~
~~- Option 2: Use a custom dependency class that inspects the request.~~
~~- Option 3: Thread `actor_id` through as an explicit function parameter~~
~~  rather than as a FastAPI dependency.~~

~~This is a foundational plumbing question that ACT-1 (ADR) must answer.~~
~~If it is left implicit, ACT-2 will make ad hoc choices across a dozen~~
~~route files and trigger endpoints. The ADR should explicitly address this.~~

~~Design-wise, Option 1 is the simplest and most explicit. It also satisfies ~~
~~the future need for actors to potentially be instantiated dynamically or in ~~
~~different execution context (e.g., actors running in separate containers as ~~
~~in the upcoming multi-actor demo scenarios.) ~~

~~Option 2 is more complex and opaque and does not provide any clear benefits ~~
~~over Option 1. ~~
~~Option 3 is the most explicit but also the most verbose and least elegant.~~

~~### B. `actor_io.py` Role Clarification~~

~~`vultron/api/v2/data/actor_io.py` is an in-memory inbox/outbox store~~
~~(a dict of `ActorIO` objects, each with inbox and outbox `Mailbox`~~
~~instances). It is currently used by:~~

~~- `routers/actors.py` — GET inbox, POST to inbox, POST to outbox.~~
~~- `api/v2/backend/inbox_handler.py` — dequeue and process inbox items.~~
~~- Demo setup utilities.~~

~~This module predates the DataLayer port abstraction. It is:~~

~~- In the wrong layer (`api/v2/data/` rather than `adapters/`).~~
~~- Not backed by the DataLayer (state is not persisted).~~
~~- Not per-actor in the isolation sense P100 requires.~~

~~P100 will need to either:~~

~~1. Migrate `actor_io.py` into the per-actor DataLayer (each actor's inbox~~
~~   and outbox stored as first-class collections in TinyDB), or~~
~~2. Formalize `actor_io.py` as a separate in-process queue driven adapter~~
~~   and wire it to the `ActivityEmitter` port (OX-1.0/1.1 design).~~

~~This decision directly affects ACT-2 scope. It is not captured as a~~
~~distinct task anywhere in the plan. It should be added to the ACT-1 ADR~~
~~scope.~~

~~### C. TECHDEBT-16 Has Become More Relevant~~

~~`TECHDEBT-16` (add a `VultronObject` base class to DRY the core domain~~
~~models) is currently rated "low priority." However, P100 will introduce~~
~~per-actor domain objects (actor-scoped state records). Without a shared~~
~~`VultronObject` base, P100 domain classes will inherit directly from~~
~~`BaseModel` and repeat the same identity and timestamp fields that every~~
~~other domain object repeats. This is also adjacent to the unresolved~~
~~domain-model separation work noted in `notes/domain-model-separation.md`.~~

~~This task does not block P100, but doing it concurrently with ACT-2 will~~
~~reduce later refactoring cost.~~

~~---~~

~~## Cleanup That Should Be Done Before P100~~

~~These items are acknowledged debt that will accumulate interest if left~~
~~until after P100 increases the codebase surface area.~~

~~| Item | File(s) | Risk if deferred |~~
~~|------|---------|-----------------|~~
~~| BT status string comparisons | `core/use_cases/case.py` (3 sites) | Tests testing per-actor case engagement will use brittle comparisons |~~
~~| `handlers/__init__.py` shim | `api/v2/backend/handlers/` | P100 handler changes must be reflected in two places |~~
~~| `DispatchEvent` deprecated alias | `vultron/types.py` | Deprecated API in active test use; accumulates as tests are added |~~
~~| `InboundPayload` alias | `core/models/events/__init__.py` | Same as above |~~
~~| OX-1.0 `ActivityEmitter` stub | `core/ports/emitter.py` | Architecture violation in `CloseCaseReceivedUseCase` |~~
~~| DOCS-1 docker README | `docker/README.md` | Developer confusion in demo environment |~~
~~| DOCS-2 docs module paths | `docs/reference/code/as_vocab/` | `mkdocs build` errors obscure real warnings |~~

~~---~~

~~## Overall Readiness Assessment~~

~~**P100 is ready to begin.** The foundational prerequisites (DataLayer~~
~~port/adapter separation, hexagonal architecture, use-case interface~~
~~standardization) are complete. The 913-test baseline is clean.~~

~~**However**, three issues should be resolved before the first P100 commit~~
~~lands in main:~~

~~1. **BT status comparisons** (deferred item, ~5 lines) — trivial fix, do~~
~~   it now before P100 case-engagement code is written.~~
~~2. **`handlers/__init__.py` shim removal** (medium effort, isolated) —~~
~~   removes an architectural layer that P100 changes would otherwise have to~~
~~   maintain.~~
~~3. **`get_datalayer` DI strategy** (design decision, no code yet) — this~~
~~   must be captured in the ACT-1 ADR before ACT-2 implementation begins, or~~
~~   ACT-2 will make inconsistent choices across route files.~~

~~**Additionally**, the ACT-1 ADR scope should explicitly include:~~

~~- The `actor_io.py` role clarification (inbox/outbox ownership and~~
~~  persistence model).~~
~~- The `get_datalayer` FastAPI DI pattern for per-actor injection.~~
~~- Whether OUTBOX-1 delivery is in-scope for P100 or deferred to after~~
~~  per-actor DataLayer isolation is proved out.~~

~~---~~

~~## Summary Checklist~~

~~### Before starting P100 implementation (ACT-2)~~

~~- [ ] Fix `result.status.name != "SUCCESS"` comparisons in~~
~~  `core/use_cases/case.py` (3 sites). *(~5 min)*~~
~~- [ ] Draft ACT-1 ADR covering: TinyDB namespace prefix vs MongoDB,~~
~~  `get_datalayer` DI pattern, `actor_io.py` inbox/outbox ownership, and~~
~~  OUTBOX-1 scope boundary. *(1 session)*~~
~~- [ ] Remove `handlers/__init__.py` shim layer; update the two test files~~
~~  that depend on it. *(1 session)*~~
~~- [ ] Remove `DispatchEvent`/`InboundPayload` deprecated aliases once~~
~~  shim removal is done. *(~15 min after above)*~~
~~- [ ] Create `vultron/core/ports/emitter.py` — `ActivityEmitter` Protocol~~
~~  stub (OX-1.0). *(~30 min)*~~

~~### Before completing P100 (can overlap with ACT-2/3)~~

~~- [ ] DOCS-1 — Update `docker/README.md`.~~
~~- [ ] DOCS-2 — Fix `docs/reference/code/as_vocab/` module paths.~~
~~- [ ] TECHDEBT-16 — `VultronObject` base class in core models (optional~~
~~  but recommended for cleanliness).~~

→ captured in plan/IMPLEMENTATION_PLAN.md (PREPX-1, PREPX-2, PREPX-3, ACT-1 scope)
