# Codebase Structure Notes

## Top-Level Module Reorganization (Future Refactoring)

Several top-level modules in `vultron/` were created at the top level for
development convenience but are candidates for reorganization into submodules
as the codebase matures. This is not a high priority for the prototype, but
worth tracking.

**Candidates for reorganization:**

- `vultron/activity_patterns.py` — pattern definitions; could move to
  `vultron/dispatch/` or `vultron/messaging/`
- `vultron/behavior_dispatcher.py` — dispatch logic; same candidate submodule
- `vultron/dispatcher_errors.py` — currently kept at top level to avoid
  circular imports; see `specs/code-style.md` CS-05-001
- `vultron/enums.py` — primary enum registry; see Enum Refactoring section
  below
- `vultron/errors.py` — top-level error base; submodule errors already exist
  at `vultron/api/v2/errors.py`
- `vultron/semantic_handler_map.py` — handler registry
- `vultron/semantic_map.py` — semantics-to-pattern registry
- `vultron/types.py` — shared type aliases; a neutral module used to break
  circular import chains

**Constraint**: `dispatcher_errors.py` and `types.py` MUST remain accessible
to both core dispatch modules and `api/v2/` without creating circular imports.
Any reorganization MUST preserve this constraint. See `AGENTS.md` "Circular
Imports" section for the import chain rules.

---

## Enum Refactoring

Enums are currently scattered across multiple locations in the codebase:

- `vultron/enums.py` — primary application-layer enums (e.g., `MessageSemantics`)
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
- `vultron/as_vocab/` — vocabulary-level type enums

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

## Module Boundary: `vultron/bt/` vs `vultron/behaviors/`

These two trees coexist and MUST NOT be merged or confused:

| Module | Purpose | BT Engine | Status |
|--------|---------|-----------|--------|
| `vultron/bt/` | Original simulation (custom engine) | Custom (`vultron.bt.base`) | Legacy; do not modify for prototype handlers |
| `vultron/behaviors/` | Prototype handler BTs | `py_trees` (v2.2.0+) | Active development |

The `vultron/sim/` module also exists as another simulation-related module and
MUST NOT be confused with `vultron/bt/` or `vultron/behaviors/`.

See `notes/bt-integration.md` for architectural decisions about the BT
layer.

---

## Roadmap: Handlers Module Refactoring

The `vultron/api/v2/backend/handlers.py` module is well over a thousand lines
and growing. Consider organizing handlers into submodules in a
`vultron/api/v2/backend/handlers/` directory, grouped by topic (e.g.,
`report.py`, `case.py`, `embargo.py`, `actor.py`, `notes.py`, `status.py`).

**Constraint**: The `SEMANTIC_HANDLER_MAP` import in `vultron/semantic_handler_map.py`
must stay importable from the same logical location. If handlers are split
into submodules, `handlers/__init__.py` should re-export all handler functions
and the submodule organization should mirror the vocabulary example module
reorganization (see below) for consistency.

**Priority**: Not urgent during initial demos. Tackle after the last handler
stubs are filled (Phase BT-7).

---

## Roadmap: Vocab Examples Module Refactoring

`vultron/scripts/vocab_examples.py` is used by demo scripts, the documentation
build pipeline, and as test fixtures. It has grown beyond a simple script into
a de-facto module. Consider moving it to `vultron/as_vocab/examples/` with
submodules organized by topic (mirroring the handler submodule topics above).

**Constraint**: Demo scripts and documentation build tools import from
`vultron.scripts.vocab_examples`. A refactor must update all import sites and
ensure backward compatibility (e.g., a compatibility shim or re-export from the
old location).

**Priority**: Not urgent during prototype. Coordinate with handlers refactoring
so the two share a consistent topic taxonomy.

---

## Demo Scripts Belong in `vultron/demo/`, Not `vultron/scripts/`

The `vultron/scripts/*_demo.py` files demonstrate end-to-end workflows and are
not standalone utility scripts. They should move to `vultron/demo/` to clarify
their role:

- **`vultron/scripts/`** — intended for standalone utilities users run directly
  (data migration, maintenance, one-off tooling)
- **`vultron/demo/`** — end-to-end workflow demonstrations, depended on by
  tests and Docker configs

**Affected files when relocating**:

- `vultron/scripts/receive_report_demo.py`
- `vultron/scripts/initialize_case_demo.py`
- `vultron/scripts/invite_actor_demo.py`
- `vultron/scripts/establish_embargo_demo.py`
- Corresponding test files in `test/scripts/`
- Docker Compose service definitions in `docker/docker-compose.yml`
- Any import paths in tests or documentation

**Priority**: Not urgent; complete demo set first, then migrate.

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
