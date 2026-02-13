# AGENTS.md — Vultron Project

## Purpose
This file defines mandatory constraints and working rules for AI coding agents operating in this repository.

Agents MUST follow these rules when generating, modifying, or reviewing code.

---

## Scope of Allowed Work
Agents MAY:
- Implement small to medium features that do not change public APIs or persistence schemas
- Refactor existing code without changing external behavior
- Add or update tests and test fixtures
- Improve typing, validation, and error handling
- Update documentation, examples, and specification markdown in `docs/` and `specs/`
- Propose architectural changes (but not apply them without approval)

Agents MUST NOT:
- Introduce breaking API changes without explicit instruction
- Modify authentication, authorization, or cryptographic logic
- Change persistence schemas or perform data migrations without explicit instruction
- Touch production deployment, CI configuration, or secrets unless explicitly instructed (see exception below for documentation updates)

Note: Small implementation tweaks (non-architectural) do not require an ADR; architectural or protocol changes (component boundaries, persistence paradigms, message formats, or moving away from ActivityStreams) SHOULD be documented as ADRs before merging. See the ADR guidance in `docs/adr/_adr-template.md` for the format and examples.

---

## Technology Stack (Authoritative)
- Python **3.12+** (project `pyproject.toml` specifies `requires-python = ">=3.12"`); CI currently runs tests on Python 3.13
- **FastAPI** for HTTP APIs
  - Route functions that trigger long-running events should use BackgroundTasks for async processing
  - Other internal components can be sync by default, but async is allowed where it makes sense (e.g., external API calls, I/O-bound operations)
- **Pydantic v2** for models and validation (project pins a specific Pydantic version)
- **pytest** for testing
- **mkdocs** with **Material** theme for documentation
- **streamlit** for UI prototyping (if needed)

### Development support tools (approved):
- **uv** for package and environment management (used in CI)
- **black** for code formatting (enforced via pre-commit)
- **mypy** for static type checking (recommended)
- **pylint** / **flake8** for linting (recommended)

Agents MUST NOT introduce alternative frameworks or package managers without explicit approval from the maintainers.

---

## Architectural Constraints
- FastAPI routers define the external API surface only
- Business logic MUST live outside route handlers
- Persistence access MUST be abstracted behind repository or data-layer interfaces
- Pydantic models are the canonical schema for data exchange
- Side effects (I/O, persistence, network) MUST be isolated from pure logic
- **Core modules MUST NOT import from application layer modules** (see `specs/code-style.md` CS-05-001)
  - Core: `behavior_dispatcher.py`, `semantic_map.py`, `semantic_handler_map.py`, `activity_patterns.py`
  - Application layer: `api/v2/*`
  - Use lazy imports or shared neutral modules (e.g., `types.py`, `dispatcher_errors.py`) when dependencies exist

Avoid tight coupling between layers.

When an agent proposes a non-trivial architectural change (new persistence paradigm, swapping ActivityStreams for a different message model, or a major refactor that impacts component boundaries), it SHOULD prepare an ADR and include migration/compatibility notes and tests.

---

# Agent Guidance for Vultron Implementation

This document provides guidance to AI agents working on the Vultron codebase. It supplements the Copilot instructions with implementation-specific advice.

**Last Updated:** 2026-02-13

## Vultron-Specific Architecture

### Semantic Message Processing Pipeline

Vultron processes inbound ActivityStreams activities through a three-stage pipeline:

1. **Inbox Endpoint** (`vultron/api/v2/routers/actors.py`): FastAPI POST endpoint accepting activities
2. **Semantic Extraction** (`vultron/semantic_map.py`): Pattern matching on (Activity Type, Object Type) to determine MessageSemantics
3. **Behavior Dispatch** (`vultron/behavior_dispatcher.py`): Routes to semantic-specific handler functions

