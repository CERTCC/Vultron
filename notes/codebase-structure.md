---
title: Codebase Structure Notes
status: active
kind: guidance
tags: [architecture, codebase, circular-imports, fastapi, docker, health-check, actor-ids]
description: >
  Module layout rules and recurring pitfalls: enum placement, the legacy
  simulator boundary, demo lifecycle helpers, FastAPI routing and serialization,
  actor-ID normalization, surrogate-key lookup, module splits, formatter and
  type-checker interplay, and small coding habits.
related_specs:
  - specs/prototype-shortcuts.yaml
  - specs/code-style.yaml
  - specs/behavior-tree-node-design.yaml
  - specs/architecture.yaml
  - specs/http-protocol.yaml
  - specs/semantic-extraction.yaml
related_notes:
  - notes/bt-integration.md
  - notes/structured-logging.md
  - notes/docker-build.md
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

## Enum Placement

Put each new enum in the enums module of the layer that owns the concept, so it is
easy to find and does not drag a dependency upward:

- `vultron/enums/` — the neutral bottom layer (`CVDRole` and its helpers); it MUST NOT
  import from `vultron/core/` or `vultron/config/` (ADR-0031).
- `vultron/core/states/` — the authoritative CS/RM/EM/PEC state enums.
- `vultron/enums/object_types.py` — object and actor type enums shared across core
  models (`vultron/core/models/enums.py` only re-exports them; do not add there).
- `vultron/wire/as2/enums.py` — AS2 structural enums.

`vultron/core/case_states/patterns/` holds the legacy 6-character case-state pattern
tables, a reference model only (ADR-0060).

When `core` needs a domain-concept enum that lives in `vultron/bt/` or
`vultron/core/case_states/`, move the enum into its owning `core` module instead of
adding a new import from the legacy tree. BT-engine internals stay in `vultron/bt/`.
An area with many enums gets an `enums/` subpackage, not one large `enums.py`.

### CVD roles are a `list[CVDRole]`, not a `Flag`

Core and wire code represent CVD roles as `list[CVDRole]`, the `StrEnum` in
`vultron/enums/roles.py`; membership is `CVDRole.VENDOR in participant.roles`. The
bitwise `CVDRolesFlag` in `vultron/bt/roles/enums.py` is for the legacy simulator only
and MUST NOT spread beyond `vultron/bt/`.

---

## Module Boundary: `vultron/bt/` vs `vultron/core/behaviors/`

| Module | Purpose | BT engine | Status |
|--------|---------|-----------|--------|
| `vultron/bt/` | Original simulation | Custom (`vultron.bt.base`) | Legacy; do not modify for prototype handlers |
| `vultron/core/behaviors/` | Prototype handler BTs | `py_trees` | Active development |

The two trees MUST NOT be merged or confused. See `notes/bt-integration.md` for the BT
layer's design.

### Demo layer MUST NOT import the legacy simulator (ARCH-01-006)

`vultron/demo/` demonstrates the production protocol, so demo logic modules
(`scenario/`, `exchange/`, `helpers/`, `fuzzer/`) MUST NOT import `vultron/bt/`. The
one exception is the CLI aggregator `vultron/demo/cli.py` (DC-01-001), which surfaces
the standalone simulator demos in `vultron/bt/base/demo/` as a sub-group.

**Relocate, don't re-launder.** A demo module that needs simulator symbols moves into
`vultron/bt/base/demo/`; it never re-exports them through `vultron/core/`, which would
pull the frozen legacy engine into the production dependency graph. Enforced by
`test/architecture/test_demo_no_bt_imports.py`.

---

## Demo Script Lifecycle Logging: `demo_step` / `demo_check` / `demo_gate`

Wrap every demo workflow step and verification in the context managers from
`vultron/demo/utils.py`. All three log entry and outcome, accumulate a failure instead
of re-raising, and need `assert_demo_success()` at the end of the scenario to surface
failures (DEMOCI-01-003/004):

- `demo_step` — a workflow step; execution continues after the block on failure.
- `demo_check` — a side-effect verification whose failure must not skip later work.
- `demo_gate` — a causal precondition: on failure the rest of the gate body is
  skipped, so dependent steps go inside it and do not produce meaningless secondary
  failures (ADR-0058).

When to use which is in `vultron/demo/AGENTS.md`; behavior is pinned by
`test/demo/test_demo_context_managers.py`. Standalone maintenance tooling belongs in
`vultron/metadata/`, not `vultron/demo/`.

---

## Starlette Path-Type Parameters for URL-Keyed Endpoints

An endpoint whose key may contain `/` (a full-URI ID) uses the `{param:path}`
converter, not `{param}`. Starlette decodes `%2F` to `/` before route matching, so
percent-encoding is no client-side workaround. Register a `/{param:path}` catch-all
**last**: Starlette matches in registration order, and an early catch-all shadows every
later literal route.

