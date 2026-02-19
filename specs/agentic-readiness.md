# Agentic Readiness

TODOs: 
- [ ] Revise this list to match the style of `./meta-specifications.md`
- [ ] Identify which items are `PROD_ONLY` according to guidance in `./README.md`
- [ ] Reconcile duplicative items in this list with other specification 
  already present in `./*.md`
- [ ] Remove this TODO list from the final committed version of this file; all items should be reflected in the prose below.

## Overview

This file defines specification for API and CLI design, data contracts, error
handling, and other aspects of the system that are critical for agentic readiness. 
The requirements outlined here ensure that the system is designed with clear, 
consistent interfaces and behaviors that enable agents to interact with it 
effectively and reliably.

## Requirements

### API Design & Endpoint Conventions

- Every endpoint accepts and returns JSON exclusively; no HTML, form-encoded, or multipart responses on data routes.
- Every request and response body is typed to a Pydantic `BaseModel` subclass; no use of raw `dict` or `Any` as a top-level body type.
- All endpoints use explicit, versioned URL prefixes (e.g., `/v1/...`); version is never inferred from headers alone.
- Every endpoint that mutates state uses `POST`, `PUT`, `PATCH`, or `DELETE` consistently and correctly; `GET` endpoints are free of side effects.
- Paginated list endpoints expose `limit`, `offset` (or `cursor`) as query parameters with documented defaults and maximums.
- Bulk operation endpoints exist for any resource that an agent may need to create, update, or delete in quantity (e.g., `POST /v1/items/batch`).
- Every endpoint returns a consistent top-level response envelope (e.g., `{"data": ..., "meta": ..., "errors": [...]}`) so agents can parse responses without per-route logic.
- Long-running operations return a job/task object immediately with a stable `id` and a `status` field; a separate polling or webhook endpoint reports completion.
- Filtering, sorting, and field selection are available on all collection endpoints via documented query parameters.

### Data Contracts & Pydantic Schema

- Every Pydantic model used in a request or response is exported in the OpenAPI schema with a `$ref` name matching the Python class name exactly.
- All fields include a `description=` string in the `Field(...)` declaration; no undocumented fields exist in any model.
- All fields with constrained values use Pydantic validators or `Literal` / `Enum` types; constraints are reflected in the JSON Schema (e.g., `minLength`, `pattern`, `minimum`).
- Optional fields are explicitly typed as `Optional[T]` with a documented default; no field is implicitly optional via `= None` without the `Optional` annotation.
- Every `Enum` used in a model is a `str` enum (inherits from `str, Enum`) so serialized values are human-readable strings, not integers.
- Date and time fields use `datetime` with explicit timezone (`datetime` with `tzinfo`) and serialize to ISO 8601 strings.
- Monetary or precision-sensitive numeric fields use `Decimal`, not `float`; the JSON schema documents precision and scale.
- Pydantic models expose `.model_json_schema()` programmatically; a `/v1/schema` or equivalent endpoint returns the full OpenAPI JSON schema document.
- Breaking changes to any model field (rename, type change, removal) require a version increment; additive changes (new optional fields) do not.

### OpenAPI / Documentation

- The FastAPI app exposes `/openapi.json` and a rendered UI (`/docs` and `/redoc`) without authentication in development; these are lockable behind auth in production but must remain machine-fetchable.
- Every path, query parameter, and body field has a non-empty `description` in the OpenAPI output.
- Every endpoint has a unique, stable `operationId` that follows a consistent naming convention (e.g., `{resource}_{action}`).
- All possible HTTP response codes for an endpoint are declared in the OpenAPI spec with a typed response model for each.
- The OpenAPI document includes a top-level `info.description` that states the system's purpose, base URL, and auth mechanism.
- A machine-readable changelog (e.g., `CHANGELOG.md` or `/v1/meta/changelog`) documents every breaking and non-breaking API change by version.

### Error Handling & Structured Errors

