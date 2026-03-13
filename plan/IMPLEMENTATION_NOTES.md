## Implementation Notes

Longer-term notes can be found in `/notes/*.md`. This file is ephemeral
and will be reset periodically, so it's meant to capture more immediate
insights, issues, and learnings during the implementation process.

Add new items below this line

---

### 2026-03-11 — Refresh #24 findings

**P65 fully complete**: All tasks P65-1 through P65-7 are confirmed complete by
code inspection. V-01 through V-23 are all resolved. See `IMPLEMENTATION_HISTORY.md`
for details.

**`notes/architecture-review.md` is stale**: The status block and per-violation
markers still show V-03-R, V-15–19, and V-22–23 as open or partial. These were
resolved by P65-4, P65-6b, and P65-7 respectively. ARCH-DOCS-1 task added.

**New violation V-24**: `vultron/wire/as2/vocab/examples/_base.py` imports
`DataLayer` from `vultron.api.v2.datalayer.abc` at module scope, and also
imports `Record` and `get_datalayer` from `api/v2/datalayer/` inside
`initialize_examples()`. This makes the wire layer dependent on the adapter
layer — a Rule 1 violation. Captured in TECHDEBT-13b.

**Residual V-23**: `test/core/behaviors/report/test_policy.py` still imports
`VulnerabilityReport` from `vultron.wire.as2.vocab.objects.vulnerability_report`.
Tests pass (duck-typing), but the import violates the rule that core tests must
not use wire-layer types as fixtures. Captured in TECHDEBT-13a.

**TYPE_CHECKING imports in top-level modules**: `vultron/types.py` and
`vultron/behavior_dispatcher.py` both have `TYPE_CHECKING` guards importing
`DataLayer` from `vultron.api.v2.datalayer.abc` (the backward-compat shim).
These should import from `vultron.core.ports.activity_store` directly.
Captured in TECHDEBT-13c.

**`api/v2` → `core/use_cases/` migration (PRIORITY-75)**: The 38 handlers
(2223 lines) in `api/v2/backend/handlers/` and the trigger services (1188 lines)
in `api/v2/backend/trigger_services/` contain domain logic that belongs in
`core/use_cases/`. The `core/use_cases/__init__.py` stub docstring already
describes the intent: "Incoming port: domain use-case callables." Migration
requires domain event types (`VultronEvent`) first (P75-1), then handler
extraction (P75-2), then trigger service extraction (P75-3), then updating
driving adapter stubs to call use cases directly (P75-4).

**api/v1 is already architecturally compliant**: All v1 routers return
`vocab_examples.*` results with no business logic. They are already thin HTTP
adapters over `wire/as2/vocab/examples/`. The only decision needed is whether
to keep, merge, or deprecate (P75-5).

**P70 needs P70-4 and P70-5**: Moving TinyDB from `api/v2/datalayer/tinydb.py`
to `adapters/driven/activity_store.py` (P70-4) and removing the backward-compat
shims (P70-5) were missing from the plan. Added in refresh #24.

**`vultron_types.py` split**: `vultron/core/models/vultron_types.py` bundles
11 domain classes in 273 lines. `notes/codebase-structure.md` recommends
splitting into per-type modules (like `wire/as2/vocab/objects/`). Low-priority
organizational improvement captured as TECHDEBT-14.

**`use_cases` directory**: `vultron/core/use_cases/__init__.py` exists with a
stub docstring but contains no implementations. Driving adapter stubs
(`http_inbox.py`, `mcp_server.py`) reference `core/use_cases/` as the
future home for use-case callables. No actionable task yet — this will come
with the hexagonal architecture maturing (PRIORITY 70+).

## Renamed activity_store

`core/ports/activity_store.py` was renamed to `core/ports/datalayer.py` to  
reflect the broader scope of the port.

`adapters/driven/activity_store.py` was renamed to 
`adapters/driven/datalayer-tinydb.py` to reflect the specific  
implementation and avoid confusion with the port. (Eventually when we get to 
having a mongo-db implementation we will want to make 
`adapters/driven/datalayer` into a package with `tinydb.py` and `mongodb.py` 
as modules.)

## docker README out of date

`docker/README.md` is out of date and needs to be updated to reflect the 
currently available services and how to run them.

## Previous refactors broke documentation generation

There are python inline code blocks in `docs/` that broke when the 
`as_vocab` modules got moved into `wire/as2/vocab/`.
These need to be updated to reflect the new paths. By building the site 
using `mkdocs build` to detect errors.

