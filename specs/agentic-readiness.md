# Agentic Readiness Specification

## Overview

Requirements for API and CLI design that enable reliable interaction by
automated agents and AI systems. Ensures consistent, machine-parseable
interfaces that support agentic workflows.

**Source**: `plan/PRIORITIES.md` (Priority 1000), API design principles
**Note**: Prototype-stage shortcuts apply; see `prototype-shortcuts.md`
**Cross-references**: `error-handling.md`, `http-protocol.md`,
`structured-logging.md`, `observability.md`

---

## API Discoverability

- `AR-01-001` The API MUST expose a machine-readable OpenAPI JSON schema at
  `/openapi.json`
- `AR-01-002` The API MUST expose rendered documentation UI at `/docs` and
  `/redoc` in development environments
- `AR-01-003` Every endpoint MUST have a unique, stable `operationId`
  following the `{resource}_{action}` naming convention
- `AR-01-004` (MUST) `PROD_ONLY` All possible HTTP response codes for each endpoint
  MUST be declared in the OpenAPI spec with typed response models

## State and Workflow Transitions

- `AR-02-001` `PROD_ONLY` Resources with a `status` field SHOULD include a
  `next_allowed_actions` list identifying valid state transitions from the
  current state
- `AR-02-002` (MUST) All valid states and state transitions for state machine
  resources MUST be documented
- `AR-02-003` `PROD_ONLY` Endpoints with prerequisites MUST return a structured
  error using the `error` field value `"PreconditionFailedError"` when invoked
  out of sequence
  - AR-02-003 depends-on EH-05-001

## Stable Error Types

- `AR-03-001` The API MUST use the `error` field (per `error-handling.md`
  EH-05-001) as a stable, machine-parseable error type identifier
  - Agents MUST be able to branch on `error` without parsing the
    human-readable `message` field
  - AR-03-001 depends-on EH-05-001

## Long-Running Operations

- `AR-04-001` `PROD_ONLY` Long-running operations SHOULD return a job or task
  object immediately with a stable `id` and `status` field
- `AR-04-002` (SHOULD) `PROD_ONLY` A separate polling endpoint or webhook mechanism
  SHOULD be available to report operation completion

## Pagination

- `AR-05-001` Collection endpoints SHOULD expose `limit` and `offset` (or
  `cursor`) query parameters with documented defaults and maximums

## Bulk Operations

- `AR-06-001` (MAY) `PROD_ONLY` Resources that agents may need to create, update, or
  delete in quantity MAY expose batch endpoints (e.g., `POST /v1/items/batch`)

## Actor Discovery Profile

- `AR-10-001` The API MUST expose `GET /actors/{actor_id}/profile` returning an
  ActivityStreams actor profile document for actor discovery and federation
  - Response MUST include `id`, `type`, `inbox`, and `outbox` fields
  - `inbox` and `outbox` MUST be string URLs linking to the actor's inbox
    and outbox collections (not embedded collection objects)
  - Optional profile fields (`name`, `preferredUsername`, `url`, `icon`,
    `image`, `summary`) SHOULD be included when present on the actor
- `AR-10-002` The profile endpoint MUST return HTTP 404 when the actor is not
  found
- `AR-10-003` The profile endpoint MUST support both full actor URI and short
  actor ID (e.g., `vendorco`) as the `actor_id` path parameter

## CVD Action Rules API

- `AR-07-001` The system SHOULD expose an endpoint that returns the set of
  valid CVD actions available to a participant given current case state and
  their role
  - Endpoint:
    `GET /actors/{actor_id}/cases/{case_id}/action-rules`
  - The actor/case pair MUST resolve internally to the matching
    `CaseParticipant`; callers MUST NOT be required to supply both actor ID and
    participant ID
- `AR-07-002` The action rules response MUST be a machine-parseable JSON
  object that includes:
  - The participant's current role (e.g., Vendor, Finder, Coordinator)
  - The participant's current RM, EM, CS, and VFD states
  - A list of valid next actions, each with `name` and `description` fields
- `AR-07-003` `PROD_ONLY` The action rules endpoint MUST be reflected in
  the OpenAPI schema per AR-01-001
  - AR-07-003 depends-on CM-07-001
  - AR-07-003 depends-on CM-07-002
  - AR-07-003 depends-on CM-07-003

## CLI Interface

- `AR-08-001` `PROD_ONLY` The CLI MUST be installable as a Python package entry point
  defined in `pyproject.toml`
- `AR-08-002` `PROD_ONLY` Every CLI command MUST support a structured JSON output mode
  (e.g., `--output json`) emitting machine-parseable JSON to stdout
