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
  - notes/codebase-structure-fastapi-patterns.md
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

### Demo layer MUST NOT import the legacy simulator (ARCH-01-006)

`vultron/demo/` demonstrates the **production** protocol (API server, core, and
wire layers). It MUST NOT import from the legacy `vultron/bt/` simulator, with
one exception: the unified demo CLI aggregator `vultron/demo/cli.py`
(mandated by DC-01-001) is permitted to import the standalone `vultron/bt/`
behaviour-tree demos (pacman, robot, cvd) so it can surface them as a
`vultrabot` sub-group. Demo *logic* modules — `scenario/`, `exchange/`,
`helpers/`, `fuzzer/` — MUST stay free of any `vultron/bt/` import.

The standalone behaviour-tree demos live **inside** the simulator tree, at
`vultron/bt/base/demo/` (`pacman.py`, `robot.py`, `cvd.py`). The CVD
self-simulation demo `cvd.py` was relocated there from `vultron/demo/vultrabot.py`
(issue #1375); it is a demo *of* the legacy simulator, not of the production
protocol, so it belongs with its siblings.

**Relocate, don't re-launder.** When a `vultron/demo/` module genuinely needs
legacy-simulator symbols (`CvdProtocolBt`, `CVDRolesFlag`, `show_graph`, etc.),
the fix is to move that module into `vultron/bt/base/demo/` — NOT to re-export
the legacy symbols through `vultron/core/`. Re-exporting simulator internals via
the core domain would pull the frozen legacy engine into the production
dependency graph, a worse layering violation than the one being fixed.

Enforced by the AST ratchet `test/architecture/test_demo_no_bt_imports.py`
(`KNOWN_VIOLATIONS` lists only `vultron/demo/cli.py`), following the ARCH-18
bidirectional-equality pattern.

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

> See also: [codebase-structure-fastapi-patterns.md](codebase-structure-fastapi-patterns.md) for the continuation of these design notes.
