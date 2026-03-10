# Codebase Structure Notes

## Top-Level Module Reorganization Status

Several top-level modules in `vultron/` were created at the top level for
development convenience but have since been reorganized as part of the
hexagonal architecture refactoring.

**Completed reorganizations (ARCH-CLEANUP-1 through P60-2):**

- `vultron/activity_patterns.py` — merged into `vultron/wire/as2/extractor.py`
- `vultron/semantic_map.py` — merged into `vultron/wire/as2/extractor.py`
- `vultron/semantic_handler_map.py` — moved to
  `vultron/api/v2/backend/handler_map.py`
- `vultron/as_vocab/` — moved to `vultron/wire/as2/vocab/` (P60-1)
- `vultron/behaviors/` — moved to `vultron/core/behaviors/` (P60-2)
- AS2 structural enums — moved from `vultron/enums.py` to
  `vultron/wire/as2/enums.py` (ARCH-CLEANUP-2)
- `MessageSemantics` — moved to `vultron/core/models/events.py` (ARCH-1.1)

**Still at top level (intentionally):**

- `vultron/behavior_dispatcher.py` — core dispatch logic; no wire imports
- `vultron/dispatcher_errors.py` — kept at top level to avoid circular imports;
  see `specs/code-style.md` CS-05-001
- `vultron/enums.py` — now only re-exports `MessageSemantics`,
  `OfferStatusEnum`, and `VultronObjectType` for backward compatibility
- `vultron/errors.py` — top-level error base; submodule errors exist at
  `vultron/api/v2/errors.py`
- `vultron/types.py` — shared type aliases; neutral module used to break
  circular import chains

**Constraint**: `dispatcher_errors.py` and `types.py` MUST remain accessible
to both core dispatch modules and `api/v2/` without creating circular imports.
Any reorganization MUST preserve this constraint. See `AGENTS.md` "Circular
Imports" section for the import chain rules.

---

## Enum Refactoring

Enums are currently organized across multiple locations in the codebase:

- `vultron/core/models/events.py` — `MessageSemantics` (domain enum)
- `vultron/wire/as2/enums.py` — AS2 structural enums (`as_ObjectType`,
  `as_TransitiveActivityType`, etc.)
- `vultron/enums.py` — backward-compat re-exports only
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

**Proposed future reorganization**: Consider a `vultron/enums/` package with
submodules grouped by domain:

- `vultron/enums/message_semantics.py`
- `vultron/enums/case_states.py`
- `vultron/enums/vocabulary.py`
- etc.

This would improve discoverability and allow a unified review of redundant or
unused enums. Not a high priority for the prototype.

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

## API Layer Architecture (Future Refactoring)

The current codebase treats `vultron/api/v1/` and `vultron/api/v2/` as version
numbers, but they are actually more like **distinct layers**:

| Layer | Current location | Purpose |
|---|---|---|
| ActivityPub layer | `vultron/api/v2/routers/actors.py` | Inbox/outbox endpoints; ActivityStreams semantics |
| Backend services layer | `vultron/api/v2/backend/` | Business logic, handlers, triggerable behaviors, DataLayer |
| Examples layer | `vultron/api/v1/` | Canned example responses; not an active coordination layer |

**Proposed future reorganization**: Rename to reflect layer semantics rather
than version numbers, e.g.:

- `vultron.api.activitypub` — ActivityPub inbox/outbox endpoints
- `vultron.api.backend` — backend services (handlers, triggers, DataLayer queries)
- `vultron.api.examples` — vocabulary and example generators

This reorganization would not require preserving old routes as long as tests
are updated accordingly. It is not high priority for the prototype but would
improve discoverability and make the intent of each layer clear.

**Constraint**: Do not start this refactor without updating all tests and
ensuring no existing functionality is broken. An ADR is not strictly required
for a rename, but the decision should be recorded in `AGENTS.md` or here.

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

## Handlers Module Structure (Completed)

The `vultron/api/v2/backend/handlers/` package contains handler submodules
organized by topic: `report.py`, `case.py`, `embargo.py`, `actor.py`,
`note.py`, `participant.py`, `status.py`, `unknown.py`.

`handlers/__init__.py` re-exports all handler functions so external imports
from `vultron.api.v2.backend.handlers` remain stable.

**See**: `plan/IMPLEMENTATION_PLAN.md` Phase TECHDEBT-1 (completed).

---

## Vocabulary Examples Module Structure (Completed)

`vultron/wire/as2/vocab/examples/` contains vocabulary example submodules
organized by topic: `_base.py`, `actor.py`, `case.py`, `embargo.py`, `note.py`,
`participant.py`, `report.py`, `status.py`. The top-level `vocab_examples.py`
in that package re-exports all public names.

The old `vultron/as_vocab/` package was relocated to `vultron/wire/as2/vocab/`
as part of P60-1. Import directly from `vultron.wire.as2.vocab.examples`.

**See**: `plan/IMPLEMENTATION_PLAN.md` Phase TECHDEBT-5, TECHDEBT-6, and P60-1
(all completed).

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

The `datalayer.read(key)` method and the `/datalayer/{key}` route use
`as_id` as the lookup key. Currently `generate_new_id()` returns a bare
UUID-4 string (e.g., `2196cbb2-fb6f-407c-b473-1ed8ae806578`) rather than a
full URL (e.g., `https://vultron.example/participants/2196cbb2-...`).

**Why bare UUIDs were used**: Avoids URL-encoding/escaping issues when
using object IDs as path segments in API routes (a full URL contains `/`
characters that require percent-encoding as `%2F`).

**What should be done**: Object IDs should be proper URL-like identifiers
per the ActivityStreams spec. API routes should accept URL-encoded IDs or
use a different lookup mechanism (e.g., query parameter `?id=<url>`, or
base64url encoding).

**Affected areas**:

- `generate_new_id()` in `vultron/as_vocab/base/utils.py` — add a default
  `prefix` based on object type
- Demo scripts and tests that assert on `as_id` format
- `/datalayer/{key}` route in `vultron/api/v2/routers/datalayer.py`
- Any handler that constructs participant or case IDs inline

---

## Known Gap: Outbox Delivery Not Implemented

`vultron/api/v2/data/actor_io.py` has a placeholder that appends strings to
an outbox list but does not write to any recipient actor's inbox. No delivery
mechanism exists. This means outbox-based activities (e.g., `CreateCase`
activity generated by the `create_case` handler) are never actually received
by other actors.

This is acceptable for the prototype demos (which sequence activities
manually) but must be resolved before the `CaseActor` broadcast model
(Priority 200 in `plan/PRIORITIES.md`) can work correctly.

**Reference**: `specs/outbox.md` OX-03-001, OX-04-001, OX-04-002;
`plan/IMPLEMENTATION_PLAN.md` Phase OUTBOX-1.

---

## Resolved: `app.py` Root Logger Side Effect

`vultron/api/v2/app.py` previously called `logging.getLogger().setLevel(logging.DEBUG)`
at module import time, causing test isolation problems.

**Status**: Fixed in BUGFIX-1.1. Root logger configuration is now inside the
`lifespan` context manager so importing the module in tests does not mutate
the root logger.

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
`LOG_LEVEL=DEBUG uvicorn vultron.api.main:app --port 7999`
"""
```

### Documentation Links

When referencing other documentation in docstrings, use proper markdown links
relative to `docs/` as the site root, with the target page title as link text:

```python
"""
See [Reporting a Vulnerability](/howto/activitypub/activities/report_vulnerability.md).
"""
```