- `AR-08-003` `PROD_ONLY` CLI commands MUST exit with code `0` on success, `1` on handled
  error, and `2` on usage or argument error
- `AR-08-004` `PROD_ONLY` CLI commands wrapping API calls MUST surface the `error`
  field and `request_id` from API error responses in their JSON error output
- `AR-08-005` `PROD_ONLY` Long-running CLI commands SHOULD support `--wait` / `--no-wait`
  flags; `--no-wait` returns the job object immediately

## MCP Server Adapter

The Model Context Protocol (MCP) server is a driving adapter that exposes the
Vultron core to AI agent tool calls. Like the CLI and HTTP inbox, the MCP
server translates external requests into domain use-case invocations without
containing domain logic.

**Note**: These requirements are later-prototype items, not production-only.
They become relevant once `vultron/core/use_cases/` is formalized (P60-3+).
They are not tagged `PROD_ONLY` because the MCP adapter is a natural extension
of the hexagonal architecture that will be valuable even in prototype-stage
multi-actor scenarios.

- `AR-09-001` A local MCP server adapter MAY be provided at
  `vultron/adapters/driving/mcp_server.py`, exposing Vultron use cases as MCP
  tools
- `AR-09-002` Each MCP tool MUST map 1:1 to a domain use case in
  `vultron/core/use_cases/`, with no business logic in the adapter itself
- `AR-09-003` `PROD_ONLY` The MCP server MUST authenticate tool calls using the
  same actor identity model as the HTTP inbox
- `AR-09-004` MCP tool responses MUST use the same structured JSON format as
  CLI `--output json` responses, enabling consistent AI agent parsing

The MCP adapter is architecturally equivalent to the CLI adapter: both are
driving adapters that invoke the same core use cases. The MCP server allows AI
agents to use Vultron as a tool in automated vulnerability coordination
workflows. See `notes/architecture-ports-and-adapters.md` (Adapter Categories,
Driving Adapters) for the architecture context.

## Verification

### AR-01-001, AR-01-002, AR-01-003 Verification

- Integration test: `GET /openapi.json` returns valid OpenAPI JSON schema
- Integration test: `GET /docs` and `GET /redoc` return HTML UI
- Code review: Every FastAPI route has a unique `operation_id`

### AR-02-001, AR-02-002 Verification

- Unit test: Resources with `status` field include `next_allowed_actions`
- Documentation review: State transitions documented per resource type

### AR-03-001 Verification

- Unit test: Structured error responses include stable `error` field
- Code review: `error` values are documented and stable across releases

### AR-04-001 Verification

- Integration test: Long-running operation returns job ID and status
  immediately

### AR-05-001 Verification

- Integration test: Collection endpoint supports `limit` and `offset`
  parameters
- Code review: Default and maximum page sizes documented in OpenAPI schema

### AR-08-001, AR-08-002, AR-08-003 Verification

- `PROD_ONLY` Integration test: CLI entry point installed and executable via
  `pyproject.toml`
- `PROD_ONLY` Integration test: `--output json` produces valid JSON on stdout
- `PROD_ONLY` Integration test: CLI exit codes match specification

### AR-07-001, AR-07-002 Verification

- Integration test:
  `GET /actors/{actor_id}/cases/{case_id}/action-rules`
  returns JSON with `role`, state fields, and `actions` list
- Unit test: Action list changes when RM/EM state transitions occur

### AR-10-001, AR-10-002, AR-10-003 Verification

- Unit test: `GET /actors/{actor_id}/profile` returns 200 with `id`, `type`,
  `inbox`, and `outbox` fields, where `inbox` and `outbox` are string URLs
  (`test_get_actor_profile_returns_discovery_fields`)
- Unit test: `GET /actors/{nonexistent}/profile` returns 404
  (`test_get_actor_profile_not_found_returns_404`)
- Unit test: Short actor ID resolves to full profile via `find_actor_by_short_id`

## Related

- **Error Handling**: `specs/error-handling.md` (EH-05-001)
- **HTTP Protocol**: `specs/http-protocol.md` (HTTP-03-001, HTTP-05-001,
  HTTP-07-004) — includes request correlation ID requirements
- **Structured Logging**: `specs/structured-logging.md` (SL-02-001)
- **Observability**: `specs/observability.md` (health check endpoints)
- **Prototype Shortcuts**: `specs/prototype-shortcuts.md` (PROD_ONLY deferral)
- **Case Management**: `specs/case-management.md` (CM-07-001 through CM-07-003)
- **Priorities**: `plan/PRIORITIES.md` (Priority 1000)
- **Implementation**: `pyproject.toml` (CLI entry points)