**Key constraint:** Semantic extraction uses **ordered pattern matching**. When adding patterns to `SEMANTICS_ACTIVITY_PATTERNS`, place more specific patterns before general ones.

See `specs/dispatch-routing.md`, `specs/semantic-extraction.md`, and ADR-0007 for complete architecture details.

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

Reference: `specs/handler-protocol.md` for complete requirements and verification criteria.

### Registry Pattern

The system uses two key registries that MUST stay synchronized:
- `SEMANTIC_HANDLER_MAP` (in `vultron/semantic_handler_map.py`): Maps MessageSemantics → handler functions
- `SEMANTICS_ACTIVITY_PATTERNS` (in `vultron/semantic_map.py`): Maps MessageSemantics → ActivityPattern objects

When adding new message types:
1. Add enum value to `MessageSemantics` in `vultron/enums.py`
2. Define ActivityPattern in `vultron/activity_patterns.py`
3. Add pattern to `SEMANTICS_ACTIVITY_PATTERNS` in correct order (specific before general)
4. Implement handler in `vultron/api/v2/backend/handlers.py`
5. Register handler in `SEMANTIC_HANDLER_MAP`
6. Add tests verifying pattern matching and handler invocation

### Layer Separation (MUST)

- **Routers** (`vultron/api/v2/routers/`): FastAPI endpoints only; delegate immediately to backend
- **Backend** (`vultron/api/v2/backend/`): Business logic; no direct HTTP concerns
- **Data Layer** (`vultron/api/v2/datalayer/`): Persistence abstraction; use Protocol interface

Never bypass layer boundaries. Routers should never directly access data layer; always go through backend.

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
- Submodule-specific errors in submodule `errors.py` (e.g., `vultron/api/v2/errors.py`)
- **Core dispatcher errors** in `vultron/dispatcher_errors.py` (not `api.v2.errors`) to avoid circular imports
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
- **ActivityStreams types**: Use `as_` prefix (e.g., `as_Activity`, `as_Actor`, `as_type`)
- **Vulnerability**: Abbreviated as `vul` (not `vuln`)
- **Handler functions**: Named after semantic action (e.g., `create_report`, `accept_invite_actor_to_case`)
- **Pattern objects**: Descriptive CamelCase (e.g., `CreateReport`, `AcceptInviteToEmbargoOnCase`)

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
- Keep formatting and linting aligned with tooling; do not reformat unnecessarily

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

See `specs/structured-logging.md` for complete logging requirements (consolidates `specs/observability.md` logging sections).

---

## Specification-Driven Development

This project uses formal specifications in `specs/` directory defining testable requirements.

### Working with Specifications
- Each spec file defines requirements with unique IDs (e.g., `HP-01-001`)
- Requirements use RFC 2119 keywords in section headers (MUST, SHOULD, MAY)
- Each requirement has verification criteria
- Implementation changes SHOULD reference relevant requirement IDs
- **Some specifications consolidate requirements from multiple sources**:
  - `http-protocol.md` consolidates HTTP-related requirements from inbox-endpoint, message-validation, error-handling
  - `structured-logging.md` consolidates logging requirements from observability, error-handling, inbox-endpoint
  - Check spec file headers for "Consolidates:" notes indicating superseded requirements

### Key Specifications
- `specs/meta-specifications.md`: How to read and write specs
- `specs/handler-protocol.md`: Handler function requirements
- `specs/semantic-extraction.md`: Pattern matching rules
- `specs/dispatch-routing.md`: Dispatcher requirements
- `specs/inbox-endpoint.md`: Endpoint behavior
- `specs/http-protocol.md`: HTTP status codes, Content-Type, headers (consolidates parts of inbox-endpoint, message-validation, error-handling)
- `specs/structured-logging.md`: Log format, levels, correlation IDs, audit trail (consolidates parts of observability, error-handling)
- `specs/message-validation.md`: ActivityStreams schema validation
- `specs/error-handling.md`: Error hierarchy and exception types
- `specs/response-format.md`: Response activity generation
- `specs/observability.md`: High-level observability overview (health checks)
- `specs/testability.md`: Testing requirements and patterns
- `specs/code-style.md`: Code formatting and import organization

