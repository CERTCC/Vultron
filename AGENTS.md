# AGENTS.md — Vultron Project

## Purpose

This file provides quick technical reference for AI coding agents working in
this repository. For implementation status, lessons learned, and design
insights, see `plan/IMPLEMENTATION_NOTES.md`.

Agents MUST follow these rules when generating, modifying, or reviewing code.

**See also**: `specs/project-documentation.md` for documentation structure
guidance.

---

## Agent Quickstart

A short, actionable checklist for AI coding agents who need to be productive
quickly in this repo.

- Read this file and the `specs/` folder first; specs contain testable
  requirements (MUST/SHOULD/MAY).
- Key architecture: FastAPI inbox → semantic extraction
  (`vultron/semantic_map.py`) → behavior dispatcher
  (`vultron/behavior_dispatcher.py`) → registered handler
  (`vultron/api/v2/backend/handlers.py`).
- Follow the Handler Protocol: handlers accept a single `DispatchActivity`
  param, use `@verify_semantics(...)`, and read `dispatchable.payload`.

Checklist (edit → validate → commit):

1. Implement or modify code in `vultron/`.
2. Add/adjust tests under `test/` mirroring the source layout.
3. Run formatter, then tests locally before committing.

Essential commands (run in zsh):

```bash
# Format code (pre-commit enforces Black)
black vultron/ test/

# Run full test-suite — use EXACTLY this command, ONCE, and read tail -5
uv run pytest --tb=short 2>&1 | tail -5

# Run a specific test file
uv run pytest test/test_semantic_activity_patterns.py -v

# Run the demo server locally (development/demo)
uv run uvicorn vultron.api.main:app --host localhost --port 7999 --reload
```

**Full test-suite rule**: Run `uv run pytest --tb=short 2>&1 | tail -5` exactly
**once** per validation cycle. The last 5 lines always contain the summary (e.g.
`472 passed, 2 xfailed in 40s`) and any short tracebacks for failures. Do NOT
re-run to grep for counts — read the tail output directly. Do NOT use `-q` for
the full suite; it suppresses the summary line in some terminal configurations.

Quick pointers and gotchas:

- Order matters in `SEMANTICS_ACTIVITY_PATTERNS` (place more specific patterns
  first).
- Always call `rehydrate()` on incoming activities to expand URI references
  before pattern matching.
- Use `object_to_record()` + `dl.update(id, record)` when persisting Pydantic
  models to the datalayer (TinyDB uses explicit id + dict).
- FastAPI endpoints should return 202 quickly and schedule background work with
  `BackgroundTasks`.

Examples (handler & datalayer):