- All error responses use a single Pydantic model (e.g., `ErrorResponse`) with at minimum: `error_code` (stable string identifier), `message` (human-readable), `details` (optional list of field-level errors), and `request_id`.
- HTTP 422 Unprocessable Entity responses include per-field validation errors in the `details` array with `field`, `issue`, and `input` sub-fields, using FastAPI's default validation error format extended to match the `ErrorResponse` model.
- HTTP 4xx errors never return an empty body; every client error is actionable (the agent can determine whether to retry, fix the request, or escalate).
- HTTP 500 errors include a `request_id` traceable in server logs; stack traces are never exposed in production responses.
- A documented, stable set of `error_code` string values is maintained (e.g., `RESOURCE_NOT_FOUND`, `VALIDATION_FAILED`, `RATE_LIMIT_EXCEEDED`); agents can branch on these without parsing `message` strings.
- Transient errors (rate limiting, temporary unavailability) return HTTP 429 or 503 with a `Retry-After` header.

### Idempotency & Safe Retry

- All `POST` endpoints that create or trigger resources accept an optional `Idempotency-Key` header; repeat requests with the same key within a defined window return the original response without re-executing the operation.
- The idempotency window duration and behavior are documented per endpoint.
- `PUT` endpoints are fully idempotent by design; calling with the same payload twice produces the same server state and response.
- Every destructive operation (`DELETE`, irreversible state transitions) is documented with its idempotency behavior explicitly (e.g., "deleting an already-deleted resource returns 404, not 500").
- Job/task submission endpoints are idempotent when an `Idempotency-Key` is provided; the returned job `id` is stable for the same key.

### Observability & Introspection

- A `GET /health` endpoint returns HTTP 200 with a structured JSON body (`{"status": "ok", "version": "...", "timestamp": "..."}`) when the service is operational; returns non-200 when degraded.
- A `GET /health/ready` endpoint separately reports dependency readiness (database, external services) with per-dependency status.
- A `GET /v1/meta/capabilities` or equivalent endpoint returns a machine-readable list of available resources, actions, and any feature flags relevant to agents.
- Every request receives a unique `X-Request-ID` response header; the service accepts and propagates a caller-supplied `X-Request-ID` header if present.
- Structured logs are emitted as JSON with at minimum: `timestamp`, `level`, `request_id`, `method`, `path`, `status_code`, `duration_ms`.
- Metrics expose request counts, error rates, and latency percentiles in a machine-scrapable format (e.g., Prometheus `/metrics` endpoint).

### Authentication (API Key)

- API keys are passed via the `Authorization: Bearer <token>` header; no API keys accepted as query parameters.
- Missing or malformed credentials return HTTP 401 with a structured `ErrorResponse`; insufficient permissions return HTTP 403.
- The API key format is documented (length, alphabet, prefix) so agents can validate keys client-side before sending requests.
- Key expiry or revocation returns HTTP 401 with `error_code: "TOKEN_EXPIRED"` or `"TOKEN_REVOKED"` so agents can distinguish and respond appropriately.

### CLI Interface

- The CLI is installable as a Python package entry point (defined in `pyproject.toml`); no need to invoke via `python -m`.
- Every CLI command accepts `--output json` (or equivalent flag) to emit structured JSON to stdout suitable for programmatic consumption.
- Every CLI command exits with code `0` on success, `1` on handled error, and `2` on usage/argument error; no command exits non-zero silently.
- CLI commands that wrap API calls surface the same `error_code` and `request_id` fields from the API response in their JSON error output.
- Long-running CLI commands support a `--wait` / `--no-wait` flag; `--no-wait` returns the job object immediately.
- All CLI arguments and options are documented via `--help`; help text is parseable (no ANSI color codes) when stdout is not a TTY.

### Workflow & Sequencing Support

- Endpoints expose sufficient state information in responses (e.g., `status`, `next_allowed_actions`) for an agent to determine valid next steps without out-of-band documentation.
- State machine transitions are documented: for every resource with a `status` field, all valid states and valid transitions between them are listed.
- Any operation with a prerequisite (e.g., "must call `/v1/session/start` before `/v1/items`") is documented and enforced; violation returns a structured error with `error_code: "PRECONDITION_FAILED"`.
- Endpoints that return related resource references include the full resource URL or `id` needed to fetch them (HATEOAS-lite: no dangling foreign keys without a resolution path).
- Rate limits are documented per endpoint or resource type; limit, window, and current consumption are available via response headers (`X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`).
