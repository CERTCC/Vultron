# Architecture Spec

## Overview

This project follows **Hexagonal Architecture** (also called Ports and
Adapters). The core domain logic is completely isolated from the outside world.
All external systems interact with the core through defined boundaries called
**ports**, via thin translation layers called **adapters**.

Additionally, this project has a **wire format layer** that sits outside the
domain entirely. This layer is explicitly separate from domain logic because the
domain vocabulary and the wire format happen to share semantics — a property
that must not be allowed to collapse the boundary between them.

---

## The Key Distinction: Wire Format vs. Domain Semantics

### How we got here

The case management domain was designed first, with its own semantic
vocabulary (cases open, participants join, ownership transfers, etc.). When
looking for a wire format for federation, Activity Streams 2.0 was found to have
a **1:1 semantic match** with the domain vocabulary. AS2 was adopted as the wire
format on that basis.

This is important context: AS2 was chosen *because* it matched the domain, not
the other way around. The domain does not depend on AS2. AS2 is a wire format
that happens to express the same concepts.

See `notes/federation_ideas.md` for more on the
distinction between the use of AS2 vocabulary and ActivityPub the protocol.

### Why the boundary still matters

Because the semantic match is so clean, it is tempting to let AS2 types leak
into domain code. This must be resisted for two reasons:

1. **Wire formats change.** AS2 is the current wire format. A future protocol, a
   binary encoding, or a revised federation standard should be replaceable
   without touching domain logic. If AS2 types are in the domain, that becomes
   impossible.

2. **Parsing concerns are not domain concerns.** Whether a JSON document is
   structurally valid AS2, whether a `@context` is present, whether an activity
   type is a known extension — these are wire layer questions. The domain should
   never see a malformed or ambiguous input. That filtering happens before the
   domain is invoked.

---

## Layer Model

There are four layers at the inbound boundary and three at the outbound
boundary.

### Inbound

```text
1. AS2 JSON (wire)
        ↓
2. AS2 Parser
   "Is this structurally valid AS2?"
   Produces: AS2 Pydantic types (structural, no semantics)
        ↓
3. Semantic Extractor
   "What does this mean in domain terms?"
   Matches AS2 message patterns → SemanticIntent enum value
   e.g. Offer{object: Report} → InboundReportOffer
        e.g. Accept{object: Case} → OwnershipTransferAccepted
        ↓
4. Handler Dispatch
   SemanticIntent → handler function
        ↓
5. Domain Logic
   Operates on Case, CaseActor, Participant, etc.
   No AS2 awareness.
```

### Outbound

```text
1. Domain Logic
   Operates on Case, CaseActor, Participant, etc.
   Emits domain events.
        ↓
2. AS2 Serializer
   Translates domain events → AS2 activity objects
   Applies journalSeq, journalPrev, relay wrapping, signing
        ↓
3. AS2 JSON (wire)
   Delivered via outbound HTTP adapter
```

### The MessageSemantics enum

`MessageSemantics` (`vultron.enums.MessageSemantics`) is a **domain type**, not a
wire type. Its values are the
authoritative vocabulary of what can happen in the system, expressed as the
domain understands them. The fact that each value maps
(`vultron.semantic_map.SEMANTICS_ACTIVITY_PATTERNS`) to an AS2 pattern
(`vultron.activity_patterns.ActivityPattern`) is an
implementation detail of the semantic extractor, not part of the domain
definition.

The semantic extractor is the **only place** where AS2 vocabulary and domain
vocabulary are coupled. This isolation is intentional — it is the single seam
where wire format changes would be absorbed.

---

## The Hexagon