## Core models must not be less rich than wire models

Because we have been in the process of separating core models from the wire 
models (they're semantically identical but we need to maintain the 
separation to maintain architectural integrity), we're frequently running 
into situations where the core model is less rich than the wire model, and 
so we're piecemeal adding features to core models to reflect things we left 
out of the translation from wire to core models. This is a code smell that 
suggests we need to invert our thinking here: the core models need to be the 
rich, fully featured models that capture all the domain semantics, and the 
wire models should ensure translation from/to syntax to/from the core models.
This is a recurring problem in recent implementation steps, and it would be 
better if we resolve it once by enriching the core models, then refactoring 
the wire models to provide the necessary syntactic translation, rather than 
continuing to add individual features to the core models as we encounter 
them. This should be captured as a technical debt item to be resolved as 
soon as possible as it will head off a lot of future code-level challenges.

## Important notes after P75-2 and bfore P75-3

`vultron/api/v2/backend/handlers` is no longer serving much of a purpose. 
The expectation here is that `vultron.api.v2.backend.inbox_handler.
inbox_handler()` would lookup the use case function to call in the 
dispatcher and call use case objects directly. Right now 
So for example, on receipt of an `AddNoteToCaseActivity`, the inbox  handler 
would know to create an `AddNoteToCaseReceivedEvent`. It seems like this 
hinges on `prepare_for_dispatch()`, and the DispatchActivity class. Ideally, 
instead of passing wire activity and wire object into the dispatch message, 
the DispatchActivity would be constructing a core event object. Consider 
renaming DispatchActivity to DispatchEvent to make it clear that it carries 
a core event model, not a wire activity model. We should be careful in our 
naming to be consistent that "Activity" is a wire-level concept and "Event" 
is a core-level concept. (There is some tension with "EmbargoEvent" being an 
object based on an "Event" object in the AS2 vocabulary), but we just need 
to be careful around that naming where it matters.

This may require changes to `extract_intent()` or at how it is used in 
`prepare_for_dispatch()`. Part of the problem here seems to be that we 
created the dispatcher before we really understood the wire vs domain model 
separation, so it seems as if there is some extra complexity in the dispatch 
message construction because of this. With the previous note about core 
models needing to be the rich models, it seems like there is a more direct 
way for DispatchActivity objects to be constructed with core object events 
not really needing the wire objects at all (this means that we really need 
to ensure that the core models capture the full content of what's coming in 
from the wire models, even if we're not yet using all the features in the 
wire models yet. Consider: any activity or object can have a "content" field 
that we might not show being used in our examples yet, but we need to make 
sure it gets passed through from wire to core.)


Implications: 
- the pattern objects in `extractor.py` should be suffixed with 
Pattern to clarify their purpose and distinguish them from similarly named 
Activity and Event objects.

---

## 2026-03-13 — Dispatch/Emit architecture clarification (refresh #31)

### Dispatch vs Emit terminology

Two distinct port concepts exist for activity flow:

- **Dispatch** = inbound: wire activity received → core use case invoked.
  This is a **driving port** — the core *exposes* an interface that adapters
  (HTTP inbox, CLI, MCP) call into. The `ActivityDispatcher` Protocol should
  live in `core/ports/dispatcher.py` alongside `DataLayer`.

- **Emit** = outbound: core action → wire object sent to recipient(s).
  This is a **driven port** — the core calls *out* to an external system that
  delivers the activity. A future `ActivityEmitter` Protocol belongs in
  `core/ports/emitter.py` (or similar). The delivery-queue adapter would
  implement it. This is distinct from, but complementary to, the
  `delivery_queue.py` port already sketched — the emitter port is the
  use-case-facing interface; delivery queue is the transport implementation.

Keep these terms consistent throughout code, comments, specs, and docs:
"dispatch" for inbound routing into use cases, "emit" for outbound sending.

### Post-P75-2 architecture findings (context for P75-2a/b/c)

**DispatchActivity carries wire objects**: `DispatchActivity` in `vultron/types.py`
has `wire_activity: Any` and `wire_object: Any` fields. These leak wire types into
the dispatch envelope and into use case signatures. Use cases in
`core/use_cases/` still accept `wire_object=None` kwargs. This is resolved by
P75-2a (enrich domain models) + P75-2b (remove wire fields).

