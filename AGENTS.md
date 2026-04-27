# AGENTS.md — Vultron Project

## Purpose

This file provides quick technical reference for AI coding agents working in
this repository.

**See also**:

- `notes/` — durable design insights (BT integration, ActivityStreams
  semantics). These files are committed to version control and are the
  authoritative source for design decisions.
- `specs/project-documentation.yaml` — documentation structure guidance.

Agents MUST follow these rules when generating, modifying, or reviewing code.

---

## Agent Quickstart

A short, actionable checklist for AI coding agents who need to be productive
quickly in this repo.

- **Load specs first**: run `uv run spec-dump` (or invoke the
  `load-specs` skill) to get all requirements as flat, inheritance-resolved
  JSON. Do **not** read raw `specs/*.yaml` files — those are for authoring
  only. See `.agents/skills/load-specs/SKILL.md` for the output format and
  field definitions.
- Key architecture: FastAPI inbox → AS2 parser
  (`vultron/wire/as2/parser.py`) → semantic extraction
  (`vultron/wire/as2/extractor.py`) → behavior dispatcher
  (`vultron/core/dispatcher.py`) → use-case callable
  (`vultron/core/use_cases/`).
- Follow the Use-Case Protocol: use-case functions accept
  `event: VultronEvent` and `dl: DataLayer`.  The routing table
  (`vultron/core/use_cases/use_case_map.py`) maps `MessageSemantics` →
  callable; semantic type validation is enforced by the dispatcher key lookup,
  not by a per-handler decorator.

Checklist (edit → validate → commit):

1. Implement or modify code in `vultron/`.
2. Add/adjust tests under `test/` mirroring the source layout.
3. Run formatter and all linters, then tests locally before committing.

Essential commands (run in zsh):

See `.agents/skills/format-code/SKILL.md`, `.agents/skills/run-linters/SKILL.md`,
`.agents/skills/run-tests/SKILL.md`, and `.agents/skills/build-docs/SKILL.md` for
the canonical Black, linter, pytest, and mkdocs invocation commands (these files
contain the exact invocation semantics, environment notes, and examples you must
follow).

> ⚠️ **STOP — Full test-suite rule (MUST follow)**
>
> Follow the instructions in `.agents/skills/run-tests/SKILL.md`
> for running the test suite exactly once per validation cycle and
> reading its output. The skill file documents the required single-run
> invocation and the rationale for the one-run rule.
>
> The project has two test suites:
>
> - **Unit (default)**: `uv run pytest --tb=short 2>&1 | tail -5`
>   Excludes `@pytest.mark.integration` tests. Runs in ~13 seconds.
> - **Integration**: `uv run pytest -m integration --tb=short 2>&1 | tail -5`
>   Demo tests and file-backed I/O tests. Runs in ~6 seconds.
> - **All tests**: `uv run pytest -m "" --tb=short 2>&1 | tail -5`
>
> For normal code changes, run the unit suite. Run integration tests
> when touching demo workflows or file-backed datalayer code.

Quick pointers and gotchas:

- Order matters in `SEMANTICS_ACTIVITY_PATTERNS` (place more specific patterns
  first); patterns live in `vultron/wire/as2/extractor.py`.
- Always call `rehydrate()` on incoming activities to expand URI references
  before pattern matching.
- Use `dl.save(obj)` when persisting Pydantic models to the datalayer. The
  `object_to_record()` + `dl.update()` pattern has been removed from core.
- FastAPI endpoints should return 202 quickly and schedule background work with
  `BackgroundTasks`.

Examples (handler & datalayer):

```python
class CreateReportReceivedUseCase:
    def __init__(
        self, dl: DataLayer, request: CreateReportReceivedEvent
    ) -> None:
        self._dl = dl
        self._request = request

    def execute(self) -> None:
        # rehydrate nested refs, validate, persist via datalayer.update(id, record)
        ...
```

If making non-trivial architectural changes, draft an ADR in
`docs/adr/_adr-template.md` and include tests. When in doubt, ask a human
maintainer or open an Issue describing assumptions and risks.

## Scope of Allowed Work

Agents MAY:

- Implement small to medium features that do not change public APIs or
  persistence schemas
- Refactor existing code without changing external behavior
- Add or update tests and test fixtures
- Improve typing, validation, and error handling
- Update documentation, examples, and specification markdown in `docs/` and
  `specs/`
- Propose architectural changes (but not apply them without approval)

Agents MUST NOT:

- Introduce breaking API changes without explicit instruction
- Modify authentication, authorization, or cryptographic logic
- Change persistence schemas or perform data migrations without explicit
  instruction
- Touch production deployment, CI configuration, or secrets unless explicitly
  instructed (see exception below for documentation updates)

Note: Small implementation tweaks (non-architectural) do not require an ADR;
architectural or protocol changes (component boundaries, persistence paradigms,
message formats, or moving away from ActivityStreams) SHOULD be documented as
ADRs before merging. See the ADR guidance in `docs/adr/_adr-template.md` for
the format and examples.

---

## Technology Stack (Authoritative)

- Python **3.12+** (project `pyproject.toml` specifies `requires-python =
  ">=3.12"`); CI currently runs tests on Python 3.13
- **FastAPI** for HTTP APIs
  - Route functions that trigger long-running events should use BackgroundTasks
    for async processing
  - Other internal components can be sync by default, but async is allowed where
    it makes sense (e.g., external API calls, I/O-bound operations)
- **Pydantic v2** for models and validation (project pins a specific Pydantic
  version)
- **pytest** for testing
- **mkdocs** with **Material** theme for documentation
- **streamlit** for UI prototyping (if needed)

### Development support tools (approved)

- **uv** for package and environment management (used in CI)
- **black** for code formatting (enforced via pre-commit hooks AND CI)
- **flake8** for PEP 8 linting (enforced in CI; MUST pass with zero errors)
- **mypy** for static type checking (enforced in CI; MUST pass with zero errors)
- **pyright** for static type checking (enforced in CI; MUST pass with zero errors)
- **markdownlint-cli2** for markdown linting (use the repository's
   `mdlint.sh` wrapper; see `.agents/skills/format-markdown/SKILL.md`)

Agents MUST NOT introduce alternative frameworks or package managers without
explicit approval from the maintainers.

---

## Architectural Constraints

- FastAPI routers define the external API surface only
- Business logic MUST live outside route handlers
- Persistence access MUST be abstracted behind repository or data-layer
  interfaces
- Pydantic models are the canonical schema for data exchange
- Side effects (I/O, persistence, network) MUST be isolated from pure logic
- **Core modules MUST NOT import from application layer modules** (see
  `specs/code-style.yaml` CS-05-001)
  - Core: `vultron/core/`, `vultron/behavior_dispatcher.py`
  - Wire layer: `vultron/wire/`
  - Application layer: `vultron/api/v2/*`
  - Use shared neutral modules (e.g., `types.py`, `dispatcher_errors.py`)
    when cross-layer dependencies exist

Avoid tight coupling between layers.

When an agent proposes a non-trivial architectural change (new persistence
paradigm, swapping ActivityStreams for a different message model, or a major
refactor that impacts component boundaries), it SHOULD prepare an ADR and
include migration/compatibility notes and tests.

---

## Agent Guidance for Vultron Implementation

This document provides guidance to AI agents working on the Vultron codebase.
It supplements the Copilot instructions with implementation-specific advice.

**For durable design insights**, see the `notes/` directory.

**Priority ordering note**: When `plan/IMPLEMENTATION_PLAN.md` grouping or
section order conflicts with `plan/PRIORITIES.md`, follow
`plan/PRIORITIES.md`.

**Path note**: The active FastAPI adapter code now lives under
`vultron/adapters/driving/fastapi/`. `vultron/api/v2/` is **deprecated** — do
not add new code there; it retains only `data/actor_io.py` (pending VCR-014)
and two `__init__.py` stubs. Similarly, `test/api/` is deprecated; new tests
MUST mirror the source layout under `test/adapters/` or `test/core/`, not
`test/api/`. Some older notes and task descriptions may still reference
`vultron/api/v2/` paths.

## Vultron-Specific Architecture

### Semantic Message Processing Pipeline