```text
                         ┌──────────────────────────────────────────┐
                         │                                          │
  [CLI]  ───────────────►│                                          │──────────► [Activity Store]
                         │                                          │
  [MCP Server] ─────────►│           CORE DOMAIN                    │──────────► [Delivery Queue]
                         │                                          │
  [HTTP Inbox]           │   Case, CaseActor, Participant           │──────────► [Outbound HTTP]
       ↓                 │   SemanticIntent (domain enum)           │            (via AS2 serializer)
  [AS2 Parser]           │   CaseEvent, JournalEntry                │
       ↓        ────────►│   Ownership, Peering, Mirror             │──────────► [DNS resolver]
  [Sem. Extractor]       │                                          │
                         └──────────────────────────────────────────┘
                                         ▲▼
                              ┌──────────────────────┐
                              │  CONNECTOR ADAPTERS  │
                              │  (tracker plugins)   │
                              │  Internal tracker    │
                              │  ←→ domain events    │
                              └──────────────────────┘

  DRIVING ADAPTERS                                         DRIVEN ADAPTERS
  (left side)                                              (right side)
```

---

## Adapter Categories

### Driving adapters (left side — trigger the core)

- **CLI** — human operator commands (Click)
- **MCP server** — AI agent tool calls
- **HTTP inbox** — inbound AS2 from peer instances (FastAPI endpoint)
- **Shared inbox** — deduplicated delivery endpoint for per-instance fan-out

The HTTP inbox and shared inbox are driving adapters, but they have the AS2
parser and semantic extractor inline before handing off to the core. See
*Inbound Pipeline* below.

### Driven adapters (right side — core calls out via ports)

- **Activity store** — PostgreSQL/JSONB or EventStoreDB
- **Delivery queue** — NATS JetStream or Celery+Redis
- **Outbound HTTP** — HTTPS POST to peer instance inboxes (httpx, mTLS)
- **DNS resolver** — (Potential future, not needed in prototype and as yet
  undecided in PROD) DNS TXT lookup for instance trust anchors

### Connector adapters (bidirectional — tracker plugins)

Neither purely driving nor driven. Each connector plugin translates between
internal tracker events and core domain events in both directions. Connectors
are discovered via `importlib.metadata` entry points — the core never imports
them directly.

### Wire adapters (inbound pipeline only)

The AS2 parser and semantic extractor are their own thin layer, sitting between
the HTTP driving adapter and the domain. They are not part of the domain, and
not part of the HTTP adapter — they are a distinct stage in the inbound
pipeline.

---

## File Layout

This layout describes the target architecture after hexagonal refactoring.
The following structural moves are complete (as of P60-1 and P60-2):

- `vultron/as_vocab/` → `vultron/wire/as2/vocab/` ✅ (P60-1)
- `vultron/behaviors/` → `vultron/core/behaviors/` ✅ (P60-2)

The following move is still pending:

- `vultron/adapters/` package structure stub (P60-3)

Key principles in force during further refactoring:

- The `core/` package contains only domain logic and types. No AS2 imports, no
  framework imports, no external system imports.
- The `wire/` package contains only AS2 parsing and semantic extraction. No domain
  logic, no case handling, no journal management.
- The `adapters/` package contains only thin translation layers. No domain  
  logic, no AS2 parsing, no semantic extraction. Just translation and dispatch.