**DispatchActivity → DispatchEvent rename**: "Activity" is a wire concept;
the dispatch envelope carries a `VultronEvent` domain payload. Rename to
`DispatchEvent` in P75-2b. Be careful around `EmbargoEvent` (an AS2 object
type, not a `VultronEvent` subclass) — the naming is coincidental and should
be clearly distinguished in documentation.

**Handler layer is vestigial after P75-2**: The 2–3-line delegate functions in
`vultron/api/v2/backend/handlers/` are the only remaining purpose of that
layer (plus `@verify_semantics`). Eliminate in P75-2c by mapping
`SEMANTICS_HANDLERS` directly to use case callables.

**SEMANTICS_HANDLERS belongs in core**: The routing table maps domain concepts
(`MessageSemantics`) to domain callables (`core/use_cases/`). It is domain
knowledge, not adapter configuration. Move to `core/use_cases/use_case_map.py`
as part of P75-2c.

**ActivityDispatcher as driving port**: Move Protocol from `vultron/types.py`
to `core/ports/dispatcher.py`. This makes the inbound dispatch interface
explicit and injectable (for testing). Concrete implementation moves to core
(or a driving adapter); the inbox handler injects it rather than using the
module-level singleton.

**Pattern naming inconsistency**: `ActivityPattern` instances in
`SEMANTICS_ACTIVITY_PATTERNS` in `extractor.py` have names like `CreateReport`,
`EngageCase` — identical to Activity and Event class names. Add `Pattern` suffix
(`CreateReportPattern`, etc.) in P75-2c.

## Separation of responsibilities

Core receives semantically meaningful events via use case callables, which 
are exposed via driving ports. Driving adapters are responsible for 
translating their specific input syntax into core domain events and calling 
the appropriate use case. Core processes the event, performs domain logic, and
emits semantically meaningful events via the emitter port. Driven adapters are
responsible for translating the emitted domain events into the appropriate output
syntax and delivering them to the appropriate recipients.

## DRY up vultron.core.models.vultron_types and vultron.core.models.events

There is some redundancy between the domain models in `vultron.core.models.vultron_types`
and the domain event models in `vultron.core.models.events`. This really 
should be a single class hierarchy that captures common fields in a 
`VultronObject` base class that `VultronEvent` can inherit from, and the 
other models in `vultron_types` can also inherit from `VultronObject`. In 
general, we shouldn't have a lot of direct inheritance from `pydantic.
BaseModel` in our domain models, instead we should have our own base class 
or classes that inherit from `BaseModel` and capture all the common fields 
so that our domain models can inherit from those and just have their 
specific details and fields where needed. This is very much parallel to the 
class hierarchy in the wire layer where there is an `as_Base` -> `as_Object` 
-> `as_Activity` etc. hierarchy. This parallel is deliberate, as the Vultron 
object and event models are meant to be rich domain data models that can be 
expressed in the wire layer with the appropriate syntactic translation.

## Flaky test is technical debt

The test `test/wire/as2/vocab/test_vocab_examples.
py::TestVocabExamples::test_remove_embargo` has been identified as flaky. 
This is a technical debt item that should be resolved as soon as possible as 
we must not have flaky tests in our suite. The test should be inspected to 
determine the root cause of the flakiness, and refactored to be reliable.
Add new TECHDEBT item to capture this, prioritize its resolution accordingly,
and add an item in `specs/testability.md` requiring that all tests must be 
reliable and consistent.

## Avoid "connectors" as adapters, keep clean driving vs driven adapter separation

Avoid using `vultron.adapters.connector` as a dumping ground for 
code that doesn't fit neatly into the driving vs driven adapter categories. 
Driving is for incoming data and events, driven is for outgoing data and 
events. Some integrations will of course require bi-directional flow. If both 
are needed 
for a 
particular integration, that's fine, 
but we 
should avoid blending the two in a single module or class. Instead, just 
have a `vultron.adapters.driving.foo` and a `vultron.adapters.driven.foo` 
module for that integration, and keep the directionality cleanly separated. 
This will help maintain architectural integrity and keep the code 
well-organized. 

## Markdownlint errors must be resolved

Markdownlint errors in `notes/`, `specs/`, `plan/` must be resolved. Also 
note that the `ignore` directives in `.markdownlintignore` and `.
markdownlint-cli2.yaml` have been modified to no longer ignore these 
directories. Adjust guidelines in `AGENTS.md` and elsewhere to reflect the 
change.

