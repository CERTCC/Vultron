---
title: "Codebase Structure: FastAPI and Test Patterns"
status: active
description: >
  Router test override pattern, circular import fixes, FastAPI response_model
  patterns, health check, Docker health check, Black/pyright config, Python 3.14
  compatibility notes, surrogate-key routing, and logger name conventions.
related_specs:
  - specs/prototype-shortcuts.yaml
related_notes:
  - notes/codebase-structure.md
  - notes/bt-integration.md
  - notes/domain-model-separation.md
relevant_packages:
  - fastapi
  - py_trees
  - vultron/core
  - vultron/bt
  - vultron/adapters
  - vultron/wire/as2
  - vultron/demo
---

# Codebase Structure: FastAPI and Test Patterns

> See also: [codebase-structure.md](codebase-structure.md) for the first half of these design notes.

## Router Test Override Pattern: `_shared_dl` and `dependency_overrides`

When writing FastAPI router tests that cover endpoints in
`vultron/adapters/driving/fastapi/routers/actors.py`, the module-level
`_shared_dl` variable is populated by calling `get_datalayer()` directly at
import time (not via `Depends`). This means:

- `app.dependency_overrides[get_datalayer] = lambda: mock_dl` alone is
  **insufficient** — the `_shared_dl` closure was already bound to the real
  DataLayer at import time.
- You **must** also patch `actors_router._shared_dl = mock_dl` (or the
  equivalent `monkeypatch.setattr`) so that the already-bound module variable
  points to the test DataLayer.

This is a deliberate design (ADR-0012): cross-actor lookups and the shared
admin DataLayer use a module-level binding for performance, not `Depends`.

---

## Circular Import Fix Pattern: Shared Helpers in `_helpers.py`

When a module in `vultron/core/behaviors/` needs a helper that is also
imported by `vultron/core/use_cases/triggers/`, importing it via
`triggers/_helpers.py` will trigger `triggers/__init__.py`, which eagerly
loads all trigger use-case sub-modules. If any trigger sub-module imports
back into the behaviors layer, a circular import results.

**Fix pattern**: Move shared helpers to
`vultron/core/use_cases/_helpers.py` (the neutral package-top-level module).
This module is importable from both the `behaviors/` layer and the
`triggers/` sub-package without loading the `triggers` package at all.