**Note**: Some specs consolidate requirements from multiple sources; check file headers for cross-references.

When implementing features, consult relevant specs for complete requirements and verification criteria.

### Test Coverage Requirements
- **80%+ line coverage overall** (per `specs/testability.md`)
- **100% coverage for critical paths**: message validation, semantic extraction, dispatch routing, error handling
- Test structure mirrors source structure
- Tests named `test_*.py` in parallel directories

---

## Current Implementation Status

### ✅ Completed Infrastructure
- Semantic extraction and pattern matching
- Behavior dispatcher with Protocol-based design
- Handler protocol with `@verify_semantics` decorator
- Error hierarchy (`VultronError` → `VultronApiError` → specific errors)
- TinyDB data layer implementation
- Inbox endpoint with BackgroundTasks
- All 47 `MessageSemantics` enum values defined
- Registry infrastructure (`SEMANTIC_HANDLER_MAP`, `SEMANTICS_ACTIVITY_PATTERNS`)

### ✅ Report Handlers Complete (6/47 handlers - 13%)
The following report workflow handlers have full business logic:
- `create_report`: Stores VulnerabilityReport + Create activity, handles duplicates
- `submit_report`: Stores VulnerabilityReport + Offer activity (mirrors create_report)
- `validate_report`: Rehydrates objects, updates statuses (ACCEPTED/VALID), creates VulnerabilityCase, adds CreateCase to actor outbox
- `invalidate_report`: Updates offer (TENTATIVELY_REJECTED) and report (INVALID) statuses
- `ack_report`: Logs acknowledgement, stores Read activity
- `close_report`: Updates offer (REJECTED) and report (CLOSED) statuses

**Implementation Pattern**: Rehydrate → validate types → update status → persist → log at INFO level

**Note**: 6 of 47 handlers complete (13%). All handler stubs exist with proper protocol compliance (decorator, signature, registration). Business logic implementation is the primary remaining work.

### ⚠️ Stub Implementations Requiring Business Logic (41 handlers)
Remaining handlers in `vultron/api/v2/backend/handlers.py` are stubs that:
- Log at DEBUG level only
- Return None without side effects
- Do not persist state or generate responses

**Categories needing implementation**:
- Case management (11): `create_case`, `read_case`, `update_case`, `add_report_to_case`, `suggest_actor_to_case`, ownership transfer, etc.
- Actor invitations (6): `invite/accept/reject_invite_actor_to_case`, `invite/accept/reject_invite_actor_to_embargo`
- Embargo management (12): `create_embargo_event`, `read/update/close_embargo_event`, embargo invitations, participant management, etc.
- Participants & metadata (7): case participants, notes, status tracking, remove operations
- Case lifecycle (5): `close_case`, `reopen_case`, case status tracking

When implementing handler business logic:
1. Extract relevant data from `dispatchable.payload`
2. Rehydrate nested object references using data layer
3. Validate business rules and object types
4. Persist state changes via data layer
5. Update actor outbox if creating new activities
6. Generate response activities (when `specs/response-format.md` is implemented)
7. Log state transitions at INFO level (not DEBUG)
8. Handle errors gracefully with appropriate exceptions

### 🔨 Future Work
- Response activity generation (`specs/response-format.md`)
- Outbox processing implementation
- Health endpoint implementation (`specs/observability.md`)
- Duplicate detection/idempotency (`specs/inbox-endpoint.md` IE-10-001)
- Async dispatcher implementation
- Integration tests for full message flows
- Behavior tree integration (per ADR-0002, ADR-0007)

### Note on _old_handlers Directory
The `vultron/api/v2/backend/_old_handlers/` directory contains an earlier implementation approach
that is being migrated to the current handler protocol. Do not add new code to this directory.

