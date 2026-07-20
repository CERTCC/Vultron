---
title: Codebase Structure Notes
status: active
tags: [architecture, codebase, circular-imports, fastapi, docker, health-check, actor-ids]
description: >
  Overview of the Vultron codebase structure, module organization, and
  hexagonal architecture layout.
related_specs:
  - specs/prototype-shortcuts.yaml
related_notes:
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

# Codebase Structure Notes

## Top-Level Modules

A few modules remain at the top level of `vultron/` by necessity:

- `vultron/errors.py` — top-level error base; adapter-layer errors live at
  `vultron/adapters/driving/fastapi/errors.py`
- `vultron/types.py` — shared type aliases (`BehaviorHandler` Protocol);
  neutral module used to break circular import chains. Contents should be
  migrated into `vultron/core/types.py` once circular imports are fully
  resolved.

**Constraint**: `types.py` MUST remain accessible to both core dispatch
modules and adapter layers without creating circular imports. See `AGENTS.md`
"Circular Imports" section for the import chain rules.

---

## Enum Refactoring

Enums are currently organized across multiple locations in the codebase:

- `vultron/core/models/events.py` — `MessageSemantics` (domain enum)
- `vultron/wire/as2/enums.py` — AS2 structural enums (`as_ObjectType`,
  `as_TransitiveActivityType`, etc.)
- `vultron/enums/` — bottom-of-stack neutral enumeration layer (`CVDRole`,
  `serialize_roles`, `validate_roles`; MUST NOT import from `vultron/core/`
  or `vultron/config/`); see `docs/adr/0031-vultron-enums-neutral-layer.md`
- `vultron/case_states/enums/` — case state enums, split into submodules:
  - `cvss_31.py`
  - `embargo.py`
  - `explanations.py`
  - `info.py`
  - `potential_actions.py`
  - `ssvc_2.py`
  - `utils.py`
  - `vep.py`
  - `zerodays.py`
- `vultron/wire/as2/vocab/` — vocabulary-level type enums (moved from
  `vultron/as_vocab/`)

**Target organization**: Each level of the package hierarchy SHOULD have a
dedicated `enums.py` module (or `enums/` subpackage if there are many enums)
so that enums are easy to find and manage. For example:

- `vultron/core/models/events/enums.py` — `MessageSemantics` (moving from
  `events.py` base)
- `vultron/core/models/enums/` — enums shared across core models (e.g.,
  `CVDRole`, state machine enums migrated from `vultron/bt` and
  `vultron/case_states`)
- `vultron/wire/as2/enums.py` — AS2 structural enums (already in place)

Enums imported from outside `core` that are used in `core` are candidates
for relocation into `core` (refactoring from their original location as
needed). In particular:

- Enums in `vultron/bt/` and `vultron/case_states/` that represent domain
  concepts (not BT-engine internals) SHOULD migrate to `core/models/enums/`.
- If a given area has many enums, split them into an `enums/` subpackage
  with multiple files rather than one large `enums.py`.

**Not a high priority for the prototype**, but each new enum SHOULD be
placed at the correct layer from the start to avoid accumulating more
technical debt.

---

## Core Object Modules: Split `vultron_types.py` (TECHDEBT-14)

`vultron/core/models/vultron_types.py` currently bundles multiple core object
types into a single file. These SHOULD be split into individual modules for
better organization, following the same pattern used in `vultron/wire/as2/vocab/objects/`:

- Each core domain object class gets its own module
  (e.g., `vultron/core/models/report.py`, `vultron/core/models/case.py`)
- `vultron/core/models/__init__.py` or a thin re-export module can re-export
  all types for callers that import from `vultron.core.models`

This makes individual classes easier to find, reduces merge conflicts, and
matches the source layout pattern already established in the wire layer.

**Priority**: Low. No blocking impact; purely organizational.
**Related**: `notes/domain-model-separation.md` "DRY Core Domain Models"
proposes consolidating `vultron_types.py` and `events.py` under a shared
`VultronObject` base class as part of this cleanup.

---

## `CVDRoles` Design Decision: StrEnum List, Not Flag

The `CVDRoles` enum in `vultron/bt/roles/states.py` uses bitwise `Flag`
semantics. This design is acceptable within `vultron/bt/` (the legacy BT
simulator) but MUST NOT be used elsewhere.