```text
vultron/
├── core/
│   ├── models/
│   │   ├── case.py             # Case, CaseActor, Participant, JournalEntry
│   │   ├── events.py           # MessageSemantics enum, InboundPayload, domain event types
│   │   ├── federation.py       # Instance, PeeringRecord
│   │   └── primitives.py       # Shared value types
│   │
│   ├── behaviors/              # ✅ Moved from vultron/behaviors/ (P60-2)
│   │   ├── bridge.py           # Handler-to-BT execution adapter
│   │   ├── helpers.py          # DataLayer-aware BT nodes
│   │   ├── report/             # Report validation tree and nodes
│   │   └── case/               # Case creation tree and nodes
│   │
│   ├── use_cases/              # (stub — P60-3 extension point)
│   │   └── __init__.py         # Incoming port: domain use-case callables
│   │
│   ├── services/
│   │   ├── case.py             # Case lifecycle: open, transfer, resolve
│   │   ├── journal.py          # Append, hash chaining, sequence management
│   │   ├── relay.py            # Fan-out logic, relay construction (domain side)
│   │   └── peering.py          # Instance trust, handshake logic
│   │
│   ├── ports/
│   │   ├── datalayer.py        # Abstract interface: store/fetch events
│   │   └── dispatcher.py       # ActivityDispatcher Protocol (evaluate for removal — VCR-025)
│   │
│   └── errors.py           # CaseNotFound, UnauthorizedParticipant, etc.
│
├── wire/
│   └── as2/                    # ✅ as_vocab moved here (P60-1)
│       ├── vocab/              # AS2 Pydantic types (structural, no domain logic)
│       ├── enums.py            # AS2 structural enums
│       ├── parser.py           # Deserialize AS2 JSON → AS2 types
│       ├── extractor.py        # AS2 types → MessageSemantics + InboundPayload
│       └── serializer.py       # Domain events → AS2 types → JSON
│   └── (future_protocol)/      # Placeholder: alternative wire formats slot in here
│
├── adapters/                   # (stub pending — P60-3)
│   ├── driving/
│   │   ├── cli.py
│   │   ├── mcp_server.py       # MCP server adapter for AI agent tool calls
│   │   ├── http_inbox.py       # FastAPI endpoint → wire/as2 pipeline → core
│   │   └── shared_inbox.py
│   │
│   ├── driven/
│   │   ├── datalayer_tinydb.py
│   │   └── http_delivery.py    # Transport only — receives serialized AS2 from wire layer
│   │
│   └── connectors/
│       ├── base.py             # ConnectorPlugin Protocol class(es)
│       ├── loader.py           # Entry-point discovery
│       └── example/
│           ├── jira.py         # Example plugin translating between Jira events and domain events
│           └── vince.py        # Example plugin translating between VINCE events and domain events
│
test/
  ├── test_core/              # Domain logic only — Pydantic objects, in-memory ports
  ├── test_wire/              # AS2 parsing and semantic extraction — no domain logic
  ├── test_adapters/          # Adapter tests with mocked ports
  └── test_connectors/        # Connector translation with domain event fixtures
```

Note that `wire/` is a top-level package, not inside `adapters/`. This reflects
its status as a distinct layer, not an adapter of a particular external system.

---

## Design Note: Use Cases as Incoming Ports

The handler functions in `vultron/api/v2/backend/handlers/` (e.g.,
`create_report`, `submit_report`, `engage_case`, `defer_case`, `accept_invite`)
are the natural "use cases" of the hexagonal architecture — they represent
the domain's incoming ports. Currently they are defined in the adapter layer
(`api/v2/`), which couples them to the HTTP/AS2 delivery mechanism.

The `vultron/core/use_cases/` stub package is reserved for the future move of
these callables into the core, so that any driving adapter (HTTP inbox, CLI,
MCP server) can invoke them without depending on the wire format or HTTP
framework. The key design challenge is that each use case will need to be
expressible independently of `MessageSemantics` (which is the AS2-derived
routing key), so that adapters can call use cases directly with domain
arguments.

**Current state:** `vultron/core/use_cases/__init__.py` is an empty stub.
Use cases still live in `vultron/api/v2/backend/handlers/`. The migration to
`core/use_cases/` is a P60-3+ task.

---

## Code Patterns

Following are notional examples of how the layers interact, to clarify the  
patterns and boundaries. Note that these examples do not necessarily reflect
the implemented codebase or the correct internal logic for individual
functions and methods. They are just meant to illustrate architectural
patterns like import boundaries.

### Inbound pipeline (HTTP inbox → core)

```python
# adapters/driving/http_inbox.py
from fastapi import FastAPI, Request
from vultron.wire.as2.parser import parse_activity
from vultron.wire.as2.extractor import extract_intent
from vultron.core.handlers import dispatch

app = FastAPI()


@app.post("/inbox")
async def instance_inbox(request: Request):
    raw = await request.json()
    as2_activity = parse_activity(raw)  # wire: structural validation
    intent, payload = extract_intent(as2_activity)  # wire: semantic mapping
    await dispatch(intent, payload)  # core: handler lookup and execution
    return {"status": "accepted"}
```

### Semantic extractor (the mapping seam)

