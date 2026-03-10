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

```
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

```
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

```
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

This is a proposed file layout that reflects the architecture. Since we are 
starting from a codebase not originally laid out this way, some refactoring 
will be needed to achieve this structure. Key principles to follow during 
that refactoring:

- The `core/` package contains only domain logic and types. No AS2 imports, no
  framework imports, no external system imports.
- The `wire/` package contains only AS2 parsing and semantic extraction. No domain
  logic, no case handling, no journal management.
- The `adapters/` package contains only thin translation layers. No domain  
  logic, no AS2 parsing, no semantic extraction. Just translation and dispatch.

```
vultron/
├── core/
│   ├── models/
│   │   ├── case.py             # Case, CaseActor, Participant, JournalEntry
│   │   ├── events.py           # SemanticIntent enum, CaseEvent types
│   │   ├── federation.py       # Instance, PeeringRecord
│   │   └── primitives.py       # Shared value types
│   │
│   ├── services/
│   │   ├── case.py             # Case lifecycle: open, transfer, resolve
│   │   ├── journal.py          # Append, hash chaining, sequence management
│   │   ├── relay.py            # Fan-out logic, relay construction (domain side)
│   │   ├── mirror.py           # Mirror consistency, gap detection
│   │   ├── peering.py          # Instance trust, handshake logic
│   │   └── signing.py          # Signing and verification (domain logic)
│   │
│   ├── ports/
│   │   ├── activity_store.py   # Abstract interface: store/fetch events
│   │   ├── delivery_queue.py   # Abstract interface: enqueue outbound
│   │   └── dns_resolver.py     # Abstract interface: DNS TXT lookup
│   │
│   └── errors.py           # CaseNotFound, UnauthorizedParticipant, etc.
│
├── wire/
│   ├── as_vocab/
│   │   ├── types.py            # AS2 Pydantic types (structural, no domain logic)
│   │   ├── parser.py           # Deserialize AS2 JSON → AS2 types
│   │   ├── extractor.py        # AS2 types → SemanticIntent (the mapping seam)
│   │   └── serializer.py       # Domain events → AS2 types → JSON
│   └── (future_protocol)/      # Placeholder: alternative wire formats slot in here
│
├── adapters/
│   ├── driving/
│   │   ├── cli.py
│   │   ├── mcp_server.py
│   │   ├── http_inbox.py       # FastAPI endpoint → wire/as2 pipeline → core
│   │   └── shared_inbox.py
│   │
│   ├── driven/
│   │   ├── activity_store.py
│   │   ├── delivery_queue.py
│   │   ├── http_delivery.py    # Transport only — receives serialized AS2 from wire layer
│   │   └── dns_resolver.py     # Optional future adapter for DNS-based trust discovery
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
# core/services/case.py
from vultron.core.models.case import Case, CaseActor
from vultron.core.models.events import SemanticIntent, CaseEvent
from vultron.core.ports.delivery_queue import DeliveryQueue


async def handle_report_offer(payload: InboundPayload,
                              queue: DeliveryQueue) -> None:
    """
    Pure domain logic. Knows nothing about AS2.
    Called by the handler dispatcher after semantic extraction.
    """
    case = Case.open_from_report(payload)
    events = case.accept_report()
    for event in events:
        await queue.enqueue(event)
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

**Tests**

- [ ] Core tests use domain types directly — no AS2, no HTTP
- [ ] Wire tests verify parsing and extraction independently of domain logic
- [ ] Adapter tests mock ports, not external systems
