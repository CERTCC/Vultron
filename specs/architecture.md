# Architecture Specification

## Overview

Defines the architectural constraints for the Vultron codebase. The system
follows **Hexagonal Architecture** (Ports and Adapters): the core domain
is isolated from all external systems. External systems interact with the
core through defined **ports**, via thin **adapters**.

**Source**: `notes/architecture-ports-and-adapters.md`,
`notes/architecture-review.md`

**Cross-references**: `code-style.md` CS-05-001 (circular import
prevention), `prototype-shortcuts.md` PROTO-06-001 (domain model deferral),
`notes/domain-model-separation.md` (wire/domain/persistence separation),
`notes/architecture-review.md` (violation inventory and remediation history),
`docs/adr/0009-hexagonal-architecture.md` (decision rationale)

---

## Layer Separation (MUST)

- `ARCH-01-001` The `core/` package (or equivalent domain layer) MUST NOT
  import from `wire/`, `adapters/`, or any external framework
  - Prohibited: `fastapi`, `typer`, `mcp`, `httpx`, `celery`, `nats`,
    connector libraries, AS2 libraries (`pyld`, `rdflib`, JSON-LD tooling)
  - **Rationale**: Keeps domain logic replaceable without touching the wire
    or transport layer
  - **Current state**: Partially achieved. `vultron/core/` has no wire/framework
    imports; `vultron/api/` still uses FastAPI and imports from `vultron/wire/`.
    Full isolation deferred to post-prototype; see PROTO-06-001
- `ARCH-01-002` Core functions MUST accept and return domain types only
  - Raw dicts, AS2 types, JSON strings, and framework objects MUST NOT
    enter the domain
  - The inbound pipeline MUST complete parse → extract steps before calling
    into core
  - **Current state**: `InboundPayload` domain type introduced (ARCH-1.2);
    parse → extract pipeline stages in `vultron/wire/as2/`. Full core isolation
    deferred to post-prototype; see PROTO-06-001
- `ARCH-01-003` The `wire/` layer (AS2 parser, semantic extractor) MUST NOT
  contain handler logic, case management, or journal management
  - **Rationale**: Wire format concerns are structurally distinct from
    domain concerns; mixing them prevents future wire format substitution

## SemanticIntent Enum (MUST)

- `ARCH-02-001` The `MessageSemantics` enum (`SemanticIntent`) MUST be
  defined in the domain layer, not in the wire layer
  - The enum expresses the authoritative vocabulary of what can happen
    in the system, as the domain understands it
  - Wire layer pattern maps are an implementation detail of the extractor,
    not part of the domain definition
  - **Current location**: `vultron/core/models/events.py` (remediated in
    ARCH-1.1); re-exported from `vultron/enums.py` for compatibility. AS2
    structural enums moved to `vultron/wire/as2/enums.py` (ARCH-CLEANUP-2).

## Semantic Extractor (MUST)

- `ARCH-03-001` AS2 vocabulary MUST be mapped to domain concepts in exactly
  one location: the semantic extractor
  - No other module maps AS2 activity patterns to domain semantics
  - Handler code MUST NOT inspect AS2 types to infer message meaning
  - **Rationale**: Isolates the single seam where wire format changes are
    absorbed
  - **Current state**: ✅ Achieved. `vultron/wire/as2/extractor.py` is the
    sole location of AS2-to-domain vocabulary mapping (ARCH-1.3,
    ARCH-CLEANUP-1). Handler code no longer inspects AS2 types (ARCH-CLEANUP-3).

## Driven Adapter Injection (MUST)

- `ARCH-04-001` Driven adapters (persistence, delivery queue, DNS resolver,
  HTTP delivery) MUST be injected into core services via port interfaces
  - Core services MUST NOT instantiate concrete adapter implementations
    directly
  - **Rationale**: Enables testing core logic with in-memory ports and
    swapping production backends without touching domain code
  - **Current state**: ✅ Achieved. All handlers receive `dl: DataLayer` via
    parameter injection (ARCH-1.4). `get_datalayer()` is no longer called
    inside handler bodies.

## Connector Plugins (MUST)

- `ARCH-05-001` Connector plugins (tracker integrations) MUST be discovered
  via Python entry points (`importlib.metadata`); the core MUST NOT import
  them directly
- `ARCH-05-002` Connector plugins MUST translate only — no case handling
  logic, authorization, or journal management belongs in a connector

## Wire Layer Replaceability (SHOULD)

- `ARCH-06-001` The wire layer (`wire/as2/`) SHOULD be replaceable as a
  unit without touching the core or adapter layers
  - If a change to the wire format requires changes in the core, a
    boundary has been violated
  - **Current state**: Substantially achieved. `DispatchEvent.payload` is
    now typed as `InboundPayload` (domain type), not `as_Activity` (ARCH-1.2).
    Full wire replaceability requires completing P60-3 (adapters package).

## Handler Isolation (MUST)

- `ARCH-07-001` Handler functions MUST NOT re-invoke semantic extraction
  - The semantic type MUST be pre-computed and carried in the dispatch
    wrapper (`DispatchEvent.semantic_type`)
  - Semantic verification decorators MUST compare `dispatchable.semantic_type`
    directly, not re-run pattern matching
  - **Current state**: ✅ Achieved. `verify_semantics` decorator now compares
    `dispatchable.semantic_type` directly (ARCH-1.2/ARCH-1.3); no second
    invocation of `find_matching_semantics`.