```python
# wire/as2/extractor.py
from vultron.wire.as2.types import AS2Activity
from vultron.core.models.events import SemanticIntent, InboundPayload

# This is the only place AS2 vocabulary and domain vocabulary are coupled.
# All AS2-to-domain mapping lives here and nowhere else.

PATTERN_MAP = [
    (lambda a: a.type == "Offer" and a.object.type == "Report",
     SemanticIntent.INBOUND_REPORT_OFFER),
    (lambda a: a.type == "Accept" and a.object.type == "Case",
     SemanticIntent.OWNERSHIP_TRANSFER_ACCEPTED),
    (lambda a: a.type == "Follow",
     SemanticIntent.PEERING_REQUEST),
    # ...
]


def extract_intent(activity: AS2Activity) -> tuple[
    SemanticIntent, InboundPayload]:
    for predicate, intent in PATTERN_MAP:
        if predicate(activity):
            return intent, InboundPayload.from_as2(activity)
    raise UnknownActivityPattern(activity)
```

### Outbound serializer (domain → wire)

```python
# wire/as2/serializer.py
from vultron.core.models.events import CaseEvent
from vultron.wire.as2.types import AS2Activity


def serialize_event(event: CaseEvent, signing_key: ...) -> AS2Activity:
    """Translate a domain event into a signed AS2 activity ready for delivery."""
    # journalSeq, journalPrev, relay wrapping all happen here
    ...
```

### Core service (no wire awareness)

```python
# core/use_cases/report.py  (illustrative — actual implementation uses UseCase protocol)
from vultron.core.models.case import Case
from vultron.core.models.events import InboundPayload
from vultron.core.ports.datalayer import DataLayer


def handle_report_offer(payload: InboundPayload, dl: DataLayer) -> None:
    """
    Pure domain logic. Knows nothing about AS2.
    Called by the handler dispatcher after semantic extraction.
    Outbound delivery will use the ActivityEmitter port (OX-1.0).
    """
    case = Case.open_from_report(payload)
    dl.update(case.as_id, case)
```

---

## Rules

### Rule 1 — The core has no wire format imports

The core must not import from `wire/` or any AS2 library. This includes `pyld`,
`rdflib`, or any JSON-LD tooling. If JSON-LD validation is needed, it happens in
the wire layer before the domain is invoked.

### Rule 2 — The core has no framework imports

No `fastapi`, `typer`, `mcp`, `httpx`, `celery`, `nats`, or connector libraries
in core.

### Rule 3 — SemanticIntent is a domain type, defined in core

The enum lives in `core/models/events.py`. The wire layer imports it to produce
intent values. The core never imports from the wire layer to consume them.

### Rule 4 — The semantic extractor is the only AS2-to-domain mapping point

No other file maps AS2 vocabulary onto domain concepts. If a new activity type
needs handling, the extractor is the only place to add the mapping. Handler code
never inspects AS2 types.

### Rule 5 — Core functions take and return domain types

Raw dicts, AS2 types, JSON strings, and framework objects never enter the
domain. The inbound pipeline completes its work before calling into core. Core
functions receive `SemanticIntent` + `InboundPayload`, not AS2 activities.

### Rule 6 — Driven adapters are injected via ports

The core defines abstract port interfaces in `core/ports/`. Driven adapters
implement them. Core services receive port implementations via dependency
injection, never instantiate them directly.

### Rule 7 — Connector plugins translate at the boundary only

Connectors map tracker events to domain events and vice versa. No case handling
logic, authorization, or journal management belongs in a connector.

### Rule 8 — The wire layer is replaceable as a unit

`wire/as2/` should be replaceable with `wire/some_future_protocol/` without
touching `core/` or `adapters/`. If a change to the wire format requires changes
in `core/`, a boundary has been violated.

---

## Dispatch vs Emit Terminology

Two distinct port concepts govern activity flow. Use these terms consistently
across code, comments, specs, and docs:

