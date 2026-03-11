# Project Ideas

## ~~vultron/api/v2 needs to turn into a driving adapter layer~~

> *Captured in `notes/architecture-ports-and-adapters.md` (Design Note: Use
> Cases as Incoming Ports) and `specs/architecture.md` ARCH-01-002.*

~~The vultron/api/v2 module is currently a mix of domain logic and API routing.
It needs to be refactored to separate concerns and turn it into a proper
driving adapter layer that translates external inputs (HTTP requests) into
calls to the core domain logic. This will involve:~~

~~- `vultron/api/v2/backend/handlers` are ports / use cases that belong
  somewhere in `vultron/core`~~
~~- most of the rest of `vultron/api/v2` are basically driving adapters that
  will interface with the core use cases.~~
~~- Note the long-running distinction between "handlers" are dealing with
  messages received (someone else did something) vs "triggered behaviors" are
  locally-initiated actions is still relevant to use cases too, we need to
  distinguish between "received a message that foo accepted a report" vs "I
  accepted a report and now there are side effects that need to happen".
  (receipt can also have side effects, of course, as we've already worked
  out in the code.)~~

## ~~`vultron/api/v1` is really an adapter too.~~

> *Captured in `notes/codebase-structure.md` (API Layer Architecture section).*

~~The difference between `v1` and `v2` is that `v2` is driven by AS2 messages
arriving in inboxes, whereas `v1` is basically a direct datalayer access
backend for prototype purposes. `v2` is semantic, `v1` is more of a "get
objects" API. However, `v1` is still an adapter layer, just one that basically
talks almost directly to the backend data layer port. It still needs to be
refactored to fit the port and adapter design. There might be a very thin
core use case layer that it interfaces with, or if that's overkill, we could
just let it talk to the data layer port directly. `v1` is essentially an
administrative visibility and management API for development and testing
purposes, but we should still refactor it to fit the architecture we're
moving towards.~~

## ~~Discriminate Naming Conventions: FooActivity vs FooEvent~~

> *Captured in `specs/code-style.md` CS-10-002 and
> `notes/domain-model-separation.md` (Naming Convention section).*

~~Let's adopt a clear object naming convention for Pydantic classes that will
help us to distinguish between wire payloads and domain events.~~

~~- `FooActivity` will be reserved for use in `vultron.wire.as2.vocab.
activities` to represent the specific payloads that the wire layer
  recognizes  and extracts from incoming AS2 messages. These are
  the "intent" objects that the extractor produces based on the semantics of the
  incoming message.~~
~~- `FooEvent` will be reserved for use in `vultron.core.models.events` to
  represent the specific domain events that the core recognizes and that
  handlers will consume. These are the "domain events" that represent things
  that have happened in the system, either as a result of receiving a
  message or as a result of a local trigger.~~
  ~~- Subtypes include `FooReceivedEvent` for things that were received from the wire, and
    `FooTriggerEvent` for things that were locally triggered by an actor's
    action.~~

~~For example:~~
~~- `vultron.wire.as2.vocab.activities.report.RmSubmitReport` would be renamed
  to `vultron.wire.as2.vocab.activities.report.ReportSubmitActivity`~~
~~- a parallel domain event class in `vultron.core.models.events` would be
  named `SubmitReportReceivedEvent` to reflect that this is a domain event that
  the
  core recognizes.~~
~~- similarly, when there is a triggerable behavior, that would be
  `FooTriggerEvent` to di~~

~~Implications: Most of the classes in vultron.wire.as2.vocab.activities will
need to have "Activity" appended to their names to clarify that they are
wire-level payloads that the system recognizes. A number of new classes will
need to be created in vultron.core.models.events. It is likely that vultron.
core.models.events will need to be turned into submodules in an `events/`
directory to avoid overcrowding files with class definitions. Structure
should be similar to that of `vultron.wire.as2.vocab.activities/` with submodules
for each message semantics category (report, case, embargo, etc.).~~

~~The `Events` should inherit basic structure from a `VultronEvent` base class
that has a clear discriminator field based on the `MessageSemantics` enum
such that the extractor will know which specific event class to instantiate
based on the semantics pattern match, and then the handlers will be able to
reconstruct the proper subclass from the generic payload using Pydantic's
discriminator functionality. The "IncomingPayload" class is likely just a
rename-away from the "VultronEvent" base class, but we should take the time
now to eliminate it as a generic bag of data and replace it with less
generically named class(es) to ensure that things like type hints are
obviously referring to specific domain events rather than a generic payload.~~