Registering it last is not enough when a route ahead of it takes two placeholders.
`/{object_type}/{object_id}` matches any key holding exactly one `/`, so it claimed
a `VultronOfferRecord` id (`offer-record/urn%3Auuid%3A…` — `build_id`
percent-quotes the suffix, and a server decodes the path once before it matches),
read only the segment after the slash, and answered 404 for a row the store held
(#5529). A key is one string: a route that splits one across placeholders falls
back to the whole matched path as the key before it reports 404 — keep the route
and read the suffix first, so a URL that works today keeps working. A key whose
suffix also names a row stays shadowed by it; the quoting is what keeps the two
sets apart.

---

## FastAPI response_model Filtering

FastAPI treats a return annotation as an implicit `response_model` and serializes only
the annotated class's fields, so `-> as_Base` silently drops every subclass field
(HTTP-08-001).

- **AS2 routes** return `AS2JSONResponse(obj)`, which dumps by alias and bypasses the
  filter (HTTP-09-002).
- **Other routes** returning several types drop the annotation or annotate the exact
  `Union`. Do not use `AS2JSONResponse` on non-AS2 routes.
- **Trigger routes declare `response_model` on purpose** (TRIG-12-001, ADR-0110): each
  `TriggerResult` subtype is the verb's exact key set with `extra="forbid"`, so there
  is nothing to drop and the declaration puts the body into OpenAPI. Pinned by
  `test/adapters/driving/fastapi/test_trigger_routes_contract.py`.

Test the JSON response, not only what was stored.

---

## Docker Health Check Coordination

`depends_on: service_started` waits for the container, not the app, so a dependent
container can get "Connection refused". Use all three layers: a `healthcheck` on the
API service (`/api/v2/health/live`), `condition: service_healthy` on its dependents,
and client retry against the server (use `httpx2`, the declared runtime dependency,
not `requests`). See `docker/docker-compose.yml`.

---

## The Formatter Can Invalidate Inline Type-Checker Suppressions

When `ruff format` wraps a long line, an end-of-line `# type: ignore` or `# pyright:
ignore` stays on the statement's last line, away from the expression it suppressed; the
error returns and the pragma reports as unused. Re-run mypy and pyright after every
format pass (the `run-linters` order does), and move the pragma onto the line carrying
the flagged argument. A file-level `# pyright: reportGeneralTypeIssues=false` is
acceptable only for a Pydantic subclass that intentionally narrows an optional base
field to required (see `vultron/wire/as2/vocab/objects/case_proposal.py`).

---

## Actor IDs

### Actor IDs Must Always Be Full URIs

Normalize an actor ID to a full URI where it is first established (actor creation, seed
load, session context); nothing downstream handles a short UUID as an actor ID. Short
IDs break semantic routing, outbox addressing, and trust-boundary checks, and let one
actor appear under two IDs in the DataLayer.

### Actor ID Normalization in Trigger Paths: Resolve Path Params Before Outbox

A trigger path that accepts a short actor ID from a route parameter overwrites
`actor_id` with the resolved `actor.id_` before any outbox mutation. The SQLite
DataLayer's bare-UUID compatibility lookup hides the bug for `urn:uuid:` IDs, so
regression tests MUST use URL-form actor records, and should assert both the outbox
mutation and the absence of a warning log (BUG-26042202).

---

## Surrogate-Key Routing

Routes accept short-ID surrogate keys beside canonical URIs
(`find_actor_by_short_id()` / `find_case_by_short_id()` in
`vultron/adapters/driven/datalayer_sqlite/queries.py`). Two invariants (ISSUE-654):

- **Ambiguity is a miss, never first-match.** More than one canonical ID matching a
  tail segment logs a WARNING and returns `None`; first-match makes lookups
  non-deterministic.
- **A non-case hit does not end case-key resolution.** When `dl.read(key)` returns a
  non-case object, continue to the short-key fallback, or non-case IDs shadow valid case
  keys with false 404s.

When asserting a mock's positional arguments, use `call_args.args`, not `call_args[0]`:
the named attribute fails clearly if the call moves to kwargs.

---

## Circular Imports: Shared Helpers in `use_cases/_helpers.py`

A helper needed by both `vultron/core/behaviors/` and
`vultron/core/use_cases/triggers/` lives in `vultron/core/use_cases/_helpers.py`.
The `triggers/` submodules import the behaviors layer, so a behaviors module that
imports anything under `triggers/` closes a cycle.

---

## Router Test Overrides

Override the per-actor dependency, not a module binding:
`app.dependency_overrides[get_actor_dl]` for routes with an actor path segment (it
replaces canonical-URI resolution too), `get_trigger_dl` for trigger routes, and
`get_hosted_actor_dls` for node-wide routes (all in
`vultron/adapters/driving/fastapi/deps.py`; ADR-0073). The
engine cache is keyed on the resolved per-actor URL, so a test that needs a fresh store
calls `dispose_actor_engines()`; in in-memory mode that also destroys the database.

---

## Cross-Actor TestClient Router: Keep Blocking `post()` off the Portal Loop

In the multi-actor demo harness (`test/demo/conftest.py`), the router's `emit()` runs
on the sending app's `TestClient` portal loop, while `TestClient.post()` blocks and
drives the target through its own portal. Calling it inline blocks the sender and can
deadlock the two portals, so the harness runs the post through
`anyio.to_thread.run_sync`. It posts the sealed body as-is (`content=`, not `json=`),
never re-serializing what the ledger recorded (VM-08-003).

---

## Phrase Tests Using `defaultdict` Cannot Detect Unfillable Slots

Rendering a phrase with `format_map(defaultdict(...))` fills every slot, so it passes a
phrase referencing a slot the real renderer never fills. The real pipeline
(`CaseTimelineEvent.summary` in `vultron/demo/report.py`) fills only `actor` and,
when `target_label` resolves, `object`/`target`. A phrase regression test builds a
representative `CaseTimelineEvent` and asserts its `summary` has no trailing `—`
and no unsubstituted `{slot}` (SE-07). `event_phrase()` fills every slot with `—`,
so a test through it is the vacuous kind this section warns against.

---

## Logger Names: Verify from Source, Not Assumption

Read a logger's name from the source before writing a log filter or a `caplog` scope;
module paths mislead. The actors router logs as `uvicorn.error`, and a BT node bound
through `node_logger(node)` logs under its class-qualified name (for example
`vultron.core.behaviors.sync.nodes.chain.PersistLogEntryNode`). Scope `caplog` to the
class-qualified name to avoid sibling nodes' records.

---

## Docstring and Markdown Compatibility

Docstrings render through `mkdocstrings`, so they use markdown: a blank line before
every list, backticks for any code-like text, and links relative to `docs/` with the
target page title as link text. The deployment entrypoint is
`vultron.adapters.driving.fastapi.main:app`; `vultron.api.main:app` is stale. FastAPI's
OpenAPI pages (`/docs`, `/redoc`) are generated from route docstrings and Pydantic field
descriptions, so keep those accurate and put new endpoints on the right router.

---

## Bulk Module Renames

- Find every caller first (`grep -r "from old.path\|import old.path" vultron/ test/`),
  then bulk-replace with `sed`.
- Mirror the move in `test/`, with an `__init__.py`, so pytest discovers the tests.
- Leave no shim at the old path: a clean test run then proves every caller moved
  (PROTO-08-001). A split differs: see the next section.

---

## Module Splits: No New God Modules, Always Re-Export

- **A split must not produce a new god module.** Submodules stay at or under 500 lines
  and are split again when they re-accumulate (CS-18-001). A BT process area's leaf
  modules go in a `nodes/` subpackage grouped by semantic concern (BTND-07-001).
- **Check `wc -l` before documenting a leaf.** A BT leaf module within ~20 lines of the
  500-line cap (BTND-07-004) is split before docstrings or audit comments are added.
- **A split re-exports what it moved, only where the old name is still a live
  interface.** A use-case subpackage re-exports its classes and their request models
  as its public API; a module split re-imports a moved name in the old module
  (`# noqa: F401`) only when it is a `monkeypatch` target; a FastAPI router package
  re-exports the names used as `dependency_overrides` keys (#972). Anything else is
  a shim (PROTO-08-001): move the callers.
- **Deleting a module instead of re-exporting needs importer proof**: no live importers
  in `vultron/` or `test/`.

---

## Small Coding Habits

- **mypy infers a variable's type from its first assignment.** Use distinct names per
  `except` or `if`/`else` branch rather than reusing one name with different types.
- **Pre-build dedup sets before fallback loops** — `seen = set(d.values())` turns an
  O(n×m) membership scan into O(n+m).
- **Use the walrus operator for single-assignment guards**:
  `if (f := self._require_factory()) is not None:`.

---

## Protocol Declarations Stay in Sync With Concrete Classes (CS-20)

When a field or method leaves a class that structurally conforms to a `Protocol`
(`vultron/core/models/protocols.py`, `vultron/core/ports/`), remove the matching
Protocol member too, and vice versa (CS-20-001): type checkers never flag a Protocol
member no implementation still has. A new `TypeGuard` discriminator MAY `hasattr`-check
only Protocol-declared members (CS-20-002).

---

## `HashChainLedgerRecord` ≠ `CaseLedgerEntry`

`HashChainLedgerRecord` (`core/models/case_ledger.py`) is the in-memory hash-chain
record, a plain `BaseModel`; `CaseLedgerEntry` (`core/models/case_ledger_entry.py`) is
the wire-serializable `CoreObject` (ARCH-12-007). Import each by its full module path.