Vultron processes inbound ActivityStreams activities through a four-stage
pipeline:

1. **Inbox Endpoint**
   (`vultron/adapters/driving/fastapi/routers/actors.py`): FastAPI POST
   endpoint accepting activities; returns 202 immediately
2. **AS2 Parser** (`vultron/wire/as2/parser.py`): Structural validation and
   deserialization of AS2 JSON
3. **Semantic Extraction** (`vultron/wire/as2/extractor.py`): Pattern matching
   on (Activity Type, Object Type) to determine `MessageSemantics`
4. **Behavior Dispatch** (`vultron/core/dispatcher.py`): Routes to
   semantic-specific use-case callables via `USE_CASE_MAP`
   (`vultron/core/use_cases/use_case_map.py`); the `dl: DataLayer` is passed
   at dispatch time, not at construction time.

**Key constraint:** Semantic extraction uses **ordered pattern matching**. When
adding patterns to `SEMANTICS_ACTIVITY_PATTERNS` in
`vultron/wire/as2/extractor.py`, place more specific patterns before general
ones.

See `specs/dispatch-routing.yaml`, `specs/semantic-extraction.yaml`,
`docs/adr/0007-use-behavior-dispatcher.md`, and
`docs/adr/0009-hexagonal-architecture.md` for complete architecture details.

### Hexagonal Architecture (Ports and Adapters)

The target architecture is **Hexagonal** (Ports and Adapters). The core domain
is isolated from external systems; adapters translate between external protocols
and domain types. Rules:

- **Core has no wire format imports**: no AS2, `pyld`, `rdflib`, JSON-LD
- **Core has no framework imports**: no `fastapi`, `httpx`, `celery`, `nats`
- **`MessageSemantics` is a domain type**: defined in core, not in the wire
  layer
- **Extractor is the only AS2→domain mapping point**: handlers never inspect
  AS2 types
- **Core functions take domain types**: the inbound pipeline finishes
  parse → extract before calling into core
- **Driven adapters injected via ports**: handlers receive `dl: DataLayer` as
  a parameter; they do not call `get_datalayer()` directly

See `notes/architecture-ports-and-adapters.md` for the full architecture
specification and code patterns. See `archived_notes/architecture-review.md` for the violation inventory (V-01 to V-12).
See `specs/architecture.yaml` for formal requirements (ARCH-01 to ARCH-08) and
`docs/adr/0009-hexagonal-architecture.md` for the decision rationale.

### Protocol Activity Model

Vultron activities are **state-change notifications**, not commands.

