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

## API Discoverability (MUST)

- `AR-01-001` The API MUST expose a machine-readable OpenAPI JSON schema at
  `/openapi.json`
- `AR-01-002` The API MUST expose rendered documentation UI at `/docs` and
  `/redoc` in development environments
- `AR-01-003` Every endpoint MUST have a unique, stable `operationId`
  following the `{resource}_{action}` naming convention
- `AR-01-004` `PROD_ONLY` All possible HTTP response codes for each endpoint
  MUST be declared in the OpenAPI spec with typed response models

## State and Workflow Transitions (SHOULD)

- `AR-02-001` `PROD_ONLY` Resources with a `status` field SHOULD include a
  `next_allowed_actions` list identifying valid state transitions from the
  current state
- `AR-02-002` All valid states and state transitions for state machine
  resources MUST be documented
- `AR-02-003` `PROD_ONLY` Endpoints with prerequisites MUST return a structured
  error using the `error` field value `"PreconditionFailedError"` when invoked
  out of sequence
  - **Cross-reference**: `error-handling.md` EH-05-001 for error response
    format

## Stable Error Types (MUST)

- `AR-03-001` The API MUST use the `error` field (per `error-handling.md`
  EH-05-001) as a stable, machine-parseable error type identifier
  - Agents MUST be able to branch on `error` without parsing the
    human-readable `message` field
  - **Cross-reference**: `error-handling.md` EH-05-001 for error response
    format

## Long-Running Operations (SHOULD)

- `AR-04-001` `PROD_ONLY` Long-running operations SHOULD return a job or task
  object immediately with a stable `id` and `status` field
- `AR-04-002` `PROD_ONLY` A separate polling endpoint or webhook mechanism
  SHOULD be available to report operation completion

## Pagination (SHOULD)

- `AR-05-001` Collection endpoints SHOULD expose `limit` and `offset` (or
  `cursor`) query parameters with documented defaults and maximums

## Bulk Operations (MAY)

- `AR-06-001` `PROD_ONLY` Resources that agents may need to create, update, or
  delete in quantity MAY expose batch endpoints (e.g., `POST /v1/items/batch`)

## Request Correlation (SHOULD)

- See `http-protocol.md` HTTP-05-001 for request correlation ID requirements.

## CLI Interface (MUST)

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

## Related

- **Error Handling**: `specs/error-handling.md` (EH-05-001)
- **HTTP Protocol**: `specs/http-protocol.md` (HTTP-03-001, HTTP-05-001,
  HTTP-07-004)
- **Structured Logging**: `specs/structured-logging.md` (SL-02-001)
- **Observability**: `specs/observability.md` (health check endpoints)
- **Prototype Shortcuts**: `specs/prototype-shortcuts.md` (PROD_ONLY deferral)
- **Priorities**: `plan/PRIORITIES.md` (Priority 1000)
- **Implementation**: `pyproject.toml` (CLI entry points)
