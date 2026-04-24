# Codebase Structure Notes

## Top-Level Module Reorganization Status

Several top-level modules in `vultron/` were created at the top level for
development convenience but have since been reorganized as part of the
hexagonal architecture refactoring.

**Completed reorganizations (ARCH-CLEANUP-1 through P60-2):**

- `vultron/activity_patterns.py` — merged into `vultron/wire/as2/extractor.py`
- `vultron/semantic_map.py` — merged into `vultron/wire/as2/extractor.py`
- `vultron/semantic_handler_map.py` — merged into
  `vultron/wire/as2/extractor.py`; handler routing table moved to
  `vultron/core/use_cases/use_case_map.py` (P75-2, REORG-1)
- `vultron/as_vocab/` — moved to `vultron/wire/as2/vocab/` (P60-1)
- `vultron/behaviors/` — moved to `vultron/core/behaviors/` (P60-2)
- AS2 structural enums — moved from `vultron/enums.py` to
  `vultron/wire/as2/enums.py` (ARCH-CLEANUP-2)
- `MessageSemantics` — moved to `vultron/core/models/events.py` (ARCH-1.1)
- `vultron/behavior_dispatcher.py` — moved to `vultron/core/dispatcher.py`
  (P65-*)
- `vultron/dispatcher_errors.py` — merged into `vultron/errors.py` and
  `vultron/core/dispatcher.py` (P65-*)
- `vultron/enums.py` — deleted; `MessageSemantics` is in
  `vultron/core/models/events.py`; AS2 structural enums in
  `vultron/wire/as2/enums.py` (VCR Batch C)

**Still at top level:**

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

- `generate_new_id()` in `vultron/wire/as2/vocab/base/utils.py` — add a default
  `prefix` based on object type
- Demo scripts and tests that assert on `as_id` format
- `/datalayer/{key}` route in
  `vultron/adapters/driving/fastapi/routers/datalayer.py`
- Any handler that constructs participant or case IDs inline

---

## Test Directory Layout (TECHDEBT-11, resolved)

After P60-1 and P60-2 (package relocations), the test directories
`test/as_vocab/` and `test/behaviors/` were migrated to their new locations.

**Status**: All test directories now match the source layout:

- `test/wire/as2/vocab/` ✅ — parallel to `vultron/wire/as2/vocab/`
- `test/core/behaviors/` ✅ — parallel to `vultron/core/behaviors/`
- `test/as_vocab/` — removed ✅
- `test/behaviors/` — removed ✅

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
  shim. See `specs/prototype-shortcuts.md` PROTO-08-001, PROTO-08-002.
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
`triggers/_helpers.py` can re-export from `_helpers.py` for callers already
inside the `triggers` package.

**Corollary**: Core domain model classes (e.g., `VultronCase`) should
implement the same interface methods as their wire-layer counterparts (e.g.,
`record_event()`) so that Protocol guards like `is_case_model()` return
`True` for both families. Avoid making the Protocol guard depend on the
concrete wire-layer class.