## Driving Adapter Boundary (MUST)

- `ARCH-08-001` Driving adapters (HTTP inbox, CLI, MCP server) MUST invoke
  the wire pipeline before calling into the core
  - AS2 parsing and semantic extraction are stages of the inbound pipeline,
    not responsibilities of the driving adapter itself
  - **Rationale**: Any driving adapter that needs to ingest AS2 can reuse
    the wire pipeline; there is no duplication
  - **Current state**: ✅ Achieved. `parse_activity()` is in
    `vultron/wire/as2/parser.py`; the router calls it as a thin wrapper
    (ARCH-1.3).

## Core Model Richness (MUST)

- `ARCH-09-001` Core domain models MUST be as rich as or richer than their
  wire-layer counterparts
  - Wire models are projections of core models — not simplified views and
    not independent representations
  - Any field present in a wire model MUST be representable in the
    corresponding core domain model
  - **Rationale**: A thinner core model forces piecemeal additions as
    handlers are implemented, causing boundary leakage and implementation
    drift
  - **Cross-reference**: `notes/architecture-ports-and-adapters.md`
    "Core Models Must Be Richer Than Wire Models"

## Fail-Fast Domain Objects (MUST)

- `ARCH-10-001` Domain events and domain models MUST validate required
  fields at construction time and fail immediately if required invariants
  are not satisfied
  - Fields that are required for a specific event subtype MUST NOT be
    typed as `Field | None` in that subtype
  - Parent classes MAY use `Field | None` for fields that are genuinely
    optional at the parent level; subclasses MUST narrow optional parent
    fields to required when the field is always present for that subtype
  - **Rationale**: Late validation masks missing data and makes debugging
    harder; fail-fast ensures errors surface at the point of construction
  - **Cross-reference**: `notes/architecture-ports-and-adapters.md`
    "Design Constraints and Invariants" invariant 2

## Port Inbound/Outbound Discrimination (SHOULD)

- `ARCH-11-001` Core ports SHOULD be organized into inbound (driving)
  and outbound (driven) categories
  - **Inbound ports (driving)**: interfaces that external adapters call
    into core (e.g., `UseCase`, `ActivityDispatcher`)
  - **Outbound ports (driven)**: interfaces that core calls out to external
    systems through (e.g., `DataLayer`, `ActivityEmitter`)
  - Port files in `core/ports/` that no longer correspond to active
    interfaces SHOULD be removed rather than left as stubs
  - **Cross-reference**: `notes/architecture-ports-and-adapters.md`
    "Core Port Taxonomy: Inbound vs Outbound"

---

## Review Checklist

Use this checklist during code review to catch boundary violations.

**Core / domain layer**

- [ ] No imports from `wire/`, `adapters/`, or any framework
- [ ] `MessageSemantics` enum defined here, not in the wire layer
- [ ] All service functions take domain types, not AS2 types or raw dicts
- [ ] No direct instantiation of DB, HTTP, or queue clients

**Wire layer**

- [ ] Structural AS2 types contain no domain logic
- [ ] Extractor is the sole location of AS2-to-domain vocabulary mapping
- [ ] Serializer is the sole location of domain-to-AS2 translation
- [ ] No handler logic or case management in the wire layer

**Adapters**

- [ ] Inbound adapters invoke the wire pipeline before calling core
- [ ] Outbound adapters receive serialized wire objects — no AS2 construction
- [ ] Each adapter function is thin — translation and dispatch only

**Connectors**

- [ ] Plugins translate only — no business logic
- [ ] Discovered via entry points, not hardcoded imports

**Tests**

- [ ] Core tests use domain types directly — no AS2, no HTTP
- [ ] Wire tests verify parsing and extraction independently of domain logic
- [ ] Adapter tests mock ports, not external systems

---

## Remediation Status

The following architectural requirements had known violations that have been
remediated through incremental refactoring (ARCH-1.1 through ARCH-CLEANUP-3).
See `docs/adr/0009-hexagonal-architecture.md` for full violation inventory.

**Remediated (ARCH-1.x and ARCH-CLEANUP-x):**

- ARCH-02-001 (`MessageSemantics` in core) — ✅ ARCH-1.1
- ARCH-03-001 (sole mapping point) — ✅ ARCH-1.3, ARCH-CLEANUP-1
- ARCH-04-001 (adapter injection) — ✅ ARCH-1.4
- ARCH-06-001 (wire replaceability) — ✅ substantially achieved (ARCH-1.2)
- ARCH-07-001 (no re-invocation) — ✅ ARCH-1.2/1.3
- ARCH-08-001 (parse in wire layer) — ✅ ARCH-1.3

**Partially deferred (PROTO-06-001):**

- ARCH-01-001, ARCH-01-002 (full core isolation from wire/framework) —
  `vultron/core/` is clean; `vultron/api/` imports from `vultron/wire/` as
  expected for an adapter. Full isolation of all existing domain objects from
  AS2 base types is deferred to post-prototype; see PROTO-06-001 and
  `notes/domain-model-separation.md`.

**Not yet started (PRIORITY-60):**

- P60-3: `vultron/adapters/` package structure stub — see
  `plan/IMPLEMENTATION_PLAN.md`

See `notes/architecture-review.md` for full violation inventory and
remediation history (R-01 to R-06).
