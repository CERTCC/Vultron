# Vultron API v2 Specifications

## Overview

This directory contains formal, testable specifications for the Vultron API v2 implementation. Each specification defines requirements using RFC 2119 keywords (MUST, SHOULD, MAY) with unique requirement IDs and verification criteria.

**How to read specifications**: See `meta-specifications.md` for style guide and conventions.

---

## Specification Structure

Specifications are organized by topic with minimal overlap. Cross-references link related requirements across files.

### Core Architecture

**Handler Pipeline** (message processing flow):

1. **`inbox-endpoint.md`** - FastAPI HTTP endpoint accepting ActivityStreams activities
2. **`message-validation.md`** - ActivityStreams 2.0 structure and semantic validation
3. **`semantic-extraction.md`** - Pattern matching to determine message semantics
4. **`dispatch-routing.md`** - Routing DispatchActivity to handler functions
5. **`handler-protocol.md`** - Handler function contract and implementation patterns

**Behavior Tree Integration** (optional for complex workflows):

6. **`behavior-tree-integration.md`** - BT execution model, bridge layer, DataLayer integration

### Case and Actor Management

7. **`case-management.md`** - CaseActor lifecycle, actor isolation, RM/EM/CS/VFD state model

### Cross-Cutting Concerns

**HTTP Protocol**:

- **`http-protocol.md`** - Status codes, Content-Type, size limits, error response format

**Logging and Observability**:

- **`structured-logging.md`** - Log format, correlation IDs, log levels, audit trail
- **`observability.md`** - Health check endpoints

**Error Handling**:

- **`error-handling.md`** - Exception hierarchy and error categories

**Quality Attributes**:

- **`idempotency.md`** - Duplicate detection and idempotent processing
- **`testability.md`** - Test coverage requirements and test organization

### Response Generation

**Future Implementation**:

- **`response-format.md`** - ActivityStreams response generation (Accept, Reject, etc.)
- **`outbox.md`** - Actor outbox structure and delivery

### Code Standards

- **`code-style.md`** - Python formatting, import organization, circular import prevention
- **`meta-specifications.md`** - How to write and maintain specifications

### Project and Agent Guidance

- **`project-documentation.md`** - Documentation file structure and purpose
- **`prototype-shortcuts.md`** - Permissible shortcuts for the prototype stage
- **`agentic-readiness.md`** - API and CLI requirements for automated agent integration

---

## Reading Order

**For new contributors**:

1. Start with `meta-specifications.md` to understand spec structure
2. Read handler pipeline specs in order (inbox → validation → extraction → dispatch → handler)
3. Consult cross-cutting specs as needed

**For implementing features**:

1. Identify relevant specifications from structure above
2. Read requirements with verification criteria
3. Follow cross-references for related requirements
4. Check `plan/IMPLEMENTATION_PLAN.md` for implementation status

**For reviewing code**:

1. Verify requirements are met per verification criteria
2. Check cross-referenced specs for related constraints
3. Ensure tests cover verification scenarios

---

## Requirement ID Format

Each requirement has a unique ID: `PREFIX-NN-NNN`

- **PREFIX**: Specification abbreviation (e.g., `HP` = Handler Protocol, `IE` = Inbox Endpoint)
- **NN**: Category number within specification
- **NNN**: Requirement number within category

Example: `HP-04-002` = Handler Protocol, category 4 (Payload Access), requirement 2

**Note**: The `HP-` prefix is reserved for `handler-protocol.md`. The
`http-protocol.md` file uses the `HTTP-` prefix to avoid ambiguity.

## Requirement Tags

Some requirements carry special tags to indicate scope or applicability:

- **`PROD_ONLY`**: Requirement may be deferred during the prototype stage.
  See `prototype-shortcuts.md` PROTO-04-001 for the deferral policy.
  Tagged requirements appear inline after the requirement ID:
  `- `REQ-ID` `PROD_ONLY` Requirement statement`

  Common categories of `PROD_ONLY` requirements include:
  - Authentication and authorization (per PROTO-01-001)
  - Federation and cross-server delivery (per PROTO-02-001/02-002)
  - Rate limiting and request size enforcement
  - Correlation ID propagation and structured log format
  - Audit and data access logging
  - Execution timeout enforcement
  - Future performance optimizations

---


Some specifications consolidate requirements from multiple sources to create a single source of truth:

- **`http-protocol.md`** consolidates HTTP requirements from `inbox-endpoint.md`,
  `message-validation.md`, `error-handling.md`, and `agentic-readiness.md`
- **`structured-logging.md`** consolidates logging requirements from `observability.md`,
  `error-handling.md`, `inbox-endpoint.md`
- **`idempotency.md`** consolidates duplicate detection requirements from
  `inbox-endpoint.md`, `message-validation.md`, `handler-protocol.md`,
  `response-format.md`
- **`case-management.md`** consolidates case state and actor isolation requirements
  from `behavior-tree-integration.md` (BT-09, BT-10), `notes/case-state-model.md`,
  and `plan/PRIORITIES.md` (Priority 100, 200)

When requirements appear consolidated, the consolidating spec is the authoritative
source.

---

## Implementation Status

See `plan/IMPLEMENTATION_PLAN.md` for detailed implementation status by specification.

**Summary (2026-02-20)**:

- ✅ **Core infrastructure complete**: Semantic extraction, dispatch routing, handler protocol, data layer
- ✅ **6/36 handlers complete**: Report workflow (create, submit, validate, invalidate, ack, close)
- ✅ **BT integration Phases BT-1 and BT-2.1 complete**: See `behavior-tree-integration.md`
- ⚠️ **Production readiness partial**: Request validation, error responses need work
- ❌ **Response generation not started**: See `response-format.md`
- ❌ **30 handler stubs remain**: Case management, embargo, participants, notes, statuses

---

## Updating Specifications

When updating specifications:

1. Follow `meta-specifications.md` style guide
2. Keep requirements atomic and testable
3. Update verification criteria when changing requirements
4. Add cross-references for related requirements
5. Update this README if adding/removing specifications
6. Consider consolidation to reduce redundancy

---

## Related Documentation

- **Implementation Plan**: `plan/IMPLEMENTATION_PLAN.md`
- **Implementation Notes**: `plan/IMPLEMENTATION_NOTES.md`
- **Architecture Decisions**: `docs/adr/*.md`
- **ActivityPub Workflows**: `docs/howto/activitypub/activities/*.md`
- **Agent Instructions**: `AGENTS.md` (AI coding agent guidance)
- **Copilot Instructions**: Embedded in system context (development guidance)