**Migration complete** (PR #1361): `_log_label`, `outbox_ids`, and
`add_activity_to_outbox` have been moved from `triggers/_helpers.py` to
`use_cases/_helpers.py`. All callers import from `use_cases._helpers` directly.
The `triggers/_helpers.py` re-export bridge is no longer needed or present.

**Corollary**: The duck-typing Protocol guards (`is_case_model()` etc.) were
removed in PR #1529 (ADR-0034 / DL-05-003). Core code now uses concrete
`isinstance(obj, VulnerabilityCase)` checks directly. The old corollary about
keeping domain model classes structurally compatible with wire types no longer
applies — the DataLayer read path (ADR-0034) ensures `dl.read()` returns core
objects, so `isinstance` always holds.

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

**Solution**:

- *For AS2 endpoints*: Return `AS2JSONResponse(obj)` instead of a plain model
  instance. `AS2JSONResponse` calls `model_dump(mode="json", by_alias=True,
  exclude_none=True)` and sets `Content-Type: application/activity+json`,
  bypassing FastAPI's `response_model` filtering entirely. This is the canonical
  fix for AS2-typed routes (see `specs/http-protocol.yaml` HTTP-09-002,
  HTTP-09-003).
- *For non-AS2 endpoints*: Remove return type annotations from endpoints that
  return multiple types, or use explicit `Union[Type1, Type2, ...]` if types are
  known. Do **not** apply `AS2JSONResponse` to generic/non-AS2 routes.

**Verification**: Test API serialization completeness, not just database
storage. Check that all expected fields appear in JSON responses.

See `specs/http-protocol.yaml` HTTP-08-001 (root cause) and HTTP-09-002,
HTTP-09-003 (AS2 endpoint fix).

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
   import httpx
   import time

   def check_server_availability(url, max_retries=30, retry_delay=1.0):
       for attempt in range(max_retries):
           try:
               response = httpx.get(url, timeout=2)
               if response.is_success:
                   return True
           except httpx.RequestError:
               if attempt < max_retries - 1:
                   time.sleep(retry_delay)
       return False
   ```

   Note: use `httpx` (the declared runtime dependency), not `requests`.

The pitfall above is self-contained. The three-layer solution (Docker health
check, `condition: service_healthy`, and client retry) is the recommended
pattern for any demo or integration test setup.

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

## Python 3.14 Compatibility Deferred

(TOOLS-1, 2026-04-23)

Python 3.14.0rc2 is available but the test suite fails with:

```text
TypeError: _eval_type() got an unexpected keyword argument 'prefer_fwd_module'
Unable to evaluate type annotation 'ClassVar[MetaData]'
```

**Root cause**: `pydantic==2.13.3` uses the old `typing._eval_type()` call
signature that Python 3.14 removed. There is no Pydantic update available
that resolves this at the time of writing.

**Current constraint**: `requires-python = ">=3.12"` and docker base image
`python:3.13-slim-bookworm` are unchanged.

**Action when unblocked**: Revisit when Pydantic releases a Python
3.14-compatible build. Update `requires-python` ceiling and docker base image
at that point. Check `uv.lock` for any other packages using `typing._eval_type`
directly.

---

## Surrogate-Key Routing Collision Handling

(ISSUE-654, 2026-06-08)

The DataLayer uses surrogate keys (short ID segments) for routing alongside
canonical full-URI IDs. Two invariants MUST be enforced:

### Ambiguous matches are errors, not first-match wins

When `dl.resolve_surrogate_key(key)` finds more than one canonical ID
matching a short-key tail segment, it MUST raise an error (e.g.,
`VultronAmbiguousKeyError`), not silently return the first result. Returning
the first match makes actor/case lookups non-deterministic when multiple
canonical IDs share the same tail segment — a bug that is extremely hard to
reproduce in tests.

### Case-key resolution continues to short-key fallback after non-case hits

When `dl.read(key)` returns a non-case object (e.g., an actor record),
case-key resolution MUST NOT treat that as a definitive miss and return a
404. It must continue the lookup chain to the short-key fallback. Otherwise
non-case IDs can shadow valid case keys and produce false 404 or validation
failures.

### Evidence

- `vultron/adapters/driven/datalayer_sqlite.py` — `resolve_surrogate_key()`
- `vultron/adapters/driven/datalayer.py` — `DataLayer` protocol

### AC-3a Asymmetric Test Pattern

The surrogate-key scope regression (BUG-2026040901) is documented by an
intentionally asymmetric test: the short-ID DataLayer sees an empty outbox
while the canonical-URI DataLayer sees the entry. This documents the failure
mode without requiring monkeypatching. Use `call_args.args` (not
`call_args[0]`) when asserting mock positional arguments — the named
attribute fails clearly if the call shifts to kwargs, while the index
subscript returns an empty tuple silently.

---

## Logger Names: Verify from Source, Not Assumption

(DEMO-CI-DIAGNOSTICS-951, 2026-06-15)

When writing diagnostic docs, log-filter commands, or structured-logging guidance,
always verify logger names directly from source — do not infer them from module
paths.

Two known non-obvious logger names in Vultron:

**Inbox receipt layer (Layer 2 of the 3-layer pipeline)**:

- Logger is `uvicorn.error`
- **Not** `vultron.adapters.driving.fastapi.routers.actors`
- The actors router explicitly overrides the module-default logger:
  `logging.getLogger("uvicorn.error")`

**`PersistLogEntryNode`**:

- Logger is `vultron.core.behaviors.sync.nodes.chain.PersistLogEntryNode`
  (class-qualified)
- **Not** the bare module path `vultron.core.behaviors.sync.nodes.chain`

When scoping `caplog` captures in tests (e.g.,
`caplog.at_level(logging.INFO, logger="...")`), use the class-qualified name
to avoid receiving unrelated records from other nodes in the same module.
