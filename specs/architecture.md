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
`notes/architecture-review.md` (current violation inventory)

---

## Layer Separation (MUST)

- `ARCH-01-001` The `core/` package (or equivalent domain layer) MUST NOT
  import from `wire/`, `adapters/`, or any external framework
  - Prohibited: `fastapi`, `typer`, `mcp`, `httpx`, `celery`, `nats`,
    connector libraries, AS2 libraries (`pyld`, `rdflib`, JSON-LD tooling)
  - **Rationale**: Keeps domain logic replaceable without touching the wire
    or transport layer
  - **Current state**: Deferred to post-prototype; see PROTO-06-001
- `ARCH-01-002` Core functions MUST accept and return domain types only
  - Raw dicts, AS2 types, JSON strings, and framework objects MUST NOT
    enter the domain
  - The inbound pipeline MUST complete parse → extract steps before calling
    into core
  - **Current state**: Deferred to post-prototype; see PROTO-06-001
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
  - **Current location**: `vultron/enums.py` (mixed with AS2 structural
    enums — see `notes/architecture-review.md` V-01 for remediation plan)

## Semantic Extractor (MUST)

- `ARCH-03-001` AS2 vocabulary MUST be mapped to domain concepts in exactly
  one location: the semantic extractor
  - No other module maps AS2 activity patterns to domain semantics
  - Handler code MUST NOT inspect AS2 types to infer message meaning
  - **Rationale**: Isolates the single seam where wire format changes are
    absorbed
  - **Current state**: Extraction is split across `semantic_map.py` and
    `activity_patterns.py`; see `notes/architecture-review.md` V-04, V-05
    for remediation plan

## Driven Adapter Injection (MUST)

- `ARCH-04-001` Driven adapters (persistence, delivery queue, DNS resolver,
  HTTP delivery) MUST be injected into core services via port interfaces
  - Core services MUST NOT instantiate concrete adapter implementations
    directly
  - **Rationale**: Enables testing core logic with in-memory ports and
    swapping production backends without touching domain code
  - **Current state**: Handlers call `get_datalayer()` directly; see
    `notes/architecture-review.md` V-10 for remediation plan

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
  - **Current state**: Not yet achieved; AS2 types currently present in
    `DispatchActivity.payload` (see `notes/architecture-review.md` V-02)

## Handler Isolation (MUST)

- `ARCH-07-001` Handler functions MUST NOT re-invoke semantic extraction
  - The semantic type MUST be pre-computed and carried in the dispatch
    wrapper (`DispatchActivity.semantic_type`)
  - Semantic verification decorators MUST compare `dispatchable.semantic_type`
    directly, not re-run pattern matching
  - **Current state**: `verify_semantics` decorator re-invokes
    `find_matching_semantics`; see `notes/architecture-review.md` V-04

## Driving Adapter Boundary (MUST)

- `ARCH-08-001` Driving adapters (HTTP inbox, CLI, MCP server) MUST invoke
  the wire pipeline before calling into the core
  - AS2 parsing and semantic extraction are stages of the inbound pipeline,
    not responsibilities of the driving adapter itself
  - **Rationale**: Any driving adapter that needs to ingest AS2 can reuse
    the wire pipeline; there is no duplication
  - **Current state**: `parse_activity` lives in the router
    (`api/v2/routers/actors.py`); see `notes/architecture-review.md` V-06

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

## Deferred to Post-Prototype

The following architectural rules are aspirational targets. Achieving them
requires a refactoring effort documented in
`notes/architecture-review.md`. The prototype MAY violate these rules while
the refactoring is in progress:

- ARCH-01-001, ARCH-01-002 (core isolation from wire/framework) — see
  PROTO-06-001
- ARCH-03-001 (extractor as sole mapping point) — partial: extraction
  logic is split but not duplicated in handler business logic
- ARCH-04-001 (adapter injection) — all handlers call `get_datalayer()`
  directly; injection is deferred
- ARCH-06-001 (wire replaceability) — not yet achieved
- ARCH-07-001 (no re-invocation in handlers) — `verify_semantics`
  currently re-runs extraction; a one-line fix (compare
  `dispatchable.semantic_type` directly) is the intended resolution

See `notes/architecture-review.md` for the full violation inventory and
remediation plan (R-01 to R-06).