**Dispatch (inbound)** — a wire activity is received → the appropriate core
use case is invoked. This is a **driving port**: the core *exposes* an
interface that adapters (HTTP inbox, CLI, MCP) call into.
The `ActivityDispatcher` Protocol lives in `core/ports/dispatcher.py`.

**Emit (outbound)** — a core action is completed → a wire object is sent to
one or more recipients. This is a **driven port**: the core calls *out* to an
external system that delivers the activity. A future `ActivityEmitter` Protocol
belongs in `core/ports/emitter.py`. The delivery-queue adapter implements it.
The emitter port is the use-case-facing interface; the delivery queue adapter
is the transport implementation.

Key rules:

- "Activity" is a wire-level concept; "Event" is a core-level concept.
- The dispatch envelope (`DispatchEvent`) carries a `VultronEvent` domain
  payload, not a raw wire activity.
- `EmbargoEvent` is an AS2 object type — its name coincides with the
  `VultronEvent` pattern but it is a wire-layer concept, not a domain event.

---

## Core Models Must Be Richer Than Wire Models

A recurring problem during early development: core domain models were
thinner than their wire equivalents, forcing piecemeal additions to core
as handlers were implemented.

**Invert this pattern**: core models are the authoritative, fully-featured
representation. Wire models provide syntactic translation to/from core.

Any field that exists in the wire model (e.g., `content`, `summary`,
`published`) MUST be representable in the core domain model. Core models
are not simplified views; they are richer domain representations that may
include fields the wire format does not yet expose.

---

## Adapter Category Discipline

**Avoid mixing driving and driven adapters** in a single module. If an
integration needs both directions, create:

- `adapters/driving/foo.py` — for inbound data and events
- `adapters/driven/foo.py` — for outbound data and events

Do not use a generic `adapters/connectors/` namespace as a dumping ground
for code that does not fit cleanly. The `connectors/` category is reserved
for **third-party tracker integrations** (e.g., Jira, VINCE) that translate
between external tracker events and Vultron domain events.

---

## Review Checklist

**Core (`core/`)**

- [ ] No imports from `wire/`, `adapters/`, or any framework
- [ ] `MessageSemantics` enum is defined here, not in the wire layer
- [ ] All service functions take domain types, not AS2 types or raw dicts
- [ ] No direct instantiation of DB, HTTP, or queue clients
- [ ] Domain exceptions defined in `core/exceptions.py`

**Wire layer (`wire/as2/`)**

- [ ] `types.py` contains only structural AS2 types — no domain logic
- [ ] `extractor.py` is the sole location of AS2-to-domain vocabulary mapping
- [ ] `serializer.py` is the sole location of domain-to-AS2 translation
- [ ] No handler logic or case management in the wire layer

**Adapters (`adapters/`)**

- [ ] Inbound adapters invoke the wire pipeline before calling core
- [ ] Outbound adapters receive serialized wire objects — no AS2 construction
- [ ] Each adapter function is thin — translation and dispatch only

**Connectors (`adapters/connectors/`)**

- [ ] Plugins translate only — no business logic
- [ ] Discovered via entry points, not hardcoded imports

**Tests** <!-- markdownlint-disable-line MD036 -->

- [ ] Core tests use domain types directly — no AS2, no HTTP
- [ ] Wire tests verify parsing and extraction independently of domain logic
- [ ] Adapter tests mock ports, not external systems

---

## Design Constraints and Invariants

The following constraints are extracted from architecture review sessions
and apply to all implementation work. They are strict requirements, not
recommendations.

1. **Core ≥ Wire**: Core models MUST be as rich as or richer than wire
   models. Wire models are projections of core models only. Any field
   present in the wire model MUST be representable in the core domain
   model. See also: "Core Models Must Be Richer Than Wire Models" section
   above.

2. **Fail-fast models**: Domain events and models MUST validate required
   fields on construction and fail immediately if required invariants are
   missing. Fields that are required for a specific event subtype MUST
   NOT be typed as `X | None` in that subtype — use `| None` only in
   the parent class when the field is genuinely optional. Subclasses
   SHOULD narrow optional parent fields to required. This applies to
   `VultronEvent` subclasses, which should never carry `activity: ... | None`
   when the activity is always present for that semantic type.