**Inbound activities** (in an actor's inbox) declare that the sender completed
a protocol-relevant state transition. When a handler processes an inbound
activity, it MUST:

- Update local RM/EM/CS state to reflect the sender's assertion
- NOT interpret the activity as an instruction to execute work on the sender's
  behalf

**Outbound activities** (from an actor's outbox) declare that the local actor
completed a state transition. The work causes the activity; the activity does
not cause the work.

**Response activities** (Accept, Reject, TentativeReject) in reply to an Offer
or Invite MUST:

- Set the `object` field to the Offer/Invite activity being responded to,
  passed as a full inline typed object (e.g., `RmSubmitReportActivity`,
  `EmProposeEmbargoActivity`) — bare string IDs are rejected at construction
  time
- Set `inReplyTo` to the ID of the Offer/Invite activity

See `specs/response-format.yaml` RF-02-003, RF-03-003, RF-04-003, RF-08-001.
See `notes/activitystreams-semantics.md` for detailed discussion.

---

### Use-Case Protocol (MANDATORY)

All use-case classes MUST:

- Follow the `UseCase[Req, Res]` Protocol (`vultron/core/ports/use_case.py`)
- Accept `(dl: DataLayer, request: XxxReceivedEvent)` in `__init__`
- Implement `execute() -> None` (or `dict` for trigger use cases)
- Be registered in `USE_CASE_MAP` (in
  `vultron/core/use_cases/use_case_map.py`)
- Use Pydantic models for type-safe access to event fields
- Follow idempotency best practices

Example:

```python
class CreateReportReceivedUseCase:
    def __init__(
        self, dl: DataLayer, request: CreateReportReceivedEvent
    ) -> None:
        self._dl = dl
        self._request = request

    def execute(self) -> None:
        # Access validated event fields via self._request
        # Use self._dl for persistence operations
        # Log state transitions
        ...
```

Reference: `specs/handler-protocol.yaml` for complete requirements and
verification criteria.

### Registry Pattern

The system uses two key registries that MUST stay synchronized:

- `USE_CASE_MAP` (in `vultron/core/use_cases/use_case_map.py`): Maps
  `MessageSemantics` → use-case classes (domain layer)
- `SEMANTICS_ACTIVITY_PATTERNS` (in `vultron/wire/as2/extractor.py`): Maps
  `MessageSemantics` → `ActivityPattern` objects (wire layer); all pattern
  objects are named with a `Pattern` suffix (e.g. `CreateReportPattern`)

When adding new message types:

1. Add enum value to `MessageSemantics` in `vultron/core/models/events.py`
   (re-exported via `vultron/enums.py` for compatibility)
2. Define `ActivityPattern` named `<Type>Pattern` in `vultron/wire/as2/extractor.py`
3. Add pattern to `SEMANTICS_ACTIVITY_PATTERNS` in correct order (specific
   before general)
4. Implement use-case class in `vultron/core/use_cases/`
5. Register use case in `USE_CASE_MAP` in
   `vultron/core/use_cases/use_case_map.py`
6. Add tests verifying pattern matching and use-case invocation

### Layer Separation (MUST)

- **FastAPI routers** (`vultron/adapters/driving/fastapi/routers/`):
  FastAPI endpoints only; delegate immediately to adapter helpers or core use
  cases
- **FastAPI adapter helpers** (`vultron/adapters/driving/fastapi/`): HTTP and
  transport orchestration only; no core business rules
- **Use cases** (`vultron/core/use_cases/`): Business logic; no direct HTTP
  concerns
- **Data Layer port** (`vultron/core/ports/datalayer.py`): `DataLayer`
  Protocol definition; use this for imports in core and handlers
- **Data Layer adapter** (`vultron/adapters/driven/datalayer_sqlite.py`):
  SQLite/SQLModel implementation

Never bypass layer boundaries. Routers should never directly access the data
layer or embed business logic; always go through adapter helpers and/or core
use cases.

### Protocol-Based Design (SHOULD)

Use Protocol classes (not ABC) for defining interfaces:

- `ActivityDispatcher`: Dispatcher implementations
- `BehaviorHandler`: Handler function signature
- `DataLayer`: Persistence operations

This allows duck typing and flexible testing without inheritance requirements.

### Background Processing (MUST)

Inbox handlers MUST:

- Return HTTP 202 within 100ms (per `specs/inbox-endpoint.yaml`)
- Queue activities via FastAPI BackgroundTasks
- Never block endpoint on handler execution

Example:

```python
@router.post("/{actor_id}/inbox")
async def inbox(actor_id: str, activity: dict, background_tasks: BackgroundTasks):
    background_tasks.add_task(inbox_handler, actor_id, activity)
    return Response(status_code=202)
```

### Error Hierarchy (MUST)

All custom exceptions:

- Inherit from `VultronError` (in `vultron/errors.py`)
- Submodule-specific errors in submodule `errors.py` (e.g.,
  `vultron/api/v2/errors.py`)
- **Core dispatcher errors** in `vultron/dispatcher_errors.py` (not
  `api.v2.errors`) to avoid circular imports
- Include contextual information (activity_id, actor_id, message)

HTTP error responses use structured format:

```json
{
    "status": 400,
    "error": "ValidationError",
    "message": "Activity missing required field: object",
    "activity_id": "urn:uuid:..."
}
```

See `specs/error-handling.yaml` for complete error hierarchy and response format.

---

## Coding Rules (Non-Negotiable)

### Naming Conventions

- **ActivityStreams class names**: Use `as_` prefix (e.g., `as_Activity`,
  `as_Actor`) — in the wire layer (`vultron/wire/as2/`) only
- **Wire-layer and core field names**: Use trailing underscore for fields
  whose plain name collides with a Python builtin or reserved word
  (e.g., `id_`, `type_`, `object_`, `context_`) with a Pydantic alias
  for the JSON key (e.g., `id_: str = Field(alias="id")`). See CS-07-002,
  CS-07-003. Do NOT use `as_`-prefixed field names anywhere.
- **Domain class names**: Use CVD-domain vocabulary, not wire-format parallels
  (e.g., `CaseTransferOffer` not `VultronOffer`). See CS-12-001.
- **Vulnerability**: Abbreviated as `vul` (not `vuln`)
- **Handler functions**: Named after semantic action (e.g., `create_report`,
  `accept_invite_actor_to_case`)
- **Handler use cases** (processing received messages): Use `Received` suffix
  (e.g., `CreateReportReceivedUseCase`). See CS-12-002.
- **Trigger use cases** (actor-initiated actions): Use `Svc` prefix
  (e.g., `SvcEngageCaseUseCase`). See CS-12-002.
- **Trigger service functions** in `trigger_services/`: Use a `_trigger`
  **suffix** (not an `svc_` prefix). For example: `engage_case_trigger`
  not `svc_engage_case`. The `Svc` prefix is reserved for use-case class
  names only.
- **Pattern objects**: Descriptive CamelCase (e.g., `CreateReport`,
  `AcceptInviteToEmbargoOnCase`)

### Validation and Type Safety

- Prefer explicit types over inference; avoid `Any` (see CS-11-001)
- Use `pydantic.BaseModel` (v2 style) for all structured data
- Never bypass validation for convenience
- Use Protocol for interface definitions
- Avoid global mutable state
- **Fail-fast domain objects**: Domain events and models MUST validate
  required fields at construction and fail immediately on missing invariants.
  Fields that are required for a specific event subtype MUST NOT be typed
  as `X | None` in that subtype. Subclasses SHOULD narrow optional parent
  fields to required. See `specs/architecture.yaml` ARCH-10-001.
- **Optional string fields MUST follow "if present, then non-empty"**:
  `Optional[str]` fields MUST reject empty strings. Use the shared
  `NonEmptyString` or `OptionalNonEmptyString` type alias from
  `vultron/wire/as2/vocab/base/` when it exists (CS-08-002), or a field
  validator that raises `ValueError` for `""` if the type alias is not yet
  available. This pattern also applies to JSON Schemas derived from Pydantic
  models (`minLength: 1`). See `specs/code-style.yaml` CS-08-001, CS-08-002.
  **Do NOT** add a new per-field `@field_validator` stub for empty-string
  rejection; instead, use or extend the shared type alias.

### Decorator Usage

- Semantic type validation is performed at dispatch time by the `USE_CASE_MAP`
  key lookup in `vultron/core/dispatcher.py`
- Unrecognised semantic types raise `VultronApiHandlerNotFoundError`

### Code Organization

- Prefer small, composable functions
- Raise domain-specific exceptions; do not swallow errors
- Keep formatting and linting aligned with tooling; do not reformat
  unnecessarily

### Markdown Formatting

- **Line length**: Regular text lines MUST NOT exceed 88 characters
- Exceptions: Tables, code blocks, long URLs, or other formatting that requires
  it
- Use `markdownlint-cli2` for linting markdown files; see Miscellaneous tips
  for the correct commands
- Break long sentences at natural points (after commas, conjunctions, etc.)
- Keep list items and paragraphs readable and well-formatted

**Rationale**: Consistent line length improves readability in text editors and
reduces diff noise. 88 characters aligns with Python's Black formatter width.

### Logging Requirements

- Use appropriate levels:
  - **DEBUG**: Diagnostic details (payload contents, detailed flow)
  - **INFO**: Lifecycle events (activity received, state transitions)
  - **WARNING**: Recoverable issues (missing optional fields)
  - **ERROR**: Unrecoverable failures (validation errors, handler exceptions)
  - **CRITICAL**: System-level failures
- Include `activity_id` and `actor_id` in log entries when available
- Log state transitions at INFO level
- Log errors at ERROR level with full context

See `specs/structured-logging.yaml` for complete logging requirements
(consolidates `specs/observability.yaml` logging sections).

---

## Specification-Driven Development

This project uses formal specifications in `specs/` directory defining testable
requirements.

### Loading Specifications

**Always run `uv run spec-dump` before any implementation or design task.**
This produces flat, inheritance-resolved JSON covering all 48 spec files. Raw
`specs/*.yaml` files are for authoring and linting only — do not read them
directly. See `.agents/skills/load-specs/SKILL.md` for field definitions and
usage guidance.

### Working with Specifications

- Each spec defines requirements with unique IDs (e.g., `HP-01-001`)
- Requirements use RFC 2119 keywords: MUST, SHOULD, MAY
- Each requirement has verification criteria
- Implementation changes SHOULD reference relevant requirement IDs
- Some specs consolidate requirements from multiple sources; check the `tags`
  field and `edges` array for cross-references

### Key Specifications

See `specs/README.md` for the full index organized by topic. Key groups:

- **Cross-cutting**: `http-protocol.yaml`, `structured-logging.yaml`,
  `idempotency.yaml`, `error-handling.yaml`
- **Handler pipeline**: `inbox-endpoint.yaml`, `message-validation.yaml`,
  `semantic-extraction.yaml`, `dispatch-routing.yaml`, `handler-protocol.yaml`
- **Quality**: `testability.yaml`, `observability.yaml`, `code-style.yaml`
- **BT integration**: `behavior-tree-integration.yaml`

Always load cross-cutting specs (`ARCH`, `CS`, `TB`, `HP`, `SL`, `EH`) even
when working on a narrow feature — they impose constraints on all code.

### Test Coverage Requirements

- **80%+ line coverage overall** (per `specs/testability.yaml`)
- **100% coverage for critical paths**: message validation, semantic
  extraction, dispatch routing, error handling
- Test structure mirrors source structure
- Tests named `test_*.py` in parallel directories

---

## Testing Expectations

### Test Organization (MUST)

- Test structure mirrors source layout (e.g., `test/adapters/driving/fastapi/`
  mirrors `vultron/adapters/driving/fastapi/`,
  `test/core/use_cases/` mirrors `vultron/core/use_cases/`)
- Test files named `test_*.py`
- Fixtures in `conftest.py` at appropriate directory levels
- Use pytest markers to distinguish unit vs integration tests

### Coverage Requirements (MUST)

Per `specs/testability.yaml`:

- 80%+ line coverage overall
- 100% coverage for critical paths:
  - Message validation
  - Semantic extraction  
  - Dispatch routing
  - Error handling

### Testing Patterns (SHOULD)

- Use `monkeypatch` fixture for dependency injection
- Mock external dependencies in unit tests
- Use real SQLite backend with test data in integration tests
- Verify logs using `caplog` fixture
- Test both success and error paths
- New behavior MUST include tests
- Tests SHOULD validate observable behavior, not implementation details
- Avoid brittle mocks when real components are cheap to instantiate
- One test per workflow is preferred over fragmented stateful tests

### Test Data Quality (MUST)

Per `specs/testability.yaml` TB-05-004 and TB-05-005:

**Domain Objects Over Primitives**:

- ✅ Use full Pydantic models: `VulnerabilityReport(name="TEST-001",
  content="...")`
- ❌ Avoid string IDs or primitives: `object="report-1"`

**Semantic Type Accuracy**:

- ✅ Match semantic to structure: `MessageSemantics.CREATE_REPORT` for
  `Create(VulnerabilityReport)`
- ❌ Avoid generic types in specific tests: `MessageSemantics.UNKNOWN` (unless
  testing unknown handling)

**Complete Activity Structure**:

- ✅ Full URIs: `actor="https://example.org/alice"`
- ❌ Incomplete references: `actor="alice"`

**Rationale**: Poor test data quality masks real bugs. Tests with string IDs
can pass even when handlers expect full objects. Tests with mismatched semantics
don't exercise the actual code paths.

### Handler Testing (MUST)

When implementing handler business logic, tests MUST verify:

- Correct semantic type validation at dispatch time via `USE_CASE_MAP` key lookup
- Payload access via `request` parameter on the use-case class
- State transitions persisted correctly
- Response activities generated (when implemented)
- Error conditions handled appropriately
- Idempotency (same input → same result)

See `specs/handler-protocol.yaml` verification section for complete requirements.

If a change touches the datalayer, include repository-level tests that verify
behavior across backends (in-memory / tinydb) where reasonable.

---

## Quick Reference

### Adding a New Message Type

1. Add `MessageSemantics` enum value in `vultron/core/models/events.py`
2. Define an `ActivityPattern` named `<TypeName>Pattern` in
   `vultron/wire/as2/extractor.py`
3. Add pattern to `SEMANTICS_ACTIVITY_PATTERNS` in
   `vultron/wire/as2/extractor.py` (order matters — specific before general)
4. Implement a use-case class in `vultron/core/use_cases/`:
   - Follow `UseCase[Req, Res]` Protocol; accept `(dl, request)` in `__init__`
   - Implement `execute() -> None`
5. Register in `USE_CASE_MAP` in
   `vultron/core/use_cases/use_case_map.py`
6. Add tests:
   - Pattern matching in `test/test_semantic_activity_patterns.py`
   - Routing coverage in `test/test_semantic_handler_map.py`
   - Use-case logic in `test/core/use_cases/`

### Key Files Map

- **Enums**: `vultron/enums.py` - Re-exports `MessageSemantics` plus
  `OfferStatusEnum`, `VultronObjectType`; `MessageSemantics` is defined in
  `vultron/core/models/events.py`
- **Patterns**: `vultron/wire/as2/extractor.py` - `ActivityPattern`
  definitions (all named `*Pattern`) and `SEMANTICS_ACTIVITY_PATTERNS` dict
  (sole AS2→domain mapping point)
- **Pattern Map**: `vultron/wire/as2/extractor.py` - `find_matching_semantics()`
- **Use Cases**: `vultron/core/use_cases/` - Domain use-case callables;
  accept `(event: VultronEvent, dl: DataLayer) -> None`
- **Use-Case Map**: `vultron/core/use_cases/use_case_map.py` - `USE_CASE_MAP`
  authoritative routing table `MessageSemantics` → use-case callable
- **Dispatcher Port**: `vultron/core/ports/dispatcher.py` - `ActivityDispatcher`
  Protocol (dispatch signature: `dispatch(event, dl)`)
- **Dispatcher**: `vultron/core/dispatcher.py` - `DispatcherBase`,
  `DirectActivityDispatcher`, `get_dispatcher` factory
- **Inbox**: `vultron/adapters/driving/fastapi/routers/actors.py` - Endpoint
  implementation
- **Triggers**: `vultron/adapters/driving/fastapi/routers/trigger_report.py`,
  `trigger_case.py`, `trigger_embargo.py` - Triggerable behavior endpoints
  (`POST /actors/{id}/trigger/{behavior-name}`); see
  `specs/triggerable-behaviors.yaml`
- **Trigger Use Cases**: `vultron/core/use_cases/triggers/` - Trigger use-case
  implementations invoked by FastAPI, CLI, and MCP adapters
- **Errors**: `vultron/errors.py`,
  `vultron/adapters/driving/fastapi/errors.py` - Exception hierarchy
- **Data Layer**: `vultron/core/ports/datalayer.py` - `DataLayer` Protocol
  (port)
- **TinyDB Backend**: `vultron/adapters/driven/datalayer_tinydb.py` - TinyDB
  implementation
- **BT Bridge**: `vultron/core/behaviors/bridge.py` - Handler-to-BT execution
  adapter
- **BT Helpers**: `vultron/core/behaviors/helpers.py` - DataLayer-aware BT
  nodes
- **BT Report**: `vultron/core/behaviors/report/` - Report validation tree and
  nodes
- **BT Prioritize**: `vultron/core/behaviors/report/prioritize_tree.py` -
  engage_case/defer_case trees
- **BT Case**: `vultron/core/behaviors/case/` - Case creation tree and nodes
- **Case Event Log**: `vultron/wire/as2/vocab/objects/case_event.py` -
  `CaseEvent` Pydantic model for trusted-timestamp event logging; use
  `VulnerabilityCase.record_event(object_id, event_type)` to append entries
- **Vocabulary Examples**: `vultron/wire/as2/vocab/examples/` - Canonical
  ActivityStreams activity examples (split into submodules by topic:
  `actor.py`, `case.py`, `embargo.py`, `note.py`, `participant.py`,
  `report.py`, `status.py`); use as reference for message semantics
  and as test fixtures for pattern matching.
- **Demo CLI**: `vultron/demo/cli.py` - Unified `click`-based entry point
  (`vultron-demo` command); sub-commands for each demo plus `all`
- **Demo Utilities**: `vultron/demo/utils.py` - Shared `demo_step`,
  `demo_check`, `DataLayerClient`, and HTTP helper utilities used by all
  demo scripts
- **Demo Scripts**: `vultron/demo/receive_report_demo.py`,
  `initialize_case_demo.py`, `invite_actor_demo.py`,
  `establish_embargo_demo.py`, `status_updates_demo.py`,
  `suggest_actor_demo.py`, `transfer_ownership_demo.py`,
  `acknowledge_demo.py`, `manage_case_demo.py`,
  `initialize_participant_demo.py`, `manage_embargo_demo.py`,
  `manage_participants_demo.py` - End-to-end workflow demonstrations;
  also used by `test/demo/` and Docker Compose configs
- **Case States**: `vultron/case_states/` - RM/EM/CS state machine enums and
  patterns; use as reference for valid state transitions and preconditions
  - **State machine enums are authoritative**: When documentation and code
    disagree on state names or valid states, the enum definitions in
    `vultron/bt/report_management/states.py`,
    `vultron/bt/embargo_management/states.py`, and
    `vultron/case_states/states.py` take precedence. Update the docs, not
    the enums.

### Specification Quick Links

See `specs/` directory for detailed requirements with testable verification
criteria.

---

## Change Protocol

When making non-trivial changes, agents SHOULD:

1. Briefly state assumptions
2. Load specifications with `uv run spec-dump` (see `load-specs` skill) and
   consult requirements relevant to the change
3. Review `notes/` directory for durable design insights
4. Describe the intended change
5. Apply the minimal diff required
6. Update or add tests per Testing Expectations
7. Call out risks or follow-ups

Do not produce speculative or exploratory code unless requested. For proposed
architectural changes, draft an ADR (use `docs/adr/_adr-template.md`) and link
to relevant tests and design notes.

### Commit Workflow

**BEFORE committing**, agents MUST follow the procedure documented in the
relevant skills, in this order:

1. `.agents/skills/format-code/SKILL.md` — Format Python sources
2. `.agents/skills/run-linters/SKILL.md` — Run all four linters (Black, flake8,
   mypy, pyright)
3. `.agents/skills/run-tests/SKILL.md` — Run the test-suite exactly once
4. `.agents/skills/build-docs/SKILL.md` — Build docs in strict mode (only if
   `docs/` files were modified)
5. Commit with message including the Co-authored-by trailer

The skill files contain the exact commands and the required invocation order.

**Why this order matters**:

1. Black formatting is enforced by pre-commit hooks — format (and run
   flake8) first to avoid a failed commit → re-stage → re-commit cycle.
2. All four linters (`black`, `flake8`, `mypy`, `pyright`) MUST pass with
   zero errors before committing. The CI pipeline enforces the same checks;
   failing locally means the PR will fail in CI.
3. The test suite must pass before committing — read the single-run test
   output as documented in the skill file (the skill explains how to capture
   the summary line and why you must not re-run pytest to grep for counts).
4. Documentation MUST build cleanly (use `build-docs` skill) whenever `docs/`
   files are modified. This catches broken links and invalid markdown before CI
   fails.

**When to run formatting and linters**:

- After editing any Python files, before staging for commit
- Run `uv run black vultron/ test/ && uv run flake8 vultron/ test/ && uv run mypy && uv run pyright`
  to check all four linters at once (see `.agents/skills/run-linters/SKILL.md`)
- Do NOT run `black` on markdown files (use `markdownlint-cli2` for those)

**When to run docs build**:

- After editing any files in `docs/` before staging for commit
- See `.agents/skills/build-docs/SKILL.md` for the exact command and instructions
- Fix all reported broken links and anchor issues before staging
- Do not run the docs build if you did not modify any
  `docs/` files

**Alternative**: If you forget and the pre-commit hook reformats files, simply:

```bash
git add -A && git commit -m "Same message"
```

---

## Specification Usage Guidance

### Reading Specifications

- Requirements use RFC 2119 keywords: **MUST**, **SHOULD**, **MAY**
- Each requirement has a unique ID (e.g., `HP-01-001`)
- **Cross-references** link related requirements across specs
- **Verification** sections show how to test requirements
- **Implementation** notes suggest approaches (not mandatory)

### When Specifications Conflict

If requirements appear to conflict:

1. Check **cross-references** in the `edges` array from `uv run spec-dump`
2. Consolidated specs (`http-protocol.yaml`, `structured-logging.yaml`) take
   precedence over older inline requirements
3. MUST requirements override SHOULD/MAY
4. Ask for clarification rather than guessing

### Updating Specifications

When updating specs per LEARN_prompt instructions:

- **Avoid over-specifying implementation details**: Specify *what*, not *how*
- **Keep requirements atomic**: One testable requirement per ID
- **Remove redundancy**: Use cross-references instead of duplicating
  requirements
- **Maintain verification criteria**: Every requirement needs a test
- **Follow existing conventions**: Match style and structure of other specs

---

## Safety & Guardrails

- Treat anything under `/security`, `/auth`, or equivalent paths as sensitive
- Do not generate secrets, credentials, or real tokens
- Flag ambiguous requirements instead of guessing

---

## Project Vocabulary

- Use **`vul`** (not `vuln`) as the abbreviation for vulnerability
- Prefer domain terms already present in the codebase
- Do not invent new terminology without justification

---

## Default Behavior

If instructions are ambiguous:

- Choose correctness over convenience
- Choose explicitness over brevity
- Ask for clarification rather than assuming intent

---

## Common Pitfalls (Lessons Learned)

**See `notes/` for durable design insights.**

### Circular Imports

**Symptom**: `ImportError: cannot import name 'X' from partially initialized
module`

**Causes**:

- Core module importing from `api.v2.*` triggers full app initialization
- Module-level registry initialization that imports handlers
- Deep import chains through `__init__.py` files

**Preferred approach**: Module-level imports are preferred. Resolve circular
dependencies by reorganizing code (e.g., moving shared types to neutral
modules), NOT by switching to lazy imports. Lazy imports make dependency
graphs harder to understand and are inconsistent with Python conventions.

**Local imports are a code smell**: When you encounter imports inside
functions, this signals a potential circular dependency that SHOULD be
refactored to module-level. If modifying code with local imports, try to
refactor them away. Only keep local imports if the circular dependency
cannot be resolved by reorganization.

**Solutions (in order of preference)**:

1. **Refactor first**: Move shared code to neutral modules
   (`types.py`, `dispatcher_errors.py`) to break the import cycle
2. Move shared code to neutral modules (`types.py`, `dispatcher_errors.py`)
3. **Last resort**: Use lazy imports (import inside functions) only when
   refactoring is not possible or practical
4. Add caching to avoid repeated initialization overhead
5. **Before adding imports, trace the chain**: `python -c "import
   vultron.MODULE"`

See `specs/code-style.yaml` CS-05-* for requirements.

### Pattern Matching with ActivityStreams

**Symptom**: `AttributeError: 'str' object has no attribute 'as_type'`

**Cause**: ActivityStreams allows both inline objects and URI string references

**Primary Solution**: Use rehydration before pattern matching:

```python
from vultron.wire.as2.rehydration import rehydrate

# Rehydrate converts string URIs to full objects from data layer
activity = rehydrate(activity)
# Now semantic extraction can safely match on object types
semantic = find_matching_semantics(activity)
```

**Defensive Fallback**: Pattern matching should handle strings gracefully:

```python
if isinstance(field, str):
    return True  # Can't type-check URI references
return pattern == getattr(field, "type_", None)
```

**Architecture**: The `inbox_handler.py` rehydrates activities before
dispatching, so handlers receive fully expanded objects.

See `specs/semantic-extraction.yaml` SE-01-002 and
`vultron/wire/as2/rehydration.py` for details.

### Test Data Quality

**Anti-pattern**:

```python
activity = as_Create(actor="alice", object="report-1")  # Bad: strings
event = CreateReportReceivedEvent(semantic_type=MessageSemantics.UNKNOWN, ...)  # Bad: wrong semantic
```

**Best practice**:

```python
report = VulnerabilityReport(name="TEST-001", content="...")  # Good: proper object
activity = as_Create(actor="https://example.org/alice", object=report)  # Good: full structure
event = CreateReportReceivedEvent(semantic_type=MessageSemantics.CREATE_REPORT, ...)  # Good: matches structure
```

See `specs/testability.yaml` TB-05-004, TB-05-005 for requirements.

### All Protocol-Significant Behavior MUST Be in the BT

**There is no "simple enough to skip" threshold for BT usage.**

All protocol-observable actions and state transitions MUST be implemented as
BT nodes or subtrees. This includes emitting activities, transitioning
RM/EM/CS state, creating/updating domain objects, and cascading to downstream
behaviors. See `specs/behavior-tree-integration.yaml` BT-06-001 and
`notes/bt-integration.md` for the trunk-removed branches model and
subtree composition guidance.

The `execute()` method of a use case MAY contain infrastructure glue only:
instantiate the BT, set up the blackboard from the event, call
`bridge.execute_with_setup()`, check BT status, extract output from
blackboard. Nothing domain-significant lives outside the tree.

**Trigger behavior logic belongs outside the API router**: Triggerable
behavior implementations MUST live in separate modules that can be called
from both API endpoints and CLI commands. API routers handle only request
parsing, validation, and response formatting. See `specs/architecture.yaml`
ARCH-08-001.

**Reuse request/response models before creating new ones**: Before adding a
new Pydantic request or response model to a router, check whether an existing
model can be reused or subclassed. If two models are structurally identical,
define one and reuse it. If a new model adds one field to an existing model,
subclass the existing model. See `specs/code-style.yaml` CS-09-002.

**`EvaluateCasePriority` is outgoing-only**: This BT node (in
`vultron/core/behaviors/report/nodes.py`) is for the **local actor deciding** to
engage or defer a case. Receive-side trees (`EngageCaseBT`, `DeferCaseBT`)
do **not** use it — they only record the **sender's already-made decision** by
updating the sender's `CaseParticipant.participant_status[].rm_state`.

See `specs/behavior-tree-integration.yaml` for formal BT requirements,
`notes/bt-integration.md` for design decisions, and
`notes/bt-integration.md` for the canonical subtree map.

### Protocol Event Cascades (Cascading Automation)

**Symptom**: Demo-runner must manually trigger intermediate protocol steps
that should be automated consequences of a primary event.

**Cause**: Some use-case handlers and BT nodes perform only their immediate
action without triggering the cascading effects required by the protocol.
For example, accepting an invitation should automatically advance RM to
ACCEPTED, but the handler only pre-seeds states and requires a separate
`engage-case` trigger.

**Principle**: The demo-runner (or a human, or an agentic client) should only
trigger *primary events* (submit-report, validate-report, add-note,
propose-embargo). Everything else should cascade automatically via BT
execution or use-case chaining.

**When implementing handlers**: When the primary action implies downstream
cascading effects that appear as parent→child in the canonical CVD protocol
BT, express those cascades as BT subtrees — not as post-BT procedural calls.
See `notes/protocol-event-cascades.md` for the full analysis and gap
inventory, and `notes/bt-integration.md` for the subtree model.

### Post-BT Procedural Cascade Anti-Pattern

**Symptom**: A use case's `execute()` calls a function or another use case
after `bridge.execute_with_setup()` returns — the cascade is invisible in
the behavior tree.

**Cause**: Domain logic or cascades were implemented procedurally after the
BT runs instead of as child subtrees. This breaks auditability: an observer
reading the BT cannot see the full causal chain.

**Example** (the `_auto_engage` violations tracked as D5-7-BTFIX-1/2):

```python
# ❌ ANTI-PATTERN — cascade outside the tree
def execute(self) -> None:
    bridge.execute_with_setup(self._dl, bt, bb)
    self._auto_engage(...)            # ← domain logic AFTER BT
```

```python
# ✅ CORRECT — cascade as child subtree
class ValidateReportBt:
    def setup(self):
        prioritize_subtree = PrioritizeBt(...)  # engage OR defer
        self.root.add_child(prioritize_subtree) # ← inside tree
```

**Rule**: `execute()` contains only infrastructure glue — BT instantiation,
blackboard setup from event, `bt.run()`, status check, output extraction.
Nothing else.

**Formal requirements**: BT-06-001, BT-06-005, BT-06-006 in
`specs/behavior-tree-integration.yaml`. Canonical subtree reference:
`notes/bt-integration.md`.

### py_trees Blackboard Global State

**Symptom**: Test state leaks between tests; blackboard key reads return values
from a previous test

**Cause**: The py_trees blackboard uses a singleton storage dict shared across
all tests in the same process. Without explicit clearing, key values written in
one test persist into the next.

**Solution**: Add an `autouse` fixture in `test/behaviors/conftest.py` that
clears the blackboard before (and optionally after) each test:

```python
import py_trees
import pytest

@pytest.fixture(autouse=True)
def clear_blackboard():
    py_trees.blackboard.Blackboard.storage.clear()
    yield
    py_trees.blackboard.Blackboard.storage.clear()
```

**When this matters**: Key collisions are unlikely in small test suites but
become a problem as the BT test suite grows. Add this fixture proactively to
`test/behaviors/conftest.py` rather than reactively after mysterious failures.

### BT Blackboard Key Naming

**Symptom**: `KeyError` or unexpected `None` from py_trees blackboard reads

**Cause**: py_trees blackboard uses hierarchical key parsing; keys containing
slashes are treated as nested paths, breaking simple key lookups.

**Solution**: Use simplified keys following `{noun}_{id_segment}` pattern:

```python
# Anti-pattern: full URI as key (contains slashes)
bb.set("https://example.org/reports/abc123", report)

# Correct: last URL segment as key suffix
id_segment = report_id.split("/")[-1]
bb.set(f"object_{id_segment}", report)  # e.g., "object_abc123"
```

**Convention**: Use `{noun}_{last_url_segment}` (e.g., `object_abc123`,
`case_def456`). Nodes must register READ/WRITE access in `setup()` before
accessing the blackboard in `update()`.

See `specs/behavior-tree-integration.yaml` BT-03-003.

### Health Check Readiness Gap

**Known gap**: The `/health/ready` endpoint in
`vultron/adapters/driving/fastapi/routers/health.py` currently returns
`{"status": "ok"}` unconditionally. It does **not** check DataLayer
connectivity as required by
`specs/observability.yaml` OB-05-002.

**When implementing readiness**: Add a DataLayer read probe (e.g., attempt a
simple `dl.list()` call) and return HTTP 503 if it fails.

### Docker Health Check Coordination

**Symptom**: Demo container fails to connect to API server with "Connection
refused" despite both containers running

**Cause**: Docker Compose `depends_on: service_started` only waits for container
start, not application readiness

**Solutions**:

1. Add health check to API service in docker-compose.yml:

   ```yaml
   api-dev:
     healthcheck:
       test: ["CMD", "curl", "-f", "http://localhost:7999/health/live"]
       interval: 2s
       timeout: 5s
       retries: 15
   ```

2. Update dependent service to use `condition: service_healthy`:

   ```yaml
   demo:
     depends_on:
       api-dev:
         condition: service_healthy
   ```

3. Implement retry logic in client code (defense in depth):

   ```python
   def check_server_availability(url, max_retries=30, retry_delay=1.0):
       for attempt in range(max_retries):
           try:
               response = requests.get(url, timeout=2)
               if response.ok:
                   return True
           except RequestException:
               if attempt < max_retries - 1:
                   time.sleep(retry_delay)
       return False
   ```

The pitfall above is self-contained. The three-layer solution (Docker health
check, `condition: service_healthy`, and client retry) is the recommended
pattern for any demo or integration test setup.

### FastAPI response_model Filtering

**Symptom**: API endpoints return objects missing subclass-specific fields

**Cause**: FastAPI uses return type annotations as implicit `response_model`,
restricting JSON serialization to fields defined in the annotated class only.

**Example**:

```python
# Anti-pattern: Returns only as_Base fields (6 fields)
def get_object_by_key() -> as_Base:
    return VulnerabilityCase(...)  # Case-specific fields excluded from response

# Correct: No return type annotation allows full serialization
def get_object_by_key():  # or use Union types for specific subclasses
    return VulnerabilityCase(...)  # All fields included in response
```

**Root Cause**: `as_Base` defines 6 fields; subclasses like `VulnerabilityCase`
add more. FastAPI's `response_model` filtering excludes fields not in the base
class model.

**Solution**: Remove return type annotations from endpoints that return multiple
types, or use explicit `Union[Type1, Type2, ...]` if types are known.

**Verification**: Test API serialization completeness, not just database
storage. Check that all expected fields appear in JSON responses.

See `specs/http-protocol.yaml` HTTP-08-001 for guidance.

### Idempotency Responsibility Chain

**Question**: Who is responsible for duplicate detection and idempotency?

**Answer**: Layered responsibility:

1. **Inbox Endpoint** (`inbox-endpoint.md` IE-10): MAY detect duplicate
   activities at HTTP layer (future optimization)
2. **Message Validation** (`message-validation.md` MV-08): SHOULD detect
   duplicate submissions during validation
3. **Handler Functions** (`handler-protocol.md` HP-07): SHOULD implement
   idempotent logic (same input → same result)
4. **Data Layer**: Provides unique ID constraints to prevent duplicate
   persistence

**Best Practice**: Handlers should check for existing records before creating
new ones. Use data layer queries to detect duplicates based on business keys
(e.g., report ID, case ID).

**Current Implementation**: Report handlers (create_report, submit_report) check
for existing offers/reports before creating duplicates. Other handlers should
follow this pattern.

See cross-references: `handler-protocol.md` HP-07-001, `message-validation.md`
MV-08-001, `inbox-endpoint.md` IE-10-001.

---

### `VulnerabilityCase.case_activity` Cannot Store Typed Activities

**Symptom**: Handler writes a typed activity (e.g., `AnnounceEmbargo`) to
`case_activity`, then a subsequent `dl.read(case.id_)` returns a raw TinyDB
`Document` instead of a `VulnerabilityCase`, causing `AttributeError` or
silent state loss.

**Cause**: `VulnerabilityCase.case_activity: list[as_Activity]` uses
`as_Activity.type_: as_ObjectType`. The `as_ObjectType` enum covers only
core AS2 object types (`'Activity'`, `'Note'`, `'Event'`, etc.) — NOT
transitive types like `'Announce'`, `'Add'`, `'Accept'`, `'Reject'`. When a
typed activity is serialized and reloaded, `model_validate` fails with
`Input should be 'Activity', 'Actor', ...` and `record_to_object` falls back
to a raw `Document`.

**Fix**: Do not write specific-typed activities to `case_activity`. Log the
event instead, or store only the activity's `id_` (string) rather than the
full object.

See `notes/activitystreams-semantics.md` for details.

---

### Accept/Reject `object` Field Must Use an Inline Typed Activity Object

**Symptom**: `ValidationError` at construction time when passing a bare string
ID as the `object_` field of an Accept, Reject, or TentativeReject activity.

**Cause**: All Accept/Reject/TentativeReject activity classes now require the
full typed inline activity object as `object_` (e.g., `RmSubmitReportActivity`,
`EmProposeEmbargoActivity`, `RmInviteToCaseActivity`). Bare string IDs and
`as_Link` references are no longer accepted — they are rejected by Pydantic
validation at construction time, preventing ambiguous dispatch.

**Fix**: Pass the full typed inline activity object, not a bare string ID.
If the activity was loaded from the DataLayer as a generic object, coerce it
to the correct type using `model_validate` before passing it.

```python
# Correct — pass the full typed inline object
accept = RmAcceptInviteToCaseActivity(actor=actor.id_, object_=invite)

# Incorrect — bare string ID is rejected at construction time
accept = RmAcceptInviteToCaseActivity(actor=actor.id_, object_=invite.id_)
```

When the original activity is read from the DataLayer as a generic object,
coerce it first:

```python
if not isinstance(invite, RmInviteToCaseActivity):
    invite = RmInviteToCaseActivity.model_validate(
        invite.model_dump(by_alias=True)
    )
accept = RmAcceptInviteToCaseActivity(actor=actor.id_, object_=invite)
```

This applies to all `Accept` / `Reject` / `TentativeReject` responses to
`Invite` or `Offer` activities.

---

### Pydantic Union Serialization Silently Returns `None` for `active_embargo`

**Symptom**: `VulnerabilityCase.active_embargo` is `None` after a round-trip
through the DataLayer, even though it was set to an `EmbargoEvent`.

**Cause**: `active_embargo: EmbargoEvent | as_Link | str | None` — Pydantic
v2 serializes Union types left-to-right. If the stored value is an `as_Event`
(not the `EmbargoEvent` subclass) AND serialized with `by_alias=True`,
Pydantic silently returns `None`.

**Fix**: Always store `embargo.id_` (a string) as `active_embargo` rather
than the full `EmbargoEvent` object. The `validate_by_name=True` in
`VulnerabilityCase.model_config` ensures the string round-trips correctly.
Retrieve the full `EmbargoEvent` from the DataLayer when needed.

See `notes/activitystreams-semantics.md` for details.

---

### `case_status` Field Is a List (Rename Pending)

**Symptom**: `AttributeError` or incorrect logic when treating `case_status` as
a single object.

**Cause**: `VulnerabilityCase.case_status` is a `list[CaseStatusRef]` — the
singular field name is misleading. Spec CM-03-006 requires renaming to
`case_statuses` (history list) with a read-only `case_status` property, but
this rename has not yet landed in the code.

**Until the rename lands**:

- Use `case.current_status` to access the active `CaseStatus` (property that
  sorts by `updated` timestamp).
- Append new `CaseStatus` objects to the list `case.case_status`; do NOT
  assign to `case.case_status` directly or treat it as a scalar.
- The same pattern applies to `CaseParticipant.participant_status` — it is also
  a list; use the most-recent entry by timestamp as the current status.

**See also**: `notes/case-state-model.md` "CaseStatus and ParticipantStatus as
Append-Only History", CM-03-006.

---

### CaseEvent Trusted Timestamps: Use `record_event()`, Never Copy Activity Timestamps

**Symptom**: Case event log entries have incorrect ordering or show timestamps
that differ across actor copies of the same case.

**Cause**: Handler copies the `published` or `updated` timestamp from the
incoming ActivityStreams activity into the event log entry, rather than
using the server clock.

**Fix**: Always record case events via `VulnerabilityCase.record_event()`:

```python
case.record_event(object_id=embargo.id_, event_type="embargo_accepted")
```

`record_event()` sets `received_at` to `now_utc()` internally. **Never
pass `received_at` as an argument** — the helper intentionally omits that
parameter to enforce the invariant.

**Rationale**: The CaseActor's clock is the only trusted source of event
ordering within a case. Using participant-supplied timestamps would allow
different actor copies of a case to disagree on ordering.

See `specs/case-management.yaml` CM-02-009; `notes/case-state-model.md`
"CaseEvent Model for Trusted Timestamps".

---

### ActivityStreams as Wire Format, Not Domain Model

**Symptom**: Refactoring status fields, notes, or embargo tracking requires
coordinated changes across handlers, tests, and DataLayer helpers because the
domain object inherits directly from an ActivityStreams base type.

**Cause**: `VulnerabilityCase` (and related objects) subclass `VultronObject`
which inherits from ActivityStreams `as_Object`. This collapses three distinct
concerns — wire format, domain logic, and persistence — into one object. The
`case_activity` type limitation and `active_embargo` union serialization
failures (documented above) are direct symptoms of this coupling.

**Architectural direction**: The correct long-term fix is a clear translation
boundary between Wire Model (ActivityStreams JSON), Domain Model (BT-facing
objects), and Persistence Model (DataLayer storage). See
`notes/domain-model-separation.md` for the full analysis and recommended next
steps.

**For now**: Work within the existing model. Use the workarounds documented
above for `case_activity`, `active_embargo`, and `case_status`. When proposing
refactors that touch `VulnerabilityCase`, consult
`notes/domain-model-separation.md` first and consider drafting an ADR before
implementing.

---

### Preserve Subclass Identity in ActivityStreams Decorators

**Symptom**: Widespread pyright field-access failures across extractors,
round-trip tests, and subclass-specific code after modifying registration
decorators.

**Cause**: The ActivityStreams registration decorators in
`vultron/wire/as2/vocab/base/registry.py` return `type[BaseModel]` instead of
preserving the generic TypeVar-based return type. When the return type collapses
to `BaseModel`, pyright collapses every decorated subclass back to `BaseModel`.

**Fix**: When modifying those decorators, preserve the decorated class type
using a `TypeVar`-based generic signature. Treat them as a typing-critical
boundary, not just a registration convenience. Never let them return
`type[BaseModel]`.

---

### Black Can Invalidate Inline pyright Suppressions on Wrapped Fields

**Symptom**: pyright errors reappear on inherited Pydantic fields after Black
formats the file, even though suppressions were previously added.

**Cause**: Inline end-of-line `# type: ignore` or `# pyright: ignore`
suppressions on field assignments are brittle once Black wraps the expression
across multiple lines — the suppression is now on a different line than the
field definition.

**Fix**: Use file-level pyright directives
(`# pyright: reportGeneralTypeIssues=false` at the top of the file) for
Pydantic inheritance edge cases where an optional base field is intentionally
narrowed to required in a subclass. Use this sparingly and only when weakening
runtime constraints would be the alternative.

---

### Pytest `filterwarnings = ["error"]` Does Not Catch All Warnings

`pyproject.toml` sets `filterwarnings = ["error"]`, which converts Python
`warnings.warn()` calls into test errors. This prevents silent accumulation
of deprecation and misuse warnings.

**Scope caveat**: This policy applies only to `warnings.warn()` calls
captured by pytest's warning machinery. It does **not** catch
`"Exception ignored in:"` messages printed by the Python interpreter at
process teardown (e.g., `ResourceWarning: unclosed file ...`). Those arise
from finalizers (`__del__`) running after pytest exits and are invisible to
`filterwarnings`.

**Rule for agents**: After running the test suite, also scan the output for
`ResourceWarning` or `"Exception ignored in:"` messages. These signal
unclosed resources and are still bugs even if they do not cause test
failures. File them in `plan/BUGS.md` if not already tracked and fix them
by explicitly closing resources in fixtures.

---

### Pytest Helper Enums Must Not Use `Test*` Names

**Symptom**: `PytestCollectionWarning` emitted for helper enum classes in test
modules: "cannot collect 'TestXxx' because it has a custom `__init__`".

**Cause**: pytest's class collection heuristics treat any class named `Test*`
as a candidate test class, even when it is just a helper enum inheriting from
`Enum`/`IntEnum`.

**Fix**: Name helper enums in `test/` with neutral names: `MockEnum`,
`ExampleState`, `FixtureEnum`, etc. — never `TestEnum` or `Test*`. The
regression test in `test/test_pytest_collection_hygiene.py` enforces this.

---

### Avoid `BaseModel` in Port/Adapter Type Hints

**Symptom**: Core and adapter layers become tightly coupled; refactoring one
layer requires changes in the other.

**Cause**: Using `BaseModel` as a type hint in Protocol definitions, port
interfaces, or cross-layer function signatures exposes Pydantic's internal
structure as an API surface instead of using domain-specific types.

**Fix**: Port interfaces (e.g., `DataLayer`, `ActivityDispatcher`) must use
domain types or abstract protocols, not `BaseModel`. When you see `BaseModel`
in a Protocol or driving/driven adapter interface, treat it as a code smell
indicating the abstraction boundary hasn't been properly defined. Define
explicit domain types for data crossing layer boundaries.

### Activity `name` Field Must Not Use `repr()` or `str()`

**Symptom**: Outbound activities have `name` fields containing Python repr
output (e.g., `VulnerabilityCase(id_='...')`), which is meaningless to
recipients.

**Cause**: A BT node constructed the `name` field using `repr(object_)` or
`str(object_)` rather than semantic content.

**Fix**: Always derive `name` from the object's own attributes:

```python
# Correct
activity_name = object_.name or object_.id_

# Wrong
activity_name = repr(object_)  # Never
activity_name = str(object_)   # Never
```

See `notes/activitystreams-semantics.md` "Activity `name` Field" for details.

### Actor IDs Must Always Be Full URIs

**Symptom**: Routing failures, duplicate actors in the DataLayer, or trust
boundary checks failing because the same actor appears under both a short
UUID and a full URI.

**Cause**: Actor ID was assigned as a bare UUID (`generate_new_id()` default)
at creation time or in seeding code, rather than normalized to a full URI
(e.g., `https://example.org/actors/alice`).

**Fix**: Normalize actor IDs to full URIs at the point of first establishment
(actor creation, seed load, session context). No downstream function should
ever receive a short UUID as an actor ID. Audit `vultron/demo/`,
`vultron/adapters/`, and `vultron/core/` seeding code for bare-UUID assignments.

See `notes/codebase-structure.md` "Actor ID Normalization" for details.

### BT Failure Reason: Use `get_failure_reason()`, Not Generic Error Logs

**Symptom**: BT failure log messages say "BT failed" with no indication of
which node failed or why, making demo and test failures hard to diagnose.

**Cause**: The BT failure handler logs the root node's name without extracting
the `feedback_message` from the failing leaf node.

**Fix**: Use `get_failure_reason(tree)` from `vultron/core/behaviors/bridge.py`:

```python
if bt.root.status == Status.FAILURE:
    reason = get_failure_reason(bt)
    logger.error("BT failed: %s (reason: %s)", bt.root.name, reason)
```

See `notes/bt-integration.md` "BT Failure Reason Propagation" for the
implementation.

### Dead-Letter vs. No-Pattern: Two Distinct UNKNOWN Failure Modes

**Symptom**: Activities with unresolvable `object_` URIs raise
`VultronApiHandlerMissingSemanticError` instead of being silently
dead-lettered.

**Cause**: `find_matching_semantics()` returns `UNKNOWN` for both
"no matching pattern" and "unresolvable `object_`". The dispatcher treats
all UNKNOWN as missing-handler errors.

**Fix**: Distinguish the two failure modes at dispatch time:

| Mode | Cause | Action |
|---|---|---|
| No matching pattern | No `ActivityPattern` for `(type, object_type)` | Raise `VultronApiHandlerMissingSemanticError` |
| Unresolvable object | `object_` still bare string after rehydration | Log WARNING, store dead-letter record, return silently |

See `notes/activitystreams-semantics.md` "Dead-Letter Handling" for the
record schema and `specs/semantic-extraction.yaml` VAM-01-009.

---

## Parallelism and Single-Agent Testing

- Agents may use parallel subagents for complex tasks, but the testing step must
  only ever use a single agent instance to ensure consistency.

---

## Skill Interaction Rules

When a skill requires user input or asks the user a question:

- **Always use the `ask_user` tool.** Never ask questions in plain text
  output — plain text questions are easy to miss and produce no structured
  response.
- Provide a recommended answer or a `choices` array (with the recommended
  option first) on every `ask_user` call.
- The `grill-me` skill is the canonical example: it interviews the user one
  question at a time using `ask_user`. All skills that include an interview
  or clarification phase MUST follow the same pattern.
- When skills compose (e.g., `learn` invokes `grill-me`, `build` invokes
  `study-project-docs`), the `ask_user` rule applies transitively — each
  invoked skill must also use `ask_user` for any user-facing questions.

---

## Governance note for agents

- Agents MAY update `AGENTS.md` to correct or clarify agent rules, but
  substantive changes to this file SHOULD be discussed with a human maintainer
  via Issue or PR. If an agent edits `AGENTS.md`, it must include a short
  rationale in the commit message and open a PR for human review.

---

## Miscellaneous tips

Do not use `black` to format markdown files, it is for python files only.
Use `markdownlint-cli2` for linting markdown. The default config
(`.markdownlint-cli2.yaml`) ignores only `wip_notes/**`.
All other directories (`specs/`, `notes/`, `docs/`, `plan/`) are linted
by the default config.

### Notes frontmatter maintenance (NF-06-001, NF-06-002)

Every `notes/*.md` file (except `notes/README.md`) MUST contain a YAML
frontmatter block at the top of the file with at least `title` and `status`
fields. Valid `status` values are `active`, `draft`, `superseded`, and
`archived`. When `status` is `superseded`, a `superseded_by` field is also
required.

When modifying any `notes/*.md` file, review and update its frontmatter —
in particular `status`, `related_specs`, and `related_notes` — to reflect
any changes in scope or relationships.

A pre-commit hook (`validate-notes-frontmatter`) and a pytest test
(`test/metadata/test_notes_frontmatter.py`) enforce that every notes file
has valid frontmatter. The schema is defined in
`vultron/metadata/notes/schema.py` and the loader in
`vultron/metadata/notes/loader.py`.

### Docs links must be relative

Markdown links in `docs/` MUST be relative to the current file and MUST NOT
go above the `docs/` directory (the site root). Keep relative paths as short
as possible. For example, a link from `docs/a/b/c/file.md` to
`docs/a/d/other.md` should be `../../d/other.md`.

**Before committing changes to `docs/`**, validate the build using the
`.agents/skills/build-docs/SKILL.md` skill:

```bash
uv run mkdocs build --strict
```

This catches broken anchor links, invalid markdown, and other documentation
issues. The build MUST pass without warnings before staging changes for commit.
See `.agents/skills/build-docs/SKILL.md` for details.

### Demo script lifecycle logging

Demo scripts use `demo_step` and `demo_check` context managers (defined
in `vultron/demo/utils.py`) to log structured lifecycle events:

- `demo_step(description)` — workflow step: logs 🚥 on entry, 🟢 on success,
  🔴 on exception (re-raises).
- `demo_check(description)` — verification block: logs 📋 on entry, ✅ on
  success, ❌ on exception (re-raises).

Wrap every numbered workflow step and every verification block in these
managers. See `notes/codebase-structure.md` "Demo Script Lifecycle Logging"
for the durable pattern and `test/demo/test_demo_context_managers.py`.

### Archiving IMPLEMENTATION_PLAN.md

`plan/IMPLEMENTATION_PLAN.md` is the forward-looking roadmap (target < 400
lines). Completed phase details and historical implementation notes belong
in `plan/IMPLEMENTATION_HISTORY.md` (append-only; create if absent). See
`specs/project-documentation.yaml` `PD-02-001`.

### `plan/*HISTORY.md` files are append-only

`plan/IMPLEMENTATION_HISTORY.md`, `plan/IDEA-HISTORY.md`, and
`plan/PRIORITY_HISTORY.md` are **append-only** logs. All new entries MUST be
added at the **end** of the file. Past entries MUST NOT be edited or removed.

**Canonical append procedure** (PD-05-004):

1. Ensure the file exists: `bash("touch <file>")` — safe no-op if already
   present; creates an empty file if absent. Do NOT run an existence check
   (`ls`, `test -f`) before this step.
2. Append using `bash` with `cat >> <file>` (heredoc for simple content) or
   Python `open(file, 'a')` (for content with shell-special characters). Do
   NOT use the `edit` tool for appending — `edit` requires a unique `old_str`
   anchor, which history files cannot guarantee.
3. Verify: `bash("tail -30 <file>")` to confirm the entry was written
   correctly.

**Prohibited patterns** (both are bugs — fix if you see them):

- `ls plan/IDEA-HISTORY.md && ... || ...` — existence-check decision tree
- `view(plan/IMPLEMENTATION_HISTORY.md)` without `view_range` — full-file
  read before appending
- Inserting new content at a specific line or before an existing section
  heading instead of at the end

See `specs/project-documentation.yaml` PD-05-001 through PD-05-005 and
`notes/append-only-file-handling.md` for full guidance.