```python
@verify_semantics(MessageSemantics.CREATE_REPORT)
def create_report(dispatchable: DispatchActivity) -> None:
    payload = dispatchable.payload
    # rehydrate nested refs, validate, persist via datalayer.update(id, record)
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
- **black** for code formatting (enforced via pre-commit)
- **mypy** for static type checking (recommended)
- **pylint** / **flake8** for linting (recommended)

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
  `specs/code-style.md` CS-05-001)
  - Core: `behavior_dispatcher.py`, `semantic_map.py`,
    `semantic_handler_map.py`, `activity_patterns.py`
  - Application layer: `api/v2/*`
  - Use lazy imports or shared neutral modules (e.g., `types.py`,
    `dispatcher_errors.py`) when dependencies exist

Avoid tight coupling between layers.

When an agent proposes a non-trivial architectural change (new persistence
paradigm, swapping ActivityStreams for a different message model, or a major
refactor that impacts component boundaries), it SHOULD prepare an ADR and
include migration/compatibility notes and tests.

---

# Agent Guidance for Vultron Implementation

This document provides guidance to AI agents working on the Vultron codebase.
It supplements the Copilot instructions with implementation-specific advice.

**Last Updated:** 2026-02-18

**For implementation status and lessons learned**, see
`plan/IMPLEMENTATION_NOTES.md`.

## Vultron-Specific Architecture

### Semantic Message Processing Pipeline

Vultron processes inbound ActivityStreams activities through a three-stage
pipeline:

1. **Inbox Endpoint** (`vultron/api/v2/routers/actors.py`): FastAPI POST
   endpoint accepting activities
2. **Semantic Extraction** (`vultron/semantic_map.py`): Pattern matching on
   (Activity Type, Object Type) to determine MessageSemantics
3. **Behavior Dispatch** (`vultron/behavior_dispatcher.py`): Routes to
   semantic-specific handler functions

**Key constraint:** Semantic extraction uses **ordered pattern matching**. When
adding patterns to `SEMANTICS_ACTIVITY_PATTERNS`, place more specific patterns
before general ones.

See `specs/dispatch-routing.md`, `specs/semantic-extraction.md`, and ADR-0007
for complete architecture details.

### Handler Protocol (MANDATORY)

All handler functions MUST:

- Accept single `DispatchActivity` parameter
- Use `@verify_semantics(MessageSemantics.X)` decorator
- Be registered in `SEMANTIC_HANDLER_MAP`
- Access activity data via `dispatchable.payload`
- Use Pydantic models for type-safe access
- Follow idempotency best practices

Example:

```python
@verify_semantics(MessageSemantics.CREATE_REPORT)
def create_report(dispatchable: DispatchActivity) -> None:
    payload = dispatchable.payload
    # Access validated activity data from payload
    # Implement business logic
    # Log state transitions
```

Reference: `specs/handler-protocol.md` for complete requirements and
verification criteria.

### Registry Pattern

The system uses two key registries that MUST stay synchronized:

- `SEMANTIC_HANDLER_MAP` (in `vultron/semantic_handler_map.py`): Maps
  MessageSemantics → handler functions
- `SEMANTICS_ACTIVITY_PATTERNS` (in `vultron/semantic_map.py`): Maps
  MessageSemantics → ActivityPattern objects

When adding new message types:

1. Add enum value to `MessageSemantics` in `vultron/enums.py`
2. Define ActivityPattern in `vultron/activity_patterns.py`
3. Add pattern to `SEMANTICS_ACTIVITY_PATTERNS` in correct order (specific
   before general)
4. Implement handler in `vultron/api/v2/backend/handlers.py`
5. Register handler in `SEMANTIC_HANDLER_MAP`
6. Add tests verifying pattern matching and handler invocation

### Layer Separation (MUST)

- **Routers** (`vultron/api/v2/routers/`): FastAPI endpoints only; delegate
  immediately to backend
- **Backend** (`vultron/api/v2/backend/`): Business logic; no direct HTTP
  concerns
- **Data Layer** (`vultron/api/v2/datalayer/`): Persistence abstraction; use
  Protocol interface

Never bypass layer boundaries. Routers should never directly access data layer;
always go through backend.

### Protocol-Based Design (SHOULD)

Use Protocol classes (not ABC) for defining interfaces:

- `ActivityDispatcher`: Dispatcher implementations
- `BehaviorHandler`: Handler function signature
- `DataLayer`: Persistence operations

This allows duck typing and flexible testing without inheritance requirements.

### Background Processing (MUST)

Inbox handlers MUST:

- Return HTTP 202 within 100ms (per `specs/inbox-endpoint.md`)
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

See `specs/error-handling.md` for complete error hierarchy and response format.

---

## Coding Rules (Non-Negotiable)

### Naming Conventions

- **ActivityStreams types**: Use `as_` prefix (e.g., `as_Activity`, `as_Actor`,
  `as_type`)
- **Vulnerability**: Abbreviated as `vul` (not `vuln`)
- **Handler functions**: Named after semantic action (e.g., `create_report`,
  `accept_invite_actor_to_case`)
- **Pattern objects**: Descriptive CamelCase (e.g., `CreateReport`,
  `AcceptInviteToEmbargoOnCase`)

### Validation and Type Safety

- Prefer explicit types over inference
- Use `pydantic.BaseModel` (v2 style) for all structured data
- Never bypass validation for convenience
- Use Protocol for interface definitions
- Avoid global mutable state

### Decorator Usage

- Handler functions MUST use `@verify_semantics(MessageSemantics.X)`
- Decorator verifies semantic type matches actual activity structure
- Raises `VultronApiHandlerSemanticMismatchError` on mismatch

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
  for the correct commands (default config ignores `AGENTS.md` and `specs/**`)
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

See `specs/structured-logging.md` for complete logging requirements
(consolidates `specs/observability.md` logging sections).

---

## Specification-Driven Development

This project uses formal specifications in `specs/` directory defining testable
requirements.

### Working with Specifications

- Each spec file defines requirements with unique IDs (e.g., `HP-01-001`)
- Requirements use RFC 2119 keywords in section headers (MUST, SHOULD, MAY)
- Each requirement has verification criteria
- Implementation changes SHOULD reference relevant requirement IDs
- **Some specifications consolidate requirements from multiple sources**:
  - `http-protocol.md` consolidates HTTP-related requirements from
    inbox-endpoint, message-validation, error-handling
  - `structured-logging.md` consolidates logging requirements from
    observability, error-handling, inbox-endpoint
  - Check spec file headers for "Consolidates:" notes indicating superseded
    requirements

### Key Specifications

- `specs/meta-specifications.md`: How to read and write specs
- `specs/handler-protocol.md`: Handler function requirements
- `specs/semantic-extraction.md`: Pattern matching rules
- `specs/dispatch-routing.md`: Dispatcher requirements
- `specs/inbox-endpoint.md`: Endpoint behavior
- `specs/http-protocol.md`: HTTP status codes, Content-Type, headers
  (consolidates parts of inbox-endpoint, message-validation, error-handling)
- `specs/structured-logging.md`: Log format, levels, correlation IDs, audit
  trail (consolidates parts of observability, error-handling)
- `specs/message-validation.md`: ActivityStreams schema validation
- `specs/error-handling.md`: Error hierarchy and exception types
- `specs/response-format.md`: Response activity generation
- `specs/observability.md`: High-level observability overview (health checks)
- `specs/testability.md`: Testing requirements and patterns
- `specs/code-style.md`: Code formatting and import organization
- `specs/project-documentation.md`: Documentation file structure and purpose

**Note**: Some specs consolidate requirements from multiple sources; check file
headers for cross-references.

When implementing features, consult relevant specs for complete requirements and
verification criteria.

### Test Coverage Requirements

- **80%+ line coverage overall** (per `specs/testability.md`)
- **100% coverage for critical paths**: message validation, semantic
  extraction, dispatch routing, error handling
- Test structure mirrors source structure
- Tests named `test_*.py` in parallel directories

---

## Testing Expectations

### Test Organization (MUST)

- Test structure mirrors source: `test/api/v2/backend/` mirrors
  `vultron/api/v2/backend/`
- Test files named `test_*.py`
- Fixtures in `conftest.py` at appropriate directory levels
- Use pytest markers to distinguish unit vs integration tests

### Coverage Requirements (MUST)

Per `specs/testability.md`:

- 80%+ line coverage overall
- 100% coverage for critical paths:
  - Message validation
  - Semantic extraction  
  - Dispatch routing
  - Error handling

### Testing Patterns (SHOULD)

- Use `monkeypatch` fixture for dependency injection
- Mock external dependencies in unit tests
- Use real TinyDB backend with test data in integration tests
- Verify logs using `caplog` fixture
- Test both success and error paths
- New behavior MUST include tests
- Tests SHOULD validate observable behavior, not implementation details
- Avoid brittle mocks when real components are cheap to instantiate
- One test per workflow is preferred over fragmented stateful tests

### Test Data Quality (MUST)

Per `specs/testability.md` TB-05-004 and TB-05-005:

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

- Correct semantic type validation via decorator
- Payload access via `dispatchable.payload`
- State transitions persisted correctly
- Response activities generated (when implemented)
- Error conditions handled appropriately
- Idempotency (same input → same result)

See `specs/handler-protocol.md` verification section for complete requirements.

If a change touches the datalayer, include repository-level tests that verify
behavior across backends (in-memory / tinydb) where reasonable.

---

## Quick Reference

### Adding a New Message Type

1. Add `MessageSemantics` enum value in `vultron/enums.py`
2. Define `ActivityPattern` in `vultron/activity_patterns.py`
3. Add pattern to `SEMANTICS_ACTIVITY_PATTERNS` in `vultron/semantic_map.py`
   (order matters!)
4. Implement handler function in `vultron/api/v2/backend/handlers.py`:
   - Use `@verify_semantics(MessageSemantics.NEW_TYPE)` decorator
   - Accept `dispatchable: DispatchActivity` parameter
   - Access data via `dispatchable.payload`
5. Register in `SEMANTIC_HANDLER_MAP` in `vultron/semantic_handler_map.py`
6. Add tests:
   - Pattern matching in `test/test_semantic_activity_patterns.py`
   - Handler registration in `test/test_semantic_handler_map.py`
   - Handler behavior in `test/api/v2/backend/test_handlers.py`

### Key Files Map

- **Enums**: `vultron/enums.py` - All enum types including MessageSemantics
- **Patterns**: `vultron/activity_patterns.py` - Pattern definitions
- **Pattern Map**: `vultron/semantic_map.py` - Semantics → Pattern mapping
- **Handlers**: `vultron/api/v2/backend/handlers.py` - Handler implementations
- **Handler Map**: `vultron/semantic_handler_map.py` - Semantics → Handler
  mapping
- **Dispatcher**: `vultron/behavior_dispatcher.py` - Dispatch logic
- **Inbox**: `vultron/api/v2/routers/actors.py` - Endpoint implementation
- **Errors**: `vultron/errors.py`, `vultron/api/v2/errors.py` - Exception
  hierarchy
- **Data Layer**: `vultron/api/v2/datalayer/abc.py` - Persistence abstraction
- **TinyDB Backend**: `vultron/api/v2/datalayer/tinydb.py` - TinyDB
  implementation
- **BT Bridge**: `vultron/behaviors/bridge.py` - Handler-to-BT execution adapter
- **BT Helpers**: `vultron/behaviors/helpers.py` - DataLayer-aware BT nodes
- **BT Report**: `vultron/behaviors/report/` - Report validation tree and nodes

### Specification Quick Links

See `specs/` directory for detailed requirements with testable verification
criteria.

---

## Change Protocol

When making non-trivial changes, agents SHOULD:

1. Briefly state assumptions
2. Consult relevant specifications in `specs/` for requirements
3. Review `plan/IMPLEMENTATION_NOTES.md` for context and lessons learned
4. Describe the intended change
5. Apply the minimal diff required
6. Update or add tests per Testing Expectations
7. Call out risks or follow-ups

Do not produce speculative or exploratory code unless requested. For proposed
architectural changes, draft an ADR (use `docs/adr/_adr-template.md`) and link
to relevant tests and design notes.

### Commit Workflow

**BEFORE committing**, agents MUST run Black then the full test suite exactly
once, in this order:

```bash
black vultron/ test/
uv run pytest --tb=short 2>&1 | tail -5
git add -A && git commit -m "..."
```

**Why this order matters**:

1. Black formatting is enforced by pre-commit hooks — format first to avoid a
   failed commit → re-stage → re-commit cycle.
2. The test suite must pass before committing — read the `tail -5` output
   directly for the summary line (e.g. `472 passed, 2 xfailed in 40s`).
   Do NOT re-run pytest to grep for counts. Run it **once** and read the tail.

**When to run Black**:

- After editing any Python files, before staging for commit
- Do NOT run `black` on markdown files (use `markdownlint-cli2` for those)

**Alternative**: If you forget and the pre-commit hook reformats files, simply:

```bash
git add -A && git commit -m "Same message"
```

---

## Specification Usage Guidance

### Key Specifications

The `specs/` directory contains testable requirements. Key specifications:

1. **Cross-cutting concerns** (reference these first):
   - `http-protocol.md`: HTTP status codes, Content-Type, size limits
   - `structured-logging.md`: Log format, correlation IDs, log levels
   - `meta-specifications.md`: How to read and write specs
   - `project-documentation.md`: Documentation file structure

2. **Message processing pipeline**:
   - `inbox-endpoint.md`: FastAPI endpoint behavior
   - `message-validation.md`: Activity validation rules
   - `semantic-extraction.md`: Pattern matching rules
   - `dispatch-routing.md`: Handler routing
   - `handler-protocol.md`: Handler function requirements

3. **Quality and observability**:
   - `error-handling.md`: Exception hierarchy
   - `response-format.md`: Response activity generation
   - `outbox.md`: Outbox population and delivery
   - `observability.md`: Health checks and monitoring
   - `testability.md`: Test coverage requirements
   - `code-style.md`: Code formatting and organization

### Reading Specifications

- Requirements use RFC 2119 keywords: **MUST**, **SHOULD**, **MAY**
- Each requirement has a unique ID (e.g., `HP-01-001`)
- **Cross-references** link related requirements across specs
- **Verification** sections show how to test requirements
- **Implementation** notes suggest approaches (not mandatory)

### When Specifications Conflict

If requirements appear to conflict:

1. Check **cross-references** for clarification
2. Consolidated specs (http-protocol.md, structured-logging.md) take precedence
   over older inline requirements
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

**See `plan/IMPLEMENTATION_NOTES.md` for detailed lessons learned and debugging
history.**

### Circular Imports

**Symptom**: `ImportError: cannot import name 'X' from partially initialized
module`

**Causes**:

- Core module importing from `api.v2.*` triggers full app initialization
- Module-level registry initialization that imports handlers
- Deep import chains through `__init__.py` files

**Solutions**:

1. Move shared code to neutral modules (`types.py`, `dispatcher_errors.py`)
2. Use lazy imports (import inside functions, not at module level)
3. Add caching to avoid repeated initialization overhead
4. **Before adding imports, trace the chain**: `python -c "import
   vultron.MODULE"`

See `specs/code-style.md` CS-05-* for requirements.

### Pattern Matching with ActivityStreams

**Symptom**: `AttributeError: 'str' object has no attribute 'as_type'`

**Cause**: ActivityStreams allows both inline objects and URI string references

**Primary Solution**: Use rehydration before pattern matching:

```python
from vultron.api.v2.data.rehydration import rehydrate

# Rehydrate converts string URIs to full objects from data layer
activity = rehydrate(activity)
# Now semantic extraction can safely match on object types
semantic = find_matching_semantics(activity)
```

**Defensive Fallback**: Pattern matching should handle strings gracefully:

```python
if isinstance(field, str):
    return True  # Can't type-check URI references
return pattern == getattr(field, "as_type", None)
```

**Architecture**: The `inbox_handler.py` rehydrates activities before
dispatching, so handlers receive fully expanded objects.

See `specs/semantic-extraction.md` SE-01-002 and
`vultron/api/v2/data/rehydration.py` for details.

### Test Data Quality

**Anti-pattern**:

```python
activity = as_Create(actor="alice", object="report-1")  # Bad: strings
dispatchable = DispatchActivity(semantic_type=MessageSemantics.UNKNOWN, ...)  # Bad: wrong semantic
```

**Best practice**:

```python
report = VulnerabilityReport(name="TEST-001", content="...")  # Good: proper object
activity = as_Create(actor="https://example.org/alice", object=report)  # Good: full structure
dispatchable = DispatchActivity(semantic_type=MessageSemantics.CREATE_REPORT, ...)  # Good: matches structure
```

See `specs/testability.md` TB-05-004, TB-05-005 for requirements.

### When to Use Behavior Trees

Not all handlers need BT execution. Use this guide when deciding:

**Use BTs** (complex orchestration):

- Multiple conditional branches in the workflow
- State machine transitions (RM/EM/CS state changes with preconditions)
- Policy injection needed (e.g., pluggable validation rules)
- Workflow composition (reuse subtrees across handlers)
- Reference implementations for CVD protocol documentation alignment

**Use procedural code** (simple workflows):

- Simple CRUD operations (ack_report, create_report, submit_report)
- Linear workflows with 3–5 steps and no branching
- Single database read/write operations
- Logging-only or passthrough operations

**Uncertain?** Start procedural; refactor to BT if branching complexity grows.

See `specs/behavior-tree-integration.md` for BT integration requirements and
`plan/IMPLEMENTATION_NOTES.md` for BT integration lessons.

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

See `specs/behavior-tree-integration.md` BT-03-003.

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

See `plan/IMPLEMENTATION_NOTES.md` Docker sections for complete context.

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

See `specs/http-protocol.md` HTTP-08-001 for guidance.

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

## Parallelism and Single-Agent Testing

- Agents may use parallel subagents for complex tasks, but the testing step must
  only ever use a single agent instance to ensure consistency.

---

## Governance note for agents

- Agents MAY update `AGENTS.md` to correct or clarify agent rules, but
  substantive changes to this file SHOULD be discussed with a human maintainer
  via Issue or PR. If an agent edits `AGENTS.md`, it must include a short
  rationale in the commit message and open a PR for human review.

---

## Running demo server

To run the demo server:

```bash
uv run uvicorn vultron.api.main:app --host localhost --port 7999 --reload
```

## Miscellaneous tips

Do not use `black` to format markdown files, it is for python files only.
Use `markdownlint-cli2` for linting markdown. The default config
(`.markdownlint-cli2.yaml`) ignores `AGENTS.md` and `specs/**`. To lint those
files, run markdownlint from outside the repo using the strict config, which
has the same rules but no ignores:

```bash
# Lint docs/ with the default config (ignores AGENTS.md and specs/**)
markdownlint-cli2 "docs/**/*.md" --fix

# Lint AGENTS.md and specs/** — must run from /tmp to bypass local config discovery
cd /tmp && markdownlint-cli2 \
  --config /Users/adh/Documents/git/vultron_pub/strict.markdownlint-cli2.yaml \
  /Users/adh/Documents/git/vultron_pub/AGENTS.md \
  "/Users/adh/Documents/git/vultron_pub/specs/**/*.md" --fix
```

The `strict.markdownlint-cli2.yaml` file at the repo root contains the same
rules as the default config with the `ignores` block removed.