3. **ActivityStreams alignment**: Actor profiles and any protocol-exposed
   objects MUST follow ActivityStreams semantics where specified
   (discovery endpoint, actor profiles, reply activity formats).

4. **Adapter/Core boundary**: Adapters own transport concerns and
   instantiate wire objects. Adapters MUST provide domain-ready data
   objects to core. No transport logic belongs in core.

5. **Non-breaking BT migration**: Changes to Behavior Trees MUST be
   initially import-layer refactors and non-breaking at runtime. Do not
   change BT node semantics and file locations in the same commit.

6. **Dispatcher port preservation**: Do not remove the dispatcher port
   without a validated migration plan. Its removal is uncertain and must
   be justified with tests confirming the use-case port fully covers all
   dispatch scenarios.

---

## Core Port Taxonomy: Inbound vs Outbound

Core ports should be discriminated into two categories for clarity:

**Inbound ports (driving)** — external adapters call into core:

- `UseCase` Protocol (`core/ports/use_case.py`) — the primary inbound port
- `ActivityDispatcher` Protocol (`core/ports/dispatcher.py`) — may be
  subsumed by the use-case port; evaluate before P100 work

**Outbound ports (driven)** — core calls out to external systems:

- `DataLayer` Protocol (`core/ports/datalayer.py`) — persistence
- `ActivityEmitter` Protocol (`core/ports/emitter.py`, to be created in
  OX-1.0) — outbound activity delivery

**Ports that have been removed** (confirmed no callers):

- `core/ports/dns_resolver.py` — deleted (VCR-024); DNS resolution is an
  adapter-level concern
- `core/ports/delivery_queue.py` — deleted (VCR-023); superseded by
  the upcoming `ActivityEmitter` port (OX-1.0)

**Ports to evaluate for removal**:

- `core/ports/dispatcher.py` — may be replaced entirely by the `UseCase`
  port; evaluate during Priority-80 cleanup (VCR-025)

When naming ports, prefer the domain concept over the implementation
mechanism: `ActivityEmitter` (not `DeliveryQueue`), `DataLayer` (not
`TinyDbAdapter`).

---

## Server-Level Inbox: Deferred Design Decision

A **per-server inbox** (buffering all inbound activities before routing
to actor inboxes) is recognized as a future architectural option but is
**not part of the current model**.

| Approach | Advantage | Cost |
|----------|-----------|------|
| Direct-to-Actor Inbox | Immediate semantic validation feedback | No durable pre-validation buffer |
| Server-Level Inbox | Durable buffering, centralized routing | Cannot perform actor-specific validation at ingest |

**Current decision**: Maintain direct delivery service → actor inbox (HTTP).
All messages are effectively DMs; actor-level validation is more valuable
than buffering at the current prototype stage.

**Future option**: A server-level inbox may later act as a durable ingress
queue or routing layer for local actors, but would require clear handling
of deferred validation failures and possibly new Event types for
rejection/acknowledgment.

---

## Outbound Delivery Invariants

These invariants govern the outbox-based delivery model:

1. **Event purity in core**: No leakage of ActivityStreams types into core.
   Core produces `VultronEvent` objects, not AS2 activities.

2. **Deterministic mapping**: Event ⇄ Activity transformation is lossless
   and mechanical. No enrichment, no recipient injection, no semantic
   alteration occurs at the mapping layer.

3. **Explicit addressing**: Recipients originate from domain logic (e.g.,
   case participation records), not from infrastructure. The `recipients`
   field is part of the event model, not injected by the delivery service.

4. **Delivery decoupling**: Emission ≠ delivery ≠ acceptance. Core emitting
   an event does not guarantee delivery or acceptance by the recipient actor.

5. **Validation split**: Transport validation (is this a valid Activity?
   is the recipient local?) occurs at the adapter boundary and results in
   immediate HTTP rejection. Semantic validation (is this transition
   allowed? is the sender authorized?) occurs in core after delivery and
   may produce compensating events (rejection, error signaling).