**For all new code in `core` and `wire`**, represent CVD roles as a
`list[CVDRole]` where `CVDRole` is a `StrEnum`:

```python
# vultron/core/models/enums/cvd_role.py  (proposed location)
from enum import StrEnum

class CVDRole(StrEnum):
    FINDER = "finder"
    REPORTER = "reporter"
    VENDOR = "vendor"
    COORDINATOR = "coordinator"
    OTHER = "other"
```

When roles appear on case objects or participant objects, the field type
SHOULD be `list[CVDRole]`. This is easier to work with than bitwise flags:
membership checks use `if CVDRole.VENDOR in participant.roles` instead of
bitwise tests.

The old `CVDRoles` `Flag` class can be renamed `CVDRoleFlags` and left in
`vultron/bt/roles/states.py` as long as the legacy BT simulator still uses it.
When the BT simulator is eventually retired or migrated, `CVDRoleFlags` can be
removed.

---

## State Machine Library Consideration

The RM, EM, and CS state machines are currently implemented as manually-defined
enums with no formal state machine enforcement. The
[`transitions`](https://github.com/pytransitions/transitions) Python library
provides a clean, declarative way to define state machines with guards,
callbacks, and transition tables.

**Long-term consideration**: Integrating `transitions` would make it easier to
define and maintain the RM/EM/CS state machines, enforce valid state transitions
at runtime, and generate transition diagrams for documentation. This is not a
high priority for the prototype, but may become valuable as the state machines
grow more complex or when implementing actor independence (PRIORITY 100).

**Open Question**: Should `transitions` (or an equivalent) be adopted before or
after the domain model separation (see `notes/domain-model-separation.md`)? The
state machines are a core domain concept; their implementation should live in
`vultron/core/` regardless of which library is used.

---

## Code Documentation (Static and Dynamic)

### Static Code Documentation

Auto-generated code documentation lives in `docs/reference/code/**/*.md`,
generated from docstrings in the codebase. The organization is currently
ad-hoc and not comprehensive. It is intended for inclusion in the MkDocs
static site. Reorganizing this section is low priority for the prototype.

**Guidelines for maintaining quality:**

- Keep docstrings accurate and up to date with implementation changes.
- MkDocs material + mkdocstrings generates from docstrings automatically.
- The static docs reflect the codebase at build time — they go stale quickly
  if not regenerated.

### Dynamic API Documentation

FastAPI's built-in OpenAPI support generates interactive API documentation
automatically. This is available at `/docs` (Swagger UI) and `/redoc` when
the server is running.

**Priority note**: The FastAPI OpenAPI docs are higher priority to maintain
than the static code docs. Developers and agents interacting with the running
API are more likely to use the OpenAPI docs. Ensure:

- Route docstrings describe the endpoint clearly.
- Request/response models have clear field descriptions in Pydantic models.
- New endpoints are added to the correct router so they appear in the docs.

---

## Module Boundary: `vultron/bt/` vs `vultron/core/behaviors/`

These two trees coexist and MUST NOT be merged or confused:

| Module | Purpose | BT Engine | Status |
|--------|---------|-----------|--------|
| `vultron/bt/` | Original simulation (custom engine) | Custom (`vultron.bt.base`) | Legacy; do not modify for prototype handlers |
| `vultron/core/behaviors/` | Prototype handler BTs | `py_trees` (v2.2.0+) | Active development |

The `vultron/sim/` module also exists as another simulation-related module and
MUST NOT be confused with `vultron/bt/` or `vultron/core/behaviors/`.

See `notes/bt-integration.md` for architectural decisions about the BT
layer.

---

## Demo Script Lifecycle Logging: `demo_step` / `demo_check`

All demo scripts use two context managers defined in `vultron/demo/utils.py`
for structured lifecycle logging:

- **`demo_step(description)`**: Wraps a workflow step. Logs `🚥 description`
  at INFO on entry, `🟢 description` on clean exit, `🔴 description` at ERROR
  on exception (and re-raises).
- **`demo_check(description)`**: Wraps a side-effect verification block. Logs
  `📋 description` at INFO on entry, `✅ description` on success,
  `❌ description` at ERROR on exception (and re-raises).

Import these from `vultron.demo.utils` in every demo script. Use them
consistently to wrap numbered workflow steps and verification blocks so that
log output clearly shows progress and failure location during test runs and
live demos.

**Pattern**:

```python
with demo_step("1. Create vulnerability report"):
    report = create_report(...)

with demo_check("1a. Verify report persisted"):
    assert dl.get(report.as_id) is not None
```

**Cross-reference**: `test/demo/test_demo_context_managers.py` (18 tests).

---

## Demo Scripts Live in `vultron/demo/`

All demo scripts are located in `vultron/demo/` (migration from
`vultron/scripts/` completed in Phase DEMO-4.3):

- **`vultron/scripts/`** — standalone utilities run directly (data migration,
  maintenance, one-off tooling), including `vocab_examples.py`
- **`vultron/demo/`** — end-to-end workflow demonstrations, CLI entry point,
  shared utilities, and all 12 `*_demo.py` scripts
- **`vultron/demo/utils.py`** — shared demo utilities (`demo_step`,
  `demo_check`, `DataLayerClient`, HTTP helpers, `demo_environment` context
  manager)
- **`vultron/demo/cli.py`** — unified `vultron-demo` Click CLI

Tests for demo scripts are in `test/demo/` (corresponding to the demo module
structure). Docker Compose services are in `docker/docker-compose.yml`.

---

## Technical Debt: Object IDs Should Be URL-Like, Not Bare UUIDs

The `datalayer.read(key)` method and the `/datalayer/{key:path}` route use
`as_id` as the lookup key. Currently `generate_new_id()` returns a bare
UUID-4 string (e.g., `2196cbb2-fb6f-407c-b473-1ed8ae806578`) rather than a
full URL (e.g., `https://vultron.example/participants/2196cbb2-...`).

**Why bare UUIDs were used**: Avoids URL-encoding/escaping issues when
using object IDs as path segments in API routes (a full URL contains `/`
characters that are treated as path-segment separators by Starlette, even
after percent-encoding as `%2F`).

**Current tactical fix**: The `/{key:path}` Starlette path converter is used
throughout the FastAPI routers (actors, datalayer) to accept URL-form keys
with embedded slashes. See
[Starlette Path-Type Parameters for URL-Keyed Endpoints](#starlette-path-type-parameters-for-url-keyed-endpoints)
below.

**Deeper architectural goal**: Object IDs should be proper URL-like identifiers
per the ActivityStreams spec. The long-term resolution is to separate routing
identity from object identity by assigning each actor and case a stable,
locally-unique, routing-safe surrogate key (e.g., a UUID or slug) used in all
URL path segments while keeping the full IRI as the canonical `id` field inside
the object graph. This mirrors ActivityPub practice of using
`preferredUsername` for routing while the full actor IRI lives in the payload.

**Affected areas**:

- `generate_new_id()` in `vultron/wire/as2/vocab/base/utils.py` — add a default
  `prefix` based on object type
- Demo scripts and tests that assert on `as_id` format
- Any handler that constructs participant or case IDs inline

---

## Starlette Path-Type Parameters for URL-Keyed Endpoints

(DR-10, 2026-05-21 — fixed in #617, which resolves #610)

When a FastAPI/Starlette endpoint needs to accept keys that may contain
literal forward slashes (e.g., full HTTP URL IDs such as
`http://vendor:7999/api/v2/actors/case-actor-{uuid}/participant`), use the
`{param:path}` path converter instead of the plain `{param}` converter.

```python
# ✅ Correct: accepts keys with embedded slashes
@router.get("/{key:path}")
def get_object_by_key(key: str, ...): ...

# ❌ Broken: Starlette decodes %2F → / before route matching,
#    so percent-encoding does not work as a workaround
@router.get("/{key}")
def get_object_by_key(key: str, ...): ...
```

**Rule**: Register catch-all `/{param:path}` routes **last** in the router so
that specific literal routes (e.g., `/Offers/`, `/Actors/`) are matched first.
Starlette matches routes in registration order; a catch-all at the top shadows
all subsequent routes.

**Why percent-encoding fails**: Starlette decodes `%2F` back to `/` before
route matching, so there is no client-side workaround. Only the server-side
`path` converter fixes the root cause.

**Implemented in**:

- `vultron/adapters/driving/fastapi/routers/datalayer.py` — `/{key:path}`
- `vultron/adapters/driving/fastapi/routers/actors.py` —
  `/{actor_id:path}/inbox`, `/{actor_id:path}/outbox/`, `/{actor_id:path}`

**See also**: GitHub concern #618 (Full-URI IDs in URL path segments —
deeper architectural issue of separating routing identity from object
identity remains open).

---

### Actor ID Normalization: Full URIs Everywhere

(DR-09, 2026-04-20)

Actor IDs MUST be full URIs everywhere in the system. They MUST be normalized
to a full URI at the point the actor ID is first established (actor creation,
seed load, session context). No function downstream of that point should ever
receive or handle a short UUID as an actor ID.

**Why this matters**: Short-UUID actor IDs break semantic routing, outbox
addressing, and trust boundary checks. They also cause non-deterministic
failures where the same actor appears under two different IDs in the DataLayer.

**Audit**: Search for short-UUID actor ID assignment in
`vultron/demo/`, `vultron/adapters/`, and `vultron/core/` seeding code.

### Actor ID Normalization in Trigger Paths

(BUG-26042202, 2026-04-22)

Trigger paths that accept short actor IDs from router path parameters MUST
overwrite `actor_id` with the resolved `actor.id_` before any outbox mutation.

**Why SQLite hides this bug**: For `urn:uuid:` actor IDs, the SQLite DataLayer
performs bare-UUID compatibility lookups in `dl.read()`, so a trigger that
passes a short UUID to the DataLayer may appear to work. The same trigger
**silently fails** if the actor record uses a URL-form ID (e.g.,
`https://example.org/actors/alice`).

**Testing guidance**: Regression tests for short-ID trigger normalization MUST
use URL-form actor records to exercise the missing canonicalization path.
Asserting both `outbox.items` mutation AND the absence of a warning log is a
better guard than checking the queued activity alone.

---

## Docstring and Markdown Compatibility

Vultron uses `mkdocstrings` to render docstrings in the MkDocs documentation
site. Docstrings MUST use markdown-compatible syntax.

### Lists

Use a blank line before every list, with consistent indentation:

```python
"""
When run as a script, this module will:

1. Check if the API server is available
2. Post a VulnerabilityReport Offer
"""
```

### Inline Code

Use backticks for inline code references even if they are not Python
identifiers:

```python
"""
To see BT execution details, run with `DEBUG` logging enabled:
`LOG_LEVEL=DEBUG uvicorn vultron.adapters.driving.fastapi.main:app --port 7999`
"""
```

The canonical deployment entrypoint is
`vultron.adapters.driving.fastapi.main:app`. Treat legacy
`vultron.api.main:app` references in demo-facing text as stale and do not copy
them into new docs.

### Documentation Links

When referencing other documentation in docstrings, use proper markdown links
relative to `docs/` as the site root, with the target page title as link text:

```python
"""
See [Reporting a Vulnerability](/howto/activitypub/activities/report_vulnerability.md).
"""
```

---

## Known Gap: `docker/README.md` Out of Date

`docker/README.md` does not reflect the current services available in
`docker/docker-compose.yml`. It was written before the unified `demo`
service, health checks, and `api-dev` service were added. Update it to
describe how to start the API server, run the demo, and any relevant
`docker-compose` commands.

---

## Known Gap: Inline Code Blocks in `docs/` Reference Old Module Paths

Several Python inline code examples in `docs/` reference old module paths
(e.g., `vultron.as_vocab.*`) that were moved to `vultron.wire.as2.vocab.*`
during the P60-1 package relocation. Run `mkdocs build` to surface errors,
then update the affected code blocks.

---

## Bulk Module-Rename Lessons Learned (VCR-019a)

When doing large-scale module renames (moving packages from one location to
another with import path changes), the following approach works reliably:

- **`sed`-based bulk replacement** is faster and less error-prone than editing
  files individually:
  `sed -i '' 's/old\.module\.path/new\.module\.path/g' <file>` applied to
  each affected file.
- **Test directory must mirror source directory.** Move `test/old_package/`
  to `test/new_package/` with a `__init__.py` to ensure pytest discovers
  tests under the new paths.
- **No shims = immediate confidence.** Without compatibility re-exports, a
  clean test run proves all callers were updated. Any missed import site
  causes an `ImportError` immediately rather than silently passing through a
  shim. See `specs/prototype-shortcuts.yaml` PROTO-08-001, PROTO-08-002.
- **Find all callers first.** Use `grep -r "from old.path\|import old.path"`
  across `vultron/` and `test/` to get the complete call-site list before
  starting.

---

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