### Key Architectural Lessons Learned

From recent implementation work (2026-02-13), critical patterns to follow:

**1. Pydantic Model Validators and Database Round-Tripping**
- Pydantic validators with `mode="after"` run EVERY TIME `model_validate()` is called, including when reconstructing objects from the database
- Validators that create default values (e.g., empty collections) MUST check if the field is already populated to avoid overwriting database values
- **Anti-pattern**: `inbox = OrderedCollection()` (unconditionally creates empty collection)
- **Correct pattern**: `if self.inbox is None: self.inbox = OrderedCollection()` (preserves existing data)
- **Impact**: This bug caused actor inbox/outbox items to disappear after being saved

**2. Data Layer Update Signature**
- `DataLayer.update()` requires TWO arguments: `id` (str) and `record` (dict)
- **Anti-pattern**: `dl.update(actor_obj)` (only one argument)
- **Correct pattern**: `dl.update(actor_obj.as_id, object_to_record(actor_obj))` (both ID and record)
- Always use `object_to_record()` helper to convert Pydantic models to database dictionaries

**3. Actor Inbox Persistence Flow**
- When adding activities to actor inbox/outbox collections, changes must be explicitly persisted
- Pattern: Read actor → Modify inbox/outbox → Call `dl.update()` → Verify persistence
- The TinyDB backend persists to disk immediately; in-memory changes are not automatically saved

**4. Async Background Processing Timing**
- FastAPI BackgroundTasks execute asynchronously after HTTP 202 response
- When testing or verifying side effects, account for async completion time
- Demo scripts may need delays (e.g., 3 seconds) or explicit polling to verify handler completion
- TestClient in pytest may bypass timing issues seen with real HTTP server

**5. Rehydration Before Semantic Extraction**
- ActivityStreams allows both inline objects and URI string references
- The inbox handler MUST call `rehydrate()` before semantic extraction to expand URI references to full objects
- Pattern matching code should still handle strings defensively (`getattr(field, "as_type", None)`)
- See `specs/semantic-extraction.md` SE-01-002 for requirements

These lessons are documented in `plan/IMPLEMENTATION_NOTES.md` with full context and debugging details.

---

## Testing Expectations