## ~~Implementation Review Notes~~

> *Captured in `notes/domain-model-separation.md` (Discriminated Event
> Hierarchy / P65-3 Design section).*

~~Based on a review of the current specifications and the Phase
PRIORITY-65 implementation plan, there is a clear requirement to move from a *
*generic enriched payload** to a **discriminated domain event hierarchy**.~~

~~While **P65-3** (as defined in the plan) focuses on enriching a single
`InboundPayload` model to eliminate `raw_activity`, the new guidance argues that
this approach is insufficient and risks information loss. To ensure handlers
operate on specific, type-safe event objects (e.g., `ReportSubmittedEvent`)
rather than a generic bag of data, a new set of tasks must be inserted to
formalize the domain event model before the dispatcher is decoupled in **P65-4
**.~~

### ~~Identified Gaps and Ambiguities~~

~~* **Generic vs. Specific Domain Types**: **ARCH-01-002** requires core functions
  to accept "domain types only". The current P65-3 definition treats
  `InboundPayload` as a single domain type, but the "Refining..." note clarifies
  that the core needs **subclasses** that map 1:1 to `MessageSemantics` to
  properly expose use cases.~~
~~* **Discrimination Responsibility**: The note suggests using Pydantic's ability
  to discriminate subclasses based on a field (the `MessageSemantics`). P65-3
  currently lacks a task to implement this "model validation step" within the
  core.~~
~~* **Event Origin Discrimination**: The note identifies a need to distinguish
  between things "received elsewhere" (remote activities) and things "a local
  actor has done" (local triggers). The current `InboundPayload` does not
  explicitly differentiate between these two modes of entry into the core.~~

### ~~Recommended Changes to Phase PRIORITY-65~~

~~To resolve these issues before **P65-4** (which decouples the dispatcher), the
following tasks should be inserted as **P65-3a** and **P65-3b**.~~

#### ~~Insert Task: P65-3a — Define Discriminated Domain Event Hierarchy~~

~~* **Description**: Define a Pydantic-based event hierarchy in
  `vultron/core/models/events.py` that replaces or wraps the generic
  `InboundPayload`.~~
~~* **Concrete Steps**:~~
    ~~1. Create a base `VultronEvent` (or `DomainEvent`) model.~~
    ~~2. Define specific subclasses for each `MessageSemantics` entry (e.g.,
       `ReportSubmittedEvent`, `CaseUpdatedEvent`, `EmbargoProposedEvent`).~~
    ~~3. Implement a discriminator field using `MessageSemantics` to allow
       Pydantic to automatically reconstitute the correct subclass.~~
    ~~4. Distinguish between "Received" and "Triggered" event flavors in the
       naming and structure to separate local actions from remote receipts.~~

#### ~~Insert Task: P65-3b — Refactor Extractor and Handlers for Event Specificity~~

~~* **Description**: Update the wire-layer extraction logic to produce these
  specific event objects and update handler signatures to consume them.~~
~~* **Concrete Steps**:~~
    ~~1. Update `wire/as2/extractor.py:extract_intent()` to return a specific
       `VultronEvent` subclass instead of a generic `InboundPayload`.~~
    ~~2. Refactor every handler in `vultron/api/v2/backend/handlers/` to accept
       the specific event type relevant to its semantics (e.g.,
       `validate_report(event: ReportReceivedEvent, dl: DataLayer)`).~~
    ~~3. Update the `BehaviorHandler` protocol in `vultron/types.py` to reflect
       that `dispatchable.payload` is now a discriminated `VultronEvent`.~~

### ~~Updated Implementation Plan Sequence~~

~~The dependency chain in the plan should be updated as follows:~~

~~1. **P65-3 (Current)**: Enrich `InboundPayload` (audit `raw_activity` usage).~~
~~2. **P65-3a (NEW)**: Define Discriminated Domain Event Hierarchy.~~
~~3. **P65-3b (NEW)**: Refactor Extractor and Handlers for Event Specificity.~~
~~4. **P65-4**: Decouple `behavior_dispatcher.py` from the wire layer (now passing
   a fully validated, specific **Domain Event** instead of a generic payload).~~

~~This ensures that when **P65-4** is executed, the dispatcher is no longer just
a "dumb" router for a generic object, but is correctly handling a strongly-typed
domain event contract as intended by the hexagonal architecture.~~