### Test Organization (MUST)
- Test structure mirrors source: `test/api/v2/backend/` mirrors `vultron/api/v2/backend/`
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
- **Use proper domain objects** (e.g., `VulnerabilityReport`, not string IDs) in test data
- **Match semantic types to activity structure** (don't use `UNKNOWN` unless testing unknown handling)

See `specs/testability.md` TB-05-004 and TB-05-005 for test data requirements.

### Handler Testing (MUST)
When implementing handler business logic, tests MUST verify:
- Correct semantic type validation via decorator
- Payload access via `dispatchable.payload`
- State transitions persisted correctly
- Response activities generated (when implemented)
- Error conditions handled appropriately
- Idempotency (same input → same result)

See `specs/handler-protocol.md` verification section for complete requirements.

If a change touches the datalayer, include repository-level tests that verify behavior across backends (in-memory / tinydb) where reasonable.

---

## Quick Reference

### Adding a New Message Type
1. Add `MessageSemantics` enum value in `vultron/enums.py`
2. Define `ActivityPattern` in `vultron/activity_patterns.py`
3. Add pattern to `SEMANTICS_ACTIVITY_PATTERNS` in `vultron/semantic_map.py` (order matters!)
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
- **Handler Map**: `vultron/semantic_handler_map.py` - Semantics → Handler mapping
- **Dispatcher**: `vultron/behavior_dispatcher.py` - Dispatch logic
- **Inbox**: `vultron/api/v2/routers/actors.py` - Endpoint implementation
- **Errors**: `vultron/errors.py`, `vultron/api/v2/errors.py` - Exception hierarchy
- **Data Layer**: `vultron/api/v2/datalayer/abc.py` - Persistence abstraction
- **TinyDB Backend**: `vultron/api/v2/datalayer/tinydb.py` - TinyDB implementation

### Specification Quick Links
See `specs/` directory for detailed requirements with testable verification criteria.

---

## Change Protocol

When making non-trivial changes, agents SHOULD:
1. Briefly state assumptions
2. Consult relevant specifications in `specs/` for requirements
3. Review Current Implementation Status above for context
4. Describe the intended change
5. Apply the minimal diff required
6. Update or add tests per Testing Expectations
7. Call out risks or follow-ups

Do not produce speculative or exploratory code unless requested. For proposed architectural changes, draft an ADR (use `docs/adr/_adr-template.md`) and link to relevant tests and design notes.

### Commit Workflow

**BEFORE committing**, agents SHOULD run Black to format code:
```bash
black vultron/ test/
```

This avoids the inefficient cycle of:
1. `git commit` → pre-commit hook runs Black → reformats files → commit fails
2. `git add` → re-stage reformatted files
3. `git commit` → try again

**Why this matters**: Pre-commit hooks are configured to enforce Black formatting. Running Black before committing ensures a clean single-commit workflow.

**When to run Black**:
- After editing any Python files
- Before staging files for commit
- As part of your validation process

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

2. **Message processing pipeline**:
   - `inbox-endpoint.md`: FastAPI endpoint behavior
   - `message-validation.md`: Activity validation rules
   - `semantic-extraction.md`: Pattern matching rules
   - `dispatch-routing.md`: Handler routing
   - `handler-protocol.md`: Handler function requirements

3. **Quality and observability**:
   - `error-handling.md`: Exception hierarchy
   - `response-format.md`: Response activity generation
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
2. Consolidated specs (http-protocol.md, structured-logging.md) take precedence over older inline requirements
3. MUST requirements override SHOULD/MAY
4. Ask for clarification rather than guessing

### Updating Specifications

When updating specs per LEARN_prompt instructions:
- **Avoid over-specifying implementation details**: Specify *what*, not *how*
- **Keep requirements atomic**: One testable requirement per ID
- **Remove redundancy**: Use cross-references instead of duplicating requirements
- **Maintain verification criteria**: Every requirement needs a test
- **Follow existing conventions**: Match style and structure of other specs

**Recent Consolidation (2026-02-13)**:
- Created `http-protocol.md` to consolidate HTTP status codes and Content-Type validation
- Created `structured-logging.md` to consolidate logging format and correlation ID requirements
- Updated `inbox-endpoint.md` to reference consolidated specs via cross-references
- This reduces duplication and creates single source of truth for common requirements

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

### Circular Imports
**Symptom**: `ImportError: cannot import name 'X' from partially initialized module`

**Causes**:
- Core module importing from `api.v2.*` triggers full app initialization
- Module-level registry initialization that imports handlers
- Deep import chains through `__init__.py` files

**Solutions**:
1. Move shared code to neutral modules (`types.py`, `dispatcher_errors.py`)
2. Use lazy imports (import inside functions, not at module level)
3. Add caching to avoid repeated initialization overhead
4. **Before adding imports, trace the chain**: `python -c "import vultron.MODULE"`

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

**Architecture**: The `inbox_handler.py` rehydrates activities before dispatching, so handlers receive fully expanded objects.

See `specs/semantic-extraction.md` SE-01-002 and `vultron/api/v2/data/rehydration.py` for details.

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

---

## Parallelism and Single-Agent Testing

- Agents may use parallel subagents for complex tasks, but the testing step must only
  ever use a single agent instance to ensure consistency.

---

## Governance note for agents
- Agents MAY update `AGENTS.md` to correct or clarify agent rules, but substantive changes to this file SHOULD be discussed with a human maintainer via Issue or PR. If an agent edits `AGENTS.md`, it must include a short rationale in the commit message and open a PR for human review.
